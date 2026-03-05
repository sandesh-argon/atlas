import { useEffect, useRef, type ReactNode } from 'react'

interface SidebarDrawerProps {
  /** Whether the viewport is below 1024px (mobile layout) */
  isMobileLayout: boolean
  /** Whether the drawer is open (mobile only) */
  isOpen: boolean
  /** Toggle drawer open/closed */
  onToggle: () => void
  /** Close the drawer */
  onClose: () => void
  /** Whether strata tabs are visible above the hamburger (mobile only) */
  strataVisible?: boolean
  /** Hide hamburger when a fullscreen panel is open */
  hideHamburger?: boolean
  children: ReactNode
}

/**
 * On desktop (>=1024px): transparent pass-through, renders children as-is.
 * On mobile (<1024px): hamburger button + slide-in drawer with backdrop.
 */
export function SidebarDrawer({
  isMobileLayout,
  isOpen,
  onToggle,
  onClose,
  strataVisible = false,
  hideHamburger = false,
  children,
}: SidebarDrawerProps) {
  const drawerRef = useRef<HTMLDivElement>(null)

  // Focus trap inside drawer when open
  useEffect(() => {
    if (!isMobileLayout || !isOpen) return

    const handleKeyDown = (e: KeyboardEvent) => {
      if (e.key === 'Escape') {
        onClose()
        return
      }
      if (e.key === 'Tab' && drawerRef.current) {
        const focusable = drawerRef.current.querySelectorAll<HTMLElement>(
          'input:not([disabled]), button:not([disabled]), select:not([disabled]), [tabindex="0"]'
        )
        if (focusable.length === 0) return
        const first = focusable[0]
        const last = focusable[focusable.length - 1]
        if (e.shiftKey && document.activeElement === first) {
          e.preventDefault()
          last.focus()
        } else if (!e.shiftKey && document.activeElement === last) {
          e.preventDefault()
          first.focus()
        }
      }
    }

    document.addEventListener('keydown', handleKeyDown)
    return () => document.removeEventListener('keydown', handleKeyDown)
  }, [isMobileLayout, isOpen, onClose])

  // Focus first element on open
  useEffect(() => {
    if (isMobileLayout && isOpen && drawerRef.current) {
      requestAnimationFrame(() => {
        const first = drawerRef.current?.querySelector<HTMLElement>('input, button, [tabindex="0"]')
        first?.focus()
      })
    }
  }, [isMobileLayout, isOpen])

  // Desktop: pass-through
  if (!isMobileLayout) {
    return <>{children}</>
  }

  return (
    <>
      {/* Hamburger button — visible on mobile unless a fullscreen panel covers it */}
      <button
        onClick={onToggle}
        aria-label={isOpen ? 'Close sidebar menu' : 'Open sidebar menu'}
        aria-expanded={isOpen}
        style={{
          position: 'fixed',
          top: strataVisible ? 58 : 16,
          left: 10,
          zIndex: 1051,
          display: (hideHamburger || isOpen) ? 'none' : 'flex',
          width: 44,
          height: 44,
          alignItems: 'center',
          justifyContent: 'center',
          background: 'rgba(255,255,255,0.95)',
          border: '1px solid #d0d5e0',
          borderRadius: 8,
          cursor: 'pointer',
          boxShadow: '0 2px 8px rgba(0,0,0,0.1)',
          backdropFilter: 'blur(8px)',
        }}
      >
        <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="#555" strokeWidth="2" strokeLinecap="round">
          <line x1="3" y1="6" x2="21" y2="6" />
          <line x1="3" y1="12" x2="21" y2="12" />
          <line x1="3" y1="18" x2="21" y2="18" />
        </svg>
      </button>

      {/* Backdrop */}
      {isOpen && (
        <div
          onClick={onClose}
          aria-hidden="true"
          style={{
            position: 'fixed',
            inset: 0,
            zIndex: 1049,
            background: 'rgba(0,0,0,0.3)',
            transition: 'opacity 200ms ease',
          }}
        />
      )}

      {/* Drawer */}
      <div
        ref={drawerRef}
        role="dialog"
        aria-modal="true"
        aria-label="Sidebar navigation"
        style={{
          position: 'fixed',
          top: 0,
          left: 0,
          bottom: 0,
          width: 'min(300px, 85vw)',
          zIndex: 1050,
          background: '#fff',
          boxShadow: isOpen ? '4px 0 20px rgba(0,0,0,0.15)' : 'none',
          transform: isOpen ? 'translateX(0)' : 'translateX(-100%)',
          transition: 'transform 200ms ease',
          display: 'flex',
          flexDirection: 'column',
          overflow: 'hidden',
        }}
      >
        {/* Drawer header with close button */}
        <div style={{
          display: 'flex',
          justifyContent: 'space-between',
          alignItems: 'center',
          padding: '12px 14px',
          borderBottom: '1px solid #e2e6ee',
          flexShrink: 0,
        }}>
          <span style={{ fontWeight: 600, fontSize: 14, color: '#333' }}>
            Menu
          </span>
          <button
            onClick={onClose}
            aria-label="Close sidebar"
            style={{
              width: 44,
              height: 44,
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center',
              background: 'none',
              border: 'none',
              cursor: 'pointer',
              color: '#666',
              fontSize: 20,
            }}
          >
            ×
          </button>
        </div>

        {/* Drawer body — scrollable, renders sidebar children */}
        <div style={{
          flex: 1,
          overflowY: 'auto',
          overflowX: 'hidden',
          padding: '12px 10px',
          fontSize: 14,
        }}>
          {children}
        </div>
      </div>
    </>
  )
}

export default SidebarDrawer
