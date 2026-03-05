#!/usr/bin/env python3
"""
B36: Semantic Hierarchy with LLM-Generated Names

This script:
1. Builds 6-layer hierarchy with strict max 5 children (flexible 3-5)
2. Uses LLM (Claude) to generate semantic names for Layers 2, 3, 4
3. Assigns all 1,962 indicators to outcomes via semantic similarity

Layers:
- Layer 0: Root (1 node)
- Layer 1: Outcomes (9 nodes) - from B1
- Layer 2: Coarse Domains (36-45 nodes, 3-5 per outcome)
- Layer 3: Fine Domains (~144 nodes, 3-5 per coarse)
- Layer 4: Indicator Groups (~576 nodes, 3-5 per fine)
- Layer 5: Indicators (1,962 nodes)
"""

import pickle
import json
import numpy as np
from pathlib import Path
from datetime import datetime
from collections import defaultdict
import sys
import time
import logging

# Setup paths
BASE_DIR = Path("<repo-root>/v2.0/v2.1")
OUTPUT_DIR = BASE_DIR / "outputs" / "B36"
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
LOG_FILE = BASE_DIR / "logs" / "B36_semantic_hierarchy_llm.log"
LOG_FILE.parent.mkdir(parents=True, exist_ok=True)

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler(LOG_FILE),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

# Progress file for monitoring
PROGRESS_FILE = OUTPUT_DIR / "progress.json"

def save_progress(step: str, pct: float, details: dict = None):
    """Save progress to JSON file for monitoring"""
    progress = {
        "step": step,
        "pct": pct,
        "updated": datetime.now().isoformat(),
        **(details or {})
    }
    with open(PROGRESS_FILE, 'w') as f:
        json.dump(progress, f, indent=2)


def get_optimal_clusters(n_indicators: int) -> int:
    """
    Determine optimal cluster count based on indicator count.
    Returns 3-5 clusters (flexible range).
    """
    if n_indicators < 10:
        return 3
    elif n_indicators < 30:
        return 4
    else:
        return 5


def main():
    logger.info("=" * 80)
    logger.info("B36: SEMANTIC HIERARCHY WITH LLM-GENERATED NAMES")
    logger.info("=" * 80)

    save_progress("Loading data", 0)

    # =========================================================================
    # STEP 1: Load all required data
    # =========================================================================
    logger.info("\n[STEP 1] Loading data...")

    # Load B1 outcomes
    with open(BASE_DIR / "outputs/B1/B1_validated_outcomes.pkl", 'rb') as f:
        b1_data = pickle.load(f)
    outcomes = b1_data['outcomes']
    logger.info(f"  Loaded {len(outcomes)} outcomes from B1")

    # Load indicator labels
    with open(BASE_DIR / "outputs/B1/indicator_labels_comprehensive.json", 'r') as f:
        indicator_labels = json.load(f)
    logger.info(f"  Loaded {len(indicator_labels)} indicator labels")

    # Load SHAP scores
    with open(BASE_DIR / "outputs/B25/B25_shap_scores.pkl", 'rb') as f:
        shap_data = pickle.load(f)
    logger.info(f"  Loaded SHAP scores for {len(shap_data)} indicators")

    # All indicators
    all_indicators = list(indicator_labels.keys())
    logger.info(f"  Total indicators: {len(all_indicators)}")

    save_progress("Loading data", 5, {"indicators": len(all_indicators)})

    # =========================================================================
    # STEP 2: Assign ALL indicators to outcomes via semantic similarity
    # =========================================================================
    logger.info("\n[STEP 2] Assigning indicators to outcomes...")

    # First, collect indicators already assigned by B1
    assigned_indicators = set()
    outcome_indicators = {}

    for oid, odata in outcomes.items():
        outcome_indicators[oid] = list(odata['all_indicators'])
        assigned_indicators.update(odata['all_indicators'])

    logger.info(f"  Already assigned (B1): {len(assigned_indicators)} indicators")

    # Find unassigned indicators
    unassigned = [ind for ind in all_indicators if ind not in assigned_indicators]
    logger.info(f"  Unassigned: {len(unassigned)} indicators")

    if unassigned:
        logger.info("  Computing semantic similarity for unassigned indicators...")

        # Load sentence transformer for semantic matching
        from sentence_transformers import SentenceTransformer
        model = SentenceTransformer('all-MiniLM-L6-v2')

        # Create outcome descriptions for matching
        outcome_texts = {}
        for oid, odata in outcomes.items():
            # Use name + description + top indicator labels
            top_labels = [indicator_labels.get(ind, {}).get('label', ind)
                         for ind in odata.get('top_indicators', odata['all_indicators'][:5])]
            text = f"{odata['name']}. {odata.get('description', '')}. " + " ".join(top_labels)
            outcome_texts[oid] = text

        # Embed outcome texts
        outcome_ids = list(outcome_texts.keys())
        outcome_embeddings = model.encode([outcome_texts[oid] for oid in outcome_ids])

        # Process unassigned in batches
        batch_size = 500
        for i in range(0, len(unassigned), batch_size):
            batch = unassigned[i:i+batch_size]

            # Get labels for batch
            batch_texts = [indicator_labels.get(ind, {}).get('label', ind) for ind in batch]
            batch_embeddings = model.encode(batch_texts)

            # Compute similarities
            from sklearn.metrics.pairwise import cosine_similarity
            similarities = cosine_similarity(batch_embeddings, outcome_embeddings)

            # Assign each indicator to best matching outcome
            for j, ind in enumerate(batch):
                best_outcome_idx = np.argmax(similarities[j])
                best_outcome = outcome_ids[best_outcome_idx]
                outcome_indicators[best_outcome].append(ind)

            logger.info(f"    Assigned batch {i//batch_size + 1}/{(len(unassigned) + batch_size - 1)//batch_size}")

        del model  # Free memory

    # Verify all assigned
    total_assigned = sum(len(inds) for inds in outcome_indicators.values())
    logger.info(f"  Total assigned: {total_assigned} / {len(all_indicators)}")

    save_progress("Assigning indicators", 15, {"assigned": total_assigned})

    # =========================================================================
    # STEP 3: Build Layer 1 (Outcomes)
    # =========================================================================
    logger.info("\n[STEP 3] Building Layer 1 (Outcomes)...")

    hierarchy = {
        'root': {
            'id': 'root',
            'label': 'Quality of Life',
            'layer': 0,
            'node_type': 'root',
            'parent': None,
            'children': [],
            'indicators': all_indicators
        },
        'nodes': {},
        'layer_counts': {0: 1}
    }

    layer_1_nodes = {}
    for oid, odata in outcomes.items():
        node = {
            'id': oid,
            'label': odata['name'],
            'layer': 1,
            'node_type': 'outcome_category',
            'domain': odata.get('domain', odata['name'].split()[0]),
            'parent': 'root',
            'children': [],
            'indicators': outcome_indicators[oid]
        }
        layer_1_nodes[oid] = node
        hierarchy['nodes'][oid] = node
        hierarchy['root']['children'].append(oid)

    hierarchy['layer_counts'][1] = len(layer_1_nodes)

    for oid, node in layer_1_nodes.items():
        logger.info(f"  {node['label']}: {len(node['indicators'])} indicators")

    save_progress("Building Layer 1", 20)

    # =========================================================================
    # STEP 4: Build Layer 2 (Coarse Domains) with MAX 5 children
    # =========================================================================
    logger.info("\n[STEP 4] Building Layer 2 (Coarse Domains) - Max 5 per outcome...")

    from sentence_transformers import SentenceTransformer
    from sklearn.cluster import KMeans

    model = SentenceTransformer('all-MiniLM-L6-v2')

    layer_2_nodes = {}
    coarse_counter = 1

    for oid, outcome_node in layer_1_nodes.items():
        indicators = outcome_node['indicators']
        n = len(indicators)

        # Determine cluster count (max 5)
        n_clusters = get_optimal_clusters(n)

        logger.info(f"\n  {outcome_node['label']}: {n} indicators -> {n_clusters} coarse domains")

        if n < 3:
            # Too few - single cluster
            clusters = {0: indicators}
        else:
            # Embed indicators
            texts = [indicator_labels.get(ind, {}).get('label', ind) for ind in indicators]
            embeddings = model.encode(texts)

            # Cluster
            n_clusters = min(n_clusters, n)
            kmeans = KMeans(n_clusters=n_clusters, random_state=42, n_init=10)
            labels = kmeans.fit_predict(embeddings)

            clusters = defaultdict(list)
            for i, ind in enumerate(indicators):
                clusters[labels[i]].append(ind)

        # Create coarse domain nodes
        # Get domain from parent outcome
        parent_domain = outcome_node.get('domain', outcome_node['label'].split()[0])

        for cluster_id, cluster_indicators in clusters.items():
            coarse_id = f"coarse_{coarse_counter}"
            coarse_counter += 1

            # Temporary name (will be replaced by LLM later)
            temp_name = f"{outcome_node['label']}_Domain_{cluster_id+1}"

            node = {
                'id': coarse_id,
                'label': temp_name,
                'layer': 2,
                'node_type': 'coarse_domain',
                'domain': parent_domain,  # Inherit domain from parent outcome
                'parent': oid,
                'children': [],
                'indicators': cluster_indicators
            }

            layer_2_nodes[coarse_id] = node
            hierarchy['nodes'][coarse_id] = node
            outcome_node['children'].append(coarse_id)

            logger.info(f"    {coarse_id}: {len(cluster_indicators)} indicators")

    hierarchy['layer_counts'][2] = len(layer_2_nodes)
    logger.info(f"\n  Total Layer 2 nodes: {len(layer_2_nodes)}")

    save_progress("Building Layer 2", 30)

    # =========================================================================
    # STEP 5: Build Layer 3 (Fine Domains) with MAX 5 children per coarse
    # =========================================================================
    logger.info("\n[STEP 5] Building Layer 3 (Fine Domains)...")

    layer_3_nodes = {}
    fine_counter = 1

    for coarse_id, coarse_node in layer_2_nodes.items():
        indicators = coarse_node['indicators']
        n = len(indicators)

        n_clusters = get_optimal_clusters(n)

        if n < 3:
            clusters = {0: indicators}
        else:
            texts = [indicator_labels.get(ind, {}).get('label', ind) for ind in indicators]
            embeddings = model.encode(texts)

            n_clusters = min(n_clusters, n)
            kmeans = KMeans(n_clusters=n_clusters, random_state=42, n_init=10)
            labels = kmeans.fit_predict(embeddings)

            clusters = defaultdict(list)
            for i, ind in enumerate(indicators):
                clusters[labels[i]].append(ind)

        for cluster_id, cluster_indicators in clusters.items():
            fine_id = f"fine_{fine_counter}"
            fine_counter += 1

            temp_name = f"{coarse_node['label']}_Sub_{cluster_id+1}"

            node = {
                'id': fine_id,
                'label': temp_name,
                'layer': 3,
                'node_type': 'fine_domain',
                'domain': coarse_node.get('domain'),  # Inherit domain from parent
                'parent': coarse_id,
                'children': [],
                'indicators': cluster_indicators
            }

            layer_3_nodes[fine_id] = node
            hierarchy['nodes'][fine_id] = node
            coarse_node['children'].append(fine_id)

    hierarchy['layer_counts'][3] = len(layer_3_nodes)
    logger.info(f"  Total Layer 3 nodes: {len(layer_3_nodes)}")

    save_progress("Building Layer 3", 40)

    # =========================================================================
    # STEP 6: Build Layer 4 (Indicator Groups) WITH PROMOTION LOGIC
    # =========================================================================
    logger.info("\n[STEP 6] Building Layer 4 (Indicator Groups with Promotion)...")

    # Summary indicator patterns - these get promoted
    SUMMARY_PATTERNS = [
        'total', 'aggregate', 'overall', 'index', 'rate', 'ratio',
        'life_expectancy', 'gdp_per_capita', 'gini', 'hdi',
        'literacy_rate', 'unemployment_rate', 'mortality_rate'
    ]

    def is_summary_indicator(indicator_id):
        """Check if indicator name suggests it's a summary metric"""
        indicator_lower = str(indicator_id).lower()
        return any(pattern in indicator_lower for pattern in SUMMARY_PATTERNS)

    def get_shap_score(ind):
        """Get SHAP score for indicator"""
        shap_info = shap_data.get(ind, {})
        return shap_info.get('shap_normalized', 0) if isinstance(shap_info, dict) else 0

    layer_4_nodes = {}
    group_counter = 1
    promoted_count = 0
    group_count = 0

    for fine_id, fine_node in layer_3_nodes.items():
        indicators = fine_node['indicators']
        n = len(indicators)
        domain = fine_node.get('domain')

        # -----------------------------
        # CASE 1: Very few indicators (≤3) - all promoted to Layer 4
        # -----------------------------
        if n <= 3:
            logger.info(f"  {fine_id}: {n} indicators → promoting all (no grouping)")

            for ind in indicators:
                label_data = indicator_labels.get(ind, {})
                label = label_data.get('label', ind) if isinstance(label_data, dict) else str(label_data)
                shap_score = get_shap_score(ind)

                node = {
                    'id': ind,
                    'label': label,
                    'layer': 4,
                    'node_type': 'indicator',
                    'domain': domain,
                    'parent': fine_id,
                    'children': [],
                    'shap_importance': shap_score,
                    'source': label_data.get('source', '') if isinstance(label_data, dict) else '',
                    'promoted': True
                }

                layer_4_nodes[ind] = node
                hierarchy['nodes'][ind] = node
                fine_node['children'].append(ind)
                promoted_count += 1

            continue

        # -----------------------------
        # CASE 2: Many indicators (>3) - cluster then check for promotion
        # -----------------------------

        # Target: 3-5 indicators per group
        n_groups = max(2, min(5, (n + 3) // 4))

        texts = [indicator_labels.get(ind, {}).get('label', ind) for ind in indicators]
        embeddings = model.encode(texts)

        n_groups = min(n_groups, n)
        kmeans = KMeans(n_clusters=n_groups, random_state=42, n_init=10)
        labels = kmeans.fit_predict(embeddings)

        cluster_dict = defaultdict(list)
        for i, ind in enumerate(indicators):
            cluster_dict[labels[i]].append(ind)

        # Process each cluster
        for cluster_id, cluster_indicators in cluster_dict.items():
            if len(cluster_indicators) == 0:
                continue

            # -----------------------------
            # PROMOTION CHECK 1: Single indicator in cluster?
            # -----------------------------
            if len(cluster_indicators) == 1:
                ind = cluster_indicators[0]
                label_data = indicator_labels.get(ind, {})
                label = label_data.get('label', ind) if isinstance(label_data, dict) else str(label_data)
                shap_score = get_shap_score(ind)

                logger.info(f"    Promoting single indicator: {ind[:40]}...")

                node = {
                    'id': ind,
                    'label': label,
                    'layer': 4,
                    'node_type': 'indicator',
                    'domain': domain,
                    'parent': fine_id,
                    'children': [],
                    'shap_importance': shap_score,
                    'source': label_data.get('source', '') if isinstance(label_data, dict) else '',
                    'promoted': True
                }

                layer_4_nodes[ind] = node
                hierarchy['nodes'][ind] = node
                fine_node['children'].append(ind)
                promoted_count += 1
                continue

            # -----------------------------
            # PROMOTION CHECK 2: High-SHAP indicator that summarizes group?
            # -----------------------------
            cluster_shap = [(ind, get_shap_score(ind)) for ind in cluster_indicators]
            cluster_shap.sort(key=lambda x: x[1], reverse=True)
            top_indicator, top_shap = cluster_shap[0]

            remaining_indicators = cluster_indicators.copy()

            if len(cluster_shap) > 1:
                second_shap = cluster_shap[1][1]

                # If top indicator has 2× SHAP of next AND is summary metric, promote it
                if top_shap > 2 * max(second_shap, 0.01) and top_shap > 0.05:
                    label_data = indicator_labels.get(top_indicator, {})
                    label = label_data.get('label', top_indicator) if isinstance(label_data, dict) else str(label_data)

                    logger.info(f"    Promoting high-SHAP indicator: {top_indicator[:40]}... (SHAP={top_shap:.3f})")

                    node = {
                        'id': top_indicator,
                        'label': label,
                        'layer': 4,
                        'node_type': 'indicator',
                        'domain': domain,
                        'parent': fine_id,
                        'children': [],
                        'shap_importance': top_shap,
                        'source': label_data.get('source', '') if isinstance(label_data, dict) else '',
                        'promoted': True
                    }

                    layer_4_nodes[top_indicator] = node
                    hierarchy['nodes'][top_indicator] = node
                    fine_node['children'].append(top_indicator)
                    promoted_count += 1

                    remaining_indicators.remove(top_indicator)

                    # If only 1 left after promotion, promote that too
                    if len(remaining_indicators) == 1:
                        ind = remaining_indicators[0]
                        label_data = indicator_labels.get(ind, {})
                        label = label_data.get('label', ind) if isinstance(label_data, dict) else str(label_data)
                        shap_score = get_shap_score(ind)

                        node = {
                            'id': ind,
                            'label': label,
                            'layer': 4,
                            'node_type': 'indicator',
                            'domain': domain,
                            'parent': fine_id,
                            'children': [],
                            'shap_importance': shap_score,
                            'source': label_data.get('source', '') if isinstance(label_data, dict) else '',
                            'promoted': True
                        }

                        layer_4_nodes[ind] = node
                        hierarchy['nodes'][ind] = node
                        fine_node['children'].append(ind)
                        promoted_count += 1
                        continue

            # -----------------------------
            # CREATE GROUP: 2+ indicators remain
            # -----------------------------
            if len(remaining_indicators) >= 2:
                group_id = f"group_{group_counter}"
                group_counter += 1

                temp_name = f"{fine_node['label']}_Group_{cluster_id+1}"

                node = {
                    'id': group_id,
                    'label': temp_name,
                    'layer': 4,
                    'node_type': 'indicator_group',
                    'domain': domain,
                    'parent': fine_id,
                    'children': remaining_indicators,
                    'indicators': remaining_indicators,
                    'promoted': False
                }

                layer_4_nodes[group_id] = node
                hierarchy['nodes'][group_id] = node
                fine_node['children'].append(group_id)
                group_count += 1

    hierarchy['layer_counts'][4] = len(layer_4_nodes)
    logger.info(f"  Total Layer 4 nodes: {len(layer_4_nodes)} ({group_count} groups + {promoted_count} promoted indicators)")

    del model  # Free memory

    save_progress("Building Layer 4", 50)

    # =========================================================================
    # STEP 7: Build Layer 5 (Only NON-promoted Indicators)
    # =========================================================================
    logger.info("\n[STEP 7] Building Layer 5 (Non-promoted Indicators)...")

    layer_5_nodes = {}

    for node_id, node in layer_4_nodes.items():
        # Only process indicator groups (not promoted indicators)
        if node.get('node_type') != 'indicator_group':
            continue

        domain = node.get('domain')

        for ind in node.get('indicators', []):
            label_data = indicator_labels.get(ind, {})
            label = label_data.get('label', ind) if isinstance(label_data, dict) else str(label_data)

            shap_info = shap_data.get(ind, {})
            shap_score = shap_info.get('shap_normalized', 0) if isinstance(shap_info, dict) else 0

            indicator_node = {
                'id': ind,
                'label': label,
                'layer': 5,
                'node_type': 'indicator',
                'domain': domain,
                'parent': node_id,
                'children': [],
                'shap_importance': shap_score,
                'source': label_data.get('source', '') if isinstance(label_data, dict) else ''
            }

            layer_5_nodes[ind] = indicator_node
            hierarchy['nodes'][ind] = indicator_node

    hierarchy['layer_counts'][5] = len(layer_5_nodes)
    logger.info(f"  Total Layer 5 nodes: {len(layer_5_nodes)} (non-promoted indicators)")

    total_indicators = promoted_count + len(layer_5_nodes)
    logger.info(f"\n  PROMOTION SUMMARY:")
    logger.info(f"    Total indicators: {total_indicators}")
    logger.info(f"    Promoted to Layer 4: {promoted_count} ({promoted_count/total_indicators*100:.1f}%)")
    logger.info(f"    Remain at Layer 5: {len(layer_5_nodes)} ({len(layer_5_nodes)/total_indicators*100:.1f}%)")

    save_progress("Building Layer 5", 55)

    # =========================================================================
    # STEP 7.5: SEMANTIC AGGREGATE PROMOTION
    # =========================================================================
    logger.info("\n[STEP 7.5] Detecting and promoting semantic aggregates...")

    # Aggregate patterns: (parent_pattern, child_patterns)
    AGGREGATE_PATTERNS = [
        # Total vs components
        ('.TO', ['.MA', '.FE']),           # Total vs Male/Female
        ('_TO', ['_MA', '_FE']),           # Total vs Male/Female (underscore)
        ('.TO.', ['.MA.', '.FE.']),        # Total vs Male/Female (with dot)
        ('.IN', ['.MA.IN', '.FE.IN']),     # Total vs Male/Female indexed
        ('TOTL', ['MALE', 'FEMA']),        # TOTL vs MALE/FEMALE
        ('.TOTL.', ['.AGRI.', '.INDU.', '.SERV.']),  # GDP components

        # Urban/Rural
        ('.TO', ['.UR', '.RU']),           # Total vs Urban/Rural
        ('_TO', ['_UR', '_RU']),           # Total vs Urban/Rural

        # Age groups
        ('TOTL', ['0014', '1564', '65UP']),  # Population age groups
        ('.TO', ['.0014', '.1564', '.65UP']),

        # Quintiles
        ('_TO', ['_Q1', '_Q2', '_Q3', '_Q4', '_Q5']),
        ('.TO', ['.Q1', '.Q2', '.Q3', '.Q4', '.Q5']),

        # Primary/Secondary/Tertiary
        ('.TO', ['.PR', '.SE', '.TE']),
        ('_ED', ['_ED.1', '_ED.2', '_ED.3']),
    ]

    def is_aggregate_of(parent_code: str, child_codes: list) -> bool:
        """Check if parent indicator code suggests aggregation of children"""
        parent_upper = str(parent_code).upper()
        child_uppers = [str(c).upper() for c in child_codes]

        for agg_pattern, child_patterns in AGGREGATE_PATTERNS:
            if agg_pattern in parent_upper:
                # Count how many children match expected patterns
                matches = 0
                for child in child_uppers:
                    for cp in child_patterns:
                        if cp in child and agg_pattern not in child:
                            matches += 1
                            break

                # If at least 2 children match, it's an aggregate
                if matches >= 2:
                    return True

        # Check code prefix hierarchy (parent code is prefix of children)
        # e.g., NY.GDP.MKTP vs NY.GDP.MKTP.CD, NY.GDP.MKTP.KD
        parent_base = parent_upper.split('.')[:-1]  # Remove last segment
        if len(parent_base) >= 2:
            parent_prefix = '.'.join(parent_base)
            children_with_prefix = sum(1 for c in child_uppers if c.startswith(parent_prefix))
            if children_with_prefix >= 2 and children_with_prefix == len(child_uppers):
                return True

        return False

    def get_shap_score(ind):
        shap_info = shap_data.get(ind, {})
        return shap_info.get('shap_normalized', 0) if isinstance(shap_info, dict) else 0

    semantic_promotions = 0
    promoted_to_layer3 = 0
    promoted_to_layer2 = 0

    # PHASE 1: Promote aggregates from Layer 5 to Layer 4 (replace indicator_groups)
    logger.info("  Phase 1: Checking Layer 5 indicators for aggregates...")

    for group_id, group_node in list(layer_4_nodes.items()):
        if group_node.get('node_type') != 'indicator_group':
            continue

        indicators = group_node.get('indicators', [])
        if len(indicators) < 2:
            continue

        # Check each indicator to see if it aggregates others
        for candidate in indicators:
            others = [ind for ind in indicators if ind != candidate]

            if is_aggregate_of(candidate, others):
                # Found an aggregate! Promote it to replace the group
                label_data = indicator_labels.get(candidate, {})
                label = label_data.get('label', candidate) if isinstance(label_data, dict) else str(label_data)

                # Update the group to be this indicator
                old_label = group_node.get('label', group_id)
                group_node['id'] = candidate
                group_node['label'] = label
                group_node['node_type'] = 'aggregate_indicator'
                group_node['original_group'] = group_id
                group_node['shap_importance'] = get_shap_score(candidate)
                group_node['promoted'] = True
                group_node['aggregates'] = others

                # Remove candidate from indicators list (it's now the parent)
                group_node['indicators'] = others

                # Update children list
                group_node['children'] = others

                # Update child indicators' parent
                for child_ind in others:
                    if child_ind in layer_5_nodes:
                        layer_5_nodes[child_ind]['parent'] = candidate
                        hierarchy['nodes'][child_ind]['parent'] = candidate

                # Update hierarchy
                del layer_4_nodes[group_id]
                layer_4_nodes[candidate] = group_node
                hierarchy['nodes'][candidate] = group_node
                if group_id in hierarchy['nodes']:
                    del hierarchy['nodes'][group_id]

                # Update parent's children list
                parent_id = group_node.get('parent')
                if parent_id and parent_id in layer_3_nodes:
                    children = layer_3_nodes[parent_id].get('children', [])
                    if group_id in children:
                        children.remove(group_id)
                        children.append(candidate)

                logger.info(f"    Promoted: {candidate} -> aggregates {len(others)} indicators (was: {old_label})")
                semantic_promotions += 1
                break  # Only one aggregate per group

    logger.info(f"  Phase 1 complete: {semantic_promotions} semantic aggregates promoted")

    # PHASE 2: Check Layer 4 for aggregates that should go to Layer 3
    logger.info("  Phase 2: Checking Layer 4 for higher-level aggregates...")

    for fine_id, fine_node in list(layer_3_nodes.items()):
        children_ids = fine_node.get('children', [])
        if len(children_ids) < 2:
            continue

        # Get child nodes from Layer 4
        child_nodes = []
        for cid in children_ids:
            if cid in layer_4_nodes:
                child_nodes.append((cid, layer_4_nodes[cid]))

        if len(child_nodes) < 2:
            continue

        # Check if any Layer 4 node aggregates the others
        for candidate_id, candidate_node in child_nodes:
            # Only consider indicators or aggregate_indicators (not groups)
            if candidate_node.get('node_type') not in ['indicator', 'aggregate_indicator']:
                continue

            other_ids = [cid for cid, _ in child_nodes if cid != candidate_id]

            if is_aggregate_of(candidate_id, other_ids):
                # Promote to Layer 3: replace fine_domain with this aggregate
                label = candidate_node.get('label', candidate_id)
                old_label = fine_node.get('label', fine_id)

                # Update fine_node to be this indicator
                fine_node['original_fine'] = fine_id
                fine_node['id'] = candidate_id
                fine_node['label'] = label
                fine_node['node_type'] = 'aggregate_indicator'
                fine_node['shap_importance'] = get_shap_score(candidate_id)
                fine_node['promoted'] = True
                fine_node['aggregates'] = other_ids

                # Remove candidate from Layer 4
                if candidate_id in layer_4_nodes:
                    del layer_4_nodes[candidate_id]
                if candidate_id in hierarchy['nodes']:
                    del hierarchy['nodes'][candidate_id]

                # Update children to point to other Layer 4 nodes
                fine_node['children'] = other_ids

                # Update child nodes' parent
                for other_id in other_ids:
                    if other_id in layer_4_nodes:
                        layer_4_nodes[other_id]['parent'] = candidate_id
                    if other_id in hierarchy['nodes']:
                        hierarchy['nodes'][other_id]['parent'] = candidate_id

                # Update Layer 3 dict
                del layer_3_nodes[fine_id]
                layer_3_nodes[candidate_id] = fine_node
                hierarchy['nodes'][candidate_id] = fine_node
                if fine_id in hierarchy['nodes']:
                    del hierarchy['nodes'][fine_id]

                # Update parent's children list
                parent_id = fine_node.get('parent')
                if parent_id and parent_id in layer_2_nodes:
                    children = layer_2_nodes[parent_id].get('children', [])
                    if fine_id in children:
                        children.remove(fine_id)
                        children.append(candidate_id)

                logger.info(f"    Promoted to L3: {candidate_id} -> aggregates {len(other_ids)} L4 nodes (was: {old_label})")
                promoted_to_layer3 += 1
                break

    logger.info(f"  Phase 2 complete: {promoted_to_layer3} indicators promoted to Layer 3")

    # PHASE 3: Check Layer 3 for aggregates that should go to Layer 2
    logger.info("  Phase 3: Checking Layer 3 for higher-level aggregates...")

    for coarse_id, coarse_node in list(layer_2_nodes.items()):
        children_ids = coarse_node.get('children', [])
        if len(children_ids) < 2:
            continue

        # Get child nodes from Layer 3
        child_nodes = []
        for cid in children_ids:
            if cid in layer_3_nodes:
                child_nodes.append((cid, layer_3_nodes[cid]))

        if len(child_nodes) < 2:
            continue

        # Check if any Layer 3 node aggregates the others
        for candidate_id, candidate_node in child_nodes:
            if candidate_node.get('node_type') not in ['indicator', 'aggregate_indicator']:
                continue

            other_ids = [cid for cid, _ in child_nodes if cid != candidate_id]

            if is_aggregate_of(candidate_id, other_ids):
                # Promote to Layer 2
                label = candidate_node.get('label', candidate_id)
                old_label = coarse_node.get('label', coarse_id)

                coarse_node['original_coarse'] = coarse_id
                coarse_node['id'] = candidate_id
                coarse_node['label'] = label
                coarse_node['node_type'] = 'aggregate_indicator'
                coarse_node['shap_importance'] = get_shap_score(candidate_id)
                coarse_node['promoted'] = True
                coarse_node['aggregates'] = other_ids

                # Remove from Layer 3
                if candidate_id in layer_3_nodes:
                    del layer_3_nodes[candidate_id]
                if candidate_id in hierarchy['nodes']:
                    del hierarchy['nodes'][candidate_id]

                coarse_node['children'] = other_ids

                for other_id in other_ids:
                    if other_id in layer_3_nodes:
                        layer_3_nodes[other_id]['parent'] = candidate_id
                    if other_id in hierarchy['nodes']:
                        hierarchy['nodes'][other_id]['parent'] = candidate_id

                del layer_2_nodes[coarse_id]
                layer_2_nodes[candidate_id] = coarse_node
                hierarchy['nodes'][candidate_id] = coarse_node
                if coarse_id in hierarchy['nodes']:
                    del hierarchy['nodes'][coarse_id]

                # Update parent (Layer 1)
                parent_id = coarse_node.get('parent')
                if parent_id and parent_id in layer_1_nodes:
                    children = layer_1_nodes[parent_id].get('children', [])
                    if coarse_id in children:
                        children.remove(coarse_id)
                        children.append(candidate_id)

                logger.info(f"    Promoted to L2: {candidate_id} -> aggregates {len(other_ids)} L3 nodes (was: {old_label})")
                promoted_to_layer2 += 1
                break

    logger.info(f"  Phase 3 complete: {promoted_to_layer2} indicators promoted to Layer 2")

    total_semantic = semantic_promotions + promoted_to_layer3 + promoted_to_layer2
    logger.info(f"\n  SEMANTIC PROMOTION SUMMARY:")
    logger.info(f"    Layer 5 -> Layer 4 aggregates: {semantic_promotions}")
    logger.info(f"    Layer 4 -> Layer 3 aggregates: {promoted_to_layer3}")
    logger.info(f"    Layer 3 -> Layer 2 aggregates: {promoted_to_layer2}")
    logger.info(f"    Total semantic promotions: {total_semantic}")

    save_progress("Semantic promotion complete", 58)

    # =========================================================================
    # STEP 8: Validate hierarchy structure
    # =========================================================================
    logger.info("\n[STEP 8] Validating hierarchy structure...")

    # Check max 5 children rule
    violations = []

    # Layer 1 -> 2
    for oid, node in layer_1_nodes.items():
        n_children = len(node['children'])
        if n_children > 5:
            violations.append((node['label'], 'Layer 1->2', n_children))
        logger.info(f"  {node['label']}: {n_children} children " +
                   ("✓" if n_children <= 5 else "⚠️ >5"))

    # Layer 2 -> 3
    over_5_l2 = sum(1 for n in layer_2_nodes.values() if len(n['children']) > 5)
    logger.info(f"  Layer 2->3: {over_5_l2} nodes with >5 children")

    # Layer 3 -> 4
    over_5_l3 = sum(1 for n in layer_3_nodes.values() if len(n['children']) > 5)
    logger.info(f"  Layer 3->4: {over_5_l3} nodes with >5 children")

    # Layer 4 -> 5 (only count indicator_groups, not promoted indicators)
    over_5_l4 = sum(1 for n in layer_4_nodes.values()
                    if n.get('node_type') == 'indicator_group' and len(n['children']) > 5)
    logger.info(f"  Layer 4->5: {over_5_l4} indicator_groups with >5 children")

    # Promotion stats
    n_promoted_l4 = sum(1 for n in layer_4_nodes.values() if n.get('promoted', False))
    n_groups_l4 = sum(1 for n in layer_4_nodes.values() if n.get('node_type') == 'indicator_group')
    logger.info(f"  Layer 4 composition: {n_groups_l4} groups + {n_promoted_l4} promoted indicators")

    save_progress("Validation complete", 60)

    # =========================================================================
    # STEP 9: Generate LLM semantic names
    # =========================================================================
    logger.info("\n[STEP 9] Generating LLM semantic names...")

    try:
        from anthropic import Anthropic
        client = Anthropic()
        use_llm = True
        logger.info("  Anthropic client initialized")
    except Exception as e:
        logger.warning(f"  Could not initialize Anthropic client: {e}")
        logger.warning("  Will use fallback naming")
        use_llm = False

    def get_representative_indicators(node, n=5):
        """Get top N indicators by SHAP score"""
        indicators = node['indicators']
        scored = [(ind, shap_data.get(ind, {}).get('shap_normalized', 0)) for ind in indicators]
        scored.sort(key=lambda x: x[1], reverse=True)
        return [ind for ind, _ in scored[:n]]

    def generate_semantic_name(parent_name: str, representative_indicators: list, max_words: int = 5) -> str:
        """Generate semantic name using Claude"""
        if not use_llm:
            return None

        labels = []
        for ind in representative_indicators:
            label_data = indicator_labels.get(ind, {})
            label = label_data.get('label', ind) if isinstance(label_data, dict) else ind
            labels.append(label)

        prompt = f"""You are naming a cluster of development indicators.

Parent category: {parent_name}
Representative indicators in this cluster:
{chr(10).join([f"- {label}" for label in labels])}

Generate a concise, descriptive name ({max_words-2}-{max_words} words) that captures what this cluster measures.
The name should be:
- Human-readable (no codes, no abbreviations)
- Specific (not just repeating the parent category)
- Action-oriented when possible

Examples of good names:
- "Healthcare Access & Quality"
- "Primary & Secondary Education"
- "Income Inequality & Wealth Distribution"
- "Democratic Institutions & Governance"
- "Clean Energy & Emissions"

Return ONLY the name, no explanation."""

        try:
            response = client.messages.create(
                model="claude-sonnet-4-20250514",
                max_tokens=50,
                messages=[{"role": "user", "content": prompt}]
            )
            return response.content[0].text.strip()
        except Exception as e:
            logger.warning(f"    LLM call failed: {e}")
            return None

    # Generate names for Layer 2
    logger.info("\n  Generating Layer 2 names...")
    layer_2_count = len(layer_2_nodes)
    for i, (node_id, node) in enumerate(layer_2_nodes.items()):
        parent_node = layer_1_nodes[node['parent']]
        parent_name = parent_node['label']

        rep_inds = get_representative_indicators(node, n=5)
        new_name = generate_semantic_name(parent_name, rep_inds, max_words=5)

        if new_name:
            node['auto_label'] = node['label']  # Keep old for debugging
            node['label'] = new_name
            logger.info(f"    {node_id}: {new_name}")

        # Rate limiting
        if use_llm and (i + 1) % 10 == 0:
            time.sleep(1)

        save_progress("Generating Layer 2 names", 60 + (i/layer_2_count) * 10,
                     {"layer": 2, "done": i+1, "total": layer_2_count})

    # Generate names for Layer 3
    logger.info("\n  Generating Layer 3 names...")
    layer_3_count = len(layer_3_nodes)
    for i, (node_id, node) in enumerate(layer_3_nodes.items()):
        parent_node = layer_2_nodes[node['parent']]
        parent_name = parent_node['label']

        rep_inds = get_representative_indicators(node, n=4)
        new_name = generate_semantic_name(parent_name, rep_inds, max_words=4)

        if new_name:
            node['auto_label'] = node['label']
            node['label'] = new_name

        if use_llm and (i + 1) % 20 == 0:
            time.sleep(1)
            logger.info(f"    Progress: {i+1}/{layer_3_count}")

        save_progress("Generating Layer 3 names", 70 + (i/layer_3_count) * 10,
                     {"layer": 3, "done": i+1, "total": layer_3_count})

    # Generate names for Layer 4 (ONLY indicator_groups, not promoted indicators)
    logger.info("\n  Generating Layer 4 names (groups only, skipping promoted indicators)...")
    layer_4_groups = {k: v for k, v in layer_4_nodes.items() if v.get('node_type') == 'indicator_group'}
    layer_4_count = len(layer_4_groups)
    logger.info(f"    {layer_4_count} groups to name ({len(layer_4_nodes) - layer_4_count} promoted indicators skipped)")

    for i, (node_id, node) in enumerate(layer_4_groups.items()):
        parent_node = layer_3_nodes.get(node['parent'])
        if not parent_node:
            continue
        parent_name = parent_node['label']

        rep_inds = get_representative_indicators(node, n=3)
        new_name = generate_semantic_name(parent_name, rep_inds, max_words=4)

        if new_name:
            node['auto_label'] = node['label']
            node['label'] = new_name

        if use_llm and (i + 1) % 50 == 0:
            time.sleep(1)
            logger.info(f"    Progress: {i+1}/{layer_4_count}")

        save_progress("Generating Layer 4 names", 80 + (i/layer_4_count) * 15,
                     {"layer": 4, "done": i+1, "total": layer_4_count})

    save_progress("LLM naming complete", 95)

    # =========================================================================
    # STEP 10: Save outputs
    # =========================================================================
    logger.info("\n[STEP 10] Saving outputs...")

    # Save main hierarchy
    output_path = OUTPUT_DIR / "B36_semantic_hierarchy_llm.pkl"
    with open(output_path, 'wb') as f:
        pickle.dump(hierarchy, f)
    logger.info(f"  Saved: {output_path}")

    # Save semantic paths JSON for quick lookup
    semantic_paths = {}
    for node_id, node in hierarchy['nodes'].items():
        # Build path from root
        path_parts = [node['label']]
        current = node
        while current.get('parent'):
            parent_id = current['parent']
            if parent_id == 'root':
                path_parts.append('Quality of Life')
                break
            parent = hierarchy['nodes'].get(parent_id)
            if parent:
                path_parts.append(parent['label'])
                current = parent
            else:
                break

        semantic_paths[node_id] = {
            'path': ' > '.join(reversed(path_parts)),
            'label': node['label'],
            'layer': node['layer']
        }

    paths_path = OUTPUT_DIR / "B36_semantic_paths.json"
    with open(paths_path, 'w') as f:
        json.dump(semantic_paths, f, indent=2)
    logger.info(f"  Saved: {paths_path}")

    save_progress("Complete", 100)

    # =========================================================================
    # SUMMARY
    # =========================================================================
    logger.info("\n" + "=" * 80)
    logger.info("SUMMARY")
    logger.info("=" * 80)
    logger.info(f"Layer 0 (Root):              {hierarchy['layer_counts'][0]} node")
    logger.info(f"Layer 1 (Outcomes):          {hierarchy['layer_counts'][1]} nodes")
    logger.info(f"Layer 2 (Coarse Domains):    {hierarchy['layer_counts'][2]} nodes")
    logger.info(f"Layer 3 (Fine Domains):      {hierarchy['layer_counts'][3]} nodes")
    logger.info(f"Layer 4 (Indicator Groups):  {hierarchy['layer_counts'][4]} nodes")
    logger.info(f"Layer 5 (Indicators):        {hierarchy['layer_counts'][5]} nodes")
    logger.info(f"\nTotal hierarchy nodes: {sum(hierarchy['layer_counts'].values())}")

    # Print Layer 1 -> 2 structure
    logger.info("\n" + "=" * 80)
    logger.info("LAYER 1 -> 2 STRUCTURE")
    logger.info("=" * 80)
    for oid, outcome_node in layer_1_nodes.items():
        logger.info(f"\n{outcome_node['label']}")
        for child_id in outcome_node['children']:
            child = layer_2_nodes[child_id]
            logger.info(f"  ├─ {child['label']} ({len(child['indicators'])} indicators)")

    logger.info("\n✅ B36 COMPLETE")

    return hierarchy


if __name__ == "__main__":
    main()
