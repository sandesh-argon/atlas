/**
 * TimelinePlayer Component
 *
 * Timeline playback UI with three states:
 * - docked: Bottom left, just play button (matches simulate button style)
 * - expanded: Center, full timeline with scrubber
 * - collapsed: Center, play button + year only
 *
 * Flow: docked -> expanded (on play) -> collapsed (4s inactivity) -> docked (4s more)
 *
 * Supports click-and-drag scrubbing with smooth cursor tracking.
 * Based on common patterns from react-scrubber and similar implementations.
 * Sources: https://www.npmjs.com/package/react-scrubber, https://motion.dev/docs/react-drag
 */

import { useEffect, useRef, useState, useCallback } from 'react'
import { useSimulationStore } from '../../stores/simulationStore'
import { INTERVENTION_YEAR_MAX, SIM_MS_PER_YEAR } from '../../constants/time'
import { useResponsive } from '../../hooks/useResponsive'

type PlayerState = 'docked' | 'expanded' | 'collapsed' | 'docking'

interface TimelinePlayerProps {
  edgesLoading?: boolean;  // True while temporal edges are loading
  isLocalView?: boolean;   // True when in local/split view
}

export function TimelinePlayer({ edgesLoading = false, isLocalView = false }: TimelinePlayerProps) {
  const {
    selectedCountry,
    selectedRegion,
    isSimulating,
    historicalTimeline,
    timelineLoading,
    temporalResults,
    simulationRunToken,
    playbackMode,
    currentYearIndex,
    isPlaying,
    setCurrentYearIndex,
    play,
    pause,
    layoutReady
  } = useSimulationStore()

  const { isMobileLayout } = useResponsive()
  const intervalRef = useRef<number | null>(null)
  const [playerState, setPlayerState] = useState<PlayerState>('docked')
  const [pendingPlay, setPendingPlay] = useState(false)

  // Drag state
  const [isDragging, setIsDragging] = useState(false)
  const trackRef = useRef<HTMLDivElement>(null)
  const wasPlayingBeforeDrag = useRef(false)
  const waitingForLayoutRef = useRef(false)

  // Reset to docked when country/region changes
  useEffect(() => {
    setPlayerState('docked')
    setPendingPlay(false)
    waitingForLayoutRef.current = false
  }, [selectedCountry, selectedRegion])

  // Auto-expand only on true simulation runs (store token increments in applyResults)
  const prevRunTokenRef = useRef(simulationRunToken)

  useEffect(() => {
    const prevToken = prevRunTokenRef.current
    const isNewRun = (
      Boolean(temporalResults) &&
      playbackMode === 'simulation' &&
      simulationRunToken !== prevToken
    )
    prevRunTokenRef.current = simulationRunToken

    if (isNewRun) {
      // Expand timeline immediately; playback waits for layoutReady signal
      setPlayerState('expanded')
      waitingForLayoutRef.current = true
    }
  }, [temporalResults, playbackMode, simulationRunToken])

  // Start playback once layout signals ready (with brief pause to show intervention pulse)
  useEffect(() => {
    if (waitingForLayoutRef.current && layoutReady) {
      waitingForLayoutRef.current = false
      // Brief pause to let the intervention node pulse be visible before expanding
      const timer = setTimeout(() => play(), 800)
      return () => clearTimeout(timer)
    }
  }, [layoutReady, play])

  // Get years array based on mode
  const years = playbackMode === 'historical'
    ? (historicalTimeline?.years || [])
    : Array.from(
      { length: (temporalResults?.horizon_years || 10) + 1 },
      (_, i) => (temporalResults?.base_year || INTERVENTION_YEAR_MAX) + i
    )

  const maxIndex = years.length - 1
  const actualYear = years[currentYearIndex] || null

  // Speed per year tick:
  // Historical: 300ms unified (35 years), 700ms country-specific (~26 years)
  // Simulation: SIM_MS_PER_YEAR (shared constant, also drives pulse cycle)
  const MS_PER_YEAR = playbackMode === 'simulation'
    ? SIM_MS_PER_YEAR
    : ((selectedCountry || selectedRegion) ? 700 : 300)

  // Handle pending play after expansion animation completes
  useEffect(() => {
    if (pendingPlay && playerState === 'expanded') {
      // Wait for expansion animation (400ms) + small delay (100ms)
      const timer = setTimeout(() => {
        play()
        setPendingPlay(false)
      }, 500)
      return () => clearTimeout(timer)
    }
  }, [pendingPlay, playerState, play])

  // Playback interval effect - smooth linear progression
  // In local view, wait for edges to load before starting playback
  // Simulation year 1 gets an extra-long first tick so nodes can animate in
  const shouldPlay = isPlaying && years.length > 0 && !isDragging && !(isLocalView && edgesLoading)
  const firstTickTimerRef = useRef<number | null>(null)

  useEffect(() => {
    if (!shouldPlay) {
      if (intervalRef.current) { clearInterval(intervalRef.current); intervalRef.current = null }
      if (firstTickTimerRef.current) { clearTimeout(firstTickTimerRef.current); firstTickTimerRef.current = null }
      return
    }

    const tick = () => {
      const state = useSimulationStore.getState()
      const maxIdx = playbackMode === 'historical'
        ? (state.historicalTimeline?.years.length || 1) - 1
        : state.horizonYears

      if (state.currentYearIndex >= maxIdx) {
        state.pause()
        if (playbackMode === 'simulation') {
          state.markPlaybackFinished()
        }
      } else {
        state.setCurrentYearIndex(state.currentYearIndex + 1)
      }
    }

    // First tick: longer delay in sim mode so year-1 nodes can animate in
    const { currentYearIndex: startIdx } = useSimulationStore.getState()
    const isFirstSimTick = playbackMode === 'simulation' && startIdx <= 1
    const firstDelay = isFirstSimTick ? MS_PER_YEAR + SIM_MS_PER_YEAR : MS_PER_YEAR

    // setTimeout for first tick (variable delay), then setInterval for steady pace
    firstTickTimerRef.current = window.setTimeout(() => {
      tick()
      intervalRef.current = window.setInterval(tick, MS_PER_YEAR)
    }, firstDelay)

    return () => {
      if (firstTickTimerRef.current) { clearTimeout(firstTickTimerRef.current); firstTickTimerRef.current = null }
      if (intervalRef.current) { clearInterval(intervalRef.current); intervalRef.current = null }
    }
  }, [shouldPlay, playbackMode, MS_PER_YEAR])

  // Inactivity timers
  const collapseTimeoutRef = useRef<number | null>(null)
  const dockTimeoutRef = useRef<number | null>(null)

  const clearTimers = useCallback(() => {
    if (collapseTimeoutRef.current) {
      clearTimeout(collapseTimeoutRef.current)
      collapseTimeoutRef.current = null
    }
    if (dockTimeoutRef.current) {
      clearTimeout(dockTimeoutRef.current)
      dockTimeoutRef.current = null
    }
  }, [])

  // Start inactivity timer for collapse
  const startCollapseTimer = useCallback(() => {
    clearTimers()
    collapseTimeoutRef.current = window.setTimeout(() => {
      setPlayerState('collapsed')
    }, 4000)
  }, [clearTimers])

  // Handle state transitions based on playback and inactivity
  useEffect(() => {
    // Don't run timers while dragging
    if (isDragging) {
      clearTimers()
      return
    }

    clearTimers()

    if (isPlaying) {
      // Playing - stay expanded, no timers
      return
    }

    if (playerState === 'expanded') {
      if (isMobileLayout) {
        // Mobile: skip collapsed, go straight to docking
        collapseTimeoutRef.current = window.setTimeout(() => {
          setPlayerState('docking')
        }, 2000)
      } else {
        // Desktop: collapse after 4s
        collapseTimeoutRef.current = window.setTimeout(() => {
          setPlayerState('collapsed')
        }, 4000)
      }
    } else if (playerState === 'collapsed') {
      // Only allow docking when on the latest year
      // Otherwise stay collapsed to show the non-latest year
      if (currentYearIndex >= maxIndex) {
        dockTimeoutRef.current = window.setTimeout(() => {
          setPlayerState('docking')
        }, 4000)
      }
    } else if (playerState === 'docking') {
      // After docking animation completes (400ms), switch to docked
      const dockCompleteTimer = setTimeout(() => {
        setPlayerState('docked')
      }, 400)
      return () => clearTimeout(dockCompleteTimer)
    }

    return clearTimers
  }, [isPlaying, playerState, isDragging, clearTimers, currentYearIndex, maxIndex, isMobileLayout])

  // T key toggles timeline expanded/docked
  useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
      if (e.target instanceof HTMLInputElement || e.target instanceof HTMLTextAreaElement) return
      if (e.key !== 't' && e.key !== 'T') return
      if (!historicalTimeline) return
      e.preventDefault()

      if (playerState === 'docked' || playerState === 'docking') {
        // Open and auto-play
        if (currentYearIndex >= maxIndex) {
          setCurrentYearIndex(0)
        }
        setPlayerState('expanded')
        setPendingPlay(true)
        clearTimers()
      } else if (isPlaying) {
        // Pause and dock
        pause()
        setPlayerState('docked')
        clearTimers()
      } else {
        setPlayerState('docked')
        clearTimers()
      }
    }
    window.addEventListener('keydown', handleKeyDown)
    return () => window.removeEventListener('keydown', handleKeyDown)
  }, [playerState, historicalTimeline, clearTimers, currentYearIndex, maxIndex, isPlaying, pause, setCurrentYearIndex])

  // Calculate index from mouse/touch position
  const getIndexFromPosition = useCallback((clientX: number): number => {
    if (!trackRef.current || maxIndex <= 0) return 0
    const rect = trackRef.current.getBoundingClientRect()
    const x = clientX - rect.left
    const percentage = Math.max(0, Math.min(1, x / rect.width))
    return Math.round(percentage * maxIndex)
  }, [maxIndex])

  // Handle drag start (mouse)
  const handleMouseDown = useCallback((e: React.MouseEvent) => {
    if (isSimulating || maxIndex <= 0) return
    e.preventDefault()

    // Pause playback and remember state
    wasPlayingBeforeDrag.current = isPlaying
    if (isPlaying) pause()

    setIsDragging(true)
    const index = getIndexFromPosition(e.clientX)
    setCurrentYearIndex(index)
  }, [isSimulating, maxIndex, isPlaying, pause, getIndexFromPosition, setCurrentYearIndex])

  // Handle drag start (touch)
  const handleTouchStart = useCallback((e: React.TouchEvent) => {
    if (isSimulating || maxIndex <= 0) return

    // Pause playback and remember state
    wasPlayingBeforeDrag.current = isPlaying
    if (isPlaying) pause()

    setIsDragging(true)
    const touch = e.touches[0]
    const index = getIndexFromPosition(touch.clientX)
    setCurrentYearIndex(index)
  }, [isSimulating, maxIndex, isPlaying, pause, getIndexFromPosition, setCurrentYearIndex])

  const handleTrackKeyDown = useCallback((event: React.KeyboardEvent<HTMLDivElement>) => {
    if (isSimulating || maxIndex <= 0) return
    if (event.key === 'ArrowRight') {
      event.preventDefault()
      setCurrentYearIndex(Math.min(maxIndex, currentYearIndex + 1))
      return
    }
    if (event.key === 'ArrowLeft') {
      event.preventDefault()
      setCurrentYearIndex(Math.max(0, currentYearIndex - 1))
      return
    }
    if (event.key === 'Home') {
      event.preventDefault()
      setCurrentYearIndex(0)
      return
    }
    if (event.key === 'End') {
      event.preventDefault()
      setCurrentYearIndex(maxIndex)
    }
  }, [currentYearIndex, isSimulating, maxIndex, setCurrentYearIndex])

  // Handle drag move and end - attach to window for reliable tracking
  useEffect(() => {
    if (!isDragging) return

    const handleMouseMove = (e: MouseEvent) => {
      const index = getIndexFromPosition(e.clientX)
      setCurrentYearIndex(index)
    }

    const handleTouchMove = (e: TouchEvent) => {
      const touch = e.touches[0]
      const index = getIndexFromPosition(touch.clientX)
      setCurrentYearIndex(index)
    }

    const handleDragEnd = () => {
      setIsDragging(false)
      // Restart inactivity timer
      startCollapseTimer()
      // Optionally resume playback if it was playing before
      // (Uncomment if you want auto-resume behavior)
      // if (wasPlayingBeforeDrag.current) play()
    }

    // Attach listeners to window for reliable tracking even when cursor leaves track
    window.addEventListener('mousemove', handleMouseMove)
    window.addEventListener('mouseup', handleDragEnd)
    window.addEventListener('touchmove', handleTouchMove, { passive: true })
    window.addEventListener('touchend', handleDragEnd)
    window.addEventListener('touchcancel', handleDragEnd)

    return () => {
      window.removeEventListener('mousemove', handleMouseMove)
      window.removeEventListener('mouseup', handleDragEnd)
      window.removeEventListener('touchmove', handleTouchMove)
      window.removeEventListener('touchend', handleDragEnd)
      window.removeEventListener('touchcancel', handleDragEnd)
    }
  }, [isDragging, getIndexFromPosition, setCurrentYearIndex, startCollapseTimer])

  // Show player when timeline data is available
  const showPlayer = (
    timelineLoading ||
    (historicalTimeline !== null && historicalTimeline.years.length > 0) ||
    isSimulating ||
    temporalResults !== null
  )

  if (!showPlayer) return null

  // Calculate cursor position (0-100%)
  const cursorPosition = maxIndex > 0 ? (currentYearIndex / maxIndex) * 100 : 0

  // Toggle play/pause
  const handlePlayPause = () => {
    if (isSimulating || years.length === 0) return
    if (isPlaying) {
      pause()
    } else {
      // If at the end, restart from beginning; otherwise resume from current position
      if (currentYearIndex >= maxIndex) {
        setCurrentYearIndex(0)
      }
      // Expand timeline and delay play until positioned
      setPlayerState('expanded')
      setPendingPlay(true)
    }
  }

  // Handle click on docked button - expand to center with delayed play
  const handleDockedClick = () => {
    if (isSimulating || years.length === 0) return
    // If at the end, restart from beginning; otherwise resume from current position
    if (currentYearIndex >= maxIndex) {
      setCurrentYearIndex(0)
    }
    setPlayerState('expanded')
    setPendingPlay(true)
  }

  // Status text
  const statusText = isSimulating
    ? 'Calculating...'
    : playbackMode === 'historical'
      ? ((selectedCountry || selectedRegion) ? 'Historical Data' : '')
      : 'Simulation'

  // Loading state - show in docked position (SHAP loading or edges loading in local view)
  const isLoading = timelineLoading || (isLocalView && edgesLoading)
  if (isLoading && playerState === 'docked') {
    return (
      <>
        <div className="timeline-docked">
          <button className="docked-btn disabled" disabled>
            <span className="spinner" />
          </button>
        </div>
        <style>{timelineStyles}</style>
      </>
    )
  }

  // Docked state - bottom left, just play button
  if (playerState === 'docked') {
    return (
      <>
        <div className="timeline-docked">
          <button
            className={`docked-btn ${isSimulating ? 'disabled' : ''}`}
            onClick={handleDockedClick}
            disabled={isSimulating}
            title="Play Timeline"
            aria-label="Play timeline"
          >
            <svg width="20" height="20" viewBox="0 0 14 14" fill="currentColor">
              <path d="M2 1.5v11a.5.5 0 00.75.43l9.5-5.5a.5.5 0 000-.86l-9.5-5.5A.5.5 0 002 1.5z" />
            </svg>
          </button>
        </div>
        <style>{timelineStyles}</style>
      </>
    )
  }

  // Determine if we're in docking animation
  const isDocking = playerState === 'docking'

  // Expanded, collapsed, or docking state
  return (
    <>
      <div className={`timeline-player ${playerState} ${isPlaying ? 'playing' : ''} ${isDragging ? 'dragging' : ''} ${playbackMode === 'simulation' ? 'sim-mode' : ''}`}>
        {/* Play/Pause Button */}
        <button
          className={`play-btn ${isSimulating ? 'disabled' : ''} ${playbackMode === 'simulation' ? 'sim-mode' : ''}`}
          onClick={handlePlayPause}
          disabled={isSimulating}
          title={isPlaying ? 'Pause' : 'Play Timeline'}
          aria-label={isPlaying ? 'Pause timeline' : 'Play timeline'}
        >
          {isSimulating ? (
            <span className="spinner" />
          ) : isPlaying ? (
            <svg width="14" height="14" viewBox="0 0 14 14" fill="currentColor">
              <rect x="2" y="1" width="4" height="12" rx="1" />
              <rect x="8" y="1" width="4" height="12" rx="1" />
            </svg>
          ) : (
            <svg width="14" height="14" viewBox="0 0 14 14" fill="currentColor">
              <path d="M2 1.5v11a.5.5 0 00.75.43l9.5-5.5a.5.5 0 000-.86l-9.5-5.5A.5.5 0 002 1.5z" />
            </svg>
          )}
        </button>

        {/* Current year always visible */}
        <span className={`year-display-always ${isDocking ? 'fading' : ''}`}>
          {actualYear}
          {playbackMode === 'simulation' && temporalResults?.affected_per_year && actualYear != null && (
            <span style={{ fontSize: '9px', color: '#767676', marginLeft: '4px' }}>
              ({temporalResults.affected_per_year[String(actualYear)] ?? 0})
            </span>
          )}
        </span>

        {/* Expandable content - only visible when expanded */}
        <div className="expandable-content">
          {/* Status Text - only render if there's text */}
          {statusText && <span className="status-text">{statusText}</span>}

          {/* Timeline Track - supports click and drag */}
          <div
            ref={trackRef}
            className={`timeline-track ${isSimulating ? 'disabled' : ''} ${isDragging ? 'dragging' : ''}`}
            onMouseDown={handleMouseDown}
            onTouchStart={handleTouchStart}
            onKeyDown={handleTrackKeyDown}
            role="slider"
            tabIndex={isSimulating ? -1 : 0}
            aria-label="Timeline year"
            aria-valuemin={years[0] ?? 0}
            aria-valuemax={years[maxIndex] ?? 0}
            aria-valuenow={actualYear ?? years[0] ?? 0}
            aria-valuetext={actualYear ? `Year ${actualYear}` : 'No year selected'}
          >
            <div className="track-line" />

            {/* Year markers at start and end */}
            {years.length > 0 && (
              <>
                <span className="year-marker start">{years[0]}</span>
                <span className="year-marker end">{years[maxIndex]}</span>
              </>
            )}

            <div
              className={`cursor ${isDragging ? 'dragging' : ''}`}
              style={{
                left: `${cursorPosition}%`,
                // Disable transition during drag for immediate response
                transition: isDragging ? 'none' : `left ${MS_PER_YEAR}ms linear`
              }}
            />
          </div>
        </div>
      </div>
      <style>{timelineStyles}</style>
    </>
  )
}

const timelineStyles = `
  /* Docked state - bottom left, 3rd in row after data quality & simulate buttons */
  .timeline-docked {
    position: fixed;
    bottom: 10px;
    left: 122px; /* 10px margin + 48px (data quality) + 8px gap + 48px (simulate) + 12px gap */
    z-index: 1000;
  }

  .docked-btn {
    width: 48px;
    height: 48px;
    display: flex;
    align-items: center;
    justify-content: center;
    background: rgba(255, 255, 255, 0.95);
    border: 1px solid #d0d5e0;
    border-radius: 24px;
    color: #666;
    cursor: pointer;
    box-shadow: 0 2px 12px rgba(0, 0, 0, 0.1);
    backdrop-filter: blur(8px);
    transition: background 0.2s ease, color 0.2s ease, box-shadow 0.2s ease;
  }

  .docked-btn:hover:not(.disabled) {
    background: #f0f0f0;
    color: #333;
  }

  .docked-btn:focus-visible,
  .play-btn:focus-visible,
  .timeline-track:focus-visible {
    outline: 2px solid #3B82F6;
    outline-offset: 2px;
  }

  .docked-btn.disabled {
    background: rgba(255, 255, 255, 0.7);
    cursor: wait;
    color: #999;
  }

  .docked-btn .spinner {
    width: 20px;
    height: 20px;
    border: 2px solid rgba(102, 102, 102, 0.2);
    border-top-color: #666;
    border-radius: 50%;
    animation: spin 0.8s linear infinite;
  }

  /* Center timeline player */
  .timeline-player {
    position: fixed;
    bottom: 10px;
    left: 50%;
    transform: translateX(-50%);
    display: flex;
    align-items: center;
    gap: 12px;
    padding: 8px 16px;
    background: rgba(255, 255, 255, 0.95);
    border: 1px solid #d0d5e0;
    border-radius: 24px;
    box-shadow: 0 2px 12px rgba(0, 0, 0, 0.1);
    backdrop-filter: blur(8px);
    z-index: 1000;
    transition: left 0.4s cubic-bezier(0.4, 0, 0.2, 1),
                transform 0.4s cubic-bezier(0.4, 0, 0.2, 1),
                padding 0.4s cubic-bezier(0.4, 0, 0.2, 1),
                gap 0.4s cubic-bezier(0.4, 0, 0.2, 1),
                opacity 0.3s ease;
    overflow: visible;
  }

  .timeline-player.collapsed {
    padding: 8px 12px;
    gap: 8px;
  }

  /* Docking animation - move from center to bottom left */
  .timeline-player.docking {
    left: 94px; /* 70px + 24px (half of 48px button) */
    transform: translateX(-50%);
    padding: 8px 12px;
    gap: 8px;
    opacity: 0;
  }

  .year-display-always {
    font-size: 13px;
    font-weight: 600;
    color: #333;
    font-variant-numeric: tabular-nums;
    min-width: 36px;
    transition: opacity 0.3s ease-out;
  }

  .year-display-always.fading {
    opacity: 0;
  }

  .expandable-content {
    display: flex;
    align-items: center;
    gap: 12px;
    overflow: visible;
    max-width: 400px;
    opacity: 1;
    transition: max-width 0.4s cubic-bezier(0.4, 0, 0.2, 1),
                opacity 0.3s cubic-bezier(0.4, 0, 0.2, 1),
                gap 0.4s cubic-bezier(0.4, 0, 0.2, 1);
  }

  .timeline-player.collapsed .expandable-content,
  .timeline-player.docking .expandable-content {
    max-width: 0;
    opacity: 0;
    gap: 0;
  }

  .timeline-player.expanded .expandable-content {
    max-width: 400px;
    opacity: 1;
  }

  .play-btn {
    position: relative;
    width: 32px;
    height: 32px;
    border: none;
    border-radius: 50%;
    background: #3B82F6;
    color: white;
    cursor: pointer;
    display: flex;
    align-items: center;
    justify-content: center;
    transition: background 0.2s ease;
    flex-shrink: 0;
  }

  .play-btn::before {
    content: '';
    position: absolute;
    top: 50%;
    left: 50%;
    transform: translate(-50%, -50%);
    min-width: 44px;
    min-height: 44px;
  }

  .play-btn:hover:not(.disabled) {
    background: #2563EB;
  }

  .play-btn.sim-mode {
    background: #F97316;
  }

  .play-btn.sim-mode:hover:not(.disabled) {
    background: #EA580C;
  }

  .play-btn.disabled {
    background: #93C5FD;
    cursor: wait;
  }

  .play-btn .spinner {
    width: 14px;
    height: 14px;
    border: 2px solid rgba(255, 255, 255, 0.3);
    border-top-color: white;
    border-radius: 50%;
    animation: spin 0.8s linear infinite;
  }

  @keyframes spin {
    to { transform: rotate(360deg); }
  }

  .status-text {
    font-size: 11px;
    color: #666;
    white-space: nowrap;
    min-width: 80px;
  }

  .timeline-track {
    position: relative;
    width: 240px;
    height: 32px;
    cursor: pointer;
    display: flex;
    align-items: center;
    overflow: visible;
    touch-action: none; /* Prevent browser handling of touch gestures */
    user-select: none;
  }

  .timeline-track.dragging {
    cursor: grabbing;
  }

  .timeline-track.disabled {
    cursor: not-allowed;
    opacity: 0.6;
  }

  .track-line {
    position: absolute;
    left: 0;
    right: 0;
    height: 4px;
    background: #d0d5e0;
    border-radius: 2px;
  }

  .year-marker {
    position: absolute;
    bottom: -2px;
    font-size: 9px;
    color: #999;
    user-select: none;
  }

  .year-marker.start {
    left: 0;
  }

  .year-marker.end {
    right: 0;
  }

  .cursor {
    position: absolute;
    width: 14px;
    height: 14px;
    background: #3B82F6;
    border: 2px solid white;
    border-radius: 50%;
    transform: translateX(-50%);
    box-shadow: 0 1px 4px rgba(0, 0, 0, 0.2);
    cursor: grab;
  }

  .timeline-player.sim-mode .cursor {
    background: #F97316;
  }

  .cursor.dragging {
    cursor: grabbing;
    transform: translateX(-50%) scale(1.2);
    box-shadow: 0 2px 8px rgba(59, 130, 246, 0.4);
  }

  .cursor-tooltip {
    position: absolute;
    bottom: 100%;
    left: 50%;
    transform: translateX(-50%);
    padding: 4px 8px;
    background: #1E293B;
    color: white;
    font-size: 11px;
    font-weight: 500;
    border-radius: 4px;
    white-space: nowrap;
    pointer-events: none;
    transition: opacity 0.15s;
    margin-bottom: 6px;
    z-index: 10;
  }

  .cursor-tooltip::after {
    content: '';
    position: absolute;
    top: 100%;
    left: 50%;
    transform: translateX(-50%);
    border: 4px solid transparent;
    border-top-color: #1E293B;
  }

  /* Visible during playback or dragging */
  .timeline-player.playing .cursor-tooltip,
  .timeline-player.dragging .cursor-tooltip {
    opacity: 1;
  }

  /* Hidden when not playing and not dragging (default) */
  .timeline-player:not(.playing):not(.dragging) .cursor-tooltip {
    opacity: 0;
  }

  /* Show on hover when expanded but not playing */
  .timeline-player.expanded:not(.playing):not(.dragging) .cursor:hover .cursor-tooltip,
  .timeline-player.expanded:not(.playing):not(.dragging) .timeline-track:hover .cursor-tooltip {
    opacity: 1;
  }

  @media (max-width: 767px) {
    .timeline-player {
      padding: 6px 10px;
      gap: 8px;
      bottom: 10px;
    }
    .timeline-player.collapsed {
      padding: 6px 8px;
      gap: 6px;
    }
    .timeline-track {
      width: 140px;
      min-height: 44px;
    }
    .expandable-content {
      gap: 8px;
      max-width: 240px;
    }
    .year-display-always {
      font-size: 11px;
      min-width: 30px;
    }
    .play-btn {
      width: 28px;
      height: 28px;
    }
    .cursor {
      width: 16px;
      height: 16px;
    }
    .docked-btn {
      width: 48px;
      height: 48px;
    }
    .timeline-docked {
      bottom: 10px;
    }
    .status-text {
      font-size: 10px;
      min-width: 60px;
    }
  }
`

export default TimelinePlayer
