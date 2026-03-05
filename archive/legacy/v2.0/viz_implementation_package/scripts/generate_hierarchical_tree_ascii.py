#!/usr/bin/env python3
"""
Hierarchical Tree ASCII Visualizer

Generates non-binary ASCII tree visualizations from the causal graph schema.
Supports multiple visualization modes and configurable depth/breadth limits.

Usage:
    python generate_hierarchical_tree_ascii.py [--max-depth DEPTH] [--max-children CHILDREN]

Options:
    --max-depth DEPTH        Maximum tree depth to display (default: 4)
    --max-children CHILDREN  Maximum children per node (default: 8)
    --mode MODE              Visualization mode: root-to-leaf, outcome-centric, or domain-grouped (default: root-to-leaf)
    --output FILE            Output file path (default: hierarchical_trees.txt)

Examples:
    # Default visualization
    python generate_hierarchical_tree_ascii.py

    # Custom depth and breadth
    python generate_hierarchical_tree_ascii.py --max-depth 5 --max-children 10

    # Outcome-centric mode
    python generate_hierarchical_tree_ascii.py --mode outcome-centric

Author: V2.0 Global Causal Discovery Team
Date: November 21, 2025
"""

import json
import argparse
from pathlib import Path
from typing import Dict, List, Set, Tuple
from collections import defaultdict


class HierarchicalTreeVisualizer:
    """Generates ASCII hierarchical tree visualizations from causal graph."""

    def __init__(self, schema_path: str, max_depth: int = 4, max_children: int = 8):
        """
        Initialize visualizer.

        Args:
            schema_path: Path to causal_graph_v2_final.json
            max_depth: Maximum tree depth to display
            max_children: Maximum children per node to display
        """
        self.max_depth = max_depth
        self.max_children = max_children

        # Load schema
        with open(schema_path) as f:
            self.schema = json.load(f)

        # Build lookup structures
        self._build_lookups()

    def _build_lookups(self):
        """Build node and edge lookup structures."""
        # Node lookups
        self.nodes_by_id = {
            node['id']: node
            for node in self.schema['graphs']['full']['nodes']
        }

        # Edge lookups (adjacency lists)
        self.children_map = defaultdict(list)  # parent -> [children]
        self.parent_map = defaultdict(list)    # child -> [parents]

        for edge in self.schema['graphs']['full']['edges']:
            source = edge['source']
            target = edge['target']
            self.children_map[source].append({
                'id': target,
                'effect': edge['effect'],
                'lag': edge['lag']
            })
            self.parent_map[target].append({
                'id': source,
                'effect': edge['effect'],
                'lag': edge['lag']
            })

        # Sort children by effect size (largest first)
        for node_id in self.children_map:
            self.children_map[node_id].sort(
                key=lambda x: abs(x['effect']),
                reverse=True
            )

        # Identify root nodes (no parents)
        self.root_nodes = [
            node_id for node_id in self.nodes_by_id
            if node_id not in self.parent_map
        ]

        # Identify leaf nodes (outcomes, no children)
        self.leaf_nodes = [
            node_id for node_id in self.nodes_by_id
            if node_id.startswith('Factor_')
        ]

    def _format_node_label(self, node_id: str, effect: float = None, lag: int = None) -> str:
        """
        Format node label for display.

        Args:
            node_id: Node identifier
            effect: Causal effect size (optional)
            lag: Temporal lag (optional)

        Returns:
            Formatted label string
        """
        node = self.nodes_by_id[node_id]

        # Base label
        label = node['label']

        # Truncate if too long
        if len(label) > 60:
            label = label[:57] + "..."

        # Add domain tag
        domain_tag = f"[{node['domain']}]"

        # Add effect and lag if provided
        effect_tag = ""
        if effect is not None:
            sign = "+" if effect > 0 else ""
            effect_tag = f" (β={sign}{effect:.3f}, lag={lag}y)"

        return f"{label} {domain_tag}{effect_tag}"

    def _render_tree_recursive(
        self,
        node_id: str,
        prefix: str = "",
        is_last: bool = True,
        depth: int = 0,
        visited: Set[str] = None,
        effect: float = None,
        lag: int = None
    ) -> List[str]:
        """
        Recursively render tree using ASCII art.

        Args:
            node_id: Current node ID
            prefix: Line prefix for indentation
            is_last: Whether this is the last child
            depth: Current depth
            visited: Set of visited nodes (cycle detection)
            effect: Effect size from parent
            lag: Temporal lag from parent

        Returns:
            List of formatted lines
        """
        if visited is None:
            visited = set()

        lines = []

        # Check depth limit
        if depth >= self.max_depth:
            return lines

        # Check for cycles
        if node_id in visited:
            cycle_marker = f"{prefix}{'└── ' if is_last else '├── '}(CYCLE DETECTED)"
            lines.append(cycle_marker)
            return lines

        visited.add(node_id)

        # Current node line
        connector = "└── " if is_last else "├── "
        label = self._format_node_label(node_id, effect, lag)
        lines.append(f"{prefix}{connector}{label}")

        # Get children
        children = self.children_map.get(node_id, [])

        # Limit children
        if len(children) > self.max_children:
            children = children[:self.max_children]
            truncated = True
        else:
            truncated = False

        # Recurse for children
        for i, child_data in enumerate(children):
            child_id = child_data['id']
            child_effect = child_data['effect']
            child_lag = child_data['lag']
            is_last_child = (i == len(children) - 1) and not truncated

            # Update prefix
            if is_last:
                child_prefix = prefix + "    "
            else:
                child_prefix = prefix + "│   "

            # Recurse
            child_lines = self._render_tree_recursive(
                child_id,
                child_prefix,
                is_last_child,
                depth + 1,
                visited.copy(),
                child_effect,
                child_lag
            )
            lines.extend(child_lines)

        # Add truncation marker
        if truncated:
            remaining = len(self.children_map.get(node_id, [])) - self.max_children
            if is_last:
                marker_prefix = prefix + "    "
            else:
                marker_prefix = prefix + "│   "
            lines.append(f"{marker_prefix}└── ... ({remaining} more children)")

        return lines

    def generate_root_to_leaf_trees(self) -> str:
        """
        Generate root-to-leaf tree visualizations.

        Returns:
            Complete ASCII tree visualization as string
        """
        output = []
        output.append("=" * 80)
        output.append("HIERARCHICAL TREE VISUALIZATION: ROOT-TO-LEAF")
        output.append("=" * 80)
        output.append("")
        output.append(f"Configuration:")
        output.append(f"  Max Depth: {self.max_depth}")
        output.append(f"  Max Children: {self.max_children}")
        output.append(f"  Total Nodes: {len(self.nodes_by_id)}")
        output.append(f"  Root Nodes: {len(self.root_nodes)}")
        output.append("")

        # Sort roots by SHAP score (if available)
        roots_with_shap = []
        roots_without_shap = []

        for root_id in self.root_nodes:
            node = self.nodes_by_id[root_id]
            if node.get('shap_available', False):
                roots_with_shap.append((root_id, node['shap_score']))
            else:
                roots_without_shap.append(root_id)

        roots_with_shap.sort(key=lambda x: x[1], reverse=True)
        sorted_roots = [r[0] for r in roots_with_shap] + roots_without_shap

        # Limit number of root trees
        max_root_trees = 10
        if len(sorted_roots) > max_root_trees:
            sorted_roots = sorted_roots[:max_root_trees]
            output.append(f"Displaying top {max_root_trees} root trees (by SHAP importance)")
            output.append("")

        # Generate tree for each root
        for i, root_id in enumerate(sorted_roots, 1):
            output.append("-" * 80)
            output.append(f"Tree {i}/{len(sorted_roots)}")
            output.append("-" * 80)

            tree_lines = self._render_tree_recursive(root_id)
            output.extend(tree_lines)
            output.append("")

        return "\n".join(output)

    def generate_outcome_centric_trees(self) -> str:
        """
        Generate outcome-centric tree visualizations (outcomes as roots).

        Returns:
            Complete ASCII tree visualization as string
        """
        output = []
        output.append("=" * 80)
        output.append("HIERARCHICAL TREE VISUALIZATION: OUTCOME-CENTRIC")
        output.append("=" * 80)
        output.append("")
        output.append(f"Configuration:")
        output.append(f"  Max Depth: {self.max_depth}")
        output.append(f"  Max Children: {self.max_children}")
        output.append(f"  Total Outcomes: {len(self.leaf_nodes)}")
        output.append("")

        # Generate tree for each outcome (inverted: parents as children)
        for i, outcome_id in enumerate(self.leaf_nodes, 1):
            output.append("-" * 80)
            output.append(f"Outcome {i}/{len(self.leaf_nodes)}")
            output.append("-" * 80)

            # Build inverted tree (parents as children)
            tree_lines = self._render_inverted_tree(outcome_id)
            output.extend(tree_lines)
            output.append("")

        return "\n".join(output)

    def _render_inverted_tree(
        self,
        node_id: str,
        prefix: str = "",
        is_last: bool = True,
        depth: int = 0,
        visited: Set[str] = None
    ) -> List[str]:
        """
        Render inverted tree (parents as children).

        Args:
            node_id: Current node ID
            prefix: Line prefix
            is_last: Last child flag
            depth: Current depth
            visited: Visited set

        Returns:
            List of formatted lines
        """
        if visited is None:
            visited = set()

        lines = []

        if depth >= self.max_depth:
            return lines

        if node_id in visited:
            cycle_marker = f"{prefix}{'└── ' if is_last else '├── '}(CYCLE DETECTED)"
            lines.append(cycle_marker)
            return lines

        visited.add(node_id)

        # Current node
        connector = "└── " if is_last else "├── "
        label = self._format_node_label(node_id)
        lines.append(f"{prefix}{connector}{label}")

        # Get parents (as "children" in inverted tree)
        parents = self.parent_map.get(node_id, [])

        # Sort by effect size
        parents.sort(key=lambda x: abs(x['effect']), reverse=True)

        # Limit
        if len(parents) > self.max_children:
            parents = parents[:self.max_children]
            truncated = True
        else:
            truncated = False

        # Recurse
        for i, parent_data in enumerate(parents):
            parent_id = parent_data['id']
            is_last_parent = (i == len(parents) - 1) and not truncated

            if is_last:
                parent_prefix = prefix + "    "
            else:
                parent_prefix = prefix + "│   "

            parent_lines = self._render_inverted_tree(
                parent_id,
                parent_prefix,
                is_last_parent,
                depth + 1,
                visited.copy()
            )
            lines.extend(parent_lines)

        if truncated:
            remaining = len(self.parent_map.get(node_id, [])) - self.max_children
            if is_last:
                marker_prefix = prefix + "    "
            else:
                marker_prefix = prefix + "│   "
            lines.append(f"{marker_prefix}└── ... ({remaining} more parents)")

        return lines

    def generate_domain_grouped_trees(self) -> str:
        """
        Generate domain-grouped tree visualizations.

        Returns:
            Complete ASCII tree visualization as string
        """
        output = []
        output.append("=" * 80)
        output.append("HIERARCHICAL TREE VISUALIZATION: DOMAIN-GROUPED")
        output.append("=" * 80)
        output.append("")

        # Group nodes by domain
        domain_groups = defaultdict(list)
        for node_id in self.root_nodes:
            node = self.nodes_by_id[node_id]
            domain = node['domain']
            domain_groups[domain].append(node_id)

        output.append(f"Configuration:")
        output.append(f"  Max Depth: {self.max_depth}")
        output.append(f"  Max Children: {self.max_children}")
        output.append(f"  Domains: {len(domain_groups)}")
        output.append("")

        # Generate tree for each domain
        for domain in sorted(domain_groups.keys()):
            roots = domain_groups[domain]

            output.append("=" * 80)
            output.append(f"DOMAIN: {domain} ({len(roots)} root nodes)")
            output.append("=" * 80)
            output.append("")

            # Limit roots per domain
            max_domain_roots = 5
            if len(roots) > max_domain_roots:
                roots = roots[:max_domain_roots]

            for i, root_id in enumerate(roots, 1):
                output.append("-" * 80)
                output.append(f"{domain} - Tree {i}/{len(roots)}")
                output.append("-" * 80)

                tree_lines = self._render_tree_recursive(root_id)
                output.extend(tree_lines)
                output.append("")

        return "\n".join(output)


def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(
        description="Generate hierarchical tree ASCII visualizations",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__
    )
    parser.add_argument(
        '--max-depth',
        type=int,
        default=4,
        help='Maximum tree depth (default: 4)'
    )
    parser.add_argument(
        '--max-children',
        type=int,
        default=8,
        help='Maximum children per node (default: 8)'
    )
    parser.add_argument(
        '--mode',
        choices=['root-to-leaf', 'outcome-centric', 'domain-grouped'],
        default='root-to-leaf',
        help='Visualization mode (default: root-to-leaf)'
    )
    parser.add_argument(
        '--output',
        type=str,
        default='hierarchical_trees.txt',
        help='Output file path (default: hierarchical_trees.txt)'
    )

    args = parser.parse_args()

    # Find schema file
    script_dir = Path(__file__).parent
    schema_path = script_dir.parent / 'data' / 'causal_graph_v2_final.json'

    if not schema_path.exists():
        print(f"❌ Error: Schema file not found at {schema_path}")
        print(f"   Please ensure causal_graph_v2_final.json is in the data/ directory")
        return 1

    print(f"📊 Loading schema from {schema_path}...")
    visualizer = HierarchicalTreeVisualizer(
        str(schema_path),
        max_depth=args.max_depth,
        max_children=args.max_children
    )

    print(f"🌳 Generating {args.mode} tree visualization...")

    # Generate visualization based on mode
    if args.mode == 'root-to-leaf':
        output = visualizer.generate_root_to_leaf_trees()
    elif args.mode == 'outcome-centric':
        output = visualizer.generate_outcome_centric_trees()
    elif args.mode == 'domain-grouped':
        output = visualizer.generate_domain_grouped_trees()

    # Write output
    output_path = Path(args.output)
    with open(output_path, 'w', encoding='utf-8') as f:
        f.write(output)

    print(f"✅ Tree visualization saved to {output_path}")
    print(f"   Lines: {len(output.splitlines())}")
    print(f"   Size: {len(output) / 1024:.1f} KB")

    return 0


if __name__ == '__main__':
    exit(main())
