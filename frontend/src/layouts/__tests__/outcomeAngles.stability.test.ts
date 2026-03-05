import { describe, expect, it } from 'vitest'
import { getRingCompactness, getTextBoostFactor } from '../branchCurves'
import {
  computeOutcomeSectors,
  getAngularDelta,
  type OutcomeSectorSnapshot,
} from '../outcomeAngles'

const OUTCOMES = [
  'health',
  'education',
  'income',
  'equality',
  'safety',
  'governance',
  'infrastructure',
  'employment',
  'environment',
]

const REQUIREMENTS = new Map<string, number>([
  ['health', 0.95],
  ['education', 1.1],
  ['income', 0.85],
  ['equality', 0.8],
  ['safety', 0.6],
  ['governance', 1.0],
  ['infrastructure', 0.9],
  ['employment', 0.7],
  ['environment', 0.95],
])

const MIN_COLLAPSED_EXTENT = Math.PI / 24

function runSolver(
  expandedNodeIds: Set<string>,
  prevSnapshot?: OutcomeSectorSnapshot,
  maxRotationStep: number = 0
) {
  return computeOutcomeSectors({
    outcomeIds: OUTCOMES,
    outcomeRequirements: REQUIREMENTS,
    expandedNodeIds,
    minCollapsedExtent: MIN_COLLAPSED_EXTENT,
    prevSnapshot,
    maxRotationStep,
  })
}

describe('computeOutcomeSectors stability', () => {
  it('keeps unrelated branches stable on single collapse after full expansion', () => {
    const allExpanded = new Set(OUTCOMES)
    const baseline = runSolver(allExpanded, undefined, 0)

    const collapsedSet = new Set(OUTCOMES)
    collapsedSet.delete('education')
    const collapsed = runSolver(collapsedSet, baseline.snapshot, 0)

    for (const id of OUTCOMES) {
      if (id === 'education') continue
      const before = baseline.angles.get(id)
      const after = collapsed.angles.get(id)
      expect(before).toBeDefined()
      expect(after).toBeDefined()
      expect(getAngularDelta(after!, before!)).toBeLessThan(0.02)
    }
  })

  it('is deterministic across repeated toggle cycles', () => {
    let snapshot: OutcomeSectorSnapshot | undefined
    const states = [
      new Set(OUTCOMES),
      new Set(OUTCOMES.filter(id => id !== 'health')),
      new Set(OUTCOMES),
      new Set(OUTCOMES.filter(id => id !== 'income')),
      new Set(OUTCOMES),
    ]

    const seen = new Map<string, Map<string, number>>()

    for (let cycle = 0; cycle < 3; cycle += 1) {
      for (const state of states) {
        const result = runSolver(state, snapshot, 0)
        const key = Array.from(state).sort().join('|')

        if (!seen.has(key)) {
          seen.set(key, new Map(result.angles))
        } else {
          const expectedAngles = seen.get(key)!
          for (const [id, angle] of result.angles) {
            const expected = expectedAngles.get(id)
            expect(expected).toBeDefined()
            expect(getAngularDelta(angle, expected!)).toBeLessThan(1e-6)
          }
        }

        snapshot = result.snapshot
      }
    }
  })

  it('always normalizes extents to 2π and respects collapsed floor', () => {
    const partiallyExpanded = new Set(['health', 'education', 'governance'])
    const result = runSolver(partiallyExpanded)

    const sum = Array.from(result.extents.values()).reduce((acc, value) => acc + value, 0)
    expect(Math.abs(sum - Math.PI * 2)).toBeLessThan(1e-6)

    for (const [id, extent] of result.extents.entries()) {
      expect(extent).toBeGreaterThan(0)
      if (!partiallyExpanded.has(id)) {
        expect(extent).toBeGreaterThanOrEqual(MIN_COLLAPSED_EXTENT - 1e-6)
      }
    }
  })
})

describe('branch curves continuity', () => {
  it('removes compactness discontinuity around 4->5 branches', () => {
    const c4 = getRingCompactness(4, OUTCOMES.length)
    const c5 = getRingCompactness(5, OUTCOMES.length)
    const c6 = getRingCompactness(6, OUTCOMES.length)

    expect(c4).toBeLessThan(c5)
    expect(c5).toBeLessThan(c6)
    expect(c5 - c4).toBeLessThan(0.12)
  })

  it('keeps text boost continuous and non-zero past 5 branches', () => {
    const b4 = getTextBoostFactor(4, OUTCOMES.length)
    const b5 = getTextBoostFactor(5, OUTCOMES.length)
    const b6 = getTextBoostFactor(6, OUTCOMES.length)

    expect(b4).toBeGreaterThan(b5)
    expect(b5).toBeGreaterThan(b6)
    expect(b5).toBeGreaterThan(0)
  })
})
