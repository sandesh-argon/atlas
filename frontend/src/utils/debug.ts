/**
 * DEBUG SYSTEM
 *
 * Runtime logs are opt-in and disabled by default.
 * Enable with:
 * - VITE_DEBUG=true
 * - Optional VITE_DEBUG_CATEGORIES=cache,error,Layout
 */

const IS_DEV = import.meta.env.DEV
const DEBUG_ENABLED = IS_DEV && import.meta.env.VITE_DEBUG === 'true'
const DEBUG_CATEGORIES = (import.meta.env.VITE_DEBUG_CATEGORIES || '')
  .split(',')
  .map((part: string) => part.trim())
  .filter(Boolean)
const PERF_ENABLED = DEBUG_ENABLED || import.meta.env.VITE_DEBUG_PERF === 'true'
const ALL_CATEGORIES_ENABLED = DEBUG_CATEGORIES.includes('*')

const CATEGORY_DEFAULTS: Record<string, boolean> = {
  Layout: false,
  Viewport: false,
  Render: false,
  Sector: false,
  Space: false,
  Overlap: false,
  cache: false,
  error: true,
}

const noop = (): void => {}

const isCategoryEnabled = (category: string): boolean => {
  if (!DEBUG_ENABLED) return false
  if (ALL_CATEGORIES_ENABLED) return true
  if (DEBUG_CATEGORIES.length > 0) return DEBUG_CATEGORIES.includes(category)
  return CATEGORY_DEFAULTS[category] ?? false
}

const createLogger = (prefix: string) =>
  isCategoryEnabled(prefix)
    ? console.log.bind(console, `[${prefix}]`)
    : noop

const createWarn = (prefix: string) =>
  isCategoryEnabled(prefix)
    ? console.warn.bind(console, `[${prefix}]`)
    : noop

const createError = (prefix: string) =>
  isCategoryEnabled(prefix)
    ? console.error.bind(console, `[${prefix}]`)
    : noop

const categoryLogger = (method: 'log' | 'warn' | 'error') => {
  return (category: string, ...args: unknown[]) => {
    if (!isCategoryEnabled(category)) return
    if (method === 'error') {
      console.error(`[${category}]`, ...args)
      return
    }
    if (method === 'warn') {
      console.warn(`[${category}]`, ...args)
      return
    }
    console.log(`[${category}]`, ...args)
  }
}

export const debug = {
  layout: createLogger('Layout'),
  layoutWarn: createWarn('Layout'),
  viewport: createLogger('Viewport'),
  viewportWarn: createWarn('Viewport'),
  render: createLogger('Render'),
  renderWarn: createWarn('Render'),
  sector: createLogger('Sector'),
  space: createLogger('Space'),
  overlap: createLogger('Overlap'),
  perf: PERF_ENABLED ? console.time.bind(console) : noop,
  perfEnd: PERF_ENABLED ? console.timeEnd.bind(console) : noop,
  log: categoryLogger('log'),
  warn: categoryLogger('warn'),
  error: categoryLogger('error'),
  cache: createLogger('cache'),
  cacheWarn: createWarn('cache'),
  cacheError: createError('cache'),
}

export default debug
