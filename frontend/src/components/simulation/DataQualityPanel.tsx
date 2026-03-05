/**
 * DataQualityPanel - Shows data quality for country, unified, or stratified views
 *
 * Features:
 * - Data coverage percentage
 * - Observed vs imputed data breakdown
 * - Confidence level (high/medium/low)
 * - Mini timeline with color-coded data quality (complete/partial/sparse)
 * - Income transitions history (country mode only)
 * - Stratum distribution pie chart with country lists (unified/stratified only)
 */

import { useState, useEffect, useMemo, useCallback, useRef } from 'react'
import { useSimulationStore } from '../../stores/simulationStore'
import { simulationAPI } from '../../services/api'
import { debug } from '../../utils/debug'
import { DATA_YEAR_MAX, DATA_YEAR_MIN } from '../../constants/time'
import { PANEL_EXIT_MS } from '../../constants/animation'
import { usePresence } from '../../hooks/usePresence'
import { useResponsive } from '../../hooks/useResponsive'
import type {
  CountryDataQuality,
  YearDataQuality,
  UnifiedDataQuality,
  StratifiedDataQuality,
  AggregatedYearQuality,
  IncomeStratum,
  StratumDistribution,
  StratumCountryInfo,
  CountryGraphEdge
} from '../../services/api'
import type { RawNodeV21 } from '../../types'

interface DataQualityPanelProps {
  isOpen: boolean
  onClose: () => void
  /** Called on mobile when user taps chevron to minimize (hide panel, keep button colored) */
  onMinimize?: () => void
  /** Edges for CI Stats tab (optional, enables CI Stats in Local View) */
  edges?: CountryGraphEdge[]
  /** Target node IDs for Local View (optional) */
  targetIds?: string[]
  /** Node lookup map for displaying node names */
  nodeById?: Map<string, RawNodeV21>
  /** Whether we're in local view mode */
  isLocalView?: boolean
}

const DQ_MAX_WIDTH = 360
const DQ_HEADER_HEIGHT = 44

// Default position (bottom-left, above PlayBar)
const DEFAULT_POSITION = { x: 10, y: window.innerHeight - 70 - 450 }

// View mode types
type ViewMode = 'country' | 'unified' | 'stratified'

// Page types within the panel
type PanelPage = 'quality' | 'distribution' | 'ci-stats'

interface CountryQualityData extends CountryDataQuality {
  viewMode: 'country'
  transitions: Array<{
    year: number
    from: string
    to: string
    gni_at_transition: number | null
  }>
}

interface UnifiedQualityData extends UnifiedDataQuality {
  viewMode: 'unified'
}

interface StratifiedQualityData extends StratifiedDataQuality {
  viewMode: 'stratified'
}

type QualityData = CountryQualityData | UnifiedQualityData | StratifiedQualityData

// Year range for the mini timeline
const TIMELINE_START = DATA_YEAR_MIN
const TIMELINE_END = DATA_YEAR_MAX

const isAbortError = (error: unknown): boolean => (
  (error instanceof DOMException && error.name === 'AbortError') ||
  (error instanceof Error && error.name === 'AbortError')
)

// Stratum display names and colors
const STRATUM_CONFIG: Record<IncomeStratum, { label: string; color: string; darkColor: string }> = {
  developing: { label: 'Developing', color: '#EF5350', darkColor: '#C62828' },
  emerging: { label: 'Emerging', color: '#FFA726', darkColor: '#EF6C00' },
  advanced: { label: 'Advanced', color: '#66BB6A', darkColor: '#2E7D32' }
}

export function DataQualityPanel({
  isOpen,
  onClose,
  onMinimize,
  edges,
  targetIds,
  nodeById,
  isLocalView
}: DataQualityPanelProps) {
  const { isMounted, isVisible } = usePresence(isOpen, PANEL_EXIT_MS)
  const { selectedCountry, selectedStratum, historicalTimeline, currentYearIndex } = useSimulationStore()
  const { isMobileLayout } = useResponsive()

  // Collapse state (local, not persisted)
  const [isCollapsed, setIsCollapsed] = useState(false)

  // Compute actual year from timeline
  const timelineYear = historicalTimeline?.years?.[currentYearIndex] ?? DATA_YEAR_MAX
  const [qualityData, setQualityData] = useState<QualityData | null>(null)
  const [loading, setLoading] = useState(false)
  const [distributionLoading, setDistributionLoading] = useState(false)
  const [activePage, setActivePage] = useState<PanelPage>('quality')
  const [expandedStratum, setExpandedStratum] = useState<IncomeStratum | null>(null)

  // Cache for all years' distribution data (for smooth timeline playback)
  const distributionCache = useRef<Map<number, StratumDistribution>>(new Map())
  const [distributionCacheVersion, setDistributionCacheVersion] = useState(0)
  const qualityRequestIdRef = useRef(0)
  const distributionRequestIdRef = useRef(0)

  // Get current distribution from cache (re-evaluates when cache version changes)
  const distributionData = useMemo(() => {
    // Access cache version to ensure re-render when cache updates
    if (distributionCacheVersion >= 0) {
      return distributionCache.current.get(timelineYear) ?? null
    }
    return null
  }, [timelineYear, distributionCacheVersion])

  // Drag state
  const [position, setPosition] = useState(DEFAULT_POSITION)
  const [isDragging, setIsDragging] = useState(false)
  const dragOffset = useRef({ x: 0, y: 0 })
  const panelRef = useRef<HTMLDivElement>(null)

  // Reset position when panel opens
  useEffect(() => {
    if (isOpen) {
      setPosition({ x: 10, y: window.innerHeight - 70 - 450 })
    }
  }, [isOpen])

  // Focus management: move focus into panel on open, restore on close
  const triggerRef = useRef<Element | null>(null)
  useEffect(() => {
    if (isOpen) {
      triggerRef.current = document.activeElement
      requestAnimationFrame(() => {
        const first = panelRef.current?.querySelector<HTMLElement>('button, input, [tabindex="0"]')
        first?.focus()
      })
    } else if (triggerRef.current instanceof HTMLElement) {
      triggerRef.current.focus()
      triggerRef.current = null
    }
  }, [isOpen])

  // Focus trap + Escape to close
  useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
      if (!isOpen || !panelRef.current) return

      if (e.key === 'Escape') {
        onClose()
        return
      }

      if (e.key === 'Tab') {
        const focusable = panelRef.current.querySelectorAll<HTMLElement>(
          'input:not([disabled]), button:not([disabled]), select:not([disabled]), textarea:not([disabled]), [tabindex="0"]'
        )
        if (focusable.length === 0) return
        const first = focusable[0]
        const last = focusable[focusable.length - 1]

        if (e.shiftKey && document.activeElement === first) {
          e.preventDefault()
          last.focus()
        } else if (!e.shiftKey && document.activeElement === last) {
          e.preventDefault()
          first.focus()
        }
      }
    }
    document.addEventListener('keydown', handleKeyDown)
    return () => document.removeEventListener('keydown', handleKeyDown)
  }, [isOpen, onClose])

  // Drag handlers
  const handleMouseDown = useCallback((e: React.MouseEvent) => {
    if (isMobileLayout) return
    // Only drag from header, not close button
    if ((e.target as HTMLElement).closest('button')) return

    setIsDragging(true)
    dragOffset.current = {
      x: e.clientX - position.x,
      y: e.clientY - position.y
    }
    e.preventDefault()
  }, [position, isMobileLayout])

  const handleMouseMove = useCallback((e: MouseEvent) => {
    if (!isDragging) return

    const newX = e.clientX - dragOffset.current.x
    const newY = e.clientY - dragOffset.current.y

    // Constrain to viewport
    const panelWidth = panelRef.current?.offsetWidth || 340
    const panelHeight = panelRef.current?.offsetHeight || 400

    setPosition({
      x: Math.max(0, Math.min(newX, window.innerWidth - panelWidth)),
      y: Math.max(0, Math.min(newY, window.innerHeight - panelHeight))
    })
  }, [isDragging])

  const handleMouseUp = useCallback(() => {
    setIsDragging(false)
  }, [])

  // Add/remove global mouse listeners for drag
  useEffect(() => {
    if (isDragging) {
      window.addEventListener('mousemove', handleMouseMove)
      window.addEventListener('mouseup', handleMouseUp)
      return () => {
        window.removeEventListener('mousemove', handleMouseMove)
        window.removeEventListener('mouseup', handleMouseUp)
      }
    }
  }, [isDragging, handleMouseMove, handleMouseUp])

  // Determine view mode
  const viewMode: ViewMode = selectedCountry ? 'country' : (selectedStratum === 'unified' ? 'unified' : 'stratified')

  // Show distribution tab only for unified/stratified views
  const showDistributionTab = viewMode !== 'country'

  // Show CI Stats tab when in local view with edges
  const showCIStatsTab = isLocalView && edges && edges.length > 0

  // Show tabs if either distribution or CI Stats tabs are available
  const showTabs = showDistributionTab || showCIStatsTab

  // For country mode without CI Stats, always show quality page
  // This guards against the race condition where effect hasn't run yet after view switch
  const effectiveActivePage = (() => {
    if (activePage === 'ci-stats' && showCIStatsTab) return 'ci-stats'
    if (viewMode === 'country' && !showCIStatsTab) return 'quality'
    if (activePage === 'distribution' && !showDistributionTab) return 'quality'
    return activePage
  })()

  // Track previous view mode to detect switches
  const prevViewModeRef = useRef<ViewMode>(viewMode)

  // Reset state when view mode changes
  useEffect(() => {
    if (prevViewModeRef.current !== viewMode) {
      // View mode changed - reset to quality page and clear data
      setActivePage('quality')
      setQualityData(null)
      setExpandedStratum(null)
      distributionCache.current.clear()
      setDistributionCacheVersion(0)
      prevViewModeRef.current = viewMode
    }
  }, [viewMode])

  // Fetch data quality based on view mode
  useEffect(() => {
    if (!isOpen) return

    const requestId = ++qualityRequestIdRef.current
    const controller = new AbortController()

    // Clear previous data and start loading
    setQualityData(null)
    setLoading(true)

    const fetchDataQuality = async () => {
      try {
        if (selectedCountry) {
          // Country mode — fetch data quality and transitions in parallel
          const [data, transitionsResult] = await Promise.all([
            simulationAPI.getCountryDataQuality(selectedCountry, controller.signal),
            simulationAPI.getCountryTransitions(selectedCountry, controller.signal)
              .catch((err: unknown) => { if (isAbortError(err)) throw err; return null; })
          ])

          const transitions: CountryQualityData['transitions'] =
            transitionsResult?.has_transitions ? transitionsResult.transitions || [] : []

          // Only set data if we're still in country mode
          if (selectedCountry && requestId === qualityRequestIdRef.current && !controller.signal.aborted) {
            setQualityData({
              ...data,
              viewMode: 'country',
              transitions
            })
          }
        } else if (selectedStratum === 'unified') {
          // Unified mode
          const data = await simulationAPI.getUnifiedDataQuality(controller.signal)
          // Only set data if we're still in unified mode
          if (!selectedCountry && selectedStratum === 'unified' && requestId === qualityRequestIdRef.current && !controller.signal.aborted) {
            setQualityData({
              ...data,
              viewMode: 'unified'
            })
          }
        } else {
          // Stratified mode
          const stratum = selectedStratum as IncomeStratum
          const data = await simulationAPI.getStratifiedDataQuality(stratum, timelineYear, controller.signal)
          // Only set data if we're still in the same stratified mode
          if (!selectedCountry && selectedStratum === stratum && requestId === qualityRequestIdRef.current && !controller.signal.aborted) {
            setQualityData({
              ...data,
              viewMode: 'stratified'
            })
          }
        }
      } catch (error) {
        if (!isAbortError(error)) {
          debug.error('data-quality', 'Failed to fetch data quality:', error)
          setQualityData(null)
        }
      } finally {
        if (requestId === qualityRequestIdRef.current && !controller.signal.aborted) {
          setLoading(false)
        }
      }
    }

    fetchDataQuality()
    return () => controller.abort()
  }, [selectedCountry, selectedStratum, isOpen, timelineYear])

  // Pre-fetch all years' distribution data when distribution tab is opened
  // This enables smooth timeline playback without per-year API calls
  useEffect(() => {
    if (!isOpen || viewMode === 'country' || activePage !== 'distribution') {
      return
    }

    const requestId = ++distributionRequestIdRef.current
    const controller = new AbortController()

    // Skip if cache is already populated
    if (distributionCache.current.size > 0) {
      setDistributionCacheVersion(v => v + 1)
      return
    }

    const fetchAllDistributions = async () => {
      setDistributionLoading(true)

      try {
        // Fetch all years in parallel (1990-2024)
        const years = Array.from(
          { length: TIMELINE_END - TIMELINE_START + 1 },
          (_, i) => TIMELINE_START + i
        )
        const batchSize = 10  // Fetch 10 years at a time to avoid overwhelming the API

        for (let i = 0; i < years.length; i += batchSize) {
          if (controller.signal.aborted || requestId !== distributionRequestIdRef.current) {
            return
          }
          const batch = years.slice(i, i + batchSize)
          const results = await Promise.all(
            batch.map(year =>
              simulationAPI.getStratumDistribution(year, controller.signal)
                .catch(() => null)  // Gracefully handle missing years
            )
          )

          // Add to cache
          results.forEach((data, idx) => {
            if (data) {
              distributionCache.current.set(batch[idx], data)
            }
          })

          // Trigger re-render after each batch for progressive loading
          if (requestId === distributionRequestIdRef.current && !controller.signal.aborted) {
            setDistributionCacheVersion(v => v + 1)
          }
        }
      } catch (error) {
        if (!isAbortError(error)) {
          debug.error('data-quality', 'Failed to fetch stratum distributions:', error)
        }
      } finally {
        if (requestId === distributionRequestIdRef.current && !controller.signal.aborted) {
          setDistributionLoading(false)
        }
      }
    }

    fetchAllDistributions()
    return () => controller.abort()
  }, [isOpen, viewMode, activePage])

  // Clear cache when panel closes
  useEffect(() => {
    if (!isOpen) {
      distributionCache.current.clear()
      setDistributionCacheVersion(0)
    }
  }, [isOpen])

  // Quality type for timeline cells
  type QualityLevel = 'complete' | 'partial' | 'sparse' | 'none'

  // Generate year cells for the mini timeline
  const timelineCells = useMemo(() => {
    const cells: Array<{
      year: number
      quality: QualityLevel
      yearData: YearDataQuality | AggregatedYearQuality | undefined
      transition?: { from: string; to: string }
    }> = []

    if (!qualityData) return cells

    const byYear = qualityData.by_year || {}
    const transitions = qualityData.viewMode === 'country' ? qualityData.transitions : []

    for (let year = TIMELINE_START; year <= TIMELINE_END; year++) {
      const yearKey = String(year)
      const yearData = byYear[yearKey]
      const transition = transitions.find((t: { year: number }) => t.year === year)

      cells.push({
        year,
        quality: (yearData?.quality || 'none') as QualityLevel,
        yearData,
        transition
      })
    }
    return cells
  }, [qualityData])

  // Calculate years with data
  const yearsWithData = useMemo(() => {
    if (!qualityData?.by_year) return 0
    return Object.keys(qualityData.by_year).length
  }, [qualityData])

  // Calculate year range
  const yearRange = useMemo(() => {
    if (!qualityData?.by_year) return { start: TIMELINE_START, end: TIMELINE_END }
    const years = Object.keys(qualityData.by_year).map(Number)
    return {
      start: Math.min(...years),
      end: Math.max(...years)
    }
  }, [qualityData])

  // Get display values based on view mode
  const getDisplayValues = () => {
    if (!qualityData) return null

    if (qualityData.viewMode === 'country') {
      return {
        title: qualityData.country,
        subtitle: null,
        coverage: qualityData.coverage_pct,
        observed: qualityData.observed_pct,
        imputed: qualityData.imputed_pct,
        confidence: qualityData.confidence,
        totalIndicators: qualityData.total_indicators,
        nCountries: null
      }
    } else if (qualityData.viewMode === 'unified') {
      return {
        title: 'Unified View',
        subtitle: `${qualityData.n_countries} countries pooled`,
        coverage: qualityData.avg_coverage_pct,
        observed: qualityData.avg_observed_pct,
        imputed: qualityData.avg_imputed_pct,
        confidence: qualityData.confidence,
        totalIndicators: qualityData.total_indicators,
        nCountries: qualityData.n_countries
      }
    } else {
      const stratumConfig = STRATUM_CONFIG[qualityData.stratum]
      return {
        title: `${stratumConfig.label} Economies`,
        subtitle: `${qualityData.n_countries} countries`,
        coverage: qualityData.avg_coverage_pct,
        observed: qualityData.avg_observed_pct,
        imputed: qualityData.avg_imputed_pct,
        confidence: qualityData.confidence,
        totalIndicators: qualityData.total_indicators,
        nCountries: qualityData.n_countries,
        stratumColor: stratumConfig.color
      }
    }
  }

  if (!isMounted) return null

  const displayValues = getDisplayValues()

  return (
    <div
      ref={panelRef}
      role="dialog"
      aria-modal={isMobileLayout ? 'true' : 'false'}
      aria-hidden={!isOpen}
      aria-label="Data quality"
      style={isMobileLayout ? {
        // Mobile: fullscreen overlay (above hamburger z-index 1051)
        position: 'fixed',
        top: 0,
        left: 0,
        right: 0,
        bottom: 0,
        background: 'white',
        borderRadius: 0,
        zIndex: 1100,
        overflow: 'hidden',
        display: 'flex',
        flexDirection: 'column',
        opacity: isVisible ? 1 : 0,
        transform: isVisible ? 'translateY(0)' : 'translateY(14px)',
        pointerEvents: isVisible ? 'auto' : 'none',
        transition: `opacity ${PANEL_EXIT_MS}ms ease, transform ${PANEL_EXIT_MS}ms ease`,
      } : {
        position: 'fixed',
        top: position.y,
        left: position.x,
        width: Math.min(DQ_MAX_WIDTH, window.innerWidth - 40),
        maxHeight: isCollapsed ? undefined : '80vh',
        background: 'white',
        borderRadius: 12,
        boxShadow: isDragging
          ? '0 8px 32px rgba(0,0,0,0.25)'
          : '0 4px 20px rgba(0,0,0,0.15)',
        zIndex: 1001,
        overflow: 'hidden',
        transition: isDragging
          ? 'none'
          : `opacity ${PANEL_EXIT_MS}ms ease, transform ${PANEL_EXIT_MS}ms ease, box-shadow 0.2s ease`,
        userSelect: isDragging ? 'none' : 'auto',
        display: 'flex',
        flexDirection: 'column',
        opacity: isVisible ? 1 : 0,
        transform: isVisible ? 'translateY(0)' : 'translateY(14px)',
        pointerEvents: isVisible ? 'auto' : 'none',
      }}
    >
      {/* Header - draggable (desktop) / tappable (mobile) */}
      <div
        onMouseDown={handleMouseDown}
        style={{
          padding: '12px 16px',
          borderBottom: isCollapsed ? 'none' : '1px solid #e2e6ee',
          display: 'flex',
          justifyContent: 'space-between',
          alignItems: 'center',
          background: '#f0f2f8',
          cursor: isMobileLayout ? 'default' : (isDragging ? 'grabbing' : 'grab'),
          flexShrink: 0,
          minHeight: DQ_HEADER_HEIGHT,
          minWidth: 0,
        }}
      >
        <div style={{ display: 'flex', alignItems: 'center', gap: 8, minWidth: 0, flex: 1 }}>
          <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="#666" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true" style={{ flexShrink: 0 }}>
            <path d="M9 3h6v5l4 9a2 2 0 0 1-1.8 2.9H6.8A2 2 0 0 1 5 17l4-9V3z" />
            <line x1="9" y1="3" x2="15" y2="3" />
            <path d="M8 14h8" />
          </svg>
          <span style={{ fontWeight: 600, fontSize: 13, color: '#333', flexShrink: 0 }}>Data Quality</span>
          {isCollapsed && activePage !== 'quality' && (
            <span style={{ fontSize: 11, color: '#767676' }}>
              {activePage === 'distribution' ? '· Distribution' : '· CI Stats'}
            </span>
          )}
        </div>
        <div style={{ display: 'flex', alignItems: 'center', gap: 4, flexShrink: 0 }}>
          <button
            className="touch-target-44"
            onClick={(e) => { e.stopPropagation(); isMobileLayout && onMinimize ? onMinimize() : setIsCollapsed(prev => !prev) }}
            title={isMobileLayout ? 'Minimize panel' : (isCollapsed ? 'Expand panel' : 'Collapse panel')}
            aria-label={isMobileLayout ? 'Minimize data quality panel' : (isCollapsed ? 'Expand data quality panel' : 'Collapse data quality panel')}
            style={{
              background: 'none',
              border: 'none',
              color: '#767676',
              fontSize: 18,
              cursor: 'pointer',
              padding: '4px 6px',
              lineHeight: 1,
              transition: 'transform 0.2s ease',
              transform: isCollapsed ? 'rotate(-90deg)' : 'rotate(0deg)',
              display: 'flex',
              alignItems: 'center'
            }}
          >
            ▾
          </button>
          <button
              className="touch-target-44"
              onClick={onClose}
              aria-label="Close data quality panel"
              style={{
                background: 'none',
                border: 'none',
                cursor: 'pointer',
                padding: 4,
                display: 'flex',
                alignItems: 'center',
                color: '#767676'
              }}
            >
              <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                <line x1="18" y1="6" x2="6" y2="18" />
                <line x1="6" y1="6" x2="18" y2="18" />
              </svg>
            </button>
        </div>
      </div>

      <div style={{ display: isCollapsed ? 'none' : 'contents' }}>
      {/* Tab navigation */}
      {showTabs && (
        <div style={{
          display: 'flex',
          borderBottom: '1px solid #e2e6ee',
          background: '#f4f5fa',
          flexShrink: 0
        }}>
          <button
            onClick={() => setActivePage('quality')}
            style={{
              flex: 1,
              padding: '10px 12px',
              border: 'none',
              background: effectiveActivePage === 'quality' ? 'white' : 'transparent',
              borderBottom: effectiveActivePage === 'quality' ? '2px solid #3B82F6' : '2px solid transparent',
              cursor: 'pointer',
              fontSize: 12,
              fontWeight: effectiveActivePage === 'quality' ? 600 : 400,
              color: effectiveActivePage === 'quality' ? '#3B82F6' : '#666',
              transition: 'all 0.2s ease'
            }}
          >
            Overview
          </button>
          {showDistributionTab && (
            <button
              onClick={() => setActivePage('distribution')}
              style={{
                flex: 1,
                padding: '10px 12px',
                border: 'none',
                background: effectiveActivePage === 'distribution' ? 'white' : 'transparent',
                borderBottom: effectiveActivePage === 'distribution' ? '2px solid #3B82F6' : '2px solid transparent',
                cursor: 'pointer',
                fontSize: 12,
                fontWeight: effectiveActivePage === 'distribution' ? 600 : 400,
                color: effectiveActivePage === 'distribution' ? '#3B82F6' : '#666',
                transition: 'all 0.2s ease'
              }}
            >
              Distribution
            </button>
          )}
          {showCIStatsTab && (
            <button
              onClick={() => setActivePage('ci-stats')}
              style={{
                flex: 1,
                padding: '10px 12px',
                border: 'none',
                background: effectiveActivePage === 'ci-stats' ? 'white' : 'transparent',
                borderBottom: effectiveActivePage === 'ci-stats' ? '2px solid #3B82F6' : '2px solid transparent',
                cursor: 'pointer',
                fontSize: 12,
                fontWeight: effectiveActivePage === 'ci-stats' ? 600 : 400,
                color: effectiveActivePage === 'ci-stats' ? '#3B82F6' : '#666',
                transition: 'all 0.2s ease'
              }}
            >
              CI Stats
            </button>
          )}
        </div>
      )}

      {/* Content - scrollable */}
      <div style={{ padding: 16, overflowY: 'auto', flex: 1 }}>
        {/* Quality Overview Page */}
        {effectiveActivePage === 'quality' && (
          loading ? (
            <div style={{ display: 'flex', justifyContent: 'center', padding: 20 }}>
              <div style={{
                width: 24,
                height: 24,
                borderWidth: 2,
                borderStyle: 'solid',
                borderColor: '#d0d5e0',
                borderTopColor: '#666',
                borderRadius: '50%',
                animation: 'spin 0.8s linear infinite'
              }} />
            </div>
          ) : qualityData && displayValues ? (
            <>
              {/* Title with confidence badge */}
              <div style={{
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'space-between',
                marginBottom: 4
              }}>
                <div style={{
                  fontWeight: 600,
                  fontSize: 14,
                  color: viewMode === 'stratified' && 'stratumColor' in displayValues
                    ? displayValues.stratumColor
                    : '#333'
                }}>
                  {displayValues.title}
                </div>
                <ConfidenceBadge confidence={displayValues.confidence} />
              </div>

              {/* Subtitle */}
              {displayValues.subtitle && (
                <div style={{ fontSize: 11, color: '#767676', marginBottom: 12 }}>
                  {displayValues.subtitle}
                </div>
              )}
              {!displayValues.subtitle && <div style={{ marginBottom: 8 }} />}

              {/* Stats grid */}
              <div style={{
                display: 'grid',
                gridTemplateColumns: '1fr 1fr 1fr',
                gap: 8,
                marginBottom: 16
              }}>
                <StatBox
                  label={viewMode === 'country' ? 'Coverage' : 'Avg Coverage'}
                  value={`${displayValues.coverage.toFixed(0)}%`}
                  subtext={`${displayValues.totalIndicators.toLocaleString()} indicators`}
                  color="#3B82F6"
                />
                <StatBox
                  label={viewMode === 'country' ? 'Observed' : 'Avg Observed'}
                  value={`${displayValues.observed.toFixed(0)}%`}
                  subtext="Real data"
                  color="#10B981"
                />
                <StatBox
                  label={viewMode === 'country' ? 'Imputed' : 'Avg Imputed'}
                  value={`${displayValues.imputed.toFixed(0)}%`}
                  subtext="Estimated"
                  color="#F59E0B"
                />
              </div>

              {/* Sample size row */}
              <div style={{
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'space-between',
                padding: '8px 12px',
                background: '#f0f2f8',
                borderRadius: 8,
                marginBottom: 16,
                fontSize: 12
              }}>
                <span style={{ color: '#666' }}>
                  {viewMode === 'country' ? 'Sample Size' : 'Time Range'}
                </span>
                <span style={{ fontWeight: 600, color: '#333' }}>
                  {yearsWithData} years ({yearRange.start} - {yearRange.end})
                </span>
              </div>

              {/* Mini timeline */}
              <div style={{ marginBottom: 16 }}>
                <div style={{ fontSize: 11, color: '#666', marginBottom: 8, fontWeight: 500 }}>
                  Data Quality Timeline
                  {viewMode !== 'country' && (
                    <span style={{ fontWeight: 400, color: '#767676' }}> (avg across countries)</span>
                  )}
                </div>
                <div style={{
                  display: 'flex',
                  gap: 1,
                  padding: '8px 0'
                }}>
                  {timelineCells.map(cell => (
                    <TimelineCell
                      key={cell.year}
                      year={cell.year}
                      quality={cell.quality}
                      yearData={cell.yearData}
                      transition={cell.transition}
                      viewMode={viewMode}
                    />
                  ))}
                </div>
                {/* Legend */}
                <div style={{
                  display: 'flex',
                  gap: 12,
                  marginTop: 8,
                  fontSize: 10,
                  color: '#767676',
                  flexWrap: 'wrap'
                }}>
                  <div style={{ display: 'flex', alignItems: 'center', gap: 4 }}>
                    <div style={{ width: 8, height: 8, background: '#10B981', borderRadius: 1 }} />
                    <span>Complete (≥50%)</span>
                  </div>
                  <div style={{ display: 'flex', alignItems: 'center', gap: 4 }}>
                    <div style={{ width: 8, height: 8, background: '#F59E0B', borderRadius: 1 }} />
                    <span>Partial (≥25%)</span>
                  </div>
                  <div style={{ display: 'flex', alignItems: 'center', gap: 4 }}>
                    <div style={{ width: 8, height: 8, background: '#EF4444', borderRadius: 1 }} />
                    <span>Sparse (&lt;25%)</span>
                  </div>
                  <div style={{ display: 'flex', alignItems: 'center', gap: 4 }}>
                    <div style={{ width: 8, height: 8, background: '#d0d5e0', borderRadius: 1 }} />
                    <span>No data</span>
                  </div>
                </div>
              </div>

              {/* Transitions (country mode only) */}
              {viewMode === 'country' && qualityData.viewMode === 'country' && qualityData.transitions.length > 0 && (
                <div>
                  <div style={{ fontSize: 11, color: '#666', marginBottom: 8, fontWeight: 500 }}>
                    Income Transitions
                  </div>
                  <div style={{ display: 'flex', flexDirection: 'column', gap: 6 }}>
                    {qualityData.transitions.map((t, i) => (
                      <TransitionRow key={i} transition={t} />
                    ))}
                  </div>
                </div>
              )}
            </>
          ) : (
            <div style={{ color: '#767676', fontSize: 12, textAlign: 'center', padding: 20 }}>
              No data quality information available
            </div>
          )
        )}

        {/* Distribution Page (for unified/stratified views) */}
        {effectiveActivePage === 'distribution' && (
          distributionLoading ? (
            <div style={{ display: 'flex', justifyContent: 'center', padding: 20 }}>
              <div style={{
                width: 24,
                height: 24,
                borderWidth: 2,
                borderStyle: 'solid',
                borderColor: '#d0d5e0',
                borderTopColor: '#666',
                borderRadius: '50%',
                animation: 'spin 0.8s linear infinite'
              }} />
            </div>
          ) : distributionData ? (
            <>
              {/* Year indicator */}
              <div style={{
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'space-between',
                marginBottom: 16
              }}>
                <div style={{ fontWeight: 600, fontSize: 14, color: '#333' }}>
                  Global Distribution
                </div>
                <div style={{
                  padding: '4px 10px',
                  background: '#f0f0f0',
                  borderRadius: 12,
                  fontSize: 12,
                  fontWeight: 600,
                  color: '#666'
                }}>
                  {distributionData.year}
                </div>
              </div>

              {/* Pie Chart */}
              <PieChart
                distribution={distributionData.distribution}
                totalCountries={distributionData.total_countries}
              />

              {/* Thresholds info */}
              <div style={{
                display: 'flex',
                justifyContent: 'center',
                gap: 16,
                marginBottom: 16,
                fontSize: 10,
                color: '#767676'
              }}>
                <div>
                  Dev→Emerg: <strong>${distributionData.thresholds.developing_to_emerging.toLocaleString()}</strong>
                </div>
                <div>
                  Emerg→Adv: <strong>${distributionData.thresholds.emerging_to_advanced.toLocaleString()}</strong>
                </div>
              </div>

              {/* Country Lists */}
              <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
                {(['developing', 'emerging', 'advanced'] as IncomeStratum[]).map(stratum => (
                  <StratumCountryList
                    key={stratum}
                    stratum={stratum}
                    countries={distributionData.countries[stratum]}
                    isExpanded={expandedStratum === stratum}
                    onToggle={() => setExpandedStratum(expandedStratum === stratum ? null : stratum)}
                    thresholds={distributionData.thresholds}
                  />
                ))}
              </div>
            </>
          ) : (
            <div style={{ color: '#767676', fontSize: 12, textAlign: 'center', padding: 20 }}>
              No distribution data available
            </div>
          )
        )}

        {/* CI Stats Page (for Local View - target nodes) */}
        {effectiveActivePage === 'ci-stats' && edges && (
          <CIStatsContent
            edges={edges}
            targetIds={targetIds || []}
            nodeById={nodeById}
          />
        )}
      </div>
      </div>
    </div>
  )
}

// ============================================
// Sub-components
// ============================================

/**
 * CIStatsContent - Displays CI statistics for edges in Local View
 */
interface CIStatsContentProps {
  edges: CountryGraphEdge[]
  targetIds: string[]
  nodeById?: Map<string, RawNodeV21>
}

function CIStatsContent({ edges, targetIds, nodeById }: CIStatsContentProps) {
  // State for expanded target
  const [expandedTarget, setExpandedTarget] = useState<string | null>(null)

  // Get node name helper
  const getNodeName = (id: string) => {
    const node = nodeById?.get(id)
    return node?.label || id
  }

  // Filter edges related to targets
  const targetEdges = useMemo(() => {
    if (targetIds.length === 0) return edges
    const targetSet = new Set(targetIds)
    return edges.filter(e => targetSet.has(e.source) || targetSet.has(e.target))
  }, [edges, targetIds])

  // Group edges by target node
  const edgesByTarget = useMemo(() => {
    const grouped = new Map<string, CountryGraphEdge[]>()

    for (const targetId of targetIds) {
      const nodeEdges = edges.filter(e =>
        e.source === targetId || e.target === targetId
      )
      if (nodeEdges.length > 0) {
        grouped.set(targetId, nodeEdges)
      }
    }
    return grouped
  }, [edges, targetIds])

  // Compute summary statistics
  const summaryStats = useMemo(() => {
    if (targetEdges.length === 0) return null

    const rSquareds = targetEdges.filter(e => e.r_squared !== undefined).map(e => e.r_squared!)
    const pValues = targetEdges.filter(e => e.p_value !== undefined).map(e => e.p_value!)
    const nSamples = targetEdges.filter(e => e.n_samples !== undefined).map(e => e.n_samples!)
    const ciWidths = targetEdges.map(e => e.ci_upper - e.ci_lower)

    const avg = (arr: number[]) => arr.length > 0 ? arr.reduce((a, b) => a + b, 0) / arr.length : 0
    const significant = pValues.filter(p => p < 0.05).length

    return {
      edgeCount: targetEdges.length,
      avgRSquared: avg(rSquareds),
      avgCIWidth: avg(ciWidths),
      significantCount: significant,
      significantPct: pValues.length > 0 ? (significant / pValues.length) * 100 : 0,
      avgSamples: avg(nSamples)
    }
  }, [targetEdges])

  // Format number
  const formatNum = (n: number | undefined, decimals = 3): string => {
    if (n === undefined) return '-'
    if (Math.abs(n) < 0.001) return n.toExponential(2)
    return n.toFixed(decimals)
  }

  // Confidence color based on CI width
  const getCIColor = (ciWidth: number) => {
    if (ciWidth < 0.1) return '#10B981'
    if (ciWidth < 0.3) return '#F59E0B'
    return '#EF4444'
  }

  // Significance badge
  const getSigBadge = (pValue: number | undefined) => {
    if (pValue === undefined) return null
    if (pValue < 0.001) return { label: '***', color: '#10B981' }
    if (pValue < 0.01) return { label: '**', color: '#22C55E' }
    if (pValue < 0.05) return { label: '*', color: '#84CC16' }
    return { label: 'ns', color: '#9CA3AF' }
  }

  if (targetIds.length === 0) {
    return (
      <div style={{ color: '#767676', fontSize: 12, textAlign: 'center', padding: 20 }}>
        Select target nodes in Local View to see CI statistics
      </div>
    )
  }

  return (
    <div>
      {/* Summary */}
      {summaryStats && (
        <div style={{ marginBottom: 16 }}>
          <div style={{ fontWeight: 600, fontSize: 13, color: '#333', marginBottom: 8 }}>
            Summary <span style={{ color: '#767676', fontWeight: 400 }}>({summaryStats.edgeCount} edges)</span>
          </div>
          <div style={{
            display: 'grid',
            gridTemplateColumns: '1fr 1fr 1fr',
            gap: 6,
            fontSize: 11
          }}>
            <div style={{ background: '#f9fafb', padding: '6px 8px', borderRadius: 4 }}>
              <div style={{ color: '#767676', fontSize: 9 }}>Avg R²</div>
              <div style={{ fontWeight: 600 }}>{formatNum(summaryStats.avgRSquared)}</div>
            </div>
            <div style={{ background: '#f9fafb', padding: '6px 8px', borderRadius: 4 }}>
              <div style={{ color: '#767676', fontSize: 9 }}>Significant</div>
              <div style={{ fontWeight: 600 }}>{summaryStats.significantPct.toFixed(0)}%</div>
            </div>
            <div style={{ background: '#f9fafb', padding: '6px 8px', borderRadius: 4 }}>
              <div style={{ color: '#767676', fontSize: 9 }}>Avg Samples</div>
              <div style={{ fontWeight: 600 }}>{Math.round(summaryStats.avgSamples).toLocaleString()}</div>
            </div>
          </div>
        </div>
      )}

      {/* Target Nodes with their edges */}
      <div style={{ fontWeight: 600, fontSize: 13, color: '#333', marginBottom: 8 }}>
        Target Nodes
      </div>
      <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
        {targetIds.map(targetId => {
          const nodeEdges = edgesByTarget.get(targetId) || []
          const isExpanded = expandedTarget === targetId
          const incomingEdges = nodeEdges.filter(e => e.target === targetId)
          const outgoingEdges = nodeEdges.filter(e => e.source === targetId)

          return (
            <div
              key={targetId}
              style={{
                border: '1px solid #dce0ea',
                borderRadius: 6,
                overflow: 'hidden'
              }}
            >
              {/* Target header */}
              <button
                onClick={() => setExpandedTarget(isExpanded ? null : targetId)}
                style={{
                  width: '100%',
                  display: 'flex',
                  alignItems: 'center',
                  justifyContent: 'space-between',
                  padding: '8px 10px',
                  background: isExpanded ? '#e8f5f7' : '#f4f5fa',
                  border: 'none',
                  cursor: 'pointer',
                  textAlign: 'left'
                }}
              >
                <div style={{ flex: 1, minWidth: 0 }}>
                  <div style={{
                    fontWeight: 600,
                    fontSize: 12,
                    color: '#333',
                    overflow: 'hidden',
                    textOverflow: 'ellipsis',
                    whiteSpace: 'nowrap'
                  }}>
                    {getNodeName(targetId)}
                  </div>
                  <div style={{ fontSize: 10, color: '#767676' }}>
                    {incomingEdges.length} in · {outgoingEdges.length} out
                  </div>
                </div>
                <svg
                  width="14"
                  height="14"
                  viewBox="0 0 24 24"
                  fill="none"
                  stroke="#888"
                  strokeWidth="2"
                  style={{
                    transform: isExpanded ? 'rotate(180deg)' : 'rotate(0deg)',
                    transition: 'transform 0.2s ease'
                  }}
                >
                  <polyline points="6 9 12 15 18 9" />
                </svg>
              </button>

              {/* Expanded edge list */}
              {isExpanded && nodeEdges.length > 0 && (
                <div style={{ padding: '8px 10px', background: '#fff', maxHeight: 200, overflowY: 'auto' }}>
                  {nodeEdges.slice(0, 15).map((edge, idx) => {
                    const isIncoming = edge.target === targetId
                    const otherNode = isIncoming ? edge.source : edge.target
                    const ciWidth = edge.ci_upper - edge.ci_lower
                    const sig = getSigBadge(edge.p_value)

                    return (
                      <div
                        key={idx}
                        style={{
                          display: 'flex',
                          alignItems: 'center',
                          gap: 6,
                          padding: '4px 0',
                          borderBottom: idx < nodeEdges.length - 1 && idx < 14 ? '1px solid #f3f4f6' : 'none',
                          fontSize: 10
                        }}
                      >
                        <span style={{ color: isIncoming ? '#3B82F6' : '#10B981', fontWeight: 600 }}>
                          {isIncoming ? '←' : '→'}
                        </span>
                        <span style={{
                          flex: 1,
                          overflow: 'hidden',
                          textOverflow: 'ellipsis',
                          whiteSpace: 'nowrap',
                          color: '#555'
                        }}>
                          {getNodeName(otherNode)}
                        </span>
                        <span style={{ fontWeight: 600, color: '#333' }}>
                          β={formatNum(edge.beta, 2)}
                        </span>
                        <span style={{ fontSize: 9, color: getCIColor(ciWidth) }}>
                          [{formatNum(edge.ci_lower, 2)},{formatNum(edge.ci_upper, 2)}]
                        </span>
                        {sig && (
                          <span style={{ fontSize: 9, fontWeight: 700, color: sig.color }}>
                            {sig.label}
                          </span>
                        )}
                      </div>
                    )
                  })}
                  {nodeEdges.length > 15 && (
                    <div style={{ fontSize: 9, color: '#767676', marginTop: 4 }}>
                      +{nodeEdges.length - 15} more edges
                    </div>
                  )}
                </div>
              )}
            </div>
          )
        })}
      </div>
    </div>
  )
}

function ConfidenceBadge({ confidence }: { confidence: 'high' | 'medium' | 'low' }) {
  const config = {
    high: { color: '#10B981', bg: '#D1FAE5', label: 'High Confidence' },
    medium: { color: '#F59E0B', bg: '#FEF3C7', label: 'Medium Confidence' },
    low: { color: '#EF4444', bg: '#FEE2E2', label: 'Low Confidence' }
  }

  const c = config[confidence]

  return (
    <div style={{
      display: 'flex',
      alignItems: 'center',
      gap: 4,
      padding: '3px 8px',
      borderRadius: 12,
      background: c.bg,
      color: c.color,
      fontSize: 10,
      fontWeight: 600
    }}>
      <div style={{
        width: 6,
        height: 6,
        borderRadius: '50%',
        background: c.color
      }} />
      {c.label}
    </div>
  )
}

function StatBox({
  label,
  value,
  subtext,
  color
}: {
  label: string
  value: string
  subtext: string
  color: string
}) {
  return (
    <div style={{
      background: '#f0f2f8',
      borderRadius: 8,
      padding: '8px 10px',
      borderLeft: `3px solid ${color}`
    }}>
      <div style={{ fontSize: 9, color: '#767676', marginBottom: 2, textTransform: 'uppercase', letterSpacing: '0.3px' }}>
        {label}
      </div>
      <div style={{ fontSize: 16, fontWeight: 600, color: '#333' }}>
        {value}
      </div>
      <div style={{ fontSize: 9, color: '#767676', marginTop: 1 }}>
        {subtext}
      </div>
    </div>
  )
}

function TimelineCell({
  year,
  quality,
  yearData,
  transition,
  viewMode
}: {
  year: number
  quality: 'complete' | 'partial' | 'sparse' | 'none'
  yearData?: YearDataQuality | AggregatedYearQuality
  transition?: { from: string; to: string }
  viewMode: ViewMode
}) {
  const showLabel = year === 1990 || year === 2000 || year === 2010 || year === 2020

  // Color based on quality level
  const qualityColors = {
    complete: '#10B981',
    partial: '#F59E0B',
    sparse: '#EF4444',
    none: '#d0d5e0'
  }

  const bgColor = qualityColors[quality]
  const hasData = quality !== 'none'

  // Height based on quality
  const heightMap = {
    complete: 20,
    partial: 14,
    sparse: 10,
    none: 6
  }

  // Build tooltip
  let tooltip = `${year}`
  if (hasData && yearData) {
    if ('indicators' in yearData) {
      // Country mode
      tooltip += `\n${yearData.indicators.toLocaleString()} indicators`
    } else if ('avg_indicators' in yearData) {
      // Aggregated mode
      tooltip += `\n~${yearData.avg_indicators.toLocaleString()} avg indicators`
      if ('n_countries' in yearData) {
        tooltip += `\n${yearData.n_countries} countries`
      }
    }
    tooltip += `\nObserved: ${yearData.observed_pct.toFixed(0)}%`
    tooltip += `\nImputed: ${yearData.imputed_pct.toFixed(0)}%`
    tooltip += `\nQuality: ${quality}`
  } else {
    tooltip += '\nNo data'
  }
  if (transition) {
    tooltip += `\n${transition.from} → ${transition.to}`
  }

  return (
    <div style={{
      display: 'flex',
      flexDirection: 'column',
      alignItems: 'center',
      flex: 1
    }}>
      <div
        style={{
          width: '100%',
          height: heightMap[quality],
          background: bgColor,
          borderRadius: 1,
          transition: 'height 0.2s ease',
          position: 'relative'
        }}
        title={tooltip}
      >
        {/* Transition marker (country mode only) */}
        {transition && viewMode === 'country' && (
          <div style={{
            position: 'absolute',
            top: -3,
            left: '50%',
            transform: 'translateX(-50%)',
            width: 0,
            height: 0,
            borderLeft: '4px solid transparent',
            borderRight: '4px solid transparent',
            borderTop: '4px solid #7C3AED'
          }} />
        )}
      </div>
      {showLabel && (
        <div style={{
          fontSize: 8,
          color: '#767676',
          marginTop: 4,
          fontWeight: 500
        }}>
          {year.toString().slice(-2)}
        </div>
      )}
    </div>
  )
}

function TransitionRow({ transition }: { transition: { year: number; from: string; to: string; gni_at_transition: number | null } }) {
  const getStratumColor = (stratum: string) => {
    switch (stratum.toLowerCase()) {
      case 'developing': return '#F97316'
      case 'emerging': return '#3B82F6'
      case 'advanced': return '#10B981'
      default: return '#666'
    }
  }

  const isUpgrade =
    (transition.from === 'developing' && transition.to === 'emerging') ||
    (transition.from === 'emerging' && transition.to === 'advanced')

  return (
    <div style={{
      display: 'flex',
      alignItems: 'center',
      gap: 8,
      padding: '6px 8px',
      background: '#f0f2f8',
      borderRadius: 6,
      fontSize: 11
    }}>
      <span style={{ fontWeight: 600, color: '#333', minWidth: 32 }}>{transition.year}</span>
      <span style={{
        color: getStratumColor(transition.from),
        fontWeight: 500,
        textTransform: 'capitalize'
      }}>
        {transition.from}
      </span>
      <span style={{ color: isUpgrade ? '#10B981' : '#EF4444' }}>
        {isUpgrade ? '→' : '←'}
      </span>
      <span style={{
        color: getStratumColor(transition.to),
        fontWeight: 500,
        textTransform: 'capitalize'
      }}>
        {transition.to}
      </span>
      {transition.gni_at_transition && (
        <span style={{ color: '#767676', marginLeft: 'auto', fontSize: 10 }}>
          ${transition.gni_at_transition.toLocaleString()}
        </span>
      )}
    </div>
  )
}

// ============================================
// Pie Chart Component
// ============================================

function PieChart({
  distribution,
  totalCountries
}: {
  distribution: Record<IncomeStratum, { count: number; percentage: number }>
  totalCountries: number
}) {
  const size = 140
  const strokeWidth = 28
  const radius = (size - strokeWidth) / 2
  const circumference = 2 * Math.PI * radius
  const center = size / 2

  // Calculate stroke offsets for each segment
  const segments: Array<{ stratum: IncomeStratum; offset: number; length: number }> = []
  let currentOffset = 0

  const strata: IncomeStratum[] = ['developing', 'emerging', 'advanced']
  for (const stratum of strata) {
    const pct = distribution[stratum].percentage / 100
    const length = circumference * pct
    segments.push({
      stratum,
      offset: currentOffset,
      length
    })
    currentOffset += length
  }

  return (
    <div style={{
      display: 'flex',
      flexDirection: 'column',
      alignItems: 'center',
      marginBottom: 16
    }}>
      <div style={{ position: 'relative', width: size, height: size }}>
        <svg width={size} height={size} style={{ transform: 'rotate(-90deg)' }}>
          {/* Background circle */}
          <circle
            cx={center}
            cy={center}
            r={radius}
            fill="none"
            stroke="#f0f0f0"
            strokeWidth={strokeWidth}
          />
          {/* Segments */}
          {segments.map(({ stratum, offset, length }) => (
            <circle
              key={stratum}
              cx={center}
              cy={center}
              r={radius}
              fill="none"
              stroke={STRATUM_CONFIG[stratum].color}
              strokeWidth={strokeWidth}
              strokeDasharray={`${length} ${circumference - length}`}
              strokeDashoffset={-offset}
              style={{ transition: 'stroke-dasharray 0.5s ease, stroke-dashoffset 0.5s ease' }}
            />
          ))}
        </svg>
        {/* Center text */}
        <div style={{
          position: 'absolute',
          top: '50%',
          left: '50%',
          transform: 'translate(-50%, -50%)',
          textAlign: 'center'
        }}>
          <div style={{ fontSize: 24, fontWeight: 700, color: '#333' }}>
            {totalCountries}
          </div>
          <div style={{ fontSize: 10, color: '#767676' }}>
            countries
          </div>
        </div>
      </div>

      {/* Legend */}
      <div style={{
        display: 'flex',
        gap: 16,
        marginTop: 12
      }}>
        {strata.map(stratum => (
          <div key={stratum} style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
            <div style={{
              width: 10,
              height: 10,
              borderRadius: 2,
              background: STRATUM_CONFIG[stratum].color
            }} />
            <div style={{ fontSize: 11 }}>
              <span style={{ fontWeight: 600, color: '#333' }}>{distribution[stratum].count}</span>
              <span style={{ color: '#767676', marginLeft: 2 }}>({distribution[stratum].percentage.toFixed(0)}%)</span>
            </div>
          </div>
        ))}
      </div>
    </div>
  )
}

// ============================================
// Stratum Country List Component
// ============================================

function StratumCountryList({
  stratum,
  countries,
  isExpanded,
  onToggle,
  thresholds
}: {
  stratum: IncomeStratum
  countries: StratumCountryInfo[]
  isExpanded: boolean
  onToggle: () => void
  thresholds: { developing_to_emerging: number; emerging_to_advanced: number }
}) {
  const config = STRATUM_CONFIG[stratum]

  // Get countries near transition (top 5 by progress for dev/emerging, or by GNI for advanced)
  const nearTransition = useMemo(() => {
    if (stratum === 'advanced') {
      // For advanced, show lowest GNI (closest to emerging threshold)
      return [...countries]
        .filter(c => c.gni_per_capita !== null)
        .sort((a, b) => (a.gni_per_capita || 0) - (b.gni_per_capita || 0))
        .slice(0, 3)
    } else {
      // For developing/emerging, show highest progress (closest to next tier)
      return [...countries]
        .filter(c => c.gni_per_capita !== null)
        .sort((a, b) => b.progress_pct - a.progress_pct)
        .slice(0, 3)
    }
  }, [countries, stratum])

  return (
    <div style={{
      border: '1px solid #e2e6ee',
      borderRadius: 8,
      overflow: 'hidden'
    }}>
      {/* Header */}
      <button
        onClick={onToggle}
        style={{
          width: '100%',
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'space-between',
          padding: '10px 12px',
          background: isExpanded ? config.color + '15' : '#f4f5fa',
          border: 'none',
          cursor: 'pointer',
          borderLeft: `4px solid ${config.color}`
        }}
      >
        <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
          <span style={{ fontWeight: 600, fontSize: 13, color: config.darkColor }}>
            {config.label}
          </span>
          <span style={{
            fontSize: 11,
            color: '#767676',
            background: '#fff',
            padding: '2px 6px',
            borderRadius: 10
          }}>
            {countries.length}
          </span>
        </div>
        <svg
          width="16"
          height="16"
          viewBox="0 0 24 24"
          fill="none"
          stroke="#888"
          strokeWidth="2"
          style={{
            transform: isExpanded ? 'rotate(180deg)' : 'rotate(0deg)',
            transition: 'transform 0.2s ease'
          }}
        >
          <polyline points="6 9 12 15 18 9" />
        </svg>
      </button>

      {/* Preview (when collapsed) */}
      {!isExpanded && nearTransition.length > 0 && (
        <div style={{
          padding: '8px 12px',
          background: '#fff',
          borderTop: '1px solid #f0f0f0'
        }}>
          <div style={{ fontSize: 9, color: '#767676', marginBottom: 6, textTransform: 'uppercase', letterSpacing: '0.5px' }}>
            {stratum === 'advanced' ? 'Lowest GNI' : 'Closest to Next Tier'}
          </div>
          <div style={{ display: 'flex', flexDirection: 'column', gap: 4 }}>
            {nearTransition.map(country => (
              <CountryProgressRow
                key={country.name}
                country={country}
                stratum={stratum}
                thresholds={thresholds}
                compact
              />
            ))}
          </div>
        </div>
      )}

      {/* Full list (when expanded) */}
      {isExpanded && (
        <div style={{
          maxHeight: 250,
          overflowY: 'auto',
          background: '#fff'
        }}>
          {countries.map(country => (
            <CountryProgressRow
              key={country.name}
              country={country}
              stratum={stratum}
              thresholds={thresholds}
              compact={false}
            />
          ))}
        </div>
      )}
    </div>
  )
}

// ============================================
// Country Progress Row Component
// ============================================

function CountryProgressRow({
  country,
  stratum,
  thresholds,
  compact
}: {
  country: StratumCountryInfo
  stratum: IncomeStratum
  thresholds: { developing_to_emerging: number; emerging_to_advanced: number }
  compact: boolean
}) {
  const config = STRATUM_CONFIG[stratum]

  // Calculate progress bar width
  const progressWidth = Math.min(100, Math.max(0, country.progress_pct))

  // Determine next threshold
  const nextThreshold = stratum === 'developing'
    ? thresholds.developing_to_emerging
    : stratum === 'emerging'
      ? thresholds.emerging_to_advanced
      : null

  return (
    <div style={{
      display: 'flex',
      alignItems: 'center',
      gap: 8,
      padding: compact ? '4px 0' : '8px 12px',
      borderBottom: compact ? 'none' : '1px solid #eef0f6',
      fontSize: compact ? 11 : 12
    }}>
      {/* Country name */}
      <div style={{
        flex: 1,
        fontWeight: 500,
        color: '#333',
        whiteSpace: 'nowrap',
        overflow: 'hidden',
        textOverflow: 'ellipsis',
        minWidth: 0
      }}>
        {country.name}
      </div>

      {/* GNI */}
      {country.gni_per_capita !== null && (
        <div style={{
          fontSize: compact ? 10 : 11,
          color: '#767676',
          whiteSpace: 'nowrap'
        }}>
          ${country.gni_per_capita.toLocaleString()}
        </div>
      )}

      {/* Progress bar (for developing/emerging) */}
      {stratum !== 'advanced' && nextThreshold && (
        <div style={{
          width: compact ? 40 : 60,
          height: 6,
          background: '#f0f0f0',
          borderRadius: 3,
          overflow: 'hidden',
          flexShrink: 0
        }}>
          <div style={{
            width: `${progressWidth}%`,
            height: '100%',
            background: config.color,
            borderRadius: 3,
            transition: 'width 0.3s ease'
          }} />
        </div>
      )}

      {/* Progress percentage or distance */}
      {!compact && (
        <div style={{
          fontSize: 10,
          color: '#767676',
          minWidth: 40,
          textAlign: 'right'
        }}>
          {stratum === 'advanced' ? (
            country.gni_per_capita !== null ? `+$${(country.gni_per_capita - thresholds.emerging_to_advanced).toLocaleString()}` : '-'
          ) : (
            country.distance_to_next !== null ? `$${country.distance_to_next.toLocaleString()} to go` : '-'
          )}
        </div>
      )}
    </div>
  )
}

export default DataQualityPanel
