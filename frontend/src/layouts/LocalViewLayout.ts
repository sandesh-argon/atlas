/**
 * LocalViewLayout - Horizontal Flow Chart Layout for Local View
 *
 * Layout structure (horizontal mode):
 *   Left columns:   Input nodes (causes) by depth
 *   Center column:  Target nodes
 *   Right columns:  Output nodes (effects) by depth
 *
 * Layout structure (vertical mode - for narrow containers):
 *   Top rows:       Input nodes (causes) by depth
 *   Middle row:     Target nodes
 *   Bottom rows:    Output nodes (effects) by depth
 *
 * Shape semantics:
 *   - Pill (rounded rect): Input/cause nodes
 *   - Rectangle: Target nodes (bold border)
 *   - Hexagon: Output/effect nodes
 */

import type { LocalViewNode, LocalViewEdge, FlowDirection } from '../types'

// ============================================
// Layout Constants
// ============================================

const NODE_SPACING = 20          // Spacing between nodes in same column/row
const NODE_SPACING_VERTICAL = 20 // Spacing for vertical layout (was 15, increased to prevent overlap)
const BASE_NODE_HEIGHT = 50      // Base height for nodes
const ASPECT_THRESHOLD = 1.0     // Switch to vertical when width/height < this
const LABEL_CHAR_WIDTH = 7       // Approximate pixels per character
const NODE_PADDING = 10          // Horizontal padding inside nodes

// Vertical layout compactness settings
const VERTICAL_DECLUTTER_THRESHOLD = 6  // Hide beta earlier in vertical mode
const VERTICAL_MAX_NODES_PER_ROW = 4    // Wrap to multiple rows when exceeded
const SUBTREE_WIDTH_BUFFER = 30         // Extra buffer between subtrees to prevent edge overlap

// Beta-based sizing defaults (MOST AGGRESSIVE - nuclear option)
// All visual elements use the same sqrt-based scale for consistency
const DEFAULT_SIZE_MIN_SCALE = 0.10  // Smallest = 10% of base (18x ratio)
const DEFAULT_SIZE_MAX_SCALE = 1.8   // Largest = 180% of base
const EDGE_WIDTH_MIN = 0.4           // Thinnest edge
const EDGE_WIDTH_MAX = 7             // Thickest edge (17.5x ratio)

// Text scaling (balanced for readability and contrast)
const BASE_FONT_SIZE = 12            // Slightly larger base
const FONT_SIZE_MIN_SCALE = 0.55     // Lower floor for more contrast
const FONT_SIZE_MAX_SCALE = 1.4      // Max scale
const MIN_READABLE_FONT = 8          // Floor for readability

// Arrow scaling (slightly compressed to prevent tiny arrows)
export const ARROW_BASE_SIZE = 2.5        // Reduced by 50%
const ARROW_MIN_SCALE = 0.7        // Prevent arrows smaller than 1.75px
const ARROW_MAX_SCALE = 1.5        // Max arrow size

// ============================================
// Interfaces
// ============================================

/** Positioned node for rendering with shape information */
export interface PositionedLocalNode extends LocalViewNode {
  x: number              // Center X coordinate
  y: number              // Center Y coordinate
  width: number          // Node width
  height: number         // Node height
  layer: 'input' | 'target' | 'output'
  maxLabelChars: number  // Max chars for label truncation
  betaDisplay: string    // Formatted beta string (e.g., "+2.34")
  betaColor: string      // Green for positive, red for negative
  fontSize: number       // Scaled font size based on beta
  edgeWidth: number      // Edge stroke width for connected edges
  arrowScale: number     // Arrow marker scale factor
}

/** Complete layout result */
export interface LocalViewLayoutResult {
  nodes: PositionedLocalNode[]
  edges: LocalViewEdge[]
  bounds: {
    width: number
    height: number
    centerX: number
    centerY: number
  }
  flowDirection: FlowDirection
  minBeta: number
  maxBeta: number
}

// ============================================
// Utility Functions
// ============================================

/**
 * Determine flow direction based on container aspect ratio
 */
export function getFlowDirection(
  containerWidth: number,
  containerHeight: number
): FlowDirection {
  const aspectRatio = containerWidth / containerHeight
  return aspectRatio >= ASPECT_THRESHOLD ? 'horizontal' : 'vertical'
}

/**
 * UNIFIED SCALING: Calculate area-proportional scale using sqrt
 * All visual elements use this same base calculation for consistency
 *
 * Uses visualBeta (propagated from targets) for sizing to create visual hierarchy:
 * - Targets: visualBeta = 1.0 (largest)
 * - Children: visualBeta = parent.visualBeta × edge.beta (progressively smaller)
 *
 * Now uses actual min/max range of visible nodes for better contrast
 */
function getAreaScale(visualBeta: number, minVisualBeta: number, maxVisualBeta: number): number {
  if (maxVisualBeta <= minVisualBeta) return 0.5 // Default to mid-point if no range
  // Normalize to 0-1 within the actual visible range
  const normalized = (visualBeta - minVisualBeta) / (maxVisualBeta - minVisualBeta)
  return Math.sqrt(Math.max(0, Math.min(1, normalized))) // sqrt for area-proportional
}

/**
 * Calculate node size scale based on visualBeta using AREA scaling
 * Since area = width * height, we use sqrt to make area proportional to visualBeta
 */
function getNodeSizeScale(
  visualBeta: number,
  minVisualBeta: number,
  maxVisualBeta: number,
  minScale: number = DEFAULT_SIZE_MIN_SCALE,
  maxScale: number = DEFAULT_SIZE_MAX_SCALE
): number {
  const areaScale = getAreaScale(visualBeta, minVisualBeta, maxVisualBeta)
  return minScale + areaScale * (maxScale - minScale)
}

/**
 * Get edge stroke width based on visualBeta (UNIFIED: uses sqrt scaling)
 * Edge width reflects the target node's visual importance
 */
export function getEdgeWidth(visualBeta: number, minVisualBeta: number, maxVisualBeta: number): number {
  if (maxVisualBeta <= minVisualBeta) return (EDGE_WIDTH_MIN + EDGE_WIDTH_MAX) / 2
  const areaScale = getAreaScale(visualBeta, minVisualBeta, maxVisualBeta)
  return EDGE_WIDTH_MIN + areaScale * (EDGE_WIDTH_MAX - EDGE_WIDTH_MIN)
}

/**
 * Get arrow scale based on visualBeta (UNIFIED: uses sqrt scaling)
 */
function getArrowScale(visualBeta: number, minVisualBeta: number, maxVisualBeta: number): number {
  const areaScale = getAreaScale(visualBeta, minVisualBeta, maxVisualBeta)
  return ARROW_MIN_SCALE + areaScale * (ARROW_MAX_SCALE - ARROW_MIN_SCALE)
}

/**
 * Format beta value for display
 */
function formatBeta(beta: number | undefined): string {
  if (beta === undefined) return ''
  const sign = beta >= 0 ? '+' : ''
  return `${sign}${beta.toFixed(2)}`
}

/**
 * Get beta color based on sign
 */
function getBetaColor(beta: number | undefined): string {
  if (beta === undefined) return '#666'
  return beta >= 0 ? '#2E7D32' : '#C62828' // Dark green / dark red
}

/**
 * Calculate font size based on visualBeta (UNIFIED: uses sqrt scaling to match node)
 */
function getFontSize(visualBeta: number, minVisualBeta: number, maxVisualBeta: number): number {
  if (maxVisualBeta <= minVisualBeta) return BASE_FONT_SIZE
  const areaScale = getAreaScale(visualBeta, minVisualBeta, maxVisualBeta)
  const scale = FONT_SIZE_MIN_SCALE + areaScale * (FONT_SIZE_MAX_SCALE - FONT_SIZE_MIN_SCALE)
  const fontSize = BASE_FONT_SIZE * scale
  return Math.max(MIN_READABLE_FONT, Math.round(fontSize * 10) / 10) // Floor at 8px
}

/**
 * Calculate node dimensions based on shape, visualBeta, and label length
 * Padding scales with text size for visual consistency
 * Area is proportional to visualBeta (propagated from target)
 *
 * @param showBeta - Whether beta text will be displayed (affects height)
 */
function getNodeDimensions(
  node: LocalViewNode,
  minVisualBeta: number,
  maxVisualBeta: number,
  horizontalPadding: number = NODE_PADDING,
  verticalPadding: number = 10,
  sizeMinScale: number = DEFAULT_SIZE_MIN_SCALE,
  sizeMaxScale: number = DEFAULT_SIZE_MAX_SCALE,
  showBeta: boolean = true
): { width: number; height: number } {
  const sizeScale = getNodeSizeScale(node.visualBeta, minVisualBeta, maxVisualBeta, sizeMinScale, sizeMaxScale)
  const fontSize = getFontSize(node.visualBeta, minVisualBeta, maxVisualBeta)
  const fontScale = fontSize / BASE_FONT_SIZE

  // Scale padding with font size
  const scaledHPad = horizontalPadding * fontScale
  const scaledVPad = verticalPadding * fontScale

  // Calculate width based on label length with scaled padding
  const labelWidth = node.label.length * LABEL_CHAR_WIDTH * fontScale + scaledHPad * 2
  const minWidth = 60 * sizeScale
  const calculatedWidth = Math.max(minWidth, labelWidth)

  // Height: significantly reduced when beta text is hidden
  // With beta: 2.5x font (room for label + beta value)
  // Without beta: 1.1x font (compact label-only)
  const textMultiplier = showBeta ? 2.5 : 1.1
  const textHeight = fontSize * textMultiplier
  const paddingMultiplier = showBeta ? 1.0 : 0.5  // Halve padding when no beta
  const calculatedHeight = textHeight + scaledVPad * 2 * paddingMultiplier

  return {
    width: calculatedWidth,
    height: Math.max(BASE_NODE_HEIGHT * sizeScale * 0.7, calculatedHeight)
  }
}

// ============================================
// Layout Functions
// ============================================

/**
 * Get maximum width of nodes in a group
 */
function getMaxColumnWidth(nodes: LocalViewNode[], minBeta: number, maxBeta: number, hPad: number, vPad: number, minScale: number, maxScale: number): number {
  if (nodes.length === 0) return 0
  return Math.max(...nodes.map(n => getNodeDimensions(n, minBeta, maxBeta, hPad, vPad, minScale, maxScale).width))
}

/**
 * Reorder children so that the biggest nodes (by visualBeta) are in the center,
 * with progressively smaller nodes alternating toward the edges.
 *
 * Example: nodes with visualBeta [0.1, 0.3, 0.5, 0.7, 0.9] become:
 *   [0.1, 0.3, 0.9, 0.7, 0.5] (biggest in center, smaller toward edges)
 */
function reorderForCenterBias<T extends { visualBeta: number }>(nodes: T[]): T[] {
  if (nodes.length <= 2) return nodes

  // Sort by visualBeta descending (biggest first)
  const sorted = [...nodes].sort((a, b) => b.visualBeta - a.visualBeta)

  // Build center-biased order: biggest in middle, smaller alternating outward
  const result: T[] = new Array(sorted.length)
  const mid = Math.floor(sorted.length / 2)

  // Place nodes from center outward
  for (let i = 0; i < sorted.length; i++) {
    if (i === 0) {
      // Biggest goes in center
      result[mid] = sorted[i]
    } else {
      // Alternate left and right of center
      const offset = Math.ceil(i / 2)
      const goLeft = i % 2 === 1
      const targetIndex = goLeft ? mid - offset : mid + offset

      // Handle edge cases for even length arrays
      if (targetIndex >= 0 && targetIndex < sorted.length && result[targetIndex] === undefined) {
        result[targetIndex] = sorted[i]
      } else {
        // Find next available slot
        for (let j = 0; j < sorted.length; j++) {
          if (result[j] === undefined) {
            result[j] = sorted[i]
            break
          }
        }
      }
    }
  }

  return result
}

/**
 * Build a tree structure from nodes using parentId
 */
function buildTree(
  nodes: LocalViewNode[],
  rootIds: string[]
): Map<string, LocalViewNode[]> {
  const childrenMap = new Map<string, LocalViewNode[]>()

  // Initialize with empty arrays for roots
  for (const rootId of rootIds) {
    childrenMap.set(rootId, [])
  }

  // Group nodes by their parent
  for (const node of nodes) {
    const parentId = node.parentId
    if (parentId) {
      if (!childrenMap.has(parentId)) {
        childrenMap.set(parentId, [])
      }
      childrenMap.get(parentId)!.push(node)
    }
  }

  return childrenMap
}

/**
 * Calculate subtree height (total vertical space needed for a node and all descendants)
 */
function calculateSubtreeHeight(
  nodeId: string,
  childrenMap: Map<string, LocalViewNode[]>,
  nodeHeights: Map<string, number>,
  spacing: number
): number {
  const children = childrenMap.get(nodeId) || []

  if (children.length === 0) {
    return nodeHeights.get(nodeId) || 40
  }

  // Sum of all children's subtree heights plus spacing between them
  let totalHeight = 0
  for (const child of children) {
    totalHeight += calculateSubtreeHeight(child.id, childrenMap, nodeHeights, spacing)
  }
  totalHeight += (children.length - 1) * spacing

  // Return max of own height and children's total
  const ownHeight = nodeHeights.get(nodeId) || 40
  return Math.max(ownHeight, totalHeight)
}

/**
 * Position nodes in a tree structure recursively
 */
function positionTreeNodes(
  nodeId: string,
  centerY: number,
  columnX: number,
  childrenMap: Map<string, LocalViewNode[]>,
  nodeMap: Map<string, LocalViewNode>,
  positionedNodes: PositionedLocalNode[],
  nodeHeights: Map<string, number>,
  nodeDims: Map<string, { width: number; height: number }>,
  minBeta: number,
  maxBeta: number,
  layer: 'input' | 'target' | 'output',
  spacing: number,
  columnGap: number,
  direction: 'left' | 'right'
): void {
  const rawChildren = childrenMap.get(nodeId) || []
  if (rawChildren.length === 0) return

  // Reorder children so biggest nodes are in the center
  const children = reorderForCenterBias(rawChildren)

  // Calculate total height needed for children
  const childHeights: number[] = children.map(child =>
    calculateSubtreeHeight(child.id, childrenMap, nodeHeights, spacing)
  )
  const totalChildHeight = childHeights.reduce((a, b) => a + b, 0) + (children.length - 1) * spacing

  // Position children centered around parent's Y
  let currentY = centerY - totalChildHeight / 2

  for (let i = 0; i < children.length; i++) {
    const child = children[i]
    const subtreeHeight = childHeights[i]
    const childCenterY = currentY + subtreeHeight / 2

    const dims = nodeDims.get(child.id) || { width: 100, height: 40 }
    const childColumnX = direction === 'right'
      ? columnX + columnGap + dims.width / 2
      : columnX - columnGap - dims.width / 2

    // Create positioned node
    const positioned: PositionedLocalNode = {
      ...child,
      x: childColumnX,
      y: childCenterY,
      width: dims.width,
      height: dims.height,
      layer,
      maxLabelChars: 999,
      betaDisplay: formatBeta(child.beta),  // Display original beta
      betaColor: getBetaColor(child.beta),
      fontSize: getFontSize(child.visualBeta, minBeta, maxBeta),      // Size by visualBeta
      edgeWidth: getEdgeWidth(child.visualBeta, minBeta, maxBeta),    // Size by visualBeta
      arrowScale: getArrowScale(child.visualBeta, minBeta, maxBeta)   // Size by visualBeta
    }
    positionedNodes.push(positioned)

    // Recursively position this node's children
    positionTreeNodes(
      child.id,
      childCenterY,
      childColumnX + (direction === 'right' ? dims.width / 2 : -dims.width / 2),
      childrenMap,
      nodeMap,
      positionedNodes,
      nodeHeights,
      nodeDims,
      minBeta,
      maxBeta,
      layer,
      spacing,
      columnGap,
      direction
    )

    currentY += subtreeHeight + spacing
  }
}

/**
 * Compute horizontal layout: Causes (left) -> Target (center) -> Effects (right)
 * Uses tree structure to avoid edge overlaps
 */
function computeHorizontalLayout(
  targets: LocalViewNode[],
  inputs: LocalViewNode[],
  outputs: LocalViewNode[],
  edges: LocalViewEdge[],
  minBeta: number,
  maxBeta: number,
  columnGap: number,
  hPad: number,
  vPad: number,
  minScale: number,
  maxScale: number,
  declutterThreshold: number,
  forceShowBeta?: boolean
): LocalViewLayoutResult {
  const positionedNodes: PositionedLocalNode[] = []
  const targetIds = targets.map(t => t.id)

  // Pre-calculate dimensions for all nodes (with declutter-aware height)
  const nodeDims = new Map<string, { width: number; height: number }>()
  const nodeHeights = new Map<string, number>()
  const allNodes = [...targets, ...inputs, ...outputs]
  const totalNodes = allNodes.length

  for (const node of allNodes) {
    const showBeta = shouldShowBeta(node, totalNodes, declutterThreshold, false, !!forceShowBeta)
    const dims = getNodeDimensions(node, minBeta, maxBeta, hPad, vPad, minScale, maxScale, showBeta)
    nodeDims.set(node.id, dims)
    nodeHeights.set(node.id, dims.height)
  }

  // Build tree structures
  const inputTree = buildTree(inputs, targetIds)
  const outputTree = buildTree(outputs, targetIds)

  // Create node lookup
  const nodeMap = new Map<string, LocalViewNode>()
  for (const node of allNodes) {
    nodeMap.set(node.id, node)
  }

  // Derive spacing from average node height (~30% of avg height, min 6, max NODE_SPACING)
  const heights = Array.from(nodeHeights.values())
  const avgHeight = heights.length > 0 ? heights.reduce((a, b) => a + b, 0) / heights.length : 40
  const nodeSpacing = Math.max(6, Math.min(NODE_SPACING, avgHeight * 0.3))

  // Position targets close together at center
  const targetWidth = getMaxColumnWidth(targets, minBeta, maxBeta, hPad, vPad, minScale, maxScale)

  // Calculate heights for targets (close together) and subtrees (spread out)
  const targetHeights: number[] = targets.map(t => nodeHeights.get(t.id) || 40)
  const inputSubtreeHeights: number[] = targets.map(t =>
    calculateSubtreeHeight(t.id, inputTree, nodeHeights, nodeSpacing)
  )
  const outputSubtreeHeights: number[] = targets.map(t =>
    calculateSubtreeHeight(t.id, outputTree, nodeHeights, nodeSpacing)
  )

  // Total height for targets (close together with small spacing)
  const totalTargetHeight = targetHeights.reduce((sum, h) => sum + h, 0) +
    (targets.length - 1) * nodeSpacing

  // Total height for subtrees (spread out to avoid overlap)
  const totalInputHeight = inputSubtreeHeights.reduce((sum, h) => sum + h, 0) +
    (targets.length - 1) * nodeSpacing * 2
  const totalOutputHeight = outputSubtreeHeights.reduce((sum, h) => sum + h, 0) +
    (targets.length - 1) * nodeSpacing * 2

  // Position targets close together at center
  let targetY = -totalTargetHeight / 2

  for (let i = 0; i < targets.length; i++) {
    const target = targets[i]
    const dims = nodeDims.get(target.id) || { width: 100, height: 40 }
    const y = targetY + dims.height / 2

    const positioned: PositionedLocalNode = {
      ...target,
      x: 0,
      y,
      width: dims.width,
      height: dims.height,
      layer: 'target',
      maxLabelChars: 999,
      betaDisplay: '',
      betaColor: '#666',
      fontSize: getFontSize(target.visualBeta, minBeta, maxBeta),
      edgeWidth: getEdgeWidth(target.visualBeta, minBeta, maxBeta),
      arrowScale: getArrowScale(target.visualBeta, minBeta, maxBeta)
    }
    positionedNodes.push(positioned)

    targetY += dims.height + nodeSpacing
  }

  // Position input subtrees (spread out vertically, independent of target Y)
  let inputSubtreeY = -totalInputHeight / 2
  for (let i = 0; i < targets.length; i++) {
    const target = targets[i]
    const subtreeHeight = inputSubtreeHeights[i]
    const subtreeCenterY = inputSubtreeY + subtreeHeight / 2

    positionTreeNodes(
      target.id,
      subtreeCenterY,  // Subtree centered at its own Y, not target's Y
      -targetWidth / 2,
      inputTree,
      nodeMap,
      positionedNodes,
      nodeHeights,
      nodeDims,
      minBeta,
      maxBeta,
      'input',
      nodeSpacing,
      columnGap,
      'left'
    )

    inputSubtreeY += subtreeHeight + nodeSpacing * 2
  }

  // Position output subtrees (spread out vertically, independent of target Y)
  let outputSubtreeY = -totalOutputHeight / 2
  for (let i = 0; i < targets.length; i++) {
    const target = targets[i]
    const subtreeHeight = outputSubtreeHeights[i]
    const subtreeCenterY = outputSubtreeY + subtreeHeight / 2

    positionTreeNodes(
      target.id,
      subtreeCenterY,  // Subtree centered at its own Y, not target's Y
      targetWidth / 2,
      outputTree,
      nodeMap,
      positionedNodes,
      nodeHeights,
      nodeDims,
      minBeta,
      maxBeta,
      'output',
      nodeSpacing,
      columnGap,
      'right'
    )

    outputSubtreeY += subtreeHeight + nodeSpacing * 2
  }

  // Calculate bounds
  const bounds = calculateBounds(positionedNodes)

  return { nodes: positionedNodes, edges, bounds, flowDirection: 'horizontal', minBeta, maxBeta }
}

/**
 * Calculate subtree width (total horizontal space needed for a node and all descendants)
 * Accounts for multi-row wrapping - only needs width of the widest row, not all children
 */
function calculateSubtreeWidth(
  nodeId: string,
  childrenMap: Map<string, LocalViewNode[]>,
  nodeWidths: Map<string, number>,
  spacing: number,
  maxNodesPerRow: number = VERTICAL_MAX_NODES_PER_ROW
): number {
  const children = childrenMap.get(nodeId) || []

  if (children.length === 0) {
    return nodeWidths.get(nodeId) || 100
  }

  // Get subtree widths for each child
  const childSubtreeWidths = children.map(child =>
    calculateSubtreeWidth(child.id, childrenMap, nodeWidths, spacing, maxNodesPerRow)
  )

  // Split into rows (same logic as splitIntoRows)
  const n = children.length
  let maxRowWidth = 0

  if (n <= maxNodesPerRow) {
    // Single row: sum all widths
    maxRowWidth = childSubtreeWidths.reduce((sum, w) => sum + w, 0) + (n - 1) * spacing
  } else {
    // Multiple rows: find widest row
    const numRows = Math.ceil(n / maxNodesPerRow)
    const basePerRow = Math.floor(n / numRows)
    const extraNodes = n % numRows

    let idx = 0
    for (let r = 0; r < numRows; r++) {
      const rowSize = basePerRow + (r < extraNodes ? 1 : 0)
      const rowWidths = childSubtreeWidths.slice(idx, idx + rowSize)
      const rowWidth = rowWidths.reduce((sum, w) => sum + w, 0) + (rowSize - 1) * spacing
      maxRowWidth = Math.max(maxRowWidth, rowWidth)
      idx += rowSize
    }
  }

  // Return max of own width and widest row, plus buffer for safety margin
  const ownWidth = nodeWidths.get(nodeId) || 100
  const subtreeWidth = Math.max(ownWidth, maxRowWidth)
  // Add buffer only if this node has children (subtrees need extra margin)
  return children.length > 0 ? subtreeWidth + SUBTREE_WIDTH_BUFFER : subtreeWidth
}

/**
 * Position a single row of nodes centered on parentX using subtree widths
 * Uses subtree widths for spacing to prevent overlaps when children expand
 * Returns the X positions for nodes in this row
 */
function positionRowCentered(
  nodes: LocalViewNode[],
  subtreeWidths: number[],
  centerX: number,
  spacing: number
): number[] {
  const n = nodes.length
  if (n === 0) return []

  const widths = subtreeWidths
  const positions: number[] = new Array(n)

  if (n === 1) {
    positions[0] = centerX
  } else if (n % 2 === 1) {
    // Odd: middle at center
    const midIndex = Math.floor(n / 2)
    positions[midIndex] = centerX

    let x = centerX
    for (let i = midIndex - 1; i >= 0; i--) {
      x -= widths[i + 1] / 2 + spacing + widths[i] / 2
      positions[i] = x
    }
    x = centerX
    for (let i = midIndex + 1; i < n; i++) {
      x += widths[i - 1] / 2 + spacing + widths[i] / 2
      positions[i] = x
    }
  } else {
    // Even: gap at center
    const leftMid = n / 2 - 1
    const rightMid = n / 2
    positions[leftMid] = centerX - spacing / 2 - widths[leftMid] / 2
    positions[rightMid] = centerX + spacing / 2 + widths[rightMid] / 2

    let x = positions[leftMid]
    for (let i = leftMid - 1; i >= 0; i--) {
      x -= widths[i + 1] / 2 + spacing + widths[i] / 2
      positions[i] = x
    }
    x = positions[rightMid]
    for (let i = rightMid + 1; i < n; i++) {
      x += widths[i - 1] / 2 + spacing + widths[i] / 2
      positions[i] = x
    }
  }

  return positions
}

/**
 * Split children into multiple rows for better viewport usage
 * Each row is balanced for visual appeal
 */
function splitIntoRows(
  children: LocalViewNode[],
  maxNodesPerRow: number = 5  // Limit nodes per row for readability
): LocalViewNode[][] {
  if (children.length <= maxNodesPerRow) {
    return [children]
  }

  const rows: LocalViewNode[][] = []
  const n = children.length
  const numRows = Math.ceil(n / maxNodesPerRow)
  const basePerRow = Math.floor(n / numRows)
  const extraNodes = n % numRows

  let idx = 0
  for (let r = 0; r < numRows; r++) {
    // Distribute extra nodes to earlier rows for balance
    const rowSize = basePerRow + (r < extraNodes ? 1 : 0)
    rows.push(children.slice(idx, idx + rowSize))
    idx += rowSize
  }

  return rows
}

/**
 * Position nodes in a vertical tree structure with multi-row support
 * Uses SUBTREE WIDTHS for spacing to prevent overlaps when children expand
 * When there are many children, they wrap into multiple rows
 * Each row is centered on parent's X axis
 */
function positionTreeNodesVertical(
  nodeId: string,
  centerX: number,
  rowY: number,
  childrenMap: Map<string, LocalViewNode[]>,
  positionedNodes: PositionedLocalNode[],
  nodeDims: Map<string, { width: number; height: number }>,
  nodeWidths: Map<string, number>,
  minBeta: number,
  maxBeta: number,
  layer: 'input' | 'target' | 'output',
  spacing: number,
  rowGap: number,
  direction: 'up' | 'down',
  maxNodesPerRow: number = 5
): void {
  const rawChildren = childrenMap.get(nodeId) || []
  if (rawChildren.length === 0) return

  // Reorder children so biggest nodes are in the center
  const children = reorderForCenterBias(rawChildren)

  // Split children into rows
  const rows = splitIntoRows(children, maxNodesPerRow)

  // Track current Y position for stacking rows
  let currentRowY = rowY

  // For 'up' direction, we process rows in reverse order (furthest first)
  const rowIndices = direction === 'up'
    ? rows.map((_, i) => i).reverse()
    : rows.map((_, i) => i)

  for (const rowIdx of rowIndices) {
    const row = rows[rowIdx]

    // Get max height in this row
    const rowHeight = Math.max(...row.map(child => {
      const dims = nodeDims.get(child.id)
      return dims ? dims.height : 40
    }))

    // Calculate Y for this row
    const thisRowY = direction === 'down'
      ? currentRowY + rowGap + rowHeight / 2
      : currentRowY - rowGap - rowHeight / 2

    // Calculate subtree widths for each child to prevent overlaps
    const subtreeWidths = row.map(child =>
      calculateSubtreeWidth(child.id, childrenMap, nodeWidths, spacing, maxNodesPerRow)
    )

    // Position nodes in this row centered on parent X, using SUBTREE widths
    const xPositions = positionRowCentered(row, subtreeWidths, centerX, spacing)

    // Create positioned nodes
    for (let i = 0; i < row.length; i++) {
      const child = row[i]
      const dims = nodeDims.get(child.id) || { width: 100, height: 40 }

      const positioned: PositionedLocalNode = {
        ...child,
        x: xPositions[i],
        y: thisRowY,
        width: dims.width,
        height: dims.height,
        layer,
        maxLabelChars: 999,
        betaDisplay: formatBeta(child.beta),
        betaColor: getBetaColor(child.beta),
        fontSize: getFontSize(child.visualBeta, minBeta, maxBeta),
        edgeWidth: getEdgeWidth(child.visualBeta, minBeta, maxBeta),
        arrowScale: getArrowScale(child.visualBeta, minBeta, maxBeta)
      }
      positionedNodes.push(positioned)

      // Recursively position this node's children
      positionTreeNodesVertical(
        child.id,
        xPositions[i],
        thisRowY + (direction === 'down' ? dims.height / 2 : -dims.height / 2),
        childrenMap,
        positionedNodes,
        nodeDims,
        nodeWidths,
        minBeta,
        maxBeta,
        layer,
        spacing,
        rowGap,
        direction,
        maxNodesPerRow
      )
    }

    // Update currentRowY for next row
    currentRowY = thisRowY + (direction === 'down' ? rowHeight / 2 : -rowHeight / 2)
  }
}

/**
 * Compute vertical layout: Causes (top) -> Target (middle) -> Effects (bottom)
 * Uses tree structure like horizontal layout for proper subtree spacing
 *
 * Child nodes are centered on their parent's X position with subtree-aware spacing
 * to prevent overlaps when branches have different depths.
 */
function computeVerticalLayout(
  targets: LocalViewNode[],
  inputs: LocalViewNode[],
  outputs: LocalViewNode[],
  edges: LocalViewEdge[],
  minBeta: number,
  maxBeta: number,
  rowGap: number,
  hPad: number,
  vPad: number,
  minScale: number,
  maxScale: number,
  declutterThreshold: number,
  forceShowBeta?: boolean
): LocalViewLayoutResult {
  const positionedNodes: PositionedLocalNode[] = []
  const targetIds = targets.map(t => t.id)

  // Pre-calculate dimensions for all nodes
  const nodeDims = new Map<string, { width: number; height: number }>()
  const nodeWidths = new Map<string, number>()
  const allNodes = [...targets, ...inputs, ...outputs]
  const totalNodes = allNodes.length

  for (const node of allNodes) {
    const showBeta = shouldShowBeta(node, totalNodes, declutterThreshold, true, !!forceShowBeta) // vertical layout - always hide beta for depth > 1
    const dims = getNodeDimensions(node, minBeta, maxBeta, hPad, vPad, minScale, maxScale, showBeta)
    nodeDims.set(node.id, dims)
    nodeWidths.set(node.id, dims.width)
  }

  // Build tree structures
  const inputTree = buildTree(inputs, targetIds)
  const outputTree = buildTree(outputs, targetIds)

  // Calculate subtree widths for proper spacing (use tighter spacing for vertical)
  const inputSubtreeWidths: number[] = targets.map(t =>
    calculateSubtreeWidth(t.id, inputTree, nodeWidths, NODE_SPACING_VERTICAL, VERTICAL_MAX_NODES_PER_ROW)
  )
  const outputSubtreeWidths: number[] = targets.map(t =>
    calculateSubtreeWidth(t.id, outputTree, nodeWidths, NODE_SPACING_VERTICAL, VERTICAL_MAX_NODES_PER_ROW)
  )

  // Total width for input/output subtrees
  const totalInputWidth = inputSubtreeWidths.reduce((sum, w) => sum + w, 0) +
    (targets.length - 1) * NODE_SPACING_VERTICAL * 2
  const totalOutputWidth = outputSubtreeWidths.reduce((sum, w) => sum + w, 0) +
    (targets.length - 1) * NODE_SPACING_VERTICAL * 2

  // Position targets centered at Y=0, spread based on max subtree requirements
  const maxSubtreeWidth = Math.max(totalInputWidth, totalOutputWidth)

  // Position targets
  let targetX = -maxSubtreeWidth / 2
  for (let i = 0; i < targets.length; i++) {
    const target = targets[i]
    const dims = nodeDims.get(target.id) || { width: 100, height: 40 }
    const subtreeWidth = Math.max(inputSubtreeWidths[i], outputSubtreeWidths[i])
    const x = targetX + subtreeWidth / 2

    const positioned: PositionedLocalNode = {
      ...target,
      x,
      y: 0,
      width: dims.width,
      height: dims.height,
      layer: 'target',
      maxLabelChars: 999,
      betaDisplay: '',
      betaColor: '#666',
      fontSize: getFontSize(target.visualBeta, minBeta, maxBeta),
      edgeWidth: getEdgeWidth(target.visualBeta, minBeta, maxBeta),
      arrowScale: getArrowScale(target.visualBeta, minBeta, maxBeta)
    }
    positionedNodes.push(positioned)

    // Position input subtree (above target)
    positionTreeNodesVertical(
      target.id,
      x,
      -dims.height / 2,
      inputTree,
      positionedNodes,
      nodeDims,
      nodeWidths,
      minBeta,
      maxBeta,
      'input',
      NODE_SPACING_VERTICAL,
      rowGap,
      'up',
      VERTICAL_MAX_NODES_PER_ROW
    )

    // Position output subtree (below target)
    positionTreeNodesVertical(
      target.id,
      x,
      dims.height / 2,
      outputTree,
      positionedNodes,
      nodeDims,
      nodeWidths,
      minBeta,
      maxBeta,
      'output',
      NODE_SPACING_VERTICAL,
      rowGap,
      'down',
      VERTICAL_MAX_NODES_PER_ROW
    )

    targetX += subtreeWidth + NODE_SPACING_VERTICAL * 2
  }

  // Resolve any remaining horizontal overlaps
  resolveHorizontalOverlaps(positionedNodes)

  // Calculate bounds
  const bounds = calculateBounds(positionedNodes)

  return { nodes: positionedNodes, edges, bounds, flowDirection: 'vertical', minBeta, maxBeta }
}

/**
 * Detect and resolve horizontal overlaps between nodes
 * Groups nodes by similar Y positions and pushes overlapping nodes apart
 */
function resolveHorizontalOverlaps(
  nodes: PositionedLocalNode[],
  minGap: number = NODE_SPACING_VERTICAL
): void {
  if (nodes.length < 2) return

  // Group nodes by similar Y position (within threshold)
  const yThreshold = 5 // Nodes within 5px vertically are considered same row
  const rows: PositionedLocalNode[][] = []

  for (const node of nodes) {
    let foundRow = false
    for (const row of rows) {
      if (Math.abs(row[0].y - node.y) < yThreshold) {
        row.push(node)
        foundRow = true
        break
      }
    }
    if (!foundRow) {
      rows.push([node])
    }
  }

  // For each row, sort by X and resolve overlaps
  for (const row of rows) {
    if (row.length < 2) continue

    // Sort by X position
    row.sort((a, b) => a.x - b.x)

    // Check each pair and push apart if overlapping
    let iterations = 0
    const maxIterations = 10 // Prevent infinite loops

    while (iterations < maxIterations) {
      let hasOverlap = false

      for (let i = 0; i < row.length - 1; i++) {
        const left = row[i]
        const right = row[i + 1]

        const leftEdge = left.x + left.width / 2
        const rightEdge = right.x - right.width / 2
        const gap = rightEdge - leftEdge

        if (gap < minGap) {
          // Overlap detected - push nodes apart
          hasOverlap = true
          const overlap = minGap - gap
          const pushAmount = overlap / 2 + 1 // Split the push, add 1px buffer

          left.x -= pushAmount
          right.x += pushAmount
        }
      }

      if (!hasOverlap) break
      iterations++
    }
  }
}

/**
 * Calculate layout bounds
 */
function calculateBounds(nodes: PositionedLocalNode[]): {
  width: number
  height: number
  centerX: number
  centerY: number
} {
  if (nodes.length === 0) {
    return { width: 100, height: 100, centerX: 0, centerY: 0 }
  }

  let minX = Infinity, maxX = -Infinity
  let minY = Infinity, maxY = -Infinity

  for (const node of nodes) {
    minX = Math.min(minX, node.x - node.width / 2)
    maxX = Math.max(maxX, node.x + node.width / 2)
    minY = Math.min(minY, node.y - node.height / 2)
    maxY = Math.max(maxY, node.y + node.height / 2)
  }

  // Add padding for labels
  const padding = 40

  return {
    width: maxX - minX + padding * 2,
    height: maxY - minY + padding * 2,
    centerX: (minX + maxX) / 2,
    centerY: (minY + maxY) / 2
  }
}

/** Layout options for padding and sizing control */
export interface LayoutOptions {
  horizontalPadding: number  // Horizontal padding inside nodes (left/right of text)
  verticalPadding: number    // Vertical padding inside nodes (top/bottom of text)
  sizeMinScale: number       // Minimum size scale (0.3-1.0)
  sizeMaxScale: number       // Maximum size scale (1.0-2.5)
  declutterThreshold: number // Hide beta on depth>1 nodes when total nodes exceed this
  forceShowBeta?: boolean    // Force all non-target nodes to reserve space for second line
}

const DEFAULT_LAYOUT_OPTIONS: LayoutOptions = {
  horizontalPadding: 10,
  verticalPadding: 10,
  sizeMinScale: DEFAULT_SIZE_MIN_SCALE,
  sizeMaxScale: DEFAULT_SIZE_MAX_SCALE,
  declutterThreshold: 10     // Hide beta text on depth>1 when >10 nodes
}

/**
 * Main layout function - computes horizontal or vertical based on container
 */
/**
 * Determine if a node should show beta text based on declutter rules
 * @param isVertical - In vertical layout, always only show beta for depth 1
 */
function shouldShowBeta(node: LocalViewNode, totalNodes: number, declutterThreshold: number, isVertical: boolean = false, forceShowBeta: boolean = false): boolean {
  // Targets never show beta (they have no incoming edge)
  if (node.isTarget) return false
  // Force mode: all non-target nodes show beta (sim mode needs room for % text)
  if (forceShowBeta) return true
  // Vertical layout: always only show beta on immediate layers (depth 1)
  if (isVertical) return node.depth <= 1
  // Horizontal: If under threshold, show beta on all nodes
  if (totalNodes <= declutterThreshold) return true
  // When decluttering, only show beta on depth 1 (direct connections)
  return node.depth <= 1
}

export function computeLocalViewLayout(
  targets: LocalViewNode[],
  inputs: LocalViewNode[],
  outputs: LocalViewNode[],
  edges: LocalViewEdge[],
  containerWidth: number,
  containerHeight: number,
  options: Partial<LayoutOptions> = {}
): LocalViewLayoutResult {
  const opts = { ...DEFAULT_LAYOUT_OPTIONS, ...options }

  // Calculate min/max visualBeta for normalization using CHILDREN ONLY
  // This gives children the full size range (0.1x-1.8x) while targets stay at max
  // Including targets in normalization compresses children into a narrow range
  const childNodes = [...inputs, ...outputs]
  const childVisualBetas = childNodes.map(n => n.visualBeta)

  // Use children's range for normalization (targets get fixed max size via visualBeta=1.0)
  const minBeta = childVisualBetas.length > 0 ? Math.min(...childVisualBetas) : 0.01
  const maxBeta = childVisualBetas.length > 0 ? Math.max(...childVisualBetas, 0.1) : 1.0
  const direction = getFlowDirection(containerWidth, containerHeight)
  const isVertical = direction === 'vertical'

  // Calculate gap based on viewport size (responsive)
  const columnGap = Math.max(30, Math.min(80, containerWidth * 0.04))

  if (!isVertical) {
    return computeHorizontalLayout(targets, inputs, outputs, edges, minBeta, maxBeta, columnGap, opts.horizontalPadding, opts.verticalPadding, opts.sizeMinScale, opts.sizeMaxScale, opts.declutterThreshold, opts.forceShowBeta)
  } else {
    // Vertical layout uses tighter spacing and more aggressive decluttering
    const rowGap = Math.max(12, Math.min(30, containerHeight * 0.025))
    const verticalDeclutter = Math.min(opts.declutterThreshold, VERTICAL_DECLUTTER_THRESHOLD)
    return computeVerticalLayout(targets, inputs, outputs, edges, minBeta, maxBeta, rowGap, opts.horizontalPadding, opts.verticalPadding, opts.sizeMinScale, opts.sizeMaxScale, verticalDeclutter, opts.forceShowBeta)
  }
}

// ============================================
// Edge Path Functions
// ============================================

/**
 * Get edge connection point based on node shape and side
 * Returns the OUTER edge of the node outline (including border stroke)
 */
function getNodeEdgePoint(
  node: PositionedLocalNode,
  side: 'left' | 'right' | 'top' | 'bottom'
): { x: number; y: number } {
  const halfW = node.width / 2
  const halfH = node.height / 2
  // Border stroke width: 3px for targets, 2px for others
  // Stroke is centered on edge, so outer edge is +half stroke width
  const borderOffset = node.isTarget ? 1.5 : 1

  if (node.shape === 'hexagon') {
    // Hexagon connection points at widest parts (including border)
    switch (side) {
      case 'left': return { x: node.x - halfW - borderOffset, y: node.y }
      case 'right': return { x: node.x + halfW + borderOffset, y: node.y }
      case 'top': return { x: node.x, y: node.y - halfH - borderOffset }
      case 'bottom': return { x: node.x, y: node.y + halfH + borderOffset }
    }
  }

  // Pill and rectangle - straight edges (including border)
  switch (side) {
    case 'left': return { x: node.x - halfW - borderOffset, y: node.y }
    case 'right': return { x: node.x + halfW + borderOffset, y: node.y }
    case 'top': return { x: node.x, y: node.y - halfH - borderOffset }
    case 'bottom': return { x: node.x, y: node.y + halfH + borderOffset }
  }
}

/**
 * Calculate edge path between two nodes
 * @param arrowOffset - pixels to shorten the path at target end (for arrow marker)
 */
export function calculateEdgePath(
  sourceNode: PositionedLocalNode,
  targetNode: PositionedLocalNode,
  direction: FlowDirection,
  arrowOffset: number = 0
): string {
  if (direction === 'horizontal') {
    // Determine if target is left of source (e.g. sim mode negative effects)
    const targetIsLeft = targetNode.x < sourceNode.x
    const startSide = targetIsLeft ? 'left' : 'right'
    const endSide = targetIsLeft ? 'right' : 'left'
    const start = getNodeEdgePoint(sourceNode, startSide)
    const end = getNodeEdgePoint(targetNode, endSide)
    // Shorten path at target end to make room for arrow
    const arrowDir = targetIsLeft ? arrowOffset : -arrowOffset
    const adjustedEnd = { x: end.x + arrowDir, y: end.y }
    const midX = (start.x + adjustedEnd.x) / 2
    return `M ${start.x} ${start.y} C ${midX} ${start.y}, ${midX} ${adjustedEnd.y}, ${adjustedEnd.x} ${adjustedEnd.y}`
  } else {
    // Vertical: orthogonal paths with 90-degree turns (no arrows in vertical mode)
    const start = getNodeEdgePoint(sourceNode, 'bottom')
    const end = getNodeEdgePoint(targetNode, 'top')

    // Calculate midpoint Y for the horizontal segment
    const midY = (start.y + end.y) / 2

    // Orthogonal path: down from source, horizontal, then down to target
    // M start -> V midY -> H end.x -> V end.y
    return `M ${start.x} ${start.y} L ${start.x} ${midY} L ${end.x} ${midY} L ${end.x} ${end.y}`
  }
}

/**
 * Get edge styling based on visualBeta (for width) and original beta (for color)
 * @param visualBeta - Target node's propagated beta (for stroke width)
 * @param minVisualBeta - Min visualBeta for normalization
 * @param maxVisualBeta - Max visualBeta for normalization
 * @param originalBeta - Original edge beta (for color: positive=green, negative=red)
 */
export function getEdgeStyle(
  visualBeta: number,
  minVisualBeta: number,
  maxVisualBeta: number,
  originalBeta: number = 1
): {
  strokeWidth: number
  stroke: string
  opacity: number
} {
  return {
    strokeWidth: getEdgeWidth(visualBeta, minVisualBeta, maxVisualBeta),
    stroke: originalBeta >= 0 ? '#4CAF50' : '#F44336', // Green / Red based on original
    opacity: 0.7
  }
}

/**
 * Calculate initial transform to fit layout in viewport
 */
export function calculateFitTransform(
  bounds: LocalViewLayoutResult['bounds'],
  containerWidth: number,
  containerHeight: number,
  padding: number = 60
): { x: number; y: number; scale: number } {
  const availableWidth = containerWidth - padding * 2
  const availableHeight = containerHeight - padding * 2

  const scaleX = availableWidth / Math.max(bounds.width, 1)
  const scaleY = availableHeight / Math.max(bounds.height, 1)
  const scale = Math.min(scaleX, scaleY, 2.5) // Cap at 2.5x

  const x = containerWidth / 2 - bounds.centerX * scale
  const y = containerHeight / 2 - bounds.centerY * scale

  return { x, y, scale }
}

// ============================================
// Legacy Exports (for compatibility)
// ============================================

export function getTargetNodeRadius(importance: number): number {
  return 25 + importance * 15
}

export function getBetaNodeRadius(beta: number, minBeta: number, maxBeta: number, centerRadius: number): number {
  const scale = getNodeSizeScale(beta, minBeta, maxBeta)
  return centerRadius * scale
}

export const getLocalNodeRadius = getTargetNodeRadius
export function getLocalNodeRadiusFromBeta(beta: number, minBeta: number, maxBeta: number): number {
  return getBetaNodeRadius(beta, minBeta, maxBeta, 25)
}

export function truncateLabel(label: string, maxWidth: number): string {
  const maxChars = Math.floor(maxWidth / LABEL_CHAR_WIDTH)
  if (label.length <= maxChars) return label
  return label.substring(0, maxChars - 1) + '…'
}
