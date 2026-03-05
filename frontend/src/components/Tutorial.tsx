import { useEffect, useRef, useState, useCallback, useImperativeHandle, forwardRef, type RefObject } from 'react'
import { createPortal } from 'react-dom'
import { useSimulationStore } from '../stores/simulationStore'
import type { GraphDataV21, PositionedNode } from '../types'
import '../styles/Tutorial.css'

// ── Types ──

export interface TutorialHandle {
  toggleExpansion: (nodeId: string) => void
  setExpandedNodes: React.Dispatch<React.SetStateAction<Set<string>>>
  expandRing: (ring: number) => void
  collapseRing: (ring: number) => void
  resetView: () => void
  allNodes: ExpandableNodeLike[]
  rawData: GraphDataV21 | null
}

/** Minimal shape we need from App's ExpandableNode */
interface ExpandableNodeLike extends PositionedNode {
  parentId: string | null
  childIds: string[]
  hasChildren: boolean
  importance: number
  angle: number
}

export interface TutorialRef {
  restart: () => void
  isActive: () => boolean
}

interface TutorialProps {
  appRef: RefObject<TutorialHandle | null>
  onActiveChange?: (active: boolean) => void
}

interface StepDef {
  headline: string
  body: string
}

const STORAGE_KEY = 'atlas_tutorial_seen'
const TOTAL_STEPS = 7

/**
 * Tutorial intervention indicator — "Total Government Spending" (XGOVEXP.IMF).
 * Chosen because it's a single ring-1 level indicator that produces clean,
 * moderate ripple effects without excessive node movement during timeline playback.
 */
const TUTORIAL_INTERVENTION = {
  id: 'tutorial-intervention-0',
  indicator: 'cda',
  indicatorLabel: 'Total Domestic Spending Power',
  change_percent: 15,
  domain: '',
  year: 2020
}

const STEPS: StepDef[] = [
  {
    headline: 'This is what drives human progress.',
    body: 'Quality of Life sits at the center. Every circle around it is a proven cause.'
  },
  {
    headline: 'Bigger means more important.',
    body: 'Each circle\u2019s area is directly proportional to its impact on Quality of Life.'
  },
  {
    headline: 'There are 3,122 indicators inside this graph.',
    body: 'Click any circle to expand it and reveal what drives it. Go as deep or as shallow as you want.'
  },
  {
    headline: 'Every country. Every income level.',
    body: 'Switch between income groups to see how Quality of Life shifts around the world. Green is higher. Red is lower.'
  },
  {
    headline: 'Zoom into any country.',
    body: 'Click any country on the map to load its unique causal graph. Every country tells a different story.'
  },
  {
    headline: 'Test what happens next.',
    body: 'Add an intervention and watch the effects ripple through the graph in real time. This is where Atlas becomes a policy tool.'
  },
  {
    headline: 'Ready to reset? One click.',
    body: 'Hit reset to clear the simulation and bring the graph back to its original state. You can always start fresh.'
  }
]

// ── Helpers ──

function getNodeRect(dataId: string): DOMRect | null {
  const el = document.querySelector<SVGCircleElement>(`circle.node[data-id="${dataId}"]`)
  return el?.getBoundingClientRect() ?? null
}

function isReducedMotion(): boolean {
  return window.matchMedia('(prefers-reduced-motion: reduce)').matches
}

/**
 * Find Brazil's SVG path element on the WorldMap.
 * Brazil's numeric id in the TopoJSON is "76".
 */
function getBrazilMapPath(): SVGPathElement | null {
  // The WorldMap renders paths with class "country" — each bound to a GeoJSON feature.
  // We find Brazil by checking the d3-bound data's `id` property (numeric "76").
  const paths = document.querySelectorAll<SVGPathElement>('path.country')
  for (const path of paths) {
    // d3 stores bound data in __data__
    const data = (path as unknown as { __data__?: { id?: string | number } }).__data__
    if (data?.id != null && String(Number(data.id)) === '76') return path
  }
  return null
}

// ── Component ──

export const Tutorial = forwardRef<TutorialRef, TutorialProps>(function Tutorial({ appRef, onActiveChange }, ref) {
  const [active, setActiveRaw] = useState(false)
  const setActive = useCallback((v: boolean) => {
    setActiveRaw(v)
    onActiveChange?.(v)
  }, [onActiveChange])
  const [step, setStep] = useState(0)
  const [spotlight, setSpotlight] = useState<{ x: number; y: number; r: number } | null>(null)
  const [showScrim, setShowScrim] = useState(true)
  const [pulseSpotlight, setPulseSpotlight] = useState(false)
  const [mapClickRipple, setMapClickRipple] = useState<{ x: number; y: number } | null>(null)
  const [cardHidden, setCardHidden] = useState(false)
  const [navDimmed, setNavDimmed] = useState(false)
  const navDimTimerRef = useRef<number | null>(null)
  const timersRef = useRef<number[]>([])
  const expandedNodeRef = useRef<string | null>(null)
  const blockerRef = useRef<((e: Event) => void) | null>(null)
  const stepRef = useRef(step)
  stepRef.current = step

  // Expose restart method to parent
  useImperativeHandle(ref, () => ({
    restart: () => {
      setStep(0)
      setSpotlight(null)
      setPulseSpotlight(false)
      setMapClickRipple(null)
      setCardHidden(false)
      setShowScrim(true)
      setActive(true)
    },
    isActive: () => active
  }), [active])

  // Check localStorage on mount
  useEffect(() => {
    if (localStorage.getItem(STORAGE_KEY) === 'true') return
    // Delay launch to let the graph render first
    const t = window.setTimeout(() => setActive(true), 1500)
    return () => clearTimeout(t)
  }, [])

  // Input blocker: capture-phase interceptor
  useEffect(() => {
    if (!active) return

    const blocker = (e: Event) => {
      const target = e.target as HTMLElement | null
      if (target?.closest?.('[data-tutorial-nav]')) return
      // On final step, allow clicking the Reset button
      if (stepRef.current === TOTAL_STEPS - 1 && target?.closest?.('[title*="Reset"]')) return
      e.stopPropagation()
      e.preventDefault()
    }
    blockerRef.current = blocker

    const events = ['click', 'mousedown', 'mouseup', 'touchstart', 'touchend', 'keydown', 'wheel'] as const
    for (const evt of events) {
      window.addEventListener(evt, blocker, true)
    }

    // Add tutorial-active class to app root
    document.getElementById('root')?.classList.add('tutorial-active')

    return () => {
      for (const evt of events) {
        window.removeEventListener(evt, blocker, true)
      }
      document.getElementById('root')?.classList.remove('tutorial-active')
      blockerRef.current = null
    }
  }, [active])

  // Clear all pending timers
  const clearTimers = useCallback(() => {
    for (const t of timersRef.current) clearTimeout(t)
    timersRef.current = []
  }, [])

  // Cancel / cleanup for current step
  const cancelStep = useCallback((stepIdx: number) => {
    clearTimers()
    setSpotlight(null)
    setPulseSpotlight(false)
    setShowScrim(true)
    setMapClickRipple(null)
    setCardHidden(false)
    setNavDimmed(false)
    if (navDimTimerRef.current) {
      clearTimeout(navDimTimerRef.current)
      navDimTimerRef.current = null
    }

    const store = useSimulationStore.getState()

    switch (stepIdx) {
      case 2: {
        // Collapse if we expanded a node
        if (expandedNodeRef.current && appRef.current) {
          appRef.current.toggleExpansion(expandedNodeRef.current)
          expandedNodeRef.current = null
        }
        break
      }
      case 3: {
        // Close map, reset stratum
        if (store.mapForeground) store.toggleMapForeground()
        store.setStratum('unified')
        break
      }
      case 4: {
        // Close map if still open (step 5 closes it, but safety check)
        if (store.mapForeground) store.toggleMapForeground()
        break
      }
      // Steps 5, 6: leave state as-is (next step depends on it)
    }
  }, [appRef, clearTimers])

  // Full reset to clean state (on skip) — delegates to App's resetView
  const resetToClean = useCallback(() => {
    clearTimers()
    expandedNodeRef.current = null
    const store = useSimulationStore.getState()
    if (store.isPanelOpen) store.closePanel()
    appRef.current?.resetView()
  }, [appRef, clearTimers])

  const endTutorial = useCallback(() => {
    cancelStep(step)
    setActive(false)
    localStorage.setItem(STORAGE_KEY, 'true')
  }, [cancelStep, step])

  const handleSkip = useCallback(() => {
    resetToClean()
    setActive(false)
    localStorage.setItem(STORAGE_KEY, 'true')
  }, [resetToClean])

  const handleNext = useCallback(() => {
    cancelStep(step)
    if (step >= TOTAL_STEPS - 1) {
      endTutorial()
      return
    }
    setStep(s => s + 1)
  }, [step, cancelStep, endTutorial])

  // On the last step, "Start exploring" resets via App's resetView (same as pressing R)
  const handleFinalAction = useCallback(() => {
    clearTimers()
    expandedNodeRef.current = null
    const store = useSimulationStore.getState()
    if (store.isPanelOpen) store.closePanel()
    appRef.current?.resetView()
    setActive(false)
    localStorage.setItem(STORAGE_KEY, 'true')
  }, [appRef, clearTimers])

  // ── Step animations ──

  useEffect(() => {
    if (!active) return
    const reduced = isReducedMotion()
    const store = useSimulationStore.getState

    const timer = (fn: () => void, ms: number) => {
      const t = window.setTimeout(fn, ms)
      timersRef.current.push(t)
      return t
    }

    switch (step) {
      // Step 1: Spotlight QoL root
      case 0: {
        setShowScrim(true)
        setPulseSpotlight(!reduced)
        const position = () => {
          const rect = getNodeRect('quality_of_life') || getNodeRect('root')
          if (rect) {
            const pad = 24
            setSpotlight({
              x: rect.left + rect.width / 2,
              y: rect.top + rect.height / 2,
              r: Math.max(rect.width, rect.height) / 2 + pad
            })
          }
        }
        // Retry positioning until node is rendered
        position()
        timer(position, 300)
        timer(position, 800)
        break
      }

      // Step 2: Sequential spotlight on 3 ring-1 nodes
      case 1: {
        setShowScrim(true)
        const nodes = appRef.current?.allNodes ?? []
        const ring1 = nodes
          .filter(n => n.ring === 1)
          .sort((a, b) => b.importance - a.importance)
          .slice(0, 3)

        if (ring1.length === 0) break

        if (reduced) {
          const rect = getNodeRect(ring1[0].id)
          if (rect) {
            setSpotlight({
              x: rect.left + rect.width / 2,
              y: rect.top + rect.height / 2,
              r: Math.max(rect.width, rect.height) / 2 + 20
            })
          }
          break
        }

        const showNode = (idx: number) => {
          if (idx >= ring1.length) return
          const rect = getNodeRect(ring1[idx].id)
          if (rect) {
            setPulseSpotlight(false)
            setSpotlight({
              x: rect.left + rect.width / 2,
              y: rect.top + rect.height / 2,
              r: Math.max(rect.width, rect.height) / 2 + 20
            })
            timer(() => setPulseSpotlight(true), 50)
          }
        }
        showNode(0)
        timer(() => showNode(1), 1200)
        timer(() => showNode(2), 2400)
        break
      }

      // Step 3: Expand/collapse Education node, then expand entire ring via "+" button
      case 2: {
        setShowScrim(false)
        setSpotlight(null)

        if (reduced) break

        const nodes = appRef.current?.allNodes ?? []
        const eduNode = nodes.find(n =>
          n.ring === 1 && /education/i.test(n.label)
        )
        if (!eduNode || !appRef.current) break

        // Phase 1: expand a single branch (t=500)
        timer(() => {
          appRef.current!.toggleExpansion(eduNode.id)
          expandedNodeRef.current = eduNode.id
        }, 500)

        // Phase 2: collapse it back (t=2800)
        timer(() => {
          if (expandedNodeRef.current) {
            appRef.current!.toggleExpansion(expandedNodeRef.current)
            expandedNodeRef.current = null
          }
        }, 2800)

        // Phase 3: spotlight the Outcomes "+" button in the sidebar (t=3600)
        timer(() => {
          const expandBtn = document.querySelector<HTMLButtonElement>('button[aria-label="Expand Outcomes"]')
          if (expandBtn) {
            const rect = expandBtn.getBoundingClientRect()
            setShowScrim(true)
            setSpotlight({
              x: rect.left + rect.width / 2,
              y: rect.top + rect.height / 2,
              r: Math.max(rect.width, rect.height) / 2 + 12
            })
            setPulseSpotlight(true)
          }
        }, 3600)

        // Phase 4: call expandRing programmatically (t=4800)
        timer(() => {
          appRef.current?.expandRing(1)
          setSpotlight(null)
          setShowScrim(false)
          setPulseSpotlight(false)
        }, 4800)

        // Phase 5: collapse ring back down (t=7200) — keep the momentum going
        timer(() => {
          appRef.current?.collapseRing(1)
        }, 7200)
        break
      }

      // Step 4: Map + strata cycling
      case 3: {
        setShowScrim(false)
        setSpotlight(null)

        const s = store()
        if (!s.mapForeground) s.toggleMapForeground()

        if (reduced) {
          timer(() => store().setStratum('developing'), 300)
          break
        }

        timer(() => store().setStratum('developing'), 1000)
        timer(() => store().setStratum('emerging'), 2500)
        timer(() => store().setStratum('advanced'), 4000)
        timer(() => store().setStratum('unified'), 5500)
        break
      }

      // Step 5: Click Brazil on the map → load its graph
      case 4: {
        setShowScrim(false)
        setSpotlight(null)

        const s = store()
        // Ensure map is open
        if (!s.mapForeground) s.toggleMapForeground()

        timer(() => {
          // Find Brazil's path on the map and animate a click ripple
          const brazilPath = getBrazilMapPath()
          if (brazilPath) {
            const rect = brazilPath.getBoundingClientRect()
            const cx = rect.left + rect.width / 2
            const cy = rect.top + rect.height / 2

            // Show spotlight on Brazil first
            setSpotlight({ x: cx, y: cy, r: Math.max(rect.width, rect.height) / 2 + 20 })
            setPulseSpotlight(!reduced)

            // Trigger click ripple animation
            timer(() => {
              setMapClickRipple({ x: cx, y: cy })

              // Select Brazil after click visual
              timer(() => {
                store().setCountry('Brazil')

                // Wait for country to load, then close map to show the graph
                const waitForCountry = () => {
                  const current = store()
                  if (!current.countryLoading && current.selectedCountry === 'Brazil') {
                    timer(() => {
                      if (store().mapForeground) store().toggleMapForeground()
                      setSpotlight(null)
                      setMapClickRipple(null)
                    }, 800)
                  } else {
                    timer(waitForCountry, 200)
                  }
                }
                timer(waitForCountry, 300)
              }, 400)
            }, reduced ? 0 : 600)
          } else {
            // Fallback: no map path found, just select directly
            store().setCountry('Brazil')
            timer(() => {
              if (store().mapForeground) store().toggleMapForeground()
            }, 1500)
          }
        }, 500)
        break
      }

      // Step 6: Add intervention, run simulation
      // On mobile: show text first, fade it, then do the actions so user can watch
      case 5: {
        setShowScrim(false)
        setSpotlight(null)
        setCardHidden(false)

        const runSimActions = () => {
          const s = store()
          s.openPanel()

          // Add a single clean intervention
          timer(() => {
            const st = store()
            st.clearInterventions()
            st.addIntervention(TUTORIAL_INTERVENTION)

            // Run simulation
            timer(async () => {
              await store().runTemporalSimulation()
              // Wait for results, then auto-play
              const waitForResults = () => {
                const current = store()
                if (current.temporalResults && !current.isSimulating) {
                  timer(() => store().play(), 500)
                } else {
                  timer(waitForResults, 200)
                }
              }
              waitForResults()
            }, 800)
          }, 500)
        }

        // Let user read the description, then fade it and start actions
        timer(() => {
          setCardHidden(true)
          // On desktop, dim the nav bar once the card fades
          if (window.innerWidth >= 768) {
            timer(() => {
              setNavDimmed(true)
              // Blur focus so :focus-within doesn't override the dim
              if (document.activeElement instanceof HTMLElement) document.activeElement.blur()
            }, 400)
          }
          timer(runSimActions, 400) // wait for fade transition
        }, 2500)
        break
      }

      // Step 7: Spotlight the Reset button, then reset
      case 6: {
        setShowScrim(true)

        // Pause playback so user can read the step
        const s = store()
        if (s.isPlaying) s.pause()

        // Spotlight the Reset (R) button in the top-right toolbar (tight fit)
        const spotlightResetBtn = () => {
          const btn = document.querySelector<HTMLButtonElement>('button[title="Reset view to initial state (R or Home)"]')
          if (btn) {
            const rect = btn.getBoundingClientRect()
            setSpotlight({
              x: rect.left + rect.width / 2,
              y: rect.top + rect.height / 2,
              r: Math.max(rect.width, rect.height) / 2 + 4
            })
            setPulseSpotlight(!reduced)
            // Make Reset button clickable through the pointer-events: none overlay
            btn.style.pointerEvents = 'auto'
            btn.style.position = 'relative'
            btn.style.zIndex = '1302'
          }
        }
        spotlightResetBtn()
        timer(spotlightResetBtn, 300)
        timer(spotlightResetBtn, 800)

        // Listen for Reset button click to end tutorial
        const onResetClick = () => {
          localStorage.setItem(STORAGE_KEY, 'true')
          setActive(false)
        }
        const resetBtn = document.querySelector<HTMLButtonElement>('button[title="Reset view to initial state (R or Home)"]')
        resetBtn?.addEventListener('click', onResetClick)

        // Cleanup: restore button styles and remove listener on step change
        return () => {
          clearTimers()
          const btn = document.querySelector<HTMLButtonElement>('button[title="Reset view to initial state (R or Home)"]')
          if (btn) {
            btn.style.pointerEvents = ''
            btn.style.position = ''
            btn.style.zIndex = ''
          }
          resetBtn?.removeEventListener('click', onResetClick)
        }
      }
    }

    return () => clearTimers()
  }, [active, step, appRef, clearTimers])

  if (!active) return null

  const currentStep = STEPS[step]
  const isLastStep = step === TOTAL_STEPS - 1

  const overlay = (
    <>
      {/* Scrim + spotlight */}
      {showScrim && !spotlight && (
        <div className="tutorial-scrim" />
      )}
      {spotlight && (
        <div
          className={`tutorial-spotlight ${pulseSpotlight ? 'tutorial-spotlight--pulse' : ''}`}
          style={{
            top: spotlight.y - spotlight.r,
            left: spotlight.x - spotlight.r,
            width: spotlight.r * 2,
            height: spotlight.r * 2,
          }}
        />
      )}

      {/* Map click ripple effect */}
      {mapClickRipple && (
        <div
          className="tutorial-map-ripple"
          style={{ left: mapClickRipple.x, top: mapClickRipple.y }}
        />
      )}

      {/* Text card — raised position during simulation steps to avoid covering QoL */}
      {/* On mobile step 7, don't raise — Reset spotlight is at top and card would cover it */}
      <div className={[
        'tutorial-card',
        step >= 3 && step < 6 ? 'tutorial-card--raised' : '',
        (step === 4 || step === 5) && window.innerWidth >= 768 ? 'tutorial-card--top' : '',
        step === 4 && window.innerWidth < 768 ? 'tutorial-card--hidden' : '',
        step === 6 && window.innerWidth < 768 ? 'tutorial-card--above-nav' : '',
        cardHidden ? 'tutorial-card--hidden' : ''
      ].filter(Boolean).join(' ')} key={step}>
        <h2 className="tutorial-card__headline">{currentStep.headline}</h2>
        <p className="tutorial-card__body">{currentStep.body}</p>
      </div>

      {/* Navigation bar */}
      <nav className={[
        'tutorial-nav',
        step >= 5 ? 'tutorial-nav--above-timeline' : '',
        step === 3 && window.innerWidth < 768 ? 'tutorial-nav--above-map' : '',
        navDimmed ? 'tutorial-nav--dimmed' : ''
      ].filter(Boolean).join(' ')} data-tutorial-nav onClick={() => {
        if (navDimmed) {
          setNavDimmed(false)
          if (navDimTimerRef.current) clearTimeout(navDimTimerRef.current)
          navDimTimerRef.current = window.setTimeout(() => setNavDimmed(true), 3000)
        }
      }}>
        <button
          className="tutorial-nav__skip"
          onClick={handleSkip}
          data-tutorial-nav
        >
          Skip tutorial
        </button>

        <div className="tutorial-nav__progress">
          <span>Step {step + 1} of {TOTAL_STEPS}</span>
          <div className="tutorial-nav__dots">
            {Array.from({ length: TOTAL_STEPS }, (_, i) => (
              <div
                key={i}
                className={`tutorial-nav__dot ${i <= step ? 'tutorial-nav__dot--active' : ''}`}
              />
            ))}
          </div>
        </div>

        <button
          className="tutorial-nav__next"
          onClick={isLastStep ? handleFinalAction : handleNext}
          data-tutorial-nav
        >
          {isLastStep ? 'Start exploring \u2192' : 'Next \u2192'}
        </button>
      </nav>
    </>
  )

  return createPortal(overlay, document.body)
})
