/**
 * DesktopBanner — delayed, dismissible "best on desktop" hint.
 * Appears after 2 seconds on mobile, dismiss lasts for the session only.
 */

import { useEffect, useState } from 'react'

const DELAY_MS = 2000

interface DesktopBannerProps {
  show: boolean
}

export function DesktopBanner({ show }: DesktopBannerProps) {
  const [visible, setVisible] = useState(false)

  useEffect(() => {
    if (!show) {
      setVisible(false)
      return
    }

    const timer = setTimeout(() => setVisible(true), DELAY_MS)
    return () => clearTimeout(timer)
  }, [show])

  if (!visible) return null

  const dismiss = () => {
    setVisible(false)
  }

  return (
    <div
      style={{
        position: 'fixed',
        bottom: 70,
        left: '50%',
        transform: 'translateX(-50%)',
        background: 'rgba(15, 23, 42, 0.88)',
        color: 'white',
        fontSize: 13,
        padding: '10px 40px 10px 16px',
        borderRadius: 24,
        zIndex: 1100,
        whiteSpace: 'nowrap',
        boxShadow: '0 4px 16px rgba(0,0,0,0.25)',
        pointerEvents: 'auto',
      }}
    >
      This visualization works best on a larger screen
      <button
        onClick={dismiss}
        aria-label="Dismiss banner"
        className="touch-target-44"
        style={{
          position: 'absolute',
          top: '50%',
          right: 6,
          transform: 'translateY(-50%)',
          background: 'none',
          border: 'none',
          color: 'rgba(255,255,255,0.7)',
          fontSize: 18,
          cursor: 'pointer',
          padding: '4px 8px',
          lineHeight: 1,
        }}
      >
        ×
      </button>
    </div>
  )
}

export default DesktopBanner
