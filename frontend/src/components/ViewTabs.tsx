/**
 * ViewTabs - Tab switcher for Global, Local, and Split views
 * With action buttons for Reset, Clear, and Share
 */

import { useState, useEffect, useRef } from 'react'
import type { ViewMode } from '../types'
import { useSimulationStore } from '../stores/simulationStore'

type MapViewMode = 'country' | 'regional'

interface ViewTabsProps {
  activeView: ViewMode
  onViewChange: (view: ViewMode) => void
  localTargetCount: number    // Number of targets in Local View
  onReset: () => void         // Reset view callback
  onClear?: () => void        // Clear local view targets callback
  canClear?: boolean          // Whether clear action should be enabled
  onShare?: () => Promise<boolean>  // Copy shareable link callback
  onTutorialRestart?: () => void   // Restart guided tutorial
  simMode?: boolean           // Sim mode enables local/split even without targets
  /** Hide text labels on action buttons, show icon only */
  compact?: boolean
  /** Hide the Split tab entirely (e.g. on narrow viewports) */
  hideSplit?: boolean
  /** Mobile layout — repositions Map button to bottom-right */
  isMobileLayout?: boolean
}

/**
 * Tab switcher component with Global/Local/Split tabs and action buttons
 */
export function ViewTabs({
  activeView,
  onViewChange,
  localTargetCount,
  onReset,
  onClear,
  canClear,
  onShare,
  onTutorialRestart,
  simMode = false,
  compact = false,
  hideSplit = false,
  isMobileLayout = false,
}: ViewTabsProps) {
  const hasTargets = localTargetCount > 0 || simMode
  const clearEnabled = canClear ?? hasTargets
  const [shareStatus, setShareStatus] = useState<'idle' | 'copied'>('idle')
  const [shareNudge, setShareNudge] = useState(false)
  const playbackFinishedToken = useSimulationStore(s => s.playbackFinishedToken)
  const mapForeground = useSimulationStore(s => s.mapForeground)
  const toggleMapForeground = useSimulationStore(s => s.toggleMapForeground)
  const mapViewMode = useSimulationStore(s => s.mapViewMode) as MapViewMode
  const setMapViewMode = useSimulationStore(s => s.setMapViewMode)
  const prevFinishedTokenRef = useRef(playbackFinishedToken)

  // Glow the share button when simulation playback reaches the final year
  useEffect(() => {
    if (playbackFinishedToken > 0 && playbackFinishedToken !== prevFinishedTokenRef.current) {
      prevFinishedTokenRef.current = playbackFinishedToken
      setShareNudge(true)
      const timer = setTimeout(() => setShareNudge(false), 4000)
      return () => clearTimeout(timer)
    }
  }, [playbackFinishedToken])

  const handleShare = async () => {
    if (onShare) {
      const success = await onShare()
      if (success) {
        setShareStatus('copied')
        setTimeout(() => setShareStatus('idle'), 2000)
      }
    }
  }

  return (
    <>
    <div
      style={{
        display: 'flex',
        flexDirection: 'column',
        alignItems: 'flex-end',
        gap: 6
      }}
    >
      {/* Row 1: View mode tabs (graph views) / Map mode toggle (when map foreground) */}
      <div
        style={{
          display: 'flex',
          background: 'white',
          borderRadius: 6,
          boxShadow: '0 2px 4px rgba(0,0,0,0.1)',
          border: '1px solid #d0d5e0',
          overflow: 'hidden'
        }}
      >
        {mapForeground ? (
          /* Map mode toggle: Country / Regional */
          <>
            <button
              onClick={() => setMapViewMode('country')}
              style={{
                padding: '8px 16px',
                fontSize: 13,
                fontWeight: mapViewMode === 'country' ? 600 : 400,
                cursor: 'pointer',
                border: 'none',
                background: mapViewMode === 'country' ? '#3B82F6' : 'white',
                color: mapViewMode === 'country' ? 'white' : '#555',
                transition: 'all 0.15s ease'
              }}
              title="Country view — each country colored by its QoL score"
            >
              Country
            </button>
            <button
              onClick={() => setMapViewMode('regional')}
              style={{
                padding: '8px 16px',
                fontSize: 13,
                fontWeight: mapViewMode === 'regional' ? 600 : 400,
                cursor: 'pointer',
                border: 'none',
                borderLeft: '1px solid #d0d5e0',
                background: mapViewMode === 'regional' ? '#3B82F6' : 'white',
                color: mapViewMode === 'regional' ? 'white' : '#555',
                transition: 'all 0.15s ease'
              }}
              title="Regional view — countries colored by region-mean QoL"
            >
              Regional
            </button>
          </>
        ) : (
          /* Standard graph view tabs */
          <>
            {/* Global tab */}
            <button
              onClick={() => onViewChange('global')}
              style={{
                padding: '8px 16px',
                fontSize: 13,
                fontWeight: activeView === 'global' ? 600 : 400,
                cursor: 'pointer',
                border: 'none',
                background: activeView === 'global' ? '#3B82F6' : 'white',
                color: activeView === 'global' ? 'white' : '#555',
                transition: 'all 0.15s ease'
              }}
              title="Global View - Explore the hierarchy (G)"
            >
              Global
            </button>

            {/* Split tab — hidden on narrow viewports */}
            {!hideSplit && (
              <button
                onClick={() => onViewChange('split')}
                disabled={!hasTargets && activeView !== 'split'}
                style={{
                  padding: '8px 16px',
                  fontSize: 13,
                  fontWeight: activeView === 'split' ? 600 : 400,
                  cursor: !hasTargets && activeView !== 'split' ? 'not-allowed' : 'pointer',
                  border: 'none',
                  borderLeft: '1px solid #d0d5e0',
                  background: activeView === 'split' ? '#3B82F6' : 'white',
                  color: activeView === 'split' ? 'white' : !hasTargets ? '#aaa' : '#555',
                  opacity: !hasTargets && activeView !== 'split' ? 0.6 : 1,
                  transition: 'all 0.15s ease'
                }}
                title={!hasTargets
                  ? "Double-click a node to enable split view"
                  : "Split View - See both views side by side (S)"
                }
              >
                Split
              </button>
            )}

            {/* Local tab */}
            <button
              onClick={() => onViewChange('local')}
              disabled={!hasTargets && activeView !== 'local'}
              style={{
                padding: '8px 16px',
                fontSize: 13,
                fontWeight: activeView === 'local' ? 600 : 400,
                cursor: !hasTargets && activeView !== 'local' ? 'not-allowed' : 'pointer',
                border: 'none',
                borderLeft: '1px solid #d0d5e0',
                background: activeView === 'local' ? '#3B82F6' : 'white',
                color: activeView === 'local' ? 'white' : !hasTargets ? '#aaa' : '#555',
                opacity: !hasTargets && activeView !== 'local' ? 0.6 : 1,
                transition: 'all 0.15s ease',
                display: 'flex',
                alignItems: 'center',
                gap: 6
              }}
              title={!hasTargets
                ? "Double-click a node to view its causal pathways"
                : `Local View - ${localTargetCount} target${localTargetCount !== 1 ? 's' : ''} (L)`
              }
            >
              Local
              {hasTargets && (
                <span
                  style={{
                    background: activeView === 'local' ? 'rgba(255,255,255,0.3)' : '#3B82F6',
                    color: 'white',
                    fontSize: 11,
                    padding: '1px 6px',
                    borderRadius: 10,
                    fontWeight: 600
                  }}
                >
                  {localTargetCount}
                </span>
              )}
            </button>
          </>
        )}
      </div>

      {/* Row 2: Clear and Reset buttons in shared bubble */}
      <div
        style={{
          display: 'flex',
          background: 'white',
          borderRadius: 6,
          boxShadow: '0 2px 4px rgba(0,0,0,0.1)',
          border: '1px solid #d0d5e0',
          overflow: 'hidden'
        }}
      >
        {/* Clear button - always rendered, fades in/out smoothly */}
        <button
          onClick={onClear}
          disabled={!clearEnabled}
          style={{
            padding: '6px 12px',
            fontSize: 12,
            fontWeight: 500,
            cursor: clearEnabled ? 'pointer' : 'default',
            border: 'none',
            background: 'white',
            color: clearEnabled ? '#E53935' : '#bcc3d4',
            transition: 'all 0.2s ease',
            opacity: clearEnabled ? 1 : 0.4,
            display: 'flex',
            alignItems: 'center',
            gap: 4
          }}
          onMouseEnter={(e) => {
            if (clearEnabled) e.currentTarget.style.background = '#FFEBEE'
          }}
          onMouseLeave={(e) => {
            e.currentTarget.style.background = 'white'
          }}
          title={clearEnabled ? "Clear working context in current scope (C)" : "Nothing to clear"}
        >
          {compact ? (
            <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
              <line x1="18" y1="6" x2="6" y2="18" />
              <line x1="6" y1="6" x2="18" y2="18" />
            </svg>
          ) : 'Clear (C)'}
        </button>

        {/* Reset button */}
        <button
          onClick={onReset}
          style={{
            padding: '6px 12px',
            fontSize: 12,
            fontWeight: 500,
            cursor: 'pointer',
            border: 'none',
            borderLeft: '1px solid #d0d5e0',
            background: 'white',
            color: '#555',
            transition: 'all 0.15s ease',
            display: 'flex',
            alignItems: 'center',
            gap: 4
          }}
          title="Reset view to initial state (R or Home)"
          onMouseEnter={(e) => {
            e.currentTarget.style.background = '#eef0f6'
          }}
          onMouseLeave={(e) => {
            e.currentTarget.style.background = 'white'
          }}
        >
          {compact ? (
            <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
              <polyline points="1 4 1 10 7 10" />
              <path d="M3.51 15a9 9 0 1 0 2.13-9.36L1 10" />
            </svg>
          ) : 'Reset (R)'}
        </button>
      </div>

      {/* Row 3: Map layer toggle — on mobile, rendered as fixed bottom-right button */}
      {!isMobileLayout && (
        <div
          style={{
            display: 'flex',
            background: 'white',
            borderRadius: 6,
            boxShadow: '0 2px 4px rgba(0,0,0,0.1)',
            border: '1px solid #d0d5e0',
            overflow: 'hidden'
          }}
        >
          <button
            onClick={() => toggleMapForeground()}
            style={{
              padding: '6px 12px',
              fontSize: 12,
              fontWeight: 500,
              cursor: 'pointer',
              border: 'none',
              borderRadius: 5,
              background: mapForeground ? '#3B82F6' : 'white',
              color: mapForeground ? 'white' : '#555',
              transition: 'all 0.15s ease',
              display: 'flex',
              alignItems: 'center',
              gap: 5
            }}
            title={mapForeground ? 'Send map to background (M)' : 'Bring map forward (M)'}
            onMouseEnter={(e) => {
              if (!mapForeground) e.currentTarget.style.background = '#eef0f6'
            }}
            onMouseLeave={(e) => {
              if (!mapForeground) e.currentTarget.style.background = 'white'
            }}
          >
            <svg
              width="14"
              height="14"
              viewBox="0 0 24 24"
              fill="none"
              stroke="currentColor"
              strokeWidth="2"
              strokeLinecap="round"
              strokeLinejoin="round"
            >
              <polygon points="1 6 1 22 8 18 16 22 23 18 23 2 16 6 8 2 1 6" />
              <line x1="8" y1="2" x2="8" y2="18" />
              <line x1="16" y1="6" x2="16" y2="22" />
            </svg>
            {!compact && 'Map (M)'}
          </button>
        </div>
      )}

      {/* Row 4: Share button */}
      <div
        className={shareNudge ? 'share-btn-wrap share-nudge-active' : 'share-btn-wrap'}
        style={{
          display: 'flex',
          background: 'white',
          borderRadius: 6,
          boxShadow: '0 2px 4px rgba(0,0,0,0.1)',
          border: '1px solid #d0d5e0',
          overflow: 'visible',
          position: 'relative'
        }}
      >
        <button
          onClick={() => { setShareNudge(false); handleShare() }}
          className={shareNudge ? 'share-btn-inner share-nudge-btn' : 'share-btn-inner'}
          style={{
            padding: '6px 12px',
            fontSize: 12,
            fontWeight: 500,
            cursor: 'pointer',
            border: 'none',
            borderRadius: 5,
            background: shareStatus === 'copied' ? '#E8F5E9' : 'white',
            color: shareStatus === 'copied' ? '#2E7D32' : '#00ACC1',
            transition: 'all 0.3s ease',
            display: 'flex',
            alignItems: 'center',
            gap: 6,
            position: 'relative',
            zIndex: 1
          }}
          title="Copy shareable link to clipboard"
          onMouseEnter={(e) => {
            if (shareStatus !== 'copied') {
              e.currentTarget.style.background = '#eef0f6'
            }
          }}
          onMouseLeave={(e) => {
            if (shareStatus !== 'copied') {
              e.currentTarget.style.background = 'white'
            }
          }}
        >
          <svg
            width="14"
            height="14"
            viewBox="0 0 24 24"
            fill="none"
            stroke="currentColor"
            strokeWidth="2"
            strokeLinecap="round"
            strokeLinejoin="round"
          >
            <path d="M4 12v8a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2v-8" />
            <polyline points="16 6 12 2 8 6" />
            <line x1="12" y1="2" x2="12" y2="15" />
          </svg>
          {compact
            ? (shareStatus === 'copied' ? '✓' : null)
            : (shareStatus === 'copied' ? 'Copied!' : 'Share')
          }
        </button>
      </div>

      {/* Row 5: Tour restart — smallest button in the cascade */}
      {onTutorialRestart && (
        <button
          onClick={onTutorialRestart}
          style={{
            padding: '4px 8px',
            fontSize: 11,
            fontWeight: 500,
            cursor: 'pointer',
            border: '1px solid #d0d5e0',
            borderRadius: 6,
            background: 'white',
            color: '#999',
            boxShadow: '0 1px 3px rgba(0,0,0,0.08)',
            transition: 'all 0.15s ease',
            display: 'flex',
            alignItems: 'center',
            gap: 4,
            alignSelf: 'flex-end'
          }}
          title="Replay guided tour"
          onMouseEnter={(e) => {
            e.currentTarget.style.background = '#eef0f6'
            e.currentTarget.style.color = '#555'
          }}
          onMouseLeave={(e) => {
            e.currentTarget.style.background = 'white'
            e.currentTarget.style.color = '#999'
          }}
        >
          <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
            <circle cx="12" cy="12" r="10" />
            <path d="M9.09 9a3 3 0 0 1 5.83 1c0 2-3 3-3 3" />
            <line x1="12" y1="17" x2="12.01" y2="17" />
          </svg>
          {!compact && 'Tour'}
        </button>
      )}
    </div>

    {/* Mobile: Map button fixed at bottom-right */}
    {isMobileLayout && (
      <div
        style={{
          position: 'fixed',
          bottom: 10,
          right: 10,
          zIndex: 100,
        }}
      >
        <button
          onClick={() => toggleMapForeground()}
          className="touch-target-44"
          style={{
            width: 48,
            height: 48,
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            cursor: 'pointer',
            border: mapForeground ? '1px solid #3B82F6' : '1px solid #d0d5e0',
            borderRadius: 24,
            background: mapForeground ? '#3B82F6' : 'rgba(255,255,255,0.95)',
            color: mapForeground ? 'white' : '#666',
            boxShadow: mapForeground ? '0 2px 8px rgba(59,130,246,0.4)' : '0 2px 12px rgba(0,0,0,0.1)',
            backdropFilter: 'blur(8px)',
            transition: 'all 0.2s ease',
          }}
          title={mapForeground ? 'Send map to background' : 'Bring map forward'}
          aria-label={mapForeground ? 'Send map to background' : 'Bring map forward'}
        >
          <svg
            width="20"
            height="20"
            viewBox="0 0 24 24"
            fill="none"
            stroke="currentColor"
            strokeWidth="2"
            strokeLinecap="round"
            strokeLinejoin="round"
          >
            <polygon points="1 6 1 22 8 18 16 22 23 18 23 2 16 6 8 2 1 6" />
            <line x1="8" y1="2" x2="8" y2="18" />
            <line x1="16" y1="6" x2="16" y2="22" />
          </svg>
        </button>
      </div>
    )}
    </>
  )
}

export default ViewTabs
