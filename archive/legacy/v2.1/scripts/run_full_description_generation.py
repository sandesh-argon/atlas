#!/usr/bin/env python3
"""
Full Indicator Description Generation Pipeline

Processes all 1,962 indicators in batches by source using Claude API.
Includes progress tracking, reading level validation, and error handling.
"""

import json
import os
import sys
import time
import re
from pathlib import Path
from typing import Dict, List, Any, Optional, Tuple
from datetime import datetime
import anthropic

# Configuration
API_KEY = os.getenv("ANTHROPIC_API_KEY", "")
MODEL = "claude-sonnet-4-20250514"
BATCH_SIZE = 15  # Process 15 indicators per API call
OUTPUT_DIR = Path("outputs/B1_indicator_descriptions")
PROGRESS_FILE = OUTPUT_DIR / "progress.json"

# Source processing order
SOURCE_ORDER = [
    "V-Dem",      # 458 indicators
    "World Bank", # 237 indicators (WDI + other WB sources)
    "WID",        # 346 indicators
    "UNESCO",     # 454 indicators
    "QoG",        # 85 indicators
    "PWT",        # 26 indicators
    "Other"       # remaining ~356 indicators
]

# Source-specific context for better descriptions
SOURCE_CONTEXT = {
    "V-Dem": """
V-Dem (Varieties of Democracy) measures democracy and governance across 200+ countries using expert surveys.

Common V-Dem code patterns:
- Prefix v2x_ = composite indices (aggregate scores combining multiple indicators)
- Prefix v2 = specific questions from expert surveys
- v2el = Elections, v2ex = Executive, v2juh = Judiciary, v2dl = Deliberation
- v2cl = Civil Liberties, v2ca = Civil Society, v2me = Media, v2sm = Social Media
- v2pe = Political Equality, v2reg = Regime, v2ed = Education, v2sv = State capacity
- v2xpe = Political equality indices, v2xdd = Direct democracy
- Suffixes: _ord = ordinal version, _mean = averaged, _nr = non-response rate, _osp = original scale point
- Number suffixes (e.g., _0, _1, _2) = specific category values

Scale: Most V-Dem scores range 0-1 or 0-4, where higher values generally indicate more democratic/positive outcomes.

IMPORTANT for _nr (non-response) indicators: These measure data quality/coverage, not the phenomenon itself.
""",

    "World Bank": """
World Bank World Development Indicators (WDI) and related databases cover economic, social, and environmental data for 217 countries.

Common patterns:
- NW.* = National Wealth accounts (human capital, natural capital, produced capital)
- SP.* = Social Protection, Population statistics
- SE.* = Education statistics
- SH.* = Health statistics
- NY.* = National accounts (GDP, GNI)
- SL.* = Labor statistics
- AG.* = Agriculture
- EN.* = Environment
- EG.* = Energy
- IT.* = ICT/Technology
- BX.*, BM.* = Balance of payments
- GC.* = Government/fiscal
- IC.* = Investment climate/business

Units vary: USD (current or constant), percentages, per capita, per 1,000 people
Time coverage: 1960-2023 for most indicators.
""",

    "WID": """
World Inequality Database (WID) tracks income and wealth inequality within and between countries.

Code structure decoded (e.g., mprpfci999, anwoffi992):

First letter(s) - statistic type:
- a = average
- m = median
- s = share (of total)
- t = threshold (entry point for top X%)
- g = gini coefficient

Middle letters - income/wealth type:
- prp, pr = pre-tax national income
- ptp = post-tax income
- nw = net wealth
- hw = housing wealth
- fi = fiscal income
- fw = financial wealth
- sec = sectoral income
- cap = capital income
- lab = labor income
- mix = mixed income
- weal = wealth

Last 3 digits - population:
- 992 = adults only (age 20+)
- 999 = all ages (total population)

Additional codes:
- c, i, n at end = country-specific adjustments
- f, m = female/male
- top, bot, mid = income distribution position

Examples:
- mprpfci999 = median pre-tax fiscal income, all ages
- anwoffi992 = average net wealth, adults
- sptinc992 = share of post-tax income, adults
""",

    "UNESCO": """
UNESCO Institute for Statistics (UIS) tracks education data globally.

Common patterns:
- ISCED levels: 02=pre-primary, 1=primary, 2=lower secondary, 3=upper secondary, 5-8=tertiary
- ROFST = Out-of-school rate
- TRTP = Teacher training percentage
- PTR = Pupil-teacher ratio
- GER = Gross enrollment rate (can exceed 100% if over/under-age students enrolled)
- NER = Net enrollment rate (only age-appropriate, max 100%)
- CR = Completion rate
- LR = Literacy rate

Demographic splits:
- M/F or .M/.F = Male/Female
- .T = Total (both sexes)
- Q1-Q5 = Income quintiles (Q1=poorest, Q5=richest)
- .URB/.RUR = Urban/Rural

Grade levels:
- Primary typically ages 6-11
- Lower secondary (grades 7-9) typically ages 12-14
- Upper secondary (grades 10-12) typically ages 15-17
""",

    "QoG": """
Quality of Government Institute (QoG) compiles governance, institutional, and policy data from many sources.

Common prefixes and their sources:
- ccp_ = Comparative Constitutions Project (constitutional provisions, 0/1 binary)
- ciri_ = CIRI Human Rights Data (human rights practices, 0-2 scale)
- wbgi_ = World Bank Governance Indicators
- fh_ = Freedom House scores
- ti_ = Transparency International
- wef_ = World Economic Forum
- bti_ = Bertelsmann Transformation Index
- eiu_ = Economist Intelligence Unit
- rsf_ = Reporters Sans Frontières (press freedom)
- atop_ = Alliance Treaty Obligations
- ucdp_ = Uppsala Conflict Data
- br_ = Regional barometers

Many QoG indicators are binary (0=no, 1=yes) or ordinal scales (0-2 or 0-4).
Higher values typically indicate presence of a feature or better performance.
""",

    "PWT": """
Penn World Table (PWT) provides internationally comparable economic data using purchasing power parity (PPP).

Common codes:
- rgdp* = Real GDP variants
- cgdp* = Current price GDP
- ctfp = Total Factor Productivity at current PPPs
- rtfp = TFP at constant national prices
- csh_* = Component shares of GDP:
  - csh_c = consumption share
  - csh_i = investment share
  - csh_g = government share
  - csh_x = exports share
  - csh_m = imports share (negative)
  - csh_r = residual trade
- hc = Human capital index (based on schooling + returns)
- emp = Employment (millions)
- avh = Average annual hours worked
- labsh = Labor share of GDP
- irr = Internal rate of return on capital
- delta = Depreciation rate
- rkna, rnna = Capital stock measures
- pop = Population
- pl_* = Price level indices

Scale: Economic values in PPP-adjusted international dollars (2017 base); shares as decimals (0-1).
""",

    "Other": """
Various other data sources including:
- IHME (Institute for Health Metrics) - health outcomes, disease burden
- FAO (Food and Agriculture Organization) - agriculture, food security, land use
- ILO (International Labour Organization) - employment, working conditions
- IMF (International Monetary Fund) - fiscal, monetary, financial data
- UNEP (UN Environment Programme) - environmental indicators
- WHO (World Health Organization) - health system indicators
- OECD - economic and social data for developed countries
- Regional databases (African Development Bank, Asian Development Bank, etc.)

Interpret based on indicator name and standard development metrics conventions.
"""
}


def get_source_context(source: str) -> str:
    """Get context string for a given source."""
    for key, context in SOURCE_CONTEXT.items():
        if key.lower() in source.lower():
            return context
    return SOURCE_CONTEXT["Other"]


def estimate_reading_level(text: str) -> float:
    """Estimate Flesch-Kincaid Grade Level without external library."""
    if not text:
        return 0.0

    # Count sentences (rough estimate)
    sentences = len(re.findall(r'[.!?]+', text)) or 1

    # Count words
    words = text.split()
    word_count = len(words) or 1

    # Count syllables (rough estimate)
    def count_syllables(word):
        word = word.lower()
        count = 0
        vowels = "aeiouy"
        prev_vowel = False
        for char in word:
            is_vowel = char in vowels
            if is_vowel and not prev_vowel:
                count += 1
            prev_vowel = is_vowel
        if word.endswith('e'):
            count -= 1
        return max(1, count)

    syllables = sum(count_syllables(w) for w in words)

    # Flesch-Kincaid Grade Level formula
    fk_grade = 0.39 * (word_count / sentences) + 11.8 * (syllables / word_count) - 15.59
    return max(0, min(20, fk_grade))


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
- For "_nr" (non-response) indicators: explain these measure data availability, not the phenomenon itself

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

Generate descriptions for all {len(indicators)} indicators above. Return ONLY valid JSON, no markdown code blocks or other text."""

    return prompt


def call_claude_api(prompt: str, max_retries: int = 3) -> Optional[Dict]:
    """Call Claude API and parse response."""

    client = anthropic.Anthropic(api_key=API_KEY)

    for attempt in range(max_retries):
        try:
            response = client.messages.create(
                model=MODEL,
                max_tokens=8192,
                messages=[
                    {"role": "user", "content": prompt}
                ]
            )

            # Extract text content
            text = response.content[0].text

            # Clean up response - remove markdown code blocks if present
            if "```" in text:
                # Extract content between code blocks
                match = re.search(r'```(?:json)?\s*([\s\S]*?)\s*```', text)
                if match:
                    text = match.group(1)
                else:
                    # Try to find JSON object directly
                    text = text.replace("```json", "").replace("```", "")

            text = text.strip()

            # Parse JSON
            result = json.loads(text)
            return result

        except json.JSONDecodeError as e:
            print(f"    JSON parse error (attempt {attempt + 1}): {e}")
            print(f"    Response preview: {text[:200] if 'text' in dir() else 'N/A'}...")
            if attempt < max_retries - 1:
                time.sleep(2)
        except anthropic.APIError as e:
            print(f"    API error (attempt {attempt + 1}): {e}")
            if attempt < max_retries - 1:
                time.sleep(5)
        except Exception as e:
            print(f"    Unexpected error (attempt {attempt + 1}): {type(e).__name__}: {e}")
            if attempt < max_retries - 1:
                time.sleep(2)

    return None


def load_progress() -> Dict:
    """Load progress from file."""
    if PROGRESS_FILE.exists():
        with open(PROGRESS_FILE, 'r') as f:
            return json.load(f)
    return {
        "completed_sources": [],
        "all_descriptions": {},
        "failed_indicators": [],
        "stats": {}
    }


def save_progress(progress: Dict):
    """Save progress to file."""
    progress["last_updated"] = datetime.now().isoformat()
    with open(PROGRESS_FILE, 'w') as f:
        json.dump(progress, f, indent=2)


def load_indicators_by_source() -> Dict[str, List[Dict]]:
    """Load all indicators grouped by source category."""

    with open('outputs/B1/indicator_labels_comprehensive.json', 'r') as f:
        labels = json.load(f)

    by_category = {cat: [] for cat in SOURCE_ORDER}

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

        # Categorize into our processing groups
        categorized = False
        for category in SOURCE_ORDER[:-1]:  # Exclude "Other"
            if category.lower() in source.lower():
                by_category[category].append(indicator)
                categorized = True
                break

        if not categorized:
            by_category["Other"].append(indicator)

    return by_category


def process_source(
    source_name: str,
    indicators: List[Dict],
    progress: Dict
) -> Tuple[Dict[str, Dict], List[str], Dict]:
    """Process all indicators from a source category."""

    results = {}
    failed = []
    reading_levels = []

    total = len(indicators)
    print(f"\n{'='*70}")
    print(f"PROCESSING: {source_name} ({total} indicators)")
    print(f"{'='*70}")

    for i in range(0, total, BATCH_SIZE):
        batch = indicators[i:i + BATCH_SIZE]
        batch_num = (i // BATCH_SIZE) + 1
        total_batches = (total + BATCH_SIZE - 1) // BATCH_SIZE

        print(f"\n  Batch {batch_num}/{total_batches} ({len(batch)} indicators)...")

        prompt = create_batch_prompt(batch, source_name)
        result = call_claude_api(prompt)

        if result:
            results.update(result)

            # Calculate reading levels for this batch
            batch_levels = []
            for ind_id, data in result.items():
                desc = data.get('description', '')
                level = estimate_reading_level(desc)
                batch_levels.append(level)
                reading_levels.append(level)

            avg_level = sum(batch_levels) / len(batch_levels) if batch_levels else 0
            print(f"    ✓ Generated {len(result)} descriptions (avg reading level: {avg_level:.1f})")
        else:
            print(f"    ✗ FAILED - adding to retry queue")
            for ind in batch:
                failed.append(ind['id'])
                results[ind['id']] = {
                    "label": ind['label'],
                    "description": f"[NEEDS MANUAL REVIEW] {ind.get('description', '')}",
                    "failed": True
                }

        # Save intermediate progress
        progress["all_descriptions"].update(results)
        progress["failed_indicators"].extend([f for f in failed if f not in progress["failed_indicators"]])
        save_progress(progress)

        # Rate limiting
        if i + BATCH_SIZE < total:
            time.sleep(0.5)

    # Calculate stats
    stats = {
        "total": total,
        "successful": total - len(failed),
        "failed": len(failed),
        "avg_reading_level": sum(reading_levels) / len(reading_levels) if reading_levels else 0,
        "reading_level_distribution": {
            "below_9": sum(1 for r in reading_levels if r < 9),
            "grade_9_12": sum(1 for r in reading_levels if 9 <= r <= 12),
            "above_12": sum(1 for r in reading_levels if r > 12)
        }
    }

    print(f"\n  {'-'*50}")
    print(f"  {source_name} SUMMARY:")
    print(f"    Processed: {stats['total']}")
    print(f"    Successful: {stats['successful']}")
    print(f"    Failed: {stats['failed']}")
    print(f"    Avg Reading Level: {stats['avg_reading_level']:.1f}")
    pct_target = stats['reading_level_distribution']['grade_9_12'] / total * 100 if total > 0 else 0
    print(f"    In Target Range (9-12): {pct_target:.1f}%")

    return results, failed, stats


def main():
    """Main entry point."""

    print("=" * 70)
    print("FULL INDICATOR DESCRIPTION GENERATION")
    print(f"Started: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("=" * 70)

    # Ensure output directory exists
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    # Load existing progress
    progress = load_progress()
    print(f"\nLoaded progress: {len(progress.get('all_descriptions', {}))} descriptions already generated")

    # Load indicators
    print("\nLoading indicators...")
    by_category = load_indicators_by_source()

    total_indicators = sum(len(v) for v in by_category.values())
    print(f"Total indicators: {total_indicators}")
    for cat in SOURCE_ORDER:
        print(f"  {cat}: {len(by_category[cat])}")

    # Process each source category
    all_stats = {}

    for source_name in SOURCE_ORDER:
        indicators = by_category[source_name]

        if not indicators:
            print(f"\n[SKIP] {source_name}: No indicators")
            continue

        if source_name in progress.get("completed_sources", []):
            print(f"\n[SKIP] {source_name}: Already completed")
            all_stats[source_name] = progress["stats"].get(source_name, {})
            continue

        results, failed, stats = process_source(source_name, indicators, progress)

        # Update progress
        progress["completed_sources"].append(source_name)
        progress["stats"][source_name] = stats
        all_stats[source_name] = stats
        save_progress(progress)

        # Save source-specific results
        safe_name = source_name.replace(' ', '_').replace('/', '_')
        source_file = OUTPUT_DIR / f"descriptions_{safe_name}.json"
        with open(source_file, 'w') as f:
            json.dump(results, f, indent=2)
        print(f"\n  Saved to {source_file}")

    # Final summary
    print("\n" + "=" * 70)
    print("FINAL SUMMARY")
    print("=" * 70)

    total_processed = sum(s.get('total', 0) for s in all_stats.values())
    total_successful = sum(s.get('successful', 0) for s in all_stats.values())
    total_failed = sum(s.get('failed', 0) for s in all_stats.values())

    all_levels = []
    for source_name in SOURCE_ORDER:
        if source_name in all_stats:
            stats = all_stats[source_name]
            all_levels.extend([stats['avg_reading_level']] * stats.get('total', 0))

    avg_reading = sum(all_levels) / len(all_levels) if all_levels else 0

    print(f"\nTotal Indicators: {total_processed}")
    print(f"Successful: {total_successful} ({total_successful/total_processed*100:.1f}%)")
    print(f"Failed (needs review): {total_failed}")
    print(f"Average Reading Level: {avg_reading:.1f}")

    # Save combined results
    combined_file = OUTPUT_DIR / "all_descriptions.json"
    with open(combined_file, 'w') as f:
        json.dump(progress["all_descriptions"], f, indent=2)
    print(f"\nSaved all descriptions to {combined_file}")

    # Save failed indicators for manual review
    if progress["failed_indicators"]:
        failed_file = OUTPUT_DIR / "failed_descriptions.json"
        with open(failed_file, 'w') as f:
            json.dump(progress["failed_indicators"], f, indent=2)
        print(f"Saved failed indicators to {failed_file}")

    print(f"\nCompleted: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")


if __name__ == "__main__":
    main()
