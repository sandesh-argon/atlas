/**
 * InterventionBuilder Component - Phase 2
 *
 * Select intervention targets and set % change.
 * Features:
 * - Indicator dropdown grouped by domain
 * - Change % slider (-100% to +500%)
 * - Add up to 5 interventions
 * - Remove intervention button
 * - Wired to Zustand store
 */

import { useEffect, useMemo, useCallback, useState, useRef } from 'react'
import { useSimulationStore } from '../../stores/simulationStore'
import { simulationAPI } from '../../services/api'
import type { Intervention } from '../../services/api'
import { INTERVENTION_YEAR_MAX, INTERVENTION_YEAR_MIN } from '../../constants/time'

// ============================================
// Constants
// ============================================

const MAX_INTERVENTIONS = 5
const MIN_CHANGE = -100
const MAX_CHANGE = 200
const MIN_YEAR = INTERVENTION_YEAR_MIN
const MAX_YEAR = INTERVENTION_YEAR_MAX

// Domain colors matching the main visualization
const DOMAIN_COLORS: Record<string, string> = {
  'Conflict & Peace': '#E53935',
  'Culture & Society': '#8E24AA',
  'Economy': '#43A047',
  'Education': '#1E88E5',
  'Environment': '#00ACC1',
  'Governance': '#FB8C00',
  'Health': '#F06292',
  'Infrastructure': '#6D4C41',
  'Demographics': '#78909C'
}

// ============================================
// Styles (Light theme)
// ============================================

const styles = {
  container: {
  },
  header: {
    display: 'flex',
    justifyContent: 'space-between',
    alignItems: 'center',
    marginBottom: 10
  },
  title: {
    color: '#333',
    fontSize: 12,
    fontWeight: 600,
    margin: 0
  },
  count: {
    color: '#767676',
    fontSize: 11
  },
  interventionCard: {
    background: '#f0f2f8',
    borderRadius: 6,
    padding: 10,
    marginBottom: 8,
    border: '1px solid #e2e6ee'
  },
  cardHeader: {
    display: 'flex',
    justifyContent: 'space-between',
    alignItems: 'center',
    marginBottom: 8
  },
  cardNumber: {
    color: '#666',
    fontSize: 11,
    fontWeight: 600
  },
  removeBtn: {
    background: '#FFEBEE',
    border: '1px solid #FFCDD2',
    color: '#C62828',
    width: 22,
    height: 22,
    borderRadius: 4,
    cursor: 'pointer',
    fontSize: 14,
    lineHeight: 1,
    transition: 'background 0.2s',
    position: 'relative' as const
  },
  select: {
    width: '100%',
    padding: '6px 8px',
    borderRadius: 4,
    border: '1px solid #d0d5e0',
    background: 'white',
    color: '#333',
    fontSize: 12,
    marginBottom: 8,
    cursor: 'pointer'
  },
  sliderContainer: {
    marginBottom: 4
  },
  sliderLabel: {
    display: 'flex',
    justifyContent: 'space-between',
    alignItems: 'center',
    marginBottom: 4
  },
  sliderText: {
    color: '#666',
    fontSize: 11
  },
  sliderValue: {
    color: '#4CAF50',
    fontSize: 12,
    fontWeight: 600,
    minWidth: 50,
    textAlign: 'right' as const
  },
  slider: {
    width: '100%',
    height: 4,
    WebkitAppearance: 'none' as const,
    background: '#d0d5e0',
    borderRadius: 2,
    cursor: 'pointer'
  },
  addButton: {
    width: '100%',
    padding: '8px 12px',
    borderRadius: 4,
    border: '1px dashed #bcc3d4',
    background: 'transparent',
    color: '#666',
    fontSize: 12,
    cursor: 'pointer',
    display: 'flex',
    alignItems: 'center',
    justifyContent: 'center',
    gap: 6,
    transition: 'all 0.2s'
  },
  emptyState: {
    textAlign: 'center' as const,
    padding: '12px',
    color: '#767676',
    fontSize: 11
  }
}

// ============================================
// Year Input — commits on blur or Enter, not on every keystroke
// ============================================

function YearInput({ value, onCommit }: { value: number; onCommit: (year: number) => void }) {
  const [draft, setDraft] = useState(String(value))
  const prevValue = useRef(value)

  // Sync draft when external value changes (e.g., parent resets)
  useEffect(() => {
    if (value !== prevValue.current) {
      setDraft(String(value))
      prevValue.current = value
    }
  }, [value])

  const commit = () => {
    const parsed = parseInt(draft, 10)
    if (isNaN(parsed)) {
      setDraft(String(value)) // revert
      return
    }
    const clamped = Math.max(MIN_YEAR, Math.min(MAX_YEAR, parsed))
    setDraft(String(clamped))
    if (clamped !== value) {
      onCommit(clamped)
      prevValue.current = clamped
    }
  }

  return (
    <input
      type="text"
      inputMode="numeric"
      name="intervention-year"
      aria-label="Intervention year"
      value={draft}
      onChange={(e) => setDraft(e.target.value)}
      onBlur={commit}
      onKeyDown={(e) => { if (e.key === 'Enter') { e.currentTarget.blur() } }}
      style={{
        width: 46,
        padding: '2px 4px',
        borderRadius: 3,
        border: '1px solid #d0d5e0',
        background: 'white',
        color: '#555',
        fontSize: 11,
        textAlign: 'center' as const
      }}
      title={`Intervention year (${MIN_YEAR}–${MAX_YEAR})`}
    />
  )
}

// ============================================
// Indicator Dropdown — searchable combobox replacing native <select>
// ============================================

interface IndicatorGroup {
  domain: string
  label: string
  color: string
  nodes: Array<{ id: string; label: string; domain: string; outEdges: number }>
}

interface TopIndicator {
  id: string
  label: string
  domain?: string
  outEdges: number
}

function IndicatorDropdown({
  index,
  value,
  selectedLabel,
  selectedDomain,
  indicatorOptions,
  topIndicators,
  onChange,
}: {
  index: number
  value: string
  selectedLabel: string
  selectedDomain: string
  indicatorOptions: IndicatorGroup[]
  topIndicators: TopIndicator[]
  onChange: (index: number, indicatorId: string) => void
}) {
  const [isOpen, setIsOpen] = useState(false)
  const [search, setSearch] = useState('')
  const containerRef = useRef<HTMLDivElement>(null)
  const inputRef = useRef<HTMLInputElement>(null)
  const listRef = useRef<HTMLDivElement>(null)

  // Close on outside click
  useEffect(() => {
    if (!isOpen) return
    const handler = (e: MouseEvent) => {
      if (containerRef.current && !containerRef.current.contains(e.target as Node)) {
        setIsOpen(false)
        setSearch('')
      }
    }
    document.addEventListener('mousedown', handler)
    return () => document.removeEventListener('mousedown', handler)
  }, [isOpen])

  const lowerSearch = search.toLowerCase()

  // Filter top indicators
  const filteredTop = lowerSearch
    ? topIndicators.filter(ind =>
        (ind.label || ind.id).toLowerCase().includes(lowerSearch) ||
        (ind.domain || '').toLowerCase().includes(lowerSearch)
      )
    : topIndicators.slice(0, 10) // Show top 10 by default

  // Filter grouped indicators
  const filteredGroups = indicatorOptions
    .map(group => {
      if (!lowerSearch) return group
      const domainMatch = group.domain.toLowerCase().includes(lowerSearch)
      const filteredNodes = domainMatch
        ? group.nodes
        : group.nodes.filter(n => n.label.toLowerCase().includes(lowerSearch))
      return filteredNodes.length > 0 ? { ...group, nodes: filteredNodes } : null
    })
    .filter((g): g is IndicatorGroup => g !== null)

  const handleSelect = (indicatorId: string) => {
    onChange(index, indicatorId)
    setIsOpen(false)
    setSearch('')
  }

  const domainColor = selectedDomain ? (DOMAIN_COLORS[selectedDomain] || '#9E9E9E') : undefined

  return (
    <div ref={containerRef} style={{ position: 'relative', marginBottom: 8 }}>
      {/* Trigger button — shows selected indicator or placeholder */}
      <button
        type="button"
        onClick={() => {
          setIsOpen(prev => !prev)
          if (!isOpen) {
            requestAnimationFrame(() => inputRef.current?.focus())
          }
        }}
        aria-label={`Indicator for intervention ${index + 1}`}
        aria-expanded={isOpen}
        style={{
          width: '100%',
          padding: '6px 28px 6px 8px',
          borderRadius: 4,
          border: `1px solid ${isOpen ? '#3B82F6' : '#d0d5e0'}`,
          background: 'white',
          color: value ? '#333' : '#767676',
          fontSize: 12,
          cursor: 'pointer',
          textAlign: 'left',
          display: 'flex',
          alignItems: 'center',
          gap: 6,
          position: 'relative',
        }}
      >
        {domainColor && (
          <span style={{
            width: 8, height: 8, borderRadius: '50%',
            backgroundColor: domainColor, flexShrink: 0,
            boxShadow: '0 0 0 1px rgba(0,0,0,0.1)',
          }} />
        )}
        <span style={{
          overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap', flex: 1,
        }}>
          {value ? selectedLabel : 'Select indicator...'}
        </span>
        <svg
          width="12" height="12" viewBox="0 0 12 12" fill="none"
          stroke="#767676" strokeWidth="2" strokeLinecap="round"
          style={{
            position: 'absolute', right: 8, top: '50%',
            transform: `translateY(-50%) ${isOpen ? 'rotate(180deg)' : 'rotate(0deg)'}`,
            transition: 'transform 0.15s ease',
          }}
        >
          <polyline points="2 4 6 8 10 4" />
        </svg>
      </button>

      {/* Dropdown */}
      {isOpen && (
        <div style={{
          position: 'absolute',
          top: '100%',
          left: 0,
          right: 0,
          zIndex: 50,
          background: 'white',
          border: '1px solid #d0d5e0',
          borderRadius: 6,
          boxShadow: '0 4px 12px rgba(0,0,0,0.15)',
          marginTop: 2,
          display: 'flex',
          flexDirection: 'column',
          maxHeight: 260,
        }}>
          {/* Search input */}
          <div style={{ padding: '6px 8px', borderBottom: '1px solid #e2e6ee', flexShrink: 0 }}>
            <input
              ref={inputRef}
              type="text"
              value={search}
              onChange={e => setSearch(e.target.value)}
              placeholder="Search indicators..."
              style={{
                width: '100%',
                padding: '5px 8px',
                border: '1px solid #d0d5e0',
                borderRadius: 4,
                fontSize: 12,
                boxSizing: 'border-box',
                outline: 'none',
              }}
              onFocus={e => e.target.style.borderColor = '#3B82F6'}
              onBlur={e => e.target.style.borderColor = '#d0d5e0'}
              onKeyDown={e => {
                if (e.key === 'Escape') {
                  setIsOpen(false)
                  setSearch('')
                }
              }}
            />
          </div>

          {/* Options list */}
          <div ref={listRef} style={{ overflowY: 'auto', flex: 1 }}>
            {/* Top indicators section */}
            {filteredTop.length > 0 && (
              <>
                <div style={{
                  padding: '6px 10px', fontSize: 10, fontWeight: 600,
                  color: '#767676', background: '#f4f5fa',
                  position: 'sticky', top: 0, zIndex: 1,
                }}>
                  ★ Top Indicators (by causal reach)
                </div>
                {filteredTop.map(ind => (
                  <button
                    key={`top-${ind.id}`}
                    type="button"
                    onClick={() => handleSelect(ind.id)}
                    style={{
                      width: '100%',
                      padding: '6px 10px',
                      border: 'none',
                      background: ind.id === value ? '#EBF5FF' : 'white',
                      cursor: 'pointer',
                      textAlign: 'left',
                      fontSize: 12,
                      color: '#333',
                      display: 'flex',
                      alignItems: 'center',
                      gap: 6,
                    }}
                    onMouseEnter={e => { if (ind.id !== value) e.currentTarget.style.background = '#eef0f6' }}
                    onMouseLeave={e => { if (ind.id !== value) e.currentTarget.style.background = 'white' }}
                  >
                    <span style={{
                      width: 6, height: 6, borderRadius: '50%', flexShrink: 0,
                      backgroundColor: DOMAIN_COLORS[ind.domain || ''] || '#9E9E9E',
                    }} />
                    <span style={{ flex: 1, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
                      {ind.label || ind.id}
                    </span>
                    <span style={{ fontSize: 10, color: '#767676', flexShrink: 0 }}>
                      {ind.outEdges}
                    </span>
                  </button>
                ))}
              </>
            )}

            {/* Domain-grouped sections */}
            {filteredGroups.map(group => (
              <div key={group.domain}>
                <div style={{
                  padding: '6px 10px', fontSize: 10, fontWeight: 600,
                  color: group.color, background: '#f4f5fa',
                  position: 'sticky', top: 0, zIndex: 1,
                  borderTop: '1px solid #e2e6ee',
                }}>
                  {group.label}
                </div>
                {group.nodes.map(node => (
                  <button
                    key={node.id}
                    type="button"
                    onClick={() => handleSelect(node.id)}
                    style={{
                      width: '100%',
                      padding: '6px 10px 6px 18px',
                      border: 'none',
                      background: node.id === value ? '#EBF5FF' : 'white',
                      cursor: 'pointer',
                      textAlign: 'left',
                      fontSize: 12,
                      color: '#333',
                      display: 'flex',
                      alignItems: 'center',
                      gap: 6,
                    }}
                    onMouseEnter={e => { if (node.id !== value) e.currentTarget.style.background = '#eef0f6' }}
                    onMouseLeave={e => { if (node.id !== value) e.currentTarget.style.background = 'white' }}
                  >
                    <span style={{ flex: 1, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
                      {node.label}
                    </span>
                    {node.outEdges > 0 && (
                      <span style={{ fontSize: 10, color: '#767676', flexShrink: 0 }}>
                        {node.outEdges}
                      </span>
                    )}
                  </button>
                ))}
              </div>
            ))}

            {/* No results */}
            {filteredTop.length === 0 && filteredGroups.length === 0 && (
              <div style={{ padding: '12px 10px', textAlign: 'center', color: '#767676', fontSize: 12 }}>
                No indicators match "{search}"
              </div>
            )}
          </div>
        </div>
      )}
    </div>
  )
}

// ============================================
// Main Component
// ============================================

export function InterventionBuilder() {
  const {
    indicators,
    indicatorsLoading,
    indicatorsLoadFailed,
    loadIndicators,
    selectedCountry,
    countryGraph,
    interventions,
    addIntervention,
    updateIntervention,
    removeIntervention,
    historicalTimeline,
    currentYearIndex,
    selectedStratum,
    simulationStartYear
  } = useSimulationStore()

  // Current timeline year (used as default for new interventions)
  const currentTimelineYear = historicalTimeline?.years[currentYearIndex] ?? INTERVENTION_YEAR_MAX

  // --------------------------------------------------
  // Temporal edge counts: per-intervention, updates on indicator/year change
  // --------------------------------------------------
  // Map: "indicatorId::year" → outgoing edge count
  const [temporalEdgeCounts, setTemporalEdgeCounts] = useState<Map<string, number>>(new Map())
  // Cache completed temporal graph edges per "country::year"
  const temporalGraphCache = useRef<Map<string, Map<string, number>>>(new Map())
  // Track in-flight fetches separately (prevents premature "0 edges" from empty cache)
  const inFlightFetches = useRef<Set<string>>(new Set())

  /**
   * Derive the current scope key for graph caching.
   * Country → "country::USA", Stratified → "stratified::developing", Unified → "unified"
   */
  const scopeKey = selectedCountry
    ? `country::${selectedCountry}`
    : selectedStratum === 'unified'
      ? 'unified'
      : `stratified::${selectedStratum}`

  /**
   * Fetch temporal edge counts for each intervention's indicator+year combo.
   * Uses the appropriate graph API based on current scope (country, stratified, unified).
   */
  useEffect(() => {
    const needed: Array<{ indicator: string; year: number; cacheKey: string; countKey: string }> = []

    for (const inv of interventions) {
      if (!inv.indicator) continue
      const year = inv.year ?? currentTimelineYear
      const cacheKey = `${scopeKey}::${year}`
      const countKey = `${inv.indicator}::${year}`

      if (temporalEdgeCounts.has(countKey)) continue

      const cached = temporalGraphCache.current.get(cacheKey)
      if (cached) {
        setTemporalEdgeCounts(prev => {
          const next = new Map(prev)
          next.set(countKey, cached.get(inv.indicator) ?? 0)
          return next
        })
        continue
      }

      if (inFlightFetches.current.has(cacheKey)) continue
      needed.push({ indicator: inv.indicator, year, cacheKey, countKey })
    }

    if (needed.length === 0) return

    const controller = new AbortController()

    const uniqueYears = new Map<string, number>()
    for (const n of needed) {
      uniqueYears.set(n.cacheKey, n.year)
    }

    for (const [cacheKey, year] of uniqueYears) {
      inFlightFetches.current.add(cacheKey)

      // Pick the right graph API based on scope
      const graphPromise: Promise<{ edges: Array<{ source: string }> }> = selectedCountry
        ? simulationAPI.getCountryTemporalGraph(selectedCountry, year, controller.signal)
        : selectedStratum === 'unified'
          ? simulationAPI.getUnifiedGraph(year, controller.signal)
          : simulationAPI.getStratifiedGraph(selectedStratum as 'developing' | 'emerging' | 'advanced', year, controller.signal)

      graphPromise
        .then(result => {
          if (controller.signal.aborted) return
          const edgeMap = new Map<string, number>()
          for (const edge of result.edges) {
            edgeMap.set(edge.source, (edgeMap.get(edge.source) ?? 0) + 1)
          }
          temporalGraphCache.current.set(cacheKey, edgeMap)
          inFlightFetches.current.delete(cacheKey)

          setTemporalEdgeCounts(prev => {
            const next = new Map(prev)
            for (const n of needed) {
              if (n.cacheKey === cacheKey) {
                next.set(n.countKey, edgeMap.get(n.indicator) ?? 0)
              }
            }
            return next
          })
        })
        .catch(() => {
          if (controller.signal.aborted) return
          inFlightFetches.current.delete(cacheKey)
          setTemporalEdgeCounts(prev => {
            const next = new Map(prev)
            for (const n of needed) {
              if (n.cacheKey === cacheKey) {
                next.set(n.countKey, 0)
              }
            }
            return next
          })
        })
    }

    return () => controller.abort()
  }, [interventions, scopeKey, currentTimelineYear, temporalEdgeCounts, selectedCountry, selectedStratum])

  // Clear temporal cache when scope changes
  useEffect(() => {
    temporalGraphCache.current.clear()
    setTemporalEdgeCounts(new Map())
  }, [scopeKey])

  /** Get temporal edge count for an intervention, or null if not yet loaded */
  const getTemporalEdges = useCallback((indicator: string, year: number): number | null => {
    if (!indicator) return null
    const key = `${indicator}::${year}`
    return temporalEdgeCounts.has(key) ? temporalEdgeCounts.get(key)! : null
  }, [temporalEdgeCounts])

  // Load indicators on mount (with failure guard to prevent infinite retry)
  useEffect(() => {
    if (indicators.length === 0 && !indicatorsLoading && !indicatorsLoadFailed) {
      loadIndicators()
    }
  }, [indicators.length, indicatorsLoading, indicatorsLoadFailed, loadIndicators])

  /**
   * Outgoing edge counts for the dropdown — loaded from the scope-appropriate graph.
   * For country: uses the already-loaded countryGraph.
   * For unified/stratified: fetches the temporal graph for the current year.
   */
  const [scopeEdgeCounts, setScopeEdgeCounts] = useState<Map<string, number>>(new Map())

  // Fetch scope-level graph edge counts when scope or year changes (non-country only)
  useEffect(() => {
    if (selectedCountry) {
      setScopeEdgeCounts(new Map()) // country mode uses countryGraph below
      return
    }

    const year = currentTimelineYear
    const graphPromise: Promise<{ edges: Array<{ source: string }> }> =
      selectedStratum === 'unified'
        ? simulationAPI.getUnifiedGraph(year)
        : simulationAPI.getStratifiedGraph(selectedStratum as 'developing' | 'emerging' | 'advanced', year)

    graphPromise
      .then(result => {
        const counts = new Map<string, number>()
        for (const edge of result.edges) {
          counts.set(edge.source, (counts.get(edge.source) ?? 0) + 1)
        }
        setScopeEdgeCounts(counts)
      })
      .catch(() => setScopeEdgeCounts(new Map()))
  }, [selectedCountry, selectedStratum, currentTimelineYear])

  const outEdgeCounts = useMemo(() => {
    // Country mode: use pre-loaded countryGraph
    if (selectedCountry && countryGraph?.edges) {
      const counts = new Map<string, number>()
      for (const edge of countryGraph.edges) {
        counts.set(edge.source, (counts.get(edge.source) || 0) + 1)
      }
      return counts
    }
    // Non-country mode: use fetched scope graph
    return scopeEdgeCounts
  }, [selectedCountry, countryGraph, scopeEdgeCounts])

  // Build indicator options grouped by domain, sorted by causal connections
  const indicatorOptions = useMemo(() => {
    if (!indicators || indicators.length === 0) {
      return []
    }

    // Group by domain
    const grouped = new Map<string, Array<{ id: string; label: string; domain: string; outEdges: number }>>()

    indicators.forEach(ind => {
      const domain = ind.domain || 'Other'
      if (!grouped.has(domain)) {
        grouped.set(domain, [])
      }
      grouped.get(domain)!.push({
        id: ind.id,
        label: ind.label || ind.id,
        domain,
        outEdges: outEdgeCounts.get(ind.id) || 0
      })
    })

    return Array.from(grouped.entries())
      .sort((a, b) => a[0].localeCompare(b[0]))
      .map(([domain, nodes]) => ({
        domain,
        label: domain,
        color: DOMAIN_COLORS[domain] || '#9E9E9E',
        // Sort by outgoing causal connections descending
        nodes: nodes.sort((a, b) => b.outEdges - a.outEdges)
      }))
  }, [indicators, outEdgeCounts])

  // Top indicators by causal connections (most propagation potential)
  const topIndicators = useMemo(() => {
    if (!indicators || indicators.length === 0) return []
    return indicators
      .map(ind => ({
        ...ind,
        outEdges: outEdgeCounts.get(ind.id) || 0
      }))
      .filter(ind => ind.outEdges > 0)
      .sort((a, b) => b.outEdges - a.outEdges)
      .slice(0, 50)
  }, [indicators, outEdgeCounts])

  // Add new intervention
  const handleAddIntervention = useCallback(() => {
    if (interventions.length >= MAX_INTERVENTIONS) return

    const newIntervention: Intervention = {
      id: `intervention-${Date.now()}`,
      indicator: '',
      change_percent: 20,
      year: simulationStartYear,
      indicatorLabel: '',
      domain: ''
    }
    addIntervention(newIntervention)
  }, [interventions.length, addIntervention, simulationStartYear])

  // Update intervention indicator (clears stale temporal edge count)
  const handleIndicatorChange = useCallback((index: number, indicatorId: string) => {
    // Find indicator info
    let indicatorLabel = indicatorId
    let domain = ''

    for (const group of indicatorOptions) {
      const node = group.nodes.find(n => n.id === indicatorId)
      if (node) {
        indicatorLabel = node.label
        domain = node.domain
        break
      }
    }

    // Clear old temporal count so the effect re-fetches
    const oldInd = interventions[index]?.indicator
    const year = interventions[index]?.year ?? currentTimelineYear
    if (oldInd) {
      setTemporalEdgeCounts(prev => {
        const next = new Map(prev)
        next.delete(`${oldInd}::${year}`)
        return next
      })
    }

    updateIntervention(index, {
      indicator: indicatorId,
      indicatorLabel,
      domain
    })
  }, [indicatorOptions, updateIntervention, interventions, currentTimelineYear])

  // Update intervention change percent
  const handleChangePercent = useCallback((index: number, change_percent: number) => {
    updateIntervention(index, { change_percent })
  }, [updateIntervention])

  // Commit intervention year change (clears stale temporal edge count, clamps value)
  const commitYearChange = useCallback((index: number, rawYear: number) => {
    const clamped = Math.max(MIN_YEAR, Math.min(MAX_YEAR, Math.round(rawYear)))
    const ind = interventions[index]?.indicator
    const oldYear = interventions[index]?.year ?? currentTimelineYear
    if (ind && oldYear !== clamped) {
      setTemporalEdgeCounts(prev => {
        const next = new Map(prev)
        next.delete(`${ind}::${oldYear}`)
        return next
      })
    }
    updateIntervention(index, { year: clamped })
  }, [updateIntervention, interventions, currentTimelineYear])

  // Format change percent for display
  const formatChange = (pct: number) => {
    const sign = pct >= 0 ? '+' : ''
    return `${sign}${pct}%`
  }

  // Get value color
  const getValueColor = (pct: number) => {
    if (pct > 0) return '#4CAF50'
    if (pct < 0) return '#ef5350'
    return '#666'
  }

  // Loading state
  if (indicatorsLoading) {
    return (
      <div style={styles.container}>
        <div style={styles.emptyState}>
          Loading indicators...
        </div>
      </div>
    )
  }

  // Error state with retry
  if (indicatorsLoadFailed) {
    return (
      <div style={styles.container}>
        <div style={{ textAlign: 'center', padding: '12px', color: '#C62828', fontSize: 12 }}>
          Failed to load indicators
          <button
            onClick={() => loadIndicators()}
            style={{
              display: 'block',
              margin: '8px auto 0',
              padding: '6px 16px',
              borderRadius: 4,
              border: '1px solid #FFCDD2',
              background: '#FFEBEE',
              color: '#C62828',
              fontSize: 12,
              cursor: 'pointer'
            }}
          >
            Retry
          </button>
        </div>
      </div>
    )
  }

  return (
    <div style={styles.container}>
      {/* Header */}
      <div style={styles.header}>
        <h3 style={styles.title}>Interventions</h3>
        <span style={styles.count}>
          {interventions.length} / {MAX_INTERVENTIONS}
        </span>
      </div>

      {/* Intervention cards */}
      {interventions.map((intervention, index) => (
        <div key={intervention.id || index} style={styles.interventionCard}>
          {/* Card header */}
          <div style={styles.cardHeader}>
            <span style={styles.cardNumber}>Intervention {index + 1}</span>
            <div style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
              <YearInput
                value={intervention.year ?? currentTimelineYear}
                onCommit={(year) => commitYearChange(index, year)}
              />
              <button
                className="touch-target-44"
                style={styles.removeBtn}
                onClick={() => removeIntervention(index)}
                title="Remove intervention"
                aria-label={`Remove intervention ${index + 1}`}
              >
                ×
              </button>
            </div>
          </div>

          {/* Indicator selector — searchable dropdown */}
          <IndicatorDropdown
            index={index}
            value={intervention.indicator}
            selectedLabel={intervention.indicatorLabel || ''}
            selectedDomain={intervention.domain || ''}
            indicatorOptions={indicatorOptions}
            topIndicators={topIndicators}
            onChange={handleIndicatorChange}
          />

          {/* Temporal edge count badge */}
          {intervention.indicator && (() => {
            const year = intervention.year ?? currentTimelineYear
            const temporalCount = getTemporalEdges(intervention.indicator, year)
            const staticCount = outEdgeCounts.get(intervention.indicator) ?? 0
            const isLoading = temporalCount === null
            const hasEdges = temporalCount !== null && temporalCount > 0
            const noEdges = temporalCount !== null && temporalCount === 0

            return (
              <div style={{
                display: 'flex',
                alignItems: 'center',
                gap: 6,
                marginBottom: 8,
                padding: '4px 8px',
                borderRadius: 4,
                fontSize: 11,
                background: noEdges ? '#FFF3E0' : '#F1F8E9',
                border: `1px solid ${noEdges ? '#FFE0B2' : '#DCEDC8'}`,
              }}>
                <span style={{
                  fontWeight: 600,
                  color: noEdges ? '#E65100' : hasEdges ? '#33691E' : '#888',
                }}>
                  {isLoading ? '...' : temporalCount}
                </span>
                <span style={{ color: '#666' }}>
                  causal edges in {year}
                </span>
                {staticCount !== temporalCount && temporalCount !== null && (
                  <span style={{ color: '#767676', marginLeft: 'auto', fontSize: 10 }}>
                    ({staticCount} static)
                  </span>
                )}
                {noEdges && (
                  <span style={{
                    color: '#E65100',
                    marginLeft: 'auto',
                    fontSize: 10,
                    fontWeight: 500,
                  }}>
                    no propagation — try a later year
                  </span>
                )}
                {hasEdges && year > simulationStartYear && (
                  <span style={{
                    color: '#F57F17',
                    marginLeft: 'auto',
                    fontSize: 10,
                    fontWeight: 500,
                  }}>
                    baseline from {simulationStartYear}
                  </span>
                )}
              </div>
            )
          })()}

          {/* Change slider */}
          <div style={styles.sliderContainer}>
            <div style={styles.sliderLabel}>
              <span style={styles.sliderText}>Change</span>
              <span style={{
                ...styles.sliderValue,
                color: getValueColor(intervention.change_percent)
              }}>
                {formatChange(intervention.change_percent)}
              </span>
            </div>
            <input
              id={`intervention-${index}-change`}
              name={`intervention-${index}-change`}
              type="range"
              min={MIN_CHANGE}
              max={MAX_CHANGE}
              value={intervention.change_percent}
              onChange={(e) => handleChangePercent(index, Number(e.target.value))}
              style={styles.slider}
              aria-label={`Change percent for intervention ${index + 1}`}
              aria-valuemin={MIN_CHANGE}
              aria-valuemax={MAX_CHANGE}
              aria-valuenow={intervention.change_percent}
              aria-valuetext={formatChange(intervention.change_percent)}
            />
          </div>
        </div>
      ))}

      {/* Add button */}
      {interventions.length < MAX_INTERVENTIONS && (
        <button
          style={styles.addButton}
          onClick={handleAddIntervention}
          onMouseEnter={(e) => {
            e.currentTarget.style.background = '#eef0f6'
            e.currentTarget.style.borderColor = '#999'
          }}
          onMouseLeave={(e) => {
            e.currentTarget.style.background = 'transparent'
            e.currentTarget.style.borderColor = '#bcc3d4'
          }}
        >
          <span style={{ fontSize: 14 }}>+</span>
          Add Intervention
        </button>
      )}

      {/* Empty state hint */}
      {interventions.length === 0 && (
        <div style={{ ...styles.emptyState, marginTop: 8 }}>
          Add interventions to simulate policy changes
        </div>
      )}

      {/* Slider thumb styles */}
      <style>{`
        button:focus-visible,
        input[type="text"]:focus-visible,
        input[type="range"]:focus-visible {
          outline: 2px solid #3B82F6;
          outline-offset: 2px;
        }

        input[type="range"]::-webkit-slider-thumb {
          -webkit-appearance: none;
          width: 16px;
          height: 16px;
          background: #fff;
          border-radius: 50%;
          cursor: pointer;
          border: 2px solid #4CAF50;
          margin-top: -6px;
        }

        input[type="range"]::-moz-range-thumb {
          width: 16px;
          height: 16px;
          background: #fff;
          border-radius: 50%;
          cursor: pointer;
          border: 2px solid #4CAF50;
        }
      `}</style>
    </div>
  )
}

export default InterventionBuilder
