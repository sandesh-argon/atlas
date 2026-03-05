export type LayoutAction =
  | 'single_expand'
  | 'single_collapse'
  | 'ring_expand'
  | 'ring_collapse'
  | 'global_expand'
  | 'global_collapse'

interface BudgetPreset {
  rotationMs: number
  enterExitMs: number
  textFadeMs: number
  exitMs: number
  cameraMs: number
  collapseGapMs: number
  glowBufferMs: number
  structuralLockMs: number
}

export interface LayoutBudget extends BudgetPreset {
  useFastPath: boolean
}

export const STRUCTURAL_LOCK_FALLBACK_MS = 300
export const PANEL_EXIT_MS = 180

const BALANCED: BudgetPreset = {
  rotationMs: 260,
  enterExitMs: 220,
  textFadeMs: 120,
  exitMs: 160,
  cameraMs: 340,
  collapseGapMs: 40,
  glowBufferMs: 40,
  structuralLockMs: 340,
}

const FAST: BudgetPreset = {
  rotationMs: 0,
  enterExitMs: 120,
  textFadeMs: 80,
  exitMs: 100,
  cameraMs: 220,
  collapseGapMs: 0,
  glowBufferMs: 0,
  structuralLockMs: 240,
}

const PRESETS: Record<LayoutAction, { normal: BudgetPreset; fast: BudgetPreset }> = {
  single_expand: { normal: BALANCED, fast: FAST },
  single_collapse: { normal: BALANCED, fast: FAST },
  ring_expand: { normal: FAST, fast: FAST },
  ring_collapse: { normal: FAST, fast: FAST },
  global_expand: { normal: FAST, fast: FAST },
  global_collapse: { normal: FAST, fast: FAST },
}
const BULK_ACTIONS = new Set<LayoutAction>([
  'ring_expand',
  'ring_collapse',
  'global_expand',
  'global_collapse',
])

export interface LayoutBudgetInput {
  action: LayoutAction
  nodeDelta: number
  edgeDelta: number
}

const NODE_DELTA_FAST_THRESHOLD = 80
const EDGE_DELTA_FAST_THRESHOLD = 160

export const resolveLayoutBudget = ({ action, nodeDelta, edgeDelta }: LayoutBudgetInput): LayoutBudget => {
  const preset = PRESETS[action]
  const isBulkAction = BULK_ACTIONS.has(action)
  const isLargeDiff = nodeDelta >= NODE_DELTA_FAST_THRESHOLD || edgeDelta >= EDGE_DELTA_FAST_THRESHOLD
  const useFastPath = isBulkAction || isLargeDiff
  const chosen = useFastPath ? preset.fast : preset.normal
  return {
    ...chosen,
    useFastPath,
  }
}
