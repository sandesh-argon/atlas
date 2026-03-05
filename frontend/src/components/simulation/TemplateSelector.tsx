/**
 * TemplateSelector Component
 *
 * Dropdown picker for pre-built scenario templates with collapsible info panel.
 * Loads templates from public/data/scenario-templates.json on first render.
 */

import { useEffect, useState, useCallback } from 'react'
import { useSimulationStore } from '../../stores/simulationStore'
import type { ScenarioTemplate } from '../../types/scenarioTemplate'

// ============================================
// Constants
// ============================================

const CATEGORY_EMOJI: Record<string, string> = {
  health: '\u{1F3E5}',
  education: '\u{1F4DA}',
  infrastructure: '\u{1F3D7}',
  governance: '\u2696\uFE0F',
  economy: '\u{1F4C8}',
  environment: '\u{1F33F}'
}

const DIFFICULTY_COLORS: Record<string, { bg: string; text: string }> = {
  easy: { bg: '#E8F5E9', text: '#2E7D32' },
  moderate: { bg: '#FFF3E0', text: '#E65100' },
  hard: { bg: '#FFEBEE', text: '#C62828' }
}

const FEASIBILITY_COLORS: Record<string, { bg: string; text: string }> = {
  low: { bg: '#FFEBEE', text: '#C62828' },
  medium: { bg: '#FFF3E0', text: '#E65100' },
  high: { bg: '#E8F5E9', text: '#2E7D32' }
}

// ============================================
// Badge sub-component
// ============================================

function Badge({ label, bg, text }: { label: string; bg: string; text: string }) {
  return (
    <span style={{
      display: 'inline-block',
      padding: '1px 5px',
      borderRadius: 3,
      fontSize: 10,
      fontWeight: 600,
      background: bg,
      color: text,
      marginLeft: 4
    }}>
      {label}
    </span>
  )
}

// ============================================
// Main Component
// ============================================

export function TemplateSelector() {
  const {
    templates,
    templatesLoaded,
    templatesLoading,
    templatesError,
    activeTemplate,
    templateModified,
    loadTemplates,
    applyTemplate,
    resetTemplate,
    clearTemplate
  } = useSimulationStore()

  const [showOutcomes, setShowOutcomes] = useState(false)
  const [showEvidence, setShowEvidence] = useState(false)
  const [descExpanded, setDescExpanded] = useState(false)

  // Auto-collapse info sections when template clears externally (e.g. clearResults)
  useEffect(() => {
    if (!activeTemplate) {
      setShowOutcomes(false)
      setShowEvidence(false)
      setDescExpanded(false)
    }
  }, [activeTemplate])

  // Load templates lazily on first render
  useEffect(() => {
    if (!templatesLoaded) {
      loadTemplates()
    }
  }, [templatesLoaded, loadTemplates])

  const handleSelectChange = useCallback((e: React.ChangeEvent<HTMLSelectElement>) => {
    const id = e.target.value
    if (id) {
      applyTemplate(id)
      setShowOutcomes(false)
      setShowEvidence(false)
      setDescExpanded(false)
    }
  }, [applyTemplate])

  const handleClear = useCallback(() => {
    clearTemplate()
    setShowOutcomes(false)
    setShowEvidence(false)
    setDescExpanded(false)
  }, [clearTemplate])

  // Group templates by category for optgroups
  const groupedTemplates = templates.reduce<Record<string, ScenarioTemplate[]>>((acc, t) => {
    const cat = t.category
    if (!acc[cat]) acc[cat] = []
    acc[cat].push(t)
    return acc
  }, {})

  const t = activeTemplate

  return (
    <div>
      {/* Header row */}
      <div style={{
        display: 'flex',
        justifyContent: 'space-between',
        alignItems: 'center',
        marginBottom: 8
      }}>
        <span style={{ fontSize: 12, fontWeight: 600, color: '#333' }}>
          Policy Templates
        </span>
      </div>

      {/* Dropdown + clear button */}
      <div style={{ display: 'flex', gap: 6, alignItems: 'center' }}>
        <select
          id="policy-template"
          name="policy-template"
          value={activeTemplate?.id ?? ''}
          onChange={handleSelectChange}
          disabled={templatesLoading}
          style={{
            flex: 1,
            padding: '6px 8px',
            borderRadius: 4,
            border: '1px solid #d0d5e0',
            background: 'white',
            color: '#333',
            fontSize: 12,
            cursor: 'pointer'
          }}
          aria-label="Select a policy template"
        >
          <option value="">{templatesLoading ? 'Loading templates...' : 'Select template...'}</option>
          {Object.entries(groupedTemplates).map(([category, tmps]) => (
            <optgroup key={category} label={`${CATEGORY_EMOJI[category] ?? ''} ${category.charAt(0).toUpperCase() + category.slice(1)}`}>
              {tmps.map(tmp => (
                <option key={tmp.id} value={tmp.id} title={tmp.description}>
                  {tmp.short_name} ({tmp.source}, {tmp.year})
                </option>
              ))}
            </optgroup>
          ))}
        </select>

        {activeTemplate && (
          <button
            className="touch-target-44"
            onClick={handleClear}
            title="Clear template"
            aria-label="Clear template"
            style={{
              background: 'none',
              border: 'none',
              color: '#767676',
              fontSize: 16,
              cursor: 'pointer',
              padding: '4px 8px',
              lineHeight: 1
            }}
            onMouseEnter={(e) => e.currentTarget.style.color = '#666'}
            onMouseLeave={(e) => e.currentTarget.style.color = '#999'}
          >
            \u00D7
          </button>
        )}
      </div>

      {templatesError && (
        <div style={{ marginTop: 6, fontSize: 11, color: '#B91C1C' }}>
          <div style={{ marginBottom: 4 }}>Failed to load templates: {templatesError}</div>
          <button
            onClick={loadTemplates}
            style={{
              padding: '4px 8px',
              border: '1px solid #FCA5A5',
              borderRadius: 4,
              background: '#FEF2F2',
              color: '#B91C1C',
              fontSize: 11,
              cursor: 'pointer'
            }}
          >
            Retry
          </button>
        </div>
      )}

      {/* Info panel (when template is active) */}
      {t && (
        <div style={{
          marginTop: 8,
          padding: '10px 12px',
          background: '#f8f9ff',
          border: '1px solid #e0e4f0',
          borderRadius: 5
        }}>
          {/* Name */}
          <div style={{ fontSize: 13, fontWeight: 600, color: '#333', marginBottom: 4 }}>
            {t.name}
          </div>

          {/* Source + badges */}
          <div style={{ fontSize: 11, color: '#767676', marginBottom: 6, display: 'flex', alignItems: 'center', flexWrap: 'wrap', gap: 2 }}>
            <span>{t.source}, {t.year}</span>
            <Badge
              label={t.difficulty}
              bg={DIFFICULTY_COLORS[t.difficulty]?.bg ?? '#e2e6ee'}
              text={DIFFICULTY_COLORS[t.difficulty]?.text ?? '#666'}
            />
            <Badge
              label={`${t.political_feasibility} feasibility`}
              bg={FEASIBILITY_COLORS[t.political_feasibility]?.bg ?? '#e2e6ee'}
              text={FEASIBILITY_COLORS[t.political_feasibility]?.text ?? '#666'}
            />
          </div>

          {/* Description (expandable) */}
          <div
            onClick={() => setDescExpanded(!descExpanded)}
            style={{
              fontSize: 11,
              color: '#555',
              marginBottom: 8,
              cursor: 'pointer',
              ...(!descExpanded ? {
                display: '-webkit-box',
                WebkitLineClamp: 2,
                WebkitBoxOrient: 'vertical' as const,
                overflow: 'hidden'
              } : {})
            }}
            title={descExpanded ? 'Click to collapse' : 'Click to expand'}
          >
            {t.description}
          </div>

          {/* Collapsible: Expected Outcomes */}
          <div style={{ marginBottom: 4 }}>
            <button
              onClick={() => setShowOutcomes(!showOutcomes)}
              style={{
                background: 'none',
                border: 'none',
                color: '#5C6BC0',
                fontSize: 11,
                cursor: 'pointer',
                padding: 0,
                fontWeight: 500
              }}
            >
              {showOutcomes ? '\u25BE' : '\u25B8'} Expected outcomes
            </button>
            {showOutcomes && (
              <div style={{ fontSize: 11, color: '#555', marginTop: 4, paddingLeft: 10 }}>
                <div style={{ fontWeight: 500, marginBottom: 2 }}>{t.expected_outcomes.primary}</div>
                {t.expected_outcomes.secondary.map((s, i) => (
                  <div key={i} style={{ color: '#777', marginLeft: 4 }}>{'\u2022'} {s}</div>
                ))}
                <div style={{ color: '#767676', marginTop: 4, fontStyle: 'italic' }}>
                  Time horizon: {t.expected_outcomes.time_horizon_years} years
                </div>
              </div>
            )}
          </div>

          {/* Collapsible: Evidence */}
          <div style={{ marginBottom: 4 }}>
            <button
              onClick={() => setShowEvidence(!showEvidence)}
              style={{
                background: 'none',
                border: 'none',
                color: '#5C6BC0',
                fontSize: 11,
                cursor: 'pointer',
                padding: 0,
                fontWeight: 500
              }}
            >
              {showEvidence ? '\u25BE' : '\u25B8'} Evidence
            </button>
            {showEvidence && (
              <div style={{ fontSize: 11, color: '#555', marginTop: 4, paddingLeft: 10 }}>
                <div style={{ marginBottom: 4, fontStyle: 'italic', color: '#666' }}>
                  {'\u201C'}{t.evidence.case_study}{'\u201D'}
                </div>
                {t.evidence.citations.map((c, i) => (
                  <div key={i} style={{ color: '#767676', fontSize: 10 }}>{c}</div>
                ))}
              </div>
            )}
          </div>

          {/* Target audience */}
          <div style={{ fontSize: 10, color: '#767676', marginTop: 4 }}>
            Target: {t.target_audience}
          </div>

          {/* Cost estimate */}
          <div style={{ fontSize: 10, color: '#767676' }}>
            Est. cost: {t.cost_estimate_usd}
          </div>

          {/* Reset to defaults button (only when user has modified template interventions) */}
          {templateModified && (
            <button
              onClick={resetTemplate}
              style={{
                width: '100%',
                marginTop: 8,
                padding: '6px 12px',
                borderRadius: 4,
                border: '1px dashed #bcc3d4',
                background: 'transparent',
                color: '#666',
                fontSize: 11,
                cursor: 'pointer',
                transition: 'all 0.2s'
              }}
              onMouseEnter={(e) => {
                e.currentTarget.style.background = '#f0f0f0'
                e.currentTarget.style.borderColor = '#999'
              }}
              onMouseLeave={(e) => {
                e.currentTarget.style.background = 'transparent'
                e.currentTarget.style.borderColor = '#bcc3d4'
              }}
            >
              Reset to policy defaults
            </button>
          )}
        </div>
      )}
    </div>
  )
}

export default TemplateSelector
