/**
 * Normalization Utility
 *
 * Provides functions to normalize country-specific values
 * for visual display (node sizing, color intensity, etc.)
 */

/**
 * Map a value to a node radius using min-max scaling
 *
 * @param value - The value to normalize
 * @param minValue - Minimum value in the dataset
 * @param maxValue - Maximum value in the dataset
 * @param baseRadius - Base node radius (default 8px)
 * @param maxVariation - Maximum radius variation (default 6px)
 * @returns Normalized radius between baseRadius and baseRadius + maxVariation
 */
export function valueToRadius(
  value: number,
  minValue: number,
  maxValue: number,
  baseRadius: number = 8,
  maxVariation: number = 6
): number {
  // Handle edge case where all values are the same
  if (maxValue === minValue) {
    return baseRadius
  }

  // Min-max normalization to [0, 1]
  const normalized = (value - minValue) / (maxValue - minValue)

  // Scale to radius range
  return baseRadius + normalized * maxVariation
}

/**
 * Compute z-score for a value
 *
 * @param value - The value to normalize
 * @param mean - Mean of the dataset
 * @param stdDev - Standard deviation of the dataset
 * @returns Z-score (number of standard deviations from mean)
 */
export function computeZScore(
  value: number,
  mean: number,
  stdDev: number
): number {
  if (stdDev === 0) {
    return 0
  }
  return (value - mean) / stdDev
}

/**
 * Map a z-score to a node radius
 *
 * @param zScore - Z-score of the value
 * @param baseRadius - Base node radius (default 8px)
 * @param radiusPerStdDev - Radius change per standard deviation (default 3px)
 * @param maxVariation - Maximum radius change (default 9px, capping at ±3 std)
 * @returns Radius adjusted by z-score
 */
export function zScoreToRadius(
  zScore: number,
  baseRadius: number = 8,
  radiusPerStdDev: number = 3,
  maxVariation: number = 9
): number {
  // Clamp z-score effect to maxVariation
  const clampedEffect = Math.max(-maxVariation, Math.min(maxVariation, zScore * radiusPerStdDev))
  return baseRadius + clampedEffect
}

/**
 * Compute statistics for a set of values
 *
 * @param values - Array of numeric values
 * @returns Object with min, max, mean, stdDev
 */
export function computeStats(values: number[]): {
  min: number
  max: number
  mean: number
  stdDev: number
} {
  if (values.length === 0) {
    return { min: 0, max: 0, mean: 0, stdDev: 0 }
  }

  const min = Math.min(...values)
  const max = Math.max(...values)
  const mean = values.reduce((a, b) => a + b, 0) / values.length

  const variance = values.reduce((sum, v) => sum + (v - mean) ** 2, 0) / values.length
  const stdDev = Math.sqrt(variance)

  return { min, max, mean, stdDev }
}

/**
 * Create a normalizer function for a specific dataset
 *
 * @param values - Array of all values in the dataset
 * @param method - Normalization method ('minmax' or 'zscore')
 * @param baseRadius - Base node radius
 * @param maxVariation - Maximum radius variation
 * @returns Function that takes a value and returns a radius
 */
export function createNormalizer(
  values: number[],
  method: 'minmax' | 'zscore' = 'minmax',
  baseRadius: number = 8,
  maxVariation: number = 6
): (value: number) => number {
  const stats = computeStats(values)

  if (method === 'zscore') {
    return (value: number) =>
      zScoreToRadius(
        computeZScore(value, stats.mean, stats.stdDev),
        baseRadius,
        maxVariation / 3,  // 3 std devs = maxVariation
        maxVariation
      )
  }

  // Default: min-max
  return (value: number) =>
    valueToRadius(value, stats.min, stats.max, baseRadius, maxVariation)
}

/**
 * Normalize an array of values to [0, 1] range
 *
 * @param values - Array of values to normalize
 * @returns Array of normalized values
 */
export function normalizeToRange(values: number[]): number[] {
  const { min, max } = computeStats(values)

  if (max === min) {
    return values.map(() => 0.5)
  }

  return values.map(v => (v - min) / (max - min))
}

/**
 * Map a change percentage to a glow intensity
 * Used for simulation result visualization
 *
 * @param changePercent - Percentage change from simulation
 * @param maxChange - Maximum change to map to full intensity (default 50%)
 * @returns Intensity value between 0 and 1
 */
export function changeToGlowIntensity(
  changePercent: number,
  maxChange: number = 50
): number {
  const absChange = Math.abs(changePercent)
  return Math.min(absChange, maxChange) / maxChange
}
