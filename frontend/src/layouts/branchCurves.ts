const DEFAULT_MIN_COMPACTNESS = 0.4
const DEFAULT_TEXT_BOOST_FLOOR = 0.08

function clamp01(value: number): number {
  if (value <= 0) return 0
  if (value >= 1) return 1
  return value
}

function getExpandedProgress(expandedCount: number, totalOutcomeCount: number): number {
  if (expandedCount <= 0 || totalOutcomeCount <= 0) {
    return 0
  }
  if (totalOutcomeCount <= 1) {
    return 1
  }

  const boundedExpanded = Math.min(expandedCount, totalOutcomeCount)
  return clamp01((boundedExpanded - 1) / (totalOutcomeCount - 1))
}

/**
 * Smooth compactness curve for ring clustering.
 *
 * Guarantees continuity across branch counts (no hard 4->5 jump):
 * - 1 expanded branch => minCompactness (default 0.4)
 * - all expanded branches => 1.0
 */
export function getRingCompactness(
  expandedCount: number,
  totalOutcomeCount: number,
  minCompactness: number = DEFAULT_MIN_COMPACTNESS
): number {
  if (expandedCount <= 0) return 1
  if (totalOutcomeCount <= 1) return 1

  const boundedMin = clamp01(minCompactness)
  const progress = getExpandedProgress(expandedCount, totalOutcomeCount)

  // Ease-out quadratic: stronger growth early, smooth near saturation.
  const eased = 1 - (1 - progress) * (1 - progress)
  return boundedMin + (1 - boundedMin) * eased
}

/**
 * Smooth readability boost factor for low-density branch exploration.
 *
 * Guarantees continuity across branch counts and never hard-drops to zero.
 * - no expanded branches => 0
 * - 1 expanded branch => 1.0
 * - all branches expanded => floor (default 0.08)
 */
export function getTextBoostFactor(
  expandedCount: number,
  totalOutcomeCount: number,
  floor: number = DEFAULT_TEXT_BOOST_FLOOR
): number {
  if (expandedCount <= 0) return 0
  if (totalOutcomeCount <= 1) return 1

  const boundedFloor = clamp01(floor)
  const progress = getExpandedProgress(expandedCount, totalOutcomeCount)
  const decay = (1 - progress) * (1 - progress)

  return boundedFloor + (1 - boundedFloor) * decay
}
