/**
 * RadialLayout - Explicit Space Accounting Algorithm
 *
 * Two-pass algorithm with detailed logging:
 * 1. Bottom-up: Calculate minimum angular requirements from leaves upward
 * 2. Top-down: Allocate space from root downward, tracking compression
 *
 * Key improvement: Tracks allocated vs required space at every node
 * to diagnose where overlaps originate.
 *
 * Now uses viewport-aware scaling for all dimensions.
 */

import type { RawNodeV21 } from '../types'
import { debug } from '../utils/debug'
import type { NodeSizeRange } from './ViewportScales'
import { getRingCompactness, getTextBoostFactor } from './branchCurves'
import {
  computeOutcomeSectors,
  type OutcomeSectorSnapshot
} from './outcomeAngles'

export interface RingConfig {
  radius: number
  nodeSize: number
  label?: string
}

/**
 * Text orientation strategy for different rings/zoom levels
 */
export type TextOrientation = 'radial' | 'horizontal' | 'hidden'

/**
 * Text configuration for layout spacing calculations
 */
export interface TextConfig {
  /** Number of expanded Ring 1 branches (affects text boost) */
  expandedBranchCount: number
  /** Total number of Ring 1 outcomes currently visible */
  totalOutcomeCount: number
  /** Minimum readable font size (default 4px) */
  minReadableSize: number
  /** Maximum boosted font size (default 5px) */
  maxBoostedSize: number
  /** Base font size range from viewport */
  minFontSize: number
  maxFontSize: number
}

/**
 * Causal layout hints for simulation mode.
 * Pre-computed once when simulation results arrive (before playback starts).
 * Enables angular clustering of causally related nodes.
 */
export interface CausalLayoutHint {
  /** Ring 1 outcomes containing affected descendants → cluster at 0° */
  anchorOutcomes: Set<string>
  /** target node ID → source node ID (immediate causal parent) */
  causalAdjacency: Map<string, string>
  /** node ID → hop distance from intervention (0=intervention itself) */
  hopDistance: Map<string, number>
}

export interface LayoutConfig {
  rings: RingConfig[]
  nodePadding: number
  startAngle: number
  totalAngle: number
  minRingGap: number
  useFixedRadii?: boolean
  // Viewport-aware sizing parameters (optional for backward compatibility)
  sizeRange?: NodeSizeRange
  baseSpacing?: number
  spacingScaleFactor?: number
  maxSpacing?: number
  // Text-aware spacing (optional)
  textConfig?: TextConfig
  // Causal layout hints for simulation angular clustering (optional)
  causalHint?: CausalLayoutHint
  // Stable ring-1 angular snapshot (optional)
  prevOutcomeSectorSnapshot?: OutcomeSectorSnapshot
  // Max per-layout global rotation adjustment for outcome sectors (radians)
  maxOutcomeRotationStep?: number
}

export interface ComputedRingConfig {
  radius: number
  nodeSize: number
  label?: string
  nodeCount: number
  requiredRadius: number
}

export interface LayoutNode {
  id: string
  rawNode: RawNodeV21
  ring: number
  angle: number
  x: number
  y: number
  children: LayoutNode[]
  parent: LayoutNode | null
  subtreeLeafCount: number
  angularExtent: number
  minAngularExtent: number  // Minimum required (from bottom-up pass)
}

export interface LayoutResult {
  nodes: LayoutNode[]
  nodeMap: Map<string, LayoutNode>
  computedRings: ComputedRingConfig[]
  outcomeSectorSnapshot: OutcomeSectorSnapshot
}

/**
 * Space allocation tracking for debugging
 */
interface SpaceAllocation {
  nodeId: string
  nodeName: string
  ring: number
  required: number      // Minimum angular extent needed (radians)
  allocated: number     // Actual angular extent received (radians)
  compressionRatio: number  // allocated / required (1.0 = perfect, <1.0 = compressed)
  ownRequirement: number    // Just this node's size requirement
  childrenRequirement: number  // Sum of children's requirements
}

/**
 * DEFAULT node sizing constants (used when viewport-aware values not provided)
 * These are fallbacks for backward compatibility
 */
const DEFAULT_MIN_NODE_RADIUS = 0.5
const DEFAULT_MAX_NODE_RADIUS = 20
const DEFAULT_MIN_NODE_AREA = Math.PI * DEFAULT_MIN_NODE_RADIUS * DEFAULT_MIN_NODE_RADIUS
const DEFAULT_MAX_NODE_AREA = Math.PI * DEFAULT_MAX_NODE_RADIUS * DEFAULT_MAX_NODE_RADIUS

/**
 * Default size range for backward compatibility
 */
const DEFAULT_SIZE_RANGE: NodeSizeRange = {
  minRadius: DEFAULT_MIN_NODE_RADIUS,
  maxRadius: DEFAULT_MAX_NODE_RADIUS,
  minArea: DEFAULT_MIN_NODE_AREA,
  maxArea: DEFAULT_MAX_NODE_AREA,
  scaleFactor: DEFAULT_MAX_NODE_AREA - DEFAULT_MIN_NODE_AREA
}

// Module-level config holder for functions that don't receive config directly
let currentSizeRange: NodeSizeRange = DEFAULT_SIZE_RANGE
let currentBaseSpacing: number = 2
let currentSpacingScaleFactor: number = 0.3
let currentMaxSpacing: number = 7

// Module-level text config holder
let currentTextConfig: TextConfig | null = null

// Module-level causal hint holder (set per layout computation)
let currentCausalHint: CausalLayoutHint | null = null

// Module-level ring node counts for density-based text scaling
let ringNodeCounts: Map<number, number> = new Map()
let totalOutcomeCount = 0

/**
 * Update the current layout parameters (called from computeRadialLayout)
 */
function setLayoutParams(config: LayoutConfig): void {
  currentSizeRange = config.sizeRange ?? DEFAULT_SIZE_RANGE
  currentBaseSpacing = config.baseSpacing ?? 2
  currentSpacingScaleFactor = config.spacingScaleFactor ?? 0.3
  currentMaxSpacing = config.maxSpacing ?? 7
  currentTextConfig = config.textConfig ?? null
  currentCausalHint = config.causalHint ?? null
}

// ============================================================================
// TEXT-AWARE SPACING CALCULATIONS
// ============================================================================

/** Average character width as fraction of font size */
const AVG_CHAR_WIDTH_RATIO = 0.55

/**
 * Ring-based text multipliers (matches ViewportScales.ts)
 */
const RING_TEXT_MULTIPLIERS: Record<number, number> = {
  0: 1.0,    // Root - full size
  1: 1.0,    // Outcomes - full size
  2: 1.0,    // Coarse Domains - full size
  3: 0.85,   // Fine Domains - slightly reduced
  4: 0.70,   // Groups - reduced
  5: 0.35    // Indicators - significantly reduced
}

/**
 * Estimate text width without DOM measurement (fast heuristic)
 * 95% accurate, 100x faster than measureText()
 */
function estimateTextWidth(text: string, fontSize: number): number {
  if (!text) return 0

  const charCount = text.length
  // Account for wide/narrow characters
  const wideCharCount = (text.match(/[WMQ@%]/gi) || []).length
  const narrowCharCount = (text.match(/[iltj!|]/gi) || []).length

  const adjustedCount = charCount +
    wideCharCount * 0.3 -     // Wide chars add 30%
    narrowCharCount * 0.3     // Narrow chars subtract 30%

  return adjustedCount * fontSize * AVG_CHAR_WIDTH_RATIO
}

/**
 * Get text orientation strategy for a ring
 * Determines how text affects spacing calculations
 */
function getTextOrientation(ringIndex: number): TextOrientation {
  if (ringIndex <= 1) {
    return 'horizontal'  // Ring 0-1: text below node
  }
  // Ring 2-5: text extends outward (radial)
  // Ring 5 included so indicator labels can be visible during branch exploration
  return 'radial'
}

/**
 * Calculate font size for a node (with boost for branch exploration)
 * Mirrors the logic in App.tsx applyTextBoost
 */
function calculateFontSize(importance: number, ringIndex: number): number {
  if (!currentTextConfig) return 0

  const {
    minFontSize,
    maxFontSize,
    expandedBranchCount,
    totalOutcomeCount: textOutcomeCount,
    minReadableSize,
    maxBoostedSize
  } = currentTextConfig
  const range = maxFontSize - minFontSize

  // Base font size (same formula as ViewportScales)
  const baseFontSize = minFontSize + range * Math.sqrt(importance)
  const ringMultiplier = RING_TEXT_MULTIPLIERS[ringIndex] ?? 0.5
  const fontSize = baseFontSize * ringMultiplier * 0.9

  // Apply smooth boost for branch exploration.
  const boostFactor = getTextBoostFactor(expandedBranchCount, textOutcomeCount)

  if (boostFactor === 0 || fontSize >= minReadableSize) {
    return fontSize
  }

  // Map small text into boosted range
  const ratio = fontSize / minReadableSize
  const boostedSize = minReadableSize + ratio * (maxBoostedSize - minReadableSize)

  return fontSize + (boostedSize - fontSize) * boostFactor
}

/**
 * Get density-based text contribution factor for a ring.
 * Dense rings (many nodes) have reduced text contribution because:
 * 1. Text is too small to read at that density
 * 2. Nodes would overlap if full text space is allocated
 *
 * Thresholds tuned for actual node counts:
 * - Ring 2: 45 nodes → 100% text (under threshold)
 * - Ring 3: 196 nodes → ~40% text (moderate reduction)
 * - Ring 4: 569 nodes → 10% text (near max)
 * - Ring 5: 1763 nodes → 10% text (capped)
 */
function getDensityTextFactor(ringIndex: number): number {
  const nodeCount = ringNodeCounts.get(ringIndex) ?? 0

  // Thresholds calibrated for typical ring densities
  const densityThreshold = 50   // Full text below this
  const maxNodes = 400          // Minimal text above this

  if (nodeCount <= densityThreshold) return 1.0
  if (nodeCount >= maxNodes) return 0.1

  // Linear interpolation between thresholds
  return Math.max(0.1, 1.0 - (nodeCount - densityThreshold) / (maxNodes - densityThreshold) * 0.9)
}

/**
 * Calculate visual footprint (tangential extent) for a node
 * This is the arc length needed to avoid text overlap
 *
 * Now includes density-based text scaling to prevent excessive space
 * allocation in dense rings where text is too small to read anyway.
 *
 * @returns tangentialExtent in pixels (arc length along ring)
 */
function calculateVisualFootprint(
  nodeRadius: number,
  label: string,
  importance: number,
  ringIndex: number
): number {
  const textOrientation = getTextOrientation(ringIndex)
  const nodeDiameter = nodeRadius * 2

  // No text consideration for hidden orientation
  if (textOrientation === 'hidden' || !currentTextConfig) {
    return nodeDiameter
  }

  const fontSize = calculateFontSize(importance, ringIndex)
  const textWidth = estimateTextWidth(label, fontSize)

  // Cap text width to prevent extreme spacing for long labels
  const cappedTextWidth = Math.min(textWidth, 150)

  // Calculate boost factor for extra spacing during single-branch exploration
  // More boost = more spacing for readability
  const { expandedBranchCount, totalOutcomeCount: textOutcomeCount } = currentTextConfig
  const boostFactor = getTextBoostFactor(expandedBranchCount, textOutcomeCount)

  // Extra padding when exploring few branches (scales down as more branches expand)
  // Increased to 3x fontSize for better indicator label readability
  const explorationPadding = boostFactor * fontSize * 3

  // Density-based text scaling: reduce text footprint for dense rings
  const densityFactor = getDensityTextFactor(ringIndex)

  switch (textOrientation) {
    case 'horizontal': {
      // Text below node - needs max of node width or text width
      // Scale text contribution by density factor
      const scaledTextWidth = cappedTextWidth * densityFactor
      return Math.max(nodeDiameter, scaledTextWidth) + explorationPadding * densityFactor
    }

    case 'radial':
      // Text extends outward - add font height + exploration padding
      // Base: 1.8x fontSize for text thickness, scaled by density
      return nodeDiameter + fontSize * 1.8 * densityFactor + explorationPadding * densityFactor

    default:
      return nodeDiameter
  }
}

/**
 * Pure area-proportional sizing with visibility floor.
 * Node area is directly proportional to importance (statistical truth).
 * Floor ensures all nodes are visible/clickable.
 * @param _ring - Unused, kept for API compatibility
 * @param importance - Normalized importance (0-1)
 */
function getActualNodeSize(_ring: number, importance: number): number {
  const { minRadius, minArea, scaleFactor } = currentSizeRange
  const targetArea = minArea + importance * scaleFactor
  const targetRadius = Math.sqrt(targetArea / Math.PI)
  return Math.max(minRadius, targetRadius)
}

/**
 * Adaptive spacing based on node size.
 * Tiny nodes don't need large gaps.
 * Larger nodes need proportionally more spacing.
 *
 * Formula: spacing = baseSpacing + nodeRadius × scaleFactor
 * Uses viewport-aware values when provided via config.
 */
function getAdaptiveSpacing(nodeRadius: number, neighborRadius?: number): number {
  if (neighborRadius === undefined) {
    // Single node: use its own radius
    return Math.min(currentMaxSpacing, currentBaseSpacing + nodeRadius * currentSpacingScaleFactor)
  }

  // Two nodes: spacing based on average of their radii
  const avgRadius = (nodeRadius + neighborRadius) / 2
  return Math.min(currentMaxSpacing, currentBaseSpacing + avgRadius * currentSpacingScaleFactor)
}

/**
 * Internal tree node for building hierarchy
 */
interface TreeNode {
  id: string
  rawNode: RawNodeV21
  children: TreeNode[]
  parent: TreeNode | null
  subtreeLeafCount: number
  minAngularExtent: number      // Calculated in bottom-up pass
  ownAngularRequirement: number // Just this node's size
  childrenAngularRequirement: number // Sum of children
}

// ============================================================================
// SMART SECTOR FILLING - GROW FROM RIGHT
// Outcomes fill the arc starting from right (0°), spreading around the circle
// Natural spacing when sparse, compressed when dense
// ============================================================================

// Minimum extent for a collapsed outcome (just the node itself, minimal subtree)
// Larger = more space reserved for collapsed outcomes when siblings are expanded
const COLLAPSED_OUTCOME_MIN_EXTENT = Math.PI / 24  // ~7.5°

/**
 * Assign target angles for all outcomes with RIGHT SIDE PRIORITY.
 *
 * Strategy:
 * - Expanded outcomes are placed centered around 0° (right side) for readable text
 * - Collapsed outcomes fill the remaining space (top/bottom/left)
 * - Always fills full 360°
 *
 * @param allOutcomeIds - All outcome IDs in order
 * @param outcomeRequirements - Map of outcome ID to angular extent needed (from Pass 1)
 * @param expandedNodeIds - Set of expanded node IDs (for determining which outcomes need more space)
 * @returns Map of outcome ID to target center angle and extent
 */
function assignOutcomeAngles(
  allOutcomeIds: string[],
  outcomeRequirements: Map<string, number>,
  expandedNodeIds: Set<string>,
  prevOutcomeSectorSnapshot: OutcomeSectorSnapshot | undefined,
  maxOutcomeRotationStep: number
): { angles: Map<string, number>; extents: Map<string, number>; snapshot: OutcomeSectorSnapshot } {
  const anchorOutcomes = currentCausalHint?.anchorOutcomes
  const result = computeOutcomeSectors({
    outcomeIds: allOutcomeIds,
    outcomeRequirements,
    expandedNodeIds,
    anchorOutcomeIds: anchorOutcomes,
    minCollapsedExtent: COLLAPSED_OUTCOME_MIN_EXTENT,
    prevSnapshot: prevOutcomeSectorSnapshot,
    maxRotationStep: maxOutcomeRotationStep,
    targetBiasAngle: 0,
  })

  const clusteredSet = new Set(result.snapshot.clusteredOutcomeIds)
  debug.sector('[SECTOR FILLING] STABLE RIGHT-BIASED:')
  debug.sector(`  Outcomes: ${allOutcomeIds.length}, clustered: ${clusteredSet.size}, rotation: ${toDeg(result.snapshot.rotation)}`)

  for (const id of result.snapshot.order) {
    const angle = result.angles.get(id)
    const extent = result.extents.get(id)
    if (angle === undefined || extent === undefined) continue
    const status = clusteredSet.has(id) ? 'CLUSTER' : 'stable'
    debug.sector(`  [${status}] ${id}: ${toDeg(angle)} (extent: ${toDeg(extent)})`)
  }

  return {
    angles: result.angles,
    extents: result.extents,
    snapshot: result.snapshot
  }
}

/**
 * Convert radians to degrees for logging
 */
function toDeg(radians: number): string {
  return (radians * 180 / Math.PI).toFixed(1) + '°'
}

// Global space allocation tracker for debugging
const spaceAllocations = new Map<string, SpaceAllocation>()

// Track expanded outcomes for compactness calculation
let expandedOutcomeCount = 0

/**
 * Unified compactness formula for Ring 1 positioning AND Ring 2 spread.
 *
 * By using the same compactness for both:
 * - Ring 1 outcomes are positioned such that their Ring 2 children's extents meet
 * - Inter-branch Ring 2 spacing equals intra-branch Ring 2 spacing
 * - No hard threshold jumps when branch count changes
 */
function getUnifiedCompactness(expandedCount: number): number {
  return getRingCompactness(expandedCount, totalOutcomeCount, 0.4)
}

// ============================================================================
// CAUSAL CHAIN SORTING
// Sort siblings so causally connected nodes are adjacent within their sector.
// Affected nodes cluster at sector center, structural nodes at edges.
// ============================================================================

/**
 * Sort children of a parent node for causal clustering.
 *
 * Algorithm:
 * 1. Partition into affected (in hopDistance) vs structural
 * 2. Group affected into causal chains (siblings sharing a chain via causalAdjacency)
 * 3. Sort chains by min hop (closest to intervention → sector center)
 * 4. Within each chain, sort by hop ascending
 * 5. Final: [...structural_left, ...chains, ...structural_right]
 *
 * Cross-sector facing tiebreaker: between chains at same hop level,
 * bias toward the side facing the source's angle (if source is in a different sector).
 *
 * @param children The sibling TreeNodes to sort
 * @param parentAngle The parent's center angle (for cross-sector facing)
 * @param nodeMap Layout node map (for source angle lookup in cross-sector heuristic)
 */
function sortChildrenByCausalChain(
  children: TreeNode[],
  parentAngle: number,
  nodeMap: Map<string, LayoutNode>
): TreeNode[] {
  if (!currentCausalHint || children.length <= 1) return children

  const { causalAdjacency, hopDistance } = currentCausalHint

  // Partition into affected and structural
  const affected: TreeNode[] = []
  const structural: TreeNode[] = []
  for (const child of children) {
    if (hopDistance.has(child.id)) {
      affected.push(child)
    } else {
      structural.push(child)
    }
  }

  // If no affected children, preserve original order
  if (affected.length === 0) return children

  // Group affected into causal chains.
  // Two siblings are in the same chain if one is the causal source of the other,
  // or they share a common chain ancestor among these siblings.
  // Simplified: group by "which chain does this node belong to" —
  // walk causalAdjacency until we find a sibling or run out.
  const siblingSet = new Set(affected.map(c => c.id))
  const chainMap = new Map<string, string>() // nodeId → chain root among siblings

  for (const node of affected) {
    // Walk the causal source chain to find the earliest sibling in the chain
    let chainRoot = node.id
    const visited = new Set<string>()
    let cur = node.id
    while (cur) {
      visited.add(cur)
      const source = causalAdjacency.get(cur)
      if (!source || visited.has(source)) break
      if (siblingSet.has(source)) {
        chainRoot = source // found a sibling that's upstream — it's the chain root
      }
      cur = source
    }
    chainMap.set(node.id, chainRoot)
  }

  // Group by chain root
  const chains = new Map<string, TreeNode[]>()
  for (const node of affected) {
    const root = chainMap.get(node.id)!
    if (!chains.has(root)) chains.set(root, [])
    chains.get(root)!.push(node)
  }

  // Sort within each chain by hop ascending
  for (const [, chain] of chains) {
    chain.sort((a, b) => (hopDistance.get(a.id) ?? 99) - (hopDistance.get(b.id) ?? 99))
  }

  // Sort chains by minimum hop (closest to intervention first → placed at center)
  const sortedChains = Array.from(chains.values()).sort((a, b) => {
    const minHopA = Math.min(...a.map(n => hopDistance.get(n.id) ?? 99))
    const minHopB = Math.min(...b.map(n => hopDistance.get(n.id) ?? 99))
    if (minHopA !== minHopB) return minHopA - minHopB

    // Cross-sector facing tiebreaker: chain whose source angle is more clockwise
    // relative to parent should be placed more clockwise (higher angle)
    const sourceA = causalAdjacency.get(a[0].id)
    const sourceB = causalAdjacency.get(b[0].id)
    const angleA = sourceA ? (nodeMap.get(sourceA)?.angle ?? parentAngle) : parentAngle
    const angleB = sourceB ? (nodeMap.get(sourceB)?.angle ?? parentAngle) : parentAngle
    // Normalize angular difference relative to parent
    const diffA = ((angleA - parentAngle) + Math.PI * 3) % (Math.PI * 2) - Math.PI
    const diffB = ((angleB - parentAngle) + Math.PI * 3) % (Math.PI * 2) - Math.PI
    return diffA - diffB
  })

  // Flatten chains
  const flatAffected = sortedChains.flat()

  // Split structural: half before affected, half after
  const halfStruct = Math.floor(structural.length / 2)
  const structLeft = structural.slice(0, halfStruct)
  const structRight = structural.slice(halfStruct)

  return [...structLeft, ...flatAffected, ...structRight]
}

/**
 * Compute subtree leaf count
 */
function computeSubtreeLeafCount(node: TreeNode): number {
  if (node.children.length === 0) {
    node.subtreeLeafCount = 1
    return 1
  }
  let total = 0
  for (const child of node.children) {
    total += computeSubtreeLeafCount(child)
  }
  node.subtreeLeafCount = total
  return total
}

/**
 * PASS 1: Bottom-up calculation of minimum angular requirements.
 *
 * Each node's minAngularExtent = MAX of:
 * 1. Its own size requirement at its ring
 * 2. Sum of all children's minAngularExtent (they need this space at next ring)
 *
 * This ensures parents "reserve" enough angular space for all descendants.
 */
function calculateMinimumRequirements(
  node: TreeNode,
  ringIndex: number,
  ringRadii: number[],
  _nodePadding: number,  // Unused - now using adaptive spacing
  verbose: boolean = false
): number {
  const radius = ringRadii[ringIndex] || ringRadii[ringRadii.length - 1]

  // Calculate own size requirement at this ring with adaptive spacing
  const nodeSize = getActualNodeSize(ringIndex, node.rawNode.importance ?? 0)
  const importance = node.rawNode.importance ?? 0
  const label = node.rawNode.label || ''

  // Calculate visual footprint (includes text if textConfig is set)
  const visualFootprint = calculateVisualFootprint(nodeSize, label, importance, ringIndex)

  // Spacing based on node size (not text - text footprint handles overlap)
  const spacing = getAdaptiveSpacing(nodeSize)

  // Convert visual footprint to angular width (arc length / radius)
  // For footprint larger than node diameter, use arc length formula
  const footprintAngular = radius > 0 ? visualFootprint / radius : Math.PI * 2
  const spacingAngular = radius > 0 ? spacing / radius : 0
  const ownMinAngle = footprintAngular + spacingAngular

  node.ownAngularRequirement = ownMinAngle

  if (node.children.length === 0) {
    // Leaf node: just needs space for itself
    node.minAngularExtent = ownMinAngle
    node.childrenAngularRequirement = 0

    // Track allocation (allocated will be set in Pass 2)
    spaceAllocations.set(node.id, {
      nodeId: node.id,
      nodeName: node.rawNode.label || node.id,
      ring: ringIndex,
      required: ownMinAngle,
      allocated: 0,
      compressionRatio: 0,
      ownRequirement: ownMinAngle,
      childrenRequirement: 0
    })

    return ownMinAngle
  }

  // Parent node: Calculate children's space needs with pairwise spacing
  const childRingIndex = ringIndex + 1
  const childRingRadius = ringRadii[childRingIndex] || ringRadii[ringRadii.length - 1]

  // Get children's visual footprints for spacing calculation
  const childFootprints = node.children.map(child => {
    const childNodeSize = getActualNodeSize(childRingIndex, child.rawNode.importance ?? 0)
    const childImportance = child.rawNode.importance ?? 0
    const childLabel = child.rawNode.label || ''
    return {
      nodeSize: childNodeSize,
      footprint: calculateVisualFootprint(childNodeSize, childLabel, childImportance, childRingIndex)
    }
  })

  // Calculate total angular extent needed: sum of visual footprints + spacing
  // Uses visual footprint (node + text) for angular width calculation
  let totalChildRequirement = 0
  for (let i = 0; i < node.children.length; i++) {
    const { nodeSize, footprint } = childFootprints[i]
    // Angular width based on visual footprint (includes text)
    const footprintAngular = childRingRadius > 0 ? footprint / childRingRadius : 0
    totalChildRequirement += footprintAngular

    if (i < node.children.length - 1) {
      // Spacing between this child and next (based on node size, not text)
      const nextNodeSize = childFootprints[i + 1].nodeSize
      const spacing = getAdaptiveSpacing(nodeSize, nextNodeSize)
      totalChildRequirement += childRingRadius > 0 ? spacing / childRingRadius : 0
    }
  }

  // Still need to recurse to set children's own requirements
  for (const child of node.children) {
    calculateMinimumRequirements(
      child,
      childRingIndex,
      ringRadii,
      _nodePadding,
      verbose
    )
  }

  node.childrenAngularRequirement = totalChildRequirement

  // Node's requirement = MAX of own need OR children's total need
  // Children's need is the constraint that propagates upward
  node.minAngularExtent = Math.max(ownMinAngle, totalChildRequirement)

  // Track allocation
  spaceAllocations.set(node.id, {
    nodeId: node.id,
    nodeName: node.rawNode.label || node.id,
    ring: ringIndex,
    required: node.minAngularExtent,
    allocated: 0,
    compressionRatio: 0,
    ownRequirement: ownMinAngle,
    childrenRequirement: totalChildRequirement
  })

  if (verbose && node.children.length > 0) {
    debug.layout(
      `[PASS 1] ${node.id} (ring ${ringIndex}): ` +
      `requires ${toDeg(node.minAngularExtent)} ` +
      `(own: ${toDeg(ownMinAngle)}, children: ${toDeg(totalChildRequirement)})`
    )
  }

  return node.minAngularExtent
}

/**
 * PASS 2: Top-down positioning with knowledge of minimum requirements.
 * Now with explicit space tracking and compression logging.
 */
function positionNode(
  treeNode: TreeNode,
  startAngle: number,
  angularExtent: number,
  ringIndex: number,
  ringRadii: number[],
  nodePadding: number,
  nodeMap: Map<string, LayoutNode>,
  parentLayoutNode: LayoutNode | null,
  verbose: boolean = false
): LayoutNode {
  const radius = ringRadii[ringIndex] || 0
  const midAngle = startAngle + angularExtent / 2

  // Root node (ring 0, radius 0) stays at center
  const x = radius === 0 ? 0 : radius * Math.cos(midAngle)
  const y = radius === 0 ? 0 : radius * Math.sin(midAngle)

  const layoutNode: LayoutNode = {
    id: treeNode.id,
    rawNode: treeNode.rawNode,
    ring: ringIndex,
    angle: midAngle,
    x,
    y,
    children: [],
    parent: parentLayoutNode,
    subtreeLeafCount: treeNode.subtreeLeafCount,
    angularExtent,
    minAngularExtent: treeNode.minAngularExtent
  }

  nodeMap.set(treeNode.id, layoutNode)

  // Update allocation tracking
  const allocation = spaceAllocations.get(treeNode.id)
  if (allocation) {
    allocation.allocated = angularExtent
    allocation.compressionRatio = angularExtent / allocation.required

    // Log compression warnings
    if (allocation.compressionRatio < 0.95 && verbose) {
      debug.layoutWarn(
        `[COMPRESSION] ${treeNode.id} (${allocation.nodeName}): ` +
        `required ${toDeg(allocation.required)}, ` +
        `allocated ${toDeg(angularExtent)} ` +
        `(${(allocation.compressionRatio * 100).toFixed(1)}%)`
      )
    }
  }

  if (treeNode.children.length === 0) return layoutNode

  // Position children using their pre-calculated minimum requirements
  const childRingIndex = ringIndex + 1
  if (childRingIndex >= ringRadii.length) return layoutNode

  // Apply causal chain sorting if hints are available
  const sortedChildren = sortChildrenByCausalChain(treeNode.children, midAngle, nodeMap)
  // Get children's minimum requirements (from Pass 1)
  const childMinimums = sortedChildren.map(c => c.minAngularExtent)
  const totalMinimum = childMinimums.reduce((a, b) => a + b, 0)
  const excessSpace = angularExtent - totalMinimum

  if (verbose && sortedChildren.length > 1) {
    debug.layout(
      `[PASS 2] Distributing space in ${treeNode.id}: ` +
      `parent has ${toDeg(angularExtent)}, ` +
      `children need ${toDeg(totalMinimum)}, ` +
      `excess: ${toDeg(excessSpace)}`
    )
  }

  // Allocate angular extents to children
  let childExtents: number[]

  if (totalMinimum <= angularExtent) {
    // CASE A: Excess space - distribute proportionally to requirement
    // Each child gets its minimum + proportional share of excess
    childExtents = childMinimums.map(min => {
      const proportion = min / totalMinimum
      const extraShare = proportion * excessSpace
      return min + extraShare
    })
  } else {
    // CASE B: Overcrowded - compress proportionally
    const compressionRatio = angularExtent / totalMinimum
    childExtents = childMinimums.map(min => min * compressionRatio)

    debug.layoutWarn(
      `[OVERCROWDING] ${treeNode.id} (ring ${ringIndex}): ` +
      `${sortedChildren.length} children need ${toDeg(totalMinimum)} ` +
      `but only have ${toDeg(angularExtent)} ` +
      `(compression: ${(compressionRatio * 100).toFixed(1)}%)`
    )
  }

  // Center children around parent's midpoint
  const totalChildExtent = childExtents.reduce((a, b) => a + b, 0)
  let currentAngle = midAngle - totalChildExtent / 2

  // Recursively position each child
  for (let i = 0; i < sortedChildren.length; i++) {
    const child = sortedChildren[i]
    const childExtent = childExtents[i]

    const childLayoutNode = positionNode(
      child,
      currentAngle,
      childExtent,
      childRingIndex,
      ringRadii,
      nodePadding,
      nodeMap,
      layoutNode,
      verbose
    )

    layoutNode.children.push(childLayoutNode)
    currentAngle += childExtent
  }

  return layoutNode
}

/**
 * PASS 2 with sector awareness: Position nodes using target angles for outcomes.
 *
 * For Ring 1 outcomes: Uses pre-assigned target angles from sector assignment
 * For other nodes: Standard proportional space allocation
 */
function positionNodeWithSectorAwareness(
  treeNode: TreeNode,
  startAngle: number,
  angularExtent: number,
  ringIndex: number,
  ringRadii: number[],
  nodePadding: number,
  nodeMap: Map<string, LayoutNode>,
  parentLayoutNode: LayoutNode | null,
  outcomeTargetAngles: Map<string, number>,
  outcomeExtents: Map<string, number>,  // Computed extents with natural spacing
  verbose: boolean = false
): LayoutNode {
  const radius = ringRadii[ringIndex] || 0
  const midAngle = startAngle + angularExtent / 2

  // Root node (ring 0, radius 0) stays at center
  const x = radius === 0 ? 0 : radius * Math.cos(midAngle)
  const y = radius === 0 ? 0 : radius * Math.sin(midAngle)

  const layoutNode: LayoutNode = {
    id: treeNode.id,
    rawNode: treeNode.rawNode,
    ring: ringIndex,
    angle: midAngle,
    x,
    y,
    children: [],
    parent: parentLayoutNode,
    subtreeLeafCount: treeNode.subtreeLeafCount,
    angularExtent,
    minAngularExtent: treeNode.minAngularExtent
  }

  nodeMap.set(treeNode.id, layoutNode)

  // Update allocation tracking
  const allocation = spaceAllocations.get(treeNode.id)
  if (allocation) {
    allocation.allocated = angularExtent
    allocation.compressionRatio = angularExtent / allocation.required
  }

  if (treeNode.children.length === 0) return layoutNode

  // Position children
  const childRingIndex = ringIndex + 1
  if (childRingIndex >= ringRadii.length) return layoutNode

  // SPECIAL CASE: Ring 0 (root) positioning Ring 1 (outcomes) with sector assignment
  if (ringIndex === 0 && outcomeTargetAngles.size > 0) {
    // Use target angles for outcomes
    for (const child of treeNode.children) {
      const targetAngle = outcomeTargetAngles.get(child.id)
      const childExtent = outcomeExtents.get(child.id) ?? child.minAngularExtent

      if (targetAngle !== undefined) {
        // Position outcome at its assigned target angle
        const childRadius = ringRadii[childRingIndex] || 0
        const childX = childRadius * Math.cos(targetAngle)
        const childY = childRadius * Math.sin(targetAngle)

        const childLayoutNode: LayoutNode = {
          id: child.id,
          rawNode: child.rawNode,
          ring: childRingIndex,
          angle: targetAngle,
          x: childX,
          y: childY,
          children: [],
          parent: layoutNode,
          subtreeLeafCount: child.subtreeLeafCount,
          angularExtent: childExtent,
          minAngularExtent: child.minAngularExtent
        }

        nodeMap.set(child.id, childLayoutNode)

        // Update allocation tracking for outcome
        const childAllocation = spaceAllocations.get(child.id)
        if (childAllocation) {
          childAllocation.allocated = childExtent
          childAllocation.compressionRatio = childExtent / childAllocation.required
        }

        // Recursively position outcome's children using standard algorithm
        if (child.children.length > 0) {
          const grandchildRingIndex = childRingIndex + 1
          if (grandchildRingIndex < ringRadii.length) {
            // Use UNIFIED compactness for Ring 2 spread
            // This matches Ring 1 positioning so inter-branch spacing equals intra-branch spacing
            const ring2Compactness = grandchildRingIndex === 2
              ? getUnifiedCompactness(expandedOutcomeCount)
              : 1.0

            positionChildrenStandard(
              child,
              childLayoutNode,
              targetAngle,
              childExtent,
              grandchildRingIndex,
              ringRadii,
              nodePadding,
              nodeMap,
              verbose,
              ring2Compactness
            )
          }
        }

        layoutNode.children.push(childLayoutNode)

        if (verbose) {
          debug.sector(
            `[SECTOR] Positioned outcome ${child.id} at ${toDeg(targetAngle)} ` +
            `with extent ${toDeg(childExtent)}`
          )
        }
      }
    }

    return layoutNode
  }

  // STANDARD CASE: Normal proportional distribution for non-root nodes
  // Apply causal chain sorting if hints are available — reorder children so
  // causally connected nodes are adjacent, affected nodes at sector center.
  const sortedChildren = sortChildrenByCausalChain(treeNode.children, midAngle, nodeMap)
  const childMinimums = sortedChildren.map(c => c.minAngularExtent)
  const totalMinimum = childMinimums.reduce((a, b) => a + b, 0)
  const excessSpace = angularExtent - totalMinimum

  let childExtents: number[]

  if (totalMinimum <= angularExtent) {
    childExtents = childMinimums.map(min => {
      const proportion = totalMinimum > 0 ? min / totalMinimum : 1 / childMinimums.length
      const extraShare = proportion * excessSpace
      return min + extraShare
    })
  } else {
    const compressionRatio = angularExtent / totalMinimum
    childExtents = childMinimums.map(min => min * compressionRatio)
  }

  const totalChildExtent = childExtents.reduce((a, b) => a + b, 0)
  let currentAngle = midAngle - totalChildExtent / 2

  for (let i = 0; i < sortedChildren.length; i++) {
    const child = sortedChildren[i]
    const childExtent = childExtents[i]

    const childLayoutNode = positionNodeWithSectorAwareness(
      child,
      currentAngle,
      childExtent,
      childRingIndex,
      ringRadii,
      nodePadding,
      nodeMap,
      layoutNode,
      outcomeTargetAngles,
      outcomeExtents,
      verbose
    )

    layoutNode.children.push(childLayoutNode)
    currentAngle += childExtent
  }

  return layoutNode
}

/**
 * Helper: Position children using standard proportional algorithm.
 * Used after sector-assigned outcomes to position their descendants.
 *
 * compactness: 0-1 value that reduces spread (1 = full spread, 0.5 = half spread)
 * Used for Ring 2 when few outcomes are expanded, to keep nodes bundled.
 */
function positionChildrenStandard(
  parentTreeNode: TreeNode,
  parentLayoutNode: LayoutNode,
  parentAngle: number,
  parentExtent: number,
  childRingIndex: number,
  ringRadii: number[],
  nodePadding: number,
  nodeMap: Map<string, LayoutNode>,
  verbose: boolean,
  compactness: number = 1.0  // 1.0 = full spread, 0.5 = half spread
): void {
  // Apply causal chain sorting if hints are available
  const sortedChildren = sortChildrenByCausalChain(parentTreeNode.children, parentAngle, nodeMap)
  const childMinimums = sortedChildren.map(c => c.minAngularExtent)
  const totalMinimum = childMinimums.reduce((a, b) => a + b, 0)

  // Apply compactness to get the effective extent for positioning
  // IMPORTANT: Never exceed parentExtent to prevent spillover into adjacent domains
  const compactedExtent = parentExtent * compactness
  const effectiveExtent = Math.min(Math.max(totalMinimum, compactedExtent), parentExtent)

  let childExtents: number[]

  if (totalMinimum <= effectiveExtent) {
    // Enough space - distribute proportionally with excess
    const excessSpace = effectiveExtent - totalMinimum
    childExtents = childMinimums.map(min => {
      const proportion = totalMinimum > 0 ? min / totalMinimum : 1 / childMinimums.length
      const extraShare = proportion * excessSpace
      return min + extraShare
    })
  } else {
    // Not enough space - compress to fit within parent's boundary
    const compressionRatio = effectiveExtent / totalMinimum
    childExtents = childMinimums.map(min => min * compressionRatio)
  }

  const totalChildExtent = childExtents.reduce((a, b) => a + b, 0)
  let currentAngle = parentAngle - totalChildExtent / 2

  for (let i = 0; i < sortedChildren.length; i++) {
    const child = sortedChildren[i]
    const childExtent = childExtents[i]

    const childLayoutNode = positionNode(
      child,
      currentAngle,
      childExtent,
      childRingIndex,
      ringRadii,
      nodePadding,
      nodeMap,
      parentLayoutNode,
      verbose
    )

    parentLayoutNode.children.push(childLayoutNode)
    currentAngle += childExtent
  }
}

/**
 * Compute ring configuration with node counts
 */
function computeRingConfigs(
  nodes: RawNodeV21[],
  config: LayoutConfig
): ComputedRingConfig[] {
  const nodeCountByLayer = new Map<number, number>()
  for (const node of nodes) {
    nodeCountByLayer.set(node.layer, (nodeCountByLayer.get(node.layer) || 0) + 1)
  }

  return config.rings.map((ringConfig, layer) => {
    const nodeCount = nodeCountByLayer.get(layer) || 0
    // Use global average node size for spacing calculations (from current config)
    const avgNodeSize = (currentSizeRange.minRadius + currentSizeRange.maxRadius) / 2
    const minSpacing = avgNodeSize * 2 + config.nodePadding
    const requiredCircumference = nodeCount * minSpacing
    const requiredRadius = requiredCircumference / (2 * Math.PI)

    return {
      radius: ringConfig.radius,
      nodeSize: ringConfig.nodeSize,
      label: ringConfig.label,
      nodeCount,
      requiredRadius
    }
  })
}

/**
 * Print space allocation summary for debugging
 */
function printAllocationSummary(): void {
  const allocations = Array.from(spaceAllocations.values())

  // Group by compression status
  const compressed = allocations.filter(a => a.compressionRatio < 0.95 && a.compressionRatio > 0)
  const adequate = allocations.filter(a => a.compressionRatio >= 0.95)

  debug.space('\n=== Space Allocation Summary ===')
  debug.space(`Total nodes: ${allocations.length}`)
  debug.space(`Adequate space: ${adequate.length} (${(adequate.length / allocations.length * 100).toFixed(1)}%)`)
  debug.space(`Compressed: ${compressed.length} (${(compressed.length / allocations.length * 100).toFixed(1)}%)`)

  if (compressed.length > 0) {
    debug.space('\nMost compressed nodes (top 20):')
    compressed
      .sort((a, b) => a.compressionRatio - b.compressionRatio)
      .slice(0, 20)
      .forEach(allocation => {
        debug.space(
          `  Ring ${allocation.ring}: ${allocation.nodeId} (${allocation.nodeName.substring(0, 30)}): ` +
          `${(allocation.compressionRatio * 100).toFixed(1)}% ` +
          `(needed ${toDeg(allocation.required)}, got ${toDeg(allocation.allocated)})`
        )
      })

    // Group compressions by ring
    debug.space('\nCompressions by ring:')
    const byRing = new Map<number, number>()
    compressed.forEach(a => {
      byRing.set(a.ring, (byRing.get(a.ring) || 0) + 1)
    })
    Array.from(byRing.entries())
      .sort((a, b) => a[0] - b[0])
      .forEach(([ring, count]) => {
        debug.space(`  Ring ${ring}: ${count} compressed nodes`)
      })
  }
}

/**
 * Main layout function - Two-pass hybrid algorithm with explicit space tracking
 *
 * Pass 1 (Bottom-up): Calculate minimum angular requirements from leaves upward
 * Pass 2 (Top-down): Allocate space from root downward, tracking compression
 *
 * Smart Lateral-First Sector Filling:
 * When expandedNodeIds is provided, expanded Ring 1 outcomes are positioned
 * in lateral bands (right, left) for readable text labels, with collapsed
 * outcomes filling the remaining space.
 */
export function computeRadialLayout(
  nodes: RawNodeV21[],
  config: LayoutConfig,
  expandedNodeIds: Set<string> = new Set(),  // NEW: Track which nodes are expanded
  verbose: boolean = false  // Disabled verbose logging
): LayoutResult {
  // Initialize viewport-aware parameters
  setLayoutParams(config)

  // Clear previous allocations
  spaceAllocations.clear()

  // Count nodes per ring for density-based text scaling
  ringNodeCounts = new Map()
  for (const node of nodes) {
    const layer = node.layer ?? 0
    ringNodeCounts.set(layer, (ringNodeCounts.get(layer) ?? 0) + 1)
  }

  // Count expanded outcomes (Ring 1 nodes) for Ring 2 compactness
  const outcomeNodeIds = nodes.filter(n => n.layer === 1).map(n => String(n.id))
  totalOutcomeCount = outcomeNodeIds.length
  expandedOutcomeCount = outcomeNodeIds.filter(id => expandedNodeIds.has(id)).length

  const computedRings = computeRingConfigs(nodes, config)
  const ringRadii = computedRings.map(r => r.radius)

  // Build tree structure
  const treeNodeMap = new Map<string, TreeNode>()

  for (const node of nodes) {
    treeNodeMap.set(String(node.id), {
      id: String(node.id),
      rawNode: node,
      children: [],
      parent: null,
      subtreeLeafCount: 0,
      minAngularExtent: 0,
      ownAngularRequirement: 0,
      childrenAngularRequirement: 0
    })
  }

  // Build parent-child relationships
  const roots: TreeNode[] = []
  for (const node of nodes) {
    const treeNode = treeNodeMap.get(String(node.id))!
    if (node.parent !== undefined) {
      const parentNode = treeNodeMap.get(String(node.parent))
      if (parentNode) {
        parentNode.children.push(treeNode)
        treeNode.parent = parentNode
      }
    } else {
      roots.push(treeNode)
    }
  }

  // Compute subtree leaf counts
  for (const root of roots) {
    computeSubtreeLeafCount(root)
  }

  // PASS 1: Bottom-up calculation of minimum requirements
  if (verbose) debug.layout('\n=== PASS 1: Calculating minimum angular requirements ===')
  for (const root of roots) {
    calculateMinimumRequirements(root, 0, ringRadii, config.nodePadding, verbose)
  }

  // Log total requirement vs available
  const totalRootRequirement = roots.reduce((sum, r) => sum + r.minAngularExtent, 0)
  if (verbose) {
    debug.layout(
      `\nTotal minimum requirement: ${toDeg(totalRootRequirement)} ` +
      `(available: ${toDeg(config.totalAngle)})`
    )
    if (totalRootRequirement > config.totalAngle) {
      debug.layoutWarn(
        `[WARNING] Total requirement exceeds available space by ${toDeg(totalRootRequirement - config.totalAngle)}!`
      )
    }
  }

  // ========================================================================
  // SMART SECTOR FILLING - GROW FROM RIGHT
  // All outcomes positioned starting from right (0°), spreading around circle
  // Natural spacing when sparse, compressed when dense
  // ========================================================================

  // Extract Ring 1 outcomes (children of root)
  const outcomeNodes: TreeNode[] = []
  for (const root of roots) {
    for (const child of root.children) {
      if (child.rawNode.layer === 1) {
        outcomeNodes.push(child)
      }
    }
  }

  // Extract angular requirements from Pass 1 results
  const outcomeRequirements = new Map<string, number>()
  for (const outcome of outcomeNodes) {
    outcomeRequirements.set(outcome.id, outcome.minAngularExtent)
  }

  // Assign target angles and extents for ALL outcomes (grow from right)
  const {
    angles: outcomeTargetAngles,
    extents: outcomeTargetExtents,
    snapshot: outcomeSectorSnapshot
  } = assignOutcomeAngles(
    outcomeNodes.map(n => n.id),
    outcomeRequirements,
    expandedNodeIds,
    config.prevOutcomeSectorSnapshot,
    config.maxOutcomeRotationStep ?? 0
  )

  // ========================================================================
  // PASS 2: Top-down positioning (with sector-aware outcome placement)
  // ========================================================================

  if (verbose) debug.layout('\n=== PASS 2: Allocating space (top-down) ===')
  const layoutNodeMap = new Map<string, LayoutNode>()
  const layoutNodes: LayoutNode[] = []

  const collectNodes = (node: LayoutNode) => {
    layoutNodes.push(node)
    for (const child of node.children) {
      collectNodes(child)
    }
  }

  if (roots.length === 1) {
    const root = roots[0]
    const rootLayoutNode = positionNodeWithSectorAwareness(
      root,
      config.startAngle,
      config.totalAngle,
      0,
      ringRadii,
      config.nodePadding,
      layoutNodeMap,
      null,
      outcomeTargetAngles,
      outcomeTargetExtents,  // Use computed extents (includes natural spacing)
      verbose
    )
    collectNodes(rootLayoutNode)
  } else {
    // Multiple roots: distribute based on their minimum requirements
    const totalRequirement = roots.reduce((sum, r) => sum + r.minAngularExtent, 0)
    let currentAngle = config.startAngle

    for (const root of roots) {
      // Allocate proportional to requirement (not just leaf count)
      const proportion = root.minAngularExtent / totalRequirement
      const extent = config.totalAngle * proportion

      const rootLayoutNode = positionNodeWithSectorAwareness(
        root,
        currentAngle,
        extent,
        0,
        ringRadii,
        config.nodePadding,
        layoutNodeMap,
        null,
        outcomeTargetAngles,
        outcomeTargetExtents,  // Use computed extents (includes natural spacing)
        verbose
      )
      collectNodes(rootLayoutNode)

      currentAngle += extent
    }
  }

  // Print allocation summary
  if (verbose) {
    printAllocationSummary()
  }

  return {
    nodes: layoutNodes,
    nodeMap: layoutNodeMap,
    computedRings,
    outcomeSectorSnapshot
  }
}

/**
 * Optional post-processing: Resolve any remaining overlaps
 *
 * This checks ALL pairs within an angular window (not just adjacent pairs)
 * to catch overlaps between siblings or nearby nodes of different sizes.
 */
export function resolveOverlaps(
  layoutNodes: LayoutNode[],
  computedRings: ComputedRingConfig[],
  _nodePadding: number,  // Unused - now using adaptive spacing
  maxIterations: number = 50
): void {
  const nodesByRing = new Map<number, LayoutNode[]>()
  for (const node of layoutNodes) {
    if (!nodesByRing.has(node.ring)) {
      nodesByRing.set(node.ring, [])
    }
    nodesByRing.get(node.ring)!.push(node)
  }

  for (const [ring, ringNodes] of nodesByRing) {
    if (ringNodes.length <= 1) continue

    const ringConfig = computedRings[ring]
    if (!ringConfig || ringConfig.radius === 0) continue

    const radius = ringConfig.radius

    // Angular window for checking nearby nodes (must match detectOverlaps)
    const maxAngularWindow = (currentSizeRange.maxRadius * 4) / radius

    for (let iter = 0; iter < maxIterations; iter++) {
      let hadOverlap = false

      ringNodes.sort((a, b) => a.angle - b.angle)

      // Check all pairs within angular window (not just adjacent)
      for (let i = 0; i < ringNodes.length; i++) {
        const n1 = ringNodes[i]
        const size1 = getActualNodeSize(n1.ring, n1.rawNode.importance ?? 0)

        // Check forward within window
        for (let j = i + 1; j < ringNodes.length; j++) {
          const n2 = ringNodes[j]

          // Calculate angular difference
          let angleDiff = n2.angle - n1.angle
          if (angleDiff > Math.PI) angleDiff = 2 * Math.PI - angleDiff

          // Stop if past window (nodes are sorted)
          if (angleDiff > maxAngularWindow) break

          const size2 = getActualNodeSize(n2.ring, n2.rawNode.importance ?? 0)
          const spacing = getAdaptiveSpacing(size1, size2)
          const minDist = size1 + size2 + spacing

          const dx = n2.x - n1.x
          const dy = n2.y - n1.y
          const dist = Math.sqrt(dx * dx + dy * dy)

          if (dist < minDist && dist > 0) {
            hadOverlap = true

            const overlap = minDist - dist
            const pushAngle = overlap / (2 * radius)

            n1.angle -= pushAngle / 2
            n2.angle += pushAngle / 2

            n1.x = radius * Math.cos(n1.angle)
            n1.y = radius * Math.sin(n1.angle)
            n2.x = radius * Math.cos(n2.angle)
            n2.y = radius * Math.sin(n2.angle)
          }
        }

        // Check wrap-around for nodes near the start
        if (i < 10) {
          for (let j = ringNodes.length - 1; j >= ringNodes.length - 10 && j > i; j--) {
            const n2 = ringNodes[j]

            // Angular diff with wrap-around
            let angleDiff = (2 * Math.PI) - (n2.angle - n1.angle)
            if (angleDiff > Math.PI) angleDiff = 2 * Math.PI - angleDiff

            if (angleDiff > maxAngularWindow) continue

            const size2 = getActualNodeSize(n2.ring, n2.rawNode.importance ?? 0)
            const spacing = getAdaptiveSpacing(size1, size2)
            const minDist = size1 + size2 + spacing

            const dx = n2.x - n1.x
            const dy = n2.y - n1.y
            const dist = Math.sqrt(dx * dx + dy * dy)

            if (dist < minDist && dist > 0) {
              hadOverlap = true

              const overlap = minDist - dist
              const pushAngle = overlap / (2 * radius)

              n1.angle -= pushAngle / 2
              n2.angle += pushAngle / 2

              // Normalize angles to [0, 2*PI)
              while (n1.angle < 0) n1.angle += 2 * Math.PI
              while (n2.angle < 0) n2.angle += 2 * Math.PI
              while (n1.angle >= 2 * Math.PI) n1.angle -= 2 * Math.PI
              while (n2.angle >= 2 * Math.PI) n2.angle -= 2 * Math.PI

              n1.x = radius * Math.cos(n1.angle)
              n1.y = radius * Math.sin(n1.angle)
              n2.x = radius * Math.cos(n2.angle)
              n2.y = radius * Math.sin(n2.angle)
            }
          }
        }
      }

      if (!hadOverlap) break
    }
  }
}

/**
 * Overlap pair with detailed info
 */
export interface OverlapPair {
  node1: string
  node2: string
  ring: number
  distance: number
  minDistance: number
  overlapAmount: number
  angleDiff: number
}

/**
 * Detailed overlap report
 */
export interface OverlapReport {
  totalOverlaps: number
  overlapsByRing: Map<number, number>
  worstOverlaps: OverlapPair[]
  overlapPairs: OverlapPair[]
}

/**
 * Detect overlaps using Euclidean distance with detailed reporting.
 * Checks nearby pairs within an angular window to catch large nodes
 * that might overlap even if not angularly adjacent.
 */
export function detectOverlaps(
  layoutNodes: LayoutNode[],
  computedRings: ComputedRingConfig[],
  _nodePadding: number  // Unused - we only detect true overlaps, not padding violations
): OverlapPair[] {
  const overlaps: OverlapPair[] = []
  const OVERLAP_TOLERANCE = 0.5  // Allow 0.5px tolerance for sub-pixel precision

  const nodesByRing = new Map<number, LayoutNode[]>()
  for (const node of layoutNodes) {
    if (!nodesByRing.has(node.ring)) {
      nodesByRing.set(node.ring, [])
    }
    nodesByRing.get(node.ring)!.push(node)
  }

  for (const [ring, ringNodes] of nodesByRing) {
    if (ringNodes.length < 2) continue

    const ringConfig = computedRings[ring]
    if (!ringConfig || ringConfig.radius === 0) continue
    const ringRadius = ringConfig.radius

    // Sort by angle for efficient nearby checking
    ringNodes.sort((a, b) => a.angle - b.angle)

    // For each node, check nearby nodes within an angular window
    // Window size based on max possible node size at this ring
    const maxNodeRadius = currentSizeRange.maxRadius
    const maxAngularWindow = (maxNodeRadius * 4) / ringRadius // 4x max radius as safety margin

    for (let i = 0; i < ringNodes.length; i++) {
      const n1 = ringNodes[i]
      const size1 = getActualNodeSize(n1.ring, n1.rawNode.importance ?? 0)

      // Check nodes within the angular window (forward only to avoid duplicates)
      for (let j = i + 1; j < ringNodes.length; j++) {
        const n2 = ringNodes[j]

        // Calculate angular difference
        let angleDiff = n2.angle - n1.angle
        if (angleDiff > Math.PI) angleDiff = 2 * Math.PI - angleDiff

        // Stop if we're past the angular window (nodes are sorted)
        if (angleDiff > maxAngularWindow) break

        const size2 = getActualNodeSize(n2.ring, n2.rawNode.importance ?? 0)

        // Use Euclidean distance (what visually matters)
        const dx = n1.x - n2.x
        const dy = n1.y - n2.y
        const distance = Math.sqrt(dx * dx + dy * dy)

        // Minimum distance for circles to NOT overlap = sum of radii
        const minDistance = size1 + size2 - OVERLAP_TOLERANCE

        if (distance < minDistance) {
          overlaps.push({
            node1: n1.id,
            node2: n2.id,
            ring,
            distance,
            minDistance,
            overlapAmount: minDistance - distance,
            angleDiff: angleDiff * 180 / Math.PI
          })
        }
      }

      // Also check wrap-around (last few nodes might overlap with first few)
      if (i < 5) { // Check first 5 nodes against last nodes
        for (let j = ringNodes.length - 1; j >= ringNodes.length - 5 && j > i; j--) {
          const n2 = ringNodes[j]

          // Angular diff with wrap-around
          let angleDiff = (2 * Math.PI - n2.angle) + n1.angle
          if (angleDiff > Math.PI) angleDiff = 2 * Math.PI - angleDiff

          if (angleDiff > maxAngularWindow) continue

          const size2 = getActualNodeSize(n2.ring, n2.rawNode.importance ?? 0)

          const dx = n1.x - n2.x
          const dy = n1.y - n2.y
          const distance = Math.sqrt(dx * dx + dy * dy)
          const minDistance = size1 + size2 - OVERLAP_TOLERANCE

          if (distance < minDistance) {
            overlaps.push({
              node1: n1.id,
              node2: n2.id,
              ring,
              distance,
              minDistance,
              overlapAmount: minDistance - distance,
              angleDiff: angleDiff * 180 / Math.PI
            })
          }
        }
      }
    }
  }

  // Log overlap summary
  if (overlaps.length > 0) {
    debug.overlap('\n=== Overlap Detection Report ===')
    debug.overlap(`Total overlaps: ${overlaps.length}`)

    // Group by ring
    const byRing = new Map<number, number>()
    overlaps.forEach(o => {
      byRing.set(o.ring, (byRing.get(o.ring) || 0) + 1)
    })
    debug.overlap('By ring:')
    Array.from(byRing.entries())
      .sort((a, b) => a[0] - b[0])
      .forEach(([ring, count]) => {
        debug.overlap(`  Ring ${ring}: ${count} overlaps`)
      })

    debug.overlap('\nWorst overlaps (top 10):')
    overlaps
      .sort((a, b) => b.overlapAmount - a.overlapAmount)
      .slice(0, 10)
      .forEach(o => {
        debug.overlap(
          `  Ring ${o.ring}: ${o.node1} <-> ${o.node2}: ` +
          `overlap=${o.overlapAmount.toFixed(2)}px, ` +
          `distance=${o.distance.toFixed(2)}px, ` +
          `needed=${o.minDistance.toFixed(2)}px, ` +
          `angleDiff=${o.angleDiff.toFixed(3)}°`
        )
      })
  }

  return overlaps
}

/**
 * Generate detailed overlap report
 */
export function generateOverlapReport(overlaps: OverlapPair[]): OverlapReport {
  const byRing = new Map<number, number>()
  overlaps.forEach(o => {
    byRing.set(o.ring, (byRing.get(o.ring) || 0) + 1)
  })

  return {
    totalOverlaps: overlaps.length,
    overlapsByRing: byRing,
    worstOverlaps: overlaps
      .sort((a, b) => b.overlapAmount - a.overlapAmount)
      .slice(0, 20),
    overlapPairs: overlaps
  }
}

/**
 * Compute layout statistics
 */
export function computeLayoutStats(
  layoutNodes: LayoutNode[],
  computedRings: ComputedRingConfig[],
  nodePadding: number
): {
  nodesPerRing: Map<number, number>
  minDistancePerRing: Map<number, number>
  requiredRadiusPerRing: Map<number, number>
} {
  const nodesPerRing = new Map<number, number>()
  const minDistancePerRing = new Map<number, number>()
  const requiredRadiusPerRing = new Map<number, number>()

  const nodesByRing = new Map<number, LayoutNode[]>()
  for (const node of layoutNodes) {
    if (!nodesByRing.has(node.ring)) {
      nodesByRing.set(node.ring, [])
    }
    nodesByRing.get(node.ring)!.push(node)
  }

  for (const [ring, ringNodes] of nodesByRing) {
    nodesPerRing.set(ring, ringNodes.length)

    let minDist = Infinity
    for (let i = 0; i < ringNodes.length; i++) {
      for (let j = i + 1; j < ringNodes.length; j++) {
        const dx = ringNodes[i].x - ringNodes[j].x
        const dy = ringNodes[i].y - ringNodes[j].y
        const dist = Math.sqrt(dx * dx + dy * dy)
        minDist = Math.min(minDist, dist)
      }
    }
    minDistancePerRing.set(ring, minDist === Infinity ? 0 : minDist)

    const ringConfig = computedRings[ring] || computedRings[computedRings.length - 1]
    const minNodeSpacing = ringConfig.nodeSize * 2 + nodePadding
    const circumference = ringNodes.length * minNodeSpacing
    const requiredRadius = circumference / (2 * Math.PI)
    requiredRadiusPerRing.set(ring, requiredRadius)
  }

  return { nodesPerRing, minDistancePerRing, requiredRadiusPerRing }
}

export { getActualNodeSize }
