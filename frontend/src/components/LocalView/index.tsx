/**
 * LocalView - Horizontal Flow Chart Visualization
 *
 * Shows causal relationships as a flow chart:
 *   Causes (pills) → Target (rectangle) → Effects (hexagons)
 *
 * Automatically switches to vertical layout for narrow containers.
 */

import { useEffect, useRef, useState, useMemo, useCallback } from 'react'
import * as d3 from 'd3'
import type { RawNodeV21, RawEdge } from '../../types'
import {
  buildLocalViewData,
  getLocalViewStats,
  getCausalEdges
} from '../../utils/causalEdges'
import {
  computeLocalViewLayout,
  calculateEdgePath,
  getEdgeStyle,
  calculateFitTransform,
  ARROW_BASE_SIZE,
  type PositionedLocalNode
} from '../../layouts/LocalViewLayout'

// ============================================
// Animation Constants (matching Global View)
// ============================================
const ANIMATION = {
  NODE_ENTER_DURATION: 300,   // Nodes appearing: scale 0→1, opacity 0→1
  NODE_EXIT_DURATION: 200,    // Nodes disappearing: scale 1→0, opacity 1→0
  POSITION_DURATION: 300,     // Position/size changes
  TEXT_FADE_DURATION: 150,    // Text fade in/out
  EDGE_DURATION: 200,         // Edges extending (shorter, starts after node moves)
  EDGE_ENTER_DELAY: 200,      // Wait for node to move past parent before showing edge
  VIEWPORT_DURATION: 400,     // Viewport pan/zoom animation
  EASING: d3.easeCubicOut,
  EXIT_EASING: d3.easeCubicIn
}

// ============================================
// Helper Functions
// ============================================

/**
 * Create a muted (lighter, pastel) version of a color
 */
function getMutedColor(hexColor: string, lightness: number = 0.85): string {
  const hex = hexColor.replace('#', '')
  const r = parseInt(hex.substr(0, 2), 16)
  const g = parseInt(hex.substr(2, 2), 16)
  const b = parseInt(hex.substr(4, 2), 16)

  // Blend with white to create muted version
  const mutedR = Math.round(r + (255 - r) * lightness)
  const mutedG = Math.round(g + (255 - g) * lightness)
  const mutedB = Math.round(b + (255 - b) * lightness)

  return `rgb(${mutedR}, ${mutedG}, ${mutedB})`
}

/**
 * Get contrasting text color for a background color
 */
function getContrastColor(_hexColor: string): string {
  // With muted backgrounds, dark text always works best
  return '#333333'
}

/**
 * Truncate label to fit within max chars
 */
function truncateLabel(label: string, maxChars: number): string {
  if (label.length <= maxChars) return label
  return label.substring(0, maxChars - 1) + '…'
}

// ============================================
// Shape Rendering Functions
// ============================================

/**
 * Render node based on shape type
 * If prevDims is provided, animate from old dimensions to new
 */
function renderNodeShape(
  group: d3.Selection<SVGGElement, unknown, null, undefined>,
  node: PositionedLocalNode,
  prevDims?: { width: number; height: number },
  simBorder?: { color: string; width: number } | null
): void {
  // Use previous dimensions for initial render if animating
  const startWidth = prevDims?.width ?? node.width
  const startHeight = prevDims?.height ?? node.height

  // Apply common styling
  const canExpand = node.isTarget || node.canExpand !== false
  const fillLightness = canExpand ? 0.75 : 0.90
  const fill = getMutedColor(node.sectorColor, fillLightness)
  const stroke = simBorder ? simBorder.color : node.sectorColor
  const strokeWidth = simBorder ? simBorder.width : (node.isTarget ? 3 : 2)

  if (node.shape === 'hexagon') {
    // Octagon shape
    const getOctagonPoints = (w: number, h: number) => {
      const cut = h * 0.22
      return [
        `${-w/2 + cut},${-h/2}`,
        `${w/2 - cut},${-h/2}`,
        `${w/2},${-h/2 + cut}`,
        `${w/2},${h/2 - cut}`,
        `${w/2 - cut},${h/2}`,
        `${-w/2 + cut},${h/2}`,
        `${-w/2},${h/2 - cut}`,
        `${-w/2},${-h/2 + cut}`
      ].join(' ')
    }

    const polygon = group.append('polygon')
      .attr('points', getOctagonPoints(startWidth, startHeight))
      .attr('fill', fill)
      .attr('stroke', stroke)
      .attr('stroke-width', strokeWidth)
      .attr('class', 'node-shape')

    if (prevDims) {
      polygon.transition()
        .duration(300)
        .ease(d3.easeCubicOut)
        .attr('points', getOctagonPoints(node.width, node.height))
    }
  } else {
    // Pill or rectangle shape
    const rx = node.shape === 'pill' ? startHeight / 2 : 6
    const ry = node.shape === 'pill' ? startHeight / 2 : 6
    const finalRx = node.shape === 'pill' ? node.height / 2 : 6
    const finalRy = node.shape === 'pill' ? node.height / 2 : 6

    const rect = group.append('rect')
      .attr('x', -startWidth / 2)
      .attr('y', -startHeight / 2)
      .attr('width', startWidth)
      .attr('height', startHeight)
      .attr('rx', rx)
      .attr('ry', ry)
      .attr('fill', fill)
      .attr('stroke', stroke)
      .attr('stroke-width', strokeWidth)
      .attr('class', 'node-shape')

    if (prevDims) {
      rect.transition()
        .duration(300)
        .ease(d3.easeCubicOut)
        .attr('x', -node.width / 2)
        .attr('y', -node.height / 2)
        .attr('width', node.width)
        .attr('height', node.height)
        .attr('rx', finalRx)
        .attr('ry', finalRy)
    }
  }
}

// ============================================
// Component Props
// ============================================

/** CI data for a node (uncertainty metrics) */
interface NodeCIData {
  mean: number
  std: number
  ci_lower: number
  ci_upper: number
  n_children?: number  // For aggregated nodes
  child_coverage?: number  // Fraction of children with data
}

/** Pre-built simulation data for Local View (bypasses structural edge traversal) */
interface SimLocalViewData {
  targets: import('../../types').LocalViewNode[]
  inputs: import('../../types').LocalViewNode[]
  outputs: import('../../types').LocalViewNode[]
  edges: import('../../types').LocalViewEdge[]
  targetRing: number
  mode: import('../../types').LocalViewMode
  activeChildCount?: number
  totalChildCount?: number
}

interface LocalViewProps {
  targetIds: string[]
  allEdges: RawEdge[]
  nodeById: Map<string, RawNodeV21>
  domainColors: Record<string, string>
  onRemoveTarget: (nodeId: string) => void
  onClearTargets: () => void
  onSwitchToGlobal: () => void
  onNavigateToNode?: (nodeId: string) => void
  onShowInGlobal?: (nodeId: string) => void  // Show node in Global View with path expanded
  onDrillDown?: (nodeId: string) => void     // Drill down: swap target for its children
  onDrillUp?: () => void                      // Go back to previous targets
  canDrillUp?: boolean                        // Can undo last drill-down
  showGlow?: boolean
  betaThreshold: number  // Controlled from parent
  onBetaThresholdChange: (threshold: number) => void
  inputDepth: number
  outputDepth: number
  onInputDepthChange?: (depth: number) => void  // Unused - layer controls use per-node expansion
  onOutputDepthChange?: (depth: number) => void  // Unused - layer controls use per-node expansion
  onResetLocalView?: (resetFn: () => void) => void  // Callback to register reset function
  ciCache?: Map<string, NodeCIData>  // CI data for nodes (from precomputedCICache)
  currentYear?: number  // Current timeline year for display
  // Simulation mode props
  simMode?: boolean                    // True when simulation results drive the view
  simPlaybackActive?: boolean          // True when timeline is playing (fill mode)
  simEffects?: Map<string, number>     // nodeId → percent_change for current year
  simData?: SimLocalViewData | null    // Pre-built sim data (bypasses structural traversal)
}

// ============================================
// Main Component
// ============================================

export function LocalView({
  targetIds,
  allEdges,
  nodeById,
  domainColors,
  onRemoveTarget,
  onClearTargets,
  onSwitchToGlobal,
  onNavigateToNode,
  onShowInGlobal,
  onDrillDown,
  onDrillUp,
  canDrillUp = false,
  showGlow = false,
  betaThreshold,
  onBetaThresholdChange,
  inputDepth,
  outputDepth,
  onResetLocalView,
  ciCache,
  currentYear,
  simMode = false,
  simPlaybackActive = false,
  simEffects,
  simData
}: LocalViewProps) {
  const svgRef = useRef<SVGSVGElement>(null)
  const containerRef = useRef<HTMLDivElement>(null)
  const zoomRef = useRef<d3.ZoomBehavior<SVGSVGElement, unknown> | null>(null)
  const currentTransformRef = useRef<d3.ZoomTransform | null>(null)
  const prevTargetIdsRef = useRef<string[]>([])
  const prevDimensionsRef = useRef<{ width: number; height: number } | null>(null)
  const prevTargetIdsForThresholdRef = useRef<string[]>([])
  const prevBetaThresholdRef = useRef<number>(betaThreshold)
  const prevLayoutRef = useRef<Map<string, { x: number; y: number; parentId?: string }>>(new Map())
  const prevNodeDimsRef = useRef<Map<string, { width: number; height: number }>>(new Map())
  const prevFlowDirectionRef = useRef<'horizontal' | 'vertical' | null>(null)
  const isFirstRenderRef = useRef(true)
  const shouldAnimateViewportRef = useRef(false)  // Flag to trigger viewport animation after expand/collapse
  const prevSimNodeCountRef = useRef(0)  // Track node count for auto-zoom on sim expansion
  const [dimensions, setDimensions] = useState({ width: 800, height: 600 })
  const [hoveredNode, setHoveredNode] = useState<PositionedLocalNode | null>(null)
  const [hoveredEdge, setHoveredEdge] = useState<{ source: string; target: string; beta: number } | null>(null)
  const isHoveringTooltipRef = useRef(false)  // Track if mouse is over tooltip
  const tooltipTimeoutRef = useRef<number | null>(null)  // Delay before hiding tooltip

  // Per-node expansion state (for adding more causal layers)
  const [expandedInputNodes, setExpandedInputNodes] = useState<Set<string>>(new Set())
  const [expandedOutputNodes, setExpandedOutputNodes] = useState<Set<string>>(new Set())

  // Layout constants
  const horizontalPadding = 16  // Extra padding for wide characters (W, M, etc.)
  const verticalPadding = 16
  const sizeMinScale = 0.5
  const sizeMaxScale = 1.5

  // Toggle expand for a node's causes
  const toggleInputExpand = useCallback((nodeId: string) => {
    shouldAnimateViewportRef.current = true
    setExpandedInputNodes(prev => {
      const next = new Set(prev)
      if (next.has(nodeId)) {
        next.delete(nodeId)
      } else {
        next.add(nodeId)
      }
      return next
    })
  }, [])

  // Toggle expand for a node's effects
  const toggleOutputExpand = useCallback((nodeId: string) => {
    shouldAnimateViewportRef.current = true
    setExpandedOutputNodes(prev => {
      const next = new Set(prev)
      if (next.has(nodeId)) {
        next.delete(nodeId)
      } else {
        next.add(nodeId)
      }
      return next
    })
  }, [])

  // Reset expansion when targets change
  useEffect(() => {
    setExpandedInputNodes(new Set())
    setExpandedOutputNodes(new Set())
  }, [targetIds])


  const TARGET_NODE_COUNT = 6

  // Calculate beta range from relevant edges for smart slider bounds
  const betaRange = useMemo(() => {
    if (targetIds.length === 0) {
      return { min: 0, max: 2, step: 0.1, relevantBetas: [] as number[] }
    }

    const causalEdges = getCausalEdges(allEdges)
    const relevantBetas: number[] = []

    // Collect all betas for edges connected to targets
    for (const targetId of targetIds) {
      causalEdges
        .filter(e => e.target === targetId)
        .forEach(e => relevantBetas.push(Math.abs(e.beta)))
      causalEdges
        .filter(e => e.source === targetId)
        .forEach(e => relevantBetas.push(Math.abs(e.beta)))
    }

    if (relevantBetas.length === 0) {
      return { min: 0, max: 2, step: 0.1, relevantBetas: [] }
    }

    relevantBetas.sort((a, b) => a - b)
    const minBeta = relevantBetas[0]
    const maxBeta = relevantBetas[relevantBetas.length - 1]
    const range = maxBeta - minBeta

    // Smart step: ~20 steps across the range, rounded to nice values
    let step: number
    if (range < 0.5) step = 0.01
    else if (range < 2) step = 0.05
    else if (range < 5) step = 0.1
    else step = 0.25

    return {
      min: Math.floor(minBeta * 10) / 10,  // Round down to 0.1
      max: Math.ceil(maxBeta * 10) / 10,   // Round up to 0.1
      step,
      relevantBetas
    }
  }, [targetIds, allEdges])

  // State for slider bounds (can be expanded with +/- buttons)
  const [sliderMin, setSliderMin] = useState(0)
  const [sliderMax, setSliderMax] = useState(2)

  // Update slider bounds when beta range changes
  useEffect(() => {
    setSliderMin(betaRange.min)
    setSliderMax(Math.max(betaRange.max, 1)) // At least 1
  }, [betaRange.min, betaRange.max])

  // Calculate optimal beta threshold
  const calculateOptimalThreshold = useMemo(() => {
    if (targetIds.length === 0) return 0.5

    const { relevantBetas } = betaRange
    if (relevantBetas.length === 0) return 0.5

    // Sort descending for threshold calculation
    const sorted = [...relevantBetas].sort((a, b) => b - a)
    const targetIndex = Math.min(TARGET_NODE_COUNT, sorted.length) - 1
    const optimalThreshold = sorted[targetIndex] * 0.99

    return Math.max(0.1, Math.min(optimalThreshold, sliderMax))
  }, [betaRange, sliderMax, targetIds.length])

  // Only auto-calculate threshold when targets actually change (not on every remount)
  useEffect(() => {
    const prevTargets = prevTargetIdsForThresholdRef.current
    const targetsChanged = JSON.stringify(targetIds) !== JSON.stringify(prevTargets)

    if (targetsChanged && targetIds.length > 0) {
      onBetaThresholdChange(calculateOptimalThreshold)
      prevTargetIdsForThresholdRef.current = [...targetIds]
    }
  }, [targetIds, calculateOptimalThreshold, onBetaThresholdChange])

  // Measure container
  useEffect(() => {
    if (!containerRef.current) return

    const updateDimensions = () => {
      if (containerRef.current) {
        const rect = containerRef.current.getBoundingClientRect()
        if (rect.width > 0 && rect.height > 0) {
          setDimensions({ width: rect.width, height: rect.height })
        }
      }
    }

    const resizeObserver = new ResizeObserver(updateDimensions)
    resizeObserver.observe(containerRef.current)
    updateDimensions()
    window.addEventListener('resize', updateDimensions)

    return () => {
      resizeObserver.disconnect()
      window.removeEventListener('resize', updateDimensions)
    }
  }, [])

  // Build Local View data — use pre-built simData when in simulation mode
  const localViewData = useMemo(() => {
    if (simData) return simData  // Simulation mode: use pre-built data
    if (targetIds.length === 0) return null
    return buildLocalViewData(
      targetIds,
      allEdges,
      nodeById,
      domainColors,
      betaThreshold,
      expandedInputNodes,
      expandedOutputNodes,
      inputDepth,
      outputDepth
    )
  }, [simData, targetIds, allEdges, nodeById, domainColors, betaThreshold, expandedInputNodes, expandedOutputNodes, inputDepth, outputDepth])

  // Compute layout
  const layout = useMemo(() => {
    if (!localViewData) return null
    return computeLocalViewLayout(
      localViewData.targets,
      localViewData.inputs,
      localViewData.outputs,
      localViewData.edges,
      dimensions.width,
      dimensions.height,
      { horizontalPadding, verticalPadding, sizeMinScale, sizeMaxScale, forceShowBeta: simMode }
    )
  }, [localViewData, dimensions, horizontalPadding, verticalPadding, sizeMinScale, sizeMaxScale, simMode])

  // Get stats
  const stats = useMemo(() => {
    if (!localViewData) return null
    return getLocalViewStats(localViewData)
  }, [localViewData])

  // Expand all visible input nodes that can expand (like Global View's expandRing)
  const expandInputLayer = useCallback(() => {
    if (!localViewData) return
    shouldAnimateViewportRef.current = true

    // Find all input nodes that have unexpanded causes
    const nodesToExpand = localViewData.inputs.filter(n => n.hasMoreInputs)
    // Also check targets that have unexpanded inputs
    const targetsToExpand = localViewData.targets.filter(n => n.hasMoreInputs)

    setExpandedInputNodes(prev => {
      const next = new Set(prev)
      nodesToExpand.forEach(n => next.add(n.id))
      targetsToExpand.forEach(n => next.add(n.id))
      return next
    })
  }, [localViewData])

  // Collapse outermost input layer (like Global View's collapseRing)
  const collapseInputLayer = useCallback(() => {
    if (!localViewData) return
    shouldAnimateViewportRef.current = true

    // Find the max depth among visible inputs
    const maxDepth = Math.max(...localViewData.inputs.map(n => n.depth), 0)
    if (maxDepth <= 1) {
      // At minimum depth, collapse all individual expansions
      setExpandedInputNodes(new Set())
      return
    }

    // Find nodes at max depth (leaves) and their parents
    const leafNodes = localViewData.inputs.filter(n => n.depth === maxDepth)
    const parentIds = new Set(leafNodes.map(n => n.parentId).filter(Boolean) as string[])

    setExpandedInputNodes(prev => {
      const next = new Set(prev)
      // Remove parents of leaves from expanded set
      parentIds.forEach(id => next.delete(id))
      return next
    })
  }, [localViewData])

  // Expand all visible output nodes that can expand
  const expandOutputLayer = useCallback(() => {
    if (!localViewData) return
    shouldAnimateViewportRef.current = true

    // Find all output nodes that have unexpanded effects
    const nodesToExpand = localViewData.outputs.filter(n => n.hasMoreOutputs)
    // Also check targets that have unexpanded outputs
    const targetsToExpand = localViewData.targets.filter(n => n.hasMoreOutputs)

    setExpandedOutputNodes(prev => {
      const next = new Set(prev)
      nodesToExpand.forEach(n => next.add(n.id))
      targetsToExpand.forEach(n => next.add(n.id))
      return next
    })
  }, [localViewData])

  // Collapse outermost output layer
  const collapseOutputLayer = useCallback(() => {
    if (!localViewData) return
    shouldAnimateViewportRef.current = true

    // Find the max depth among visible outputs
    const maxDepth = Math.max(...localViewData.outputs.map(n => n.depth), 0)
    if (maxDepth <= 1) {
      // At minimum depth, collapse all individual expansions
      setExpandedOutputNodes(new Set())
      return
    }

    // Find nodes at max depth (leaves) and their parents
    const leafNodes = localViewData.outputs.filter(n => n.depth === maxDepth)
    const parentIds = new Set(leafNodes.map(n => n.parentId).filter(Boolean) as string[])

    setExpandedOutputNodes(prev => {
      const next = new Set(prev)
      // Remove parents of leaves from expanded set
      parentIds.forEach(id => next.delete(id))
      return next
    })
  }, [localViewData])

  // Reset function: collapse all expansions and fit viewport
  const resetLocalView = useCallback(() => {
    if (!svgRef.current || !zoomRef.current || !layout) return

    // Reset all expanded nodes
    setExpandedInputNodes(new Set())
    setExpandedOutputNodes(new Set())

    // Animate viewport to fit - will happen on next render via shouldAnimateViewportRef
    shouldAnimateViewportRef.current = true
  }, [layout])

  // Register reset function with parent
  useEffect(() => {
    if (onResetLocalView) {
      onResetLocalView(resetLocalView)
    }
  }, [onResetLocalView, resetLocalView])

  // Keyboard shortcuts: W = Show in Global, D = Drill Down, E = Expand
  useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
      if (e.target instanceof HTMLInputElement || e.target instanceof HTMLTextAreaElement) return

      if (e.key === 'w' || e.key === 'W') {
        if (hoveredNode && !hoveredNode.isTarget && onShowInGlobal) {
          e.preventDefault()
          onShowInGlobal(hoveredNode.id)
        }
      }

      // 'd' for drill-down (destructive - replaces targets with hierarchical children)
      if (e.key === 'd' || e.key === 'D') {
        // If can drill up, pressing D goes back
        if (canDrillUp && onDrillUp) {
          e.preventDefault()
          onDrillUp()
          return
        }
        // Otherwise, drill down if possible
        if (hoveredNode && onDrillDown) {
          const canDrill = hoveredNode.hasChildren && hoveredNode.ring < 5
          if (canDrill) {
            e.preventDefault()
            onDrillDown(hoveredNode.id)
          }
        }
      }
    }

    window.addEventListener('keydown', handleKeyDown)
    return () => window.removeEventListener('keydown', handleKeyDown)
  }, [hoveredNode, onShowInGlobal, onDrillDown, onDrillUp, canDrillUp])

  // Helper to handle delayed tooltip hiding
  const handleNodeMouseLeave = useCallback(() => {
    // Clear any existing timeout
    if (tooltipTimeoutRef.current) {
      clearTimeout(tooltipTimeoutRef.current)
    }
    // Delay hiding to allow mouse to reach tooltip
    tooltipTimeoutRef.current = window.setTimeout(() => {
      if (!isHoveringTooltipRef.current) {
        setHoveredNode(null)
      }
    }, 150)
  }, [])

  // Render SVG with animations
  useEffect(() => {
    if (!svgRef.current || !layout) return

    const svg = d3.select(svgRef.current)
    const isFirstRender = isFirstRenderRef.current
    isFirstRenderRef.current = false

    // Check if targets changed
    const targetsChanged = JSON.stringify(targetIds) !== JSON.stringify(prevTargetIdsRef.current)
    prevTargetIdsRef.current = [...targetIds]

    // Check if beta threshold changed significantly (causes edge filtering changes)
    const betaChanged = Math.abs(betaThreshold - prevBetaThresholdRef.current) > 0.01
    prevBetaThresholdRef.current = betaThreshold

    // Check if dimensions changed significantly
    const prevDims = prevDimensionsRef.current
    let dimensionsChanged = prevDims === null
    if (prevDims) {
      const widthChange = Math.abs(dimensions.width - prevDims.width) / Math.max(prevDims.width, 1)
      const heightChange = Math.abs(dimensions.height - prevDims.height) / Math.max(prevDims.height, 1)
      dimensionsChanged = widthChange > 0.05 || heightChange > 0.05
    }
    prevDimensionsRef.current = { ...dimensions }

    // Check if flow direction changed (horizontal <-> vertical)
    const flowDirectionChanged = prevFlowDirectionRef.current !== null &&
      prevFlowDirectionRef.current !== layout.flowDirection
    prevFlowDirectionRef.current = layout.flowDirection

    // Auto-zoom when sim node count changes (new effects appearing during playback)
    const currentNodeCount = layout.nodes.length
    const simNodeCountChanged = simMode && currentNodeCount !== prevSimNodeCountRef.current
    if (simNodeCountChanged) {
      shouldAnimateViewportRef.current = true
    }
    prevSimNodeCountRef.current = currentNodeCount

    // Should we animate? (not on first render, not on structural changes)
    // When targets/beta change, the graph structure changes fundamentally - don't animate
    // When flow direction changes, we need a clean reset - don't animate
    const shouldAnimate = !isFirstRender && !dimensionsChanged && !targetsChanged && !betaChanged && !flowDirectionChanged

    // Create node lookup
    const nodePositions = new Map<string, PositionedLocalNode>()
    layout.nodes.forEach(n => nodePositions.set(n.id, n))

    // Get or create persistent groups
    let defs = svg.select<SVGDefsElement>('defs')
    if (defs.empty()) {
      defs = svg.append('defs')
    }

    let g = svg.select<SVGGElement>('g.local-view-content')
    if (g.empty()) {
      g = svg.append('g').attr('class', 'local-view-content')
    }

    // Set up zoom behavior (once)
    if (!zoomRef.current) {
      const zoom = d3.zoom<SVGSVGElement, unknown>()
        .scaleExtent([0.3, 3])
        .on('zoom', (event) => {
          currentTransformRef.current = event.transform
          svg.select('g.local-view-content').attr('transform', event.transform.toString())
        })

      zoomRef.current = zoom
      svg.call(zoom)
        .on('dblclick.zoom', null)  // Disable default double-click zoom
    }

    // Add double-click on empty space to fit all nodes
    svg.on('dblclick', (event) => {
      // Only trigger if clicking on SVG background (not on a node)
      const target = event.target as Element
      if (target.tagName === 'svg' || target.classList.contains('local-view-content')) {
        event.preventDefault()
        // Fit all nodes in view
        const fitTransformNow = calculateFitTransform(layout.bounds, dimensions.width, dimensions.height, 80)
        const resetTransform = d3.zoomIdentity
          .translate(fitTransformNow.x, fitTransformNow.y)
          .scale(fitTransformNow.scale)
        currentTransformRef.current = resetTransform
        svg.transition()
          .duration(ANIMATION.VIEWPORT_DURATION)
          .ease(ANIMATION.EASING)
          .call(zoomRef.current!.transform, resetTransform)
      }
    })

    // Calculate fit transform
    const fitTransform = calculateFitTransform(
      layout.bounds,
      dimensions.width,
      dimensions.height,
      80
    )
    const targetTransform = d3.zoomIdentity
      .translate(fitTransform.x, fitTransform.y)
      .scale(fitTransform.scale)

    // Check if viewport animation was requested (from expand/collapse or depth change)
    const shouldAnimateViewport = shouldAnimateViewportRef.current
    shouldAnimateViewportRef.current = false  // Reset flag

    // Set transform
    if (targetsChanged || dimensionsChanged || !currentTransformRef.current) {
      currentTransformRef.current = targetTransform
      if (dimensionsChanged && !targetsChanged) {
        svg.transition().duration(200).call(zoomRef.current!.transform, targetTransform)
      } else {
        svg.call(zoomRef.current!.transform, targetTransform)
      }
    } else if (shouldAnimateViewport) {
      // Animate viewport to fit new layout after expand/collapse
      currentTransformRef.current = targetTransform
      svg.transition()
        .duration(ANIMATION.VIEWPORT_DURATION)
        .ease(ANIMATION.EASING)
        .call(zoomRef.current!.transform, targetTransform)
    } else {
      g.attr('transform', currentTransformRef.current.toString())
    }

    // Get or create edge/node groups
    let edgesGroup = g.select<SVGGElement>('g.edges')
    if (edgesGroup.empty()) {
      edgesGroup = g.append('g').attr('class', 'edges')
    }

    let nodesGroup = g.select<SVGGElement>('g.nodes')
    if (nodesGroup.empty()) {
      nodesGroup = g.append('g').attr('class', 'nodes')
    }

    // If not animating (targets/dimensions changed), interrupt all ongoing transitions
    // This prevents stale animations from interfering with the new state
    if (!shouldAnimate) {
      edgesGroup.selectAll('*').interrupt()
      nodesGroup.selectAll('*').interrupt()
    }

    // When flow direction changes, do a full clear to prevent rendering artifacts
    // This handles switching between horizontal (split) and vertical (local) layouts
    if (flowDirectionChanged) {
      edgesGroup.selectAll('*').remove()
      nodesGroup.selectAll('*').remove()
      prevLayoutRef.current = new Map()
    }

    // Use layout-computed min/max visualBeta
    const { minBeta, maxBeta: maxVisualBeta } = layout
    const isVertical = layout.flowDirection === 'vertical'

    // === UPDATE ARROW MARKERS ===
    // Only create arrow markers for horizontal layout (not sim mode or vertical)
    defs.selectAll('*').remove()
    const showArrows = !isVertical && !simMode
    if (showArrows) {
      for (const edge of layout.edges) {
        const sourceNode = nodePositions.get(edge.source)
        const arrowScale = sourceNode?.arrowScale ?? 1.0
        const arrowSize = ARROW_BASE_SIZE * arrowScale
        const isPositive = edge.beta >= 0
        const color = isPositive ? '#4CAF50' : '#F44336'
        const markerId = `arrow-${edge.source}-${edge.target}`

        defs.append('marker')
          .attr('id', markerId)
          .attr('viewBox', '0 0 10 10')
          .attr('refX', 6)
          .attr('refY', 5)
          .attr('markerWidth', arrowSize)
          .attr('markerHeight', arrowSize)
          .attr('orient', 'auto')
          .append('path')
          .attr('d', 'M 0 0 L 10 5 L 0 10 z')
          .attr('fill', color)
      }
    }

    // === ANIMATE EDGES ===
    // Create edge data with unique keys
    const edgeData = layout.edges.map((edge, i) => ({
      ...edge,
      key: `${edge.source}-${edge.target}`,
      index: i,
      sourceNode: nodePositions.get(edge.source),
      targetNode: nodePositions.get(edge.target)
    })).filter(e => e.sourceNode && e.targetNode)

    const edgeSelection = edgesGroup
      .selectAll<SVGPathElement, typeof edgeData[0]>('path.edge')
      .data(edgeData, d => d.key)

    // EXIT edges
    edgeSelection.exit()
      .classed('edge-exiting', true)
      .transition('edge-exit')
      .duration(shouldAnimate ? ANIMATION.NODE_EXIT_DURATION : 0)
      .ease(ANIMATION.EXIT_EASING)
      .style('stroke-opacity', 0)
      .remove()

    // ENTER edges
    const enterEdges = edgeSelection.enter()
      .append('path')
      .attr('class', 'edge')
      .attr('fill', 'none')
      .attr('data-source', d => d.source)
      .attr('data-target', d => d.target)
      .attr('data-beta', d => d.beta)
      .style('cursor', 'pointer')

    // Track which edges are entering
    const enteringEdgeKeys = new Set(enterEdges.data().map(d => d.key))

    // Merge enter + update for shared attributes
    const allEdges = enterEdges.merge(edgeSelection)

    // Apply styles to all edges
    allEdges.each(function(d) {
      const edgeVisualBeta = d.targetNode!.isTarget ? d.sourceNode!.visualBeta : d.targetNode!.visualBeta
      const style = getEdgeStyle(edgeVisualBeta, minBeta, maxVisualBeta, d.beta)
      const el = d3.select(this)

      el.attr('stroke', style.stroke)
        .attr('stroke-width', style.strokeWidth)

      // Store style and calculated path for later use
      const arrowScale = d.sourceNode!.arrowScale ?? 1.0
      const arrowSize = ARROW_BASE_SIZE * arrowScale
      const finalPath = calculateEdgePath(d.sourceNode!, d.targetNode!, layout.flowDirection, arrowSize)

      el.datum({ ...d, style, finalPath, arrowSize })
    })

    // Handle animations differently for entering vs updating edges
    if (shouldAnimate) {
      allEdges.each(function(d) {
        const el = d3.select(this)
        const datum = el.datum() as typeof d & { style: ReturnType<typeof getEdgeStyle>; finalPath: string }
        const isEntering = enteringEdgeKeys.has(d.key)

        const markerId = `arrow-${d.source}-${d.target}`
        if (isEntering) {
          // Entering edges: set final path immediately, fade in after delay
          el.attr('d', datum.finalPath)
            .attr('marker-end', null)  // Hide arrow initially
            .style('stroke-opacity', 0)
            .transition('edge-fade-in')
            .delay(ANIMATION.EDGE_ENTER_DELAY)
            .duration(ANIMATION.EDGE_DURATION)
            .ease(ANIMATION.EASING)
            .style('stroke-opacity', 0.7)
            .on('end', function() {
              // Add arrow after edge fade-in completes (only in horizontal mode)
              if (showArrows) {
                d3.select(this).attr('marker-end', `url(#${markerId})`)
              }
            })
        } else {
          // Existing edges: animate path to follow moving nodes
          el.attr('marker-end', showArrows ? `url(#${markerId})` : null)
            .transition('edge-update')
            .duration(ANIMATION.POSITION_DURATION)
            .ease(ANIMATION.EASING)
            .attr('d', datum.finalPath)
        }
      })
    } else {
      // No animation: set everything immediately
      allEdges.each(function(d) {
        const el = d3.select(this)
        const datum = el.datum() as typeof d & { finalPath: string }
        const markerId = `arrow-${d.source}-${d.target}`
        el.attr('d', datum.finalPath)
          .attr('marker-end', showArrows ? `url(#${markerId})` : null)
          .style('stroke-opacity', 0.7)
      })
    }

    // Re-apply hover handlers
    allEdges
      .on('mouseenter', function(_event, d) {
        const datum = d3.select(this).datum() as typeof d & { style: ReturnType<typeof getEdgeStyle> }
        d3.select(this)
          .attr('stroke-opacity', 1)
          .attr('stroke-width', datum.style.strokeWidth + 2)
        setHoveredEdge({ source: d.source, target: d.target, beta: d.beta })
      })
      .on('mouseleave', function(_event, _d) {
        const datum = d3.select(this).datum() as typeof _d & { style: ReturnType<typeof getEdgeStyle> }
        d3.select(this)
          .attr('stroke-opacity', datum.style.opacity)
          .attr('stroke-width', datum.style.strokeWidth)
        setHoveredEdge(null)
      })

    // === ANIMATE NODES ===
    const MAX_NODES_FOR_FULL_BETA = 10
    const totalNodes = layout.nodes.length
    // In vertical layout, always declutter (only show beta on depth 1)
    const shouldDeclutter = isVertical || totalNodes > MAX_NODES_FOR_FULL_BETA

    const nodeSelection = nodesGroup
      .selectAll<SVGGElement, PositionedLocalNode>('g.node')
      .data(layout.nodes, d => d.id)

    // Get previous positions for exit animation
    const prevLayout = prevLayoutRef.current

    // EXIT nodes
    nodeSelection.exit()
      .each(function() {
        const el = d3.select(this)
        const nodeId = el.attr('data-id')
        const prevPos = prevLayout.get(nodeId)
        const parentPos = prevPos?.parentId ? prevLayout.get(prevPos.parentId) : null

        if (shouldAnimate && parentPos) {
          // Animate toward parent position
          el.transition('node-exit')
            .duration(ANIMATION.NODE_EXIT_DURATION)
            .ease(ANIMATION.EXIT_EASING)
            .attr('transform', `translate(${parentPos.x}, ${parentPos.y}) scale(0)`)
            .style('opacity', 0)
            .remove()
        } else {
          // Just fade out
          el.transition('node-exit')
            .duration(shouldAnimate ? ANIMATION.NODE_EXIT_DURATION : 0)
            .style('opacity', 0)
            .remove()
        }
      })

    // ENTER nodes
    const enterNodes = nodeSelection.enter()
      .append('g')
      .attr('class', d => `node node-${d.layer} node-${d.shape}`)
      .attr('data-id', d => d.id)

    // Track which nodes are new (for animation differentiation)
    const enteringNodeIds = new Set(enterNodes.data().map(d => d.id))

    // Set initial position for entering nodes
    if (shouldAnimate) {
      enterNodes.each(function(d) {
        const el = d3.select(this)
        // Start from parent position if available
        const parentPos = d.parentId ? nodePositions.get(d.parentId) : null
        const startX = parentPos?.x ?? d.x
        const startY = parentPos?.y ?? d.y

        el.attr('transform', `translate(${startX}, ${startY}) scale(0)`)
          .style('opacity', 0)
      })
    } else {
      enterNodes.attr('transform', d => `translate(${d.x}, ${d.y})`)
    }

    // Merge for shared operations
    const allNodes = enterNodes.merge(nodeSelection)

    // Get previous dimensions for animation
    const prevNodeDims = prevNodeDimsRef.current

    // Clear and rebuild node contents (shapes change based on state)
    allNodes.selectAll('*').remove()

    allNodes.each(function(d) {
      // Cast to generic type for renderNodeShape compatibility
      const nodeGroup = d3.select(this) as d3.Selection<SVGGElement, unknown, null, undefined>
      const isEntering = enteringNodeIds.has(d.id)
      const prevDims = prevNodeDims.get(d.id)
      const dimsChanged = prevDims && (Math.abs(prevDims.width - d.width) > 1 || Math.abs(prevDims.height - d.height) > 1)

      // Compute sim border for post-simulation stopped state (thin colored borders)
      let nodeBorder: { color: string; width: number } | null = null
      if (simMode && !simPlaybackActive && simEffects) {
        const pct = simEffects.get(d.id)
        if (pct !== undefined && Math.abs(pct) > 0.01 && !d.isTarget) {
          const absPct = Math.abs(pct)
          const intensity = 1 - Math.exp(-absPct / 6)
          // Thin border: 1-2.5px based on effect intensity
          const bw = 1 + 1.5 * intensity
          nodeBorder = {
            color: pct >= 0 ? '#39FF14' : '#FF1744',
            width: bw
          }
        }
      }

      // Render shape - animate size change if dimensions changed
      renderNodeShape(nodeGroup, d, shouldAnimate && !isEntering && dimsChanged ? prevDims : undefined, nodeBorder)

      // Invisible hit area
      nodeGroup.append('rect')
        .attr('x', -d.width / 2 - 5)
        .attr('y', -d.height / 2 - 5)
        .attr('width', d.width + 10)
        .attr('height', d.height + 10)
        .attr('fill', 'transparent')
        .attr('pointer-events', 'all')
        .style('cursor', 'pointer')
        .on('mouseenter', () => {
          // Cancel any pending hide timeout
          if (tooltipTimeoutRef.current) {
            clearTimeout(tooltipTimeoutRef.current)
            tooltipTimeoutRef.current = null
          }
          setHoveredNode(d)
        })
        .on('mouseleave', handleNodeMouseLeave)
        .on('click', () => {
          if (d.isInput) toggleInputExpand(d.id)
          else if (d.isOutput) toggleOutputExpand(d.id)
        })
        .on('dblclick', () => {
          if (!d.isTarget && onNavigateToNode) onNavigateToNode(d.id)
        })

      // === Text content ===
      const textColor = getContrastColor(d.sectorColor)
      const truncatedLabel = truncateLabel(d.label, d.maxLabelChars)
      const betaFontSize = Math.max(8, d.fontSize - 1)

      // In sim mode: show % change instead of beta
      const simPct = simMode && simEffects ? simEffects.get(d.id) : undefined
      const hasSimPct = simPct !== undefined && Math.abs(simPct) > 0.001
      const showBetaInNode = hasSimPct
        ? true  // Always show % change in sim mode
        : (d.betaDisplay && (!shouldDeclutter || d.depth <= 1))
      // Format % change: cap display at ±999%, use integer for large values
      const formatSimPct = (pct: number): string => {
        const sign = pct >= 0 ? '+' : ''
        const clamped = Math.max(-999, Math.min(999, pct))
        const suffix = Math.abs(pct) > 999 ? '' : ''
        if (Math.abs(clamped) >= 10) return `${sign}${Math.round(clamped)}%${suffix}`
        return `${sign}${clamped.toFixed(1)}%${suffix}`
      }
      const secondLineText = hasSimPct
        ? formatSimPct(simPct)
        : (d.betaDisplay ? `β = ${d.betaDisplay}` : '')
      const secondLineColor = hasSimPct
        ? (simPct >= 0 ? '#4CAF50' : '#F44336')
        : d.betaColor

      // Create text group for fade animation
      const textGroup = nodeGroup.append('g').attr('class', 'text-content')

      // Primary label
      textGroup.append('text')
        .attr('x', 0)
        .attr('y', showBetaInNode ? -6 : 0)
        .attr('text-anchor', 'middle')
        .attr('dominant-baseline', 'middle')
        .attr('font-size', d.fontSize)
        .attr('font-weight', d.isTarget ? 600 : 500)
        .attr('fill', textColor)
        .attr('pointer-events', 'none')
        .text(truncatedLabel)

      // Second line: beta value or % change
      if (showBetaInNode && secondLineText) {
        textGroup.append('text')
          .attr('x', 0)
          .attr('y', 10)
          .attr('text-anchor', 'middle')
          .attr('dominant-baseline', 'middle')
          .attr('font-size', betaFontSize)
          .attr('font-weight', 600)
          .attr('fill', secondLineColor)
          .attr('pointer-events', 'none')
          .text(secondLineText)
      }

      // Animate text fade in for entering nodes
      if (shouldAnimate && enteringNodeIds.has(d.id)) {
        textGroup
          .style('opacity', 0)
          .transition('text-fade')
          .delay(ANIMATION.NODE_ENTER_DURATION)
          .duration(ANIMATION.TEXT_FADE_DURATION)
          .style('opacity', 1)
      }

      // Glow effect - only for targets and immediate (depth 1) inputs/outputs
      const shouldShowGlow = showGlow && (d.isTarget || d.depth === 1)
      if (shouldShowGlow) {
        const glowColors: Record<string, string> = {
          target: '#00BCD4',
          input: '#FF9800',
          output: '#9C27B0'
        }
        const glowColor = glowColors[d.layer]
        const glowPadding = 4

        if (d.shape === 'hexagon') {
          // Octagon glow - match the shape
          const w = d.width + glowPadding * 2
          const h = d.height + glowPadding * 2
          const cut = h * 0.22
          const points = [
            `${-w/2 + cut},${-h/2}`,
            `${w/2 - cut},${-h/2}`,
            `${w/2},${-h/2 + cut}`,
            `${w/2},${h/2 - cut}`,
            `${w/2 - cut},${h/2}`,
            `${-w/2 + cut},${h/2}`,
            `${-w/2},${h/2 - cut}`,
            `${-w/2},${-h/2 + cut}`
          ].join(' ')

          nodeGroup.insert('polygon', ':first-child')
            .attr('points', points)
            .attr('fill', 'none')
            .attr('stroke', glowColor)
            .attr('stroke-width', 3)
            .attr('opacity', 0.4)
            .style('filter', 'blur(3px)')
            .attr('pointer-events', 'none')
        } else {
          // Rectangle/pill glow
          nodeGroup.insert('rect', ':first-child')
            .attr('x', -d.width / 2 - glowPadding)
            .attr('y', -d.height / 2 - glowPadding)
            .attr('width', d.width + glowPadding * 2)
            .attr('height', d.height + glowPadding * 2)
            .attr('rx', d.shape === 'pill' ? d.height / 2 + glowPadding : 10)
            .attr('ry', d.shape === 'pill' ? d.height / 2 + glowPadding : 10)
            .attr('fill', 'none')
            .attr('stroke', glowColor)
            .attr('stroke-width', 3)
            .attr('opacity', 0.4)
            .style('filter', 'blur(3px)')
            .attr('pointer-events', 'none')
        }
      }

      // Sim mode: pulsing cyan glow around intervention (target) nodes — persists entire sim
      if (simMode && d.isTarget) {
        const glowPad = 3
        nodeGroup.insert('rect', ':first-child')
          .attr('x', -d.width / 2 - glowPad)
          .attr('y', -d.height / 2 - glowPad)
          .attr('width', d.width + glowPad * 2)
          .attr('height', d.height + glowPad * 2)
          .attr('rx', 8)
          .attr('ry', 8)
          .attr('fill', 'none')
          .attr('stroke', '#00E5FF')
          .attr('stroke-width', 2.5)
          .attr('opacity', 0)
          .style('filter', 'blur(3px)')
          .style('pointer-events', 'none')
          .style('animation', 'intervention-pulse 2s ease-in-out infinite')
          .transition()
          .duration(600)
          .ease(d3.easeCubicOut)
          .attr('opacity', 0.8)
      }

      // Remove button for targets
      if (d.isTarget) {
        const btnX = d.width / 2 - 8
        const btnY = -d.height / 2 + 8

        const removeBtn = nodeGroup.append('g')
          .attr('class', 'remove-btn')
          .attr('transform', `translate(${btnX}, ${btnY})`)
          .style('cursor', 'pointer')
          .on('click', (event) => {
            event.stopPropagation()
            onRemoveTarget(d.id)
          })

        removeBtn.append('circle')
          .attr('r', 8)
          .attr('fill', '#f44336')

        removeBtn.append('line')
          .attr('x1', -3).attr('y1', -3)
          .attr('x2', 3).attr('y2', 3)
          .attr('stroke', '#fff').attr('stroke-width', 2)

        removeBtn.append('line')
          .attr('x1', 3).attr('y1', -3)
          .attr('x2', -3).attr('y2', 3)
          .attr('stroke', '#fff').attr('stroke-width', 2)
      }
    })

    // Animate nodes to final position
    if (shouldAnimate) {
      // Animate all nodes - entering nodes scale up, existing nodes move
      allNodes.each(function(d) {
        const el = d3.select(this)
        const isEntering = enteringNodeIds.has(d.id)

        if (isEntering) {
          // Entering nodes: animate from parent/initial to final with scale
          el.transition('node-enter')
            .duration(ANIMATION.NODE_ENTER_DURATION)
            .ease(ANIMATION.EASING)
            .attr('transform', `translate(${d.x}, ${d.y}) scale(1)`)
            .style('opacity', 1)
        } else {
          // Updating nodes: animate position change
          el.transition('node-update')
            .duration(ANIMATION.POSITION_DURATION)
            .ease(ANIMATION.EASING)
            .attr('transform', `translate(${d.x}, ${d.y})`)
        }
      })
    } else {
      // No animation: set positions directly
      allNodes.attr('transform', d => `translate(${d.x}, ${d.y})`)
    }

    // Store current layout for next render's exit animations
    const newLayoutMap = new Map<string, { x: number; y: number; parentId?: string }>()
    layout.nodes.forEach(n => {
      newLayoutMap.set(n.id, { x: n.x, y: n.y, parentId: n.parentId })
    })
    prevLayoutRef.current = newLayoutMap

    // Store current node dimensions for next render's size animations
    const newNodeDimsMap = new Map<string, { width: number; height: number }>()
    layout.nodes.forEach(n => {
      newNodeDimsMap.set(n.id, { width: n.width, height: n.height })
    })
    prevNodeDimsRef.current = newNodeDimsMap

  }, [layout, dimensions, targetIds, betaThreshold, onRemoveTarget, onNavigateToNode, showGlow, toggleInputExpand, toggleOutputExpand, simMode, simPlaybackActive, simEffects, handleNodeMouseLeave])

  // Empty state - no targets selected (skip if simData has targets)
  if (targetIds.length === 0 && !simData) {
    return (
      <div
        ref={containerRef}
        style={{
          width: '100%',
          height: '100%',
          display: 'flex',
          flexDirection: 'column',
          alignItems: 'center',
          justifyContent: 'center',
          background: '#f4f5fa'
        }}
      >
        <div style={{ textAlign: 'center', color: '#666' }}>
          <div style={{ fontSize: 48, marginBottom: 16 }}>🔍</div>
          <div style={{ fontSize: 18, fontWeight: 500, marginBottom: 8 }}>
            No targets selected
          </div>
          <div style={{ fontSize: 14, color: '#767676' }}>
            Double-click a node in Global View to explore its causal pathways
          </div>
          <button
            onClick={onSwitchToGlobal}
            style={{
              marginTop: 24,
              padding: '10px 20px',
              fontSize: 14,
              cursor: 'pointer',
              border: '1px solid #3B82F6',
              borderRadius: 6,
              background: '#3B82F6',
              color: 'white',
              fontWeight: 500
            }}
          >
            Go to Global View
          </button>
        </div>
      </div>
    )
  }

  // Empty mode - targets exist but no causal edges found (skip in sim mode — show target with pulse)
  if (localViewData?.mode === 'empty' && !simMode) {
    const firstTarget = nodeById.get(targetIds[0])
    const targetLabel = firstTarget?.label.replace(/_/g, ' ') || 'Selected node'
    const hasChildren = firstTarget?.children && firstTarget.children.length > 0
    const childCount = firstTarget?.children?.length || 0

    return (
      <div
        ref={containerRef}
        style={{
          width: '100%',
          height: '100%',
          display: 'flex',
          flexDirection: 'column',
          alignItems: 'center',
          justifyContent: 'center',
          background: '#f4f5fa'
        }}
      >
        <div style={{ textAlign: 'center', color: '#666', maxWidth: 500, padding: 20 }}>
          <div style={{ fontSize: 48, marginBottom: 16 }}>📊</div>
          <div style={{ fontSize: 18, fontWeight: 500, marginBottom: 8 }}>
            No causal relationships found
          </div>
          <div style={{ fontSize: 14, color: '#767676', marginBottom: 16, lineHeight: 1.5 }}>
            <strong>{targetLabel}</strong> has no causal connections at its ring level
            {localViewData.totalChildCount !== undefined && localViewData.totalChildCount > 0 && (
              <span> (checked {localViewData.totalChildCount} child indicators)</span>
            )}
          </div>
          <div style={{
            fontSize: 12,
            color: '#666',
            background: '#eef0f6',
            padding: 12,
            borderRadius: 6,
            textAlign: 'left',
            marginBottom: 16
          }}>
            <div style={{ fontWeight: 500, marginBottom: 4 }}>Possible reasons:</div>
            <ul style={{ margin: 0, paddingLeft: 20 }}>
              <li>Beta threshold too high (use controls in bottom-right)</li>
              <li>Exogenous variable (not caused by other factors in the model)</li>
              <li>Isolated node (no statistically significant relationships)</li>
              <li>Data limitation (relationships not yet modeled)</li>
            </ul>
          </div>
          <div style={{ display: 'flex', gap: 12, justifyContent: 'center', flexWrap: 'wrap' }}>
            {/* Go Back button - shown when there's drill history */}
            {canDrillUp && onDrillUp && (
              <button
                onClick={onDrillUp}
                style={{
                  padding: '10px 20px',
                  fontSize: 14,
                  cursor: 'pointer',
                  border: '1px solid #2196F3',
                  borderRadius: 6,
                  background: '#2196F3',
                  color: 'white',
                  fontWeight: 500
                }}
              >
                ← Go Back
              </button>
            )}
            {hasChildren && onDrillDown && (
              <button
                onClick={() => onDrillDown(targetIds[0])}
                style={{
                  padding: '10px 20px',
                  fontSize: 14,
                  cursor: 'pointer',
                  border: '1px solid #9C27B0',
                  borderRadius: 6,
                  background: canDrillUp ? 'white' : '#9C27B0',
                  color: canDrillUp ? '#9C27B0' : 'white',
                  fontWeight: 500
                }}
              >
                Drill Down ({childCount})
              </button>
            )}
            <button
              onClick={onSwitchToGlobal}
              style={{
                padding: '10px 20px',
                fontSize: 14,
                cursor: 'pointer',
                border: '1px solid #3B82F6',
                borderRadius: 6,
                background: (canDrillUp || hasChildren) ? 'white' : '#3B82F6',
                color: (canDrillUp || hasChildren) ? '#3B82F6' : 'white',
                fontWeight: 500
              }}
            >
              Global View
            </button>
          </div>
        </div>

        {/* Controls Panel - always visible */}
        <div
          style={{
            position: 'absolute',
            bottom: 40,
            right: 10,
            background: 'rgba(255,255,255,0.95)',
            padding: '8px 12px',
            borderRadius: 6,
            boxShadow: '0 1px 4px rgba(0,0,0,0.1)',
            zIndex: 10,
            fontSize: 11
          }}
        >
          {/* Beta Threshold with +/- buttons */}
          <div style={{ display: 'flex', alignItems: 'center', gap: 3, marginBottom: 6 }}>
            <span style={{ color: '#666', whiteSpace: 'nowrap', fontSize: 11 }}>β ≥ {betaThreshold.toFixed(2)}</span>
            <button
              onClick={() => {
                const decrement = betaRange.step * 2
                const newMin = Math.max(0, sliderMin - decrement)
                setSliderMin(Math.round(newMin * 100) / 100)
              }}
              disabled={sliderMin <= 0}
              style={{
                width: 14, height: 14, padding: 0, fontSize: 10, lineHeight: 1,
                cursor: sliderMin <= 0 ? 'not-allowed' : 'pointer',
                border: '1px solid #bcc3d4', borderRadius: 2,
                background: sliderMin <= 0 ? '#eef0f6' : 'white',
                color: sliderMin <= 0 ? '#bcc3d4' : '#666'
              }}
              title="Decrease min"
            >−</button>
            <span style={{ fontSize: 10, color: '#767676', minWidth: 20, textAlign: 'right' }}>{sliderMin.toFixed(1)}</span>
            <input
              type="range"
              min={sliderMin}
              max={sliderMax}
              step={betaRange.step}
              value={Math.min(Math.max(betaThreshold, sliderMin), sliderMax)}
              onChange={(e) => onBetaThresholdChange(parseFloat(e.target.value))}
              onPointerDown={(e) => e.currentTarget.setPointerCapture(e.pointerId)}
              style={{ width: 70, cursor: 'grab' }}
            />
            <span style={{ fontSize: 10, color: '#767676', minWidth: 20 }}>{sliderMax.toFixed(1)}</span>
            <button
              onClick={() => {
                const increment = betaRange.step * 2
                const newMax = sliderMax + increment
                setSliderMax(Math.round(newMax * 100) / 100)
              }}
              style={{
                width: 14, height: 14, padding: 0, fontSize: 10, lineHeight: 1,
                cursor: 'pointer', border: '1px solid #bcc3d4', borderRadius: 2,
                background: 'white', color: '#666'
              }}
              title="Increase max"
            >+</button>
            <button
              onClick={() => {
                setSliderMin(betaRange.min)
                setSliderMax(Math.max(betaRange.max, 1))
                onBetaThresholdChange(calculateOptimalThreshold)
              }}
              style={{
                width: 14, height: 14, padding: 0, fontSize: 9, lineHeight: 1,
                cursor: 'pointer', border: '1px solid #bcc3d4', borderRadius: 2,
                background: 'white', color: '#767676'
              }}
              title="Reset"
            >↺</button>
          </div>

          {/* Clear button */}
          <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
            <button
              onClick={onClearTargets}
              style={{
                padding: '2px 8px', fontSize: 10,
                cursor: 'pointer', border: '1px solid #bcc3d4',
                borderRadius: 3, background: 'white', color: '#666'
              }}
            >Clear (C)</button>
          </div>
        </div>
      </div>
    )
  }

  return (
    <div
      ref={containerRef}
      style={{
        width: '100%',
        height: '100%',
        position: 'relative',
        background: '#f4f5fa'
      }}
    >
      {/* Controls Panel */}
      <div
        style={{
          position: 'absolute',
          bottom: 20,
          right: 20,
          background: 'rgba(255,255,255,0.95)',
          padding: '8px 12px',
          borderRadius: 6,
          boxShadow: '0 1px 4px rgba(0,0,0,0.1)',
          zIndex: 10,
          fontSize: 11
        }}
      >
        {/* Simulation mode label */}
        {simMode && (
          <div style={{ display: 'flex', alignItems: 'center', gap: 6, marginBottom: 6 }}>
            <span style={{ fontWeight: 600, color: '#333' }}>Simulation Results</span>
            {simPlaybackActive && (
              <span style={{ fontSize: 10, color: '#39FF14', fontWeight: 500 }}>LIVE</span>
            )}
          </div>
        )}

        {/* Layer Controls (like Global View's ring expand/collapse) — hidden in sim mode */}
        {!simMode && (() => {
          // Compute current state for button enable/disable
          const inputMaxDepth = localViewData ? Math.max(...localViewData.inputs.map(n => n.depth), 0) : 0
          const outputMaxDepth = localViewData ? Math.max(...localViewData.outputs.map(n => n.depth), 0) : 0
          const canExpandInputs = localViewData && (
            localViewData.inputs.some(n => n.hasMoreInputs) ||
            localViewData.targets.some(n => n.hasMoreInputs)
          )
          const canExpandOutputs = localViewData && (
            localViewData.outputs.some(n => n.hasMoreOutputs) ||
            localViewData.targets.some(n => n.hasMoreOutputs)
          )
          const canCollapseInputs = inputMaxDepth > 0 || expandedInputNodes.size > 0
          const canCollapseOutputs = outputMaxDepth > 0 || expandedOutputNodes.size > 0

          return (
            <div style={{ display: 'flex', alignItems: 'center', gap: 12, marginBottom: 6 }}>
              <div style={{ display: 'flex', alignItems: 'center', gap: 4 }}>
                <span style={{ color: '#FF9800', fontWeight: 500 }}>Causes</span>
                <button
                  onClick={collapseInputLayer}
                  disabled={!canCollapseInputs}
                  style={{
                    width: 18, height: 18, padding: 0, fontSize: 14, lineHeight: 1,
                    cursor: !canCollapseInputs ? 'not-allowed' : 'pointer',
                    border: '1px solid #bcc3d4', borderRadius: 3,
                    background: !canCollapseInputs ? '#eef0f6' : 'white',
                    color: !canCollapseInputs ? '#bbb' : '#666'
                  }}
                  title="Collapse outermost layer"
                >−</button>
                <span style={{ minWidth: 14, textAlign: 'center', color: '#666' }}>{inputMaxDepth}</span>
                <button
                  onClick={expandInputLayer}
                  disabled={!canExpandInputs}
                  style={{
                    width: 18, height: 18, padding: 0, fontSize: 14, lineHeight: 1,
                    cursor: !canExpandInputs ? 'not-allowed' : 'pointer',
                    border: '1px solid #bcc3d4', borderRadius: 3,
                    background: !canExpandInputs ? '#eef0f6' : 'white',
                    color: !canExpandInputs ? '#bbb' : '#666'
                  }}
                  title="Expand all visible nodes"
                >+</button>
              </div>

              <div style={{ display: 'flex', alignItems: 'center', gap: 4 }}>
                <span style={{ color: '#9C27B0', fontWeight: 500 }}>Effects</span>
                <button
                  onClick={collapseOutputLayer}
                  disabled={!canCollapseOutputs}
                  style={{
                    width: 18, height: 18, padding: 0, fontSize: 14, lineHeight: 1,
                    cursor: !canCollapseOutputs ? 'not-allowed' : 'pointer',
                    border: '1px solid #bcc3d4', borderRadius: 3,
                    background: !canCollapseOutputs ? '#eef0f6' : 'white',
                    color: !canCollapseOutputs ? '#bbb' : '#666'
                  }}
                  title="Collapse outermost layer"
                >−</button>
                <span style={{ minWidth: 14, textAlign: 'center', color: '#666' }}>{outputMaxDepth}</span>
                <button
                  onClick={expandOutputLayer}
                  disabled={!canExpandOutputs}
                  style={{
                    width: 18, height: 18, padding: 0, fontSize: 14, lineHeight: 1,
                    cursor: !canExpandOutputs ? 'not-allowed' : 'pointer',
                    border: '1px solid #bcc3d4', borderRadius: 3,
                    background: !canExpandOutputs ? '#eef0f6' : 'white',
                    color: !canExpandOutputs ? '#bbb' : '#666'
                  }}
                  title="Expand all visible nodes"
                >+</button>
              </div>
            </div>
          )
        })()}

        {/* Beta Threshold with +/- buttons — hidden in sim mode */}
        {!simMode && (
          <div style={{ display: 'flex', alignItems: 'center', gap: 3, marginBottom: 6 }}>
            <span style={{ color: '#666', whiteSpace: 'nowrap', fontSize: 11 }}>β ≥ {betaThreshold.toFixed(2)}</span>
            {/* Decrease min bound */}
            <button
              onClick={() => {
                const decrement = betaRange.step * 2
                const newMin = Math.max(0, sliderMin - decrement)
                setSliderMin(Math.round(newMin * 100) / 100)
              }}
              disabled={sliderMin <= 0}
              style={{
                width: 14, height: 14, padding: 0, fontSize: 10, lineHeight: 1,
                cursor: sliderMin <= 0 ? 'not-allowed' : 'pointer',
                border: '1px solid #bcc3d4', borderRadius: 2,
                background: sliderMin <= 0 ? '#eef0f6' : 'white',
                color: sliderMin <= 0 ? '#bcc3d4' : '#666'
              }}
              title="Decrease min"
            >−</button>
            <span style={{ fontSize: 10, color: '#767676', minWidth: 20, textAlign: 'right' }}>{sliderMin.toFixed(1)}</span>
            <input
              type="range"
              min={sliderMin}
              max={sliderMax}
              step={betaRange.step}
              value={Math.min(Math.max(betaThreshold, sliderMin), sliderMax)}
              onChange={(e) => onBetaThresholdChange(parseFloat(e.target.value))}
              onPointerDown={(e) => e.currentTarget.setPointerCapture(e.pointerId)}
              style={{ width: 70, cursor: 'grab' }}
            />
            <span style={{ fontSize: 10, color: '#767676', minWidth: 20 }}>{sliderMax.toFixed(1)}</span>
            {/* Increase max bound */}
            <button
              onClick={() => {
                const increment = betaRange.step * 2
                const newMax = sliderMax + increment
                setSliderMax(Math.round(newMax * 100) / 100)
              }}
              style={{
                width: 14, height: 14, padding: 0, fontSize: 10, lineHeight: 1,
                cursor: 'pointer', border: '1px solid #bcc3d4', borderRadius: 2,
                background: 'white', color: '#666'
              }}
              title="Increase max"
            >+</button>
            {/* Reset to auto-calculated range */}
            <button
              onClick={() => {
                setSliderMin(betaRange.min)
                setSliderMax(Math.max(betaRange.max, 1))
                onBetaThresholdChange(calculateOptimalThreshold)
              }}
              style={{
                width: 14, height: 14, padding: 0, fontSize: 9, lineHeight: 1,
                cursor: 'pointer', border: '1px solid #bcc3d4', borderRadius: 2,
                background: 'white', color: '#767676'
              }}
              title="Reset"
            >↺</button>
          </div>
        )}

        {/* Stats + Clear */}
        <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
          {stats && (
            <span style={{ color: '#767676' }}>
              {stats.totalInputs}↓ {stats.totalOutputs}↑ ({stats.totalEdges})
            </span>
          )}
          <button
            onClick={onClearTargets}
            style={{
              padding: '2px 8px', fontSize: 10,
              cursor: 'pointer', border: '1px solid #bcc3d4',
              borderRadius: 3, background: 'white', color: '#666'
            }}
          >Clear (C)</button>
        </div>
      </div>

      {/* SVG Canvas */}
      <svg ref={svgRef} style={{ width: '100%', height: '100%' }} />

      {/* Node Tooltip */}
      {hoveredNode && (
        <div
          onMouseEnter={() => {
            isHoveringTooltipRef.current = true
            // Cancel any pending hide timeout
            if (tooltipTimeoutRef.current) {
              clearTimeout(tooltipTimeoutRef.current)
              tooltipTimeoutRef.current = null
            }
          }}
          onMouseLeave={() => {
            isHoveringTooltipRef.current = false
            setHoveredNode(null)
          }}
          style={{
            position: 'absolute',
            bottom: 20,
            left: '50%',
            transform: 'translateX(-50%)',
            background: 'white',
            padding: '12px 16px',
            borderRadius: 8,
            boxShadow: '0 4px 12px rgba(0,0,0,0.15)',
            zIndex: 20,
            maxWidth: 400
          }}
        >
          <div style={{ fontWeight: 600, marginBottom: 4 }}>{hoveredNode.label}</div>
          <div style={{ fontSize: 12, color: '#666' }}>
            <span style={{
              display: 'inline-block',
              width: 8, height: 8, borderRadius: '50%',
              background: hoveredNode.sectorColor,
              marginRight: 6
            }} />
            {hoveredNode.sector} • Ring {hoveredNode.ring}
            {hoveredNode.isTarget && <span style={{ marginLeft: 8, color: '#3B82F6', fontWeight: 500 }}>Target</span>}
            {hoveredNode.isInput && <span style={{ marginLeft: 8, color: '#FF9800' }}>Cause</span>}
            {hoveredNode.isOutput && <span style={{ marginLeft: 8, color: '#9C27B0' }}>Effect</span>}
          </div>
          {hoveredNode.beta !== undefined && (
            <div style={{
              fontSize: 14, fontWeight: 600, marginTop: 8,
              color: hoveredNode.beta >= 0 ? '#4CAF50' : '#F44336'
            }}>
              β = {hoveredNode.beta >= 0 ? '+' : ''}{hoveredNode.beta.toFixed(3)}
            </div>
          )}
          {/* Simulation effect display */}
          {simMode && simEffects && (() => {
            const pct = simEffects.get(hoveredNode.id)
            if (pct === undefined) return null
            const color = pct >= 0 ? '#39FF14' : '#FF1744'
            return (
              <div style={{
                fontSize: 11, marginTop: 6, padding: '4px 8px',
                background: '#1a1a2e', borderRadius: 4,
                borderLeft: `3px solid ${color}`
              }}>
                <div style={{ fontWeight: 600, color, fontSize: 13 }}>
                  {pct >= 0 ? '+' : ''}{Math.abs(pct) >= 10 ? Math.round(pct) : pct.toFixed(2)}% simulated
                </div>
                {currentYear && (
                  <div style={{ color: '#aaa', fontSize: 10, marginTop: 2 }}>
                    Year {currentYear}
                  </div>
                )}
              </div>
            )
          })()}
          {/* CI bounds and uncertainty metrics */}
          {(() => {
            const ciData = ciCache?.get(hoveredNode.id)
            if (!ciData || ciData.std === 0) return null
            const isAggregated = hoveredNode.ring < 5
            return (
              <div style={{
                fontSize: 10,
                color: '#666',
                marginTop: 8,
                padding: '6px 8px',
                background: '#f0f2f8',
                borderRadius: 4,
                borderLeft: '3px solid #3B82F6'
              }}>
                <div style={{ display: 'flex', gap: 12, flexWrap: 'wrap', alignItems: 'center' }}>
                  <span>
                    <strong>SHAP:</strong> {(ciData.mean * 100).toFixed(1)}%
                  </span>
                  <span>
                    <strong>95% CI:</strong> [{(ciData.ci_lower * 100).toFixed(1)}%, {(ciData.ci_upper * 100).toFixed(1)}%]
                  </span>
                  <span style={{ color: '#767676' }}>
                    ±{(ciData.std * 100).toFixed(2)}%
                  </span>
                </div>
                {isAggregated && ciData.n_children && (
                  <div style={{ marginTop: 4, fontSize: 9, color: '#767676' }}>
                    Aggregated from {ciData.n_children} children
                    {ciData.child_coverage !== undefined && ciData.child_coverage < 1 && (
                      <span> ({(ciData.child_coverage * 100).toFixed(0)}% with data)</span>
                    )}
                  </div>
                )}
                {currentYear && (
                  <div style={{ marginTop: 4, fontSize: 9, color: '#767676' }}>
                    Year: {currentYear}
                  </div>
                )}
              </div>
            )
          })()}
          {/* Actions for non-target nodes */}
          {!hoveredNode.isTarget && (
            <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginTop: 8, flexWrap: 'wrap' }}>
              {/* Drill-down for non-indicator nodes with children */}
              {hoveredNode.hasChildren && hoveredNode.ring < 5 && onDrillDown && (
                <button
                  onClick={() => onDrillDown(hoveredNode.id)}
                  style={{
                    padding: '4px 8px',
                    fontSize: 11,
                    cursor: 'pointer',
                    border: '1px solid #9C27B0',
                    borderRadius: 4,
                    background: 'white',
                    color: '#9C27B0',
                    fontWeight: 500
                  }}
                >
                  Drill Down (d)
                </button>
              )}
              {onShowInGlobal && (
                <button
                  onClick={() => onShowInGlobal(hoveredNode.id)}
                  style={{
                    padding: '4px 8px',
                    fontSize: 11,
                    cursor: 'pointer',
                    border: '1px solid #3B82F6',
                    borderRadius: 4,
                    background: 'white',
                    color: '#3B82F6',
                    fontWeight: 500
                  }}
                >
                  Global (W)
                </button>
              )}
              <span style={{ fontSize: 11, color: '#767676' }}>
                Double-click to explore
              </span>
            </div>
          )}
          {/* Drill-up to go back */}
          {hoveredNode.isTarget && canDrillUp && onDrillUp && (
            <div style={{ display: 'flex', alignItems: 'center', gap: 12, marginTop: 8 }}>
              <button
                onClick={onDrillUp}
                style={{
                  padding: '4px 8px',
                  fontSize: 11,
                  cursor: 'pointer',
                  border: '1px solid #2196F3',
                  borderRadius: 4,
                  background: 'white',
                  color: '#2196F3',
                  fontWeight: 500
                }}
              >
                ← Go Back (d)
              </button>
              <span style={{ fontSize: 11, color: '#767676' }}>
                Return to previous view
              </span>
            </div>
          )}
          {/* Drill-down for target nodes */}
          {hoveredNode.isTarget && !canDrillUp && hoveredNode.hasChildren && onDrillDown && (
            <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginTop: 8, flexWrap: 'wrap' }}>
              <button
                onClick={() => onDrillDown(hoveredNode.id)}
                style={{
                  padding: '4px 8px',
                  fontSize: 11,
                  cursor: 'pointer',
                  border: '1px solid #9C27B0',
                  borderRadius: 4,
                  background: 'white',
                  color: '#9C27B0',
                  fontWeight: 500
                }}
              >
                Drill Down (d)
              </button>
              <span style={{ fontSize: 11, color: '#767676' }}>
                View {hoveredNode.childIds?.length || 0} children
              </span>
            </div>
          )}
        </div>
      )}

      {/* Edge Tooltip */}
      {hoveredEdge && (() => {
        // Find the full edge data to check for aggregation
        const fullEdge = localViewData?.edges.find(
          e => e.source === hoveredEdge.source && e.target === hoveredEdge.target
        )
        const isAggregated = fullEdge?.isAggregated
        const pathwayCount = fullEdge?.pathwayCount

        return (
          <div
            style={{
              position: 'absolute',
              top: 70,
              right: 10,
              background: 'white',
              padding: '12px 16px',
              borderRadius: 8,
              boxShadow: '0 4px 12px rgba(0,0,0,0.15)',
              zIndex: 20,
              maxWidth: 300
            }}
          >
            <div style={{ fontSize: 12, fontWeight: 600, marginBottom: 4 }}>
              {isAggregated ? 'Aggregated Causal Effect' : 'Causal Effect'}
            </div>
            <div style={{
              fontSize: 18, fontWeight: 600,
              color: hoveredEdge.beta >= 0 ? '#4CAF50' : '#F44336'
            }}>
              β = {hoveredEdge.beta >= 0 ? '+' : ''}{hoveredEdge.beta.toFixed(3)}
              {isAggregated && <span style={{ fontSize: 12, fontWeight: 400, marginLeft: 4 }}>(avg)</span>}
            </div>
            <div style={{ fontSize: 11, color: '#767676', marginTop: 4 }}>
              {isAggregated
                ? `${pathwayCount} pathway${pathwayCount !== 1 ? 's' : ''} through child indicators`
                : (hoveredEdge.beta >= 0 ? 'Positive relationship' : 'Negative relationship')
              }
            </div>
            {isAggregated && fullEdge?.pathways && fullEdge.pathways.length > 0 && (
              <div style={{ fontSize: 10, color: '#666', marginTop: 8, borderTop: '1px solid #e2e6ee', paddingTop: 8 }}>
                <div style={{ fontWeight: 500, marginBottom: 4 }}>Top pathways:</div>
                {fullEdge.pathways.slice(0, 3).map((p, i) => {
                  const srcNode = nodeById.get(p.childSource)
                  return (
                    <div key={i} style={{ marginBottom: 2 }}>
                      {srcNode?.label.substring(0, 25) || p.childSource}
                      <span style={{ color: p.beta >= 0 ? '#4CAF50' : '#F44336', marginLeft: 4 }}>
                        β={p.beta.toFixed(2)}
                      </span>
                    </div>
                  )
                })}
              </div>
            )}
          </div>
        )
      })()}
    </div>
  )
}

export default LocalView
