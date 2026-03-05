/**
 * URL State Management
 *
 * Encodes/decodes application state to/from URL for shareable links.
 * Uses query parameters for readability with base64 fallback for complex state.
 */

import type { ViewMode } from '../types'
import type { IncomeStratum } from '../services/api'
import { SIMULATION_YEAR_MIN, SIMULATION_YEAR_MAX } from '../constants/time'

/** Compact intervention for URL encoding */
export interface URLIntervention {
  ind: string   // indicator ID
  pct: number   // change_percent
  yr?: number   // optional year
}

/**
 * State to persist in URL
 */
export interface URLState {
  view: ViewMode
  expanded?: string[]      // Expanded node IDs (Global View)
  targets?: string[]       // Target node IDs (Local View)
  beta?: number            // Beta threshold
  highlight?: string       // Highlighted/searched node
  zoom?: {
    k: number              // Scale
    x: number              // Pan X
    y: number              // Pan Y
  }
  // Simulation state
  country?: string                    // Country name (e.g. "India")
  stratum?: IncomeStratum | 'unified' // Income stratum
  interventions?: URLIntervention[]   // Compact intervention list
  template?: string                   // Template ID (e.g. "bolsa_familia")
  simStart?: number                   // simulationStartYear
  simEnd?: number                     // simulationEndYear
}

/**
 * Encode state to URL search params
 */
export function encodeStateToURL(state: URLState): string {
  const params = new URLSearchParams()

  // View mode (always included)
  params.set('v', state.view)

  // Expanded nodes (comma-separated)
  if (state.expanded && state.expanded.length > 0) {
    params.set('e', state.expanded.join(','))
  }

  // Local View targets (comma-separated)
  if (state.targets && state.targets.length > 0) {
    params.set('t', state.targets.join(','))
  }

  // Beta threshold (only if not default)
  if (state.beta !== undefined && state.beta !== 0.5) {
    params.set('b', state.beta.toFixed(2))
  }

  // Highlighted node
  if (state.highlight) {
    params.set('h', state.highlight)
  }

  // Zoom state (compact format: k,x,y)
  if (state.zoom) {
    params.set('z', `${state.zoom.k.toFixed(2)},${state.zoom.x.toFixed(0)},${state.zoom.y.toFixed(0)}`)
  }

  // Simulation: country
  if (state.country) {
    params.set('c', state.country)
  }

  // Simulation: stratum (omit if 'unified' which is default)
  if (state.stratum && state.stratum !== 'unified') {
    params.set('st', state.stratum)
  }

  // Simulation: interventions (compact: indicator~pct~yr,indicator~pct,...)
  if (state.interventions && state.interventions.length > 0) {
    const encoded = state.interventions.map(iv => {
      const parts = [iv.ind, String(iv.pct)]
      if (iv.yr !== undefined) parts.push(String(iv.yr))
      return parts.join('~')
    }).join(',')
    params.set('i', encoded)
  }

  // Simulation: template ID
  if (state.template) {
    params.set('tp', state.template)
  }

  // Simulation: year range (omit defaults)
  if (state.simStart !== undefined && state.simStart !== 2020) {
    params.set('sy', String(state.simStart))
  }
  if (state.simEnd !== undefined && state.simEnd !== 2029) {
    params.set('ey', String(state.simEnd))
  }

  return params.toString()
}

/**
 * Decode URL search params to state
 */
export function decodeStateFromURL(search: string): Partial<URLState> | null {
  if (!search || search === '?') return null

  try {
    const params = new URLSearchParams(search)
    const state: Partial<URLState> = {}

    // View mode
    const view = params.get('v')
    if (view && ['global', 'local', 'split'].includes(view)) {
      state.view = view as ViewMode
    }

    // Expanded nodes
    const expanded = params.get('e')
    if (expanded) {
      state.expanded = expanded.split(',').filter(Boolean)
    }

    // Local View targets
    const targets = params.get('t')
    if (targets) {
      state.targets = targets.split(',').filter(Boolean)
    }

    // Beta threshold
    const beta = params.get('b')
    if (beta) {
      const parsed = parseFloat(beta)
      if (!isNaN(parsed) && parsed >= 0 && parsed <= 10) {
        state.beta = parsed
      }
    }

    // Highlighted node
    const highlight = params.get('h')
    if (highlight) {
      state.highlight = highlight
    }

    // Zoom state
    const zoom = params.get('z')
    if (zoom) {
      const parts = zoom.split(',')
      if (parts.length === 3) {
        const k = parseFloat(parts[0])
        const x = parseFloat(parts[1])
        const y = parseFloat(parts[2])
        if (!isNaN(k) && !isNaN(x) && !isNaN(y)) {
          state.zoom = { k, x, y }
        }
      }
    }

    // Simulation: country
    const country = params.get('c')
    if (country) {
      state.country = country
    }

    // Simulation: stratum
    const stratum = params.get('st')
    const validStrata: Array<IncomeStratum | 'unified'> = ['unified', 'developing', 'emerging', 'advanced']
    if (stratum && validStrata.includes(stratum as IncomeStratum | 'unified')) {
      state.stratum = stratum as IncomeStratum | 'unified'
    }

    // Simulation: interventions (compact: indicator~pct~yr,indicator~pct,...)
    const interventionsStr = params.get('i')
    if (interventionsStr) {
      const parsed: URLIntervention[] = []
      const entries = interventionsStr.split(',').filter(Boolean)
      for (const entry of entries.slice(0, 5)) { // Cap at 5
        const parts = entry.split('~')
        if (parts.length >= 2) {
          const pct = parseFloat(parts[1])
          if (!isNaN(pct)) {
            const iv: URLIntervention = { ind: parts[0], pct }
            if (parts.length >= 3) {
              const yr = parseInt(parts[2], 10)
              if (!isNaN(yr)) iv.yr = yr
            }
            parsed.push(iv)
          }
        }
      }
      if (parsed.length > 0) {
        state.interventions = parsed
      }
    }

    // Simulation: template ID
    const template = params.get('tp')
    if (template) {
      state.template = template
    }

    // Simulation: year range
    const sy = params.get('sy')
    if (sy) {
      const parsed = parseInt(sy, 10)
      if (!isNaN(parsed) && parsed >= SIMULATION_YEAR_MIN && parsed <= SIMULATION_YEAR_MAX) {
        state.simStart = parsed
      }
    }
    const ey = params.get('ey')
    if (ey) {
      const parsed = parseInt(ey, 10)
      if (!isNaN(parsed) && parsed >= SIMULATION_YEAR_MIN && parsed <= SIMULATION_YEAR_MAX) {
        state.simEnd = parsed
      }
    }

    return Object.keys(state).length > 0 ? state : null
  } catch {
    return null
  }
}

/**
 * Update browser URL without navigation
 */
export function updateBrowserURL(state: URLState): void {
  const encoded = encodeStateToURL(state)
  const newURL = encoded ? `?${encoded}` : window.location.pathname
  window.history.replaceState(null, '', newURL)
}

/**
 * Get current state from browser URL
 */
export function getStateFromBrowserURL(): Partial<URLState> | null {
  return decodeStateFromURL(window.location.search)
}

/**
 * Generate a shareable URL for current state
 */
export function generateShareableURL(state: URLState): string {
  const encoded = encodeStateToURL(state)
  const base = window.location.origin + window.location.pathname
  return encoded ? `${base}?${encoded}` : base
}

/**
 * Copy URL to clipboard and return success status
 */
export async function copyURLToClipboard(state: URLState): Promise<boolean> {
  try {
    const url = generateShareableURL(state)
    await navigator.clipboard.writeText(url)
    return true
  } catch {
    // Fallback for older browsers
    try {
      const url = generateShareableURL(state)
      const textArea = document.createElement('textarea')
      textArea.value = url
      textArea.style.position = 'fixed'
      textArea.style.left = '-9999px'
      document.body.appendChild(textArea)
      textArea.select()
      document.execCommand('copy')
      document.body.removeChild(textArea)
      return true
    } catch {
      return false
    }
  }
}
