/**
 * CSV Export Utilities
 *
 * Pure functions for generating CSV strings from simulation results,
 * downloading them as files, and copying to clipboard.
 * No React or store dependencies.
 */

import type { Intervention, IndicatorInfo } from '../services/api'
import type { ScenarioTemplate } from '../types/scenarioTemplate'

interface EffectRow {
  baseline: number
  simulated: number
  absolute_change: number
  percent_change: number
}

interface TemporalResultsData {
  base_year: number
  horizon_years: number
  effects: Record<string, Record<string, EffectRow>>
}

/** Escape a CSV field: wrap in quotes if it contains commas, quotes, or newlines */
function escapeCSV(value: string): string {
  if (value.includes(',') || value.includes('"') || value.includes('\n')) {
    return `"${value.replace(/"/g, '""')}"`
  }
  return value
}

/**
 * Build the metadata comment header block for CSV files.
 * Lines prefixed with # are ignored by most CSV parsers but visible in text editors.
 */
function buildMetadataHeader(
  interventions: Intervention[],
  country: string | null,
  baseYear: number,
  endYear: number,
  template: ScenarioTemplate | null
): string[] {
  const lines: string[] = []
  lines.push(`# Country: ${country || 'Global'}`)

  const interventionStr = interventions
    .filter(i => i.indicator)
    .map(i => {
      const label = i.indicatorLabel || i.indicator
      const sign = i.change_percent >= 0 ? '+' : ''
      return `${label} ${sign}${i.change_percent}%`
    })
    .join(', ')
  lines.push(`# Interventions: ${interventionStr || 'None'}`)

  lines.push(`# Simulation: ${baseYear}–${endYear}`)

  if (template) {
    lines.push(`# Template: ${template.name}`)
  }

  lines.push(`# Exported: ${new Date().toISOString()}`)
  lines.push('#')

  return lines
}

/**
 * Build an indicator ID → label lookup map.
 */
function buildNameMap(indicators: IndicatorInfo[]): Map<string, string> {
  const map = new Map<string, string>()
  indicators.forEach(ind => map.set(ind.id, ind.label))
  return map
}

/**
 * Generate a CSV string for the final-year simulation summary.
 * Matches the results table view: one row per affected indicator, sorted by |percent_change| desc.
 */
export function generateSummaryCSV(
  results: TemporalResultsData,
  interventions: Intervention[],
  country: string | null,
  indicators: IndicatorInfo[],
  template: ScenarioTemplate | null
): string {
  const nameMap = buildNameMap(indicators)
  const endYear = results.base_year + results.horizon_years
  const header = buildMetadataHeader(interventions, country, results.base_year, endYear, template)

  // Get final year effects
  const yearKeys = Object.keys(results.effects).sort()
  const finalYearKey = yearKeys[yearKeys.length - 1]
  const finalEffects = finalYearKey ? results.effects[finalYearKey] : {}

  // Build rows, filter noise, sort by magnitude
  const rows = Object.entries(finalEffects)
    .map(([id, effect]) => ({
      id,
      name: nameMap.get(id) || id,
      baseline: effect.baseline,
      simulated: effect.simulated,
      absoluteChange: effect.absolute_change,
      percentChange: effect.percent_change
    }))
    .filter(row => Math.abs(row.absoluteChange) > 0.001 && Math.abs(row.baseline) > 0.01)
    .sort((a, b) => Math.abs(b.percentChange) - Math.abs(a.percentChange))

  const csvLines = [
    ...header,
    'Indicator ID,Indicator Name,Baseline,Simulated,Absolute Change,Percent Change',
    ...rows.map(row =>
      [
        escapeCSV(row.id),
        escapeCSV(row.name),
        row.baseline.toFixed(4),
        row.simulated.toFixed(4),
        row.absoluteChange.toFixed(4),
        row.percentChange.toFixed(2)
      ].join(',')
    )
  ]

  return csvLines.join('\n')
}

/**
 * Generate a CSV string with all years and all affected indicators.
 * One row per indicator per year, sorted by year asc then |percent_change| desc.
 */
export function generateTimelineCSV(
  results: TemporalResultsData,
  interventions: Intervention[],
  country: string | null,
  indicators: IndicatorInfo[],
  template: ScenarioTemplate | null
): string {
  const nameMap = buildNameMap(indicators)
  const endYear = results.base_year + results.horizon_years
  const header = buildMetadataHeader(interventions, country, results.base_year, endYear, template)

  const yearKeys = Object.keys(results.effects).sort()

  const allRows: string[] = []
  for (const yearKey of yearKeys) {
    const yearEffects = results.effects[yearKey]
    const rows = Object.entries(yearEffects)
      .map(([id, effect]) => ({
        year: yearKey,
        id,
        name: nameMap.get(id) || id,
        baseline: effect.baseline,
        simulated: effect.simulated,
        absoluteChange: effect.absolute_change,
        percentChange: effect.percent_change
      }))
      .filter(row => Math.abs(row.absoluteChange) > 0.001 && Math.abs(row.baseline) > 0.01)
      .sort((a, b) => Math.abs(b.percentChange) - Math.abs(a.percentChange))

    for (const row of rows) {
      allRows.push(
        [
          row.year,
          escapeCSV(row.id),
          escapeCSV(row.name),
          row.baseline.toFixed(4),
          row.simulated.toFixed(4),
          row.absoluteChange.toFixed(4),
          row.percentChange.toFixed(2)
        ].join(',')
      )
    }
  }

  const csvLines = [
    ...header,
    'Year,Indicator ID,Indicator Name,Baseline,Simulated,Absolute Change,Percent Change',
    ...allRows
  ]

  return csvLines.join('\n')
}

/**
 * Trigger a browser file download from a CSV string.
 */
export function downloadCSV(csvString: string, filename: string): void {
  const blob = new Blob([csvString], { type: 'text/csv;charset=utf-8;' })
  const url = URL.createObjectURL(blob)
  const link = document.createElement('a')
  link.href = url
  link.download = filename
  link.style.display = 'none'
  document.body.appendChild(link)
  link.click()
  document.body.removeChild(link)
  URL.revokeObjectURL(url)
}

/**
 * Copy a CSV string to the clipboard.
 * Uses navigator.clipboard with textarea fallback for older browsers.
 */
export async function copyCSVToClipboard(csvString: string): Promise<boolean> {
  try {
    await navigator.clipboard.writeText(csvString)
    return true
  } catch {
    try {
      const textArea = document.createElement('textarea')
      textArea.value = csvString
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

/**
 * Generate a filename for CSV export.
 * Format: simulation-{country}-{type}-{date}.csv
 */
export function makeCSVFilename(country: string | null, type: 'summary' | 'timeline'): string {
  const countrySlug = (country || 'global').toLowerCase().replace(/\s+/g, '-')
  const date = new Date().toISOString().slice(0, 10)
  return `simulation-${countrySlug}-${type}-${date}.csv`
}
