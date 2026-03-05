/**
 * SimulationRunner Component
 *
 * "Run Simulation" button with:
 * - Validation (country selected, interventions added)
 * - Loading state with spinner
 * - Error handling
 * - Success triggers visualization updates
 */

import { useCallback, useState, useMemo, useRef, useEffect } from 'react'
import { useSimulationStore } from '../../stores/simulationStore'
import { SIMULATION_YEAR_MAX, SIMULATION_YEAR_MIN } from '../../constants/time'
import { REGION_DISPLAY_NAMES } from '../../constants/regions'
import {
  generateSummaryCSV,
  generateTimelineCSV,
  downloadCSV,
  copyCSVToClipboard,
  makeCSVFilename
} from '../../utils/csvExport'

// ============================================
// Main Component
// ============================================

export function SimulationRunner() {
  const {
    selectedCountry,
    interventions,
    isSimulating,
    temporalResults,
    error,
    simulationStartYear,
    simulationEndYear,
    runTemporalSimulation,
    clearResults,
    clearError,
    setSimulationStartYear,
    setSimulationEndYear,
    savedScenarios,
    saveScenario,
    loadScenario,
    deleteScenario,
    selectedStratum,
    selectedRegion,
    targetVisibleEffects,
    setTargetVisibleEffects
  } = useSimulationStore()

  const [showSaveInput, setShowSaveInput] = useState(false)
  const [scenarioName, setScenarioName] = useState('')
  const [showScenarioList, setShowScenarioList] = useState(false)
  const [activeThumb, setActiveThumb] = useState<'start' | 'end' | null>(null)
  const scenarioListRef = useRef<HTMLDivElement>(null)

  // Close scenario dropdown on outside click
  useEffect(() => {
    if (!showScenarioList) return
    const handler = (e: MouseEvent) => {
      if (scenarioListRef.current && !scenarioListRef.current.contains(e.target as Node)) {
        setShowScenarioList(false)
      }
    }
    document.addEventListener('mousedown', handler)
    return () => document.removeEventListener('mousedown', handler)
  }, [showScenarioList])

  const handleSave = useCallback(() => {
    const name = scenarioName.trim() || `${selectedCountry} — ${new Date().toLocaleDateString()}`
    saveScenario(name)
    setScenarioName('')
    setShowSaveInput(false)
  }, [scenarioName, selectedCountry, saveScenario])

  // Handle run simulation
  const handleRunSimulation = useCallback(async () => {
    clearError()
    await runTemporalSimulation()
  }, [runTemporalSimulation, clearError])

  // Handle clear results
  const handleClearResults = useCallback(() => {
    clearResults()
  }, [clearResults])

  // Derive scope label from current graph view
  const scopeLabel = selectedCountry
    ? selectedCountry
    : selectedRegion
      ? `Region: ${REGION_DISPLAY_NAMES[selectedRegion] ?? selectedRegion}`
    : selectedStratum === 'unified'
      ? 'Global (unified)'
      : `${selectedStratum.charAt(0).toUpperCase() + selectedStratum.slice(1)} countries`

  // Determine button state and message
  const getButtonState = () => {
    if (isSimulating) {
      return { disabled: true, text: 'Simulating...', className: 'loading' }
    }
    if (interventions.length === 0) {
      return { disabled: true, text: 'Add Interventions', className: 'disabled' }
    }
    if (interventions.some(i => !i.indicator)) {
      return { disabled: true, text: 'Complete Interventions', className: 'disabled' }
    }
    return { disabled: false, text: 'Run Simulation', className: 'ready' }
  }

  const buttonState = getButtonState()

  // Count valid interventions
  const validInterventions = interventions.filter(i => i.indicator).length
  const isThumbOverlap = Math.abs(simulationEndYear - simulationStartYear) <= 1

  return (
    <div className="simulation-runner">
      {/* Status Summary */}
      <div className="status-summary">
        <div className="status-item">
          <span className="status-label">Scope:</span>
          <span className="status-value set">
            {scopeLabel}
          </span>
        </div>
        <div className="status-item">
          <span className="status-label">Interventions:</span>
          <span className={`status-value ${validInterventions > 0 ? 'set' : 'unset'}`}>
            {validInterventions} configured
          </span>
        </div>
      </div>

      {/* Simulation Timeline Range — dual thumb on single track */}
      {(
        <div className="sim-timeline-range">
          <div className="sim-timeline-label">
            <span>Simulation Range</span>
            <span className="sim-timeline-years">
              {simulationStartYear} → {simulationEndYear} ({simulationEndYear - simulationStartYear}yr)
            </span>
          </div>
          <div className="sim-dual-slider">
            <span className="sim-timeline-bound">{SIMULATION_YEAR_MIN}</span>
            <div className={`sim-dual-track ${isThumbOverlap ? 'overlap' : ''}`} role="group" aria-label="Simulation year range">
              {/* Filled region between thumbs */}
              <div
                className="sim-dual-fill"
                style={{
                  left: `${((simulationStartYear - SIMULATION_YEAR_MIN) / (SIMULATION_YEAR_MAX - SIMULATION_YEAR_MIN)) * 100}%`,
                  right: `${((SIMULATION_YEAR_MAX - simulationEndYear) / (SIMULATION_YEAR_MAX - SIMULATION_YEAR_MIN)) * 100}%`
                }}
              />
              <input
                id="sim-start-year"
                name="sim-start-year"
                type="range"
                min={SIMULATION_YEAR_MIN}
                max={SIMULATION_YEAR_MAX}
                value={simulationStartYear}
                onChange={(e) => {
                  const v = Number(e.target.value)
                  if (v < simulationEndYear) setSimulationStartYear(v)
                }}
                onMouseDown={() => setActiveThumb('start')}
                onTouchStart={() => setActiveThumb('start')}
                onFocus={() => setActiveThumb('start')}
                onBlur={() => setActiveThumb(prev => (prev === 'start' ? null : prev))}
                className={`sim-thumb sim-thumb-start ${activeThumb === 'start' ? 'sim-thumb-active' : ''}`}
                aria-label="Simulation start year"
                aria-valuemin={SIMULATION_YEAR_MIN}
                aria-valuemax={simulationEndYear - 1}
                aria-valuenow={simulationStartYear}
                aria-valuetext={`Start year ${simulationStartYear}`}
              />
              <input
                id="sim-end-year"
                name="sim-end-year"
                type="range"
                min={SIMULATION_YEAR_MIN}
                max={SIMULATION_YEAR_MAX}
                value={simulationEndYear}
                onChange={(e) => {
                  const v = Number(e.target.value)
                  if (v > simulationStartYear) setSimulationEndYear(v)
                }}
                onMouseDown={() => setActiveThumb('end')}
                onTouchStart={() => setActiveThumb('end')}
                onFocus={() => setActiveThumb('end')}
                onBlur={() => setActiveThumb(prev => (prev === 'end' ? null : prev))}
                className={`sim-thumb sim-thumb-end ${activeThumb === 'end' ? 'sim-thumb-active' : ''}`}
                aria-label="Simulation end year"
                aria-valuemin={simulationStartYear + 1}
                aria-valuemax={SIMULATION_YEAR_MAX}
                aria-valuenow={simulationEndYear}
                aria-valuetext={`End year ${simulationEndYear}`}
              />
            </div>
            <span className="sim-timeline-bound">{SIMULATION_YEAR_MAX}</span>
          </div>
        </div>
      )}

      {/* Effects to Show */}
      <div className="effects-count-row">
        <div className="effects-count-label">
          <span>Effects to show</span>
          <span className="effects-count-value">{targetVisibleEffects}</span>
        </div>
        <input
          id="effects-count"
          name="effects-count"
          type="range"
          min={3}
          max={50}
          step={1}
          value={targetVisibleEffects}
          onChange={(e) => setTargetVisibleEffects(Number(e.target.value))}
          className="effects-count-slider"
          aria-label="Number of effects to display"
          aria-valuemin={3}
          aria-valuemax={50}
          aria-valuenow={targetVisibleEffects}
          aria-valuetext={`Show ${targetVisibleEffects} effects`}
        />
      </div>

      {/* Run Button */}
      <button
        className={`run-btn ${buttonState.className}`}
        onClick={handleRunSimulation}
        disabled={buttonState.disabled}
        aria-busy={isSimulating}
      >
        {isSimulating && <span className="spinner" />}
        {buttonState.text}
      </button>

      {/* Scenario Save/Load */}
      {(savedScenarios.length > 0 || (selectedCountry && interventions.length > 0)) && (
        <div className="scenario-actions">
          {showSaveInput ? (
            <div className="scenario-save-row">
              <input
                type="text"
                id="scenario-name"
                name="scenario-name"
                className="scenario-name-input"
                placeholder="Scenario name..."
                aria-label="Scenario name"
                value={scenarioName}
                onChange={(e) => setScenarioName(e.target.value)}
                onKeyDown={(e) => { if (e.key === 'Enter') handleSave(); if (e.key === 'Escape') setShowSaveInput(false); }}
                autoFocus
              />
              <button className="scenario-btn save" onClick={handleSave}>Save</button>
              <button className="scenario-btn cancel" onClick={() => setShowSaveInput(false)} aria-label="Cancel scenario save">×</button>
            </div>
          ) : (
            <div className="scenario-btn-row">
              {selectedCountry && interventions.length > 0 && (
                <button className="scenario-btn save" onClick={() => setShowSaveInput(true)}>
                  💾 Save
                </button>
              )}
              {savedScenarios.length > 0 && (
                <div className="scenario-dropdown-wrap" ref={scenarioListRef}>
                  <button
                    className="scenario-btn load"
                    onClick={() => setShowScenarioList(!showScenarioList)}
                    aria-expanded={showScenarioList}
                    aria-controls="saved-scenarios-list"
                  >
                    📂 Load ({savedScenarios.length})
                  </button>
                  {showScenarioList && (
                    <div className="scenario-dropdown" id="saved-scenarios-list" role="listbox" aria-label="Saved scenarios">
                      {savedScenarios.map((s) => (
                        <div key={s.id} className="scenario-item">
                          <div
                            className="scenario-item-main"
                            onClick={() => { loadScenario(s.id); setShowScenarioList(false); }}
                            onKeyDown={(e) => {
                              if (e.key === 'Enter' || e.key === ' ') {
                                e.preventDefault()
                                loadScenario(s.id)
                                setShowScenarioList(false)
                              }
                            }}
                            role="option"
                            tabIndex={0}
                          >
                            <span className="scenario-item-name">{s.name}</span>
                            <span className="scenario-item-meta">
                              {s.country} · {s.interventions.length} int · {s.simulationStartYear}–{s.simulationEndYear}
                            </span>
                          </div>
                          <button
                            className="scenario-delete-btn"
                            onClick={(e) => { e.stopPropagation(); deleteScenario(s.id); }}
                            title="Delete"
                            aria-label={`Delete scenario ${s.name}`}
                          >×</button>
                        </div>
                      ))}
                    </div>
                  )}
                </div>
              )}
            </div>
          )}
        </div>
      )}

      {/* Error Display */}
      {error && (
        <div className="runner-error">
          <span className="error-icon">!</span>
          <span className="error-text">{error}</span>
          <button className="dismiss-btn" onClick={clearError} aria-label="Dismiss simulation error">×</button>
        </div>
      )}

      {/* Results Status + Expandable Details */}
      {temporalResults && !error && (
        <TemporalResultsDropdown
          temporalResults={temporalResults}
          onClear={handleClearResults}
        />
      )}

      <style>{`
        .simulation-runner {
        }

        .status-summary {
          display: flex;
          flex-direction: column;
          gap: 4px;
          margin-bottom: 10px;
        }

        .status-item {
          display: flex;
          justify-content: space-between;
          font-size: 11px;
        }

        .status-label {
          color: #767676;
        }

        .status-value {
          font-weight: 500;
        }

        .status-value.set {
          color: #4caf50;
        }

        .status-value.unset {
          color: #bbb;
        }

        .run-btn {
          width: 100%;
          padding: 10px 14px;
          border: none;
          border-radius: 6px;
          font-size: 13px;
          font-weight: 600;
          cursor: pointer;
          transition: all 0.2s;
          display: flex;
          align-items: center;
          justify-content: center;
          gap: 8px;
        }

        .run-btn.ready {
          background: #3B82F6;
          color: white;
        }

        .run-btn.ready:hover {
          background: #2563EB;
          box-shadow: 0 2px 8px rgba(59,130,246,0.3);
        }

        .run-btn.disabled {
          background: #f0f0f0;
          color: #bbb;
          cursor: not-allowed;
        }

        .run-btn.loading {
          background: #93C5FD;
          color: #1E40AF;
          cursor: wait;
        }

        .spinner {
          width: 14px;
          height: 14px;
          border: 2px solid rgba(30,64,175,0.3);
          border-top-color: #1E40AF;
          border-radius: 50%;
          animation: spin 0.8s linear infinite;
        }

        @keyframes spin {
          to { transform: rotate(360deg); }
        }

        .runner-error {
          display: flex;
          align-items: center;
          gap: 6px;
          margin-top: 10px;
          padding: 8px;
          background: #FFEBEE;
          border: 1px solid #FFCDD2;
          border-radius: 4px;
        }

        .error-icon {
          width: 18px;
          height: 18px;
          background: #f44336;
          color: #fff;
          border-radius: 50%;
          display: flex;
          align-items: center;
          justify-content: center;
          font-size: 11px;
          font-weight: bold;
          flex-shrink: 0;
        }

        .error-text {
          flex: 1;
          font-size: 11px;
          color: #C62828;
        }

        .dismiss-btn {
          background: none;
          border: none;
          color: #EF9A9A;
          font-size: 16px;
          cursor: pointer;
          padding: 0;
          line-height: 1;
        }

        .dismiss-btn:hover {
          color: #C62828;
        }

        .results-status {
          margin-top: 10px;
          padding: 8px;
          background: #E8F5E9;
          border: 1px solid #C8E6C9;
          border-radius: 4px;
          display: flex;
          flex-direction: column;
          gap: 6px;
        }

        .results-summary {
          display: flex;
          align-items: center;
          gap: 6px;
          font-size: 12px;
          color: #2E7D32;
        }

        .check-icon {
          font-size: 14px;
        }

        .results-detail {
          font-size: 11px;
          color: #666;
        }

        .clear-btn {
          width: 100%;
          padding: 5px 10px;
          background: white;
          border: 1px solid #C8E6C9;
          border-radius: 4px;
          color: #666;
          font-size: 11px;
          cursor: pointer;
          transition: all 0.2s;
        }

        .clear-btn:hover {
          background: #eef0f6;
          border-color: #A5D6A7;
        }

        .sim-timeline-range {
          margin-bottom: 10px;
          padding: 8px;
          background: #f8f9ff;
          border: 1px solid #e0e4f0;
          border-radius: 5px;
        }

        .sim-timeline-label {
          display: flex;
          justify-content: space-between;
          align-items: center;
          font-size: 11px;
          color: #555;
          margin-bottom: 6px;
        }

        .sim-timeline-years {
          font-weight: 600;
          color: #3B82F6;
          font-size: 11px;
          font-family: 'JetBrains Mono', monospace;
        }

        .sim-dual-slider {
          display: flex;
          align-items: center;
          gap: 6px;
        }

        .sim-timeline-bound {
          font-size: 10px;
          color: #767676;
          font-family: 'JetBrains Mono', monospace;
          min-width: 28px;
          text-align: center;
          flex-shrink: 0;
        }

        .sim-dual-track {
          position: relative;
          flex: 1;
          height: 20px;
        }

        .sim-dual-track::before {
          content: '';
          position: absolute;
          top: 50%;
          left: 0;
          right: 0;
          height: 4px;
          transform: translateY(-50%);
          background: #dde1f0;
          border-radius: 2px;
        }

        .sim-dual-fill {
          position: absolute;
          top: 50%;
          height: 4px;
          transform: translateY(-50%);
          background: #3B82F6;
          border-radius: 2px;
          pointer-events: none;
        }

        .sim-thumb {
          position: absolute;
          top: 0;
          left: 0;
          width: 100%;
          height: 100%;
          -webkit-appearance: none;
          appearance: none;
          background: transparent;
          pointer-events: none;
          /* outline handled by :focus-visible */
          margin: 0;
          padding: 0;
          z-index: 2;
        }

        .sim-thumb.sim-thumb-active {
          z-index: 5;
        }

        .sim-thumb.sim-thumb-end {
          z-index: 3;
        }

        .sim-thumb::-webkit-slider-thumb {
          -webkit-appearance: none;
          width: 4px;
          height: 16px;
          background: #3B82F6;
          border-radius: 1px;
          cursor: pointer;
          pointer-events: auto;
          box-shadow: 0 0 0 3px rgba(59,130,246,0.15);
          transition: box-shadow 0.15s;
        }

        .sim-thumb::-moz-range-thumb {
          width: 4px;
          height: 16px;
          background: #3B82F6;
          border-radius: 1px;
          border: none;
          cursor: pointer;
          pointer-events: auto;
          box-shadow: 0 0 0 3px rgba(59,130,246,0.15);
        }

        .sim-thumb::-webkit-slider-thumb:hover {
          box-shadow: 0 0 0 5px rgba(59,130,246,0.25);
        }

        .sim-thumb::-moz-range-thumb:hover {
          box-shadow: 0 0 0 5px rgba(59,130,246,0.25);
        }

        .sim-dual-track.overlap .sim-thumb-start::-webkit-slider-thumb,
        .sim-dual-track.overlap .sim-thumb-start::-moz-range-thumb {
          background: #1E40AF;
        }

        .sim-dual-track.overlap .sim-thumb-end::-webkit-slider-thumb,
        .sim-dual-track.overlap .sim-thumb-end::-moz-range-thumb {
          background: #60A5FA;
        }

        .sim-thumb:focus-visible::-webkit-slider-thumb {
          box-shadow: 0 0 0 6px rgba(59,130,246,0.3);
        }

        .sim-thumb:focus-visible::-moz-range-thumb {
          box-shadow: 0 0 0 6px rgba(59,130,246,0.3);
        }

        .effects-count-row {
          margin-bottom: 10px;
          padding: 8px;
          background: #f8f9ff;
          border: 1px solid #e0e4f0;
          border-radius: 5px;
        }

        .effects-count-label {
          display: flex;
          justify-content: space-between;
          align-items: center;
          font-size: 11px;
          color: #555;
          margin-bottom: 6px;
        }

        .effects-count-value {
          font-weight: 600;
          color: #3B82F6;
          font-family: 'JetBrains Mono', monospace;
        }

        .effects-count-slider {
          width: 100%;
          height: 4px;
          -webkit-appearance: none;
          appearance: none;
          background: #dde1f0;
          border-radius: 2px;
          /* outline handled by :focus-visible */
        }

        .effects-count-slider::-webkit-slider-thumb {
          -webkit-appearance: none;
          width: 14px;
          height: 14px;
          background: #3B82F6;
          border-radius: 50%;
          cursor: pointer;
          box-shadow: 0 0 0 3px rgba(59,130,246,0.15);
        }

        .effects-count-slider::-moz-range-thumb {
          width: 14px;
          height: 14px;
          background: #3B82F6;
          border-radius: 50%;
          border: none;
          cursor: pointer;
          box-shadow: 0 0 0 3px rgba(59,130,246,0.15);
        }

        .effects-count-slider::-webkit-slider-thumb:hover {
          box-shadow: 0 0 0 5px rgba(59,130,246,0.25);
        }

        .effects-count-slider::-moz-range-thumb:hover {
          box-shadow: 0 0 0 5px rgba(59,130,246,0.25);
        }

        .effects-count-slider:focus-visible {
          outline: 2px solid #3B82F6;
          outline-offset: 2px;
        }

        .scenario-actions {
          margin-top: 8px;
        }

        .scenario-btn-row {
          display: flex;
          gap: 6px;
        }

        .scenario-save-row {
          display: flex;
          gap: 4px;
          align-items: center;
        }

        .scenario-name-input {
          flex: 1;
          padding: 4px 8px;
          border: 1px solid #d0d5e0;
          border-radius: 4px;
          font-size: 11px;
          /* outline handled by :focus-visible */
        }

        .scenario-name-input:focus {
          border-color: #3B82F6;
        }

        .scenario-btn {
          padding: 4px 10px;
          border: 1px solid #d0d5e0;
          border-radius: 4px;
          background: #f0f2f8;
          font-size: 11px;
          cursor: pointer;
          white-space: nowrap;
          transition: all 0.15s;
        }

        .scenario-btn:hover {
          background: #e2e6ee;
          border-color: #bbb;
        }

        .scenario-btn.save {
          color: #2E7D32;
          border-color: #C8E6C9;
        }

        .scenario-btn.load {
          color: #1565C0;
          border-color: #BBDEFB;
        }

        .scenario-btn.cancel {
          color: #767676;
          padding: 4px 6px;
          font-size: 14px;
          line-height: 1;
        }

        .scenario-dropdown-wrap {
          position: relative;
        }

        .scenario-dropdown {
          position: absolute;
          bottom: 100%;
          left: 0;
          min-width: 240px;
          max-height: 200px;
          overflow-y: auto;
          background: white;
          border: 1px solid #d0d5e0;
          border-radius: 6px;
          box-shadow: 0 -4px 16px rgba(0,0,0,0.12);
          z-index: 300;
          margin-bottom: 4px;
        }

        .scenario-item {
          display: flex;
          align-items: center;
          border-bottom: 1px solid #f0f0f0;
        }

        .scenario-item:last-child {
          border-bottom: none;
        }

        .scenario-item-main {
          flex: 1;
          padding: 8px 10px;
          cursor: pointer;
          display: flex;
          flex-direction: column;
          gap: 2px;
        }

        .scenario-item-main:hover {
          background: #f0f7ff;
        }

        .scenario-item-main:focus-visible,
        .run-btn:focus-visible,
        .dismiss-btn:focus-visible,
        .scenario-btn:focus-visible,
        .clear-btn:focus-visible {
          outline: 2px solid #3B82F6;
          outline-offset: 2px;
        }

        .scenario-item-name {
          font-size: 12px;
          font-weight: 500;
          color: #333;
        }

        .scenario-item-meta {
          font-size: 10px;
          color: #767676;
        }

        .scenario-delete-btn {
          background: none;
          border: none;
          color: #bcc3d4;
          font-size: 16px;
          padding: 4px 8px;
          cursor: pointer;
          line-height: 1;
        }

        .scenario-delete-btn:hover {
          color: #f44336;
        }
      `}</style>
    </div>
  )
}

// ============================================
// Temporal Results Dropdown
// ============================================

interface TemporalResultsDropdownProps {
  temporalResults: {
    base_year: number
    horizon_years: number
    effects: Record<string, Record<string, { baseline: number; simulated: number; absolute_change: number; percent_change: number }>>
  }
  onClear: () => void
}

function TemporalResultsDropdown({ temporalResults, onClear }: TemporalResultsDropdownProps) {
  const [isExpanded, setIsExpanded] = useState(true)
  const [copyFeedback, setCopyFeedback] = useState(false)
  const [showCSVMenu, setShowCSVMenu] = useState(false)
  const csvMenuRef = useRef<HTMLDivElement>(null)
  const { indicators, targetVisibleEffects, setTargetVisibleEffects, highlightedIndicator, setHighlightedIndicator, selectedCountry, interventions, activeTemplate } = useSimulationStore()
  const resultsRef = useRef<HTMLDivElement>(null)

  // Auto-scroll results into view when they first appear
  useEffect(() => {
    if (resultsRef.current) {
      resultsRef.current.scrollIntoView({ behavior: 'smooth', block: 'nearest' })
    }
  }, [])

  // Close CSV dropdown on outside click
  useEffect(() => {
    if (!showCSVMenu) return
    const handler = (e: MouseEvent) => {
      if (csvMenuRef.current && !csvMenuRef.current.contains(e.target as Node)) {
        setShowCSVMenu(false)
      }
    }
    document.addEventListener('mousedown', handler)
    return () => document.removeEventListener('mousedown', handler)
  }, [showCSVMenu])

  const handleCopyCSV = useCallback(async () => {
    const csv = generateSummaryCSV(temporalResults, interventions, selectedCountry, indicators, activeTemplate)
    const ok = await copyCSVToClipboard(csv)
    if (ok) {
      setCopyFeedback(true)
      setTimeout(() => setCopyFeedback(false), 2000)
    }
  }, [temporalResults, interventions, selectedCountry, indicators, activeTemplate])

  const handleDownloadSummary = useCallback(() => {
    const csv = generateSummaryCSV(temporalResults, interventions, selectedCountry, indicators, activeTemplate)
    downloadCSV(csv, makeCSVFilename(selectedCountry, 'summary'))
    setShowCSVMenu(false)
  }, [temporalResults, interventions, selectedCountry, indicators, activeTemplate])

  const handleDownloadTimeline = useCallback(() => {
    const csv = generateTimelineCSV(temporalResults, interventions, selectedCountry, indicators, activeTemplate)
    downloadCSV(csv, makeCSVFilename(selectedCountry, 'timeline'))
    setShowCSVMenu(false)
  }, [temporalResults, interventions, selectedCountry, indicators, activeTemplate])

  const tableId = 'temporal-results-table'

  // Build indicator name lookup
  const indicatorNames = useMemo(() => {
    const map = new Map<string, string>()
    indicators.forEach(ind => map.set(ind.id, ind.label))
    return map
  }, [indicators])

  // Get final year effects, filtered by percentile, sorted by magnitude
  const { affectedCount, totalNonZero, rows } = useMemo(() => {
    const yearKeys = Object.keys(temporalResults.effects).sort()
    const finalYearKey = yearKeys[yearKeys.length - 1]
    const finalEffects = finalYearKey ? temporalResults.effects[finalYearKey] : {}

    const allRows = Object.entries(finalEffects)
      .map(([id, effect]) => {
        const e = effect as Record<string, number>
        return {
          id,
          name: indicatorNames.get(id) || id,
          baseline: e.baseline,
          simulated: e.simulated,
          absoluteChange: e.absolute_change,
          percentChange: e.percent_change,
          absPct: Math.abs(e.percent_change),
          absChange: Math.abs(e.absolute_change)
        }
      })
      .filter(row => row.absChange > 0.001 && Math.abs(row.baseline) > 0.01)
      .sort((a, b) => b.absPct - a.absPct)

    const totalNonZero = allRows.length

    // Filter to top N by magnitude (matches targetVisibleEffects count)
    if (allRows.length > targetVisibleEffects) {
      const filtered = allRows.slice(0, targetVisibleEffects)
      return { affectedCount: filtered.length, totalNonZero, rows: filtered }
    }

    return { affectedCount: allRows.length, totalNonZero, rows: allRows }
  }, [temporalResults, indicatorNames, targetVisibleEffects])

  const formatVal = (v: number) => {
    if (isNaN(v)) return 'N/A'
    if (Math.abs(v) >= 1e9) return `${(v / 1e9).toFixed(1)}B`
    if (Math.abs(v) >= 1e6) return `${(v / 1e6).toFixed(1)}M`
    if (Math.abs(v) >= 1e3) return `${(v / 1e3).toFixed(1)}K`
    if (Math.abs(v) < 0.01 && v !== 0) return v.toExponential(1)
    return v.toFixed(2)
  }

  /**
   * Format the change column based on indicator context.
   * For indicators where baseline and simulated are both small numbers
   * (percentages, ratios, indices), show "baseline → simulated" which
   * is more intuitive than a large percent change.
   * e.g., "6.4 → 29.6" is clearer than "+360%"
   */
  const formatChange = (row: { baseline: number; simulated: number; absoluteChange: number; percentChange: number }) => {
    const absPct = Math.abs(row.percentChange)
    const absBase = Math.abs(row.baseline)

    // For small-valued indicators (ratios, percentages, indices) where
    // % change looks alarming, show level change instead
    if (absPct > 100 && absBase < 1000) {
      const sign = row.absoluteChange >= 0 ? '+' : ''
      return `${sign}${formatVal(row.absoluteChange)}`
    }

    return `${row.percentChange >= 0 ? '+' : ''}${row.percentChange.toFixed(1)}%`
  }

  const handleRowClick = useCallback((id: string) => {
    setHighlightedIndicator(highlightedIndicator === id ? null : id)
  }, [highlightedIndicator, setHighlightedIndicator])

  return (
    <div className="results-status" ref={resultsRef}>
      {/* Header row — always visible, clickable */}
      <button
        type="button"
        className="results-dropdown-header"
        onClick={() => setIsExpanded(!isExpanded)}
        aria-expanded={isExpanded}
        aria-controls={tableId}
      >
        <div style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
          <span className="check-icon">✓</span>
          <span style={{ fontSize: 12, color: '#2E7D32' }}>
            {affectedCount} of {totalNonZero} effects shown
          </span>
          <span className={`dropdown-chevron ${isExpanded ? 'open' : ''}`}>▾</span>
        </div>
        <span style={{ fontSize: 10, color: '#767676' }}>
          {temporalResults.base_year} → {temporalResults.base_year + temporalResults.horizon_years}
        </span>
      </button>

      {/* Export actions */}
      <div className="export-actions-row">
        <button
          className="export-btn copy-btn"
          onClick={handleCopyCSV}
          title="Copy summary CSV to clipboard"
          aria-label="Copy results to clipboard"
        >
          {copyFeedback ? '✓ Copied' : '📋 Copy'}
        </button>
        <div className="csv-dropdown-wrap" ref={csvMenuRef}>
          <button
            className="export-btn csv-btn"
            onClick={() => setShowCSVMenu(!showCSVMenu)}
            title="Download CSV"
            aria-expanded={showCSVMenu}
            aria-label="Download CSV export"
          >
            ⬇ CSV
          </button>
          {showCSVMenu && (
            <div className="csv-dropdown-menu" role="menu">
              <button className="csv-menu-item" onClick={handleDownloadSummary} role="menuitem">
                Summary (final year)
              </button>
              <button className="csv-menu-item" onClick={handleDownloadTimeline} role="menuitem">
                Full Timeline (all years)
              </button>
            </div>
          )}
        </div>
      </div>

      {/* Filter slider — always visible when results exist */}
      <div className="effect-filter-row">
        <label className="effect-filter-label" htmlFor="effect-filter">
          Show: top {affectedCount} of {totalNonZero}
        </label>
        <input
          id="effect-filter"
          name="effect-filter"
          type="range"
          min={3}
          max={50}
          step={1}
          value={targetVisibleEffects}
          onChange={(e) => setTargetVisibleEffects(Number(e.target.value))}
          className="effect-filter-slider"
          aria-label="Number of effects to display"
          aria-valuemin={3}
          aria-valuemax={50}
          aria-valuenow={targetVisibleEffects}
          aria-valuetext={`Show top ${targetVisibleEffects} effects`}
        />
      </div>

      {/* Expanded table */}
      {isExpanded && (
        <div className="dropdown-table-wrapper" id={tableId}>
          <table className="dropdown-table" aria-label="Simulation results">
            <caption className="sr-only">
              Simulation effects showing {affectedCount} of {totalNonZero} affected indicators
            </caption>
            <thead>
              <tr>
                <th scope="col">Indicator</th>
                <th scope="col">Baseline</th>
                <th scope="col">Final</th>
                <th scope="col">Change</th>
              </tr>
            </thead>
            <tbody>
              {rows.map(row => (
                <tr
                  key={row.id}
                  onClick={() => handleRowClick(row.id)}
                  onKeyDown={(e) => {
                    if (e.key === 'Enter' || e.key === ' ') {
                      e.preventDefault()
                      handleRowClick(row.id)
                    }
                  }}
                  tabIndex={0}
                  role="row"
                  aria-selected={highlightedIndicator === row.id}
                  className={highlightedIndicator === row.id ? 'dt-row-active' : ''}
                  style={{ cursor: 'pointer' }}
                >
                  <td className="dt-name" title={row.name}>{row.name}</td>
                  <td className="dt-val">{formatVal(row.baseline)}</td>
                  <td className="dt-val">{formatVal(row.simulated)}</td>
                  <td className={`dt-change ${row.percentChange >= 0 ? 'pos' : 'neg'}`}>
                    {formatChange(row)}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      <button className="clear-btn" onClick={onClear} aria-label="Clear simulation results">
        Clear Results
      </button>

      <style>{`
        .results-dropdown-header {
          display: flex;
          justify-content: space-between;
          align-items: center;
          cursor: pointer;
          user-select: none;
          width: 100%;
          border: none;
          background: transparent;
          padding: 0;
          text-align: left;
        }

        .results-dropdown-header:hover {
          opacity: 0.8;
        }

        .dropdown-chevron {
          font-size: 12px;
          color: #767676;
          transition: transform 0.2s;
          display: inline-block;
        }

        .dropdown-chevron.open {
          transform: rotate(180deg);
        }

        .dropdown-table-wrapper {
          max-height: 280px;
          overflow-y: auto;
          margin-top: 8px;
          border-top: 1px solid #C8E6C9;
          padding-top: 4px;
        }

        .dropdown-table {
          width: 100%;
          border-collapse: collapse;
          font-size: 10px;
        }

        .dropdown-table th {
          font-size: 9px;
          font-weight: 600;
          color: #767676;
          text-transform: uppercase;
          letter-spacing: 0.3px;
          padding: 4px 3px;
          text-align: left;
          position: sticky;
          top: 0;
          background: #E8F5E9;
          border-bottom: 1px solid #C8E6C9;
        }

        .dropdown-table td {
          padding: 3px;
          border-bottom: 1px solid #f0f0f0;
        }

        .dropdown-table tbody tr:hover {
          background: rgba(76,175,80,0.08);
        }

        .dropdown-table tbody tr:focus-visible {
          outline: 2px solid #3B82F6;
          outline-offset: -2px;
        }

        .dropdown-table tbody tr.dt-row-active {
          background: rgba(59,130,246,0.12);
        }

        .dropdown-table tbody tr.dt-row-active:hover {
          background: rgba(59,130,246,0.18);
        }

        .dt-name {
          max-width: 180px;
          overflow: hidden;
          text-overflow: ellipsis;
          white-space: nowrap;
          color: #444;
        }

        .dt-val {
          font-family: 'JetBrains Mono', monospace;
          text-align: right;
          color: #666;
          white-space: nowrap;
        }

        .dt-change {
          font-family: 'JetBrains Mono', monospace;
          text-align: right;
          font-weight: 600;
          white-space: nowrap;
        }

        .dt-change.pos { color: #4caf50; }
        .dt-change.neg { color: #f44336; }

        .effect-filter-row {
          display: flex;
          align-items: center;
          gap: 8px;
          margin-top: 6px;
          padding: 4px 0;
        }

        .effect-filter-label {
          font-size: 10px;
          color: #666;
          white-space: nowrap;
          min-width: 72px;
        }

        .effect-filter-slider {
          flex: 1;
          height: 3px;
          -webkit-appearance: none;
          appearance: none;
          background: #C8E6C9;
          border-radius: 2px;
          /* outline handled by :focus-visible */
        }

        .effect-filter-slider::-webkit-slider-thumb {
          -webkit-appearance: none;
          width: 12px;
          height: 12px;
          background: #4caf50;
          border-radius: 50%;
          cursor: pointer;
        }

        .effect-filter-slider::-moz-range-thumb {
          width: 12px;
          height: 12px;
          background: #4caf50;
          border-radius: 50%;
          border: none;
          cursor: pointer;
        }

        .results-dropdown-header:focus-visible,
        .effect-filter-slider:focus-visible,
        .clear-btn:focus-visible,
        .export-btn:focus-visible,
        .csv-menu-item:focus-visible {
          outline: 2px solid #3B82F6;
          outline-offset: 2px;
        }

        .export-actions-row {
          display: flex;
          gap: 4px;
          margin-top: 6px;
        }

        .export-btn {
          padding: 3px 8px;
          border: 1px solid #C8E6C9;
          border-radius: 4px;
          background: white;
          font-size: 10px;
          cursor: pointer;
          color: #555;
          transition: all 0.3s ease;
          white-space: nowrap;
        }

        .export-btn.nudge {
          border-color: rgba(0, 229, 255, 0.6);
          color: #00ACC1;
          background-image: linear-gradient(
            110deg,
            transparent 25%,
            rgba(255, 255, 255, 0.4) 37%,
            rgba(255, 255, 255, 0.7) 50%,
            rgba(255, 255, 255, 0.4) 63%,
            transparent 75%
          );
          background-color: rgba(0, 229, 255, 0.1);
          background-size: 300% 100%;
          background-position: -200% center;
          box-shadow: 0 0 8px rgba(0, 229, 255, 0.5);
          animation: export-nudge-shimmer 1.2s cubic-bezier(0.4, 0, 0.2, 1) 3;
        }

        @keyframes export-nudge-shimmer {
          0% {
            transform: scale(1);
            background-position: -200% center;
            box-shadow: 0 0 6px rgba(0, 229, 255, 0.4);
          }
          15% {
            transform: scale(1.1);
            box-shadow: 0 0 14px rgba(0, 229, 255, 0.7);
          }
          30% {
            transform: scale(1);
            background-position: 200% center;
            box-shadow: 0 0 8px rgba(0, 229, 255, 0.5);
          }
          100% {
            transform: scale(1);
            background-position: 200% center;
            box-shadow: 0 0 6px rgba(0, 229, 255, 0.3);
          }
        }

        @media (prefers-reduced-motion: reduce) {
          .export-btn.nudge {
            animation: none;
            outline: 2px solid rgba(0, 229, 255, 0.7);
            outline-offset: 2px;
          }
        }

        .export-btn:hover {
          background: #f0f7ff;
          border-color: #90CAF9;
          color: #1565C0;
        }

        .export-btn.nudge:hover {
          background: rgba(0, 229, 255, 0.15);
        }

        .export-btn.copy-btn {
          min-width: 64px;
        }

        .csv-dropdown-wrap {
          position: relative;
        }

        .csv-dropdown-menu {
          position: absolute;
          top: 100%;
          left: 0;
          margin-top: 2px;
          min-width: 160px;
          background: white;
          border: 1px solid #d0d5e0;
          border-radius: 6px;
          box-shadow: 0 4px 12px rgba(0,0,0,0.12);
          z-index: 300;
          overflow: hidden;
        }

        .csv-menu-item {
          display: block;
          width: 100%;
          padding: 7px 10px;
          border: none;
          background: none;
          font-size: 11px;
          color: #444;
          cursor: pointer;
          text-align: left;
        }

        .csv-menu-item:hover {
          background: #f0f7ff;
          color: #1565C0;
        }

        .csv-menu-item + .csv-menu-item {
          border-top: 1px solid #f0f0f0;
        }
      `}</style>
    </div>
  )
}

export default SimulationRunner
