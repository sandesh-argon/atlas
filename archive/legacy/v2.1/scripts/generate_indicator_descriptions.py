#!/usr/bin/env python3
"""
Generate Plain English Indicator Descriptions using Claude API

This script processes indicators in batches by source and generates
human-readable descriptions at 9th-12th grade reading level.
"""

import json
import os
import sys
import time
from pathlib import Path
from typing import Dict, List, Any, Optional
import anthropic

# Configuration
API_KEY = os.getenv("ANTHROPIC_API_KEY", "")
MODEL = "claude-sonnet-4-20250514"
BATCH_SIZE = 15  # Process 15 indicators per API call
OUTPUT_DIR = Path("outputs/B1_indicator_descriptions")

# Source-specific context for better descriptions
SOURCE_CONTEXT = {
    "V-Dem": """
V-Dem (Varieties of Democracy) measures democracy and governance across 200+ countries using expert surveys.

Common V-Dem code patterns:
- Prefix v2x_ = composite indices (aggregate scores combining multiple indicators)
- Prefix v2 = specific questions from expert surveys
- v2el = Elections, v2ex = Executive, v2juh = Judiciary, v2dl = Deliberation
- v2cl = Civil Liberties, v2ca = Civil Society, v2me = Media, v2sm = Social Media
- v2pe = Political Equality, v2reg = Regime, v2ed = Education
- Suffixes: _ord = ordinal, _mean = averaged, _nr = non-response, _0/1/2... = specific categories

Scale: Most V-Dem scores range 0-1 or 0-4, where higher values generally indicate more democratic/positive outcomes.
""",

    "World Bank": """
World Bank World Development Indicators (WDI) cover economic, social, and environmental data for 217 countries.

Common patterns:
- NW.* = National Wealth accounts (human capital, natural capital, produced capital)
- SP.* = Social Protection, Population statistics
- SE.* = Education statistics
- SH.* = Health statistics
- NY.* = National accounts (GDP, GNI)
- Units vary: USD (current or constant), percentages, per capita, per 1,000 people

Time coverage: 1960-2023 for most indicators.
""",

    "WID": """
World Inequality Database (WID) tracks income and wealth inequality within and between countries.

Code structure (e.g., mprpfci999):
- First letter: a=average, m=median, s=share, t=threshold
- Second part: income type
  - pr/prp = pre-tax income
  - nw = net wealth
  - fi = fiscal income (post-tax)
  - hw = housing wealth
  - sec = sectoral
- Last 3 digits: age group
  - 992 = adults (age 20+)
  - 999 = all ages

Units: Usually local currency in real terms (inflation-adjusted) or purchasing power parity.
""",

    "UNESCO": """
UNESCO Institute for Statistics tracks education data globally.

Common patterns:
- ISCED levels: 0=pre-primary, 1=primary, 2=lower secondary, 3=upper secondary, 5-8=tertiary
- Demographic splits: M/F (gender), urban/rural, Q1-Q5 (income quintiles)
- TRTP = Teacher training, ROFST = Out-of-school rate
- Gross enrollment can exceed 100% (includes over/under-age students)
- Net enrollment: only age-appropriate students, max 100%
""",

    "QoG": """
Quality of Government Institute compiles governance, institutional, and policy data from many sources.

Common prefixes:
- ccp_ = Comparative Constitutions Project (constitutional provisions)
- ciri_ = CIRI Human Rights Data (human rights practices)
- wbgi_ = World Bank Governance Indicators
- atop_ = Alliance Treaty Obligations and Provisions

Many indicators are binary (0/1) or ordinal scales (0-2, 0-4).
""",

    "PWT": """
Penn World Table provides internationally comparable economic data using purchasing power parity (PPP).

Common codes:
- ctfp = Total Factor Productivity (at current PPPs)
- csh_* = Component shares of GDP (c=consumption, i=investment, g=government, x=exports, m=imports)
- rgdp = Real GDP, cgdp = Current GDP
- hc = Human capital index
- emp = Employment, avh = Average hours worked

Scale: Economic values in PPP-adjusted international dollars; shares as decimals (0-1).
"""
}


def get_source_context(source: str) -> str:
    """Get context string for a given source."""
    for key, context in SOURCE_CONTEXT.items():
        if key.lower() in source.lower():
            return context
    return "General development indicator. Interpret based on the indicator name and code patterns."


def create_batch_prompt(indicators: List[Dict], source: str) -> str:
    """Create a prompt for a batch of indicators."""

    source_context = get_source_context(source)

    indicators_text = "\n".join([
        f"- ID: {ind['id']}\n  Current Label: {ind['label']}\n  Current Description: {ind.get('description', '') or '(none)'}"
        for ind in indicators
    ])

    prompt = f"""You are an expert in international development data. Generate plain English descriptions for these indicators that a high school graduate can understand.

SOURCE: {source}

SOURCE CONTEXT:
{source_context}

INDICATORS TO DESCRIBE:
{indicators_text}

For each indicator, provide:
1. **What it measures** (1-2 sentences, concrete and specific)
2. **How to interpret values** (scale/units, direction - is higher better or worse?)
3. **Why it matters** (1 sentence connecting to quality of life)

REQUIREMENTS:
- Target 9th-12th grade reading level (Flesch-Kincaid)
- Avoid jargon - explain any technical terms
- Be specific about what "higher" or "lower" values mean
- Use concrete examples where helpful
- Keep total description to 2-4 sentences (50-150 words)

OUTPUT FORMAT (valid JSON):
{{
  "indicator_id_1": {{
    "label": "Improved human-readable label",
    "description": "Full plain English description combining what it measures, interpretation, and importance."
  }},
  "indicator_id_2": {{
    ...
  }}
}}

Generate descriptions for all {len(indicators)} indicators above. Return ONLY valid JSON, no markdown code blocks."""

    return prompt


def call_claude_api(prompt: str, max_retries: int = 3) -> Optional[Dict]:
    """Call Claude API and parse response."""

    client = anthropic.Anthropic(api_key=API_KEY)

    for attempt in range(max_retries):
        try:
            response = client.messages.create(
                model=MODEL,
                max_tokens=4096,
                messages=[
                    {"role": "user", "content": prompt}
                ]
            )

            # Extract text content
            text = response.content[0].text

            # Clean up response - remove markdown code blocks if present
            if text.startswith("```"):
                text = text.split("```")[1]
                if text.startswith("json"):
                    text = text[4:]
            if text.endswith("```"):
                text = text[:-3]

            # Parse JSON
            result = json.loads(text.strip())
            return result

        except json.JSONDecodeError as e:
            print(f"  JSON parse error (attempt {attempt + 1}): {e}")
            if attempt < max_retries - 1:
                time.sleep(2)
        except anthropic.APIError as e:
            print(f"  API error (attempt {attempt + 1}): {e}")
            if attempt < max_retries - 1:
                time.sleep(5)
        except Exception as e:
            print(f"  Unexpected error (attempt {attempt + 1}): {e}")
            if attempt < max_retries - 1:
                time.sleep(2)

    return None


def process_source_batch(
    indicators: List[Dict],
    source: str,
    progress_callback=None
) -> Dict[str, Dict]:
    """Process all indicators from a source in batches."""

    all_results = {}
    total = len(indicators)

    for i in range(0, total, BATCH_SIZE):
        batch = indicators[i:i + BATCH_SIZE]
        batch_num = i // BATCH_SIZE + 1
        total_batches = (total + BATCH_SIZE - 1) // BATCH_SIZE

        print(f"  Processing batch {batch_num}/{total_batches} ({len(batch)} indicators)...")

        prompt = create_batch_prompt(batch, source)
        result = call_claude_api(prompt)

        if result:
            all_results.update(result)
            print(f"    Generated {len(result)} descriptions")
        else:
            print(f"    WARNING: Failed to process batch {batch_num}")
            # Add placeholder for failed indicators
            for ind in batch:
                all_results[ind['id']] = {
                    "label": ind['label'],
                    "description": f"[NEEDS MANUAL REVIEW] {ind.get('description', '')}"
                }

        # Rate limiting - be gentle with API
        if i + BATCH_SIZE < total:
            time.sleep(1)

        if progress_callback:
            progress_callback(min(i + BATCH_SIZE, total), total)

    return all_results


def load_indicators_by_source() -> Dict[str, List[Dict]]:
    """Load all indicators grouped by source."""

    with open('outputs/B1/indicator_labels_comprehensive.json', 'r') as f:
        labels = json.load(f)

    by_source = {}
    for ind_id, data in labels.items():
        if isinstance(data, dict):
            source = data.get('source', 'Unknown')
            indicator = {
                'id': ind_id,
                'label': data.get('label', ind_id),
                'description': data.get('description', ''),
                'source': source
            }
        else:
            source = 'Unknown'
            indicator = {
                'id': ind_id,
                'label': data,
                'description': '',
                'source': source
            }

        if source not in by_source:
            by_source[source] = []
        by_source[source].append(indicator)

    return by_source


def save_progress(results: Dict, source: str):
    """Save intermediate results."""
    safe_source = source.replace(' ', '_').replace('/', '_')[:30]
    filepath = OUTPUT_DIR / f"descriptions_{safe_source}.json"
    with open(filepath, 'w') as f:
        json.dump(results, f, indent=2)
    print(f"  Saved to {filepath}")


def main():
    """Main entry point."""

    print("=" * 60)
    print("INDICATOR DESCRIPTION GENERATOR")
    print("=" * 60)

    # Ensure output directory exists
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    # Load indicators
    print("\nLoading indicators...")
    by_source = load_indicators_by_source()

    total_indicators = sum(len(v) for v in by_source.values())
    print(f"Loaded {total_indicators} indicators from {len(by_source)} sources")

    # Process command line arguments
    if len(sys.argv) > 1:
        # Process specific source
        target_source = ' '.join(sys.argv[1:])
        matching_sources = [s for s in by_source.keys() if target_source.lower() in s.lower()]
        if not matching_sources:
            print(f"ERROR: No source matching '{target_source}'")
            print("Available sources:", list(by_source.keys()))
            return
        sources_to_process = matching_sources
    else:
        # Process all sources (sorted by count, largest first)
        sources_to_process = sorted(by_source.keys(), key=lambda x: -len(by_source[x]))

    # Process each source
    all_descriptions = {}

    for source in sources_to_process:
        indicators = by_source[source]
        print(f"\n{'='*60}")
        print(f"Processing: {source} ({len(indicators)} indicators)")
        print("=" * 60)

        results = process_source_batch(indicators, source)
        all_descriptions.update(results)

        # Save intermediate progress
        save_progress(results, source)

    # Save combined results
    print(f"\n{'='*60}")
    print("SAVING COMBINED RESULTS")
    print("=" * 60)

    combined_path = OUTPUT_DIR / "all_descriptions.json"
    with open(combined_path, 'w') as f:
        json.dump(all_descriptions, f, indent=2)
    print(f"Saved {len(all_descriptions)} descriptions to {combined_path}")

    # Generate summary stats
    needs_review = [k for k, v in all_descriptions.items() if '[NEEDS MANUAL REVIEW]' in v.get('description', '')]
    print(f"\nSummary:")
    print(f"  Total processed: {len(all_descriptions)}")
    print(f"  Successful: {len(all_descriptions) - len(needs_review)}")
    print(f"  Needs review: {len(needs_review)}")


if __name__ == "__main__":
    main()
