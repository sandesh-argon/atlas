/**
 * SimulateButton Component - Phase 2
 *
 * Single button to open simulation panel
 */

import { useState } from 'react'

// ============================================
// Types
// ============================================

interface SimulateButtonProps {
  onClick: () => void
  isActive?: boolean
}

// ============================================
// Icon - Robot/CPU icon for "computing" vibe
// ============================================

function ComputeIcon() {
  return (
    <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
      {/* CPU/chip shape */}
      <rect x="4" y="4" width="16" height="16" rx="2" />
      {/* Inner circuit */}
      <rect x="9" y="9" width="6" height="6" />
      {/* Connection pins */}
      <line x1="9" y1="1" x2="9" y2="4" />
      <line x1="15" y1="1" x2="15" y2="4" />
      <line x1="9" y1="20" x2="9" y2="23" />
      <line x1="15" y1="20" x2="15" y2="23" />
      <line x1="20" y1="9" x2="23" y2="9" />
      <line x1="20" y1="15" x2="23" y2="15" />
      <line x1="1" y1="9" x2="4" y2="9" />
      <line x1="1" y1="15" x2="4" y2="15" />
    </svg>
  )
}

// ============================================
// Main Component
// ============================================

export function SimulateButton({ onClick, isActive = false }: SimulateButtonProps) {
  const [isHovering, setIsHovering] = useState(false)

  const getColor = () => {
    if (isActive) return 'white'
    if (isHovering) return '#333'
    return '#666'
  }

  return (
    <button
      onClick={onClick}
      onMouseEnter={() => setIsHovering(true)}
      onMouseLeave={() => setIsHovering(false)}
      title="Simulate"
      style={{
        position: 'fixed',
        bottom: 16,
        left: 16,
        width: 48,
        height: 48,
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'center',
        background: isActive ? '#3B82F6' : 'rgba(255, 255, 255, 0.95)',
        border: isActive ? '1px solid #3B82F6' : '1px solid #d0d5e0',
        borderRadius: 24,
        color: getColor(),
        cursor: 'pointer',
        boxShadow: isActive ? '0 2px 8px rgba(59, 130, 246, 0.4)' : '0 2px 12px rgba(0, 0, 0, 0.1)',
        backdropFilter: 'blur(8px)',
        transition: 'all 0.2s ease',
        transform: isHovering && !isActive ? 'scale(1.05)' : 'scale(1)',
        zIndex: 1000
      }}
    >
      <ComputeIcon />
    </button>
  )
}

// Keep PlayBar export for backwards compatibility but redirect to SimulateButton
export function PlayBar({ onSettingsClick, isActive }: { onSettingsClick: () => void; isActive?: boolean }) {
  return <SimulateButton onClick={onSettingsClick} isActive={isActive} />
}
