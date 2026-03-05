/**
 * Country Aggregation Utility
 *
 * Computes Ring 0-4 aggregate values from Ring 5 indicator values
 * using bottom-up aggregation (mean of children).
 *
 * Data Flow:
 * 1. Country graph provides edge-based indicators (source/target pairs)
 * 2. Extract unique indicators from graph edges
 * 3. Run minimal simulation to get baseline values for those indicators
 * 4. Aggregate upward: Ring 5 → Ring 4 → Ring 3 → Ring 2 → Ring 1 → Ring 0
 */

import type { RawNodeV21 } from '../types'
import type { CountryGraphEdge } from '../services/api'

/**
 * Node with optional country-specific value
 */
export interface NodeWithCountryValue extends RawNodeV21 {
  countryValue?: number
}

/**
 * Extract unique indicator IDs from country graph edges
 * These are Ring 5 nodes (leaf indicators)
 */
export function extractIndicatorsFromGraph(edges: CountryGraphEdge[]): Set<string> {
  const indicators = new Set<string>()
  for (const edge of edges) {
    indicators.add(edge.source)
    indicators.add(edge.target)
  }
  return indicators
}

/**
 * Build a parent-child lookup map from hierarchy nodes
 * Returns: Map<parentId, childIds[]>
 */
export function buildChildrenMap(nodes: RawNodeV21[]): Map<string | number, (string | number)[]> {
  const childrenMap = new Map<string | number, (string | number)[]>()

  for (const node of nodes) {
    if (node.parent !== undefined && node.parent !== null) {
      const existing = childrenMap.get(node.parent) || []
      existing.push(node.id)
      childrenMap.set(node.parent, existing)
    }
  }

  return childrenMap
}

/**
 * Compute Ring 0-4 aggregate values from Ring 5 baseline values
 *
 * @param baselineValues - Map of indicator ID → baseline value (Ring 5 only)
 * @param hierarchyNodes - All nodes in the hierarchy (Ring 0-5)
 * @returns Updated nodes with countryValue set
 */
export function computeCountryHierarchy(
  baselineValues: Record<string, number>,
  hierarchyNodes: RawNodeV21[]
): NodeWithCountryValue[] {
  // Create a mutable copy with countryValue field
  const nodes: NodeWithCountryValue[] = hierarchyNodes.map(n => ({ ...n }))
  const nodeMap = new Map<string | number, NodeWithCountryValue>()

  for (const node of nodes) {
    nodeMap.set(node.id, node)
  }

  // Build children map
  const childrenMap = buildChildrenMap(nodes)

  // Step 1: Set Ring 5 values from baselines
  for (const node of nodes) {
    if (node.layer === 5) {
      const value = baselineValues[String(node.id)]
      if (value !== undefined && !isNaN(value)) {
        node.countryValue = value
      }
    }
  }

  // Step 2: Bottom-up aggregation from Ring 4 to Ring 0
  // Process rings in descending order (4, 3, 2, 1, 0)
  for (let ring = 4; ring >= 0; ring--) {
    const ringNodes = nodes.filter(n => n.layer === ring)

    for (const node of ringNodes) {
      const childIds = childrenMap.get(node.id) || []
      const childValues: number[] = []

      for (const childId of childIds) {
        const child = nodeMap.get(childId)
        if (child?.countryValue !== undefined && !isNaN(child.countryValue)) {
          childValues.push(child.countryValue)
        }
      }

      if (childValues.length > 0) {
        // Use mean of children as aggregate value
        node.countryValue = childValues.reduce((a, b) => a + b, 0) / childValues.length
      }
    }
  }

  return nodes
}

/**
 * Get the coverage of country-specific values across the hierarchy
 *
 * @returns Object with counts of nodes with/without values per ring
 */
export function getHierarchyCoverage(nodes: NodeWithCountryValue[]): Record<number, { total: number; withValue: number }> {
  const coverage: Record<number, { total: number; withValue: number }> = {}

  for (const node of nodes) {
    const ring = node.layer
    if (!coverage[ring]) {
      coverage[ring] = { total: 0, withValue: 0 }
    }
    coverage[ring].total++
    if (node.countryValue !== undefined) {
      coverage[ring].withValue++
    }
  }

  return coverage
}

/**
 * Create a lookup map from node ID to country value
 */
export function createCountryValueMap(nodes: NodeWithCountryValue[]): Map<string | number, number> {
  const valueMap = new Map<string | number, number>()

  for (const node of nodes) {
    if (node.countryValue !== undefined) {
      valueMap.set(node.id, node.countryValue)
    }
  }

  return valueMap
}

/**
 * Compute which nodes have data coverage for a country
 * A node has coverage if:
 * - It's a Ring 5 indicator that appears in the country graph edges
 * - It's a Ring 0-4 node with at least one descendant that has coverage
 *
 * @param countryIndicators - Set of indicator IDs that have data in the country graph
 * @param hierarchyNodes - All nodes in the hierarchy
 * @returns Set of node IDs that have coverage
 */
export function computeCountryCoverage(
  countryIndicators: Set<string>,
  hierarchyNodes: RawNodeV21[]
): Set<string> {
  const coveredNodes = new Set<string>()
  const nodeMap = new Map<string | number, RawNodeV21>()
  const childrenMap = buildChildrenMap(hierarchyNodes)

  for (const node of hierarchyNodes) {
    nodeMap.set(node.id, node)
  }

  // Helper to recursively check if a node or its descendants have coverage
  const checkCoverage = (nodeId: string | number): boolean => {
    const strId = String(nodeId)

    // If already computed, return result
    if (coveredNodes.has(strId)) return true

    const node = nodeMap.get(nodeId)
    if (!node) return false

    // Ring 5: check if indicator is in country graph
    if (node.layer === 5) {
      if (countryIndicators.has(strId)) {
        coveredNodes.add(strId)
        return true
      }
      return false
    }

    // Ring 0-4: check if any child has coverage
    const children = childrenMap.get(nodeId) || []
    for (const childId of children) {
      if (checkCoverage(childId)) {
        coveredNodes.add(strId)
        return true
      }
    }

    return false
  }

  // Check coverage for all nodes
  for (const node of hierarchyNodes) {
    checkCoverage(node.id)
  }

  return coveredNodes
}
