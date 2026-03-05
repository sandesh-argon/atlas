import { useViewport } from './useViewport'

interface ResponsiveState {
  /** Below 768px — phone/mobile layout (fullscreen panels, hamburger, etc.) */
  isMobileLayout: boolean
  /** Below 768px — phone layout (alias for isMobileLayout) */
  isPhone: boolean
  /** Below 1024px — no split view, but otherwise desktop layout on tablets */
  isTabletOrBelow: boolean
  width: number
  height: number
}

/**
 * Convenience wrapper around useViewport with named layout breakpoint booleans.
 * Tablets (768–1024px) use desktop layout with split view disabled.
 */
export function useResponsive(): ResponsiveState {
  const { width, height } = useViewport()

  return {
    isMobileLayout: width < 768,
    isPhone: width < 768,
    isTabletOrBelow: width < 1024,
    width,
    height,
  }
}
