"""
Indicator Service

Handles indicator metadata lookup for rich tooltips and indicator lists.
"""

import json
from pathlib import Path
from typing import Dict, List, Optional, Any
from collections import defaultdict

from ..config import V21_GRAPH_PATH, GRAPHS_DIR


class IndicatorService:
    """Service for indicator metadata and statistics."""

    def __init__(self):
        self._indicators: Optional[Dict[str, dict]] = None
        self._indicator_list: Optional[List[dict]] = None
        self._graph_stats: Optional[Dict[str, Dict[str, int]]] = None

    def _load_indicators(self):
        """Load indicator metadata from V2.1 unified graph."""
        if self._indicators is not None:
            return

        self._indicators = {}

        # Try to load from V2.1 graph
        if V21_GRAPH_PATH.exists():
            try:
                with open(V21_GRAPH_PATH) as f:
                    graph = json.load(f)

                for node in graph.get('nodes', []):
                    node_id = node.get('id', '')
                    if node_id:
                        self._indicators[node_id] = {
                            'id': node_id,
                            'label': node.get('label', node_id),
                            'description': node.get('description'),
                            'domain': node.get('domain'),
                            'ring': node.get('ring'),
                            'shap_importance': node.get('shap_value') or node.get('shap_importance'),
                        }
            except Exception:
                pass

        # Supplement with indicators found in country graphs
        self._supplement_from_country_graphs()

    def _supplement_from_country_graphs(self):
        """Add indicators found in country graphs but not in V2.1."""
        if not GRAPHS_DIR.exists():
            return

        # Scan a few graphs to find additional indicators
        for graph_file in list(GRAPHS_DIR.glob("*.json"))[:10]:
            if graph_file.name.startswith("_"):
                continue

            try:
                with open(graph_file) as f:
                    graph = json.load(f)

                for edge in graph.get('edges', []):
                    for node_id in [edge.get('source'), edge.get('target')]:
                        if node_id and node_id not in self._indicators:
                            self._indicators[node_id] = {
                                'id': node_id,
                                'label': node_id,
                                'description': None,
                                'domain': None,
                                'ring': None,
                                'shap_importance': None,
                            }
            except Exception:
                continue

    def _compute_graph_stats(self):
        """Compute in/out degree for indicators across all graphs."""
        if self._graph_stats is not None:
            return

        self._graph_stats = defaultdict(lambda: {'in_degree': 0, 'out_degree': 0})

        if not GRAPHS_DIR.exists():
            return

        for graph_file in GRAPHS_DIR.glob("*.json"):
            if graph_file.name.startswith("_"):
                continue

            try:
                with open(graph_file) as f:
                    graph = json.load(f)

                for edge in graph.get('edges', []):
                    source = edge.get('source')
                    target = edge.get('target')
                    if source:
                        self._graph_stats[source]['out_degree'] += 1
                    if target:
                        self._graph_stats[target]['in_degree'] += 1
            except Exception:
                continue

    def get_all_indicators(self) -> List[dict]:
        """Get list of all indicators with basic metadata, sorted by importance."""
        self._load_indicators()

        if self._indicator_list is None:
            self._indicator_list = [
                {
                    'id': ind['id'],
                    'label': ind.get('label'),
                    'domain': ind.get('domain'),
                    'importance': ind.get('shap_importance') or 0
                }
                for ind in self._indicators.values()
            ]
            # Sort by importance descending (most important first)
            self._indicator_list.sort(key=lambda x: (-(x['importance'] or 0), x['id']))

        return self._indicator_list

    def get_indicator_detail(self, indicator_id: str) -> Optional[dict]:
        """
        Get detailed indicator information for rich tooltips.

        Returns:
            Dict with id, label, description, domain, ring,
            shap_importance, in_degree, out_degree, data_available
        """
        self._load_indicators()
        self._compute_graph_stats()

        if indicator_id not in self._indicators:
            return None

        ind = self._indicators[indicator_id]
        stats = self._graph_stats.get(indicator_id, {'in_degree': 0, 'out_degree': 0})

        return {
            'id': ind['id'],
            'label': ind.get('label'),
            'description': ind.get('description'),
            'domain': ind.get('domain'),
            'ring': ind.get('ring'),
            'shap_importance': ind.get('shap_importance'),
            'in_degree': stats['in_degree'],
            'out_degree': stats['out_degree'],
            'data_available': True  # If we found it, data exists
        }

    def indicator_exists(self, indicator_id: str) -> bool:
        """Check if indicator exists in catalog."""
        self._load_indicators()
        return indicator_id in self._indicators

    def get_indicators_by_domain(self, domain: str) -> List[dict]:
        """Get all indicators in a specific domain."""
        self._load_indicators()

        return [
            {
                'id': ind['id'],
                'label': ind.get('label'),
                'domain': ind.get('domain')
            }
            for ind in self._indicators.values()
            if ind.get('domain') == domain
        ]

    def get_domains(self) -> List[str]:
        """Get list of all indicator domains."""
        self._load_indicators()

        domains = set()
        for ind in self._indicators.values():
            if ind.get('domain'):
                domains.add(ind['domain'])

        return sorted(list(domains))

    def search_indicators(self, query: str, limit: int = 20) -> List[dict]:
        """Search indicators by ID or label."""
        self._load_indicators()

        query_lower = query.lower()
        results = []

        for ind in self._indicators.values():
            # Check ID match
            if query_lower in ind['id'].lower():
                results.append(ind)
                continue

            # Check label match
            label = ind.get('label', '')
            if label and query_lower in label.lower():
                results.append(ind)

        # Sort by relevance (exact ID match first, then by ID)
        results.sort(key=lambda x: (
            0 if x['id'].lower() == query_lower else 1,
            x['id']
        ))

        return [
            {'id': r['id'], 'label': r.get('label'), 'domain': r.get('domain')}
            for r in results[:limit]
        ]


# Singleton instance
indicator_service = IndicatorService()
