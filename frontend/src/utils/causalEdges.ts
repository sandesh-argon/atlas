/**
 * Causal Edge Utilities
 *
 * Functions for extracting, filtering, and grouping causal edges
 * from the visualization data for Local View.
 *
 * Supports country-specific edge weights via countryGraphToRawEdges()
 */

import type { RawEdge, RawNodeV21, LocalViewEdge, LocalViewNode, LocalNodeShape, LocalViewMode, EdgePathway } from '../types'
import type { CountryGraphEdge, CausalPathEntry, TemporalEffect } from '../services/api'

/** Default beta threshold for filtering edges */
export const DEFAULT_BETA_THRESHOLD = 0.5

/** Maximum beta value to consider (filters outliers) */
export const MAX_BETA_VALUE = 100

/**
 * Visual Beta Propagation Constants
 *
 * These control how node sizes are calculated in Local View based on causal strength.
 *
 * VISUAL_BETA_PARENT_CAP: Maximum ratio of child to parent visualBeta
 *   - Lower = more compression, children always much smaller than parents
 *   - Higher = allow strong edges to create larger children
 *   - Old: 0.65 (compressed all children to <52% of target)
 *   - New: 0.90 (allow up to 90% for very strong edges)
 *
 * VISUAL_BETA_DEPTH_SHRINK: Multiplier applied per depth level
 *   - Lower = rapid size decrease with depth
 *   - 1.0 = no shrinking based on depth alone
 *   - Old: 0.80 (20% shrink per level)
 *   - New: 0.95 (only 5% shrink per level, let beta drive differentiation)
 */
export const VISUAL_BETA_PARENT_CAP = 0.90
export const VISUAL_BETA_DEPTH_SHRINK = 0.95

/**
 * Convert country-specific graph edges to RawEdge format
 * This allows using country data with existing Local View functions
 *
 * @param countryEdges - Edges from API's /graph/{country} endpoint
 * @param useCountryBeta - If true, use country-specific beta; if false, use global_beta
 * @returns RawEdge[] compatible with getCausalEdges and other functions
 */
export function countryGraphToRawEdges(
  countryEdges: CountryGraphEdge[],
  useCountryBeta: boolean = true
): RawEdge[] {
  return countryEdges.map(edge => ({
    source: edge.source,
    target: edge.target,
    weight: useCountryBeta ? edge.beta : edge.global_beta,
    relationship: 'causal' as const
  }))
}

/**
 * Create a beta lookup map from country graph edges
 * Key format: "source->target"
 *
 * @param countryEdges - Edges from country graph
 * @returns Map of edge key to country-specific beta
 */
export function createCountryBetaMap(
  countryEdges: CountryGraphEdge[]
): Map<string, { beta: number; globalBeta: number; ciLower: number; ciUpper: number }> {
  const betaMap = new Map<string, { beta: number; globalBeta: number; ciLower: number; ciUpper: number }>()

  for (const edge of countryEdges) {
    const key = `${edge.source}->${edge.target}`
    betaMap.set(key, {
      beta: edge.beta,
      globalBeta: edge.global_beta,
      ciLower: edge.ci_lower,
      ciUpper: edge.ci_upper
    })
  }

  return betaMap
}

/**
 * Override edge betas with country-specific values where available
 *
 * @param edges - Original edges (from unified model)
 * @param countryBetaMap - Map from createCountryBetaMap()
 * @returns Edges with country-specific betas applied
 */
export function applyCountryBetas(
  edges: LocalViewEdge[],
  countryBetaMap: Map<string, { beta: number; globalBeta: number; ciLower: number; ciUpper: number }>
): LocalViewEdge[] {
  return edges.map(edge => {
    const key = `${edge.source}->${edge.target}`
    const countryData = countryBetaMap.get(key)

    if (countryData) {
      return {
        ...edge,
        beta: countryData.beta
      }
    }
    return edge
  })
}

/**
 * Extract causal edges from raw edges
 * @param ringFilter - If provided, only return edges where BOTH source and target are at this ring level
 */
export function getCausalEdges(
  edges: RawEdge[],
  nodeById?: Map<string, RawNodeV21>,
  ringFilter?: number
): LocalViewEdge[] {
  let filtered = edges
    .filter(e => e.relationship === 'causal' && e.weight !== undefined)
    .filter(e => Math.abs(e.weight!) <= MAX_BETA_VALUE) // Filter outliers

  // If ring filter is provided, only include same-ring edges
  if (ringFilter !== undefined && nodeById) {
    filtered = filtered.filter(e => {
      const srcNode = nodeById.get(e.source)
      const tgtNode = nodeById.get(e.target)
      return srcNode?.layer === ringFilter && tgtNode?.layer === ringFilter
    })
  }

  return filtered.map(e => ({
    source: e.source,
    target: e.target,
    beta: e.weight!,
    sourceSector: '', // Will be filled by getSectorForNode
    targetSector: ''
  }))
}

/**
 * Get the Ring 1 ancestor (sector/outcome) for a node
 */
export function getSectorForNode(
  nodeId: string,
  nodeById: Map<string, RawNodeV21>
): string {
  let current = nodeById.get(nodeId)

  while (current) {
    if (current.layer === 1) {
      return current.label
    }
    if (current.parent) {
      current = nodeById.get(String(current.parent))
    } else {
      break
    }
  }

  return 'Unknown'
}

/**
 * Get incoming edges (causes) for a target node
 */
export function getIncomingEdges(
  targetId: string,
  allEdges: LocalViewEdge[],
  threshold: number = DEFAULT_BETA_THRESHOLD
): LocalViewEdge[] {
  return allEdges
    .filter(e => e.target === targetId && Math.abs(e.beta) >= threshold)
    .sort((a, b) => Math.abs(b.beta) - Math.abs(a.beta)) // Sort by strength
}

/**
 * Get outgoing edges (effects) for a target node
 */
export function getOutgoingEdges(
  targetId: string,
  allEdges: LocalViewEdge[],
  threshold: number = DEFAULT_BETA_THRESHOLD
): LocalViewEdge[] {
  return allEdges
    .filter(e => e.source === targetId && Math.abs(e.beta) >= threshold)
    .sort((a, b) => Math.abs(b.beta) - Math.abs(a.beta))
}

/**
 * Get all Ring 5 (indicator) descendants of a node
 * Recursively traverses hierarchy to find all leaf indicators
 */
function getAllIndicatorDescendants(
  nodeId: string,
  nodeById: Map<string, RawNodeV21>
): string[] {
  const node = nodeById.get(nodeId)
  if (!node) return []

  // If this IS a Ring 5 indicator, return it
  if (node.layer === 5) return [nodeId]

  // Otherwise, recursively get all children's indicators
  const indicators: string[] = []
  if (node.children) {
    for (const childId of node.children) {
      indicators.push(...getAllIndicatorDescendants(String(childId), nodeById))
    }
  }
  return indicators
}

/**
 * Get ancestor at a specific ring level
 */
function getAncestorAtRing(
  nodeId: string,
  targetRing: number,
  nodeById: Map<string, RawNodeV21>
): RawNodeV21 | null {
  let current = nodeById.get(nodeId)

  while (current) {
    if (current.layer === targetRing) return current
    if (current.layer < targetRing) return null // Gone too high
    if (current.parent) {
      current = nodeById.get(String(current.parent))
    } else {
      break
    }
  }
  return null
}

/**
 * Check if a node has direct same-ring causal edges
 */
export function hasDirectSameRingEdges(
  nodeId: string,
  allEdges: RawEdge[],
  nodeById: Map<string, RawNodeV21>
): boolean {
  const node = nodeById.get(nodeId)
  if (!node) return false
  const ring = node.layer

  return allEdges.some(e => {
    if (e.relationship !== 'causal') return false
    const src = nodeById.get(e.source)
    const tgt = nodeById.get(e.target)
    if (!src || !tgt) return false
    if (src.layer !== ring || tgt.layer !== ring) return false
    return e.source === nodeId || e.target === nodeId
  })
}

/**
 * Aggregate descendant indicator edges upward to target ring level
 * Works for Ring 1-4 nodes by finding their Ring 5 descendants' edges
 * and grouping by ancestor at target ring level
 */
export function aggregateChildEdges(
  targetIds: string[],
  allEdges: RawEdge[],
  nodeById: Map<string, RawNodeV21>,
  threshold: number = DEFAULT_BETA_THRESHOLD
): {
  inputEdges: Map<string, { edge: LocalViewEdge; pathways: EdgePathway[] }>
  outputEdges: Map<string, { edge: LocalViewEdge; pathways: EdgePathway[] }>
  activeChildCount: number
  totalChildCount: number
} {
  // Determine target ring from first target
  const firstTarget = targetIds[0] ? nodeById.get(targetIds[0]) : undefined
  const targetRing = firstTarget?.layer ?? 4

  // Get all Ring 5 causal edges (the base causal data)
  const ring5Edges = getCausalEdges(allEdges, nodeById, 5)

  // Collect all Ring 5 indicator descendants of target nodes
  const targetIndicatorIds = new Set<string>()
  for (const targetId of targetIds) {
    const indicators = getAllIndicatorDescendants(targetId, nodeById)
    indicators.forEach(id => targetIndicatorIds.add(id))
  }
  const totalChildCount = targetIndicatorIds.size

  // Maps for aggregated edges
  const inputEdges = new Map<string, { edge: LocalViewEdge; pathways: EdgePathway[] }>()
  const outputEdges = new Map<string, { edge: LocalViewEdge; pathways: EdgePathway[] }>()

  // Track which indicators have edges
  const activeIndicatorIds = new Set<string>()

  // Process each Ring 5 edge
  for (const edge of ring5Edges) {
    const isInputToIndicator = targetIndicatorIds.has(edge.target)
    const isOutputFromIndicator = targetIndicatorIds.has(edge.source)

    // Skip edges below threshold
    if (Math.abs(edge.beta) < threshold) continue

    if (isInputToIndicator) {
      // This edge points TO one of our indicators
      activeIndicatorIds.add(edge.target)

      // Get ancestors at target ring level
      const sourceAncestor = getAncestorAtRing(edge.source, targetRing, nodeById)
      const targetAncestor = getAncestorAtRing(edge.target, targetRing, nodeById)

      if (!sourceAncestor || !targetAncestor) continue

      // Skip internal edges (both endpoints under same target)
      if (targetIndicatorIds.has(edge.source)) continue

      const key = sourceAncestor.id + '->' + targetAncestor.id

      if (!inputEdges.has(key)) {
        inputEdges.set(key, {
          edge: {
            source: String(sourceAncestor.id),
            target: String(targetAncestor.id),
            beta: 0,
            sourceSector: getSectorForNode(String(sourceAncestor.id), nodeById),
            targetSector: getSectorForNode(String(targetAncestor.id), nodeById),
            isAggregated: true,
            pathwayCount: 0,
            pathways: []
          },
          pathways: []
        })
      }

      const agg = inputEdges.get(key)!
      agg.pathways.push({
        childSource: edge.source,
        childTarget: edge.target,
        beta: edge.beta
      })
    }

    if (isOutputFromIndicator) {
      // This edge originates FROM one of our indicators
      activeIndicatorIds.add(edge.source)

      // Get ancestors at target ring level
      const sourceAncestor = getAncestorAtRing(edge.source, targetRing, nodeById)
      const targetAncestor = getAncestorAtRing(edge.target, targetRing, nodeById)

      if (!sourceAncestor || !targetAncestor) continue

      // Skip internal edges
      if (targetIndicatorIds.has(edge.target)) continue

      const key = sourceAncestor.id + '->' + targetAncestor.id

      if (!outputEdges.has(key)) {
        outputEdges.set(key, {
          edge: {
            source: String(sourceAncestor.id),
            target: String(targetAncestor.id),
            beta: 0,
            sourceSector: getSectorForNode(String(sourceAncestor.id), nodeById),
            targetSector: getSectorForNode(String(targetAncestor.id), nodeById),
            isAggregated: true,
            pathwayCount: 0,
            pathways: []
          },
          pathways: []
        })
      }

      const agg = outputEdges.get(key)!
      agg.pathways.push({
        childSource: edge.source,
        childTarget: edge.target,
        beta: edge.beta
      })
    }
  }

  // Calculate averages and attach pathways
  for (const [, agg] of inputEdges) {
    const avgBeta = agg.pathways.reduce((sum, p) => sum + Math.abs(p.beta), 0) / agg.pathways.length
    agg.edge.beta = avgBeta
    agg.edge.pathwayCount = agg.pathways.length
    agg.edge.pathways = agg.pathways.sort((a, b) => Math.abs(b.beta) - Math.abs(a.beta))
  }

  for (const [, agg] of outputEdges) {
    const avgBeta = agg.pathways.reduce((sum, p) => sum + Math.abs(p.beta), 0) / agg.pathways.length
    agg.edge.beta = avgBeta
    agg.edge.pathwayCount = agg.pathways.length
    agg.edge.pathways = agg.pathways.sort((a, b) => Math.abs(b.beta) - Math.abs(a.beta))
  }

  return {
    inputEdges,
    outputEdges,
    activeChildCount: activeIndicatorIds.size,
    totalChildCount
  }
}

/**
 * Group edges by sector (for collapsible groups in Local View)
 */
export function groupEdgesBySector(
  edges: LocalViewEdge[],
  nodeById: Map<string, RawNodeV21>,
  direction: 'incoming' | 'outgoing'
): Map<string, LocalViewEdge[]> {
  const groups = new Map<string, LocalViewEdge[]>()

  for (const edge of edges) {
    const nodeId = direction === 'incoming' ? edge.source : edge.target
    const sector = getSectorForNode(nodeId, nodeById)

    if (!groups.has(sector)) {
      groups.set(sector, [])
    }
    groups.get(sector)!.push({ ...edge, sourceSector: sector })
  }

  // Sort edges within each group by beta magnitude
  for (const [sector, sectorEdges] of groups) {
    groups.set(sector, sectorEdges.sort((a, b) => Math.abs(b.beta) - Math.abs(a.beta)))
  }

  return groups
}

/**
 * Get shape based on node role
 */
function getShapeForRole(role: 'target' | 'input' | 'output'): LocalNodeShape {
  switch (role) {
    case 'target': return 'rectangle'
    case 'input': return 'pill'
    case 'output': return 'hexagon'
  }
}

/**
 * Create LocalViewNode from raw node data
 */
export function toLocalViewNode(
  rawNode: RawNodeV21,
  nodeById: Map<string, RawNodeV21>,
  domainColors: Record<string, string>,
  role: 'target' | 'input' | 'output',
  depth: number = 1,
  beta?: number,
  visualBeta: number = 1.0,
  parentId?: string
): LocalViewNode {
  const sector = getSectorForNode(String(rawNode.id), nodeById)
  const childIds = rawNode.children?.map(c => String(c)) ?? []
  const hasChildren = childIds.length > 0

  return {
    id: String(rawNode.id),
    label: rawNode.label.replace(/_/g, ' '),
    sector,
    sectorColor: domainColors[rawNode.domain || ''] || '#9E9E9E',
    ring: rawNode.layer,
    importance: rawNode.importance ?? 0,
    isTarget: role === 'target',
    isInput: role === 'input',
    isOutput: role === 'output',
    depth,
    shape: getShapeForRole(role),
    beta,
    visualBeta,
    parentId,
    hasChildren,
    childIds
  }
}

/**
 * Build complete Local View data for given targets with per-node expansion
 *
 * Uses PROPAGATED BETAS for visual hierarchy:
 * - Targets have visualBeta = 1.0 (reference point)
 * - Children: visualBeta = parent's visualBeta × edge beta
 * - This ensures visual hierarchy: children always smaller than parents
 *
 * @param expandedInputNodes - Set of node IDs whose causes are expanded (beyond global depth)
 * @param expandedOutputNodes - Set of node IDs whose effects are expanded (beyond global depth)
 * @param maxInputDepth - Global max depth for causes (1-3)
 * @param maxOutputDepth - Global max depth for effects (1-3)
 */
export function buildLocalViewData(
  targetIds: string[],
  allEdges: RawEdge[],
  nodeById: Map<string, RawNodeV21>,
  domainColors: Record<string, string>,
  threshold: number = DEFAULT_BETA_THRESHOLD,
  expandedInputNodes: Set<string> = new Set(),
  expandedOutputNodes: Set<string> = new Set(),
  maxInputDepth: number = 1,
  maxOutputDepth: number = 1
): {
  targets: LocalViewNode[]
  inputs: LocalViewNode[]
  outputs: LocalViewNode[]
  edges: LocalViewEdge[]
  targetRing: number
  mode: LocalViewMode
  activeChildCount?: number
  totalChildCount?: number
} {
  // Determine target ring level from first target
  const firstTarget = targetIds[0] ? nodeById.get(targetIds[0]) : undefined
  const targetRing = firstTarget?.layer ?? 5

  // Check if targets need aggregation (non-Ring-5 nodes without direct same-ring edges)
  // For Ring 1-4, we aggregate from their Ring 5 descendants
  const needsAggregation = targetRing < 5 && targetIds.every(
    id => !hasDirectSameRingEdges(id, allEdges, nodeById)
  )

  // === AGGREGATED MODE: Non-indicator nodes without direct edges ===
  // Uses BFS to support multi-layer traversal at the aggregated ring level
  if (needsAggregation) {
    // Build target nodes
    const targets: LocalViewNode[] = targetIds
      .map(id => nodeById.get(id))
      .filter((n): n is RawNodeV21 => n !== undefined)
      .map(n => {
        const node = toLocalViewNode(n, nodeById, domainColors, 'target', 0, undefined, 1.0, undefined)
        node.hasMoreInputs = false
        node.hasMoreOutputs = false
        node.isInputExpanded = true
        node.isOutputExpanded = true
        return node
      })

    const inputs: LocalViewNode[] = []
    const outputs: LocalViewNode[] = []
    const edges: LocalViewEdge[] = []
    const allCollectedIds = new Set<string>(targetIds)
    const nodeVisualBetaMap = new Map<string, number>()
    const nodeParentMap = new Map<string, string>()
    const hasMoreInputsMap = new Map<string, boolean>()
    const hasMoreOutputsMap = new Map<string, boolean>()

    // Initialize targets with visualBeta = 1.0
    for (const targetId of targetIds) {
      nodeVisualBetaMap.set(targetId, 1.0)
    }

    // === BFS FOR INPUTS (AGGREGATED) ===
    const inputQueue: Array<{ nodeId: string; depth: number }> =
      targetIds.map(id => ({ nodeId: id, depth: 0 }))

    while (inputQueue.length > 0) {
      const { nodeId, depth: parentDepth } = inputQueue.shift()!
      const currentDepth = parentDepth + 1

      // Check expansion criteria
      const isTarget = targetIds.includes(nodeId)
      const withinGlobalDepth = parentDepth < maxInputDepth
      const isExpanded = isTarget || withinGlobalDepth || expandedInputNodes.has(nodeId)

      // Get aggregated inputs for this node
      const nodeAggregated = aggregateChildEdges([nodeId], allEdges, nodeById, threshold)
      const potentialInputs = [...nodeAggregated.inputEdges.values()]
        .filter(({ edge }) => !allCollectedIds.has(edge.source))

      // Mark if has unexpanded inputs
      if (potentialInputs.length > 0 && !isTarget) {
        hasMoreInputsMap.set(nodeId, !isExpanded)
      }

      if (!isExpanded) continue

      const parentVisualBeta = nodeVisualBetaMap.get(nodeId) ?? 1.0

      for (const { edge } of potentialInputs) {
        const rawNode = nodeById.get(edge.source)
        if (!rawNode) continue

        allCollectedIds.add(edge.source)

        // Calculate visual beta with propagation
        const edgeBeta = Math.abs(edge.beta)
        const cappedBeta = Math.min(edgeBeta, parentVisualBeta * VISUAL_BETA_PARENT_CAP)
        const childVisualBeta = cappedBeta * Math.pow(VISUAL_BETA_DEPTH_SHRINK, currentDepth)
        nodeVisualBetaMap.set(edge.source, childVisualBeta)
        nodeParentMap.set(edge.source, edge.target)

        const node = toLocalViewNode(
          rawNode, nodeById, domainColors, 'input',
          currentDepth, edge.beta, childVisualBeta, edge.target
        )
        inputs.push(node)
        edges.push(edge)

        // Continue BFS
        inputQueue.push({ nodeId: edge.source, depth: currentDepth })
      }
    }

    // === BFS FOR OUTPUTS (AGGREGATED) ===
    const outputQueue: Array<{ nodeId: string; depth: number }> =
      targetIds.map(id => ({ nodeId: id, depth: 0 }))

    while (outputQueue.length > 0) {
      const { nodeId, depth: parentDepth } = outputQueue.shift()!
      const currentDepth = parentDepth + 1

      const isTarget = targetIds.includes(nodeId)
      const withinGlobalDepth = parentDepth < maxOutputDepth
      const isExpanded = isTarget || withinGlobalDepth || expandedOutputNodes.has(nodeId)

      const nodeAggregated = aggregateChildEdges([nodeId], allEdges, nodeById, threshold)
      const potentialOutputs = [...nodeAggregated.outputEdges.values()]
        .filter(({ edge }) => !allCollectedIds.has(edge.target))

      if (potentialOutputs.length > 0 && !isTarget) {
        hasMoreOutputsMap.set(nodeId, !isExpanded)
      }

      if (!isExpanded) continue

      const parentVisualBeta = nodeVisualBetaMap.get(nodeId) ?? 1.0

      for (const { edge } of potentialOutputs) {
        const rawNode = nodeById.get(edge.target)
        if (!rawNode) continue

        allCollectedIds.add(edge.target)

        const edgeBeta = Math.abs(edge.beta)
        const cappedBeta = Math.min(edgeBeta, parentVisualBeta * VISUAL_BETA_PARENT_CAP)
        const childVisualBeta = cappedBeta * Math.pow(VISUAL_BETA_DEPTH_SHRINK, currentDepth)
        nodeVisualBetaMap.set(edge.target, childVisualBeta)
        nodeParentMap.set(edge.target, edge.source)

        const node = toLocalViewNode(
          rawNode, nodeById, domainColors, 'output',
          currentDepth, edge.beta, childVisualBeta, edge.source
        )
        outputs.push(node)
        edges.push(edge)

        outputQueue.push({ nodeId: edge.target, depth: currentDepth })
      }
    }

    // Update hasMoreInputs/Outputs on all nodes
    for (const node of inputs) {
      node.hasMoreInputs = hasMoreInputsMap.get(node.id) ?? false
    }
    for (const node of outputs) {
      node.hasMoreOutputs = hasMoreOutputsMap.get(node.id) ?? false
    }
    // Also update targets
    for (const target of targets) {
      target.hasMoreInputs = hasMoreInputsMap.get(target.id) ?? false
      target.hasMoreOutputs = hasMoreOutputsMap.get(target.id) ?? false
    }

    const hasAnyEdges = inputs.length > 0 || outputs.length > 0
    return {
      targets,
      inputs,
      outputs,
      edges,
      targetRing,
      mode: hasAnyEdges ? 'aggregated' : 'empty',
      activeChildCount: 0,
      totalChildCount: 0
    }
  }

  // === DIRECT MODE: Normal same-ring edge processing ===
  // Get causal edges filtered to same-ring connections
  const causalEdges = getCausalEdges(allEdges, nodeById, targetRing)

  // Track all edges and nodes
  const relevantEdges: LocalViewEdge[] = []
  const inputNodes = new Map<string, { depth: number }>()
  const outputNodes = new Map<string, { depth: number }>()

  // All node IDs that are targets or already collected (to avoid duplicates)
  const allCollectedIds = new Set<string>(targetIds)

  // Track the beta, visual beta, and parent for each node
  const nodeBetaMap = new Map<string, number>()         // Original edge beta (for display)
  const nodeVisualBetaMap = new Map<string, number>()   // Propagated beta (for sizing)
  const nodeParentMap = new Map<string, string>()

  // Track which nodes have potential children (for +/- buttons)
  const hasMoreInputsMap = new Map<string, boolean>()
  const hasMoreOutputsMap = new Map<string, boolean>()

  // Track which nodes CAN expand (have any children at current threshold)
  const canExpandMap = new Map<string, boolean>()

  // Initialize targets with visualBeta = 1.0 (reference point)
  for (const targetId of targetIds) {
    nodeVisualBetaMap.set(targetId, 1.0)
  }

  // === COLLECT INPUT NODES (causes) via BFS ===
  // Queue: [nodeId, depth]
  const inputQueue: Array<[string, number]> = targetIds.map(id => [id, 0])

  while (inputQueue.length > 0) {
    const [nodeId, parentDepth] = inputQueue.shift()!
    const currentDepth = parentDepth + 1

    // Check if this node's inputs should be expanded:
    // - Targets always expand
    // - Nodes within global depth limit expand
    // - Individually expanded nodes expand
    const isTarget = targetIds.includes(nodeId)
    const withinGlobalDepth = parentDepth < maxInputDepth
    const isExpanded = isTarget || withinGlobalDepth || expandedInputNodes.has(nodeId)

    // Get incoming edges for this node
    const incoming = getIncomingEdges(nodeId, causalEdges, threshold)

    // Check if there are any potential inputs (for showing +/- button)
    const potentialInputs = incoming.filter(e => !allCollectedIds.has(e.source))
    if (potentialInputs.length > 0 && !targetIds.includes(nodeId)) {
      hasMoreInputsMap.set(nodeId, !isExpanded)
      canExpandMap.set(nodeId, true)  // Has children at current threshold
    }

    // Only add children if this node is expanded
    if (!isExpanded) continue

    const parentVisualBeta = nodeVisualBetaMap.get(nodeId) ?? 1.0

    for (const edge of incoming) {
      // Skip if already collected
      if (allCollectedIds.has(edge.source)) continue

      inputNodes.set(edge.source, { depth: currentDepth })
      allCollectedIds.add(edge.source)

      // Store original beta (for display) and parent
      const edgeBeta = Math.abs(edge.beta)
      nodeBetaMap.set(edge.source, edgeBeta)
      nodeParentMap.set(edge.source, edge.target)

      // Calculate propagated visual beta
      const uncappedBeta = parentVisualBeta * edgeBeta
      const cappedBeta = Math.min(uncappedBeta, parentVisualBeta * VISUAL_BETA_PARENT_CAP)
      const childVisualBeta = cappedBeta * Math.pow(VISUAL_BETA_DEPTH_SHRINK, currentDepth)
      nodeVisualBetaMap.set(edge.source, childVisualBeta)

      // Add edge with sector info
      edge.sourceSector = getSectorForNode(edge.source, nodeById)
      edge.targetSector = getSectorForNode(edge.target, nodeById)
      relevantEdges.push(edge)

      // Add to queue for further expansion
      inputQueue.push([edge.source, currentDepth])
    }
  }

  // === COLLECT OUTPUT NODES (effects) via BFS ===
  const outputQueue: Array<[string, number]> = targetIds.map(id => [id, 0])

  while (outputQueue.length > 0) {
    const [nodeId, parentDepth] = outputQueue.shift()!
    const currentDepth = parentDepth + 1

    // Check if this node's outputs should be expanded:
    // - Targets always expand
    // - Nodes within global depth limit expand
    // - Individually expanded nodes expand
    const isTarget = targetIds.includes(nodeId)
    const withinGlobalDepth = parentDepth < maxOutputDepth
    const isExpanded = isTarget || withinGlobalDepth || expandedOutputNodes.has(nodeId)

    // Get outgoing edges for this node
    const outgoing = getOutgoingEdges(nodeId, causalEdges, threshold)

    // Check if there are any potential outputs (for showing +/- button)
    const potentialOutputs = outgoing.filter(e => !allCollectedIds.has(e.target))
    if (potentialOutputs.length > 0 && !targetIds.includes(nodeId)) {
      hasMoreOutputsMap.set(nodeId, !isExpanded)
      canExpandMap.set(nodeId, true)  // Has children at current threshold
    }

    // Only add children if this node is expanded
    if (!isExpanded) continue

    const parentVisualBeta = nodeVisualBetaMap.get(nodeId) ?? 1.0

    for (const edge of outgoing) {
      // Skip if already collected
      if (allCollectedIds.has(edge.target)) continue

      outputNodes.set(edge.target, { depth: currentDepth })
      allCollectedIds.add(edge.target)

      // Store original beta (for display) and parent
      const edgeBeta = Math.abs(edge.beta)
      nodeBetaMap.set(edge.target, edgeBeta)
      nodeParentMap.set(edge.target, edge.source)

      // Calculate propagated visual beta
      const uncappedBeta = parentVisualBeta * edgeBeta
      const cappedBeta = Math.min(uncappedBeta, parentVisualBeta * VISUAL_BETA_PARENT_CAP)
      const childVisualBeta = cappedBeta * Math.pow(VISUAL_BETA_DEPTH_SHRINK, currentDepth)
      nodeVisualBetaMap.set(edge.target, childVisualBeta)

      // Add edge with sector info
      edge.sourceSector = getSectorForNode(edge.source, nodeById)
      edge.targetSector = getSectorForNode(edge.target, nodeById)
      relevantEdges.push(edge)

      // Add to queue for further expansion
      outputQueue.push([edge.target, currentDepth])
    }
  }

  // Targets are always expanded, so hasMore is always false for them
  for (const targetId of targetIds) {
    hasMoreInputsMap.set(targetId, false)
    hasMoreOutputsMap.set(targetId, false)
  }

  // === BUILD NODE LISTS ===
  const targets: LocalViewNode[] = targetIds
    .map(id => nodeById.get(id))
    .filter((n): n is RawNodeV21 => n !== undefined)
    .map(n => {
      const node = toLocalViewNode(n, nodeById, domainColors, 'target', 0, undefined, 1.0, undefined)
      node.hasMoreInputs = false  // Targets always show their direct children
      node.hasMoreOutputs = false
      node.isInputExpanded = true
      node.isOutputExpanded = true
      return node
    })

  // Build input nodes list
  const inputs: LocalViewNode[] = []
  for (const [id, { depth }] of inputNodes) {
    const rawNode = nodeById.get(id)
    if (rawNode) {
      const beta = nodeBetaMap.get(id)
      const visualBeta = nodeVisualBetaMap.get(id) ?? 0.5
      const parentId = nodeParentMap.get(id)
      const node = toLocalViewNode(rawNode, nodeById, domainColors, 'input', depth, beta, visualBeta, parentId)
      node.hasMoreInputs = hasMoreInputsMap.get(id) ?? false
      node.isInputExpanded = expandedInputNodes.has(id)
      node.canExpand = canExpandMap.get(id) ?? false
      inputs.push(node)
    }
  }

  // Build output nodes list
  const outputs: LocalViewNode[] = []
  for (const [id, { depth }] of outputNodes) {
    const rawNode = nodeById.get(id)
    if (rawNode) {
      const beta = nodeBetaMap.get(id)
      const visualBeta = nodeVisualBetaMap.get(id) ?? 0.5
      const parentId = nodeParentMap.get(id)
      const node = toLocalViewNode(rawNode, nodeById, domainColors, 'output', depth, beta, visualBeta, parentId)
      node.hasMoreOutputs = hasMoreOutputsMap.get(id) ?? false
      node.isOutputExpanded = expandedOutputNodes.has(id)
      node.canExpand = canExpandMap.get(id) ?? false
      outputs.push(node)
    }
  }

  // Determine mode based on whether any edges exist
  const hasAnyEdges = inputs.length > 0 || outputs.length > 0
  const mode: LocalViewMode = hasAnyEdges ? 'direct' : 'empty'

  return {
    targets,
    inputs,
    outputs,
    edges: relevantEdges,
    targetRing,
    mode
  }
}

/**
 * Build Local View data from simulation results (causal_paths + year effects).
 *
 * Transforms simulation output into the same {targets, inputs, outputs, edges}
 * structure that the existing `computeLocalViewLayout` expects.
 *
 * - **targets** = intervention nodes (center column)
 * - **outputs** = positive effect nodes (right side, by hop distance)
 * - **inputs** = negative effect nodes (left side, by hop distance)
 * - Tree structure derived from `causal_paths[id].source` chains
 *
 * @param interventionIds - IDs of the intervention indicator nodes
 * @param causalPaths - causal_paths from TemporalResults
 * @param yearEffects - effects[currentYear] from TemporalResults
 * @param everAffected - set of node IDs that have been affected in any year so far (progressive reveal)
 * @param nodeById - full node lookup
 * @param domainColors - domain → hex color mapping
 */
export function buildSimLocalViewData(
  interventionIds: string[],
  causalPaths: Record<string, CausalPathEntry>,
  yearEffects: Record<string, TemporalEffect>,
  everAffected: Set<string>,
  nodeById: Map<string, RawNodeV21>,
  domainColors: Record<string, string>
): {
  targets: LocalViewNode[]
  inputs: LocalViewNode[]
  outputs: LocalViewNode[]
  edges: LocalViewEdge[]
  targetRing: number
  mode: LocalViewMode
} {
  const interventionSet = new Set(interventionIds)
  const targets: LocalViewNode[] = []
  const inputs: LocalViewNode[] = []
  const outputs: LocalViewNode[] = []
  const edges: LocalViewEdge[] = []
  const includedIds = new Set<string>()

  // Build targets from intervention IDs
  for (const id of interventionIds) {
    const rawNode = nodeById.get(id)
    if (!rawNode) continue
    includedIds.add(id)
    const node = toLocalViewNode(rawNode, nodeById, domainColors, 'target', 0, undefined, 1.0, undefined)
    node.hasMoreInputs = false
    node.hasMoreOutputs = false
    node.isInputExpanded = true
    node.isOutputExpanded = true
    targets.push(node)
  }

  // Collect all nodes from everAffected that have causal path info
  // This includes nodes affected in current year AND nodes from prior years (progressive reveal)
  const affectedNodes: Array<{
    id: string
    hop: number
    source: string
    beta: number
    pctChange: number
    isCurrentYear: boolean
  }> = []

  for (const id of everAffected) {
    if (interventionSet.has(id)) continue // Skip interventions
    const pathEntry = causalPaths[id]
    if (!pathEntry || pathEntry.hop === 0) continue

    const currentEffect = yearEffects[id]
    const pctChange = currentEffect?.percent_change ?? 0
    affectedNodes.push({
      id,
      hop: pathEntry.hop,
      source: pathEntry.source,
      beta: pathEntry.beta,
      pctChange,
      isCurrentYear: !!currentEffect && Math.abs(currentEffect.percent_change) > 0.001
    })
  }

  // Also include bridge nodes (in causal_paths, have source chains, but not directly affected)
  // These connect intervention → affected leaf through intermediate hops
  const bridgeNeeded = new Set<string>()
  for (const node of affectedNodes) {
    let curId = node.source
    let depth = 0
    while (depth < 10) {
      if (interventionSet.has(curId) || includedIds.has(curId)) break
      const entry = causalPaths[curId]
      if (!entry) break
      bridgeNeeded.add(curId)
      if (entry.hop === 0 || !entry.source) break
      curId = entry.source
      depth++
    }
  }

  for (const id of bridgeNeeded) {
    if (everAffected.has(id) || interventionSet.has(id)) continue
    const entry = causalPaths[id]
    if (!entry) continue
    const currentEffect = yearEffects[id]
    const pctChange = currentEffect?.percent_change ?? 0
    affectedNodes.push({
      id,
      hop: entry.hop,
      source: entry.source,
      beta: entry.beta,
      pctChange,
      isCurrentYear: !!currentEffect && Math.abs(currentEffect.percent_change) > 0.001
    })
  }

  // Build node list: negative → inputs (left), positive/zero → outputs (right)
  // Side is determined by CURRENT year's percent_change
  for (const node of affectedNodes) {
    if (includedIds.has(node.id)) continue
    const rawNode = nodeById.get(node.id)
    if (!rawNode) continue
    includedIds.add(node.id)

    // Current year effect determines side (left = negative, right = positive)
    const currentEffect = yearEffects[node.id]
    const currentPct = currentEffect?.percent_change ?? node.pctChange
    const role: 'input' | 'output' = currentPct < 0 ? 'input' : 'output'
    // visualBeta: normalize percent_change to [0.15, 1.0] range for sizing
    // Use log scale so extreme values (100%+) don't dominate
    const absPct = Math.abs(currentPct)
    const visualBeta = Math.max(0.15, Math.min(1.0, 0.15 + 0.85 * (1 - Math.exp(-absPct / 10))))

    // Determine parentId: walk source chain to find an included node
    let parentId: string | undefined
    let sourceId = node.source
    let sourceDepth = 0
    while (sourceDepth < 10) {
      if (includedIds.has(sourceId) || interventionSet.has(sourceId)) {
        parentId = sourceId
        break
      }
      const sourceEntry = causalPaths[sourceId]
      if (!sourceEntry || !sourceEntry.source || sourceEntry.hop === 0) break
      sourceId = sourceEntry.source
      sourceDepth++
    }

    const localNode = toLocalViewNode(
      rawNode, nodeById, domainColors, role,
      node.hop, node.beta, visualBeta, parentId
    )
    // Use hexagon for all sim effect nodes
    localNode.shape = 'hexagon'

    if (role === 'input') {
      inputs.push(localNode)
    } else {
      outputs.push(localNode)
    }

    // Create edge from parentId → this node
    if (parentId) {
      edges.push({
        source: parentId,
        target: node.id,
        beta: node.beta,
        sourceSector: getSectorForNode(parentId, nodeById),
        targetSector: getSectorForNode(node.id, nodeById)
      })
    }
  }

  const targetRing = targets[0] ? (nodeById.get(targets[0].id)?.layer ?? 5) : 5
  const hasAnyEdges = inputs.length > 0 || outputs.length > 0

  return {
    targets,
    inputs,
    outputs,
    edges,
    targetRing,
    mode: hasAnyEdges ? 'direct' : 'empty'
  }
}

/**
 * Get statistics for Local View data
 */
export function getLocalViewStats(data: ReturnType<typeof buildLocalViewData>): {
  totalInputs: number
  totalOutputs: number
  totalEdges: number
  avgBeta: number
  maxBeta: number
} {
  const betas = data.edges.map(e => Math.abs(e.beta))

  return {
    totalInputs: data.inputs.length,
    totalOutputs: data.outputs.length,
    totalEdges: data.edges.length,
    avgBeta: betas.length > 0 ? betas.reduce((a, b) => a + b, 0) / betas.length : 0,
    maxBeta: betas.length > 0 ? Math.max(...betas) : 0
  }
}
