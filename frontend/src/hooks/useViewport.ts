import { useState, useEffect, useCallback } from 'react'

interface ViewportState {
  width: number
  height: number
  isBelow: (breakpoint: number) => boolean
}

/**
 * Lightweight hook that tracks window dimensions with debounced resize.
 * Replaces scattered window.innerWidth calls in panel positioning code.
 */
export function useViewport(debounceMs = 200): ViewportState {
  const [dimensions, setDimensions] = useState(() => ({
    width: typeof window !== 'undefined' ? window.innerWidth : 1920,
    height: typeof window !== 'undefined' ? window.innerHeight : 1080,
  }))

  useEffect(() => {
    let timeoutId: ReturnType<typeof setTimeout>

    const handleResize = () => {
      clearTimeout(timeoutId)
      timeoutId = setTimeout(() => {
        setDimensions({
          width: window.innerWidth,
          height: window.innerHeight,
        })
      }, debounceMs)
    }

    window.addEventListener('resize', handleResize)
    return () => {
      window.removeEventListener('resize', handleResize)
      clearTimeout(timeoutId)
    }
  }, [debounceMs])

  const isBelow = useCallback(
    (breakpoint: number) => dimensions.width < breakpoint,
    [dimensions.width]
  )

  return { width: dimensions.width, height: dimensions.height, isBelow }
}
