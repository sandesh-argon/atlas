import { useEffect, useRef, useState } from 'react'

export function usePresence(isOpen: boolean, exitMs: number) {
  const [isMounted, setIsMounted] = useState(isOpen)
  const [isVisible, setIsVisible] = useState(isOpen)
  const exitTimerRef = useRef<number | null>(null)
  const rafRef = useRef<number | null>(null)

  useEffect(() => {
    if (isOpen) {
      if (exitTimerRef.current !== null) {
        clearTimeout(exitTimerRef.current)
        exitTimerRef.current = null
      }
      setIsMounted(true)
      rafRef.current = requestAnimationFrame(() => {
        rafRef.current = null
        setIsVisible(true)
      })
      return
    }

    setIsVisible(false)
    if (exitTimerRef.current !== null) {
      clearTimeout(exitTimerRef.current)
    }
    exitTimerRef.current = window.setTimeout(() => {
      exitTimerRef.current = null
      setIsMounted(false)
    }, exitMs)
  }, [isOpen, exitMs])

  useEffect(() => {
    return () => {
      if (exitTimerRef.current !== null) {
        clearTimeout(exitTimerRef.current)
        exitTimerRef.current = null
      }
      if (rafRef.current !== null) {
        cancelAnimationFrame(rafRef.current)
        rafRef.current = null
      }
    }
  }, [])

  return { isMounted, isVisible }
}
