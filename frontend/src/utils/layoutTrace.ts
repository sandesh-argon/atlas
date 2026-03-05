import type { OutcomeSectorSnapshot } from '../layouts/outcomeAngles'
import { getAngularDelta } from '../layouts/outcomeAngles'

interface LayoutTraceRecord {
  id: number
  timestamp: number
  action: string
  contextKey: string
  outcomeOrder: string[]
  centers: Record<string, number>
  extents: Record<string, number>
  maxCenterDelta: number
  maxExtentDelta: number
}

export interface AtlasLayoutTraceSurface {
  report: () => LayoutTraceRecord[]
  reset: () => void
}

declare global {
  interface Window {
    __atlasLayout?: AtlasLayoutTraceSurface
  }
}

const MAX_LAYOUT_TRACE_RECORDS = 300

const createLayoutTrace = () => {
  const records: LayoutTraceRecord[] = []
  let previousSnapshot: OutcomeSectorSnapshot | null = null
  let previousContextKey = ''
  let nextId = 1

  const toRecordMap = (source: Map<string, number>): Record<string, number> => {
    const result: Record<string, number> = {}
    for (const [id, value] of source.entries()) {
      result[id] = value
    }
    return result
  }

  const record = (input: {
    action: string
    contextKey: string
    snapshot: OutcomeSectorSnapshot
  }) => {
    if (!import.meta.env.DEV || typeof window === 'undefined') return

    if (input.contextKey !== previousContextKey) {
      previousSnapshot = null
      previousContextKey = input.contextKey
    }

    let maxCenterDelta = 0
    let maxExtentDelta = 0

    if (previousSnapshot) {
      for (const id of input.snapshot.order) {
        const previousCenter = previousSnapshot.centers.get(id)
        const currentCenter = input.snapshot.centers.get(id)
        if (previousCenter !== undefined && currentCenter !== undefined) {
          maxCenterDelta = Math.max(maxCenterDelta, getAngularDelta(currentCenter, previousCenter))
        }

        const previousExtent = previousSnapshot.extents.get(id)
        const currentExtent = input.snapshot.extents.get(id)
        if (previousExtent !== undefined && currentExtent !== undefined) {
          maxExtentDelta = Math.max(maxExtentDelta, Math.abs(currentExtent - previousExtent))
        }
      }
    }

    const entry: LayoutTraceRecord = {
      id: nextId++,
      timestamp: performance.now(),
      action: input.action,
      contextKey: input.contextKey,
      outcomeOrder: [...input.snapshot.order],
      centers: toRecordMap(input.snapshot.centers),
      extents: toRecordMap(input.snapshot.extents),
      maxCenterDelta,
      maxExtentDelta,
    }

    records.push(entry)
    if (records.length > MAX_LAYOUT_TRACE_RECORDS) {
      records.splice(0, records.length - MAX_LAYOUT_TRACE_RECORDS)
    }

    previousSnapshot = {
      order: [...input.snapshot.order],
      centers: new Map(input.snapshot.centers),
      extents: new Map(input.snapshot.extents),
      rotation: input.snapshot.rotation,
      clusteredOutcomeIds: [...input.snapshot.clusteredOutcomeIds],
    }
  }

  const reset = () => {
    records.length = 0
    previousSnapshot = null
    previousContextKey = ''
  }

  const report = (): LayoutTraceRecord[] => {
    const snapshot = [...records]
    if (import.meta.env.DEV && typeof window !== 'undefined') {
      console.table(snapshot.map(record => ({
        id: record.id,
        action: record.action,
        context: record.contextKey,
        max_center_delta_deg: Number(((record.maxCenterDelta * 180) / Math.PI).toFixed(2)),
        max_extent_delta_deg: Number(((record.maxExtentDelta * 180) / Math.PI).toFixed(2)),
      })))
    }
    return snapshot
  }

  return { record, report, reset }
}

export const layoutTrace = createLayoutTrace()

if (import.meta.env.DEV && typeof window !== 'undefined') {
  window.__atlasLayout = {
    report: () => layoutTrace.report(),
    reset: () => layoutTrace.reset(),
  }
}
