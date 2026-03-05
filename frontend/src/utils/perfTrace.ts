export type StructuralActionName =
  | 'toggleExpansion'
  | 'expandRing'
  | 'collapseRing'
  | 'expandAll'
  | 'collapseAll'

interface StructuralTraceStart {
  action: StructuralActionName
  nodeCountBefore: number
  edgeCountBefore: number
  expectedWindowMs?: number
  details?: Record<string, unknown>
}

interface StructuralTraceEnd {
  nodeCountAfter: number
  edgeCountAfter: number
  animationWindowMs: number
}

interface StructuralTraceRecord extends StructuralTraceStart, StructuralTraceEnd {
  id: number
  startedAt: number
  endedAt: number
  elapsedMs: number
  nodeDelta: number
  edgeDelta: number
  overlappingZoomAttempts: number
  longFrameCount: number
}

interface ActiveTrace extends StructuralTraceStart {
  id: number
  startedAt: number
  overlappingZoomAttempts: number
  longFrameCount: number
  rafId: number | null
  lastFrameAt: number | null
}

export interface AtlasPerfSurface {
  report: () => StructuralTraceRecord[]
  reset: () => void
}

declare global {
  interface Window {
    __atlasPerf?: AtlasPerfSurface
  }
}

const LONG_FRAME_MS = 24
const MAX_TRACE_RECORDS = 500

const createPerfTrace = () => {
  const records: StructuralTraceRecord[] = []
  const active = new Map<number, ActiveTrace>()
  let nextId = 1

  const startFrameMonitor = (trace: ActiveTrace) => {
    const tick = (now: number) => {
      if (!active.has(trace.id)) return
      if (trace.lastFrameAt != null && now - trace.lastFrameAt > LONG_FRAME_MS) {
        trace.longFrameCount += 1
      }
      trace.lastFrameAt = now
      trace.rafId = window.requestAnimationFrame(tick)
    }
    trace.rafId = window.requestAnimationFrame(tick)
  }

  const stopFrameMonitor = (trace: ActiveTrace) => {
    if (trace.rafId != null) {
      window.cancelAnimationFrame(trace.rafId)
      trace.rafId = null
    }
  }

  const start = (input: StructuralTraceStart): number | null => {
    if (!import.meta.env.DEV || typeof window === 'undefined') return null
    const id = nextId++
    const trace: ActiveTrace = {
      ...input,
      id,
      startedAt: performance.now(),
      overlappingZoomAttempts: 0,
      longFrameCount: 0,
      rafId: null,
      lastFrameAt: null,
    }
    active.set(id, trace)
    startFrameMonitor(trace)
    return id
  }

  const noteZoomOverlap = (id: number | null) => {
    if (!import.meta.env.DEV || id == null) return
    const trace = active.get(id)
    if (!trace) return
    trace.overlappingZoomAttempts += 1
  }

  const finish = (id: number | null, input: StructuralTraceEnd): StructuralTraceRecord | null => {
    if (!import.meta.env.DEV || id == null) return null
    const trace = active.get(id)
    if (!trace) return null
    stopFrameMonitor(trace)
    active.delete(id)

    const endedAt = performance.now()
    const record: StructuralTraceRecord = {
      ...trace,
      ...input,
      startedAt: trace.startedAt,
      endedAt,
      elapsedMs: endedAt - trace.startedAt,
      nodeDelta: input.nodeCountAfter - trace.nodeCountBefore,
      edgeDelta: input.edgeCountAfter - trace.edgeCountBefore,
      overlappingZoomAttempts: trace.overlappingZoomAttempts,
      longFrameCount: trace.longFrameCount,
    }
    records.push(record)
    if (records.length > MAX_TRACE_RECORDS) {
      records.splice(0, records.length - MAX_TRACE_RECORDS)
    }
    return record
  }

  const report = (): StructuralTraceRecord[] => {
    const snapshot = [...records]
    if (import.meta.env.DEV && typeof window !== 'undefined') {
      console.table(snapshot.map(r => ({
        id: r.id,
        action: r.action,
        elapsed_ms: Number(r.elapsedMs.toFixed(1)),
        anim_window_ms: r.animationWindowMs,
        node_delta: r.nodeDelta,
        edge_delta: r.edgeDelta,
        zoom_overlaps: r.overlappingZoomAttempts,
        long_frames: r.longFrameCount,
      })))
    }
    return snapshot
  }

  const reset = () => {
    records.length = 0
  }

  return { start, noteZoomOverlap, finish, report, reset }
}

export const perfTrace = createPerfTrace()

if (import.meta.env.DEV && typeof window !== 'undefined') {
  window.__atlasPerf = {
    report: () => perfTrace.report(),
    reset: () => perfTrace.reset(),
  }
}
