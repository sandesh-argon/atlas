/**
 * StrataTabs - Tab switcher for income stratification views
 *
 * Four tabs: Unified, Developing, Emerging, Advanced
 * Simple tab selection without counters or animations
 */

import type { IncomeStratum } from '../services/api'

type Stratum = IncomeStratum | 'unified'

interface StrataTabsProps {
  activeStratum: Stratum
  onStratumChange: (stratum: Stratum) => void
  disabled?: boolean
  /** Use short labels below 1200px viewport */
  compact?: boolean
}

// Stratum configuration
const STRATA_CONFIG: {
  id: Stratum
  label: string
  shortLabel: string
  color: string
  minWidth: number
  compactMinWidth: number
  definition: string
  gdpThreshold?: string
}[] = [
  {
    id: 'unified',
    label: 'Unified',
    shortLabel: 'All',
    color: '#3B82F6',
    minWidth: 65,
    compactMinWidth: 40,
    definition: 'All countries pooled together'
  },
  {
    id: 'developing',
    label: 'Developing',
    shortLabel: 'Dev',
    color: '#EF5350',
    minWidth: 85,
    compactMinWidth: 45,
    definition: 'Low + Lower-middle income economies',
    gdpThreshold: 'GNI < $4,500/capita'
  },
  {
    id: 'emerging',
    label: 'Emerging',
    shortLabel: 'Emrg',
    color: '#FFA726',
    minWidth: 75,
    compactMinWidth: 50,
    definition: 'Upper-middle income economies',
    gdpThreshold: 'GNI $4,500 - $14,000/capita'
  },
  {
    id: 'advanced',
    label: 'Advanced',
    shortLabel: 'Adv',
    color: '#66BB6A',
    minWidth: 75,
    compactMinWidth: 45,
    definition: 'High income economies',
    gdpThreshold: 'GNI > $14,000/capita'
  }
]

/**
 * Tab switcher for income stratification
 */
export function StrataTabs({
  activeStratum,
  onStratumChange,
  disabled = false,
  compact = false
}: StrataTabsProps) {
  return (
    <div
      style={{
        display: 'flex',
        background: 'white',
        borderRadius: 6,
        boxShadow: '0 2px 4px rgba(0,0,0,0.1)',
        border: '1px solid #d0d5e0',
        overflow: 'hidden',
        alignSelf: 'flex-start',
        height: 'fit-content',
        opacity: disabled ? 0.5 : 1,
        pointerEvents: disabled ? 'none' : 'auto'
      }}
    >
      {STRATA_CONFIG.map((stratum, index) => {
        const isActive = activeStratum === stratum.id
        const tooltip = stratum.gdpThreshold
          ? `${stratum.definition}\n${stratum.gdpThreshold}`
          : stratum.definition

        return (
          <button
            key={stratum.id}
            onClick={() => onStratumChange(stratum.id)}
            disabled={disabled}
            style={{
              position: 'relative',
              padding: compact ? '8px 10px' : '8px 16px',
              fontSize: 13,
              fontWeight: isActive ? 600 : 400,
              cursor: disabled ? 'default' : 'pointer',
              border: 'none',
              borderLeft: index > 0 ? '1px solid #d0d5e0' : 'none',
              background: 'white',
              color: '#333',
              transition: 'color 0.15s ease',
              minWidth: compact ? stratum.compactMinWidth : stratum.minWidth,
              textAlign: 'center' as const,
              overflow: 'hidden',
              whiteSpace: 'nowrap'
            }}
            title={tooltip}
          >
            {/* Active indicator fill */}
            {isActive && (
              <span
                style={{
                  position: 'absolute',
                  top: 0,
                  left: 0,
                  height: '100%',
                  width: '100%',
                  background: stratum.color,
                  opacity: 1,
                  zIndex: 0
                }}
              />
            )}
            {/* Label text */}
            <span style={{ position: 'relative', zIndex: 1 }}>
              {compact ? stratum.shortLabel : stratum.label}
            </span>
          </button>
        )
      })}
    </div>
  )
}

export default StrataTabs
