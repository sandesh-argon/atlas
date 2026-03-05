/**
 * Screen reader live region announcer.
 * Sets textContent on a visually-hidden aria-live div so screen readers
 * speak state changes (country selection, simulation results, etc.).
 */

let liveRegion: HTMLDivElement | null = null

/** Ensure the live region div exists in the DOM. Called once from App mount. */
export function initAnnouncer(): void {
  if (liveRegion) return
  liveRegion = document.createElement('div')
  liveRegion.setAttribute('aria-live', 'polite')
  liveRegion.setAttribute('aria-atomic', 'true')
  liveRegion.setAttribute('role', 'status')
  liveRegion.className = 'sr-only'
  document.body.appendChild(liveRegion)
}

/** Announce a message to screen readers via the live region. */
export function announce(message: string): void {
  if (!liveRegion) return
  // Clear then set — forces re-announcement even if text is identical
  liveRegion.textContent = ''
  requestAnimationFrame(() => {
    if (liveRegion) liveRegion.textContent = message
  })
}
