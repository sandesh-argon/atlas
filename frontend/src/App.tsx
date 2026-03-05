import { useEffect, useRef, useState, useCallback, useMemo } from 'react'
import * as d3 from 'd3'
import Fuse from 'fuse.js'
import './styles/App.css'
import { debug } from './utils/debug'
import {
  getStateFromBrowserURL,
  updateBrowserURL,
  copyURLToClipboard,
  type URLState
} from './utils/urlState'
import type {
  RawNodeV21,
  GraphDataV21,
  PositionedNode,
  StructuralEdge,
  ViewMode
} from './types'
import { ViewTabs } from './components/ViewTabs'
import { SidebarDrawer } from './components/SidebarDrawer'
import { DesktopBanner } from './components/DesktopBanner'
import { StrataTabs } from './components/StrataTabs'
import { LocalView } from './components/LocalView'
import { WorldMap } from './components/WorldMap'
import { CountrySelector, SimulationPanel, TimelinePlayer, DataQualityPanel } from './components/simulation'
import { Tutorial, type TutorialHandle, type TutorialRef } from './components/Tutorial'
import { useSimulationStore, useIsPanelOpen } from './stores/simulationStore'
import { simulationAPI, type CountryGraphEdge } from './services/api'
import { getCausalEdges, countryGraphToRawEdges, buildSimLocalViewData } from './utils/causalEdges'
import { extractIndicatorsFromGraph, computeCountryCoverage } from './utils/countryAggregation'
import { perfTrace, type StructuralActionName } from './utils/perfTrace'
import { layoutTrace } from './utils/layoutTrace'
import { initAnnouncer, announce } from './utils/announce'
import {
  buildGraphNavModel,
  formatAnnouncement,
  getFallbackFocus,
  getNextSibling,
  getParent,
  getPrevSibling,
  type GraphNavModel,
  type GraphNavNode,
} from './a11y/graphNodeNav'
import { SIM_MS_PER_YEAR } from './constants/time'
import { BREAKPOINTS } from './constants/breakpoints'
import { useViewport } from './hooks/useViewport'
import { REGION_DISPLAY_NAMES, REGION_TO_ISO3S } from './constants/regions'
import {
  resolveLayoutBudget,
  STRUCTURAL_LOCK_FALLBACK_MS,
  type LayoutAction,
  type LayoutBudget
} from './constants/animation'
import {
  computeRadialLayout,
  detectOverlaps,
  computeLayoutStats,
  resolveOverlaps,
  type LayoutConfig,
  type LayoutNode,
  type TextConfig,
  type CausalLayoutHint
} from './layouts/RadialLayout'
import { getTextBoostFactor } from './layouts/branchCurves'
import type { OutcomeSectorSnapshot } from './layouts/outcomeAngles'
import {
  ViewportAwareLayout,
  createViewportLayout
} from './layouts/ViewportScales'

/**
 * Semantic hierarchy visualization with concentric rings - v2.1 only
 * 6 rings: Root → Outcomes → Coarse Domains → Fine Domains → Indicator Groups → Indicators
 *
 * Features:
 * - Click to expand/collapse node children
 * - Hover to see node details
 * - Starts with only root visible, expand to explore hierarchy
 * - Adjustable ring radii via sliders
 * - Node sizes represent SHAP importance directly (area ∝ importance)
 */

// Ring labels
const RING_LABELS = [
  'Quality of Life',
  'Outcomes',
  'Coarse Domains',
  'Fine Domains',
  'Indicator Groups',
  'Indicators'
]

const GRAPH_NAV_INSTRUCTIONS_ID = 'global-graph-kbd-instructions'
const GRAPH_ANNOUNCE_DEDUPE_MS = 220

/**
 * Loading spinner with delay to avoid flash for fast loads.
 * Positioned at specified x, y coordinates (follows QoL node).
 */
function LoadingSpinner({ show, delay = 200, minDisplay = 300, posRef, elRef }: {
  show: boolean
  delay?: number
  minDisplay?: number
  posRef: React.RefObject<{ x: number; y: number } | null>
  elRef: React.RefObject<HTMLDivElement | null>
}) {
  const [visible, setVisible] = useState(false)
  const showTimerRef = useRef<number | null>(null)
  const hideTimerRef = useRef<number | null>(null)
  const shownAtRef = useRef<number>(0)
  const visibleRef = useRef(false)

  useEffect(() => {
    visibleRef.current = visible
  }, [visible])

  useEffect(() => {
    if (show) {
      if (hideTimerRef.current !== null) {
        clearTimeout(hideTimerRef.current)
        hideTimerRef.current = null
      }
      if (!visibleRef.current && showTimerRef.current === null) {
        showTimerRef.current = window.setTimeout(() => {
          showTimerRef.current = null
          shownAtRef.current = performance.now()
          setVisible(true)
        }, delay)
      }
    } else {
      if (showTimerRef.current !== null) {
        clearTimeout(showTimerRef.current)
        showTimerRef.current = null
      }
      if (!visibleRef.current) {
        setVisible(false)
      } else {
        const elapsed = performance.now() - shownAtRef.current
        const remaining = Math.max(0, minDisplay - elapsed)
        if (hideTimerRef.current !== null) {
          clearTimeout(hideTimerRef.current)
        }
        hideTimerRef.current = window.setTimeout(() => {
          hideTimerRef.current = null
          shownAtRef.current = 0
          setVisible(false)
        }, remaining)
      }
    }
    return () => {
      if (showTimerRef.current !== null) {
        clearTimeout(showTimerRef.current)
        showTimerRef.current = null
      }
      if (hideTimerRef.current !== null) {
        clearTimeout(hideTimerRef.current)
        hideTimerRef.current = null
      }
    }
  }, [show, delay, minDisplay])

  // Sync initial position on mount/visibility change
  const callbackRef = useCallback((node: HTMLDivElement | null) => {
    (elRef as { current: HTMLDivElement | null }).current = node
    if (node && posRef.current) {
      node.style.left = `${posRef.current.x}px`
      node.style.top = `${posRef.current.y}px`
    }
  }, [elRef, posRef])

  if (!visible) return null

  const pos = posRef.current
  const hasPos = pos != null

  return (
    <div
      ref={callbackRef}
      style={{
        position: 'absolute',
        left: hasPos ? pos.x : '50%',
        top: hasPos ? pos.y : '50%',
        transform: 'translate(-50%, -50%)',
        zIndex: 100,
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'center',
        willChange: 'left, top'
      }}
    >
      <div style={{
        width: 32,
        height: 32,
        border: '3px solid rgba(0, 229, 255, 0.15)',
        borderTopColor: '#00E5FF',
        borderRadius: '50%',
        animation: 'spin 0.8s linear infinite',
        filter: 'drop-shadow(0 0 4px rgba(0, 229, 255, 0.4))'
      }} />
    </div>
  )
}

// Average character width as fraction of font size (for text width estimation)
const AVG_CHAR_WIDTH_RATIO = 0.55

// Note: getAdaptiveSpacing, calculateDynamicRadii, getNodeRadius, isNodeFloored
// are now provided by ViewportAwareLayout instance

/**
 * Generate ring configs from individual radii
 * nodeSize is a placeholder - actual sizing uses viewport-aware calculations
 */
function generateRingConfigs(radii: number[], maxNodeRadius: number = 20) {
  return RING_LABELS.map((label, i) => ({
    radius: radii[i] || i * 150,
    nodeSize: maxNodeRadius,  // Placeholder, actual sizing is viewport-aware
    label
  }))
}

function getOutcomeRotationStep(layoutAction: LayoutAction | null): number {
  switch (layoutAction) {
    case 'single_expand':
      return Math.PI / 14  // ~12.9°
    case 'ring_expand':
    case 'global_expand':
      return Math.PI / 18  // 10°
    case 'single_collapse':
    case 'ring_collapse':
    case 'global_collapse':
    default:
      return 0
  }
}

/** Extended PositionedNode with parent reference for expansion logic */
interface ExpandableNode extends PositionedNode {
  parentId: string | null
  childIds: string[]
  hasChildren: boolean
  importance: number  // Normalized SHAP importance (0-1) for node sizing
  angle: number  // Angular position in radians (from RadialLayout)
}

/** Searchable node for fuzzy search (all 3,122 nodes) */
interface SearchableNode {
  id: string
  label: string
  domain: string
  subdomain: string
  ring: number
  importance: number
  parentId: string | null
  hasChildren: boolean
}

const DOMAIN_COLORS: Record<string, string> = {
  'Health': '#E91E63',
  'Education': '#FF9800',
  'Economic': '#4CAF50',
  'Governance': '#9C27B0',
  'Environment': '#00BCD4',
  'Demographics': '#795548',
  'Security': '#F44336',
  'Development': '#3F51B5',
  'Research': '#009688'
}

// Use Vite's base URL for correct path in GitHub Pages
const DATA_FILE = `${import.meta.env.BASE_URL}data/v2_1_visualization_final.json`

// Node padding for layout (used by RadialLayout, but actual spacing is adaptive)
const DEFAULT_NODE_PADDING = 2  // Base padding, actual spacing is adaptive

/**
 * Converts a LayoutNode to an ExpandableNode for rendering
 */
function toExpandableNode(layoutNode: LayoutNode): ExpandableNode {
  const raw = layoutNode.rawNode
  return {
    id: layoutNode.id,
    label: raw.node_type === 'root' ? 'Quality of Life' : raw.label.replace(/_/g, ' '),
    description: raw.description || getDefaultDescription(raw),
    semanticPath: {
      domain: raw.domain || '',
      subdomain: raw.subdomain || '',
      fine_cluster: '',
      full_path: raw.label
    },
    isDriver: raw.node_type === 'indicator' && raw.out_degree > 0,
    isOutcome: raw.node_type === 'outcome_category',
    shapImportance: 0,  // Deprecated - using temporal SHAP only
    importance: 0,  // Always 0 - sizing comes from temporal SHAP (v3.1)
    degree: raw.in_degree + raw.out_degree,
    ring: layoutNode.ring,
    x: layoutNode.x,
    y: layoutNode.y,
    parentId: layoutNode.parent?.id || null,
    childIds: (raw.children || []).map(c => String(c)),  // Use raw data for all children
    hasChildren: (raw.children?.length || 0) > 0,  // Use raw data to check if expandable
    angle: layoutNode.angle  // Angular position from layout
  }
}

/**
 * Generates default description based on node type
 */
function getDefaultDescription(node: RawNodeV21): string {
  switch (node.node_type) {
    case 'root':
      return 'Root'
    case 'outcome_category':
      return `${node.indicator_count || 0} indicators`
    case 'coarse_domain':
      return `Coarse Domain: ${node.label}`
    case 'fine_domain':
      return `Fine Domain: ${node.label}`
    case 'indicator':
      return ''
    default:
      return ''
  }
}

/** Interpolate QoL score for a year: linear between known points, hold at edges. */
function interpolateQol(byYear: Record<string, number>, year: number): number | null {
  const known: Array<[number, number]> = []
  for (const [yStr, val] of Object.entries(byYear)) {
    if (val != null) known.push([Number(yStr), val])
  }
  if (known.length === 0) return null
  known.sort((a, b) => a[0] - b[0])

  if (year <= known[0][0]) return known[0][1]
  if (year >= known[known.length - 1][0]) return known[known.length - 1][1]

  let ki = 0
  while (ki < known.length - 2 && known[ki + 1][0] <= year) ki++
  const [y0, v0] = known[ki]
  const [y1, v1] = known[ki + 1]
  if (y1 === y0) return v0
  const t = (year - y0) / (y1 - y0)
  return v0 + t * (v1 - v0)
}

type IdleHandle = { kind: 'idle' | 'timeout'; id: number }

function scheduleIdleTask(task: () => void, timeoutMs: number): IdleHandle {
  const win = window as Window & {
    requestIdleCallback?: (callback: (deadline: IdleDeadline) => void, options?: { timeout: number }) => number
  }
  if (typeof win.requestIdleCallback === 'function') {
    return { kind: 'idle', id: win.requestIdleCallback(() => task(), { timeout: timeoutMs }) }
  }
  return { kind: 'timeout', id: window.setTimeout(task, 16) }
}

function cancelIdleTask(handle: IdleHandle | null) {
  if (!handle) return
  if (handle.kind === 'idle') {
    const win = window as Window & { cancelIdleCallback?: (id: number) => void }
    win.cancelIdleCallback?.(handle.id)
    return
  }
  clearTimeout(handle.id)
}

/** Compute adaptive split default based on viewport width */
function getAdaptiveSplitDefault(width: number): number {
  if (width >= BREAKPOINTS.DESKTOP_XL) return 0.67
  if (width >= BREAKPOINTS.DESKTOP) return 0.60
  if (width >= BREAKPOINTS.TABLET_LANDSCAPE) return 0.55
  return 0.50
}

/** On mobile, the graph's vertical anchor is at 1/6 of viewport (center of top 1/3).
 *  On desktop, it's the normal center (1/2). */
function getGraphCenterY(h: number): number {
  return window.innerWidth < BREAKPOINTS.TABLET ? h / 3 : h / 2
}

function App() {
  const viewport = useViewport()
  const svgRef = useRef<SVGSVGElement>(null)
  const tutorialRef = useRef<TutorialHandle>({} as TutorialHandle)
  const tutorialCompRef = useRef<TutorialRef>(null)
  const [tutorialActive, setTutorialActive] = useState(false)
  const zoomRef = useRef<d3.ZoomBehavior<SVGSVGElement, unknown> | null>(null)
  const currentTransformRef = useRef<d3.ZoomTransform | null>(null)
  const prevVisibleNodeIdsRef = useRef<Set<string>>(new Set())
  const prevVisibleEdgeIdsRef = useRef<Set<string>>(new Set())
  const prevViewModeForVizRef = useRef<ViewMode>('global')  // Track view mode changes in visualization
  const prevSplitRatioRef = useRef<number>(getAdaptiveSplitDefault(window.innerWidth))  // Track split ratio changes
  const nodePositionsRef = useRef<Map<string, { x: number; y: number; parentId: string | null }>>(new Map())
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [_stats, setStats] = useState<{
    nodes: number
    structuralEdges: number
    outcomes: number
    drivers: number
    overlaps: number
  } | null>(null)
  const [domainCounts, setDomainCounts] = useState<Record<string, number>>({})
  const qolNodePositionRef = useRef<{ x: number; y: number } | null>(null)  // QoL node screen position for loading spinner
  const spinnerElRef = useRef<HTMLDivElement | null>(null)  // Direct DOM ref for spinner positioning
  const [hoveredNode, setHoveredNode] = useState<ExpandableNode | null>(null)
  const [simulateBtnHovered, setSimulateBtnHovered] = useState(false)
  const [dataQualityOpen, setDataQualityOpen] = useState(false)
  // Mobile minimized states: panel hidden but button stays colored
  const [simMinimized, setSimMinimized] = useState(false)
  const [dqMinimized, setDqMinimized] = useState(false)
  const [dataQualityBtnHovered, setDataQualityBtnHovered] = useState(false)
  const tooltipNodeRef = useRef<ExpandableNode | null>(null)  // Caches last hovered node for smooth tooltip fade
  const tooltipShowTimerRef = useRef<number | null>(null)
  const [ringStats, setRingStats] = useState<Array<{ label: string; count: number; minDistance: number }>>([])
  const [_fps, setFps] = useState<number>(0)

  // Search state
  const [searchQuery, setSearchQuery] = useState('')
  const [searchResults, setSearchResults] = useState<SearchableNode[]>([])
  const [showSearchResults, setShowSearchResults] = useState(false)
  const [domainFilter] = useState<string>('')  // Domain filter removed from UI for space
  const [recentSearches, setRecentSearches] = useState<string[]>([])
  const [showRecentSearches, setShowRecentSearches] = useState(false)
  const searchInputRef = useRef<HTMLInputElement>(null)
  const recentSearchesTimeoutRef = useRef<number | null>(null)
  const [highlightedPath, setHighlightedPath] = useState<Set<string>>(new Set())
  const [highlightedTarget, setHighlightedTarget] = useState<string | null>(null)  // The searched node itself
  const [highlightSource, setHighlightSource] = useState<'search' | 'sim'>('search')

  // View mode state (Global vs Local)
  const [viewMode, setViewMode] = useState<ViewMode>('global')
  const [localViewTargets, setLocalViewTargets] = useState<string[]>([])
  const [localViewBetaThreshold, setLocalViewBetaThreshold] = useState(0.5)  // Synced from LocalView
  const [localViewInputDepth, setLocalViewInputDepth] = useState(1)  // Global depth for causes
  const [localViewOutputDepth, setLocalViewOutputDepth] = useState(1)  // Global depth for effects
  const [splitRatio, setSplitRatio] = useState(() => getAdaptiveSplitDefault(window.innerWidth))
  const userAdjustedSplitRef = useRef(false) // Track if user manually dragged the split divider
  const [drillDownHistory, setDrillDownHistory] = useState<{ prevTargets: string[]; prevBeta: number } | null>(null)
  const isDraggingRef = useRef(false)
  const mKeyRef = useRef<{ down: boolean; time: number; origForeground: boolean }>({ down: false, time: 0, origForeground: false })
  const localViewResetRef = useRef<(() => void) | null>(null)  // Store LocalView's reset function
  const urlStateRestoredRef = useRef(false)  // Track if URL state has been restored
  const pendingExpandedNodesRef = useRef<string[] | null>(null)  // Expanded nodes from URL, applied after raw data loads
  const clickTimeoutRef = useRef<number | null>(null)  // For delayed single-click to allow double-click
  const layoutReadyTimerRef = useRef<number | null>(null)  // Debounced layout-ready signal timer
  const resetExpandTimerRef = useRef<number | null>(null)
  const resetFitTimerRef = useRef<number | null>(null)
  const structuralTraceIdRef = useRef<number | null>(null)
  const structuralTraceFinalizeTimerRef = useRef<number | null>(null)
  const structuralTraceScheduledIdRef = useRef<number | null>(null)
  const structuralLockUntilRef = useRef(0)
  const structuralLockTimerRef = useRef<number | null>(null)
  const queuedStructuralActionRef = useRef<(() => void) | null>(null)
  const activeLayoutActionRef = useRef<LayoutAction | null>(null)
  const activeLayoutBudgetRef = useRef<LayoutBudget | null>(null)
  const activeLayoutRunIdRef = useRef(0)
  const autoZoomDelayTimerRef = useRef<number | null>(null)
  const autoZoomRafRef = useRef<number | null>(null)
  const autoZoomRunTokenRef = useRef(0)
  const visibleCountsRef = useRef({ nodes: 0, edges: 0 })
  const outcomeSectorSnapshotRef = useRef<OutcomeSectorSnapshot | null>(null)
  const preSimulationExpandedNodesRef = useRef<Set<string>>(new Set())
  const preSimulationPinnedPathsRef = useRef<Set<string>>(new Set())
  const [sidebarOpen, setSidebarOpen] = useState(false)
  const restoreNavAfterClearRef = useRef(false)
  const focusedGraphNodeIdRef = useRef<string | null>(null)
  const graphNavActiveRef = useRef(false)
  const graphNavModelRef = useRef<GraphNavModel | null>(null)
  const focusGraphNodeByIdRef = useRef<((nodeId: string) => boolean) | null>(null)
  const pendingExpandedBranchFocusRef = useRef<string | null>(null)
  const lastGraphAnnounceRef = useRef<{ message: string; at: number }>({ message: '', at: 0 })

  // Temporal edges cache for Local View timeline playback
  // Maps year → country edges for the currently selected country/stratum
  const temporalEdgesCacheRef = useRef<Map<number, CountryGraphEdge[]>>(new Map())
  const [temporalEdgesLoading, setTemporalEdgesLoading] = useState(false)
  const [temporalEdgesCacheKey, setTemporalEdgesCacheKey] = useState<string | null>(null)  // Track cache key (triggers re-render)
  const temporalEdgesCountryRef = useRef<string | null>(null)  // Track which country/stratum the cache is for
  const temporalEdgesLoadIdRef = useRef(0)  // Guard loading state against overlapping aborted runs

  // Country-specific data from simulation store
  const {
    countryGraph,
    selectedCountry,
    clearCountry,
    togglePanel,
    openPanel,
    temporalResults,
    historicalTimeline,
    temporalShapTimeline,
    stratifiedShapTimeline,
    playbackMode,
    currentYearIndex,
    loadUnifiedTimeline,
    shapTimelineLoading,
    timelineLoading,
    countryLoading,
    selectedStratum,
    setStratum,
    loadAllClassifications,
    interventions: storeInterventions,
    targetVisibleEffects,
    isPlaying,
    play: storePlay,
    pause: storePause,
    setPlaybackMode,
    layoutReady,
    setLayoutReady,
    highlightedIndicator,
    setHighlightedIndicator,
    clearResults,
    mapForeground,
    qolScores,
    loadQolScores,
    classificationsCache,
    setCountry: storeSetCountry,
    setMapHoveredCountry,
    selectedRegion,
    setSelectedRegion,
    mapViewMode,
  } = useSimulationStore()
  const isPanelOpen = useIsPanelOpen()

  // Derive selected country's iso3 for map outline
  const selectedCountryIso3 = useMemo(() => {
    if (!selectedCountry || !classificationsCache) return null
    // eslint-disable-next-line @typescript-eslint/no-explicit-any
    const data = (classificationsCache.classifications as any)?.[selectedCountry]
    return data?.iso3 as string | null ?? null
  }, [selectedCountry, classificationsCache])

  const graphNavEnabled = viewMode === 'global' && !mapForeground && !error

  const announceGraphNav = useCallback((message: string) => {
    const now = performance.now()
    const { message: lastMessage, at: lastAt } = lastGraphAnnounceRef.current
    if (lastMessage === message && now - lastAt < GRAPH_ANNOUNCE_DEDUPE_MS) return
    lastGraphAnnounceRef.current = { message, at: now }
    announce(message)
  }, [])

  const startStructuralTrace = useCallback((action: StructuralActionName, details?: Record<string, unknown>) => {
    if (!import.meta.env.DEV) return
    if (structuralTraceFinalizeTimerRef.current !== null) {
      clearTimeout(structuralTraceFinalizeTimerRef.current)
      structuralTraceFinalizeTimerRef.current = null
    }

    const previousId = structuralTraceIdRef.current
    if (previousId !== null) {
      perfTrace.finish(previousId, {
        nodeCountAfter: visibleCountsRef.current.nodes,
        edgeCountAfter: visibleCountsRef.current.edges,
        animationWindowMs: 0,
      })
      structuralTraceIdRef.current = null
      structuralTraceScheduledIdRef.current = null
    }

    structuralTraceIdRef.current = perfTrace.start({
      action,
      nodeCountBefore: visibleCountsRef.current.nodes,
      edgeCountBefore: visibleCountsRef.current.edges,
      details,
    })
    structuralTraceScheduledIdRef.current = null
  }, [])

  const finalizeStructuralTrace = useCallback((animationWindowMs: number) => {
    const traceId = structuralTraceIdRef.current
    if (import.meta.env.DEV && traceId !== null) {
      perfTrace.finish(traceId, {
        nodeCountAfter: visibleCountsRef.current.nodes,
        edgeCountAfter: visibleCountsRef.current.edges,
        animationWindowMs: Math.max(0, Math.round(animationWindowMs)),
      })
    }
    structuralTraceIdRef.current = null
    structuralTraceScheduledIdRef.current = null
    structuralTraceFinalizeTimerRef.current = null
    activeLayoutActionRef.current = null
    activeLayoutBudgetRef.current = null
  }, [])

  const noteStructuralZoomOverlap = useCallback(() => {
    if (!import.meta.env.DEV) return
    perfTrace.noteZoomOverlap(structuralTraceIdRef.current)
  }, [])

  const resetOutcomeSectorCache = useCallback(() => {
    outcomeSectorSnapshotRef.current = null
    if (import.meta.env.DEV) {
      layoutTrace.reset()
    }
  }, [])

  const flushQueuedStructuralAction = useCallback(() => {
    const queuedAction = queuedStructuralActionRef.current
    if (!queuedAction) return
    queuedStructuralActionRef.current = null
    queuedAction()
  }, [])

  const setStructuralLock = useCallback((lockMs: number) => {
    const nextLockMs = Math.max(0, Math.round(lockMs))
    if (structuralLockTimerRef.current !== null) {
      clearTimeout(structuralLockTimerRef.current)
      structuralLockTimerRef.current = null
    }

    if (nextLockMs === 0) {
      structuralLockUntilRef.current = 0
      flushQueuedStructuralAction()
      return
    }

    structuralLockUntilRef.current = performance.now() + nextLockMs
    structuralLockTimerRef.current = window.setTimeout(() => {
      structuralLockTimerRef.current = null
      structuralLockUntilRef.current = 0
      flushQueuedStructuralAction()
    }, nextLockMs)
  }, [flushQueuedStructuralAction])

  const runOrQueueStructuralAction = useCallback((runner: () => void) => {
    if (performance.now() < structuralLockUntilRef.current) {
      queuedStructuralActionRef.current = runner
      return false
    }
    runner()
    return true
  }, [])

  const cancelStructuralTransitions = useCallback(() => {
    if (!svgRef.current) return
    const svg = d3.select(svgRef.current)
    const graphContainer = svg.select<SVGGElement>('g.graph-container')
    if (graphContainer.empty()) return

    graphContainer.selectAll('circle.node').interrupt('rotation').interrupt('timeline-size').interrupt('node-exit')
    graphContainer.selectAll('line.edge').interrupt('rotation').interrupt('edge-exit')
    graphContainer.selectAll('text.node-label').interrupt('rotation').interrupt('label-exit')
    graphContainer.selectAll('circle.glow').interrupt('glow-move').interrupt('glow-show')
    graphContainer.selectAll('circle.local-glow').interrupt('local-glow-move').interrupt('local-glow-show')
    graphContainer.selectAll('circle.sim-glow').interrupt('sim-glow-move').interrupt('sim-glow-show')
  }, [])

  const beginLayoutAction = useCallback(
    (layoutAction: LayoutAction, traceAction: StructuralActionName, details?: Record<string, unknown>) => {
      cancelStructuralTransitions()
      activeLayoutActionRef.current = layoutAction
      activeLayoutBudgetRef.current = null
      activeLayoutRunIdRef.current += 1
      startStructuralTrace(traceAction, { ...details, layoutAction })
      setStructuralLock(STRUCTURAL_LOCK_FALLBACK_MS)
    },
    [cancelStructuralTransitions, startStructuralTrace, setStructuralLock]
  )

  // Sync highlighted indicator from results table → graph highlight (single node, no expansion)
  useEffect(() => {
    if (highlightedIndicator) {
      setHighlightedPath(new Set([highlightedIndicator]))
      setHighlightedTarget(highlightedIndicator)
      if (highlightSource !== 'sim') {
        setHighlightSource('sim')
      }
    } else {
      // Only clear if the current highlight is from sim (don't clobber search highlights)
      if (highlightSource === 'sim') {
        setHighlightedPath(new Set())
        setHighlightedTarget(null)
      }
    }
  }, [highlightedIndicator, highlightSource])

  // Clear indicator highlight when panel closes or results cleared
  useEffect(() => {
    if (!isPanelOpen || !temporalResults) {
      setHighlightedIndicator(null)
    }
  }, [isPanelOpen, temporalResults, setHighlightedIndicator])

  useEffect(() => {
    if (graphNavEnabled) return

    graphNavActiveRef.current = false
    focusedGraphNodeIdRef.current = null
    graphNavModelRef.current = null
    focusGraphNodeByIdRef.current = null
    pendingExpandedBranchFocusRef.current = null
    lastGraphAnnounceRef.current = { message: '', at: 0 }

    const activeEl = document.activeElement
    if (activeEl instanceof SVGCircleElement && activeEl.classList.contains('node')) {
      activeEl.blur()
    }

    if (!svgRef.current) return
    const svg = d3.select(svgRef.current)
    svg.select<SVGGElement>('g.graph-container')
      .selectAll<SVGCircleElement, ExpandableNode>('circle.node')
      .attr('tabindex', -1)
  }, [graphNavEnabled])

  useEffect(() => {
    const handleTabIntoGraph = (event: KeyboardEvent) => {
      if (!graphNavEnabled || event.key !== 'Tab' || event.shiftKey) return

      const activeEl = document.activeElement
      const noCurrentFocus =
        activeEl === null
        || activeEl === document.body
        || activeEl === document.documentElement
      if (!noCurrentFocus) return

      const rootId = graphNavModelRef.current?.rootId
      const focusNode = focusGraphNodeByIdRef.current
      if (!rootId || !focusNode) return

      event.preventDefault()
      focusNode(rootId)
    }

    window.addEventListener('keydown', handleTabIntoGraph, true)
    return () => window.removeEventListener('keydown', handleTabIntoGraph, true)
  }, [graphNavEnabled])

  // Current year derived from active playback source (historical SHAP vs simulation timeline)
  const mapCurrentYear = useMemo(() => {
    if (playbackMode === 'simulation' && temporalResults) {
      return temporalResults.base_year + currentYearIndex
    }
    // Stratified timeline only applies when no country/region scope is active.
    if (
      !selectedCountry
      && !selectedRegion
      && selectedStratum !== 'unified'
      && stratifiedShapTimeline?.years?.[currentYearIndex] !== undefined
    ) {
      return stratifiedShapTimeline.years[currentYearIndex]
    }
    // Use historicalTimeline (filtered/effective years) first since currentYearIndex
    // indexes into it, not the full unfiltered temporalShapTimeline
    return historicalTimeline?.years?.[currentYearIndex]
      ?? temporalShapTimeline?.years?.[currentYearIndex] ?? 2020
  }, [
    playbackMode,
    temporalResults,
    currentYearIndex,
    selectedCountry,
    selectedRegion,
    selectedStratum,
    stratifiedShapTimeline,
    temporalShapTimeline,
    historicalTimeline
  ])

  // Apply simulation QoL delta to selected country on the map during simulation playback.
  const mapSimAdjustments = useMemo(() => {
    if (playbackMode !== 'simulation' || !temporalResults?.qol_timeline || !selectedCountry || !classificationsCache) {
      return undefined
    }
    const qolYear = temporalResults.qol_timeline[String(mapCurrentYear)]
    if (!qolYear) return undefined

    const iso3 = classificationsCache.classifications[selectedCountry]?.iso3
    if (!iso3) return undefined

    const base: Record<string, number> = { [iso3]: qolYear.delta }

    return base
  }, [playbackMode, temporalResults, selectedCountry, classificationsCache, mapCurrentYear, currentYearIndex])

  // Scope filter for regional QoL aggregation.
  const selectedRegionIso3s = useMemo(() => {
    if (!selectedRegion) return null
    return new Set(REGION_TO_ISO3S[selectedRegion] || [])
  }, [selectedRegion])

  // Compute historical QoL for active scope at a specific year.
  const getHistoricalScopeQol = useCallback((year: number): number | null => {
    if (!qolScores) return null

    if (selectedCountry) {
      const countryData = qolScores[selectedCountry]
      if (!countryData?.by_year) return null
      return interpolateQol(countryData.by_year, year)
    }

    const scores: number[] = []
    for (const [countryName, countryData] of Object.entries(qolScores)) {
      if (!countryData?.by_year) continue
      if (selectedRegionIso3s && !selectedRegionIso3s.has(countryData.iso3)) continue
      const val = interpolateQol(countryData.by_year, year)
      if (val == null) continue

      if (!selectedRegionIso3s && selectedStratum !== 'unified' && classificationsCache) {
        const yearStr = String(year)
        const cc = classificationsCache.classifications[countryName] as { by_year?: Record<string, { classification_3tier?: string }> } | undefined
        const tier = cc?.by_year?.[yearStr]?.classification_3tier?.toLowerCase()
        if (tier !== selectedStratum) continue
      }
      scores.push(val)
    }
    return scores.length > 0 ? scores.reduce((a, b) => a + b, 0) / scores.length : null
  }, [qolScores, selectedCountry, selectedRegionIso3s, selectedStratum, classificationsCache])

  // Component-level QoL score for tooltip/JSX (mirrors D3 render cycle computation).
  // In simulation playback, prefer the simulated QoL timeline so text updates live.
  const qolNodeScoreForTooltip = useMemo(() => {
    if (playbackMode === 'simulation' && temporalResults?.qol_timeline) {
      const simYear = String(temporalResults.base_year + currentYearIndex)
      const simQol = temporalResults.qol_timeline[simYear]
      if (simQol) return simQol.simulated
    }
    return getHistoricalScopeQol(mapCurrentYear)
  }, [playbackMode, temporalResults, currentYearIndex, mapCurrentYear, getHistoricalScopeQol])

  // Load all classifications once at startup (cached for other features)
  useEffect(() => {
    loadAllClassifications()
  }, [loadAllClassifications])

  // Load QOL scores for world map background layer
  useEffect(() => {
    loadQolScores()
  }, [loadQolScores])

  // Cleanup any pending layout-ready timer on unmount
  useEffect(() => {
    return () => {
      if (layoutReadyTimerRef.current !== null) {
        clearTimeout(layoutReadyTimerRef.current)
        layoutReadyTimerRef.current = null
      }
      if (structuralTraceFinalizeTimerRef.current !== null) {
        clearTimeout(structuralTraceFinalizeTimerRef.current)
        structuralTraceFinalizeTimerRef.current = null
      }
      if (structuralLockTimerRef.current !== null) {
        clearTimeout(structuralLockTimerRef.current)
        structuralLockTimerRef.current = null
      }
      if (autoZoomDelayTimerRef.current !== null) {
        clearTimeout(autoZoomDelayTimerRef.current)
        autoZoomDelayTimerRef.current = null
      }
      if (autoZoomRafRef.current !== null) {
        cancelAnimationFrame(autoZoomRafRef.current)
        autoZoomRafRef.current = null
      }
      if (tooltipShowTimerRef.current !== null) {
        clearTimeout(tooltipShowTimerRef.current)
        tooltipShowTimerRef.current = null
      }
      if (resetExpandTimerRef.current !== null) {
        clearTimeout(resetExpandTimerRef.current)
        resetExpandTimerRef.current = null
      }
      if (resetFitTimerRef.current !== null) {
        clearTimeout(resetFitTimerRef.current)
        resetFitTimerRef.current = null
      }
      if (collapseGuardTimerRef.current !== null) {
        clearTimeout(collapseGuardTimerRef.current)
        collapseGuardTimerRef.current = null
      }
      if (structuralTraceIdRef.current !== null) {
        perfTrace.finish(structuralTraceIdRef.current, {
          nodeCountAfter: visibleCountsRef.current.nodes,
          edgeCountAfter: visibleCountsRef.current.edges,
          animationWindowMs: 0,
        })
        structuralTraceIdRef.current = null
      }
    }
  }, [])

  // Handle split divider drag
  const handleDividerMouseDown = useCallback((e: React.MouseEvent) => {
    e.preventDefault()
    isDraggingRef.current = true
    document.body.style.cursor = 'col-resize'
    document.body.style.userSelect = 'none'

    const handleMouseMove = (moveEvent: MouseEvent) => {
      if (!isDraggingRef.current) return
      const container = document.querySelector('.split-container') as HTMLElement
      if (!container) return
      const rect = container.getBoundingClientRect()
      const newRatio = Math.max(0.2, Math.min(0.8, (moveEvent.clientX - rect.left) / rect.width))
      setSplitRatio(newRatio)
      userAdjustedSplitRef.current = true
    }

    const handleMouseUp = () => {
      isDraggingRef.current = false
      document.body.style.cursor = ''
      document.body.style.userSelect = ''
      document.removeEventListener('mousemove', handleMouseMove)
      document.removeEventListener('mouseup', handleMouseUp)
    }

    document.addEventListener('mousemove', handleMouseMove)
    document.addEventListener('mouseup', handleMouseUp)
  }, [])

  // Update split ratio when viewport changes (only if user hasn't manually dragged)
  useEffect(() => {
    if (!userAdjustedSplitRef.current) {
      setSplitRatio(getAdaptiveSplitDefault(viewport.width))
    }
  }, [viewport.width])

  // Auto-switch from split to local when viewport drops below 1024px
  useEffect(() => {
    if (viewport.isBelow(1024)) {
      setViewMode(prev => prev === 'split' ? 'local' : prev)
    }
  }, [viewport.width, viewport.isBelow])

  // Auto-close sidebar drawer when a panel opens on mobile (phones only)
  useEffect(() => {
    if (viewport.isBelow(768) && (isPanelOpen || dataQualityOpen)) {
      setSidebarOpen(false)
    }
  }, [isPanelOpen, dataQualityOpen, viewport])

  // Reset minimized state when panel is fully closed (X button)
  useEffect(() => {
    if (!isPanelOpen) setSimMinimized(false)
  }, [isPanelOpen])
  useEffect(() => {
    if (!dataQualityOpen) setDqMinimized(false)
  }, [dataQualityOpen])

  // Add a node to Local View targets
  const addToLocalView = useCallback((nodeId: string) => {
    setLocalViewTargets(prev => {
      if (prev.includes(nodeId)) return prev
      return [...prev, nodeId]
    })
    // Switch to local view when double-clicking from global view
    // Stay in local view if already there
    setViewMode(prev => prev === 'global' ? 'local' : prev)
    // Clear drill-down history (manual change invalidates undo)
    setDrillDownHistory(null)
  }, [])

  // Remove a node from Local View targets
  const removeFromLocalView = useCallback((nodeId: string) => {
    setLocalViewTargets(prev => prev.filter(id => id !== nodeId))
    // Clear drill-down history (manual change invalidates undo)
    setDrillDownHistory(null)
  }, [])

  // Clear working context in the current scope (country/region/stratum preserved).
  const clearWorkingContext = useCallback(() => {
    restoreNavAfterClearRef.current = temporalResults !== null
    setLocalViewTargets([])
    setDrillDownHistory(null)
    if (viewMode !== 'global') {
      setViewMode('global')
    }
    setHighlightedPath(new Set())
    setHighlightedTarget(null)
    setHoveredNode(null)
    tooltipNodeRef.current = null
    setPinnedPaths(new Set())
    setHighlightedIndicator(null)
    clearResults()
  }, [viewMode, temporalResults, clearResults, setHighlightedIndicator])

  // Viewport-aware layout engine
  const viewportLayoutRef = useRef<ViewportAwareLayout | null>(null)
  const [layoutValues, setLayoutValues] = useState<ReturnType<ViewportAwareLayout['getLayoutValues']> | null>(null)

  // Initialize viewport layout on mount
  useEffect(() => {
    const width = window.innerWidth
    const height = window.innerHeight
    const dpr = window.devicePixelRatio || 1

    viewportLayoutRef.current = createViewportLayout(width, height, dpr, 1, 100)
    viewportLayoutRef.current.logParameters()
    setLayoutValues(viewportLayoutRef.current.getLayoutValues())
  }, [])

  // Load unified temporal SHAP timeline on mount (for global view playback)
  useEffect(() => {
    loadUnifiedTimeline()
  }, [loadUnifiedTimeline])

  // Load temporal graphs for Local View timeline playback
  // This pre-fetches all years' edges so timeline scrubbing is instant
  // Works for country-specific, stratified, regional, AND unified views
  useEffect(() => {
    const loadId = ++temporalEdgesLoadIdRef.current

    // Only load when in local/split view
    if (viewMode === 'global') {
      setTemporalEdgesLoading(false)
      return
    }

    // Determine cache key: region > country > stratum > 'unified'
    const cacheKey = selectedRegion
      ? `region:${selectedRegion}`
      : selectedCountry || (selectedStratum !== 'unified' ? selectedStratum : 'unified')

    // Check if cache is already populated for this key
    if (temporalEdgesCountryRef.current === cacheKey && temporalEdgesCacheRef.current.size > 0) {
      debug.log('cache', `Temporal edges cache already populated for ${cacheKey}`)
      setTemporalEdgesLoading(false)
      return
    }

    // Fetch all available years, then load each year's graph
    const controller = new AbortController()

    const loadTemporalEdges = async () => {
      setTemporalEdgesLoading(true)

      try {
        // Get available years based on selection type
        // For regions, use the historicalTimeline years (already loaded by setSelectedRegion)
        let years: number[]
        if (selectedRegion) {
          // Use timeline years from the store (populated by setSelectedRegion)
          const timeline = useSimulationStore.getState().historicalTimeline
          years = timeline?.years ?? []
          if (years.length === 0) {
            debug.log('cache', `No timeline years for region ${selectedRegion}, skipping edge load`)
            return
          }
        } else {
          const yearsData = await simulationAPI.getCountryGraphYears(selectedCountry || 'unified')
          if (controller.signal.aborted) return
          years = yearsData.years
        }

        debug.log('cache', `Loading temporal edges for ${cacheKey}: ${years.length} years`)

        // Clear cache and set new key
        temporalEdgesCacheRef.current = new Map()
        temporalEdgesCountryRef.current = cacheKey
        setTemporalEdgesCacheKey(null)  // Clear state to prevent using stale data during load

        // Fetch graphs for all years in parallel (batched to avoid overwhelming the API)
        const BATCH_SIZE = 10
        for (let i = 0; i < years.length; i += BATCH_SIZE) {
          if (controller.signal.aborted) return
          const batch = years.slice(i, i + BATCH_SIZE)
          const results = await Promise.all(
            batch.map(year => {
              // Choose the right API based on selection
              if (selectedRegion) {
                return simulationAPI.getRegionalGraph(selectedRegion, controller.signal, year)
                  .then(g => ({ edges: g.edges }))
              } else if (selectedCountry) {
                return simulationAPI.getCountryTemporalGraph(selectedCountry, year, controller.signal)
              } else if (selectedStratum !== 'unified') {
                return simulationAPI.getStratifiedGraph(selectedStratum, year, controller.signal)
              } else {
                return simulationAPI.getUnifiedGraph(year, controller.signal)
              }
            }).map(p => p.catch(err => {
              if (controller.signal.aborted) return null
              debug.log('error', `Failed to load ${cacheKey}/${err}:`, err)
              return null
            }))
          )

          if (controller.signal.aborted) return

          // Store successful results in cache
          results.forEach((result, idx) => {
            if (result) {
              temporalEdgesCacheRef.current.set(batch[idx], result.edges)
            }
          })
        }

        if (controller.signal.aborted) return
        debug.log('cache', `Temporal edges cache populated: ${temporalEdgesCacheRef.current.size} years for ${cacheKey}`)
        // Update state to trigger re-render of effectiveEdges
        setTemporalEdgesCacheKey(cacheKey)
      } catch (err) {
        if (!controller.signal.aborted) {
          debug.log('error', 'Failed to load temporal edges:', err)
        }
      } finally {
        // Only the latest run can clear loading; prevents aborted prior runs from racing.
        if (temporalEdgesLoadIdRef.current === loadId) {
          setTemporalEdgesLoading(false)
        }
      }
    }

    loadTemporalEdges()
    return () => controller.abort()
    // timelineLoading in deps: when a region loads, the effect first runs while timeline is still
    // loading (empty years → early return), then re-runs when timelineLoading becomes false
  }, [selectedCountry, selectedRegion, selectedStratum, viewMode, timelineLoading, historicalTimeline])

  // Handle window resize
  useEffect(() => {
    const handleResize = () => {
      if (!viewportLayoutRef.current) return

      const width = window.innerWidth
      const height = window.innerHeight

      viewportLayoutRef.current.updateContext({ width, height })
      setLayoutValues(viewportLayoutRef.current.getLayoutValues())

      debug.viewport('[Viewport Resize] New dimensions:', width, 'x', height)
      viewportLayoutRef.current.logParameters()
    }

    // Debounce resize handler
    let resizeTimeout: ReturnType<typeof setTimeout>
    const debouncedResize = () => {
      clearTimeout(resizeTimeout)
      resizeTimeout = setTimeout(handleResize, 300)
    }

    window.addEventListener('resize', debouncedResize)
    return () => {
      window.removeEventListener('resize', debouncedResize)
      clearTimeout(resizeTimeout)
    }
  }, [])

  // Layout configuration
  const nodePadding = DEFAULT_NODE_PADDING
  // Ring radii are calculated dynamically based on visible nodes
  // Initial values are placeholders that get replaced on first layout computation
  const [ringRadii, setRingRadii] = useState<number[]>([0, 100, 180, 260, 340, 420])

  const ringConfigs = useMemo(
    () => generateRingConfigs(ringRadii),
    [ringRadii]
  )

  // Expansion state - tracks which nodes have their children visible
  const [expandedNodes, setExpandedNodes] = useState<Set<string>>(new Set())

  // Pinned paths - individual node IDs visible after simulation (no sibling expansion)
  const [pinnedPaths, setPinnedPaths] = useState<Set<string>>(new Set())

  // Preserve/restore global navigation context around simulation sessions.
  const prevTemporalResultsRef = useRef(temporalResults)
  useEffect(() => {
    const wasPresent = prevTemporalResultsRef.current !== null
    prevTemporalResultsRef.current = temporalResults
    const isNowPresent = temporalResults !== null

    if (!wasPresent && isNowPresent) {
      preSimulationExpandedNodesRef.current = new Set(expandedNodes)
      preSimulationPinnedPathsRef.current = new Set(pinnedPaths)
      return
    }

    if (wasPresent && !isNowPresent) {
      resetOutcomeSectorCache()
      if (restoreNavAfterClearRef.current) {
        restoreNavAfterClearRef.current = false
        setExpandedNodes(new Set(preSimulationExpandedNodesRef.current))
        setPinnedPaths(new Set(preSimulationPinnedPathsRef.current))
      } else {
        setExpandedNodes(new Set())
        setPinnedPaths(new Set())
      }
    }
  }, [temporalResults, expandedNodes, pinnedPaths, resetOutcomeSectorCache])

  // Track if initial expansion after data load has happened
  const initialExpansionDoneRef = useRef(false)

  // Cache last valid SHAP importance values (used during loading to maintain node sizes)
  const lastValidShapRef = useRef<Map<string, number>>(new Map())

  // Dots mode: when true, deep-ring nodes (ring >= 4) render as lightweight dots
  // (no labels, no glows, no transitions). Activated by Rings menu bulk expansion,
  // deactivated by individual node clicks.
  const dotsModeRef = useRef(false)

  // Track last expansion action for auto-zoom
  const pendingZoomRef = useRef<{ nodeId: string; action: 'expand' | 'collapse' } | null>(null)
  const isAnimatingZoomRef = useRef(false)

  // Track collapse animation to prevent second render from overriding delayed rotation
  const collapseAnimationRef = useRef<{ inProgress: boolean; endTime: number }>({ inProgress: false, endTime: 0 })
  const collapseGuardTimerRef = useRef<number | null>(null)

  // Raw data (fetched once, cached)
  const [rawData, setRawData] = useState<GraphDataV21 | null>(null)

  // Topology/context boundaries invalidate cached outcome sectors.
  useEffect(() => {
    resetOutcomeSectorCache()
  }, [rawData, selectedCountry, selectedRegion, selectedStratum, playbackMode, resetOutcomeSectorCache])

  // Memoized node lookup map for Local View
  const nodeByIdMap = useMemo(() => {
    if (!rawData) return new Map<string, RawNodeV21>()
    return new Map(rawData.nodes.map(n => [String(n.id), n]))
  }, [rawData])

  // Effective edges for Local View: uses year-specific edges when in local view with timeline
  // Works for country-specific, stratified, regional, AND unified views
  const effectiveEdges = useMemo(() => {
    if (!rawData) return []

    // Get hierarchical edges from unified model (always needed)
    const hierarchicalEdges = rawData.edges.filter(e => e.relationship === 'hierarchical')

    // Determine current year from the effective timeline (historicalTimeline has filtered years
    // matching currentYearIndex, while temporalShapTimeline may have extra zero-data years)
    const currentYear = historicalTimeline?.years?.[currentYearIndex]
      ?? temporalShapTimeline?.years?.[currentYearIndex]

    // Check if we're in local/split view with temporal edges available
    if ((viewMode === 'local' || viewMode === 'split') && currentYear && !temporalEdgesLoading) {
      // Cache key matches the loading logic: region > country > stratum > unified
      const cacheKey = selectedRegion
        ? `region:${selectedRegion}`
        : selectedCountry || (selectedStratum !== 'unified' ? selectedStratum : 'unified')
      const cachedEdges = temporalEdgesCacheRef.current.get(currentYear)

      // Use cached edges if available and cache key matches
      if (cachedEdges && temporalEdgesCacheKey === cacheKey) {
        // Use year-specific edges from cache
        const causalEdges = countryGraphToRawEdges(cachedEdges, true)
        debug.log('localview', `Using temporal edges for ${cacheKey}/${currentYear}: ${cachedEdges.length} edges`)
        return [...hierarchicalEdges, ...causalEdges]
      }
    }

    // If a country or region is selected, use static countryGraph edges as fallback
    if ((selectedCountry || selectedRegion) && countryGraph?.edges) {
      const countryCausalEdges = countryGraphToRawEdges(countryGraph.edges, true)
      return [...hierarchicalEdges, ...countryCausalEdges]
    }

    // No country/region selected or no cached edges: use static unified model edges
    return rawData.edges
  }, [
    rawData,
    selectedCountry,
    selectedRegion,
    selectedStratum,
    countryGraph,
    viewMode,
    temporalShapTimeline,
    historicalTimeline,
    currentYearIndex,
    temporalEdgesLoading,
    temporalEdgesCacheKey
  ])

  /**
   * Pre-compute SHAP and CI caches after initial paint (idle) to avoid blocking LCP.
   * When stratum != unified (and no country/region), use stratified timeline.
   */
  const effectiveShapTimeline = useMemo(() => {
    if (selectedStratum !== 'unified' && !selectedCountry && !selectedRegion && stratifiedShapTimeline) {
      return stratifiedShapTimeline
    }
    return temporalShapTimeline
  }, [selectedStratum, selectedCountry, selectedRegion, stratifiedShapTimeline, temporalShapTimeline])

  // Build parent-child map once; reused for SHAP and CI precompute.
  const childrenMap = useMemo(() => {
    const map = new Map<string | number, string[]>()
    if (!rawData) return map
    for (const node of rawData.nodes) {
      if (node.children) map.set(node.id, node.children.map(c => String(c)))
    }
    return map
  }, [rawData])

  const rootNodeId = useMemo(() => rawData?.nodes.find(n => n.layer === 0)?.id ?? null, [rawData])

  const computeYearImportance = useCallback((year: number): Map<string, number> => {
    const yearImportance = new Map<string, number>()
    if (!rawData || !effectiveShapTimeline) return yearImportance

      const shapValues = effectiveShapTimeline.shap_by_year[String(year)]
      if (!shapValues) return yearImportance

      // First pass: assign SHAP to Ring 5 indicators.
      for (const node of rawData.nodes) {
        if (node.layer !== 5) continue
        const shapValue = shapValues[String(node.id)]
        if (shapValue === undefined || shapValue === null) continue
        const rawImportance = typeof shapValue === 'object' && 'mean' in shapValue
          ? shapValue.mean
          : shapValue
        if (!Number.isFinite(rawImportance)) continue
        yearImportance.set(String(node.id), Math.abs(rawImportance))
      }

    // Aggregate up hierarchy (Ring 4 -> Ring 0) using sums.
    for (let ring = 4; ring >= 0; ring -= 1) {
      for (const node of rawData.nodes) {
        if (node.layer !== ring) continue
        const childIds = childrenMap.get(node.id) || []
        let sumShap = 0
        let hasChildData = false
        for (const childId of childIds) {
          const childShap = yearImportance.get(String(childId))
          if (childShap !== undefined) {
            sumShap += childShap
            hasChildData = true
          }
        }
        if (hasChildData) yearImportance.set(String(node.id), sumShap)
      }
    }

    // Normalize to root mean = 1.0.
    const rootShap = rootNodeId != null ? (yearImportance.get(String(rootNodeId)) || 1) : 1
    if (rootShap > 0) {
      for (const [nodeId, shap] of yearImportance.entries()) {
        yearImportance.set(nodeId, shap / rootShap)
      }
    }

    return yearImportance
  }, [rawData, effectiveShapTimeline, childrenMap, rootNodeId])

  interface NodeCIData {
    mean: number
    std: number
    ci_lower: number
    ci_upper: number
    n_children?: number
    child_coverage?: number
  }

  const computeYearCI = useCallback((year: number): Map<string, NodeCIData> => {
    const yearCI = new Map<string, NodeCIData>()
    if (!rawData || !effectiveShapTimeline) return yearCI

    const shapValues = effectiveShapTimeline.shap_by_year[String(year)]
    if (!shapValues) return yearCI

    // First pass: extract CI values for Ring 5.
    for (const node of rawData.nodes) {
      if (node.layer !== 5) continue
      const shapValue = shapValues[String(node.id)]
      if (shapValue === undefined || shapValue === null) continue
      if (typeof shapValue === 'object' && 'mean' in shapValue) {
        yearCI.set(String(node.id), {
          mean: shapValue.mean,
          std: shapValue.std,
          ci_lower: shapValue.ci_lower,
          ci_upper: shapValue.ci_upper
        })
      } else {
        yearCI.set(String(node.id), {
          mean: shapValue as number,
          std: 0,
          ci_lower: shapValue as number,
          ci_upper: shapValue as number
        })
      }
    }

    // Second pass: aggregate uncertainty up hierarchy.
    for (let ring = 4; ring >= 0; ring -= 1) {
      for (const node of rawData.nodes) {
        if (node.layer !== ring) continue
        const childIds = childrenMap.get(node.id) || []
        const childCIs: NodeCIData[] = []
        for (const childId of childIds) {
          const childCI = yearCI.get(String(childId))
          if (childCI) childCIs.push(childCI)
        }
        if (childCIs.length === 0) continue
        const sumMean = childCIs.reduce((acc, c) => acc + c.mean, 0)
        const sumVariance = childCIs.reduce((acc, c) => acc + c.std * c.std, 0)
        const propagatedStd = Math.sqrt(sumVariance)
        yearCI.set(String(node.id), {
          mean: sumMean,
          std: propagatedStd,
          ci_lower: sumMean - 1.96 * propagatedStd,
          ci_upper: sumMean + 1.96 * propagatedStd,
          n_children: childIds.length,
          child_coverage: childCIs.length / childIds.length
        })
      }
    }

    // Normalize to root mean = 1.0.
    const rootMean = rootNodeId != null ? (yearCI.get(String(rootNodeId))?.mean || 1) : 1
    if (rootMean > 0) {
      for (const [nodeId, ci] of yearCI.entries()) {
        yearCI.set(nodeId, {
          ...ci,
          mean: ci.mean / rootMean,
          std: ci.std / rootMean,
          ci_lower: ci.ci_lower / rootMean,
          ci_upper: ci.ci_upper / rootMean
        })
      }
    }

    return yearCI
  }, [rawData, effectiveShapTimeline, childrenMap, rootNodeId])

  const [precomputedShapCache, setPrecomputedShapCache] = useState<Map<number, Map<string, number>>>(new Map())
  const [precomputedCICache, setPrecomputedCICache] = useState<Map<number, Map<string, NodeCIData>>>(new Map())

  // SHAP cache: seed the first available year quickly, then finish the rest in idle chunks.
  // Important: do not depend on currentYearIndex/historicalTimeline; scrubbing should not restart this pipeline.
  useEffect(() => {
    if (!effectiveShapTimeline || !rawData) return

    const years = [...effectiveShapTimeline.years]
    if (years.length === 0) return

    const cache = new Map<number, Map<string, number>>()
    let cancelled = false
    let idleHandle: IdleHandle | null = null

    const primeYear = years[0]
    const primeIndex = years.indexOf(primeYear)
    if (primeIndex >= 0) {
      cache.set(primeYear, computeYearImportance(primeYear))
      years.splice(primeIndex, 1)
      setPrecomputedShapCache(new Map(cache))
    }

    const scheduleNext = () => {
      idleHandle = scheduleIdleTask(() => {
        if (cancelled) return
        let processed = 0
        while (years.length > 0 && processed < 3) {
          const nextYear = years.shift()!
          cache.set(nextYear, computeYearImportance(nextYear))
          processed += 1
        }
        if (years.length > 0) {
          scheduleNext()
          return
        }
        setPrecomputedShapCache(new Map(cache))
        debug.log('cache', `Pre-computed SHAP for ${cache.size} years (stratum: ${selectedStratum})`)
      }, 250)
    }

    scheduleNext()
    return () => {
      cancelled = true
      cancelIdleTask(idleHandle)
    }
  }, [effectiveShapTimeline, rawData, computeYearImportance, selectedStratum])

  // CI cache: non-critical, fully deferred to idle.
  useEffect(() => {
    if (!effectiveShapTimeline || !rawData) return

    const years = [...effectiveShapTimeline.years]
    if (years.length === 0) return

    const cache = new Map<number, Map<string, NodeCIData>>()
    let cancelled = false
    let idleHandle: IdleHandle | null = null

    const scheduleNext = () => {
      idleHandle = scheduleIdleTask(() => {
        if (cancelled) return
        let processed = 0
        while (years.length > 0 && processed < 2) {
          const nextYear = years.shift()!
          cache.set(nextYear, computeYearCI(nextYear))
          processed += 1
        }
        if (years.length > 0) {
          scheduleNext()
          return
        }
        setPrecomputedCICache(cache)
      }, 500)
    }

    scheduleNext()
    return () => {
      cancelled = true
      cancelIdleTask(idleHandle)
    }
  }, [effectiveShapTimeline, rawData, computeYearCI])

  /**
   * Compute effective nodes with country-specific SHAP importance values.
   *
   * When a country is selected:
   * 1. Uses country-specific SHAP importance for Ring 5 indicators (already 0-1 normalized)
   * 2. Aggregates SHAP up the hierarchy (mean of children) for Ring 0-4
   * 3. Filters out nodes without SHAP data coverage
   *
   * The importance field is used by the Phase 1 sizing pipeline (vLayout.getNodeRadius)
   */
  const effectiveNodes = useMemo((): RawNodeV21[] | null => {
    if (!rawData) return null

    // No country selected - use original nodes with their global SHAP-based importance
    if (!selectedCountry || !countryGraph?.shap_importance || !countryGraph?.edges) {
      return rawData.nodes
    }

    const countryShap = countryGraph.shap_importance

    // If no SHAP data for this country, fall back to global
    if (Object.keys(countryShap).length === 0) {
      return rawData.nodes
    }

    // Get coverage info (nodes that have edges in country graph)
    const countryIndicators = extractIndicatorsFromGraph(countryGraph.edges)
    const coveredNodeIds = computeCountryCoverage(countryIndicators, rawData.nodes)

    // Build parent-child map for aggregation
    const childrenMap = new Map<string | number, (string | number)[]>()
    for (const node of rawData.nodes) {
      if (node.children) {
        childrenMap.set(node.id, node.children.map(c => String(c)))
      }
    }

    // First pass: assign SHAP to Ring 5 indicators
    const nodeShapMap = new Map<string | number, number>()
    for (const node of rawData.nodes) {
      if (node.layer === 5) {
        const shap = countryShap[String(node.id)]
        if (shap !== undefined && !isNaN(shap)) {
          nodeShapMap.set(node.id, shap)
        }
      }
    }

    // Second pass: aggregate up the hierarchy (Ring 4 → Ring 0)
    // Bottom-up: compute parent SHAP as SUM of children's SHAP
    // This preserves hierarchy: parents are always >= any individual child
    for (let ring = 4; ring >= 0; ring--) {
      for (const node of rawData.nodes) {
        if (node.layer !== ring) continue

        const childIds = childrenMap.get(node.id) || []
        const childShaps: number[] = []

        for (const childId of childIds) {
          const childShap = nodeShapMap.get(childId)
          if (childShap !== undefined) {
            childShaps.push(childShap)
          }
        }

        if (childShaps.length > 0) {
          // Use SUM of children's SHAP for parent importance (preserves hierarchy)
          const sumShap = childShaps.reduce((a, b) => a + b, 0)
          nodeShapMap.set(node.id, sumShap)
        }
      }
    }

    // Third pass: normalize so root = 1.0 (matches unified model approach)
    const rootNode = rawData.nodes.find(n => n.layer === 0)
    const rootShap = rootNode ? (nodeShapMap.get(rootNode.id) || 1) : 1

    // Normalize all values by root (so root = 1.0, others are proportional)
    if (rootShap > 0) {
      for (const [nodeId, shap] of nodeShapMap.entries()) {
        nodeShapMap.set(nodeId, shap / rootShap)
      }
    }

    // Create nodes with country-specific SHAP importance, filtered to covered only
    const nodesWithCountryImportance: RawNodeV21[] = []

    for (const node of rawData.nodes) {
      const nodeId = String(node.id)

      // Skip nodes without coverage (remove them, don't dim)
      // Root is always kept
      if (!coveredNodeIds.has(nodeId) && node.layer !== 0) {
        continue
      }

      const countryImportance = nodeShapMap.get(node.id)
      let importance: number

      if (countryImportance !== undefined && !isNaN(countryImportance)) {
        importance = Math.abs(countryImportance)
      } else if (node.layer === 0) {
        // Root always gets max importance
        importance = 1.0
      } else {
        // Fallback to small floor for nodes without SHAP
        importance = 0.01
      }

      nodesWithCountryImportance.push({
        ...node,
        importance
      })
    }

    return nodesWithCountryImportance
  }, [rawData, selectedCountry, countryGraph])

  // Drill down: replace targets with children (works for targets and non-targets)
  // Also handles undo (drill up) when history exists
  const drillDownTarget = useCallback((nodeId: string) => {
    const node = nodeByIdMap.get(nodeId)
    if (!node?.children || node.children.length === 0) return

    const childIds = node.children.map(c => String(c))
    const prevBeta = localViewBetaThreshold
    const prevTargets = [...localViewTargets]
    const isCurrentTarget = localViewTargets.includes(nodeId)

    if (isCurrentTarget) {
      // Replace the target with its children
      setLocalViewTargets(prev => {
        const filtered = prev.filter(id => id !== nodeId)
        return [...filtered, ...childIds]
      })
    } else {
      // For non-target nodes: replace ALL targets with just the children
      // This drills into that branch of the hierarchy
      setLocalViewTargets(childIds)
    }

    // Always save history for undo (can go back one step)
    setDrillDownHistory({ prevTargets, prevBeta })

    // Auto-adjust beta threshold based on number of new targets
    const childCount = childIds.length
    if (childCount > 10) {
      setLocalViewBetaThreshold(prev => Math.max(prev, 1.0))
    } else if (childCount > 5) {
      setLocalViewBetaThreshold(prev => Math.max(prev, 0.7))
    }
  }, [nodeByIdMap, localViewTargets, localViewBetaThreshold])

  // Drill up: restore previous targets from history
  const drillUpTarget = useCallback(() => {
    if (!drillDownHistory) return
    setLocalViewTargets(drillDownHistory.prevTargets)
    setLocalViewBetaThreshold(drillDownHistory.prevBeta)
    setDrillDownHistory(null)
  }, [drillDownHistory])

  // All nodes from layout (stored for filtering)
  const [allNodes, setAllNodes] = useState<ExpandableNode[]>([])
  const [allEdges, setAllEdges] = useState<StructuralEdge[]>([])
  const [computedRingsState, setComputedRingsState] = useState<Array<{ radius: number; nodeSize: number; label?: string }>>([])

  // Keep tutorial handle current
  useEffect(() => {
    if (tutorialRef.current) {
      Object.assign(tutorialRef.current, { toggleExpansion, setExpandedNodes, expandRing, collapseRing, resetView, allNodes, rawData })
    }
  })

  // Share current state via URL
  const shareCurrentState = useCallback(async (): Promise<boolean> => {
    const simState = useSimulationStore.getState()
    const state: URLState = {
      view: viewMode,
      expanded: Array.from(expandedNodes),
      targets: localViewTargets,
      beta: localViewBetaThreshold !== 0.5 ? localViewBetaThreshold : undefined,
      highlight: highlightedTarget || undefined,
      zoom: currentTransformRef.current ? {
        k: currentTransformRef.current.k,
        x: currentTransformRef.current.x,
        y: currentTransformRef.current.y
      } : undefined
    }

    // Include simulation state in shared URL
    if (simState.selectedCountry) state.country = simState.selectedCountry
    if (!simState.selectedCountry && simState.selectedStratum !== 'unified') {
      state.stratum = simState.selectedStratum
    }
    if (simState.interventions.length > 0 && (!simState.activeTemplate || simState.templateModified)) {
      state.interventions = simState.interventions.map(iv => ({
        ind: iv.indicator,
        pct: iv.change_percent,
        yr: iv.year
      }))
    }
    if (simState.activeTemplate && !simState.templateModified) {
      state.template = simState.activeTemplate.id
    }
    if (simState.simulationStartYear !== 2020) state.simStart = simState.simulationStartYear
    if (simState.simulationEndYear !== 2029) state.simEnd = simState.simulationEndYear

    return copyURLToClipboard(state)
  }, [viewMode, expandedNodes, localViewTargets, localViewBetaThreshold, highlightedTarget])

  // Toggle expansion of a node
  const toggleExpansion = useCallback((nodeId: string) => {
    if (!rawData) return
    const isCollapsing = expandedNodes.has(nodeId)
    runOrQueueStructuralAction(() => {
      beginLayoutAction(
        isCollapsing ? 'single_collapse' : 'single_expand',
        'toggleExpansion',
        {
          nodeId,
          mode: isCollapsing ? 'collapse' : 'expand'
        }
      )
      // Individual node click — disable dots mode (full rendering)
      dotsModeRef.current = false
      const nodeById = new Map(rawData.nodes.map(n => [String(n.id), n]))

      setPinnedPaths(new Set())  // Clear pinned paths on manual interaction
      setExpandedNodes(prev => {
        const next = new Set(prev)
        const wasExpanded = next.has(nodeId)

        if (wasExpanded) {
          // Collapse: remove this node and all descendants from expanded set
          next.delete(nodeId)
          // Also collapse all descendants (use rawData for full tree)
          const collapseDescendants = (id: string) => {
            const node = nodeById.get(id)
            if (node?.children) {
              for (const childId of node.children) {
                const childIdStr = String(childId)
                next.delete(childIdStr)
                collapseDescendants(childIdStr)
              }
            }
          }
          collapseDescendants(nodeId)
          // Record collapse for auto-zoom
          pendingZoomRef.current = { nodeId, action: 'collapse' }
          if (import.meta.env.DEV) {
            console.log('[Camera]', 'queue collapse', { nodeId, nextExpandedCount: next.size })
          }
        } else {
          next.add(nodeId)
          // Record expansion for auto-zoom
          pendingZoomRef.current = { nodeId, action: 'expand' }
          if (import.meta.env.DEV) {
            console.log('[Camera]', 'queue expand', { nodeId, nextExpandedCount: next.size })
          }
        }
        return next
      })
    })
  }, [rawData, expandedNodes, runOrQueueStructuralAction, beginLayoutAction])

  // Expand all nodes
  // Calculate initial zoom transform to fit content tightly
  const calculateInitialTransform = useCallback((nodes: ExpandableNode[], containerWidth?: number, containerHeight?: number) => {
    // Use provided dimensions or calculate from viewMode and splitRatio
    const fullWidth = window.innerWidth
    const fullHeight = window.innerHeight
    const width = containerWidth ?? (viewMode === 'split' ? fullWidth * splitRatio : fullWidth)
    const height = containerHeight ?? fullHeight

    // Calculate bounding box of all nodes (including root at 0,0)
    const allXs = nodes.map(n => n.x)
    const allYs = nodes.map(n => n.y)

    if (allXs.length === 0) {
      return d3.zoomIdentity.translate(width / 2, getGraphCenterY(height)).scale(1)
    }

    const boundsMinX = Math.min(...allXs)
    const boundsMaxX = Math.max(...allXs)
    const boundsMinY = Math.min(...allYs)
    const boundsMaxY = Math.max(...allYs)

    const boundsWidth = Math.max(boundsMaxX - boundsMinX, 50)
    const boundsHeight = Math.max(boundsMaxY - boundsMinY, 50)

    const centerX = (boundsMinX + boundsMaxX) / 2
    const centerY = (boundsMinY + boundsMaxY) / 2

    // Tight padding (5% margin) to fill the screen
    const padding = 0.05
    const scaleX = width * (1 - 2 * padding) / boundsWidth
    const scaleY = height * (1 - 2 * padding) / boundsHeight
    const scale = Math.min(scaleX, scaleY, 3) // Cap at 3x zoom

    const translateX = width / 2 - centerX * scale
    const translateY = getGraphCenterY(height) - centerY * scale

    return d3.zoomIdentity.translate(translateX, translateY).scale(scale)
  }, [viewMode, splitRatio])

  // FPS counter (dev mode only)
  useEffect(() => {
    if (!import.meta.env.DEV) return

    let frameCount = 0
    let lastTime = performance.now()
    let animationId: number

    const measureFps = () => {
      frameCount++
      const currentTime = performance.now()
      const elapsed = currentTime - lastTime

      // Update FPS every 500ms
      if (elapsed >= 500) {
        setFps(Math.round((frameCount * 1000) / elapsed))
        frameCount = 0
        lastTime = currentTime
      }

      animationId = requestAnimationFrame(measureFps)
    }

    animationId = requestAnimationFrame(measureFps)
    return () => cancelAnimationFrame(animationId)
  }, [])

  // Expand all nodes in a specific ring (that are currently visible)
  const expandRing = useCallback((ring: number) => {
    announce(`Expanded to ${RING_LABELS[ring + 1] ?? `ring ${ring + 1}`}`)
    runOrQueueStructuralAction(() => {
      beginLayoutAction('ring_expand', 'expandRing', { ring })
      // Bulk expansion — enable dots mode for deep rings
      if (ring >= 3) dotsModeRef.current = true
      setPinnedPaths(new Set())
      setExpandedNodes(prev => {
        const next = new Set(prev)
        // Find nodes in this ring that are visible (parent is expanded or is root) and have children
        allNodes
          .filter(n => {
            if (n.ring !== ring || !n.hasChildren) return false
            // Check if visible: root is always visible, others need parent expanded
            if (n.ring === 0) return true
            return n.parentId && prev.has(n.parentId)
          })
          .forEach(n => next.add(n.id))
        return next
      })
    })
  }, [allNodes, runOrQueueStructuralAction, beginLayoutAction])

  // Collapse all nodes in a specific ring
  const collapseRing = useCallback((ring: number) => {
    if (!rawData) return
    announce(`Collapsed to ${RING_LABELS[ring] ?? `ring ${ring}`}`)
    runOrQueueStructuralAction(() => {
      beginLayoutAction('ring_collapse', 'collapseRing', { ring })
      dotsModeRef.current = false
      setPinnedPaths(new Set())
      const nodeById = new Map(rawData.nodes.map(n => [String(n.id), n]))

      setExpandedNodes(prev => {
        const next = new Set(prev)
        // Remove all nodes in this ring and their descendants (use rawData for full tree)
        rawData.nodes
          .filter(n => n.layer === ring)
          .forEach(n => {
            const nodeId = String(n.id)
            next.delete(nodeId)
            // Also collapse descendants
            const collapseDescendants = (id: string) => {
              const node = nodeById.get(id)
              if (node?.children) {
                for (const childId of node.children) {
                  const childIdStr = String(childId)
                  next.delete(childIdStr)
                  collapseDescendants(childIdStr)
                }
              }
            }
            collapseDescendants(nodeId)
          })
        return next
      })
    })
  }, [rawData, runOrQueueStructuralAction, beginLayoutAction])

  /**
   * Aggregate simulation effects up the hierarchy.
   * Leaf indicators get their direct percent_change from the API.
   * Parent nodes get the mean percent_change across ALL children (0 for unaffected).
   * This naturally dilutes as you go up: a domain with 20 children where 2 shift by -50%
   * gets an aggregate of -5%.
   *
   * Threshold rationale (2% absolute):
   *   - Filters noise: tiny spillover effects (<1%) on distant branches are hidden
   *   - Catches real signal: even one child at -40% in a group of 20 produces -2%
   *   - At ring 1 (broadest aggregation), 2% means a genuinely widespread shift
   *   - At ring 4 (small groups of 3-5), most groups with any affected child pass easily
   *
   * The 2% sits right at the boundary of "would a human notice this in the data" —
   * below it, the aggregate change is indistinguishable from measurement noise in
   * development indicators.
   */
  /**
   * Aggregate simulation effects for all hierarchy nodes.
   * Leaves: direct percent_change from API.
   * Parents: affected-only mean + coverage ratio.
   * Returns { pct, coverage, isLeaf } per node.
   */
  const aggregateEffects = useMemo(() => {
    const effects = new Map<string, { pct: number; coverage: number; isLeaf: boolean }>()
    if (!temporalResults?.effects || !rawData) return effects

    // In simulation playback: use current year's effects for tint
    // Otherwise: use final year
    let yearEffects: Record<string, { percent_change: number; baseline: number }>
    let yearKeyUsed: string
    if (playbackMode === 'simulation') {
      const simYear = temporalResults.base_year + currentYearIndex
      yearKeyUsed = String(simYear)
      yearEffects = temporalResults.effects[yearKeyUsed] ?? {}
    } else {
      const yearKeys = Object.keys(temporalResults.effects).sort()
      yearKeyUsed = yearKeys[yearKeys.length - 1] ?? ''
      yearEffects = yearKeyUsed ? temporalResults.effects[yearKeyUsed] : {}
    }
    const PCT_EPS = 0.5 // minimum % to count a child as "affected"

    // Seed leaf effects — include all non-zero effects (baseline filter
    // was too aggressive, excluded bridge nodes with small baselines)
    for (const [id, eff] of Object.entries(yearEffects)) {
      if (Math.abs(eff.percent_change) > 0.001) {
        effects.set(id, { pct: eff.percent_change, coverage: 1.0, isLeaf: true })
      }
    }

    // Build children lookup
    const childrenOf = new Map<string, string[]>()
    for (const n of rawData.nodes) {
      if (n.children && n.children.length > 0) {
        childrenOf.set(String(n.id), n.children.map(String))
      }
    }

    // Aggregate bottom-up: importance-weighted percent change.
    // Parent importance = sum(children importances). The simulation shifts each
    // child's value by percent_change. The parent's aggregate change is:
    //   pct = sum(child_imp * child_pct) / sum(child_imp)
    // This is what the sim actually did to this domain's aggregate value,
    // weighted by each child's contribution to the parent.
    const impOf = new Map<string, number>()
    for (const n of rawData.nodes) {
      impOf.set(String(n.id), n.importance ?? 0)
    }

    const nodesByLayerDesc = [...rawData.nodes].sort((a, b) => b.layer - a.layer)
    for (const n of nodesByLayerDesc) {
      const id = String(n.id)
      if (effects.has(id)) continue // Leaf already has a direct effect

      const children = childrenOf.get(id)
      if (!children || children.length === 0) continue

      let weightedSum = 0
      let totalWeight = 0
      let affectedCount = 0
      for (const childId of children) {
        const childImp = impOf.get(childId) ?? 0
        totalWeight += childImp
        const childEffect = effects.get(childId)
        if (childEffect) {
          weightedSum += childImp * childEffect.pct
          if (Math.abs(childEffect.pct) >= PCT_EPS) affectedCount++
        }
      }

      if (affectedCount === 0 || totalWeight < 1e-9) continue

      const coverage = affectedCount / children.length
      const pct = weightedSum / totalWeight

      effects.set(id, { pct, coverage, isLeaf: false })
    }

    return effects
  }, [temporalResults, rawData, playbackMode, currentYearIndex])

  // Ref for progressive reveal: nodes revealed during playback stay permanently
  const everAffectedRef = useRef<Set<string>>(new Set())

  /**
   * Pre-compute global top-X effects across ALL simulation years.
   * For each indicator, take its peak |percent_change| across all years.
   * The top X (by targetVisibleEffects count) are the ONLY leaves that will ever be revealed.
   */
  const globalTopEffectIds = useMemo(() => {
    if (!temporalResults?.effects) return new Set<string>()

    // Find peak |percent_change| for each indicator across all years
    const peakByIndicator = new Map<string, number>()
    for (const yearEffects of Object.values(temporalResults.effects)) {
      for (const [id, e] of Object.entries(yearEffects)) {
        if (Math.abs(e.baseline) <= 0.01) continue
        const abs = Math.abs(e.percent_change)
        if (abs > (peakByIndicator.get(id) ?? 0)) {
          peakByIndicator.set(id, abs)
        }
      }
    }

    // Sort by peak magnitude, take top N directly
    const sorted = [...peakByIndicator.entries()]
      .filter(([, peak]) => peak > 0.01)
      .sort((a, b) => b[1] - a[1])

    return new Set(sorted.slice(0, targetVisibleEffects).map(([id]) => id))
  }, [temporalResults, targetVisibleEffects])

  /** Build pins from a set of leaf IDs: root + ring1 + interventions + leaves + ancestors, then prune. */
  const buildPins = (leafIds: Set<string>, rawDataRef: typeof rawData, interventions: typeof storeInterventions): Set<string> => {
    if (!rawDataRef) return new Set()

    const parentOf = new Map<string, string>()
    for (const n of rawDataRef.nodes) {
      if (n.parent !== undefined) parentOf.set(String(n.id), String(n.parent))
    }

    const pins = new Set<string>()

    // Always pin root (ring 0 only — ring 1 domains are pinned via
    // ancestor-walking from interventions/effects, so unaffected domains
    // are hidden during simulation for a cleaner focused view)
    for (const n of rawDataRef.nodes) {
      if (n.layer === 0) pins.add(String(n.id))
    }

    // Pin interventions + ancestors (this naturally pins their ring 1 domain parents)
    for (const intv of interventions) {
      if (intv.indicator) {
        pins.add(intv.indicator)
        let cur = parentOf.get(intv.indicator)
        while (cur) { pins.add(cur); cur = parentOf.get(cur) }
      }
    }

    // Pin leaf effects + ancestors
    for (const id of leafIds) {
      pins.add(id)
      let cur = parentOf.get(id)
      while (cur) { pins.add(cur); cur = parentOf.get(cur) }
    }

    // Prune single-child intermediates (ring 2+)
    const layerOf = new Map(rawDataRef.nodes.map(n => [String(n.id), n.layer]))
    const childrenOf = new Map<string, string[]>()
    for (const n of rawDataRef.nodes) {
      if (n.children && n.children.length > 0) {
        childrenOf.set(String(n.id), n.children.map(String))
      }
    }
    let pruned = true
    while (pruned) {
      pruned = false
      for (const id of [...pins]) {
        const layer = layerOf.get(id) ?? 0
        if (layer <= 1) continue
        const children = childrenOf.get(id)
        if (!children) continue
        const pinnedChildCount = children.filter(c => pins.has(c)).length
        if (pinnedChildCount <= 1) {
          pins.delete(id)
          pruned = true
        }
      }
    }

    return pins
  }

  // On simulation start: pin only interventions (no effects yet — progressive reveal handles them)
  useEffect(() => {
    if (!temporalResults || !rawData || storeInterventions.length === 0) return

    everAffectedRef.current = new Set()
    const pins = buildPins(new Set(), rawData, storeInterventions)
    if (pins.size <= 1) return

    resetOutcomeSectorCache()
    setExpandedNodes(new Set())
    setPinnedPaths(pins)
  }, [temporalResults, rawData, storeInterventions, resetOutcomeSectorCache])

  // Track whether playback has started at least once for this simulation run
  const playbackStartedRef = useRef(false)
  useEffect(() => {
    if (isPlaying && playbackMode === 'simulation') {
      playbackStartedRef.current = true
    }
  }, [isPlaying, playbackMode])
  // Reset when new results arrive
  useEffect(() => {
    playbackStartedRef.current = false
  }, [temporalResults])

  // When timeline resets to year 0, collapse back to intervention-only view
  useEffect(() => {
    if (playbackMode !== 'simulation' || !temporalResults || !rawData) return
    if (currentYearIndex === 0 && !isPlaying) {
      playbackStartedRef.current = false
      everAffectedRef.current = new Set()
      const pins = buildPins(new Set(), rawData, storeInterventions)
      if (pins.size > 1) setPinnedPaths(pins)
    }
  }, [currentYearIndex, isPlaying, playbackMode, temporalResults, storeInterventions, rawData])

  // When globalTopEffectIds changes (user moved slider), re-derive everAffected from scratch.
  // Walk all years up to current to rebuild the revealed set, then update pins immediately.
  const prevTopEffectIdsRef = useRef(globalTopEffectIds)
  useEffect(() => {
    if (prevTopEffectIdsRef.current === globalTopEffectIds) return
    prevTopEffectIdsRef.current = globalTopEffectIds

    if (playbackMode !== 'simulation' || !temporalResults?.effects || !rawData) return

    // Rebuild everAffected: walk all years up to current, reveal nodes in new top set
    const newEverAffected = new Set<string>()
    const { base_year } = temporalResults
    for (let yi = 1; yi <= currentYearIndex; yi++) {
      const yearEffects = temporalResults.effects[String(base_year + yi)]
      if (!yearEffects) continue
      for (const id of globalTopEffectIds) {
        if (newEverAffected.has(id)) continue
        const eff = yearEffects[id]
        if (eff && Math.abs(eff.percent_change) > 0.01) {
          newEverAffected.add(id)
        }
      }
    }
    everAffectedRef.current = newEverAffected

    const pins = buildPins(newEverAffected, rawData, storeInterventions)
    if (pins.size > 1) setPinnedPaths(pins)
  }, [globalTopEffectIds, playbackMode, temporalResults, rawData, storeInterventions, currentYearIndex])

  /**
   * Progressive pinning during simulation playback.
   * Each year, check which globalTopEffectIds have become significant (|pct| > 0.01).
   * Once revealed, a node stays permanently — no expiry, no hold years.
   * Only globalTopEffectIds can be revealed (pre-computed top X across all years).
   */
  useEffect(() => {
    if (playbackMode !== 'simulation' || !temporalResults?.effects || !rawData) return
    if (storeInterventions.length === 0) return
    if (!playbackStartedRef.current) return

    const { base_year } = temporalResults
    const simYear = base_year + currentYearIndex
    const yearEffects = temporalResults.effects[String(simYear)]
    if (!yearEffects) return

    // Reveal: any globalTopEffect that has |pct| > 0.01 this year gets permanently added
    let changed = false
    for (const id of globalTopEffectIds) {
      if (everAffectedRef.current.has(id)) continue
      const eff = yearEffects[id]
      if (eff && Math.abs(eff.percent_change) > 0.01) {
        everAffectedRef.current.add(id)
        changed = true
      }
    }

    // Only rebuild pins when new nodes were revealed
    if (changed || everAffectedRef.current.size > 0) {
      const pins = buildPins(everAffectedRef.current, rawData, storeInterventions)
      if (pins.size > 1) {
        setPinnedPaths(pins)
      }
    }
  }, [playbackMode, currentYearIndex, temporalResults, rawData, storeInterventions, globalTopEffectIds, isPlaying])

  // Clean up simulation visuals when panel closes
  // Panel open → simulation visuals active (fill/borders depending on playback state)
  // Panel closed → revert to regular historical view
  useEffect(() => {
    if (!isPanelOpen && playbackMode === 'simulation') {
      setPlaybackMode('historical')
      setPinnedPaths(new Set())
      everAffectedRef.current = new Set()
      playbackStartedRef.current = false
      // Expand root so ring 1 (domains) is visible instead of just the QoL node
      const rootNode = allNodes.find(n => n.ring === 0)
      if (rootNode) {
        setExpandedNodes(new Set([rootNode.id]))
      }
    }
  }, [isPanelOpen, playbackMode, setPlaybackMode, allNodes])

  // ============================================
  // Simulation in Local View
  // ============================================

  // Determine if local view should show simulation data
  const localViewSimMode = !!(temporalResults?.causal_paths) && isPanelOpen

  // Build sim data for local view
  const simLocalViewData = useMemo(() => {
    if (!localViewSimMode || !temporalResults?.causal_paths || !rawData) return null

    // Get intervention indicator IDs
    const interventionIds = storeInterventions
      .filter(i => i.indicator)
      .map(i => i.indicator!)
    if (interventionIds.length === 0) return null

    // At base year with playback not yet started: show only intervention targets
    if (!playbackStartedRef.current) {
      return buildSimLocalViewData(
        interventionIds,
        temporalResults.causal_paths,
        {},  // No effects → targets only
        new Set<string>(),
        nodeByIdMap,
        DOMAIN_COLORS
      )
    }

    const simYear = temporalResults.base_year + currentYearIndex
    const yearEffects = temporalResults.effects[String(simYear)]
    if (!yearEffects) {
      // No effects for this year — show targets only
      return buildSimLocalViewData(
        interventionIds,
        temporalResults.causal_paths,
        {},
        new Set<string>(),
        nodeByIdMap,
        DOMAIN_COLORS
      )
    }

    // Filter to top N effects — cap at 10 for local view (layout gets crowded beyond that)
    const LOCAL_VIEW_MAX_EFFECTS = 10
    const allEffects = Object.entries(yearEffects)
      .filter(([, e]) => Math.abs(e.percent_change) > 0.01)
      .sort((a, b) => Math.abs(b[1].percent_change) - Math.abs(a[1].percent_change))

    const keepCount = Math.min(targetVisibleEffects, LOCAL_VIEW_MAX_EFFECTS)

    const topIds = new Set(allEffects.slice(0, keepCount).map(([id]) => id))

    // Build filtered yearEffects (only top N)
    const filteredEffects: Record<string, typeof yearEffects[string]> = {}
    for (const id of topIds) {
      filteredEffects[id] = yearEffects[id]
    }

    // Use only current year's filtered IDs (no progressive accumulation —
    // the local view re-layouts per year, so accumulation just adds clutter)
    return buildSimLocalViewData(
      interventionIds,
      temporalResults.causal_paths,
      filteredEffects,
      topIds,
      nodeByIdMap,
      DOMAIN_COLORS
    )
  }, [localViewSimMode, temporalResults, currentYearIndex, storeInterventions, nodeByIdMap, rawData, targetVisibleEffects])

  // Build simEffects map for local view coloring (nodeId → percent_change for current year)
  const simLocalEffects = useMemo(() => {
    if (!localViewSimMode || !temporalResults?.effects) return undefined

    const simYear = temporalResults.base_year + currentYearIndex
    const yearEffects = temporalResults.effects[String(simYear)]
    if (!yearEffects) return undefined

    const effects = new Map<string, number>()
    for (const [id, eff] of Object.entries(yearEffects)) {
      if (Math.abs(eff.percent_change) > 0.001) {
        effects.set(id, eff.percent_change)
      }
    }
    return effects
  }, [localViewSimMode, temporalResults, currentYearIndex])

  /**
   * Pre-computed causal layout hint for angular clustering.
   * Built once from temporalResults (all years union) + causal_paths.
   * Passed to computeRadialLayout so affected nodes cluster at 0° and
   * causally connected siblings are adjacent. Stable across playback —
   * no re-sorting during animation.
   */
  const causalHint = useMemo((): CausalLayoutHint | undefined => {
    if (!temporalResults?.causal_paths || !rawData) return undefined

    const causalPaths = temporalResults.causal_paths

    // Build causalAdjacency and hopDistance from causal_paths
    const causalAdjacency = new Map<string, string>()
    const hopDistance = new Map<string, number>()
    for (const [targetId, entry] of Object.entries(causalPaths)) {
      hopDistance.set(targetId, entry.hop)
      if (entry.source && entry.hop > 0) {
        causalAdjacency.set(targetId, entry.source)
      }
    }

    // Also include all affected nodes across ALL years to get the full set
    if (temporalResults.effects) {
      for (const yearEffects of Object.values(temporalResults.effects)) {
        for (const [id, effect] of Object.entries(yearEffects)) {
          if (Math.abs(effect.percent_change) > 0.01 && !hopDistance.has(id)) {
            // Affected but not in causal_paths (shouldn't happen, but defensive)
            hopDistance.set(id, 99)
          }
        }
      }
    }

    // Find Ring 1 outcomes that contain affected descendants
    const parentOf = new Map<string, string>()
    const layerOf = new Map<string, number>()
    for (const n of rawData.nodes) {
      layerOf.set(String(n.id), n.layer)
      if (n.parent !== undefined) parentOf.set(String(n.id), String(n.parent))
    }

    const anchorOutcomes = new Set<string>()
    // Walk each affected node up to its Ring 1 ancestor
    for (const id of hopDistance.keys()) {
      let cur: string | undefined = id
      while (cur) {
        const layer = layerOf.get(cur)
        if (layer === 1) {
          anchorOutcomes.add(cur)
          break
        }
        cur = parentOf.get(cur)
      }
    }

    return { anchorOutcomes, causalAdjacency, hopDistance }
  }, [temporalResults, rawData])

  // Compute visible nodes based on expansion state and pinned paths
  const visibleNodes = useMemo(() => {
    if (allNodes.length === 0) return []

    const visible = new Set<string>()

    // Root is always visible
    const rootNode = allNodes.find(n => n.ring === 0)
    if (rootNode) {
      visible.add(rootNode.id)

      // For each expanded node, its children are visible
      const addVisibleChildren = (nodeId: string) => {
        if (expandedNodes.has(nodeId)) {
          const node = allNodes.find(n => n.id === nodeId)
          if (node) {
            node.childIds.forEach(childId => {
              visible.add(childId)
              addVisibleChildren(childId)
            })
          }
        }
      }

      addVisibleChildren(rootNode.id)
    }

    // Pinned paths: individual nodes visible (no sibling expansion)
    for (const nodeId of pinnedPaths) {
      visible.add(nodeId)
    }

    return allNodes.filter(n => visible.has(n.id))
  }, [allNodes, expandedNodes, pinnedPaths])

  // Compute visible edges: connect each visible node to its nearest visible ancestor.
  // When intermediate nodes are pruned, this creates skip-edges across ring gaps.
  const visibleEdges = useMemo(() => {
    const visibleIds = new Set(visibleNodes.map(n => n.id))

    // If no pinned paths active, use the simple filter (normal expansion)
    if (pinnedPaths.size === 0) {
      return allEdges.filter(e => visibleIds.has(e.sourceId) && visibleIds.has(e.targetId))
    }

    // Build parent lookup from rawData for walking up
    const parentOfRaw = new Map<string, string>()
    const ringOfRaw = new Map<string, number>()
    if (rawData) {
      for (const n of rawData.nodes) {
        if (n.parent !== undefined) parentOfRaw.set(String(n.id), String(n.parent))
        ringOfRaw.set(String(n.id), n.layer)
      }
    }

    // For each visible non-root node, find nearest visible ancestor
    const edges: StructuralEdge[] = []
    const nodeMap = new Map(visibleNodes.map(n => [n.id, n]))
    for (const node of visibleNodes) {
      if (node.ring === 0) continue
      // Walk up through raw parents until we find a visible one
      let cur = parentOfRaw.get(node.id)
      while (cur && !visibleIds.has(cur)) {
        cur = parentOfRaw.get(cur)
      }
      if (cur && visibleIds.has(cur)) {
        const parentNode = nodeMap.get(cur)
        if (parentNode) {
          edges.push({
            sourceId: cur,
            targetId: node.id,
            sourceRing: parentNode.ring,
            targetRing: node.ring
          })
        }
      }
    }
    return edges
  }, [allEdges, visibleNodes, pinnedPaths, rawData])

  useEffect(() => {
    visibleCountsRef.current = {
      nodes: visibleNodes.length,
      edges: visibleEdges.length
    }
  }, [visibleNodes.length, visibleEdges.length])

  // Memoized map of nodes by ring for percentile calculations (avoids recreation in render)
  const nodesByRingMemo = useMemo(() => {
    const map = new Map<number, ExpandableNode[]>()
    visibleNodes.forEach(n => {
      if (!map.has(n.ring)) map.set(n.ring, [])
      map.get(n.ring)!.push(n)
    })
    return map
  }, [visibleNodes])

  // Compute all node IDs visible in Local View (targets + inputs + outputs)
  // Used for glow highlighting in Global View
  // Track node roles for glow colors: target=cyan, input=orange, output=purple
  // Supports multi-depth (causes of causes, effects of effects)
  const localViewNodeRoles = useMemo(() => {
    const roles = new Map<string, 'target' | 'input' | 'output'>()
    if (localViewTargets.length === 0 || !rawData) return roles

    const causalEdges = getCausalEdges(rawData.edges)

    // Mark targets
    for (const targetId of localViewTargets) {
      roles.set(targetId, 'target')
    }

    // Collect input nodes (causes) up to inputDepth levels
    let currentInputSources = new Set(localViewTargets)
    for (let depth = 1; depth <= localViewInputDepth; depth++) {
      const nextSources = new Set<string>()
      for (const nodeId of currentInputSources) {
        causalEdges
          .filter(e => e.target === nodeId && Math.abs(e.beta) >= localViewBetaThreshold)
          .forEach(e => {
            if (!roles.has(e.source)) {
              roles.set(e.source, 'input')
              nextSources.add(e.source)
            }
          })
      }
      currentInputSources = nextSources
    }

    // Collect output nodes (effects) up to outputDepth levels
    let currentOutputSources = new Set(localViewTargets)
    for (let depth = 1; depth <= localViewOutputDepth; depth++) {
      const nextSources = new Set<string>()
      for (const nodeId of currentOutputSources) {
        causalEdges
          .filter(e => e.source === nodeId && Math.abs(e.beta) >= localViewBetaThreshold)
          .forEach(e => {
            if (!roles.has(e.target)) {
              roles.set(e.target, 'output')
              nextSources.add(e.target)
            }
          })
      }
      currentOutputSources = nextSources
    }

    return roles
  }, [localViewTargets, rawData, localViewBetaThreshold, localViewInputDepth, localViewOutputDepth])

  // Flat set of all Local View node IDs (for filtering)
  const localViewNodeIds = useMemo(() => {
    return new Set(localViewNodeRoles.keys())
  }, [localViewNodeRoles])

  // Reset view: handles both Global and Local views based on current viewMode
  // Collapses to QoL root, then after a delay expands ring 1 with animation
  const resetView = useCallback(() => {
    if (resetExpandTimerRef.current !== null) {
      clearTimeout(resetExpandTimerRef.current)
      resetExpandTimerRef.current = null
    }
    if (resetFitTimerRef.current !== null) {
      clearTimeout(resetFitTimerRef.current)
      resetFitTimerRef.current = null
    }

    // Full reset should never restore pre-simulation navigation state.
    restoreNavAfterClearRef.current = false

    // Reset analysis context
    setLocalViewTargets([])
    setDrillDownHistory(null)
    setHighlightedPath(new Set())
    setHighlightedTarget(null)
    setHoveredNode(null)
    tooltipNodeRef.current = null
    setPinnedPaths(new Set())
    setHighlightedIndicator(null)
    clearResults()
    setStratum('unified')
    void setSelectedRegion(null)
    clearCountry()
    setViewMode('global')

    // Reset Local View if in local or split mode
    if ((viewMode === 'local' || viewMode === 'split') && localViewResetRef.current) {
      localViewResetRef.current()
    }

    if (!zoomRef.current || !svgRef.current) return

    const svg = d3.select(svgRef.current)

    // Phase 1: collapse to just the QoL root node
    resetOutcomeSectorCache()
    setExpandedNodes(new Set())
    setPinnedPaths(new Set())
    currentTransformRef.current = null

    // Zoom to fit just the root node
    const rootNodes = allNodes.filter(n => n.ring === 0)
    const rootTransform = calculateInitialTransform(rootNodes)
    svg.transition().duration(300).call(zoomRef.current.transform, rootTransform)

    // Phase 2: after delay, expand root to reveal ring 1 and zoom to fit
    const rootNode = allNodes.find(n => n.ring === 0)
    if (rootNode) {
      resetExpandTimerRef.current = window.setTimeout(() => {
        resetExpandTimerRef.current = null
        setExpandedNodes(new Set([rootNode.id]))
        // Zoom to fit ring 0 + ring 1 after expansion settles
        resetFitTimerRef.current = window.setTimeout(() => {
          resetFitTimerRef.current = null
          if (!zoomRef.current || !svgRef.current) return
          const svgEl = d3.select(svgRef.current)
          const ring01 = allNodes.filter(n => n.ring <= 1)
          const fitTransform = calculateInitialTransform(ring01.length > 0 ? ring01 : rootNodes)
          svgEl.transition().duration(400).call(zoomRef.current!.transform, fitTransform)
        }, 350)
      }, 1500)
    }
  }, [allNodes, calculateInitialTransform, viewMode, clearCountry, clearResults, setSelectedRegion, setStratum, setHighlightedIndicator, resetOutcomeSectorCache])

  // Fit view to all visible nodes (for double-click on empty space)
  const fitToVisibleNodes = useCallback(() => {
    if (!zoomRef.current || !svgRef.current || visibleNodes.length === 0) return

    const svg = d3.select(svgRef.current)
    const width = viewMode === 'split' ? window.innerWidth * splitRatio : window.innerWidth
    const height = window.innerHeight

    // Calculate bounding box of all visible nodes
    const allXs = visibleNodes.map(n => n.x)
    const allYs = visibleNodes.map(n => n.y)

    const boundsMinX = Math.min(...allXs)
    const boundsMaxX = Math.max(...allXs)
    const boundsMinY = Math.min(...allYs)
    const boundsMaxY = Math.max(...allYs)

    const boundsWidth = boundsMaxX - boundsMinX
    const boundsHeight = boundsMaxY - boundsMinY

    // Calculate center
    const centerX = (boundsMinX + boundsMaxX) / 2
    const centerY = (boundsMinY + boundsMaxY) / 2

    // Calculate scale to fit with padding (extra margin so labels aren't clipped)
    const padding = 0.15
    const scaleX = width * (1 - 2 * padding) / Math.max(boundsWidth, 1)
    const scaleY = height * (1 - 2 * padding) / Math.max(boundsHeight, 1)
    const fitScale = Math.min(scaleX, scaleY, 3) // Cap at 3x zoom

    const newX = width / 2 - centerX * fitScale
    const newY = getGraphCenterY(height) - centerY * fitScale
    const newTransform = d3.zoomIdentity.translate(newX, newY).scale(fitScale)

    svg.transition().duration(300).call(zoomRef.current.transform, newTransform)
    currentTransformRef.current = newTransform
  }, [visibleNodes, viewMode, splitRatio])

  // Auto-zoom when sim causes visible node count to change (new effects cascading in)
  const prevSimVisibleCountRef = useRef(0)
  useEffect(() => {
    if (!temporalResults || !isPanelOpen) {
      prevSimVisibleCountRef.current = 0
      return
    }
    const count = visibleNodes.length
    if (prevSimVisibleCountRef.current > 0 && count !== prevSimVisibleCountRef.current) {
      fitToVisibleNodes()
    }
    prevSimVisibleCountRef.current = count
  }, [visibleNodes.length, temporalResults, isPanelOpen, fitToVisibleNodes])

  // Zoom to node when clicking in results panel (pan to center on highlighted indicator)
  const prevHighlightedRef = useRef<string | null>(null)
  useEffect(() => {
    if (!highlightedIndicator || highlightedIndicator === prevHighlightedRef.current) {
      prevHighlightedRef.current = highlightedIndicator
      return
    }
    prevHighlightedRef.current = highlightedIndicator

    const node = visibleNodes.find(n => n.id === highlightedIndicator)
    if (!node || !zoomRef.current || !svgRef.current) return

    const svg = d3.select(svgRef.current)
    const width = viewMode === 'split' ? window.innerWidth * splitRatio : window.innerWidth
    const height = window.innerHeight
    const currentScale = currentTransformRef.current?.k ?? 1

    const newX = width / 2 - node.x * currentScale
    const newY = getGraphCenterY(height) - node.y * currentScale
    const newTransform = d3.zoomIdentity.translate(newX, newY).scale(currentScale)

    svg.transition().duration(400).ease(d3.easeCubicOut)
      .call(zoomRef.current!.transform, newTransform)
    currentTransformRef.current = newTransform
  }, [highlightedIndicator, visibleNodes, viewMode, splitRatio])

  // Keyboard shortcuts for reset view (R or Home) and view switching (G, L, S)
  useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
      // Ignore if user is typing in an input
      if (e.target instanceof HTMLInputElement || e.target instanceof HTMLTextAreaElement) return

      if (e.key === 'r' || e.key === 'R' || e.key === 'Home') {
        e.preventDefault()
        resetView()
      } else if (e.key === 'g' || e.key === 'G') {
        e.preventDefault()
        setViewMode('global')
      } else if (e.key === 'l' || e.key === 'L') {
        e.preventDefault()
        // Switch to local if there are targets or sim mode is active
        if (localViewTargets.length > 0 || localViewSimMode) {
          setViewMode('local')
        }
      } else if (e.key === 's' || e.key === 'S') {
        e.preventDefault()
        // Switch to split if there are targets or sim mode is active (disabled below 1024px)
        if ((localViewTargets.length > 0 || localViewSimMode) && window.innerWidth >= 1024) {
          setViewMode('split')
        }
      } else if (e.key === 'm' || e.key === 'M') {
        e.preventDefault()
        if (mKeyRef.current.down) return // already held, ignore repeat
        const store = useSimulationStore.getState()
        mKeyRef.current = { down: true, time: Date.now(), origForeground: store.mapForeground }
        store.toggleMapForeground()
        if (store.mapForeground) {
          // Went to foreground → will clear hover on release if held
        }
      }
    }

    const handleKeyUp = (e: KeyboardEvent) => {
      if (e.key === 'm' || e.key === 'M') {
        const ref = mKeyRef.current
        if (!ref.down) return
        const held = Date.now() - ref.time
        ref.down = false
        // Hold threshold: if held ≥ 250ms, revert to original state
        if (held >= 250) {
          const store = useSimulationStore.getState()
          if (store.mapForeground !== ref.origForeground) {
            store.toggleMapForeground()
          }
          // Clear hover when reverting from foreground
          if (ref.origForeground === false) {
            store.setMapHoveredCountry(null)
          }
        }
      }
    }

    window.addEventListener('keydown', handleKeyDown)
    window.addEventListener('keyup', handleKeyUp)
    return () => {
      window.removeEventListener('keydown', handleKeyDown)
      window.removeEventListener('keyup', handleKeyUp)
    }
  }, [resetView, localViewTargets.length, localViewSimMode])

  // All nodes for search (derived from rawData, not just visible nodes)
  const searchableNodes = useMemo(() => {
    if (!rawData) return []
    return rawData.nodes.map(n => ({
      id: String(n.id),
      label: n.node_type === 'root' ? 'Quality of Life' : n.label.replace(/_/g, ' '),
      domain: n.domain || '',
      subdomain: n.subdomain || '',
      ring: n.layer,
      importance: n.importance ?? 0,
      parentId: n.parent ? String(n.parent) : null,
      hasChildren: (n.children?.length || 0) > 0
    }))
  }, [rawData])

  // Node map for breadcrumb navigation
  const breadcrumbNodeMap = useMemo(() => {
    return new Map(searchableNodes.map(n => [n.id, n]))
  }, [searchableNodes])

  // Fuse.js index for fuzzy search (searches ALL nodes, not just visible)
  const fuseIndex = useMemo(() => {
    if (searchableNodes.length === 0) return null
    return new Fuse(searchableNodes, {
      keys: [
        { name: 'label', weight: 0.7 },
        { name: 'domain', weight: 0.2 },
        { name: 'subdomain', weight: 0.1 }
      ],
      threshold: 0.4,
      includeScore: true,
      minMatchCharLength: 2
    })
  }, [searchableNodes])

  // Search handler
  const handleSearch = useCallback((query: string) => {
    setSearchQuery(query)
    if (!fuseIndex || query.length < 2) {
      setSearchResults([])
      setShowSearchResults(false)
      return
    }

    let results = fuseIndex.search(query)

    // Apply domain filter if set
    if (domainFilter) {
      results = results.filter(r => r.item.domain === domainFilter)
    }

    // Take top 5 results
    const topResults = results.slice(0, 5).map(r => r.item)
    setSearchResults(topResults)
    setShowSearchResults(topResults.length > 0)
  }, [fuseIndex, domainFilter])

  // Get path from root to node (list of node IDs to expand)
  const getPathToNode = useCallback((nodeId: string): string[] => {
    const path: string[] = []
    const nodeMap = new Map(searchableNodes.map(n => [n.id, n]))

    let current = nodeMap.get(nodeId)
    while (current && current.parentId) {
      path.unshift(current.parentId)
      current = nodeMap.get(current.parentId)
    }
    return path
  }, [searchableNodes])

  // Jump to node: expand path and zoom to frame
  const jumpToNode = useCallback((node: SearchableNode) => {
    // Add to recent searches (keep last 5, no duplicates)
    setRecentSearches(prev => {
      const filtered = prev.filter(s => s !== node.label)
      return [node.label, ...filtered].slice(0, 5)
    })

    // Clear search
    setSearchQuery('')
    setSearchResults([])
    setShowSearchResults(false)

    // Get path from root to target node
    const pathToExpand = getPathToNode(node.id)

    // Calculate highlight path: from target node up to Ring 1 ancestor
    // Include the target node + all ancestors up to and including Ring 1
    const nodeMap = new Map(searchableNodes.map(n => [n.id, n]))
    const highlightPath = new Set<string>()
    highlightPath.add(node.id)

    let current = nodeMap.get(node.id)
    while (current && current.parentId) {
      const parent = nodeMap.get(current.parentId)
      if (parent) {
        highlightPath.add(parent.id)
        // Stop at Ring 1 (outcome level)
        if (parent.ring <= 1) break
      }
      current = parent
    }

    // Expand all nodes in path first
    setExpandedNodes(prev => {
      const next = new Set(prev)
      pathToExpand.forEach(id => next.add(id))
      return next
    })

    // Set pending zoom to frame the target node
    pendingZoomRef.current = { nodeId: node.id, action: 'expand' }

    // Delay highlight to ensure nodes are rendered first
    setTimeout(() => {
      setHighlightedPath(highlightPath)
      setHighlightedTarget(node.id)  // Track which node is the actual search target
      setHighlightSource('search')
    }, 350)
  }, [getPathToNode, searchableNodes])

  // Show node in Global View (from Local View)
  // Expands path to node, switches to Global View, highlights and zooms to node
  const showInGlobalView = useCallback((nodeId: string) => {
    // Get path from root to target node
    const pathToExpand = getPathToNode(nodeId)

    // Calculate highlight path: from target node up to Ring 1 ancestor
    const nodeMap = new Map(searchableNodes.map(n => [n.id, n]))
    const highlightPath = new Set<string>()
    highlightPath.add(nodeId)

    let current = nodeMap.get(nodeId)
    while (current && current.parentId) {
      const parent = nodeMap.get(current.parentId)
      if (parent) {
        highlightPath.add(parent.id)
        // Stop at Ring 1 (outcome level)
        if (parent.ring <= 1) break
      }
      current = parent
    }

    // Expand all nodes in path
    setExpandedNodes(prev => {
      const next = new Set(prev)
      pathToExpand.forEach(id => next.add(id))
      return next
    })

    // Switch to Global View
    setViewMode('global')

    // Set pending zoom to frame the target node
    pendingZoomRef.current = { nodeId, action: 'expand' }

    // Delay highlight to ensure nodes are rendered first
    setTimeout(() => {
      setHighlightedPath(highlightPath)
      setHighlightedTarget(nodeId)
      setHighlightSource('search')
    }, 350)
  }, [getPathToNode, searchableNodes])

  // Close search results when clicking outside
  useEffect(() => {
    const handleClickOutside = (e: MouseEvent) => {
      const target = e.target as HTMLElement
      if (!target.closest('.search-container')) {
        setShowSearchResults(false)
      }
    }
    document.addEventListener('click', handleClickOutside)
    return () => document.removeEventListener('click', handleClickOutside)
  }, [])

  // Keyboard shortcut for search (Ctrl/Cmd + K or /)
  useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
      if (e.target instanceof HTMLInputElement || e.target instanceof HTMLTextAreaElement) return

      if (e.key === '/' || ((e.ctrlKey || e.metaKey) && e.key === 'k')) {
        e.preventDefault()
        searchInputRef.current?.focus()
      }

      // Escape to close search
      if (e.key === 'Escape') {
        setShowSearchResults(false)
        searchInputRef.current?.blur()
      }

      // C to clear working context (preserve country/region/stratum scope)
      if (e.key === 'c' || e.key === 'C') {
        e.preventDefault()
        clearWorkingContext()
      }

      // Space to toggle timeline play/pause
      if (e.key === ' ') {
        e.preventDefault()
        if (isPlaying) {
          storePause()
        } else {
          storePlay()
        }
      }

      // +/= to expand next ring layer, -/_ to collapse outermost ring layer
      if (e.key === '+' || e.key === '=') {
        e.preventDefault()
        const maxRing = visibleNodes.reduce((max, n) => Math.max(max, n.ring), 0)
        if (maxRing < 5) expandRing(maxRing)
      }
      if (e.key === '-' || e.key === '_') {
        e.preventDefault()
        const maxRing = visibleNodes.reduce((max, n) => Math.max(max, n.ring), 0)
        if (maxRing > 0) collapseRing(maxRing - 1)
      }
    }
    window.addEventListener('keydown', handleKeyDown)
    return () => window.removeEventListener('keydown', handleKeyDown)
  }, [clearWorkingContext, visibleNodes, expandRing, collapseRing, isPlaying, storePlay, storePause])

  // Fetch data once on mount
  const fetchData = useCallback(async () => {
    setLoading(true)
    setError(null)

    try {
      const response = await fetch(DATA_FILE)
      if (!response.ok) throw new Error(`Failed to load: ${response.status}`)
      const data: GraphDataV21 = await response.json()
      setRawData(data)

      // Count domains for legend (from indicators, layer 5)
      const counts: Record<string, number> = {}
      data.nodes.forEach(n => {
        if (n.layer === 5 && n.domain) {
          counts[n.domain] = (counts[n.domain] || 0) + 1
        }
      })
      setDomainCounts(counts)

      setLoading(false)
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to load')
      setLoading(false)
    }
  }, [])

  // Compute layout whenever expansion state or country selection changes
  // Layout is computed on VISIBLE nodes only, so nodes spread when siblings are collapsed
  // Ring radii are calculated DYNAMICALLY based on visible node count
  // Country selection affects node importance values and filters out uncovered nodes
  const computeLayout = useCallback(() => {
    if (!effectiveNodes || !viewportLayoutRef.current) return

    const vLayout = viewportLayoutRef.current

    // Use effectiveNodes which has country-specific importance and filters uncovered nodes
    const nodeById = new Map(effectiveNodes.map(n => [String(n.id), n]))

    // Determine which nodes are visible based on expansion state
    const visibleNodeIds = new Set<string>()

    // Root is always visible
    const rootNode = effectiveNodes.find(n => n.layer === 0)
    if (rootNode) {
      visibleNodeIds.add(String(rootNode.id))

      // Recursively add visible children (only if they exist in effectiveNodes)
      const addVisibleChildren = (nodeId: string) => {
        if (expandedNodes.has(nodeId)) {
          const node = nodeById.get(nodeId)
          if (node?.children) {
            for (const childId of node.children) {
              const childIdStr = String(childId)
              // Only add if node exists in effectiveNodes (may be filtered out for country)
              if (nodeById.has(childIdStr)) {
                visibleNodeIds.add(childIdStr)
                addVisibleChildren(childIdStr)
              }
            }
          }
        }
      }
      addVisibleChildren(String(rootNode.id))
    }

    // Pinned paths: individual nodes visible (no sibling expansion)
    for (const nodeId of pinnedPaths) {
      if (nodeById.has(nodeId)) {
        visibleNodeIds.add(nodeId)
      }
    }

    // When pinnedPaths is active, remap parent references so each visible node
    // points to its nearest visible ancestor. This compresses tree depth naturally:
    // e.g. a ring-5 indicator whose ring 2-4 ancestors were pruned remaps its parent
    // to its ring-1 ancestor, landing at tree depth 2 in the layout.
    // No gap-fill ancestors needed — the layout derives ring from tree depth.
    let parentOverrides: Map<string, string | undefined> | null = null
    if (pinnedPaths.size > 0) {
      parentOverrides = new Map()
      const fullNodeById = new Map(effectiveNodes.map(n => [String(n.id), n]))
      for (const nodeId of visibleNodeIds) {
        const node = fullNodeById.get(nodeId)
        if (!node?.parent) continue
        const rawParentId = String(node.parent)
        if (visibleNodeIds.has(rawParentId)) continue // Parent already visible, no remap needed
        // Walk up raw hierarchy to find nearest visible ancestor
        let cur = rawParentId
        while (cur && !visibleNodeIds.has(cur)) {
          const pn = fullNodeById.get(cur)
          cur = pn?.parent !== undefined ? String(pn.parent) : ''
        }
        parentOverrides.set(nodeId, cur || undefined)
      }
    }

    // Filter to visible nodes only, applying parent remaps for pinned mode
    const visibleRawNodes = effectiveNodes
      .filter(n => visibleNodeIds.has(String(n.id)))
      .map(n => {
        if (!parentOverrides) return n
        const id = String(n.id)
        if (!parentOverrides.has(id)) return n
        const newParent = parentOverrides.get(id)
        return { ...n, parent: newParent !== undefined ? Number(newParent) : undefined }
      })

    // Update viewport layout with current visible node count
    vLayout.updateContext({ visibleNodes: visibleRawNodes.length })
    const currentLayoutValues = vLayout.getLayoutValues()
    setLayoutValues(currentLayoutValues)

    // For pinned mode, compute actual tree depth (after parent remapping) for ring radii.
    // This ensures nodesByRing matches what computeRadialLayout will derive from tree depth.
    let depthOf: Map<string, number> | null = null
    if (pinnedPaths.size > 0) {
      depthOf = new Map()
      const childrenOf = new Map<string, string[]>()
      for (const n of visibleRawNodes) {
        const id = String(n.id)
        if (n.parent !== undefined) {
          const pid = String(n.parent)
          if (!childrenOf.has(pid)) childrenOf.set(pid, [])
          childrenOf.get(pid)!.push(id)
        }
      }
      // BFS from root to compute depths
      const root = visibleRawNodes.find(n => n.parent === undefined || n.parent === null)
      if (root) {
        const queue = [{ id: String(root.id), depth: 0 }]
        depthOf.set(String(root.id), 0)
        while (queue.length > 0) {
          const { id, depth } = queue.shift()!
          const kids = childrenOf.get(id) ?? []
          for (const kid of kids) {
            depthOf.set(kid, depth + 1)
            queue.push({ id: kid, depth: depth + 1 })
          }
        }
      }
    }

    // Group nodes by ring for radius calculation
    const nodesByRing = new Map<number, Array<{ importance?: number }>>()
    visibleRawNodes.forEach(n => {
      const id = String(n.id)
      // In pinned mode, use tree depth as ring index (matches layout); otherwise use layer
      const ring = depthOf ? (depthOf.get(id) ?? n.layer) : n.layer
      if (!nodesByRing.has(ring)) nodesByRing.set(ring, [])
      nodesByRing.get(ring)!.push({ importance: n.importance })
    })

    // Determine how many rings are actually needed
    const maxRing = depthOf
      ? Math.max(0, ...depthOf.values()) + 1
      : 6

    // Calculate DYNAMIC ring radii using viewport-aware layout — natural density-based
    const rawRadii = vLayout.calculateRingRadii(nodesByRing, Math.max(maxRing, 2))
    // Pad to 6 entries so generateRingConfigs always has enough
    const dynamicRadii = [...rawRadii]
    while (dynamicRadii.length < 6) {
      dynamicRadii.push(dynamicRadii[dynamicRadii.length - 1] + 100)
    }

    // Update ringRadii state so sliders reflect current values
    setRingRadii(dynamicRadii)

    // Generate ring configs from dynamic radii
    const dynamicRingConfigs = generateRingConfigs(dynamicRadii)

    // Count expanded Ring 1 branches for text boost calculation
    const expandedBranchCount = visibleRawNodes.filter(
      n => n.layer === 1 && expandedNodes.has(String(n.id))
    ).length
    const totalOutcomeCount = visibleRawNodes.filter(n => n.layer === 1).length

    // Build text config for text-aware spacing
    const textConfig: TextConfig = {
      expandedBranchCount,
      totalOutcomeCount,
      minReadableSize: 3,
      maxBoostedSize: 5,
      minFontSize: currentLayoutValues.textMinSize,
      maxFontSize: currentLayoutValues.textMaxSize
    }

    const contextScope = selectedCountry
      ? `country:${selectedCountry}`
      : selectedRegion
        ? `region:${selectedRegion}`
        : `stratum:${selectedStratum}`
    const traceContextKey = `${contextScope}|playback:${playbackMode}|pinned:${pinnedPaths.size > 0 ? '1' : '0'}`
    const maxOutcomeRotationStep = getOutcomeRotationStep(activeLayoutActionRef.current)

    // Build layout config with dynamic radii and viewport-aware sizing
    const layoutConfig: LayoutConfig = {
      rings: dynamicRingConfigs,
      nodePadding,
      startAngle: -Math.PI / 2,
      totalAngle: 2 * Math.PI,
      minRingGap: currentLayoutValues.ringGap,
      useFixedRadii: true,
      // Pass viewport-aware sizing parameters
      sizeRange: currentLayoutValues.sizeRange,
      baseSpacing: currentLayoutValues.baseSpacing,
      spacingScaleFactor: 0.3,  // Scale factor remains constant
      maxSpacing: currentLayoutValues.maxSpacing,
      // Pass text config for text-aware spacing
      textConfig,
      // Pass causal hints for angular clustering during simulation
      causalHint: playbackMode === 'simulation' ? causalHint : undefined,
      prevOutcomeSectorSnapshot: outcomeSectorSnapshotRef.current ?? undefined,
      maxOutcomeRotationStep
    }

    // Compute layout using ring-independent angular positioning algorithm
    // Each ring positions independently - children spread to fill available space
    // Pass expandedNodes for smart lateral-first sector filling of outcomes
    const layoutResult = computeRadialLayout(visibleRawNodes, layoutConfig, expandedNodes)
    const { computedRings } = layoutResult
    outcomeSectorSnapshotRef.current = layoutResult.outcomeSectorSnapshot
    if (import.meta.env.DEV) {
      layoutTrace.record({
        action: activeLayoutActionRef.current ?? 'passive',
        contextKey: traceContextKey,
        snapshot: layoutResult.outcomeSectorSnapshot,
      })
    }

    // Post-process: resolve any remaining overlaps by pushing nodes apart
    resolveOverlaps(layoutResult.nodes, computedRings, nodePadding, 50)

    // Detect any remaining overlaps for stats
    const overlaps = detectOverlaps(layoutResult.nodes, computedRings, nodePadding)

    // Compute layout statistics
    const layoutStats = computeLayoutStats(layoutResult.nodes, computedRings, nodePadding)

    // Convert to ExpandableNodes
    const expandableNodes: ExpandableNode[] = layoutResult.nodes.map(toExpandableNode)

    // Build structural edges
    const structuralEdges: StructuralEdge[] = []
    for (const layoutNode of layoutResult.nodes) {
      if (layoutNode.parent) {
        structuralEdges.push({
          sourceId: layoutNode.parent.id,
          targetId: layoutNode.id,
          sourceRing: layoutNode.parent.ring,
          targetRing: layoutNode.ring
        })
      }
    }

    // Store data for rendering
    setAllNodes(expandableNodes)
    setAllEdges(structuralEdges)
    setComputedRingsState(computedRings)

    // Compute ring stats using dynamicRingConfigs
    const computedRingStats = dynamicRingConfigs.map((ring, i) => ({
      label: ring.label,
      count: layoutStats.nodesPerRing.get(i) || 0,
      minDistance: layoutStats.minDistancePerRing.get(i) || 0
    }))
    setRingStats(computedRingStats)

    // Compute outcome count
    const outcomeCount = expandableNodes.filter(n => n.isOutcome).length
    const driverCount = expandableNodes.filter(n => n.isDriver).length

    setStats({
      nodes: expandableNodes.length,
      structuralEdges: structuralEdges.length,
      outcomes: outcomeCount,
      drivers: driverCount,
      overlaps: overlaps.length
    })
  }, [effectiveNodes, nodePadding, expandedNodes, pinnedPaths, playbackMode, causalHint, selectedCountry, selectedRegion, selectedStratum])  // Uses effectiveNodes for country-specific importance

  // Render visible nodes and edges (called when expansion state changes)
  const renderVisualization = useCallback(() => {
    if (!svgRef.current || visibleNodes.length === 0 || !viewportLayoutRef.current || !layoutValues) return

    const vLayout = viewportLayoutRef.current
    const svg = d3.select(svgRef.current)
    // In split mode, Global View only takes the left portion
    const width = viewMode === 'split' ? window.innerWidth * splitRatio : window.innerWidth
    const height = window.innerHeight
    svg.attr('width', width).attr('height', height)

    // Accessible SVG title + description (screen readers)
    if (svg.select('title').empty()) {
      svg.insert('title', ':first-child')
    }
    svg.select('title').text('')  // Keep element for a11y tree but clear text to avoid browser hover tooltip
    if (svg.select('desc').empty()) {
      svg.insert('desc', 'title + *').raise()
      // Ensure desc follows title
    }
    svg.select('desc').text(
      `${visibleNodes.length} nodes and ${visibleEdges.length} edges visualized as concentric rings`
    )

    // Get or create persistent container with layered groups for z-ordering
    let g = svg.select<SVGGElement>('g.graph-container')
    if (g.empty()) {
      g = svg.append('g')
        .attr('class', 'graph-container')
        .style('will-change', 'transform')
      // Create layer groups in correct z-order (first = back, last = front)
      g.append('g').attr('class', 'layer-rings').attr('aria-hidden', 'true')
      g.append('g').attr('class', 'layer-glow-local')  // Cyan glow for Local View nodes
      g.append('g').attr('class', 'layer-glow-sim')    // Simulation effect glow (green/red)
      g.append('g').attr('class', 'layer-glow')  // Glow layer for search highlights (yellow)
      g.append('g').attr('class', 'layer-edges')
      g.append('g').attr('class', 'layer-nodes')
      g.append('g').attr('class', 'layer-labels')
    }

    // Get layer references
    const ringsLayer = g.select<SVGGElement>('g.layer-rings')
    const localGlowLayer = g.select<SVGGElement>('g.layer-glow-local')
    const simGlowLayer = g.select<SVGGElement>('g.layer-glow-sim')
    const glowLayer = g.select<SVGGElement>('g.layer-glow')
    const edgesLayer = g.select<SVGGElement>('g.layer-edges')
    const nodesLayer = g.select<SVGGElement>('g.layer-nodes')
    const labelsLayer = g.select<SVGGElement>('g.layer-labels')

    // Zoom level thresholds for CSS-based label visibility
    const getZoomClass = (scale: number): string => {
      if (scale < 1.0) return 'zoom-xs'
      if (scale < 1.6) return 'zoom-sm'
      if (scale < 2.5) return 'zoom-md'
      if (scale < 4.0) return 'zoom-lg'
      return 'zoom-xl'
    }

    // Helper to update QoL node screen position from transform (direct DOM, no React re-render)
    const updateQolPosition = (transform: d3.ZoomTransform) => {
      qolNodePositionRef.current = { x: transform.x, y: transform.y }
      if (spinnerElRef.current) {
        spinnerElRef.current.style.left = `${transform.x}px`
        spinnerElRef.current.style.top = `${transform.y}px`
      }
    }

    // Setup zoom behavior (only once)
    if (!zoomRef.current) {
      const zoom = d3.zoom<SVGSVGElement, unknown>()
        .scaleExtent([0.05, 20])
        .on('zoom', (event) => {
          g.attr('transform', event.transform)
          currentTransformRef.current = event.transform
          const zoomClass = getZoomClass(event.transform.k)
          g.attr('class', `graph-container ${zoomClass}`)
          updateQolPosition(event.transform)
        })
      zoomRef.current = zoom
      svg.call(zoom)

      // Initial view - use shared calculation
      const initialTransform = calculateInitialTransform(visibleNodes)
      svg.call(zoom.transform, initialTransform)
      currentTransformRef.current = initialTransform
      updateQolPosition(initialTransform)
    }

    // Check if we need to recalculate zoom based on view mode or split ratio changes
    const prevViewMode = prevViewModeForVizRef.current
    const prevSplitRatio = prevSplitRatioRef.current

    // Helper: Calculate transform to fit highlighted nodes (Local View nodes) tightly
    const calculateHighlightedFitTransform = (containerWidth: number, containerHeight: number): d3.ZoomTransform | null => {
      if (localViewNodeIds.size === 0) return null

      const highlightedNodes = visibleNodes.filter(n => localViewNodeIds.has(n.id))
      if (highlightedNodes.length === 0) return null

      // Calculate bounding box of highlighted nodes + root (0,0)
      const allXs = highlightedNodes.map(n => n.x)
      const allYs = highlightedNodes.map(n => n.y)

      const boundsMinX = Math.min(0, ...allXs)
      const boundsMaxX = Math.max(0, ...allXs)
      const boundsMinY = Math.min(0, ...allYs)
      const boundsMaxY = Math.max(0, ...allYs)

      const boundsWidth = boundsMaxX - boundsMinX
      const boundsHeight = boundsMaxY - boundsMinY

      const centerX = (boundsMinX + boundsMaxX) / 2
      const centerY = (boundsMinY + boundsMaxY) / 2

      // Tight padding (5% margin) to fill the screen
      const padding = 0.05
      const scaleX = containerWidth * (1 - 2 * padding) / Math.max(boundsWidth, 1)
      const scaleY = containerHeight * (1 - 2 * padding) / Math.max(boundsHeight, 1)
      const fitScale = Math.min(scaleX, scaleY, 3) // Cap at 3x zoom

      const newX = containerWidth / 2 - centerX * fitScale
      const newY = getGraphCenterY(containerHeight) - centerY * fitScale

      return d3.zoomIdentity.translate(newX, newY).scale(fitScale)
    }

    // Case 1: Switched TO global-only mode from split/local - fit to highlighted nodes or all
    const wasInSplitOrLocal = prevViewMode === 'split' || prevViewMode === 'local'
    const nowInGlobalOnly = viewMode === 'global'
    if (wasInSplitOrLocal && nowInGlobalOnly && zoomRef.current) {
      const containerWidth = window.innerWidth
      const containerHeight = window.innerHeight
      const highlightedTransform = calculateHighlightedFitTransform(containerWidth, containerHeight)
      const resetTransform = highlightedTransform || calculateInitialTransform(visibleNodes)
      svg.transition().duration(300).call(zoomRef.current.transform, resetTransform)
      currentTransformRef.current = resetTransform
    }

    // Case 2: Switched TO split view - fit to highlighted nodes in reduced width
    const nowInSplit = viewMode === 'split'
    const wasNotInSplit = prevViewMode !== 'split'
    if (nowInSplit && wasNotInSplit && zoomRef.current) {
      const containerWidth = window.innerWidth * splitRatio
      const containerHeight = window.innerHeight
      const highlightedTransform = calculateHighlightedFitTransform(containerWidth, containerHeight)
      const resetTransform = highlightedTransform || calculateInitialTransform(visibleNodes, containerWidth, containerHeight)
      svg.transition().duration(300).call(zoomRef.current.transform, resetTransform)
      currentTransformRef.current = resetTransform
    }

    // Case 3: Split ratio changed significantly while in split view (>5% change)
    const splitRatioChanged = Math.abs(splitRatio - prevSplitRatio) > 0.05
    if (nowInSplit && splitRatioChanged && zoomRef.current) {
      const containerWidth = window.innerWidth * splitRatio
      const containerHeight = window.innerHeight
      const highlightedTransform = calculateHighlightedFitTransform(containerWidth, containerHeight)
      const resetTransform = highlightedTransform || calculateInitialTransform(visibleNodes, containerWidth, containerHeight)
      svg.transition().duration(200).call(zoomRef.current.transform, resetTransform)
      currentTransformRef.current = resetTransform
    }

    // Update refs for next render
    prevViewModeForVizRef.current = viewMode
    prevSplitRatioRef.current = splitRatio

    // Restore transform if not animating
    if (!isAnimatingZoomRef.current && currentTransformRef.current) {
      g.attr('transform', currentTransformRef.current.toString())
    }

    // === HELPER FUNCTIONS ===

    // Use pre-computed aggregate effects (leaf + parent nodes) for border rendering
    // simEffectLookup: Map<string, { pct, coverage, isLeaf }>
    const simEffectLookup = aggregateEffects

    // Set of node IDs that have at least one visible child (used for parent eligibility)
    const hasVisibleChild = new Set<string>()
    for (const n of visibleNodes) {
      if (n.parentId) hasVisibleChild.add(n.parentId)
    }

    // Build top-K eligible parents per ring for border display.
    // Parents need at least one visible child AND |pct| >= 1%.
    const TOP_K_PER_RING = 10
    const PARENT_MIN_PCT = 1.0
    const LEAF_MIN_PCT = 0.5

    const borderEligible = new Set<string>()
    // Leaves: eligible if |pct| >= LEAF_MIN_PCT
    // Parents: gate on coverage + pct, then top-K per ring
    const parentsByRing = new Map<number, Array<{ id: string; score: number }>>()
    for (const node of visibleNodes) {
      const eff = simEffectLookup.get(node.id)
      if (!eff) continue
      if (eff.isLeaf) {
        if (Math.abs(eff.pct) >= LEAF_MIN_PCT) borderEligible.add(node.id)
      } else {
        // Parent gating: must have at least one visible child
        if (!hasVisibleChild.has(node.id)) continue
        if (Math.abs(eff.pct) >= PARENT_MIN_PCT) {
          const score = Math.abs(eff.pct)
          if (!parentsByRing.has(node.ring)) parentsByRing.set(node.ring, [])
          parentsByRing.get(node.ring)!.push({ id: node.id, score })
        }
      }
    }
    // Top-K parents per ring
    for (const [, parents] of parentsByRing) {
      parents.sort((a, b) => b.score - a.score)
      for (const p of parents.slice(0, TOP_K_PER_RING)) {
        borderEligible.add(p.id)
      }
    }

    // Set of intervention indicator IDs (for distinct highlight treatment)
    const interventionNodeIds = new Set(
      storeInterventions.map(i => i.indicator).filter(Boolean)
    )

    // QoL score for ring 0 outline/text (country, regional, stratum, or global scope).
    // In simulation playback this value comes from temporalResults.qol_timeline (simulated).
    const qolNodeScore = qolNodeScoreForTooltip

    /**
     * Get node fill color — blends toward green/red when simulation-affected.
     * Intensity: clamp(|percent_change| / 50, 0, 0.5) — subtle, max 50% blend.
     * Only in global view, only for non-intervention affected nodes.
     * Bridge nodes (in causal_paths but not in aggregateEffects) get no tint.
     */
    const getColor = (n: ExpandableNode): string => {
      if (n.ring === 0) return '#78909C' // fill always grey; outline carries QoL color
      const domainColor = DOMAIN_COLORS[n.semanticPath.domain] || '#9E9E9E'

      // Only tint in global view when simulation results exist
      if (viewMode !== 'global' && viewMode !== 'split') return domainColor
      if (!temporalResults || interventionNodeIds.has(n.id)) return domainColor

      // Leaf nodes stay domain color — edge ripples + node flash glows signal effects
      return domainColor
    }

    // Node sizing uses importance (0-1) mapped to area
    // Historical playback: use pre-cached temporal SHAP values (V3.1 data)
    // Simulation mode: apply temporal effects

    // Get pre-cached SHAP for current year (O(1) lookup from pre-computed cache)
    const currentYearForShap = historicalTimeline?.years[currentYearIndex]
    let timelineImportance = (playbackMode === 'historical' && currentYearForShap)
      ? (precomputedShapCache.get(currentYearForShap) || new Map<string, number>())
      : new Map<string, number>()

    // Cache valid SHAP data; use cache during loading to maintain node sizes
    if (timelineImportance.size > 0) {
      lastValidShapRef.current = timelineImportance
    } else if (lastValidShapRef.current.size > 0) {
      // Use cached SHAP during loading (prevents nodes shrinking to 0)
      timelineImportance = lastValidShapRef.current
    }

    const nonNegative = (value: number | undefined, fallback = 0): number => {
      if (value === undefined || !Number.isFinite(value)) return fallback
      return Math.max(0, value)
    }

    const finalizeRadius = (node: ExpandableNode, radius: number): number => {
      const safeRadius = Number.isFinite(radius) && radius > 0 ? radius : vLayout.getNodeRadius(0.01)
      // Keep ring-1 outcomes visually stable even if yearly SHAP momentarily drops.
      if (node.ring === 1) {
        const ring1Floor = vLayout.getNodeRadius(0.12)
        return Math.max(safeRadius, ring1Floor)
      }
      return safeRadius
    }

    const getSize = (n: ExpandableNode): number => {
      // Ring 0 (QoL): size encodes relative QoL level (0.5–1.0), max in unified mode
      if (n.ring === 0) {
        const sizeImp = qolNodeScore != null ? 0.5 + qolNodeScore * 0.5 : 1.0
        return finalizeRadius(n, vLayout.getNodeRadius(sizeImp))
      }

      const nodeId = String(n.id)

      // For all other rings, use temporal SHAP (v3.1 data)
      if (playbackMode === 'historical') {
        if (timelineImportance.size > 0) {
          const historicalImp = timelineImportance.get(nodeId)
          if (historicalImp !== undefined) {
            return finalizeRadius(n, vLayout.getNodeRadius(nonNegative(historicalImp, 0)))
          }
        }

        // Fallback to cached SHAP, then raw importance so first paint remains meaningful.
        const cachedImp = lastValidShapRef.current.get(nodeId)
        if (cachedImp !== undefined) return finalizeRadius(n, vLayout.getNodeRadius(nonNegative(cachedImp, 0)))
        const baseFallbackImportance = n.ring <= 1
          ? Math.max(0.15, nonNegative(n.importance, 0))
          : Math.max(0.01, nonNegative(n.importance, 0))
        return finalizeRadius(n, vLayout.getNodeRadius(baseFallbackImportance))
      }

      // Simulation mode: baseline importance shifted by percent_change.
      if (playbackMode === 'simulation') {
        const baseImp = nonNegative(lastValidShapRef.current.get(nodeId), nonNegative(n.importance, 0.01))
        if (temporalResults) {
          const simYear = temporalResults.base_year + currentYearIndex
          const yearEffects = temporalResults.effects[String(simYear)]
          if (yearEffects && yearEffects[n.id]) {
            const pctChange = yearEffects[n.id].percent_change / 100
            return finalizeRadius(n, vLayout.getNodeRadius(Math.max(0, baseImp * (1 + pctChange))))
          }
        }
        return finalizeRadius(n, vLayout.getNodeRadius(baseImp))
      }

      // Last resort: prefer cached SHAP, then base importance.
      const cachedImp = lastValidShapRef.current.get(nodeId)
      if (cachedImp !== undefined) return finalizeRadius(n, vLayout.getNodeRadius(nonNegative(cachedImp, 0)))
      return finalizeRadius(n, vLayout.getNodeRadius(Math.max(0.01, nonNegative(n.importance, 0))))
    }

    const isNodeFloored = (importance: number): boolean => {
      return vLayout.isNodeFloored(Math.max(0, importance))
    }

    const getPercentileInRing = (node: ExpandableNode): number => {
      const ringNodes = nodesByRingMemo.get(node.ring) || []
      if (ringNodes.length <= 1) return 1
      const sorted = ringNodes.map(n => n.importance).sort((a, b) => b - a)
      const rank = sorted.findIndex(imp => imp <= node.importance)
      return 1 - (rank / sorted.length)
    }

    const getBorderWidth = (node: ExpandableNode): number => {
      const percentile = getPercentileInRing(node)
      let baseWidth: number
      if (percentile >= 0.95) baseWidth = 2
      else if (percentile >= 0.75) baseWidth = 1.5
      else if (percentile >= 0.50) baseWidth = 1
      else baseWidth = 0.75
      const radius = getSize(node)
      return Math.min(baseWidth, radius * 0.5)
    }

    /**
     * Get simulation-aware stroke properties for an affected node.
     *
     * Eligibility gating (computed above in borderEligible):
     *   Leaf: |pct| >= 0.5%
     *   Parent: coverage >= 15% AND |pct| >= 1.0% AND in top-K by score per ring
     *
     * Width: saturating curve — width = minPx + maxExtraPx * (1 - e^(-|pct|/s))
     *   Leaf:   minPx=0.6, maxExtraPx=2.4, s=6
     *   Parent: minPx=0.4, maxExtraPx=1.6, s=6
     *
     * Color alpha scales by coverage for parents (honest visual weight).
     * Ineligible parents get no border (subtle glow handled separately).
     */
    // Simulation fill mode remains active once playback has started for this run.
    // This keeps scrubbing responsive even when paused (once playback has started).
    const simPlaybackActive =
      playbackMode === 'simulation' &&
      isPanelOpen &&
      isPlaying
    const hideQolStroke =
      playbackMode === 'simulation' &&
      temporalResults !== null

    const getSimBorder = (node: ExpandableNode): { color: string; width: number; opacity: number } | null => {
      if (simPlaybackActive) return null  // During playback/scrub: fill, not borders
      if (!isPanelOpen) return null        // Panel closed: no sim visuals
      if (node.ring === 0) return null
      if (interventionNodeIds.has(node.id)) return null
      // Don't show border on parent nodes that have no visible children
      if (node.hasChildren && !hasVisibleChild.has(node.id)) return null

      const eff = simEffectLookup.get(node.id)
      if (!eff) return null

      // Must be in the eligible set (gating + top-K)
      if (!borderEligible.has(node.id)) return null

      const absPct = Math.abs(eff.pct)
      const S = 6 // saturation constant: 6% gives a decent ring, 20% saturates
      // Effect intensity: 0→0, 6%→0.63, 20%→0.96, 50%→1.0
      const intensity = 1 - Math.exp(-absPct / S)

      let width: number
      let opacity: number

      if (eff.isLeaf) {
        // Border proportional to node radius so it doesn't overwhelm small nodes
        const radius = getSize(node)
        // 10-25% of radius, scaled by effect intensity
        width = radius * (0.1 + 0.15 * intensity)
        // Minimum 0.5px for visibility, cap at 2px
        width = Math.max(0.5, Math.min(2, width))
        opacity = 1.0
      } else {
        const radius = getSize(node)
        width = radius * (0.08 + 0.12 * intensity)
        width = Math.max(0.4, Math.min(1.5, width))
        opacity = Math.max(0.2, Math.min(1.0, 0.2 + 0.8 * eff.coverage))
      }

      return {
        color: eff.pct >= 0 ? '#39FF14' : '#FF1744',
        width,
        opacity
      }
    }

    /**
     * Subtle glow for ineligible parent nodes that have SOME effect
     * but didn't pass the coverage/magnitude gating. Returns opacity 0-0.25.
     */
    const getSimGlowForIneligible = (node: ExpandableNode): { color: string; opacity: number } | null => {
      if (simPlaybackActive || !isPanelOpen) return null  // Only show when panel open + playback stopped
      if (node.ring === 0 || !node.hasChildren) return null
      if (interventionNodeIds.has(node.id)) return null
      if (borderEligible.has(node.id)) return null // Already has a border

      const eff = simEffectLookup.get(node.id)
      if (!eff || eff.isLeaf) return null

      const alpha = Math.min(0.25, Math.abs(eff.pct) * eff.coverage / 20)
      if (alpha < 0.03) return null // Too faint to bother

      return {
        color: eff.pct >= 0 ? '#39FF14' : '#FF1744',
        opacity: alpha
      }
    }

    const getParentPosition = (node: ExpandableNode): { x: number; y: number } => {
      if (node.parentId) {
        // Check NEW positions first (from current layout) so enter nodes
        // start from parent's final position after rotation
        const parent = visibleNodes.find(n => n.id === node.parentId)
        if (parent) return { x: parent.x, y: parent.y }
        // Fall back to previous positions for edge cases
        const parentPos = nodePositionsRef.current.get(node.parentId)
        if (parentPos) return parentPos
      }
      return { x: 0, y: 0 }
    }

    // Detect new vs existing vs exiting nodes
    const prevVisibleIds = prevVisibleNodeIdsRef.current
    const currentVisibleIds = new Set(visibleNodes.map(n => n.id))
    const newNodeIds = new Set<string>()
    const existingNodeIds = new Set<string>()  // Nodes that existed before and still exist

    const actuallyMovingNodeIds = new Set<string>()  // Nodes whose position actually changed
    const exitingNodeIds = new Set<string>()

    // Threshold for considering a position "changed" (in pixels)
    const POSITION_CHANGE_THRESHOLD = 1

    // Dots mode: deep-ring nodes rendered as lightweight dots (no labels/glows/transitions)
    // Only active when triggered by Rings menu bulk expansion
    const DEEP_RING_THRESHOLD = 4
    const dotsMode = dotsModeRef.current

    currentVisibleIds.forEach(id => {
      if (!prevVisibleIds.has(id)) {
        newNodeIds.add(id)
      } else {
        existingNodeIds.add(id)
        // Check if position actually changed
        const prevPos = nodePositionsRef.current.get(id)
        const node = visibleNodes.find(n => n.id === id)
        if (prevPos && node) {
          const dx = Math.abs(node.x - prevPos.x)
          const dy = Math.abs(node.y - prevPos.y)
          if (dx > POSITION_CHANGE_THRESHOLD || dy > POSITION_CHANGE_THRESHOLD) {
            actuallyMovingNodeIds.add(id)
          }
        }
      }
    })
    prevVisibleIds.forEach(id => {
      if (!currentVisibleIds.has(id)) {
        exitingNodeIds.add(id)
      }
    })

    const previousEdgeIds = prevVisibleEdgeIdsRef.current
    const currentEdgeIds = new Set(visibleEdges.map(e => `${e.sourceId}-${e.targetId}`))
    let edgeDelta = 0
    currentEdgeIds.forEach(id => {
      if (!previousEdgeIds.has(id)) edgeDelta += 1
    })
    previousEdgeIds.forEach(id => {
      if (!currentEdgeIds.has(id)) edgeDelta += 1
    })

    // Determine animation timing based on expand vs collapse:
    // EXPAND sequence: Rotation → Nodes/Edges enter → Text appears
    // COLLAPSE sequence: Text disappears → Nodes/Edges exit → Rotation
    const isCollapsing = exitingNodeIds.size > 0
    const nodeDelta = newNodeIds.size + exitingNodeIds.size
    const layoutAction = activeLayoutActionRef.current
      ?? (isCollapsing ? 'single_collapse' : 'single_expand')
    const activeBudget = resolveLayoutBudget({
      action: layoutAction,
      nodeDelta,
      edgeDelta
    })
    activeLayoutBudgetRef.current = activeBudget
    if (activeLayoutActionRef.current) {
      setStructuralLock(activeBudget.structuralLockMs)
    }

    const isFirstVisibleRender = prevVisibleIds.size === 0 && currentVisibleIds.size > 0
    const hasRotation = !activeBudget.useFastPath && actuallyMovingNodeIds.size > 0

    const rotationDuration = activeBudget.rotationMs
    const enterExitDuration = isFirstVisibleRender
      ? Math.min(activeBudget.enterExitMs, 120)
      : activeBudget.enterExitMs
    const textFadeDuration = isFirstVisibleRender
      ? Math.min(activeBudget.textFadeMs, 90)
      : activeBudget.textFadeMs
    const exitDuration = activeBudget.exitMs  // Duration for nodes/edges collapsing

    // Timing for EXPAND: rotation first, then enter, then text
    const expandEnterDelay = isFirstVisibleRender ? 0 : (hasRotation ? rotationDuration : 0)
    const expandTextDelay = isFirstVisibleRender ? 0 : (expandEnterDelay + enterExitDuration)

    // Timing for COLLAPSE: text first, then exit, then rotation
    // Sequence: Text fades (0-150ms) → Nodes collapse (150-350ms) → Rotation starts after collapse complete
    const collapseTextDelay = 0  // Text disappears immediately
    const collapseExitDelay = textFadeDuration  // Exit after text fades (150ms)
    const collapseExitEndTime = collapseExitDelay + exitDuration  // When collapse finishes (350ms)
    const collapseRotationDelay = collapseExitEndTime + activeBudget.collapseGapMs
    const rotationDelay = isCollapsing ? collapseRotationDelay : 0

    // Build node map
    const nodeMap = new Map<string, ExpandableNode>()
    visibleNodes.forEach(n => nodeMap.set(n.id, n))

    // === RING CIRCLES (data join pattern) ===
    const visibleRings = new Set(visibleNodes.map(n => n.ring))
    const ringData = computedRingsState
      .map((ring, i) => ({ ...ring, index: i }))
      .slice(1)
      .filter(ring => visibleRings.has(ring.index))

    // Ring outlines
    ringsLayer.selectAll<SVGCircleElement, typeof ringData[0]>('circle.ring-outline')
      .data(ringData, d => d.index)
      .join(
        enter => enter.append('circle')
          .attr('class', 'ring-outline')
          .attr('cx', 0)
          .attr('cy', 0)
          .attr('fill', 'none')
          .attr('stroke', '#e5e5e5')
          .attr('stroke-width', 1.5)
          .attr('r', d => d.radius),
        update => update.attr('r', d => d.radius),
        exit => exit.remove()
      )

    // Ring labels (commented out — may re-enable later)
    // ringsLayer.selectAll<SVGTextElement, typeof ringData[0]>('text.ring-label')
    //   .data(ringData, d => d.index)
    //   .join(
    //     enter => enter.append('text')
    //       .attr('class', 'ring-label')
    //       .attr('x', 0)
    //       .attr('text-anchor', 'middle')
    //       .attr('font-size', 10)
    //       .attr('font-weight', '400')
    //       .attr('fill', '#767676')
    //       .attr('fill-opacity', 1)
    //       .attr('y', d => -d.radius - 12)
    //       .text(d => d.label || ringConfigs[d.index]?.label || ''),
    //     update => update
    //       .attr('y', d => -d.radius - 12)
    //       .text(d => d.label || ringConfigs[d.index]?.label || ''),
    //     exit => exit.remove()
    //   )
    ringsLayer.selectAll('text.ring-label').remove()

    // === GLOW ANIMATION TIMING ===
    // Glows must wait until nodes finish ALL animation before appearing
    const isAnimating = isCollapsing || newNodeIds.size > 0 || actuallyMovingNodeIds.size > 0

    // Calculate when all node animations complete
    // COLLAPSE: text fade → exit → rotation
    // EXPAND: rotation → enter → text fade
    const nodeAnimationEndTime = isCollapsing
      ? (hasRotation ? collapseRotationDelay + rotationDuration : collapseExitEndTime)
      : (hasRotation ? expandEnterDelay + enterExitDuration : enterExitDuration)
    const structuralAnimationWindowMs = isAnimating ? nodeAnimationEndTime + activeBudget.glowBufferMs : 0

    // Glows appear after ALL node animations complete
    const glowReappearDelay = isAnimating ? nodeAnimationEndTime + activeBudget.glowBufferMs : 0

    // For collapse: glows follow nodes during rotation phase
    // For expand: glows wait until nodes finish entering before appearing
    const glowRotationDelay = isCollapsing ? collapseRotationDelay : 0
    const expandGlowDelay = hasRotation ? expandEnterDelay + enterExitDuration : enterExitDuration

    // === GLOW CIRCLES for search/sim highlight ===
    const glowColorTarget = highlightSource === 'sim' ? '#FF9800' : '#D32F2F'
    const glowColorParent = highlightSource === 'sim' ? '#FFE0B2' : '#FFCDD2'
    const highlightedNodes = visibleNodes.filter(n => highlightedPath.has(n.id))
    const glowSelection = glowLayer.selectAll<SVGCircleElement, ExpandableNode>('circle.glow')
      .data(highlightedNodes, d => d.id)

    // Remove old glows immediately
    glowSelection.exit().remove()

    // Only animate glows for nodes that ACTUALLY move - stationary nodes keep their glow visible
    const glowsToAnimate = glowSelection.filter(d => actuallyMovingNodeIds.has(d.id))
    const glowsToKeepVisible = glowSelection.filter(d => !actuallyMovingNodeIds.has(d.id))

    // Stationary glows - just update position immediately, stay visible
    glowsToKeepVisible.each(function(d) {
      const isTarget = d.id === highlightedTarget
      d3.select(this)
        .attr('cx', d.x)
        .attr('cy', d.y)
        .attr('r', getSize(d) + 3)
        .attr('stroke', isTarget ? glowColorTarget : glowColorParent)
        .attr('stroke-width', 3)
        .attr('opacity', 0.5)
    })

    // Moving glows - check actual DOM position vs target to determine if animation needed
    if (!activeBudget.useFastPath && actuallyMovingNodeIds.size > 0) {
      // Check each glow's node's ACTUAL DOM position vs target
      glowsToAnimate.each(function(d) {
        const glowEl = d3.select(this)
        const nodeEl = nodesLayer.select<SVGCircleElement>(`circle.node[data-id="${d.id}"]`)
        const isTarget = d.id === highlightedTarget
        const glowColor = isTarget ? glowColorTarget : glowColorParent

        if (!nodeEl.empty()) {
          const nodeCx = parseFloat(nodeEl.attr('cx') || '0')
          const nodeCy = parseFloat(nodeEl.attr('cy') || '0')
          const targetX = d.x
          const targetY = d.y

          // Check if node actually needs to move (compare DOM position to target)
          const dx = Math.abs(targetX - nodeCx)
          const dy = Math.abs(targetY - nodeCy)
          const nodeActuallyMoves = dx > POSITION_CHANGE_THRESHOLD || dy > POSITION_CHANGE_THRESHOLD

          if (nodeActuallyMoves) {
            // Sync glow to node's current DOM position, then animate
            glowEl
              .attr('cx', nodeCx)
              .attr('cy', nodeCy)
              .attr('opacity', 0)
              .attr('stroke', glowColor)
              .transition('glow-move')
              .delay(glowRotationDelay)
              .duration(rotationDuration)
              .ease(d3.easeCubicOut)
              .attr('cx', targetX)
              .attr('cy', targetY)
              .attr('r', getSize(d) + 3)

            glowEl
              .transition('glow-show')
              .delay(glowReappearDelay)
              .duration(200)
              .attr('opacity', 0.5)
          } else {
            // Node isn't actually moving - just update glow position, keep visible
            glowEl
              .attr('cx', targetX)
              .attr('cy', targetY)
              .attr('r', getSize(d) + 3)
              .attr('stroke', glowColor)
              .attr('opacity', 0.5)
          }
        }
      })
    } else if (activeBudget.useFastPath) {
      glowsToAnimate
        .attr('cx', d => d.x)
        .attr('cy', d => d.y)
        .attr('r', d => getSize(d) + 3)
        .attr('opacity', 0.5)
    }

    // Add new glows - RED for search (dark red for target, light pink for parents)
    // During collapse: start at OLD position, animate with nodes, then fade in
    // During expand: wait until node finishes entering, then fade in at final position
    const hasAnyAnimation = !activeBudget.useFastPath && (isCollapsing || actuallyMovingNodeIds.size > 0 || newNodeIds.size > 0)

    const newSearchGlows = glowSelection.enter()
      .append('circle')
      .attr('class', 'glow')
      .attr('cx', d => {
        // During collapse, start at old position so glow follows node
        if (isCollapsing) {
          const prevPos = nodePositionsRef.current.get(d.id)
          return prevPos?.x ?? d.x
        }
        // During expand, start at final position (will fade in after node enters)
        return d.x
      })
      .attr('cy', d => {
        if (isCollapsing) {
          const prevPos = nodePositionsRef.current.get(d.id)
          return prevPos?.y ?? d.y
        }
        return d.y
      })
      .attr('r', d => getSize(d) + 3)
      .attr('fill', 'none')
      .attr('stroke', d => d.id === highlightedTarget ? glowColorTarget : glowColorParent)
      .attr('stroke-width', 3)
      .attr('opacity', 0)  // Start hidden
      .style('filter', 'blur(2px)')
      .style('pointer-events', 'none')

    // Animate glows based on whether their SPECIFIC node's DOM position differs from target
    if (isCollapsing) {
      // COLLAPSE: check each glow's node's actual DOM position
      newSearchGlows.each(function(d) {
        const glowEl = d3.select(this)
        const nodeEl = nodesLayer.select<SVGCircleElement>(`circle.node[data-id="${d.id}"]`)

        if (!nodeEl.empty()) {
          const nodeCx = parseFloat(nodeEl.attr('cx') || '0')
          const nodeCy = parseFloat(nodeEl.attr('cy') || '0')
          const targetX = d.x
          const targetY = d.y

          // Check if node actually needs to move
          const dx = Math.abs(targetX - nodeCx)
          const dy = Math.abs(targetY - nodeCy)
          const nodeActuallyMoves = dx > POSITION_CHANGE_THRESHOLD || dy > POSITION_CHANGE_THRESHOLD

          if (nodeActuallyMoves) {
            // Node is moving: animate from current position to target
            glowEl
              .attr('cx', nodeCx)
              .attr('cy', nodeCy)
              .transition('new-glow-position')
              .delay(glowRotationDelay)
              .duration(rotationDuration)
              .ease(d3.easeCubicOut)
              .attr('cx', targetX)
              .attr('cy', targetY)
              .transition()
              .duration(200)
              .attr('opacity', 0.5)
          } else {
            // Node is stationary: snap to position, fade in after exit
            glowEl
              .attr('cx', targetX)
              .attr('cy', targetY)
              .transition()
              .delay(collapseExitEndTime + 50)
              .duration(200)
              .attr('opacity', 0.5)
          }
        } else {
          // Node not found, just fade in at target position
          glowEl
            .attr('cx', d.x)
            .attr('cy', d.y)
            .transition()
            .delay(collapseExitEndTime + 50)
            .duration(200)
            .attr('opacity', 0.5)
        }
      })
    } else if (hasAnyAnimation) {
      // EXPAND: wait until nodes finish entering, then fade in
      newSearchGlows
        .transition('new-glow-expand')
        .delay(expandGlowDelay + 50)
        .duration(200)
        .attr('opacity', 0.5)
    } else {
      // No animation - just fade in
      newSearchGlows
        .transition()
        .duration(200)
        .attr('opacity', 0.5)
    }

    // === GLOW for Local View nodes (different colors by role) ===
    // Target: cyan, Input: orange, Output: purple
    const LOCAL_GLOW_COLORS = {
      target: '#00BCD4',  // Cyan
      input: '#FF9800',   // Orange
      output: '#9C27B0'   // Purple
    }

    // Create set of visible node IDs for quick lookup
    const visibleNodeIds = new Set(visibleNodes.map(n => n.id))

    // For nodes not visible, find their visible ancestor and glow that instead
    // Map: visible node ID -> { node, role } (may aggregate multiple roles)
    const glowTargets = new Map<string, { node: ExpandableNode; role: 'target' | 'input' | 'output' }>()

    for (const [nodeId, role] of localViewNodeRoles.entries()) {
      if (visibleNodeIds.has(nodeId)) {
        // Node is visible, glow it directly
        const node = visibleNodes.find(n => n.id === nodeId)
        if (node) {
          glowTargets.set(nodeId, { node, role })
        }
      } else {
        // Node not visible, find visible ancestor
        let currentId = nodeId
        let foundAncestor: ExpandableNode | null = null

        // Walk up the tree to find visible parent
        while (!foundAncestor && currentId) {
          const rawNode = rawData?.nodes.find(n => String(n.id) === currentId)
          if (rawNode?.parent) {
            const parentId = String(rawNode.parent)
            if (visibleNodeIds.has(parentId)) {
              foundAncestor = visibleNodes.find(n => n.id === parentId) || null
            }
            currentId = parentId
          } else {
            break
          }
        }

        if (foundAncestor) {
          // Use highest priority role (target > input > output)
          const existing = glowTargets.get(foundAncestor.id)
          if (!existing || (role === 'target') || (role === 'input' && existing.role === 'output')) {
            glowTargets.set(foundAncestor.id, { node: foundAncestor, role })
          }
        }
      }
    }

    const nodesToGlow = Array.from(glowTargets.values()).map(g => ({ ...g.node, glowRole: g.role }))

    // Performance limit: max 50 nodes to prevent FPS drops
    const MAX_GLOW_NODES = 50
    const limitedNodesToGlow = nodesToGlow.length > MAX_GLOW_NODES
      ? nodesToGlow.slice(0, MAX_GLOW_NODES)
      : nodesToGlow

    // Type for glow nodes with role
    type GlowNode = ExpandableNode & { glowRole: 'target' | 'input' | 'output' }

    const localGlowSelection = localGlowLayer
      .selectAll<SVGCircleElement, GlowNode>('circle.glow-local')
      .data(limitedNodesToGlow as GlowNode[], d => d.id)

    // Remove old local glows immediately
    localGlowSelection.exit().remove()

    // Only animate glows for nodes that ACTUALLY move - stationary nodes keep their glow visible
    const localGlowsToAnimate = localGlowSelection.filter(d => actuallyMovingNodeIds.has(d.id))
    const localGlowsToKeepVisible = localGlowSelection.filter(d => !actuallyMovingNodeIds.has(d.id))

    // Stationary local glows - just update position immediately, stay visible
    localGlowsToKeepVisible
      .attr('cx', d => d.x)
      .attr('cy', d => d.y)
      .attr('r', d => getSize(d) + 3)
      .attr('stroke', d => LOCAL_GLOW_COLORS[d.glowRole])

    // Moving local glows - check actual DOM position vs target to determine if animation needed
    if (!activeBudget.useFastPath && actuallyMovingNodeIds.size > 0) {
      localGlowsToAnimate.each(function(d) {
        const glowEl = d3.select(this)
        const nodeEl = nodesLayer.select<SVGCircleElement>(`circle.node[data-id="${d.id}"]`)

        if (!nodeEl.empty()) {
          const nodeCx = parseFloat(nodeEl.attr('cx') || '0')
          const nodeCy = parseFloat(nodeEl.attr('cy') || '0')
          const targetX = d.x
          const targetY = d.y

          // Check if node actually needs to move (compare DOM position to target)
          const dx = Math.abs(targetX - nodeCx)
          const dy = Math.abs(targetY - nodeCy)
          const nodeActuallyMoves = dx > POSITION_CHANGE_THRESHOLD || dy > POSITION_CHANGE_THRESHOLD

          if (nodeActuallyMoves) {
            // Sync glow to node's current DOM position, then animate
            glowEl
              .attr('cx', nodeCx)
              .attr('cy', nodeCy)
              .attr('opacity', 0)
              .transition('local-glow-move')
              .delay(glowRotationDelay)
              .duration(rotationDuration)
              .ease(d3.easeCubicOut)
              .attr('cx', targetX)
              .attr('cy', targetY)
              .attr('r', getSize(d) + 3)
              .attr('stroke', LOCAL_GLOW_COLORS[d.glowRole])

            glowEl
              .transition('local-glow-show')
              .delay(glowReappearDelay)
              .duration(200)
              .attr('opacity', 0.35)
          } else {
            // Node isn't actually moving - just update glow position, keep visible
            glowEl
              .attr('cx', targetX)
              .attr('cy', targetY)
              .attr('r', getSize(d) + 3)
              .attr('stroke', LOCAL_GLOW_COLORS[d.glowRole])
          }
        }
      })
    } else if (activeBudget.useFastPath) {
      localGlowsToAnimate
        .attr('cx', d => d.x)
        .attr('cy', d => d.y)
        .attr('r', d => getSize(d) + 3)
        .attr('opacity', 0.35)
    }

    // Add new local glows
    // During collapse: start at OLD position, animate with nodes, then fade in
    // During expand: wait until node finishes entering, then fade in at final position
    const newLocalGlows = localGlowSelection.enter()
      .append('circle')
      .attr('class', 'glow-local')
      .attr('cx', d => {
        // During collapse, start at old position so glow follows node
        if (isCollapsing) {
          const prevPos = nodePositionsRef.current.get(d.id)
          return prevPos?.x ?? d.x
        }
        // During expand, start at final position
        return d.x
      })
      .attr('cy', d => {
        if (isCollapsing) {
          const prevPos = nodePositionsRef.current.get(d.id)
          return prevPos?.y ?? d.y
        }
        return d.y
      })
      .attr('r', d => getSize(d) + 3)
      .attr('fill', 'none')
      .attr('stroke', d => LOCAL_GLOW_COLORS[d.glowRole])
      .attr('stroke-width', 3)
      .attr('opacity', 0)  // Start hidden
      .style('filter', 'blur(2px)')
      .style('pointer-events', 'none')

    // Animate glows based on whether their SPECIFIC node's DOM position differs from target
    if (isCollapsing) {
      // COLLAPSE: check each glow's node's actual DOM position
      newLocalGlows.each(function(d) {
        const glowEl = d3.select(this)
        const nodeEl = nodesLayer.select<SVGCircleElement>(`circle.node[data-id="${d.id}"]`)

        if (!nodeEl.empty()) {
          const nodeCx = parseFloat(nodeEl.attr('cx') || '0')
          const nodeCy = parseFloat(nodeEl.attr('cy') || '0')
          const targetX = d.x
          const targetY = d.y

          // Check if node actually needs to move
          const dx = Math.abs(targetX - nodeCx)
          const dy = Math.abs(targetY - nodeCy)
          const nodeActuallyMoves = dx > POSITION_CHANGE_THRESHOLD || dy > POSITION_CHANGE_THRESHOLD

          if (nodeActuallyMoves) {
            // Node is moving: animate from current position to target
            glowEl
              .attr('cx', nodeCx)
              .attr('cy', nodeCy)
              .transition('new-local-glow-position')
              .delay(glowRotationDelay)
              .duration(rotationDuration)
              .ease(d3.easeCubicOut)
              .attr('cx', targetX)
              .attr('cy', targetY)
              .transition()
              .duration(200)
              .attr('opacity', 0.35)
          } else {
            // Node is stationary: snap to position, fade in after exit
            glowEl
              .attr('cx', targetX)
              .attr('cy', targetY)
              .transition()
              .delay(collapseExitEndTime + 50)
              .duration(200)
              .attr('opacity', 0.35)
          }
        } else {
          // Node not found, just fade in at target position
          glowEl
            .attr('cx', d.x)
            .attr('cy', d.y)
            .transition()
            .delay(collapseExitEndTime + 50)
            .duration(200)
            .attr('opacity', 0.35)
        }
      })
    } else if (hasAnyAnimation) {
      // EXPAND: wait until nodes finish entering, then fade in
      newLocalGlows
        .transition('new-local-glow-expand')
        .delay(expandGlowDelay + 50)
        .duration(200)
        .attr('opacity', 0.35)
    } else {
      // No animation - just fade in
      newLocalGlows
        .transition()
        .duration(200)
        .attr('opacity', 0.35)
    }

    // === Hop distance from intervention (shared by flash nodes + edge pulse) ===
    // BFS on visible edges — ring compression makes ring values unreliable
    const hopFromIntervention = new Map<string, number>()
    for (const id of interventionNodeIds) hopFromIntervention.set(id, 0)
    let hopBfsChanged = true
    while (hopBfsChanged) {
      hopBfsChanged = false
      for (const e of visibleEdges) {
        for (const [a, b] of [[e.sourceId, e.targetId], [e.targetId, e.sourceId]] as const) {
          const aHop = hopFromIntervention.get(a)
          if (aHop !== undefined && !hopFromIntervention.has(b)) {
            hopFromIntervention.set(b, aHop + 1)
            hopBfsChanged = true
          }
        }
      }
    }
    const simMaxHop = Math.max(1, ...Array.from(hopFromIntervention.values()))

    // === SIMULATION: intervention node glow + affected node borders ===
    // Affected nodes use direct stroke on circle.node (via getSimBorder).
    // Intervention nodes get a dedicated glow ring on the sim glow layer.
    {
      const interventionGlowNodes = visibleNodes.filter(n => interventionNodeIds.has(n.id))

      const simGlowSelection = simGlowLayer
        .selectAll<SVGCircleElement, ExpandableNode>('circle.glow-sim')
        .data(interventionGlowNodes, d => d.id)

      // Remove old
      simGlowSelection.exit()
        .transition().duration(300).attr('opacity', 0).remove()

      // Update existing — match node transition timing so ring tracks node
      simGlowSelection.each(function(d) {
        const el = d3.select(this)
        const curCx = parseFloat(el.attr('cx') || '0')
        const curCy = parseFloat(el.attr('cy') || '0')
        const dx = Math.abs(d.x - curCx)
        const dy = Math.abs(d.y - curCy)
        if (dx > POSITION_CHANGE_THRESHOLD || dy > POSITION_CHANGE_THRESHOLD) {
          el.transition('glow-rotation')
            .delay(rotationDelay)
            .duration(rotationDuration)
            .ease(d3.easeCubicOut)
            .attr('cx', d.x)
            .attr('cy', d.y)
            .attr('r', getSize(d) + 3)
        } else {
          el.attr('cx', d.x).attr('cy', d.y).attr('r', getSize(d) + 3)
        }
      })

      // Enter new — cyan glow pulse (persists entire sim state)
      simGlowSelection.enter()
        .append('circle')
        .attr('class', 'glow-sim')
        .attr('cx', d => getParentPosition(d).x)
        .attr('cy', d => getParentPosition(d).y)
        .attr('r', 0)
        .attr('fill', 'none')
        .attr('stroke', '#00E5FF')
        .attr('stroke-width', 2.5)
        .attr('opacity', 0)
        .style('filter', 'blur(3px)')
        .style('pointer-events', 'none')
        .style('animation', `intervention-pulse ${SIM_MS_PER_YEAR}ms ease-in-out infinite`)
        .transition()
        .delay(expandEnterDelay)
        .duration(enterExitDuration)
        .ease(d3.easeCubicOut)
        .attr('cx', d => d.x)
        .attr('cy', d => d.y)
        .attr('r', d => getSize(d) + 3)
        .attr('opacity', 0.8)

      // Subtle glow for ineligible parent nodes (weak effect, didn't pass gating)
      // Dots mode: skip glows for deep-ring nodes
      const ineligibleGlowNodes = visibleNodes.filter(n => {
        if (dotsMode && n.ring >= DEEP_RING_THRESHOLD) return false
        const g = getSimGlowForIneligible(n)
        return g !== null
      })

      const ineligibleSelection = simGlowLayer
        .selectAll<SVGCircleElement, ExpandableNode>('circle.glow-sim-weak')
        .data(ineligibleGlowNodes, d => d.id)

      ineligibleSelection.exit()
        .transition().duration(300).attr('opacity', 0).remove()

      ineligibleSelection.each(function(d) {
        const el = d3.select(this)
        const curCx = parseFloat(el.attr('cx') || '0')
        const curCy = parseFloat(el.attr('cy') || '0')
        const dx = Math.abs(d.x - curCx)
        const dy = Math.abs(d.y - curCy)
        if (dx > POSITION_CHANGE_THRESHOLD || dy > POSITION_CHANGE_THRESHOLD) {
          el.transition('glow-rotation')
            .delay(rotationDelay)
            .duration(rotationDuration)
            .ease(d3.easeCubicOut)
            .attr('cx', d.x)
            .attr('cy', d.y)
            .attr('r', getSize(d) + 3)
        } else {
          el.attr('cx', d.x).attr('cy', d.y).attr('r', getSize(d) + 3)
        }
      })

      ineligibleSelection.enter()
        .append('circle')
        .attr('class', 'glow-sim-weak')
        // Spawn at the indicator itself (no parent-origin travel).
        .attr('cx', d => d.x)
        .attr('cy', d => d.y)
        .attr('r', 0)
        .attr('fill', 'none')
        .attr('stroke', d => {
          const g = getSimGlowForIneligible(d)
          return g ? g.color : '#999'
        })
        .attr('stroke-width', 1.5)
        .attr('opacity', 0)
        .style('filter', 'blur(3px)')
        .style('pointer-events', 'none')
        .transition()
        .delay(expandEnterDelay)
        .duration(enterExitDuration)
        .ease(d3.easeCubicOut)
        .attr('r', d => getSize(d) + 3)
        .attr('opacity', d => {
          const g = getSimGlowForIneligible(d)
          return g ? g.opacity : 0
        })

      // Affected node flash — glow red/green when the edge ripple arrives
      // Only during active playback; synced to hop delay so flash = pulse arrival

      const flashNodes = simPlaybackActive
        ? visibleNodes.filter(n => {
            // Dots mode: skip flash effects for deep-ring nodes
            if (dotsMode && n.ring >= DEEP_RING_THRESHOLD) return false
            if (interventionNodeIds.has(n.id)) return false
            const eff = simEffectLookup.get(n.id)
            if (!eff || Math.abs(eff.pct) < 0.01) return false
            // Only leaf nodes and parents with visible children
            if (n.hasChildren && !hasVisibleChild.has(n.id)) return false
            // Parent nodes only flash if they have meaningful effect (>=1%)
            if (n.hasChildren && Math.abs(eff.pct) < 1.0) return false
            return true
          })
        : []

      const flashSelection = simGlowLayer
        .selectAll<SVGCircleElement, ExpandableNode>('circle.glow-sim-flash')
        .data(flashNodes, d => d.id)

      flashSelection.exit()
        .transition().duration(200).attr('opacity', 0).remove()

      // Update positions — match node transition timing
      flashSelection.each(function(d) {
        const el = d3.select(this)
        const curCx = parseFloat(el.attr('cx') || '0')
        const curCy = parseFloat(el.attr('cy') || '0')
        const dx = Math.abs(d.x - curCx)
        const dy = Math.abs(d.y - curCy)
        if (dx > POSITION_CHANGE_THRESHOLD || dy > POSITION_CHANGE_THRESHOLD) {
          el.transition('glow-rotation')
            .delay(rotationDelay)
            .duration(rotationDuration)
            .ease(d3.easeCubicOut)
            .attr('cx', d.x)
            .attr('cy', d.y)
            .attr('r', getSize(d) + 1.5)
        } else {
          el.attr('cx', d.x).attr('cy', d.y).attr('r', getSize(d) + 1.5)
        }
      })

      // Enter — flash animation timed to edge ripple arrival at this ring
      flashSelection.enter()
        .append('circle')
        .attr('class', 'glow-sim-flash')
        // Spawn at the affected node itself (no root/parent travel).
        .attr('cx', d => d.x)
        .attr('cy', d => d.y)
        .attr('r', 0)
        .attr('fill', 'none')
        .attr('stroke', d => {
          const eff = simEffectLookup.get(d.id)
          return eff && eff.pct >= 0 ? '#39FF14' : '#FF1744'
        })
        .attr('stroke-width', 1.5)
        .attr('opacity', 0)
        .style('pointer-events', 'none')
        .style('animation', d => {
          const eff = simEffectLookup.get(d.id)
          const anim = eff && eff.pct >= 0 ? 'sim-node-flash-pos' : 'sim-node-flash-neg'
          const hop = hopFromIntervention.get(d.id) ?? simMaxHop
          const delay = hop * 120
          return `${anim} ${SIM_MS_PER_YEAR}ms ease-out ${delay}ms infinite`
        })
        .transition()
        .delay(expandEnterDelay)
        .duration(enterExitDuration)
        .ease(d3.easeCubicOut)
        .attr('r', d => getSize(d) + 1.5)
        .attr('opacity', 1)

      // Ring 0 (QoL) cyan pulse — synced to edge ripple arrival at the root
      // Gives visual continuity: pulse passes through QoL node, doesn't die there
      const qolNode = simPlaybackActive ? visibleNodes.filter(n => n.ring === 0) : []
      const qolPulseSelection = simGlowLayer
        .selectAll<SVGCircleElement, ExpandableNode>('circle.glow-sim-qol')
        .data(qolNode, d => d.id)

      qolPulseSelection.exit()
        .transition().duration(300).attr('opacity', 0).remove()

      qolPulseSelection.each(function(d) {
        d3.select(this).attr('cx', d.x).attr('cy', d.y).attr('r', getSize(d) + 4)
      })

      qolPulseSelection.enter()
        .append('circle')
        .attr('class', 'glow-sim-qol')
        .attr('cx', d => d.x)
        .attr('cy', d => d.y)
        .attr('r', d => getSize(d) + 4)
        .attr('fill', 'none')
        .attr('stroke', '#00E5FF')
        .attr('stroke-width', 2)
        .attr('opacity', 0)
        .style('filter', 'blur(2px)')
        .style('pointer-events', 'none')
        .style('animation', () => {
          // Time the flash to arrive when the edge ripple reaches ring 0 (last hop)
          const hop = hopFromIntervention.get(qolNode[0]?.id ?? '') ?? simMaxHop
          const delay = hop * 120
          return `qol-cyan-flash ${SIM_MS_PER_YEAR}ms ease-out ${delay}ms infinite`
        })
        .attr('opacity', 0.8)
    }

    // === EDGES with enter/update/exit ===
    const edgeKey = (d: StructuralEdge) => `${d.sourceId}-${d.targetId}`
    const edgeSelection = edgesLayer.selectAll<SVGLineElement, StructuralEdge>('line.edge')
      .data(visibleEdges, edgeKey)

    // Exit edges (COLLAPSE: after text disappears, before rotation)
    // Dots mode: deep-ring edges exit instantly
    edgeSelection.exit()
      .each(function() {
        const el = d3.select(this)
        const targetRing = parseInt(el.attr('data-target-ring') || '0', 10)
        if (dotsMode && targetRing >= DEEP_RING_THRESHOLD) {
          el.remove()
        } else if (activeBudget.useFastPath) {
          el.transition('edge-exit')
            .duration(exitDuration)
            .style('opacity', 0)
            .remove()
        } else {
          el.transition('edge-exit')
            .delay(collapseExitDelay)
            .duration(exitDuration)
            .attr('x2', el.attr('x1'))
            .attr('y2', el.attr('y1'))
            .style('opacity', 0)
            .remove()
        }
      })

    // Check if we're in the middle of a collapse animation (from a previous render)
    // IMPORTANT: Check BEFORE setting new animation state
    const now = Date.now()
    const useCollapseAnimationGuard = !activeBudget.useFastPath
    const inCollapseAnimation = useCollapseAnimationGuard
      && collapseAnimationRef.current.inProgress
      && now < collapseAnimationRef.current.endTime

    // Track collapse animation state to prevent re-renders from overriding
    if (useCollapseAnimationGuard && isCollapsing && exitingNodeIds.size > 0) {
      // Start of collapse animation - mark it and set end time
      const totalCollapseTime = collapseRotationDelay + rotationDuration
      collapseAnimationRef.current = { inProgress: true, endTime: now + totalCollapseTime }
      if (collapseGuardTimerRef.current !== null) {
        clearTimeout(collapseGuardTimerRef.current)
        collapseGuardTimerRef.current = null
      }
      // Schedule cleanup after animation completes
      collapseGuardTimerRef.current = window.setTimeout(() => {
        collapseGuardTimerRef.current = null
        collapseAnimationRef.current = { inProgress: false, endTime: 0 }
      }, totalCollapseTime + 50)
    } else if (!useCollapseAnimationGuard) {
      if (collapseGuardTimerRef.current !== null) {
        clearTimeout(collapseGuardTimerRef.current)
        collapseGuardTimerRef.current = null
      }
      collapseAnimationRef.current = { inProgress: false, endTime: 0 }
    }

    // Update edges (animate to new positions)
    // Check each edge's actual DOM position vs target - animate if different
    const shouldSkipRotation = inCollapseAnimation && !isCollapsing

    edgeSelection.each(function(d) {
      const edgeEl = d3.select(this)
      const targetX1 = nodeMap.get(d.sourceId)?.x || 0
      const targetY1 = nodeMap.get(d.sourceId)?.y || 0
      const targetX2 = nodeMap.get(d.targetId)?.x || 0
      const targetY2 = nodeMap.get(d.targetId)?.y || 0

      // Dots mode: deep-ring edges set position directly, no transition
      if (dotsMode && d.targetRing >= DEEP_RING_THRESHOLD) {
        edgeEl
          .attr('x1', targetX1).attr('y1', targetY1)
          .attr('x2', targetX2).attr('y2', targetY2)
        return
      }
      if (activeBudget.useFastPath) {
        edgeEl
          .attr('x1', targetX1)
          .attr('y1', targetY1)
          .attr('x2', targetX2)
          .attr('y2', targetY2)
        return
      }

      const currentX1 = parseFloat(edgeEl.attr('x1') || '0')
      const currentY1 = parseFloat(edgeEl.attr('y1') || '0')
      const currentX2 = parseFloat(edgeEl.attr('x2') || '0')
      const currentY2 = parseFloat(edgeEl.attr('y2') || '0')

      // Check if edge actually needs to move
      const dx1 = Math.abs(targetX1 - currentX1)
      const dy1 = Math.abs(targetY1 - currentY1)
      const dx2 = Math.abs(targetX2 - currentX2)
      const dy2 = Math.abs(targetY2 - currentY2)
      const needsMove = dx1 > POSITION_CHANGE_THRESHOLD || dy1 > POSITION_CHANGE_THRESHOLD ||
                        dx2 > POSITION_CHANGE_THRESHOLD || dy2 > POSITION_CHANGE_THRESHOLD

      if (needsMove || !shouldSkipRotation) {
        edgeEl
          .transition('rotation')
          .delay(rotationDelay)
          .duration(rotationDuration)
          .ease(d3.easeCubicOut)
          .attr('x1', targetX1)
          .attr('y1', targetY1)
          .attr('x2', targetX2)
          .attr('y2', targetY2)
      }
    })

    // Enter edges (EXPAND: after rotation completes)
    // Dots mode: deep-ring edges appear instantly; shallow edges animate
    const enterEdges = edgeSelection.enter()
      .append('line')
      .attr('class', 'edge')
      .attr('data-target-ring', d => d.targetRing)
      .attr('x1', d => nodeMap.get(d.sourceId)?.x || 0)
      .attr('y1', d => nodeMap.get(d.sourceId)?.y || 0)
      .attr('stroke', '#bcc3d4')
      .attr('stroke-width', d => vLayout.getEdgeThickness(d.sourceRing))
      .style('pointer-events', 'none')

    // Deep-ring edges in dots mode: instant placement
    enterEdges.filter(d => dotsMode && d.targetRing >= DEEP_RING_THRESHOLD)
      .attr('x2', d => nodeMap.get(d.targetId)?.x || 0)
      .attr('y2', d => nodeMap.get(d.targetId)?.y || 0)
      .attr('stroke-opacity', d => vLayout.getEdgeOpacity(d.sourceRing))

    // Shallow edges (or non-dots-mode): animated enter
    const shallowEnterEdges = enterEdges.filter(d => !(dotsMode && d.targetRing >= DEEP_RING_THRESHOLD))
    if (activeBudget.useFastPath) {
      shallowEnterEdges
        .attr('x2', d => nodeMap.get(d.targetId)?.x || 0)
        .attr('y2', d => nodeMap.get(d.targetId)?.y || 0)
        .attr('stroke-opacity', 0)
        .transition()
        .duration(Math.min(enterExitDuration, 100))
        .attr('stroke-opacity', d => vLayout.getEdgeOpacity(d.sourceRing))
    } else {
      shallowEnterEdges
        .attr('x2', d => nodeMap.get(d.sourceId)?.x || 0)
        .attr('y2', d => nodeMap.get(d.sourceId)?.y || 0)
        .attr('stroke-opacity', 0)
        .transition()
        .delay(expandEnterDelay)
        .duration(enterExitDuration)
        .ease(d3.easeCubicOut)
        .attr('x2', d => nodeMap.get(d.targetId)?.x || 0)
        .attr('y2', d => nodeMap.get(d.targetId)?.y || 0)
        .attr('stroke-opacity', d => vLayout.getEdgeOpacity(d.sourceRing))
    }

    // === SIMULATION EDGE PULSE — cyan ripple along hierarchical edges during playback ===
    {
      // Only show during sim playback when panel is open
      const showSimPulse = simPlaybackActive && pinnedPaths.size > 0

      // Filter edges: both endpoints must be pinned (on a sim path).
      // Skip edges TO ring-1 nodes that have no visible children (dead-end domains).
      const pulseEdges = showSimPulse
        ? visibleEdges.filter(e => {
            if (!pinnedPaths.has(e.sourceId) || !pinnedPaths.has(e.targetId)) return false
            // Skip ring-1 target nodes without visible children
            if (e.targetRing === 1 && !hasVisibleChild.has(e.targetId)) return false
            // Dots mode: skip pulse animation for deep-ring edges
            if (dotsMode && e.targetRing >= DEEP_RING_THRESHOLD) return false
            return true
          })
        : []

      const pulseKey = (d: StructuralEdge) => `pulse-${d.sourceId}-${d.targetId}`
      const pulseSelection = edgesLayer
        .selectAll<SVGLineElement, StructuralEdge>('line.edge-sim-pulse')
        .data(pulseEdges, pulseKey)

      // Exit
      pulseSelection.exit()
        .transition().duration(300).attr('stroke-opacity', 0).remove()

      // Update positions
      pulseSelection
        .attr('x1', d => nodeMap.get(d.sourceId)?.x || 0)
        .attr('y1', d => nodeMap.get(d.sourceId)?.y || 0)
        .attr('x2', d => nodeMap.get(d.targetId)?.x || 0)
        .attr('y2', d => nodeMap.get(d.targetId)?.y || 0)

      // Edge hop = min hop of its two endpoints (using shared hopFromIntervention map)
      const edgeHop = (e: StructuralEdge) => {
        const s = hopFromIntervention.get(e.sourceId) ?? simMaxHop
        const t = hopFromIntervention.get(e.targetId) ?? simMaxHop
        return Math.min(s, t)
      }

      pulseSelection.enter()
        .append('line')
        .attr('class', 'edge-sim-pulse')
        .attr('x1', d => nodeMap.get(d.sourceId)?.x || 0)
        .attr('y1', d => nodeMap.get(d.sourceId)?.y || 0)
        .attr('x2', d => nodeMap.get(d.targetId)?.x || 0)
        .attr('y2', d => nodeMap.get(d.targetId)?.y || 0)
        .attr('stroke', '#00E5FF')
        .attr('stroke-width', 0.3)
        .attr('stroke-opacity', 0.05)
        .style('pointer-events', 'none')
        .style('animation', d => {
          const hop = edgeHop(d)
          const delay = hop * 120
          // 3-tier based on actual hop distance from intervention
          const animName = hop === 0 ? 'sim-edge-ripple-near'
            : hop <= Math.ceil(simMaxHop / 2) ? 'sim-edge-ripple-mid'
            : 'sim-edge-ripple-far'
          return `${animName} ${SIM_MS_PER_YEAR}ms ease-out ${delay}ms infinite`
        })
    }

    // === NODES with enter/update/exit ===
    // Fix: remove stale circles that are mid-exit-transition but whose IDs match
    // incoming visible nodes. Without this, D3 reuses the exiting circle (with its
    // active exit transition driving opacity→0 + .remove()) instead of creating a
    // fresh enter node. This happens when resetView's Phase 2 fires while Phase 1's
    // exit transitions are still pending due to silent D3 re-renders resetting them.
    if (newNodeIds.size > 0) {
      nodesLayer.selectAll<SVGCircleElement, ExpandableNode>('circle.node')
        .each(function() {
          const el = d3.select(this)
          const id = el.attr('data-id')
          if (id && newNodeIds.has(id)) {
            el.interrupt().remove()
          }
        })
    }

    const nodeSelection = nodesLayer.selectAll<SVGCircleElement, ExpandableNode>('circle.node')
      .data(visibleNodes, d => d.id)

    // Exit nodes (COLLAPSE: after text disappears, before rotation)
    // Dots mode: deep-ring nodes exit instantly
    nodeSelection.exit()
      .each(function() {
        const el = d3.select(this)
        const ring = parseInt(el.attr('data-ring') || '0', 10)
        if (dotsMode && ring >= DEEP_RING_THRESHOLD) {
          el.remove()
          return
        }
        if (activeBudget.useFastPath) {
          el.transition('node-exit')
            .duration(exitDuration)
            .style('opacity', 0)
            .remove()
          return
        }
        const id = el.attr('data-id')
        if (id) {
          const nodeData = nodePositionsRef.current.get(id)
          const parentPos = nodeData?.parentId ? nodePositionsRef.current.get(nodeData.parentId) : null
          el.transition('node-exit')
            .delay(collapseExitDelay)
            .duration(exitDuration)
            .ease(d3.easeCubicIn)
            .attr('cx', parentPos?.x ?? el.attr('cx'))
            .attr('cy', parentPos?.y ?? el.attr('cy'))
            .attr('r', 0)
            .style('opacity', 0)
            .remove()
        }
      })

    // Update nodes (animate to new positions)
    // Check each node's actual DOM position vs target - animate if different
    nodeSelection.each(function(d) {
      const nodeEl = d3.select(this)
      const targetX = d.x
      const targetY = d.y
      const nodeRadius = getSize(d)
      const focusStrokeWidth = Math.max(1.5, nodeRadius * 0.06)
      nodeEl.style('--kbd-focus-stroke-width', `${focusStrokeWidth}px`)

      // Compute simulation border for this node
      // During active playback: affected LEAF nodes get no stroke (solid fill only)
      const effLookup = simEffectLookup.get(d.id)
      const isAffectedDuringPlayback = simPlaybackActive && effLookup?.isLeaf && Math.abs(effLookup.pct) >= 0.01
      const simBorder = getSimBorder(d)
      let strokeColor = isAffectedDuringPlayback
        ? getColor(d)  // match fill = invisible border
        : simBorder
          ? simBorder.color
          : isNodeFloored(d.importance) ? '#999' : (DOMAIN_COLORS[d.semanticPath.domain] || '#9E9E9E')
      let strokeWidth = isAffectedDuringPlayback
        ? 0.5
        : simBorder
          ? simBorder.width
          : isNodeFloored(d.importance) ? Math.min(1, getSize(d) * 0.5) : getBorderWidth(d)
      const strokeOpacity = isAffectedDuringPlayback ? 0 : (simBorder ? simBorder.opacity : 1.0)
      const dashArray = (!simBorder && !isAffectedDuringPlayback && isNodeFloored(d.importance)) ? '2,2' : 'none'

      // Ring 0 QoL outline: RdYlGn tint — hidden during simulation (cyan pulse + glow handle it)
      if (d.ring === 0 && hideQolStroke) {
        strokeColor = 'transparent'
        strokeWidth = 0
      } else if (d.ring === 0 && qolNodeScore != null && playbackMode !== 'simulation') {
        strokeColor = d3.scaleSequential(d3.interpolateRdYlGn).domain([0.3, 0.95])(qolNodeScore)
        strokeWidth = Math.max(1.5, getSize(d) * 0.06)
      } else if (d.ring === 0 && playbackMode === 'simulation') {
        strokeColor = '#78909C'  // match fill — invisible border during sim
        strokeWidth = 0.5
      }

      // Dots mode: deep-ring nodes set attrs directly, no transition
      if (dotsMode && d.ring >= DEEP_RING_THRESHOLD) {
        nodeEl
          .attr('cx', targetX).attr('cy', targetY)
          .attr('r', nodeRadius)
          .attr('fill', getColor(d))
          .attr('stroke', strokeColor)
          .attr('stroke-width', strokeWidth)
          .attr('stroke-opacity', d.ring === 0 && hideQolStroke ? 0 : strokeOpacity)
          .attr('stroke-dasharray', dashArray)
        return
      }
      if (activeBudget.useFastPath) {
        nodeEl
          .attr('cx', targetX)
          .attr('cy', targetY)
          .attr('r', nodeRadius)
          .attr('fill', getColor(d))
          .attr('stroke', strokeColor)
          .attr('stroke-width', strokeWidth)
          .attr('stroke-opacity', d.ring === 0 && hideQolStroke ? 0 : strokeOpacity)
          .attr('stroke-dasharray', dashArray)
      } else {
        if (d.ring === 0 && hideQolStroke) {
          // Apply immediately so delayed transitions never flash the historical QoL border.
          nodeEl
            .attr('stroke', 'transparent')
            .attr('stroke-width', 0)
            .attr('stroke-opacity', 0)
        }

        const currentCx = parseFloat(nodeEl.attr('cx') || '0')
        const currentCy = parseFloat(nodeEl.attr('cy') || '0')

        // Check if node actually needs to move
        const dx = Math.abs(targetX - currentCx)
        const dy = Math.abs(targetY - currentCy)
        const needsMove = dx > POSITION_CHANGE_THRESHOLD || dy > POSITION_CHANGE_THRESHOLD

        if (needsMove) {
          // Node position differs from target - animate to new position
          nodeEl
            .transition('rotation')
            .delay(rotationDelay)
            .duration(rotationDuration)
            .ease(d3.easeCubicOut)
            .attr('cx', targetX)
            .attr('cy', targetY)
            .attr('r', nodeRadius)
            .attr('fill', getColor(d))
            .attr('stroke', strokeColor)
            .attr('stroke-width', strokeWidth)
            .attr('stroke-opacity', d.ring === 0 && hideQolStroke ? 0 : strokeOpacity)
            .attr('stroke-dasharray', dashArray)
        } else if (!shouldSkipRotation) {
          // Position matches but may need size/color update
          nodeEl
            .transition('rotation')
            .delay(rotationDelay)
            .duration(rotationDuration)
            .ease(d3.easeCubicOut)
            .attr('r', nodeRadius)
            .attr('fill', getColor(d))
            .attr('stroke', strokeColor)
            .attr('stroke-width', strokeWidth)
            .attr('stroke-opacity', d.ring === 0 && hideQolStroke ? 0 : strokeOpacity)
            .attr('stroke-dasharray', dashArray)
        }
      }
      nodeEl.style('opacity', 1)

      // Ring 0 simulation glow: green/red drop-shadow proportional to QoL delta
      if (d.ring === 0 && temporalResults?.qol_timeline) {
        const simYear = String(temporalResults.base_year + currentYearIndex)
        const qolDelta = temporalResults.qol_timeline[simYear]
        if (qolDelta) {
          const glowColor = qolDelta.delta >= 0 ? '#39FF14' : '#FF1744'
          const intensity = Math.min(12, Math.abs(qolDelta.delta) * 200)
          nodeEl.style('filter', `drop-shadow(0 0 ${intensity}px ${glowColor})`)
        } else {
          nodeEl.style('filter', null)
        }
      } else if (d.ring === 0) {
        nodeEl.style('filter', null)
      }
      // Note: opacity is always 1 since uncovered nodes are filtered out by effectiveNodes
    })

    // Enter nodes (EXPAND: after rotation completes)
    // Dots mode: deep-ring nodes appear instantly; shallow nodes animate from parent
    const enterNodes = nodeSelection.enter()
      .append('circle')
      .attr('class', 'node')
      .attr('data-id', d => d.id)
      .attr('data-ring', d => d.ring)
      .attr('fill', d => getColor(d))
      .attr('stroke', d => {
        // Ring 0 QoL outline: hidden during sim, RdYlGn tint otherwise
        if (d.ring === 0 && hideQolStroke) return 'transparent'
        if (d.ring === 0 && playbackMode === 'simulation') return '#78909C'
        if (d.ring === 0 && qolNodeScore != null) {
          return d3.scaleSequential(d3.interpolateRdYlGn).domain([0.3, 0.95])(qolNodeScore)
        }
        const eLookup = simEffectLookup.get(d.id)
        const affectedDuringPlayback = simPlaybackActive && eLookup?.isLeaf && Math.abs(eLookup.pct) >= 0.01
        if (affectedDuringPlayback) return getColor(d)
        const sb = getSimBorder(d)
        return sb ? sb.color : isNodeFloored(d.importance) ? '#999' : (DOMAIN_COLORS[d.semanticPath.domain] || '#9E9E9E')
      })
      .attr('stroke-width', d => {
        // Ring 0 QoL outline: hidden during sim
        if (d.ring === 0 && hideQolStroke) return 0
        if (d.ring === 0 && playbackMode === 'simulation') return 0.5
        if (d.ring === 0 && qolNodeScore != null) {
          return Math.max(1.5, getSize(d) * 0.06)
        }
        const eLookup = simEffectLookup.get(d.id)
        const affectedDuringPlayback = simPlaybackActive && eLookup?.isLeaf && Math.abs(eLookup.pct) >= 0.01
        if (affectedDuringPlayback) return 0.5
        const sb = getSimBorder(d)
        if (sb) return sb.width
        const radius = getSize(d)
        if (isNodeFloored(d.importance)) return Math.min(1, radius * 0.5)
        return getBorderWidth(d)
      })
      .attr('stroke-opacity', d => {
        if (d.ring === 0 && hideQolStroke) return 0
        const eLookup = simEffectLookup.get(d.id)
        const affectedDuringPlayback = simPlaybackActive && eLookup?.isLeaf && Math.abs(eLookup.pct) >= 0.01
        if (affectedDuringPlayback) return 0
        const sb = getSimBorder(d)
        return sb ? sb.opacity : 1.0
      })
      .attr('stroke-dasharray', d => {
        const eLookup = simEffectLookup.get(d.id)
        const affectedDuringPlayback = simPlaybackActive && eLookup?.isLeaf && Math.abs(eLookup.pct) >= 0.01
        if (affectedDuringPlayback) return 'none'
        const sb = getSimBorder(d)
        return (!sb && isNodeFloored(d.importance)) ? '2,2' : 'none'
      })
      .style('cursor', d => d.hasChildren ? 'pointer' : 'default')
      .style('--kbd-focus-stroke-width', d => `${Math.max(1.5, getSize(d) * 0.06)}px`)

    // Deep-ring nodes in dots mode: instant placement, full opacity
    enterNodes.filter(d => dotsMode && d.ring >= DEEP_RING_THRESHOLD)
      .attr('cx', d => d.x)
      .attr('cy', d => d.y)
      .attr('r', d => getSize(d))
      .style('opacity', 1)

    // Shallow nodes (or non-dots-mode): animated enter from parent position
    const shallowEnterNodes = enterNodes.filter(d => !(dotsMode && d.ring >= DEEP_RING_THRESHOLD))
    if (activeBudget.useFastPath) {
      shallowEnterNodes
        .attr('cx', d => d.x)
        .attr('cy', d => d.y)
        .attr('r', d => getSize(d))
        .style('opacity', 0)
        .transition()
        .duration(Math.min(enterExitDuration, 120))
        .style('opacity', 1)
    } else {
      shallowEnterNodes
        .attr('cx', d => getParentPosition(d).x)
        .attr('cy', d => getParentPosition(d).y)
        .attr('r', 0)
        .style('opacity', 0)
        .transition()
        .delay(expandEnterDelay)
        .duration(enterExitDuration)
        .ease(d3.easeCubicOut)
        .attr('cx', d => d.x)
        .attr('cy', d => d.y)
        .attr('r', d => getSize(d))
        .style('opacity', 1)
    }

    // === TIMELINE-BASED SIZE UPDATES ===
    // When timeline year changes, update all node radii with smooth transition
    // Speed: 300ms for unified (35 years), 700ms for country-specific (~26 years)
    if (playbackMode === 'historical' && historicalTimeline) {
      const MS_PER_YEAR = selectedCountry ? 700 : 300

      g.selectAll<SVGCircleElement, ExpandableNode>('circle.node')
        .transition('timeline-size')
        .duration(MS_PER_YEAR)
        .ease(d3.easeLinear)  // Linear for smooth continuous feel
        .attr('r', d => getSize(d))
        .attr('stroke-width', d => {
          const radius = getSize(d)
          if (isNodeFloored(d.importance)) return Math.min(1, radius * 0.5)
          return getBorderWidth(d)
        })
    }

    // Update refs for next render
    prevVisibleNodeIdsRef.current = currentVisibleIds
    prevVisibleEdgeIdsRef.current = currentEdgeIds
    visibleNodes.forEach(n => {
      nodePositionsRef.current.set(n.id, { x: n.x, y: n.y, parentId: n.parentId })
    })

    // === EVENT DELEGATION ===
    const nodeDataMap = new Map<string, ExpandableNode>()
    visibleNodes.forEach(n => nodeDataMap.set(n.id, n))

    const graphNodeSelection = nodesLayer.selectAll<SVGCircleElement, ExpandableNode>('circle.node')

    const navNodes: GraphNavNode[] = visibleNodes.map(node => ({
      id: node.id,
      label: node.label,
      ring: node.ring,
      angle: node.angle,
      parentId: node.parentId,
      domain: node.semanticPath.domain || '',
      hasChildren: node.hasChildren,
    }))

    const navModel = buildGraphNavModel(navNodes)
    const prevNavModel = graphNavModelRef.current
    const prevFocusedNodeId = focusedGraphNodeIdRef.current
    const prevFocusedParentId = prevFocusedNodeId
      ? prevNavModel?.nodesById.get(prevFocusedNodeId)?.parentId ?? null
      : null

    if (graphNavEnabled) {
      const fallback = getFallbackFocus(navModel, {
        preferredNodeId: prevFocusedNodeId,
        preferredParentId: prevFocusedParentId,
      })
      focusedGraphNodeIdRef.current = fallback?.id ?? null
      graphNavModelRef.current = navModel
    } else {
      focusedGraphNodeIdRef.current = null
      graphNavActiveRef.current = false
      graphNavModelRef.current = null
    }

    const applyGraphRovingTabIndex = (focusedNodeId: string | null) => {
      graphNodeSelection.attr('tabindex', d => {
        if (!graphNavEnabled) return -1
        return focusedNodeId !== null && d.id === focusedNodeId ? 0 : -1
      })
    }

    applyGraphRovingTabIndex(focusedGraphNodeIdRef.current)

    graphNodeSelection
      .attr('focusable', graphNavEnabled ? 'true' : 'false')
      .attr('role', 'button')
      .attr('aria-label', d => {
        const ringLabel = RING_LABELS[d.ring] ?? `Ring ${d.ring}`
        const domain = d.semanticPath.domain || 'Domain unavailable'
        return `${d.label}, ${ringLabel}, ${domain}`
      })
      .attr('aria-expanded', d => d.hasChildren ? String(expandedNodes.has(d.id)) : null)
      .attr('aria-disabled', d => d.hasChildren ? null : 'true')

    const focusGraphNodeById = (nodeId: string) => {
      if (!graphNavEnabled) return false
      if (!graphNavModelRef.current?.nodesById.has(nodeId)) return false

      focusedGraphNodeIdRef.current = nodeId
      applyGraphRovingTabIndex(nodeId)

      let focusTarget: SVGCircleElement | null = null
      graphNodeSelection.each(function(nodeDatum) {
        if (nodeDatum.id === nodeId) {
          focusTarget = this as SVGCircleElement
        }
      })

      const targetEl = focusTarget
      if (!targetEl) return false
      const focusableTarget = targetEl as unknown as { focus: (options?: FocusOptions) => void }

      if (document.activeElement !== targetEl) {
        try {
          focusableTarget.focus({ preventScroll: true })
        } catch {
          focusableTarget.focus()
        }
      }

      return true
    }
    focusGraphNodeByIdRef.current = focusGraphNodeById

    if (graphNavEnabled && pendingExpandedBranchFocusRef.current) {
      const branchParentId = pendingExpandedBranchFocusRef.current
      const children = visibleNodes
        .filter(node => node.parentId === branchParentId)
        .sort((a, b) => a.angle - b.angle)

      if (children.length > 0) {
        const middleChild = children[Math.floor(children.length / 2)]
        if (focusGraphNodeById(middleChild.id)) {
          pendingExpandedBranchFocusRef.current = null
        }
      } else if (!graphNavModelRef.current?.nodesById.has(branchParentId)) {
        pendingExpandedBranchFocusRef.current = null
      }
    }

    // Remove old handlers and add new ones
    g.on('.graphNav', null)
      .on('click', null)
      .on('dblclick', null)
      .on('mouseenter', null)
      .on('mouseleave', null)

    // Delayed single-click to allow time for double-click detection
    // This prevents accidental expand/collapse when user intended to double-click
    const CLICK_DELAY = 100 // ms - window for double-click
    const TOOLTIP_SHOW_DELAY = 260

    g.on('click', (event) => {
      const target = event.target as Element
      if (target.classList.contains('node')) {
        event.stopPropagation()
        const nodeId = target.getAttribute('data-id')
        if (nodeId) {
          const node = nodeDataMap.get(nodeId)

          // Clear any pending click timeout
          if (clickTimeoutRef.current) {
            window.clearTimeout(clickTimeoutRef.current)
            clickTimeoutRef.current = null
          }

          // Delay single-click action to allow double-click
          clickTimeoutRef.current = window.setTimeout(() => {
            clickTimeoutRef.current = null
            if (node?.hasChildren) {
              // Root node (ring 0): reset view if expanded, normal expand if collapsed
              if (node.ring === 0 && expandedNodes.has(node.id)) {
                resetView()
              } else {
                toggleExpansion(node.id)
              }
            }
            // Clear highlight when clicking any node
            if (highlightedPath.size > 0) {
              setHighlightedPath(new Set())
              setHighlightedTarget(null)
            }
          }, CLICK_DELAY)
        }
      } else {
        // Clicked on background - clear highlight immediately
        if (highlightedPath.size > 0) {
          setHighlightedPath(new Set())
          setHighlightedTarget(null)
        }
      }
    })
    .on('dblclick', (event) => {
      const target = event.target as Element

      // Cancel pending single-click
      if (clickTimeoutRef.current) {
        window.clearTimeout(clickTimeoutRef.current)
        clickTimeoutRef.current = null
      }

      if (target.classList.contains('node')) {
        // Double-click on node - add to Local View
        event.stopPropagation()
        event.preventDefault()
        const nodeId = target.getAttribute('data-id')
        if (nodeId) {
          addToLocalView(nodeId)
        }
      } else {
        // Double-click on empty space - fit all visible nodes
        event.preventDefault()
        fitToVisibleNodes()
      }
    })
    .on('mouseenter', (event) => {
      const target = event.target as Element
      if (target.classList.contains('node')) {
        const nodeId = target.getAttribute('data-id')
        if (nodeId) {
          const node = nodeDataMap.get(nodeId)
          if (node) {
            const radius = getSize(node)
            const sb = getSimBorder(node)
            const baseStroke = (node.ring === 0 && hideQolStroke)
              ? 0
              : (sb ? sb.width : isNodeFloored(node.importance) ? Math.min(1, radius * 0.5) : getBorderWidth(node))
            const hoverStroke = (node.ring === 0 && hideQolStroke)
              ? 0
              : Math.min(baseStroke + 1, radius * 0.8)
            d3.select(target)
              .attr('r', radius * 1.3)
              .attr('stroke-width', hoverStroke)
            if (tooltipShowTimerRef.current !== null) {
              clearTimeout(tooltipShowTimerRef.current)
              tooltipShowTimerRef.current = null
            }
            tooltipShowTimerRef.current = window.setTimeout(() => {
              setHoveredNode(node)
              tooltipNodeRef.current = node  // Cache for smooth tooltip fade
              tooltipShowTimerRef.current = null
            }, TOOLTIP_SHOW_DELAY)
          }
        }
      }
    }, true)
    .on('mouseleave', (event) => {
      const target = event.target as Element
      if (target.classList.contains('node')) {
        const nodeId = target.getAttribute('data-id')
        if (nodeId) {
          const node = nodeDataMap.get(nodeId)
          if (node) {
            const radius = getSize(node)
            const sb = getSimBorder(node)
            const baseStroke = (node.ring === 0 && hideQolStroke)
              ? 0
              : (sb ? sb.width : isNodeFloored(node.importance) ? Math.min(1, radius * 0.5) : getBorderWidth(node))
            d3.select(target)
              .attr('r', radius)
              .attr('stroke-width', baseStroke)
            if (tooltipShowTimerRef.current !== null) {
              clearTimeout(tooltipShowTimerRef.current)
              tooltipShowTimerRef.current = null
            }
            setHoveredNode(null)
          }
        }
      }
    }, true)
    .on('focusin.graphNav', (event) => {
      if (!graphNavEnabled) return
      const target = event.target as Element
      if (!target.classList.contains('node')) return

      const nodeId = target.getAttribute('data-id')
      if (!nodeId) return

      const navModelRef = graphNavModelRef.current
      const navNode = navModelRef?.nodesById.get(nodeId)
      if (!navNode) return

      graphNavActiveRef.current = true
      focusedGraphNodeIdRef.current = nodeId
      applyGraphRovingTabIndex(nodeId)
      announceGraphNav(formatAnnouncement(navNode, { ringLabels: RING_LABELS }))
    })
    .on('focusout.graphNav', (event) => {
      const relatedTarget = event.relatedTarget as Element | null
      if (relatedTarget?.classList?.contains('node')) return
      graphNavActiveRef.current = false
    })
    .on('keydown.graphNav', (event) => {
      if (!graphNavEnabled) return

      const target = event.target as Element
      if (!target.classList.contains('node')) return

      const key = event.key
      const currentNodeId = target.getAttribute('data-id') ?? focusedGraphNodeIdRef.current
      const navModelRef = graphNavModelRef.current
      if (!currentNodeId || !navModelRef) return

      const currentNode = nodeDataMap.get(currentNodeId)
      let handled = false

      if (key === 'ArrowLeft') {
        const previousNode = getPrevSibling(navModelRef, currentNodeId)
        if (previousNode && previousNode.id !== currentNodeId) {
          focusGraphNodeById(previousNode.id)
        } else if (currentNode?.ring === 0) {
          const rootChildren = visibleNodes
            .filter(node => node.parentId === currentNodeId)
            .sort((a, b) => a.angle - b.angle)
          if (rootChildren.length > 0) {
            focusGraphNodeById(rootChildren[rootChildren.length - 1].id)
          } else {
            announceGraphNav('Expand Quality of Life to navigate outcomes')
          }
        }
        handled = true
      } else if (key === 'ArrowRight') {
        const nextNode = getNextSibling(navModelRef, currentNodeId)
        if (nextNode && nextNode.id !== currentNodeId) {
          focusGraphNodeById(nextNode.id)
        } else if (currentNode?.ring === 0) {
          const rootChildren = visibleNodes
            .filter(node => node.parentId === currentNodeId)
            .sort((a, b) => a.angle - b.angle)
          if (rootChildren.length > 0) {
            focusGraphNodeById(rootChildren[0].id)
          } else {
            announceGraphNav('Expand Quality of Life to navigate outcomes')
          }
        }
        handled = true
      } else if (key === 'ArrowUp') {
        const children = visibleNodes
          .filter(node => node.parentId === currentNodeId)
          .sort((a, b) => a.angle - b.angle)
        if (children.length > 0) {
          focusGraphNodeById(children[0].id)
        } else if (currentNode?.hasChildren && !expandedNodes.has(currentNodeId)) {
          announceGraphNav(`Expand ${currentNode.label} to move deeper`)
        } else if (currentNode) {
          announceGraphNav(`${currentNode.label} has no deeper visible nodes`)
        }
        handled = true
      } else if (key === 'ArrowDown') {
        const parentNode = getParent(navModelRef, currentNodeId)
        if (parentNode) {
          focusGraphNodeById(parentNode.id)
        } else if (navModelRef.rootId) {
          focusGraphNodeById(navModelRef.rootId)
        }
        handled = true
      } else if (key === 'Enter' || key === ' ' || key === 'Spacebar') {
        if (currentNode?.hasChildren) {
          const isCurrentlyExpanded = expandedNodes.has(currentNodeId)
          const actionLabel = isCurrentlyExpanded ? 'Collapsed' : 'Expanded'
          pendingExpandedBranchFocusRef.current = isCurrentlyExpanded ? null : currentNodeId
          toggleExpansion(currentNodeId)
          announceGraphNav(`${actionLabel} ${currentNode.label}`)
        } else if (currentNode) {
          announceGraphNav(`${currentNode.label} has no children to expand`)
        } else {
          announceGraphNav('No children to expand')
        }
        handled = true
      } else if (key === 'Escape') {
        const parentNode = getParent(navModelRef, currentNodeId)
        if (parentNode) {
          focusGraphNodeById(parentNode.id)
          announceGraphNav(`Focused parent ${parentNode.label}`)
        } else if (navModelRef.rootId) {
          focusGraphNodeById(navModelRef.rootId)
          announceGraphNav('Already at root node')
        }
        handled = true
      }

      if (handled) {
        event.preventDefault()
        event.stopPropagation()
      }
    })

    // === LABELS with enter/update/exit ===
    const labelNodes = visibleNodes.filter(n => {
      // Dots mode: skip labels for deep-ring nodes
      if (dotsMode && n.ring >= DEEP_RING_THRESHOLD) return false
      if (n.ring === 0) return true
      if (n.parentId && expandedNodes.has(n.parentId)) return true
      if (pinnedPaths.has(n.id)) return true
      return false
    })

    // Helper functions for labels
    const estimateTextWidth = (text: string, fontSize: number) => text.length * fontSize * AVG_CHAR_WIDTH_RATIO
    /**
     * Split label into N lines, distributing words evenly
     */
    const splitIntoLines = (label: string, numLines: number): string[] => {
      const words = label.split(' ')
      if (words.length <= 1 || numLines <= 1) return [label]

      const wordsPerLine = Math.ceil(words.length / numLines)
      const lines: string[] = []

      for (let i = 0; i < words.length; i += wordsPerLine) {
        lines.push(words.slice(i, i + wordsPerLine).join(' '))
      }

      return lines
    }

    /**
     * Determine optimal line count for a label based on available space
     * Prefers fewer lines, only uses more if needed to avoid collision
     */
    const getOptimalLines = (
      label: string,
      fontSize: number,
      availableWidth: number,
      isHorizontal: boolean
    ): string[] => {
      if (!label.includes(' ')) return [label]

      const lineHeight = fontSize * 1.1

      // Try 1 line
      const width1 = estimateTextWidth(label, fontSize)
      if (width1 <= availableWidth) {
        return [label]
      }

      // Try 2 lines
      const lines2 = splitIntoLines(label, 2)
      const maxWidth2 = Math.max(...lines2.map(l => estimateTextWidth(l, fontSize)))
      const height2 = lineHeight * 2
      if (isHorizontal) {
        // For horizontal text, check width fits
        if (maxWidth2 <= availableWidth) {
          return lines2
        }
      } else {
        // For radial text, height (along radius) matters more
        if (maxWidth2 <= availableWidth || height2 <= availableWidth) {
          return lines2
        }
      }

      // Use 3 lines as last resort
      return splitIntoLines(label, 3)
    }
    const getNextRingRadius = (ring: number): number => {
      const nextRing = ring + 1
      if (nextRing < ringRadii.length) return ringRadii[nextRing]
      return Infinity
    }

    // Calculate text boost for branch exploration
    // When exploring few branches, boost small text into readable range (3-5px)
    // Smoothly transition to original sizes as more branches expand
    const MIN_READABLE_SIZE = 3
    const MAX_BOOSTED_SIZE = 5

    // Count expanded Ring 1 nodes (outcomes being explored)
    const expandedOutcomes = visibleNodes.filter(n => n.ring === 1 && expandedNodes.has(n.id))
    const expandedCount = expandedOutcomes.length
    const totalVisibleOutcomes = visibleNodes.filter(n => n.ring === 1).length

    // Smooth boost factor: no hard drop at branch count thresholds.
    const boostFactor = getTextBoostFactor(expandedCount, totalVisibleOutcomes)

    /**
     * Apply readability boost to font size
     * - Ring 0-1: No boost (constant text size for QoL and Outcomes)
     * - Text >= MIN_READABLE_SIZE: no change
     * - Text < MIN_READABLE_SIZE: boost into MIN_READABLE_SIZE to MAX_BOOSTED_SIZE range
     * - Boost strength controlled by boostFactor (based on expanded branch count)
     */
    const applyTextBoost = (baseSize: number, ring: number): number => {
      // Ring 0 (QoL) and Ring 1 (Outcomes) always use base size - no boost
      if (ring <= 1) {
        return baseSize
      }

      if (boostFactor === 0 || baseSize >= MIN_READABLE_SIZE) {
        return baseSize
      }

      // Map small text (0 to MIN_READABLE_SIZE) into boosted range (MIN to MAX)
      // Preserve relative ordering: smaller base = smaller boosted
      const ratio = baseSize / MIN_READABLE_SIZE  // 0 to 1
      const boostedSize = MIN_READABLE_SIZE + ratio * (MAX_BOOSTED_SIZE - MIN_READABLE_SIZE)

      // Blend between original and boosted based on boostFactor
      return baseSize + (boostedSize - baseSize) * boostFactor
    }

    // Compute label positions
    const labelPositions = new Map<string, { x: number; y: number; anchor: string; rotation: number; fontSize: number; lines: string[] }>()
    debug.render('=== RING 1 FONT SIZES ===')

    for (const d of labelNodes) {
      const nodeSize = getSize(d)
      // Ring 0 always uses importance=1.0, others use temporal SHAP (with cache fallback)
      const nodeId = String(d.id)
      const rawImportance = d.ring === 0
        ? (qolNodeScore != null ? 0.5 + qolNodeScore * 0.5 : 1.0)
        : (timelineImportance.get(nodeId) ?? lastValidShapRef.current.get(nodeId) ?? d.importance ?? 0.01)
      const importance = Math.max(0, Number.isFinite(rawImportance) ? rawImportance : 0.01)
      const label = d.label || ''

      // Calculate font size based on ring
      let fontSize: number
      const isSimAffected = simEffectLookup.has(d.id) || interventionNodeIds.has(d.id)
      if (d.ring === 0) {
        // Ring 0 (QoL): size tracks QoL score when country selected
        fontSize = vLayout.getFontSize(importance, d.ring)
      } else if (d.ring === 1) {
        // Ring 1 (Outcomes): Narrower range (4-8px scaled by viewport)
        const baseMax = vLayout.getFontSize(1, 1)  // Get viewport-scaled maximum
        const scaleFactor = baseMax / 16  // Normalize to ~1.0 on 1080p
        const mobileBoost = window.innerWidth < 768 ? 1.4 : 1
        const ring1Min = 4 * scaleFactor * mobileBoost
        const ring1Max = 8 * scaleFactor * mobileBoost
        fontSize = ring1Min + (ring1Max - ring1Min) * Math.sqrt(importance)
        // DEBUG: Log all Ring 1 font sizes
        debug.render(`  ${label}: ${fontSize.toFixed(1)}px (importance=${importance.toFixed(4)})`)
      } else if (isSimAffected) {
        // Affected/intervention nodes at ring 2+: boost to ring 1 size range
        const baseMax = vLayout.getFontSize(1, 1)
        const scaleFactor = baseMax / 16
        const ring1Min = 4 * scaleFactor
        const ring1Max = 8 * scaleFactor
        // Use midpoint of ring 1 range — readable from any zoom
        fontSize = (ring1Min + ring1Max) / 2
      } else {
        // Ring 2+: Importance-based with boost
        const baseFontSize = vLayout.getFontSize(importance, d.ring)
        fontSize = applyTextBoost(baseFontSize, d.ring)
      }

      if (d.ring <= 1) {
        // Ring 0-1: Constant text - no wrapping, no boost
        // Dynamic padding: larger nodes need more space
        const basePadding = Math.max(4, nodeSize * 0.2)
        const offset = nodeSize + fontSize * 0.6 + basePadding

        // Ring 0: add QoL score as second line when country selected
        const scoreText = qolNodeScore != null
          ? `${(qolNodeScore * 10).toFixed(playbackMode === 'simulation' ? 2 : 1)}/10`
          : null
        const lines = d.ring === 0 && qolNodeScore != null
          ? [label, scoreText!]
          : [label]

        labelPositions.set(d.id, { x: d.x, y: d.y + offset, anchor: 'middle', rotation: 0, fontSize, lines })
      } else {
        const offset = nodeSize + fontSize * 0.3 + 2
        const angle = Math.atan2(d.y, d.x)
        const angleDeg = angle * (180 / Math.PI)
        const labelX = d.x + Math.cos(angle) * offset
        const labelY = d.y + Math.sin(angle) * offset
        let rotation = angleDeg
        let anchor: 'start' | 'end' = 'start'
        if (Math.abs(angleDeg) > 90) {
          rotation = angleDeg + 180
          anchor = 'end'
        }
        const nodeRadius = Math.sqrt(d.x * d.x + d.y * d.y)
        const nextRingRadius = getNextRingRadius(d.ring)

        // Available radial space for text
        const availableSpace = nextRingRadius - nodeRadius - offset - 5

        const lines = getOptimalLines(label, fontSize, availableSpace, false)
        labelPositions.set(d.id, { x: labelX, y: labelY, anchor, rotation, fontSize, lines })
      }
    }

    // Labels with enter/update/exit for proper animation timing
    const currentScale = currentTransformRef.current?.k ?? 1
    const initialZoomClass = getZoomClass(currentScale)
    g.attr('class', `graph-container ${initialZoomClass}`)

    // Minimum effective size for readability (font-size * zoom)
    // Set to 3 so boosted 3px text is visible at 1x zoom
    const MIN_EFFECTIVE_SIZE = 3

    /**
     * Check if a label should be visible based on font size and zoom
     * Ring 0-1 always visible, others require minimum effective size
     */
    const isLabelVisible = (ring: number, fontSize: number, zoomScale: number): boolean => {
      if (ring <= 1) return true  // Root and outcomes always visible
      const effectiveSize = fontSize * zoomScale
      return effectiveSize >= MIN_EFFECTIVE_SIZE
    }

    /**
     * Update all label visibility based on current zoom
     * Always sets explicit opacity (1 or 0) to avoid CSS conflicts
     */
    const updateLabelVisibility = (zoomScale: number) => {
      labelsLayer.selectAll<SVGTextElement, ExpandableNode>('text.node-label')
        .style('opacity', function() {
          const ring = parseInt(d3.select(this).attr('data-ring') || '0')
          const fontSize = parseFloat(d3.select(this).attr('data-fontsize') || '0')
          return isLabelVisible(ring, fontSize, zoomScale) ? 1 : 0
        })
    }

    // Update zoom handler to use dynamic visibility
    if (zoomRef.current) {
      zoomRef.current.on('zoom', (event) => {
        g.attr('transform', event.transform)
        currentTransformRef.current = event.transform
        const zoomClass = getZoomClass(event.transform.k)
        g.attr('class', `graph-container ${zoomClass}`)
        // Update label visibility based on actual font sizes
        updateLabelVisibility(event.transform.k)
        // Update QoL node position for loading spinner (direct DOM, no re-render)
        updateQolPosition(event.transform)
      })
    }

    // Fix: remove stale labels mid-exit-transition whose IDs match incoming labels
    if (newNodeIds.size > 0) {
      labelsLayer.selectAll<SVGTextElement, ExpandableNode>('text.node-label')
        .each(function() {
          const el = d3.select(this)
          const id = el.attr('data-id')
          if (id && newNodeIds.has(id)) {
            el.interrupt().remove()
          }
        })
    }

    const labelSelection = labelsLayer.selectAll<SVGTextElement, ExpandableNode>('text.node-label')
      .data(labelNodes, d => d.id)

    // Exit labels (COLLAPSE: fade out first, before nodes collapse)
    labelSelection.exit()
      .transition('label-exit')
      .delay(collapseTextDelay)
      .duration(textFadeDuration)
      .style('opacity', 0)
      .remove()

    // Update labels (move with rotation, update font-size for boost changes)
    // Check each label's actual DOM position vs target - animate if different
    labelSelection.each(function(d) {
      const pos = labelPositions.get(d.id)
      if (pos) {
        const textEl = d3.select(this)
        const currentX = parseFloat(textEl.attr('x') || '0')
        const currentY = parseFloat(textEl.attr('y') || '0')

        // Check if label actually needs to move
        const dx = Math.abs(pos.x - currentX)
        const dy = Math.abs(pos.y - currentY)
        const needsMove = dx > POSITION_CHANGE_THRESHOLD || dy > POSITION_CHANGE_THRESHOLD

        // Parse current rotation from transform attribute
        const currentTransform = textEl.attr('transform') || ''
        const rotateMatch = currentTransform.match(/rotate\(([^,)]+)/)
        const currentRotation = rotateMatch ? parseFloat(rotateMatch[1]) : 0

        // Check if rotation change is large (> 90°) - indicates text direction flip
        // In this case, skip animation to avoid text spinning visibly
        const rotationDiff = Math.abs(pos.rotation - currentRotation)
        const isLargeRotationChange = rotationDiff > 90 && rotationDiff < 270

        // Update data-fontsize for visibility calculations
        textEl.attr('data-fontsize', pos.fontSize)

        // Update text content for ring 0 (QoL score changes with year/country/stratum)
        if (d.ring === 0) {
          const tspans = textEl.selectAll('tspan')
          if (pos.lines.length === 1 && tspans.empty()) {
            // Single line — update text directly
            textEl.text(pos.lines[0])
          } else if (pos.lines.length === 1 && !tspans.empty()) {
            // Had multi-line, now single — remove tspans, set text
            tspans.remove()
            textEl.text(pos.lines[0])
          } else if (pos.lines.length > 1) {
            if (tspans.size() !== pos.lines.length) {
              // Line count changed — rebuild tspans
              textEl.text(null)
              const lineHeight = pos.fontSize * 1.1
              pos.lines.forEach((line, i) => {
                const tspan = textEl.append('tspan')
                  .attr('x', pos.x)
                  .attr('dy', i === 0 ? 0 : lineHeight)
                  .text(line)
                // Score line (second line on ring 0) — smaller and subdued
                if (i === 1 && d.ring === 0) {
                  tspan.attr('font-size', pos.fontSize * 0.7).attr('fill-opacity', 0.7)
                }
              })
            } else {
              // Same line count — update text in place
              tspans.each(function(_d, i) {
                const el = d3.select(this)
                el.text(pos.lines[i])
                if (i === 1 && d.ring === 0) {
                  el.attr('font-size', pos.fontSize * 0.7).attr('fill-opacity', 0.7)
                }
              })
            }
          }
        }

        // Sync text content (e.g. QoL score updates during simulation)
        const tspans = textEl.selectAll('tspan')
        if (pos.lines.length > 1 && tspans.size() === pos.lines.length) {
          tspans.each(function(_: unknown, i: number) {
            const el = d3.select(this as Element)
            if (el.text() !== pos.lines[i]) el.text(pos.lines[i])
          })
        } else if (pos.lines.length === 1 && tspans.empty()) {
          const current = textEl.text()
          if (current !== pos.lines[0]) textEl.text(pos.lines[0])
        }

        const newTransform = pos.rotation !== 0 ? `rotate(${pos.rotation}, ${pos.x}, ${pos.y})` : null

        if (activeBudget.useFastPath) {
          textEl
            .attr('x', pos.x)
            .attr('y', pos.y)
            .attr('font-size', pos.fontSize)
            .attr('text-anchor', pos.anchor)
            .attr('transform', newTransform)
          textEl.selectAll('tspan').attr('x', pos.x)
        } else if (isLargeRotationChange) {
          // Large rotation change (text direction flip) - set instantly without animation
          // Must also update text-anchor when direction flips
          textEl
            .attr('x', pos.x)
            .attr('y', pos.y)
            .attr('font-size', pos.fontSize)
            .attr('text-anchor', pos.anchor)
            .attr('transform', newTransform)
          textEl.selectAll('tspan').attr('x', pos.x)
        } else if (needsMove) {
          // Label position differs from target - animate to new position
          // Update text-anchor immediately (not animatable)
          textEl.attr('text-anchor', pos.anchor)
          textEl
            .transition('rotation')
            .delay(rotationDelay)
            .duration(rotationDuration)
            .attr('x', pos.x)
            .attr('y', pos.y)
            .attr('font-size', pos.fontSize)
            .attr('transform', newTransform)

          // Also update tspans (for multi-line labels)
          textEl.selectAll('tspan')
            .transition('rotation')
            .delay(rotationDelay)
            .duration(rotationDuration)
            .attr('x', pos.x)
        } else if (!shouldSkipRotation) {
          // Position matches but may need font-size/rotation update
          textEl.attr('text-anchor', pos.anchor)
          textEl
            .transition('rotation')
            .delay(rotationDelay)
            .duration(rotationDuration)
            .attr('font-size', pos.fontSize)
            .attr('transform', newTransform)
        }
      }
    })

    // Update visibility after font sizes change
    updateLabelVisibility(currentScale)

    // Enter labels (EXPAND: fade in last, after nodes appear)
    labelSelection.enter()
      .append('text')
      .attr('class', 'node-label')
      .attr('data-id', d => d.id)
      .attr('data-ring', d => d.ring)
      .attr('data-fontsize', d => labelPositions.get(d.id)?.fontSize ?? 0)
      .style('opacity', 0)
      .each(function(d) {
        const pos = labelPositions.get(d.id)!
        const textEl = d3.select(this)
          .attr('x', pos.x)
          .attr('y', pos.y)
          .attr('text-anchor', pos.anchor)
          .attr('transform', pos.rotation !== 0 ? `rotate(${pos.rotation}, ${pos.x}, ${pos.y})` : null)
          .attr('font-size', pos.fontSize)
          .attr('font-weight', d.ring <= 1 ? 'bold' : 'normal')
          .attr('fill', '#333')
          .style('pointer-events', 'none')

        if (pos.lines.length === 1) {
          textEl.text(pos.lines[0])
        } else {
          const lineHeight = pos.fontSize * 1.1
          pos.lines.forEach((line, i) => {
            textEl.append('tspan')
              .attr('x', pos.x)
              .attr('dy', i === 0 ? 0 : lineHeight)
              .text(line)
          })
        }
      })
      .transition()
      .delay(expandTextDelay)
      .duration(textFadeDuration)
      .style('opacity', function(d) {
        // Fade in only if visible at current zoom
        // Always use explicit opacity (1 or 0) to avoid CSS conflicts
        const pos = labelPositions.get(d.id)
        if (!pos) return 0
        return isLabelVisible(d.ring, pos.fontSize, currentScale) ? 1 : 0
      })

    if (activeLayoutActionRef.current !== null) {
      const runId = activeLayoutRunIdRef.current
      if (structuralTraceScheduledIdRef.current !== runId) {
        structuralTraceScheduledIdRef.current = runId
        if (structuralTraceFinalizeTimerRef.current !== null) {
          clearTimeout(structuralTraceFinalizeTimerRef.current)
          structuralTraceFinalizeTimerRef.current = null
        }
        if (structuralAnimationWindowMs <= 0) {
          finalizeStructuralTrace(0)
        } else {
          structuralTraceFinalizeTimerRef.current = window.setTimeout(() => {
            if (activeLayoutRunIdRef.current === runId && activeLayoutActionRef.current !== null) {
              finalizeStructuralTrace(structuralAnimationWindowMs)
            }
          }, structuralAnimationWindowMs)
        }
      }
    } else if (structuralTraceFinalizeTimerRef.current !== null) {
      clearTimeout(structuralTraceFinalizeTimerRef.current)
      structuralTraceFinalizeTimerRef.current = null
      structuralTraceScheduledIdRef.current = null
    }

    // Signal layout ready after all D3 transitions complete.
    // Keep one timer alive at a time so rapid re-renders don't enqueue stale callbacks.
    if (!layoutReady && playbackMode === 'simulation') {
      const settleMs = nodeAnimationEndTime + 200  // +200ms buffer for paint
      if (layoutReadyTimerRef.current !== null) {
        clearTimeout(layoutReadyTimerRef.current)
      }
      layoutReadyTimerRef.current = window.setTimeout(() => {
        layoutReadyTimerRef.current = null
        setLayoutReady(true)
      }, settleMs)
    } else if (layoutReadyTimerRef.current !== null) {
      clearTimeout(layoutReadyTimerRef.current)
      layoutReadyTimerRef.current = null
    }

  }, [visibleNodes, visibleEdges, computedRingsState, ringConfigs, expandedNodes, toggleExpansion, resetView, fitToVisibleNodes, ringRadii, layoutValues, calculateInitialTransform, highlightedPath, highlightedTarget, highlightSource, nodesByRingMemo, addToLocalView, localViewNodeIds, localViewNodeRoles, viewMode, splitRatio, temporalResults, historicalTimeline, playbackMode, currentYearIndex, precomputedShapCache, aggregateEffects, isPlaying, isPanelOpen, layoutReady, setLayoutReady, pinnedPaths, rawData, selectedCountry, selectedRegion, selectedStratum, qolNodeScoreForTooltip, storeInterventions, finalizeStructuralTrace, setStructuralLock, graphNavEnabled, announceGraphNav])

  // Initialize screen reader live region
  useEffect(() => { initAnnouncer() }, [])

  // ── Screen reader announcements for key state changes ──

  // Country / region selection
  const prevAnnouncedCountry = useRef(selectedCountry)
  const prevAnnouncedRegion = useRef(selectedRegion)
  useEffect(() => {
    if (selectedCountry && selectedCountry !== prevAnnouncedCountry.current) {
      announce(`Now showing ${selectedCountry} causal graph`)
    } else if (selectedRegion && selectedRegion !== prevAnnouncedRegion.current) {
      announce(`Now showing ${REGION_DISPLAY_NAMES[selectedRegion] ?? selectedRegion} causal graph`)
    }
    prevAnnouncedCountry.current = selectedCountry
    prevAnnouncedRegion.current = selectedRegion
  }, [selectedCountry, selectedRegion])

  // View mode switch
  const prevAnnouncedView = useRef(viewMode)
  useEffect(() => {
    if (viewMode !== prevAnnouncedView.current) {
      announce(`Switched to ${viewMode} view`)
      prevAnnouncedView.current = viewMode
    }
  }, [viewMode])

  // Simulation complete
  const prevTemporalResultsForA11y = useRef(temporalResults)
  useEffect(() => {
    if (temporalResults && !prevTemporalResultsForA11y.current) {
      const lastYear = Object.keys(temporalResults.effects).sort().pop()
      const count = lastYear ? Object.keys(temporalResults.effects[lastYear]).length : 0
      announce(`Simulation complete. ${count} indicators affected`)
    }
    prevTemporalResultsForA11y.current = temporalResults
  }, [temporalResults])

  // Timeline year change (debounced during playback)
  const yearAnnounceTimer = useRef<number | null>(null)
  useEffect(() => {
    if (yearAnnounceTimer.current) clearTimeout(yearAnnounceTimer.current)
    const year = playbackMode === 'simulation' && temporalResults
      ? temporalResults.base_year + currentYearIndex
      : historicalTimeline?.years?.[currentYearIndex]
    if (year == null) return
    yearAnnounceTimer.current = window.setTimeout(() => {
      announce(`Year ${year}`)
    }, 500)
    return () => { if (yearAnnounceTimer.current) clearTimeout(yearAnnounceTimer.current) }
  }, [currentYearIndex, playbackMode, temporalResults, historicalTimeline])

  // Fetch data once on mount
  useEffect(() => {
    fetchData()
  }, [fetchData])

  // Restore state from URL after data loads
  useEffect(() => {
    if (!rawData || urlStateRestoredRef.current) return

    const urlState = getStateFromBrowserURL()
    if (!urlState) {
      urlStateRestoredRef.current = true
      return
    }

    debug.layout('[URL Restore] Restoring state from URL:', urlState)

    // Restore view mode
    if (urlState.view) {
      setViewMode(urlState.view)
    }

    // Store expanded nodes for later (applied once raw graph data is mounted)
    if (urlState.expanded && urlState.expanded.length > 0) {
      pendingExpandedNodesRef.current = urlState.expanded
    }

    // Restore Local View targets
    if (urlState.targets && urlState.targets.length > 0) {
      setLocalViewTargets(urlState.targets)
    }

    // Restore beta threshold
    if (urlState.beta !== undefined) {
      setLocalViewBetaThreshold(urlState.beta)
    }

    // Restore highlighted node (trigger navigation)
    if (urlState.highlight) {
      const nodeMap = new Map(rawData.nodes.map(n => [String(n.id), n]))
      const node = nodeMap.get(urlState.highlight)
      if (node) {
        // Delay highlight to ensure nodes are rendered
        setTimeout(() => {
          setHighlightedTarget(urlState.highlight!)
          // Build highlight path from node to Ring 1
          const highlightPath = new Set<string>()
          highlightPath.add(urlState.highlight!)
          let current = node
          while (current.parent) {
            const parentId = String(current.parent)
            highlightPath.add(parentId)
            const parent = nodeMap.get(parentId)
            if (!parent || parent.layer <= 1) break
            current = parent
          }
          setHighlightedPath(highlightPath)
        }, 500)
      }
    }

    // Restore zoom state
    if (urlState.zoom && zoomRef.current && svgRef.current) {
      setTimeout(() => {
        const transform = d3.zoomIdentity
          .translate(urlState.zoom!.x, urlState.zoom!.y)
          .scale(urlState.zoom!.k)
        currentTransformRef.current = transform
        d3.select(svgRef.current!).call(zoomRef.current!.transform, transform)
      }, 600)
    }

    // Restore simulation state from URL
    if (urlState.country || urlState.interventions || urlState.template) {
      const simStore = useSimulationStore.getState()
      simStore.openPanel()
      // On mobile, start minimized so the graph is visible
      if (window.innerWidth < 768) {
        setSimMinimized(true)
      }

      // Country and stratum are mutually exclusive in shared state
      if (urlState.country) {
        simStore.setCountry(urlState.country)
      } else if (urlState.stratum && urlState.stratum !== 'unified') {
        simStore.setStratum(urlState.stratum)
      }

      // Apply template OR set custom interventions
      if (urlState.template) {
        // Load templates then apply
        simStore.loadTemplates().then(() => {
          useSimulationStore.getState().applyTemplate(urlState.template!)
          // Apply explicit URL range after template defaults.
          if (urlState.simStart) useSimulationStore.getState().setSimulationStartYear(urlState.simStart)
          if (urlState.simEnd) useSimulationStore.getState().setSimulationEndYear(urlState.simEnd)
        })
      } else if (urlState.interventions) {
        const interventions = urlState.interventions.map((iv, idx) => ({
          id: `url-${idx}`,
          indicator: iv.ind,
          indicatorLabel: '',  // Resolved by InterventionBuilder on render
          change_percent: iv.pct,
          year: iv.yr,
          domain: ''
        }))
        simStore.setInterventions(interventions)
        if (urlState.simStart) simStore.setSimulationStartYear(urlState.simStart)
        if (urlState.simEnd) simStore.setSimulationEndYear(urlState.simEnd)
      } else {
        if (urlState.simStart) simStore.setSimulationStartYear(urlState.simStart)
        if (urlState.simEnd) simStore.setSimulationEndYear(urlState.simEnd)
      }
    }

    urlStateRestoredRef.current = true
  }, [rawData])

  // Apply expanded nodes as soon as raw graph data is ready.
  // SHAP cache can hydrate later without blocking initial paint.
  useEffect(() => {
    if (!rawData || !urlStateRestoredRef.current || initialExpansionDoneRef.current) return
    if (expandedNodes.size > 0) return  // Already expanded

    // Use pending expanded nodes from URL if available
    if (pendingExpandedNodesRef.current) {
      setExpandedNodes(new Set(pendingExpandedNodesRef.current))
      pendingExpandedNodesRef.current = null
    } else {
      // Default: expand Ring 1 (root node)
      const rootNode = rawData.nodes.find(n => n.layer === 0)
      if (rootNode) {
        setExpandedNodes(new Set([String(rootNode.id)]))
      }
    }
    initialExpansionDoneRef.current = true
  }, [rawData, expandedNodes.size])

  // Subscribe to simulation store fields for URL sync
  const simCountry = useSimulationStore(s => s.selectedCountry)
  const simStratum = useSimulationStore(s => s.selectedStratum)
  const simInterventions = useSimulationStore(s => s.interventions)
  const simActiveTemplate = useSimulationStore(s => s.activeTemplate)
  const simTemplateModified = useSimulationStore(s => s.templateModified)
  const simStartYear = useSimulationStore(s => s.simulationStartYear)
  const simEndYear = useSimulationStore(s => s.simulationEndYear)

  // Sync state to URL when key state changes
  useEffect(() => {
    // Don't sync until URL state has been restored (avoid overwriting on load)
    if (!urlStateRestoredRef.current) return

    const state: URLState = {
      view: viewMode,
      expanded: expandedNodes.size > 0 ? Array.from(expandedNodes) : undefined,
      targets: localViewTargets.length > 0 ? localViewTargets : undefined,
      beta: localViewBetaThreshold !== 0.5 ? localViewBetaThreshold : undefined,
      highlight: highlightedTarget || undefined
    }

    // Add zoom state if available
    if (currentTransformRef.current) {
      const t = currentTransformRef.current
      state.zoom = { k: t.k, x: t.x, y: t.y }
    }

    // Add simulation state
    if (simCountry) state.country = simCountry
    if (!simCountry && simStratum !== 'unified') state.stratum = simStratum
    if (simInterventions.length > 0 && (!simActiveTemplate || simTemplateModified)) {
      state.interventions = simInterventions.map(iv => ({
        ind: iv.indicator,
        pct: iv.change_percent,
        yr: iv.year
      }))
    }
    if (simActiveTemplate && !simTemplateModified) state.template = simActiveTemplate.id
    if (simStartYear !== 2020) state.simStart = simStartYear
    if (simEndYear !== 2029) state.simEnd = simEndYear

    updateBrowserURL(state)
  }, [viewMode, expandedNodes, localViewTargets, localViewBetaThreshold, highlightedTarget,
      simCountry, simStratum, simInterventions, simActiveTemplate, simTemplateModified, simStartYear, simEndYear])

  // Recompute layout when rawData or ringRadii changes
  useEffect(() => {
    computeLayout()
  }, [computeLayout])

  // Re-render when visible nodes change (expansion state changes)
  useEffect(() => {
    renderVisualization()
  }, [renderVisualization])

  // Auto-zoom on expand/collapse
  useEffect(() => {
    const logCamera = (...args: unknown[]) => {
      if (!import.meta.env.DEV) return
      console.log('[Camera]', ...args)
    }

    if (!pendingZoomRef.current || !zoomRef.current || !svgRef.current || visibleNodes.length === 0) return

    const runToken = ++autoZoomRunTokenRef.current

    if (autoZoomDelayTimerRef.current !== null) {
      clearTimeout(autoZoomDelayTimerRef.current)
      autoZoomDelayTimerRef.current = null
      noteStructuralZoomOverlap()
    }
    if (autoZoomRafRef.current !== null) {
      cancelAnimationFrame(autoZoomRafRef.current)
      autoZoomRafRef.current = null
      noteStructuralZoomOverlap()
    }
    if (isAnimatingZoomRef.current) {
      noteStructuralZoomOverlap()
    }

    const { nodeId, action } = pendingZoomRef.current
    logCamera('start', {
      action,
      nodeId,
      visibleNodeCount: visibleNodes.length,
      expandedNodeCount: expandedNodes.size,
    })

    // Find the node that was expanded/collapsed
    const targetNode = visibleNodes.find(n => n.id === nodeId)
    if (!targetNode) {
      logCamera('abort: target node not visible yet', { nodeId, action })
      return
    }

    // No camera change when expanding root (ring 0)
    if (action === 'expand' && targetNode.ring === 0) {
      logCamera('skip: root expand', { nodeId })
      pendingZoomRef.current = null
      return
    }

    if (action === 'expand') {
      // For expand, we need to wait until children are actually visible
      const directChildren = visibleNodes.filter(n => n.parentId === nodeId)
      if (targetNode.hasChildren && directChildren.length === 0) {
        // Children not yet in visibleNodes, wait for next update
        logCamera('wait: expand children not visible yet', { nodeId })
        return
      }
    }

    // Clear the pending action now that we're ready to process
    pendingZoomRef.current = null

    const svg = d3.select(svgRef.current)
    const zoom = zoomRef.current
    // Use split-aware dimensions for zoom calculations
    const width = viewMode === 'split' ? window.innerWidth * splitRatio : window.innerWidth
    const height = window.innerHeight
    const currentTransform = currentTransformRef.current || d3.zoomIdentity

    const runCameraComputation = () => {
      if (runToken !== autoZoomRunTokenRef.current) {
        logCamera('skip: stale run token', { runToken, latest: autoZoomRunTokenRef.current, action, nodeId })
        return
      }

      /**
       * Find the Ring 1 ancestor of a node (walk up the tree)
       */
      const getRing1Ancestor = (node: ExpandableNode): ExpandableNode | null => {
        if (node.ring === 1) return node
        if (node.ring === 0) return null // Root has no Ring 1 ancestor

        // Walk up the tree to find Ring 1 ancestor
        let current = node
        while (current.ring > 1 && current.parentId) {
          const parent = visibleNodes.find(n => n.id === current.parentId)
          if (!parent) break
          current = parent
        }
        return current.ring === 1 ? current : null
      }

      /**
       * Get all descendants of a node (entire subtree)
       */
      const getSubtreeNodes = (rootId: string): ExpandableNode[] => {
        const result: ExpandableNode[] = []
        const rootNode = visibleNodes.find(n => n.id === rootId)
        if (rootNode) result.push(rootNode)

        const addDescendants = (parentId: string) => {
          visibleNodes.filter(n => n.parentId === parentId).forEach(child => {
            result.push(child)
            addDescendants(child.id)
          })
        }
        addDescendants(rootId)
        return result
      }

      const computeBounds = (nodes: ExpandableNode[]) => {
        if (nodes.length === 0) return null
        const allXs = nodes.map(n => n.x)
        const allYs = nodes.map(n => n.y)
        const minX = Math.min(...allXs)
        const maxX = Math.max(...allXs)
        const minY = Math.min(...allYs)
        const maxY = Math.max(...allYs)
        return {
          minX,
          maxX,
          minY,
          maxY,
          width: Math.max(maxX - minX, 1),
          height: Math.max(maxY - minY, 1),
          centerX: (minX + maxX) / 2,
          centerY: (minY + maxY) / 2,
        }
      }

      const getCollapseFocusNodes = (): ExpandableNode[] => {
        const focusById = new Map<string, ExpandableNode>()
        const rootNode = visibleNodes.find(n => n.ring === 0)
        if (rootNode) {
          focusById.set(rootNode.id, rootNode)
        }

        const ring1Nodes = visibleNodes.filter(n => n.ring === 1)
        const expandedRing1 = ring1Nodes.filter(n => expandedNodes.has(n.id))
        const ring1Roots = expandedRing1.length > 0 ? expandedRing1 : ring1Nodes

        ring1Roots.forEach(branchRoot => {
          getSubtreeNodes(branchRoot.id).forEach(node => {
            focusById.set(node.id, node)
          })
        })

        if (focusById.size === 0) {
          focusById.set(targetNode.id, targetNode)
        }

        return Array.from(focusById.values())
      }

      let focusNodes: ExpandableNode[] = []

      if (action === 'expand') {
        // EXPAND: fit root + the active branch being expanded.
        const ring1Ancestor = getRing1Ancestor(targetNode)
        const branchRootId = ring1Ancestor ? ring1Ancestor.id : nodeId
        focusNodes = getSubtreeNodes(branchRootId)
      } else {
        // COLLAPSE: fit root + all currently expanded branches that remain visible.
        focusNodes = getCollapseFocusNodes()
      }

      const bounds = computeBounds(focusNodes)
      if (!bounds) {
        logCamera('abort: no bounds from focus nodes', { action, nodeId, focusCount: focusNodes.length })
        return
      }

      let centerX = bounds.centerX
      let centerY = bounds.centerY

      // Calculate zoom-to-fit with padding.
      const currentScale = currentTransform.k
      let newScale = currentScale

      const padding = 0.1
      const scaleX = width * (1 - 2 * padding) / bounds.width
      const scaleY = height * (1 - 2 * padding) / bounds.height
      const fitScale = Math.min(scaleX, scaleY)

      // Always zoom out if content won't fit.
      if (fitScale < currentScale) {
        newScale = fitScale
      } else if (action === 'expand' && currentScale < 0.8) {
        // Expand keeps previous behavior: gently zoom in only when very zoomed out.
        newScale = Math.min(0.8, fitScale)
      } else if (action === 'collapse') {
        // Collapse: allow a small zoom-in step so recentering remains perceptible.
        const collapseZoomInCap = Math.min(fitScale, currentScale * 1.12)
        if (collapseZoomInCap > currentScale + 0.01) {
          newScale = collapseZoomInCap
        }
      }

      // Cap at reasonable bounds
      newScale = Math.max(0.1, Math.min(newScale, 3))

      // On collapse, bias camera toward QoL center when current scale has spare room.
      // Clamp to the feasible center range so active branches remain fully visible.
      let collapseCenterRange: {
        minCenterX: number
        maxCenterX: number
        minCenterY: number
        maxCenterY: number
      } | null = null
      if (action === 'collapse') {
        const halfVisibleWidth = (width * (1 - 2 * padding)) / (2 * newScale)
        const halfVisibleHeight = (height * (1 - 2 * padding)) / (2 * newScale)

        const minCenterX = bounds.maxX - halfVisibleWidth
        const maxCenterX = bounds.minX + halfVisibleWidth
        const minCenterY = bounds.maxY - halfVisibleHeight
        const maxCenterY = bounds.minY + halfVisibleHeight
        collapseCenterRange = { minCenterX, maxCenterX, minCenterY, maxCenterY }

        const clamp = (value: number, minValue: number, maxValue: number) =>
          Math.min(maxValue, Math.max(minValue, value))

        centerX = clamp(0, minCenterX, maxCenterX)
        centerY = clamp(0, minCenterY, maxCenterY)
      }

      // Calculate translation to center the relevant content
      let newX = width / 2 - centerX * newScale
      let newY = getGraphCenterY(height) - centerY * newScale

      if (action === 'collapse' && collapseCenterRange) {
        const deltaX = Math.abs(newX - currentTransform.x)
        const deltaY = Math.abs(newY - currentTransform.y)
        const deltaScale = Math.abs(newScale - currentScale)

        // If computed collapse transform is nearly unchanged, nudge toward QoL center.
        if (deltaX < 10 && deltaY < 10 && deltaScale < 0.015) {
          const clamp = (value: number, minValue: number, maxValue: number) =>
            Math.min(maxValue, Math.max(minValue, value))

          const recenteredX = clamp(centerX * 0.72, collapseCenterRange.minCenterX, collapseCenterRange.maxCenterX)
          const recenteredY = clamp(centerY * 0.72, collapseCenterRange.minCenterY, collapseCenterRange.maxCenterY)
          newX = width / 2 - recenteredX * newScale
          newY = getGraphCenterY(height) - recenteredY * newScale
          logCamera('collapse nudge applied', {
            centerBefore: { x: centerX, y: centerY },
            centerAfter: { x: recenteredX, y: recenteredY },
            deltaBefore: { x: deltaX, y: deltaY, scale: deltaScale },
          })
        }
      }

      const newTransform = d3.zoomIdentity.translate(newX, newY).scale(newScale)
      logCamera('target computed', {
        action,
        nodeId,
        focusCount: focusNodes.length,
        bounds,
        scale: { currentScale, fitScale, newScale },
        translation: {
          current: { x: currentTransform.x, y: currentTransform.y },
          next: { x: newX, y: newY },
          delta: {
            x: newX - currentTransform.x,
            y: newY - currentTransform.y,
            scale: newScale - currentScale,
          },
        },
        collapseCenterRange,
      })

      // Animate using manual interpolation for smoother results
      isAnimatingZoomRef.current = true
      const startTransform = currentTransform
      const baseDuration = activeLayoutBudgetRef.current?.cameraMs ?? 400
      const duration = action === 'collapse'
        ? Math.round(baseDuration * 1.22)
        : baseDuration
      const startTime = performance.now()

      const animate = (currentTime: number) => {
        if (runToken !== autoZoomRunTokenRef.current) {
          isAnimatingZoomRef.current = false
          return
        }
        const elapsed = currentTime - startTime
        const t = Math.min(elapsed / duration, 1)
        // Ease out cubic
        const eased = 1 - Math.pow(1 - t, 3)

        const interpolatedK = startTransform.k + (newTransform.k - startTransform.k) * eased
        const interpolatedX = startTransform.x + (newTransform.x - startTransform.x) * eased
        const interpolatedY = startTransform.y + (newTransform.y - startTransform.y) * eased

        const interpolatedTransform = d3.zoomIdentity.translate(interpolatedX, interpolatedY).scale(interpolatedK)

        // Apply transform directly to the g element and update zoom
        svg.select('g.graph-container').attr('transform', interpolatedTransform.toString())
        currentTransformRef.current = interpolatedTransform

        if (t < 1) {
          autoZoomRafRef.current = requestAnimationFrame(animate)
        } else {
          // Sync zoom behavior state at the end
          svg.call(zoom.transform, newTransform)
          currentTransformRef.current = newTransform
          isAnimatingZoomRef.current = false
          autoZoomRafRef.current = null
        }
      }

      autoZoomRafRef.current = requestAnimationFrame(animate)
    }

    if (action === 'collapse') {
      // Collapse should react immediately; delaying this often gets canceled by rerender churn.
      autoZoomRafRef.current = requestAnimationFrame(() => {
        autoZoomRafRef.current = null
        runCameraComputation()
      })
      logCamera('schedule: collapse on next animation frame', { nodeId })
    } else {
      // Expand waits briefly so newly-entering children are laid out before framing.
      autoZoomDelayTimerRef.current = window.setTimeout(() => {
        autoZoomDelayTimerRef.current = null
        runCameraComputation()
      }, 100)
      logCamera('schedule: expand after delay', { nodeId, delayMs: 100 })
    }
  }, [visibleNodes, expandedNodes, viewMode, splitRatio, noteStructuralZoomOverlap])

  return (
    <div style={{ width: '100vw', height: '100vh', overflow: 'hidden', background: '#eef0f6', position: 'relative' }}>
      {/* World Map - background choropleth layer */}
      <WorldMap
        foreground={mapForeground}
        qolScores={qolScores}
        currentYear={mapCurrentYear}
        selectedStratum={selectedStratum}
        classificationsCache={classificationsCache}
        simAdjustments={mapSimAdjustments}
        onCountrySelect={(name) => storeSetCountry(name)}
        onCountryHover={(name) => setMapHoveredCountry(name)}
        selectedCountryIso3={selectedCountryIso3}
        mapViewMode={mapViewMode}
        onRegionSelect={(regionKey) => setSelectedRegion(regionKey as import('./constants/regions').RegionKey)}
        selectedRegion={selectedRegion}
        enableZoom={viewport.isBelow(768)}
        mobileLayout={viewport.isBelow(768)}
      />

      {/* Left Sidebar - Responsive flex container */}
      <SidebarDrawer
        isMobileLayout={viewport.isBelow(768)}
        isOpen={sidebarOpen}
        onToggle={() => setSidebarOpen(prev => !prev)}
        onClose={() => setSidebarOpen(false)}
        strataVisible={!selectedCountry && !selectedRegion}
        hideHamburger={(isPanelOpen && !simMinimized) || (dataQualityOpen && !dqMinimized)}
      >
      <div
        className="left-sidebar"
        style={{
          position: viewport.isBelow(768) ? 'relative' : 'absolute',
          top: viewport.isBelow(768) ? 0 : 16,
          left: viewport.isBelow(768) ? 0 : 10,
          bottom: viewport.isBelow(768) ? undefined : 10,
          width: viewport.isBelow(768) ? '100%' : 'min(220px, 26vw)',
          display: 'flex',
          flexDirection: 'column',
          justifyContent: 'space-between',
          zIndex: viewport.isBelow(768) ? undefined : 100,
          pointerEvents: viewport.isBelow(768) ? 'auto' : 'none'
        }}
      >
        {/* Top Group - Search, Country, Rings, Domains */}
        <header style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
          {/* Search Bar */}
          <div className="search-container" style={{
            display: 'flex', flexDirection: 'column', alignItems: 'stretch',
            pointerEvents: 'auto'
          }}>
        <div style={{
          display: 'flex', alignItems: 'center', gap: 8,
          background: 'white', padding: '10px 12px', borderRadius: 6,
          boxShadow: '0 2px 6px rgba(0,0,0,0.1)', width: '100%', boxSizing: 'border-box'
        }}>
          {/* Search icon */}
          <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="#888" strokeWidth="2" aria-hidden="true">
            <circle cx="11" cy="11" r="8" />
            <path d="M21 21l-4.35-4.35" />
          </svg>

          {/* Search input */}
          <input
            ref={searchInputRef}
            id="graph-search"
            name="graph-search"
            type="text"
            value={searchQuery}
            onChange={(e) => handleSearch(e.target.value)}
            onFocus={() => {
              if (searchResults.length > 0) setShowSearchResults(true)
              // Show recent searches on focus, auto-hide after 5 seconds
              if (recentSearches.length > 0 && !searchQuery) {
                setShowRecentSearches(true)
                if (recentSearchesTimeoutRef.current) {
                  clearTimeout(recentSearchesTimeoutRef.current)
                }
                recentSearchesTimeoutRef.current = window.setTimeout(() => {
                  setShowRecentSearches(false)
                }, 5000)
              }
            }}
            onBlur={() => {
              // Hide recent searches on blur (with small delay for click handling)
              setTimeout(() => setShowRecentSearches(false), 200)
            }}
            placeholder="Search... (/)"
            style={{
              flex: 1, border: 'none', fontSize: 12,
              background: 'transparent', minWidth: 0
            }}
          />

          {/* Clear button */}
          {searchQuery && (
            <button
              className="touch-target-44"
              aria-label="Clear search"
              onClick={() => {
                setSearchQuery('')
                setSearchResults([])
                setShowSearchResults(false)
              }}
              style={{
                background: 'none', border: 'none', cursor: 'pointer',
                padding: 4, display: 'flex', alignItems: 'center'
              }}
            >
              <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="#888" strokeWidth="2" aria-hidden="true">
                <path d="M18 6L6 18M6 6l12 12" />
              </svg>
            </button>
          )}
        </div>

        {/* Search results dropdown */}
        {showSearchResults && searchResults.length > 0 && (
          <div style={{
            background: 'white', borderRadius: 8, marginTop: 4,
            boxShadow: '0 4px 12px rgba(0,0,0,0.15)', width: '100%',
            maxHeight: 300, overflow: 'auto'
          }}>
            {searchResults.map((node, i) => (
              <div
                key={node.id}
                onClick={() => jumpToNode(node)}
                style={{
                  padding: '10px 14px', cursor: 'pointer',
                  borderBottom: i < searchResults.length - 1 ? '1px solid #e2e6ee' : 'none',
                  display: 'flex', alignItems: 'center', gap: 10
                }}
                onMouseEnter={(e) => e.currentTarget.style.background = '#eef0f6'}
                onMouseLeave={(e) => e.currentTarget.style.background = 'white'}
              >
                {/* Domain color dot */}
                <div style={{
                  width: 10, height: 10, borderRadius: '50%',
                  backgroundColor: DOMAIN_COLORS[node.domain] || '#9E9E9E',
                  flexShrink: 0
                }} />

                <div style={{ flex: 1, minWidth: 0 }}>
                  <div style={{ fontSize: 13, fontWeight: 500, color: '#333' }}>
                    {node.label}
                  </div>
                  <div style={{ fontSize: 11, color: '#767676', marginTop: 2 }}>
                    {node.domain}
                    {node.subdomain && node.subdomain !== node.domain && (
                      <> &rsaquo; {node.subdomain}</>
                    )}
                    <span style={{ marginLeft: 8, color: '#767676' }}>
                      Ring {node.ring}
                    </span>
                  </div>
                </div>

                {/* Importance badge */}
                <div style={{
                  fontSize: 10, padding: '2px 6px', borderRadius: 4,
                  background: '#f0f0f0', color: '#666'
                }}>
                  {(node.importance * 100).toFixed(1)}%
                </div>
              </div>
            ))}
          </div>
        )}

        {/* Recent searches */}
        {!showSearchResults && !searchQuery && showRecentSearches && recentSearches.length > 0 && (
          <div style={{
            background: 'white', borderRadius: 8, marginTop: 4, padding: '8px 12px',
            boxShadow: '0 2px 8px rgba(0,0,0,0.1)', width: '100%'
          }}>
            <div style={{ fontSize: 10, color: '#767676', marginBottom: 6 }}>Recent searches</div>
            <div style={{ display: 'flex', flexWrap: 'wrap', gap: 6 }}>
              {recentSearches.map((term, i) => (
                <button
                  key={i}
                  onClick={() => handleSearch(term)}
                  style={{
                    background: '#eef0f6', border: 'none', borderRadius: 4,
                    padding: '4px 8px', fontSize: 11, cursor: 'pointer', color: '#555'
                  }}
                >
                  {term}
                </button>
              ))}
            </div>
          </div>
        )}
        </div>

        {/* Country Selector */}
        <div style={{ background: 'white', padding: viewport.isBelow(768) ? '10px 12px' : '8px 10px', borderRadius: 6, boxShadow: '0 2px 4px rgba(0,0,0,0.1)', border: '1px solid #d0d5e0', pointerEvents: 'auto' }}>
          <CountrySelector />
        </div>

        {/* Rings Panel - Hidden in local view */}
        {ringStats.length > 0 && viewMode !== 'local' && (
          <nav aria-label="Graph controls" style={{ background: 'white', padding: '8px 10px', borderRadius: 4, boxShadow: '0 2px 4px rgba(0,0,0,0.1)', fontSize: 11, pointerEvents: 'auto', maxWidth: viewport.isBelow(768) ? undefined : 180 }}>
            <div style={{ fontWeight: 'bold', marginBottom: 6, fontSize: 11 }}>Rings</div>
            {ringStats.map((ring, i) => (
              <div key={i} style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 2, paddingBottom: 2, borderBottom: i < ringStats.length - 1 ? '1px solid #e2e6ee' : 'none' }}>
                <span style={{ color: '#555', fontSize: 10 }}>{ring.label}</span>
                <div style={{ display: 'flex', alignItems: 'center', gap: 4 }}>
                  <span style={{ fontWeight: 'bold', color: '#333', fontSize: 10, marginRight: 2 }}>{ring.count.toLocaleString()}</span>
                  {i < ringStats.length - 1 && (
                    <>
                      <button
                        className="touch-target-44"
                        onClick={() => expandRing(i)}
                        aria-label={`Expand ${ring.label}`}
                        style={{ padding: '3px 7px', fontSize: 11, cursor: 'pointer', border: '1px solid #bcc3d4', borderRadius: 2, background: '#eef0f6', lineHeight: 1.2 }}
                        title={`Expand ${ring.label}`}
                      >+</button>
                      <button
                        className="touch-target-44"
                        onClick={() => collapseRing(i)}
                        aria-label={`Collapse ${ring.label}`}
                        style={{ padding: '3px 7px', fontSize: 11, cursor: 'pointer', border: '1px solid #bcc3d4', borderRadius: 2, background: '#eef0f6', lineHeight: 1.2 }}
                        title={`Collapse ${ring.label}`}
                      >−</button>
                    </>
                  )}
                </div>
              </div>
            ))}
          </nav>
        )}

        {/* Domain Legend */}
        {Object.keys(domainCounts).length > 0 && (
          <div style={{
            background: 'white',
            padding: '8px 10px',
            borderRadius: 4,
            boxShadow: '0 2px 4px rgba(0,0,0,0.1)',
            pointerEvents: 'auto',
            flex: viewMode === 'local' ? 1 : 'none',
            display: 'flex',
            flexDirection: 'column',
            maxWidth: viewport.isBelow(768) ? undefined : 180
          }}>
            <div style={{ fontWeight: 'bold', marginBottom: 4, fontSize: 11 }}>Domains</div>
            <div style={{ display: 'flex', flexDirection: 'column', gap: 2 }}>
              {Object.entries(domainCounts).sort((a, b) => b[1] - a[1]).map(([domain, count]) => (
                <div key={domain} style={{ display: 'flex', alignItems: 'center' }}>
                  <div style={{ width: 8, height: 8, borderRadius: '50%', backgroundColor: DOMAIN_COLORS[domain] || '#9E9E9E', marginRight: 6, flexShrink: 0 }} />
                  <span style={{ fontSize: 10, flex: 1, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>{domain}</span>
                  <span style={{ fontSize: 9, color: '#767676', marginLeft: 4 }}>({count})</span>
                </div>
              ))}
            </div>
          </div>
        )}
        </header>

        {/* Bottom - Data Quality & Simulate Buttons (desktop only inside sidebar) */}
        {!viewport.isBelow(768) && (
        <div style={{ pointerEvents: 'auto', display: 'flex', gap: 8 }}>
          {/* Data Quality Button */}
          <button
            onClick={() => setDataQualityOpen(!dataQualityOpen)}
            onMouseEnter={() => setDataQualityBtnHovered(true)}
            onMouseLeave={() => setDataQualityBtnHovered(false)}
            title="Data Quality"
            style={{
              width: 48,
              height: 48,
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center',
              background: dataQualityOpen ? '#10B981' : dataQualityBtnHovered ? '#f0f0f0' : 'rgba(255, 255, 255, 0.95)',
              border: dataQualityOpen ? '1px solid #10B981' : '1px solid #d0d5e0',
              borderRadius: 24,
              color: dataQualityOpen ? 'white' : dataQualityBtnHovered ? '#333' : '#666',
              cursor: 'pointer',
              boxShadow: dataQualityOpen ? '0 2px 8px rgba(16, 185, 129, 0.4)' : '0 2px 12px rgba(0, 0, 0, 0.1)',
              backdropFilter: 'blur(8px)',
              transition: 'background 0.2s ease, color 0.2s ease, box-shadow 0.2s ease'
            }}
          >
            {/* Erlenmeyer flask icon */}
            <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
              <path d="M9 3h6v5l4 9a2 2 0 0 1-1.8 2.9H6.8A2 2 0 0 1 5 17l4-9V3z" />
              <line x1="9" y1="3" x2="15" y2="3" />
              <path d="M8 14h8" />
            </svg>
          </button>

          {/* Simulate Button */}
          <button
            onClick={togglePanel}
            onMouseEnter={() => setSimulateBtnHovered(true)}
            onMouseLeave={() => setSimulateBtnHovered(false)}
            title="Simulate"
            style={{
              width: 48,
              height: 48,
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center',
              background: isPanelOpen ? '#3B82F6' : simulateBtnHovered ? '#f0f0f0' : 'rgba(255, 255, 255, 0.95)',
              border: isPanelOpen ? '1px solid #3B82F6' : '1px solid #d0d5e0',
              borderRadius: 24,
              color: isPanelOpen ? 'white' : simulateBtnHovered ? '#333' : '#666',
              cursor: 'pointer',
              boxShadow: isPanelOpen ? '0 2px 8px rgba(59, 130, 246, 0.4)' : '0 2px 12px rgba(0, 0, 0, 0.1)',
              backdropFilter: 'blur(8px)',
              transition: 'background 0.2s ease, color 0.2s ease, box-shadow 0.2s ease'
            }}
          >
            <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
              <rect x="4" y="4" width="16" height="16" rx="2" />
              <rect x="9" y="9" width="6" height="6" />
              <line x1="9" y1="1" x2="9" y2="4" />
              <line x1="15" y1="1" x2="15" y2="4" />
              <line x1="9" y1="20" x2="9" y2="23" />
              <line x1="15" y1="20" x2="15" y2="23" />
              <line x1="20" y1="9" x2="23" y2="9" />
              <line x1="20" y1="15" x2="23" y2="15" />
              <line x1="1" y1="9" x2="4" y2="9" />
              <line x1="1" y1="15" x2="4" y2="15" />
            </svg>
          </button>
        </div>
        )}
      </div>
      </SidebarDrawer>

      {/* Bottom buttons — rendered outside drawer on mobile so they stay visible */}
      {viewport.isBelow(768) && (
        <div style={{
          position: 'fixed',
          bottom: 10,
          left: 10,
          display: 'flex',
          gap: 8,
          zIndex: 100,
          pointerEvents: 'auto',
        }}>
          <button
            onClick={() => {
              if (dqMinimized) { setDqMinimized(false) }
              else { setDataQualityOpen(!dataQualityOpen) }
            }}
            title="Data Quality"
            style={{
              width: 48,
              height: 48,
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center',
              background: dataQualityOpen ? '#10B981' : 'rgba(255, 255, 255, 0.95)',
              border: dataQualityOpen ? '1px solid #10B981' : '1px solid #d0d5e0',
              borderRadius: 24,
              color: dataQualityOpen ? 'white' : '#666',
              cursor: 'pointer',
              boxShadow: dataQualityOpen ? '0 2px 8px rgba(16, 185, 129, 0.4)' : '0 2px 12px rgba(0, 0, 0, 0.1)',
              backdropFilter: 'blur(8px)',
              transition: 'background 0.2s ease, color 0.2s ease, box-shadow 0.2s ease',
            }}
          >
            <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
              <path d="M9 3h6v5l4 9a2 2 0 0 1-1.8 2.9H6.8A2 2 0 0 1 5 17l4-9V3z" />
              <line x1="9" y1="3" x2="15" y2="3" />
              <path d="M8 14h8" />
            </svg>
          </button>
          <button
            onClick={() => {
              if (simMinimized) { setSimMinimized(false) }
              else if (isPanelOpen) { setSimMinimized(true) }
              else { openPanel(); setSimMinimized(false) }
            }}
            title="Simulate"
            style={{
              width: 48,
              height: 48,
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center',
              background: isPanelOpen ? '#3B82F6' : 'rgba(255, 255, 255, 0.95)',
              border: isPanelOpen ? '1px solid #3B82F6' : '1px solid #d0d5e0',
              borderRadius: 24,
              color: isPanelOpen ? 'white' : '#666',
              cursor: 'pointer',
              boxShadow: isPanelOpen ? '0 2px 8px rgba(59, 130, 246, 0.4)' : '0 2px 12px rgba(0, 0, 0, 0.1)',
              backdropFilter: 'blur(8px)',
              transition: 'background 0.2s ease, color 0.2s ease, box-shadow 0.2s ease',
            }}
          >
            <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
              <rect x="4" y="4" width="16" height="16" rx="2" />
              <rect x="9" y="9" width="6" height="6" />
              <line x1="9" y1="1" x2="9" y2="4" />
              <line x1="15" y1="1" x2="15" y2="4" />
              <line x1="9" y1="20" x2="9" y2="23" />
              <line x1="15" y1="20" x2="15" y2="23" />
              <line x1="20" y1="9" x2="23" y2="9" />
              <line x1="20" y1="15" x2="23" y2="15" />
              <line x1="1" y1="9" x2="4" y2="9" />
              <line x1="1" y1="15" x2="4" y2="15" />
            </svg>
          </button>
        </div>
      )}

      {/* Data Quality Panel */}
      {!dqMinimized && (
      <DataQualityPanel
        isOpen={dataQualityOpen}
        onClose={() => setDataQualityOpen(false)}
        onMinimize={() => setDqMinimized(true)}
        edges={(() => {
          // Get current year from the effective timeline (historicalTimeline has filtered years)
          const year = historicalTimeline?.years?.[currentYearIndex]
            ?? temporalShapTimeline?.years?.[currentYearIndex]
          if (year && temporalEdgesCacheRef.current.has(year)) {
            return temporalEdgesCacheRef.current.get(year)
          }
          // Fallback to country graph edges
          return countryGraph?.edges
        })()}
        targetIds={localViewTargets}
        nodeById={nodeByIdMap}
        isLocalView={viewMode === 'local' || viewMode === 'split'}
      />
      )}

      {/* Minimal loading spinner - centered on QoL node, with delay to avoid flash */}
      <LoadingSpinner
        show={loading || shapTimelineLoading || timelineLoading || countryLoading}
        delay={100}
        minDisplay={300}
        posRef={qolNodePositionRef}
        elRef={spinnerElRef}
      />

      {/* Desktop recommendation banner (mobile only) */}
      <DesktopBanner show={viewport.isBelow(768) && !tutorialActive} />

      {/* Error State */}
      {error && (
        <div className="loading-screen">
          <div style={{ fontSize: 48, marginBottom: 16 }}>⚠️</div>
          <div style={{ color: '#e53935', fontSize: 16, fontWeight: 'bold' }}>Failed to load data</div>
          <div style={{ color: '#666', fontSize: 13, marginTop: 8 }}>{error}</div>
        </div>
      )}

      {/* View Tabs - Top right */}
      <div
        style={{
          position: 'absolute',
          top: 16,
          right: 10,
          display: 'flex',
          gap: 8,
          zIndex: 100
        }}
      >
        <ViewTabs
          activeView={viewMode}
          onViewChange={setViewMode}
          localTargetCount={localViewTargets.length}
          onReset={resetView}
          onClear={clearWorkingContext}
          canClear={
            localViewTargets.length > 0
            || temporalResults !== null
            || highlightedPath.size > 0
            || highlightedTarget !== null
            || pinnedPaths.size > 0
          }
          onShare={shareCurrentState}
          onTutorialRestart={() => tutorialCompRef.current?.restart()}
          simMode={localViewSimMode}
          compact={viewport.isBelow(1200)}
          hideSplit={viewport.isBelow(1024)}
          isMobileLayout={viewport.isBelow(768)}
        />
      </div>

      {/* Strata Tabs - Center top, available in all views when non-country/region specific */}
      {!selectedCountry && !selectedRegion && (
        <div
          style={viewport.isBelow(768) ? {
            position: 'absolute',
            top: 16,
            left: 10,
            zIndex: 100,
          } : {
            position: 'absolute',
            top: 4,
            left: '50%',
            transform: 'translateX(-50%)',
            zIndex: 100,
          }}
        >
          <StrataTabs
            activeStratum={selectedStratum}
            onStratumChange={setStratum}
            compact={viewport.isBelow(1024) || viewport.isBelow(1200)}
          />
        </div>
      )}

      {/* Views Container - handles split view layout */}
      <main
        id="main-content"
        className="split-container"
        style={{
          display: 'flex',
          width: '100%',
          height: '100%',
          position: 'absolute',
          top: 0,
          left: 0,
          opacity: mapForeground ? 0.08 : 1,
          transition: 'opacity 0.5s cubic-bezier(0.4, 0, 0.2, 1)',
          pointerEvents: mapForeground ? 'none' : 'auto',
          willChange: 'opacity'
        }}
      >
        {/* Global View */}
        <div
          style={{
            width: viewMode === 'split' ? `${splitRatio * 100}%` : '100%',
            height: '100%',
            display: viewMode === 'local' ? 'none' : 'block',
            position: 'relative',
            flexShrink: 0
          }}
        >
          <p id={GRAPH_NAV_INSTRUCTIONS_ID} className="sr-only">
            In global graph view, tab to a node, use arrow keys to move between sibling nodes, press Enter or Space to expand or collapse, and press Escape to move to the parent node.
          </p>
          <svg
            ref={svgRef}
            role="img"
            aria-label={`Causal graph visualization for ${selectedCountry || (selectedRegion ? REGION_DISPLAY_NAMES[selectedRegion] : selectedStratum)}`}
            aria-describedby={GRAPH_NAV_INSTRUCTIONS_ID}
            style={{
              width: '100%',
              height: '100%',
              willChange: 'transform'
            }}
          />
        </div>

        {/* Draggable Divider */}
        {viewMode === 'split' && (
          <div
            onMouseDown={handleDividerMouseDown}
            style={{
              width: 6,
              height: '100%',
              background: '#d0d5e0',
              cursor: 'col-resize',
              flexShrink: 0,
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center',
              zIndex: 60
            }}
            onMouseEnter={(e) => e.currentTarget.style.background = '#bbb'}
            onMouseLeave={(e) => e.currentTarget.style.background = '#d0d5e0'}
          >
            <div style={{
              width: 2,
              height: 40,
              background: '#999',
              borderRadius: 1
            }} />
          </div>
        )}

        {/* Local View */}
        <div
          style={{
            width: viewMode === 'split' ? `${(1 - splitRatio) * 100}%` : '100%',
            height: '100%',
            display: viewMode === 'global' ? 'none' : 'block',
            position: 'relative',
            flexShrink: 0
          }}
        >
          {(viewMode === 'local' || viewMode === 'split') && rawData && (
            <LocalView
              targetIds={localViewTargets}
              allEdges={effectiveEdges}
              nodeById={nodeByIdMap}
              domainColors={DOMAIN_COLORS}
              onRemoveTarget={removeFromLocalView}
              onClearTargets={clearWorkingContext}
              onSwitchToGlobal={() => setViewMode('global')}
              onNavigateToNode={(nodeId) => {
                // Add clicked node as new target
                addToLocalView(nodeId)
              }}
              onShowInGlobal={showInGlobalView}
              onDrillDown={drillDownTarget}
              onDrillUp={drillUpTarget}
              canDrillUp={drillDownHistory !== null}
              showGlow={true}
              betaThreshold={localViewBetaThreshold}
              onBetaThresholdChange={setLocalViewBetaThreshold}
              inputDepth={localViewInputDepth}
              outputDepth={localViewOutputDepth}
              onInputDepthChange={setLocalViewInputDepth}
              onOutputDepthChange={setLocalViewOutputDepth}
              onResetLocalView={(resetFn) => { localViewResetRef.current = resetFn }}
              ciCache={historicalTimeline?.years[currentYearIndex] ? precomputedCICache.get(historicalTimeline.years[currentYearIndex]) : undefined}
              currentYear={historicalTimeline?.years[currentYearIndex]}
              simMode={localViewSimMode}
              simPlaybackActive={playbackMode === 'simulation' && isPlaying}
              simEffects={simLocalEffects}
              simData={simLocalViewData}
            />
          )}
        </div>
      </main>

      {/* Hover tooltip panel - always rendered for smooth transitions */}
      {(() => {
        // Use current hovered node or cached node for fade-out
        const displayNode = hoveredNode || tooltipNodeRef.current
        const isVisible = hoveredNode !== null

        if (!displayNode || !layoutValues || !viewportLayoutRef.current) return null

        // Get SHAP importance from temporal data (use precomputed cache)
        const nodeId = String(displayNode.id)
        const currentYear = historicalTimeline?.years[currentYearIndex]
        const yearShapCache = currentYear ? precomputedShapCache.get(currentYear) : null
        const shapValue = yearShapCache?.get(nodeId) ?? lastValidShapRef.current.get(nodeId)

        // Compute ring rank using cached SHAP values
        const ringNodes = allNodes.filter(n => n.ring === displayNode.ring)
        const getNodeShap = (n: ExpandableNode) => {
          const raw = yearShapCache?.get(String(n.id)) ?? lastValidShapRef.current.get(String(n.id)) ?? n.importance ?? 0
          return Math.max(0, Number.isFinite(raw) ? raw : 0)
        }
        const sortedRing = ringNodes.map(getNodeShap).sort((a, b) => b - a)
        const ringRank = sortedRing.findIndex(imp => imp <= (shapValue ?? 0)) + 1

        // Build breadcrumb path (file-path style)
        const buildBreadcrumbPath = (): string[] => {
          const path: string[] = []
          let current = breadcrumbNodeMap.get(nodeId)
          while (current) {
            path.unshift(current.label)
            if (current.parentId) {
              current = breadcrumbNodeMap.get(current.parentId)
            } else {
              break
            }
          }
          return path
        }
        const breadcrumbPath = buildBreadcrumbPath()

        return (
          <div style={{
            position: window.innerWidth < BREAKPOINTS.TABLET ? 'fixed' : 'absolute',
            bottom: window.innerWidth < BREAKPOINTS.TABLET ? 60 : 20,
            left: '50%', transform: 'translateX(-50%)',
            background: 'white', padding: '10px 14px', borderRadius: 8,
            boxShadow: '0 4px 12px rgba(0,0,0,0.15)', minWidth: 220,
            maxWidth: window.innerWidth < BREAKPOINTS.TABLET ? 'calc(100% - 32px)' : 420,
            ...(window.innerWidth < BREAKPOINTS.TABLET ? { maxHeight: 'calc(100vh - 130px)', overflowY: 'auto' as const } : {}),
            zIndex: 1100,
            pointerEvents: 'none',
            opacity: isVisible ? 1 : 0,
            transition: 'opacity 0.2s ease'
          }}>
            {/* Breadcrumb path (file-path style) */}
            {breadcrumbPath.length > 1 && (
              <div style={{ fontSize: 10, color: '#767676', marginBottom: 6, fontFamily: 'monospace' }}>
                {breadcrumbPath.slice(0, -1).join(' / ')}
              </div>
            )}

            {/* Node name */}
            <div style={{ fontWeight: 600, fontSize: 13, marginBottom: 6 }}>{displayNode.label}</div>

            {/* QoL score for ring 0 (country, region mean, stratum mean, or global mean) */}
            {displayNode.ring === 0 && qolNodeScoreForTooltip != null && (() => {
              const decimals = playbackMode === 'simulation' ? 2 : 1
              const label = selectedCountry
                ? selectedCountry
                : selectedRegion
                  ? `${REGION_DISPLAY_NAMES[selectedRegion] ?? selectedRegion} mean`
                  : selectedStratum !== 'unified'
                    ? `${selectedStratum} mean`
                    : 'global mean'
              return (
                <div style={{ fontSize: 12, color: '#333', marginBottom: 6, fontWeight: 500 }}>
                  QoL: {(qolNodeScoreForTooltip * 10).toFixed(decimals)}/10 ({label}, {mapCurrentYear})
                </div>
              )
            })()}

            {/* QoL sim delta for ring 0 during simulation */}
            {displayNode.ring === 0 && temporalResults?.qol_timeline && (() => {
              const simYear = String(temporalResults.base_year + currentYearIndex)
              const qd = temporalResults.qol_timeline[simYear]
              if (!qd) return null
              const color = qd.delta >= 0 ? '#39FF14' : '#FF1744'
              const sign = qd.delta >= 0 ? '+' : ''
              return (
                <div style={{ fontSize: 11, padding: '4px 8px', background: '#1a1a2e', borderRadius: 4, borderLeft: `3px solid ${color}`, marginBottom: 6 }}>
                  <div style={{ color, fontWeight: 600 }}>{(qd.simulated * 10).toFixed(1)}/10 ({sign}{(qd.delta * 10).toFixed(2)})</div>
                  <div style={{ color: '#aaa', fontSize: 10 }}>from {(qd.baseline * 10).toFixed(1)}/10</div>
                </div>
              )
            })()}

            {/* Badge row: ring + domain */}
            <div style={{ display: 'flex', gap: 6, flexWrap: 'wrap', marginBottom: 6 }}>
              <span style={{ padding: '2px 6px', borderRadius: 4, backgroundColor: '#e2e6ee', fontSize: 10 }}>
                {ringConfigs[displayNode.ring]?.label || `Ring ${displayNode.ring}`}
              </span>
              {displayNode.semanticPath.domain && (
                <span style={{ padding: '2px 6px', borderRadius: 4, backgroundColor: DOMAIN_COLORS[displayNode.semanticPath.domain] || '#9E9E9E', color: 'white', fontSize: 10 }}>
                  {displayNode.semanticPath.domain}
                </span>
              )}
            </div>

            {/* SHAP importance + rank */}
            <div style={{ fontSize: 11, color: '#444', display: 'flex', gap: 12 }}>
              {shapValue !== undefined && (
                <span><strong>SHAP:</strong> {(shapValue * 100).toFixed(1)}%</span>
              )}
              {ringNodes.length > 1 && (
                <span style={{ color: '#666' }}>#{ringRank} of {ringNodes.length}</span>
              )}
              {currentYear && (
                <span style={{ color: '#767676' }}>{currentYear}</span>
              )}
            </div>

            {/* Simulation effect (visible during sim state: playback, pause, or after finish) */}
            {temporalResults && isPanelOpen && (() => {
              const eff = aggregateEffects.get(String(displayNode.id))
              if (!eff) return null
              const color = eff.pct >= 0 ? '#39FF14' : '#FF1744'
              const simYear = temporalResults.base_year + currentYearIndex
              return (
                <div style={{
                  fontSize: 11, marginTop: 6, padding: '4px 8px',
                  background: '#1a1a2e', borderRadius: 4,
                  borderLeft: `3px solid ${color}`
                }}>
                  <div style={{ fontWeight: 600, color, fontSize: 13 }}>
                    {eff.pct >= 0 ? '+' : ''}{Math.abs(eff.pct) >= 10 ? Math.round(eff.pct) : eff.pct.toFixed(2)}% simulated
                  </div>
                  <div style={{ color: '#aaa', fontSize: 10, marginTop: 2 }}>
                    Year {simYear}
                    {!eff.isLeaf && eff.coverage < 1 && (
                      <span> · {Math.round(eff.coverage * 100)}% of children affected</span>
                    )}
                  </div>
                </div>
              )
            })()}

            {/* Node description */}
            {displayNode.description && (
              <div style={{
                fontSize: 11,
                color: '#555',
                marginTop: 8,
                lineHeight: 1.4,
                maxHeight: 60,
                overflow: 'hidden',
                textOverflow: 'ellipsis'
              }}>
                {displayNode.description}
              </div>
            )}

            {/* Expand hint */}
            {displayNode.hasChildren && (
              <div style={{ fontSize: 10, color: '#767676', marginTop: 4 }}>
                {expandedNodes.has(displayNode.id) ? 'Click to collapse' : `Click to expand (${displayNode.childIds.length})`}
              </div>
            )}
          </div>
        )
      })()}

      {/* Simulation Panel - Right sidebar */}
      {!simMinimized && (
        <SimulationPanel onMinimize={() => setSimMinimized(true)} />
      )}

      {/* Timeline Player - Bottom center */}
      <TimelinePlayer
        edgesLoading={temporalEdgesLoading}
        isLocalView={viewMode === 'local' || viewMode === 'split'}
      />

      {/* Tutorial overlay — auto-launches on first visit */}
      <Tutorial ref={tutorialCompRef} appRef={tutorialRef} onActiveChange={setTutorialActive} />
    </div>
  )
}

export default App
