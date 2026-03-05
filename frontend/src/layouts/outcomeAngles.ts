const TWO_PI = Math.PI * 2
const EPSILON = 1e-9

function normalizeAngle(angle: number): number {
  let normalized = angle
  while (normalized > Math.PI) normalized -= TWO_PI
  while (normalized <= -Math.PI) normalized += TWO_PI
  return normalized
}

function clamp(value: number, min: number, max: number): number {
  return Math.max(min, Math.min(max, value))
}

function buildCanonicalOrder(outcomeIds: string[], previousOrder: string[] | undefined): string[] {
  const present = new Set(outcomeIds)
  const order: string[] = []

  if (previousOrder && previousOrder.length > 0) {
    for (const id of previousOrder) {
      if (present.has(id)) {
        order.push(id)
        present.delete(id)
      }
    }
  }

  for (const id of outcomeIds) {
    if (present.has(id)) {
      order.push(id)
      present.delete(id)
    }
  }

  return order
}

function computeRequirementScale(
  order: string[],
  clusteredOutcomeIds: Set<string>,
  requirements: Map<string, number>,
  previousExtents: Map<string, number> | undefined,
  previousClusteredOutcomeIds: Set<string> | undefined
): number {
  if (!previousExtents || previousExtents.size === 0) {
    return 1
  }

  const ratios: number[] = []

  for (const id of order) {
    if (!clusteredOutcomeIds.has(id)) continue
    if (previousClusteredOutcomeIds && !previousClusteredOutcomeIds.has(id)) continue

    const requirement = requirements.get(id)
    const previousExtent = previousExtents.get(id)

    if (requirement === undefined || previousExtent === undefined) continue
    if (requirement <= EPSILON || previousExtent <= EPSILON) continue

    ratios.push(previousExtent / requirement)
  }

  if (ratios.length === 0) {
    return 1
  }

  ratios.sort((a, b) => a - b)
  return ratios[Math.floor(ratios.length / 2)]
}

function normalizeExtents(order: string[], rawExtents: Map<string, number>): Map<string, number> {
  const extents = new Map<string, number>()
  const totalRaw = order.reduce((sum, id) => sum + (rawExtents.get(id) ?? 0), 0)

  if (order.length === 0) {
    return extents
  }

  if (totalRaw <= EPSILON) {
    const evenExtent = TWO_PI / order.length
    for (const id of order) {
      extents.set(id, evenExtent)
    }
    return extents
  }

  const scale = TWO_PI / totalRaw
  for (const id of order) {
    extents.set(id, (rawExtents.get(id) ?? 0) * scale)
  }

  return extents
}

function positionCenters(order: string[], extents: Map<string, number>, rotation: number): Map<string, number> {
  const centers = new Map<string, number>()
  let cursor = -Math.PI + rotation

  for (const id of order) {
    const extent = extents.get(id) ?? 0
    const center = cursor + extent / 2
    centers.set(id, normalizeAngle(center))
    cursor += extent
  }

  return centers
}

function computeClusterCentroid(
  clusteredOutcomeIds: Set<string>,
  centers: Map<string, number>,
  extents: Map<string, number>
): number | null {
  if (clusteredOutcomeIds.size === 0) {
    return null
  }

  let sumX = 0
  let sumY = 0
  let totalWeight = 0

  for (const id of clusteredOutcomeIds) {
    const center = centers.get(id)
    if (center === undefined) continue

    const weight = extents.get(id) ?? 0
    if (weight <= EPSILON) continue

    sumX += Math.cos(center) * weight
    sumY += Math.sin(center) * weight
    totalWeight += weight
  }

  if (totalWeight <= EPSILON) {
    return null
  }

  return Math.atan2(sumY, sumX)
}

function copyMap(source: Map<string, number>): Map<string, number> {
  return new Map(source)
}

export interface OutcomeSectorSnapshot {
  order: string[]
  centers: Map<string, number>
  extents: Map<string, number>
  rotation: number
  clusteredOutcomeIds: string[]
}

export interface ComputeOutcomeSectorsInput {
  outcomeIds: string[]
  outcomeRequirements: Map<string, number>
  expandedNodeIds: Set<string>
  anchorOutcomeIds?: Set<string>
  minCollapsedExtent: number
  prevSnapshot?: OutcomeSectorSnapshot
  maxRotationStep?: number
  targetBiasAngle?: number
}

export interface ComputeOutcomeSectorsResult {
  angles: Map<string, number>
  extents: Map<string, number>
  snapshot: OutcomeSectorSnapshot
}

/**
 * Stable ring-1 sector solver.
 *
 * Design goals:
 * - deterministic circular order for all outcomes
 * - stable extents through collapse (cached extent reservation)
 * - bounded global rotation toward a right-side bias
 */
export function computeOutcomeSectors({
  outcomeIds,
  outcomeRequirements,
  expandedNodeIds,
  anchorOutcomeIds,
  minCollapsedExtent,
  prevSnapshot,
  maxRotationStep = 0,
  targetBiasAngle = 0,
}: ComputeOutcomeSectorsInput): ComputeOutcomeSectorsResult {
  const order = buildCanonicalOrder(outcomeIds, prevSnapshot?.order)

  if (order.length === 0) {
    const empty = new Map<string, number>()
    return {
      angles: empty,
      extents: empty,
      snapshot: {
        order: [],
        centers: new Map(),
        extents: new Map(),
        rotation: 0,
        clusteredOutcomeIds: [],
      }
    }
  }

  const clusteredOutcomeIds = new Set<string>()
  const previousExtents = prevSnapshot?.extents
  const previousClusteredOutcomeIds = prevSnapshot
    ? new Set(prevSnapshot.clusteredOutcomeIds)
    : undefined

  for (const id of order) {
    if (expandedNodeIds.has(id) || anchorOutcomeIds?.has(id)) {
      clusteredOutcomeIds.add(id)
    }
  }

  const requirementScale = computeRequirementScale(
    order,
    clusteredOutcomeIds,
    outcomeRequirements,
    previousExtents,
    previousClusteredOutcomeIds
  )

  const rawExtents = new Map<string, number>()
  for (const id of order) {
    const previousExtent = previousExtents?.get(id)

    if (clusteredOutcomeIds.has(id)) {
      const requirement = outcomeRequirements.get(id) ?? minCollapsedExtent
      const scaledRequirement = Math.max(minCollapsedExtent, requirement * requirementScale)
      rawExtents.set(id, scaledRequirement)
      continue
    }

    rawExtents.set(id, Math.max(minCollapsedExtent, previousExtent ?? minCollapsedExtent))
  }

  const extents = normalizeExtents(order, rawExtents)

  const previousRotation = prevSnapshot?.rotation ?? 0
  const centersBeforeRotationAdjust = positionCenters(order, extents, previousRotation)
  const centroid = computeClusterCentroid(clusteredOutcomeIds, centersBeforeRotationAdjust, extents)

  const rotationLimit = prevSnapshot ? Math.max(0, maxRotationStep) : Math.PI
  let rotationDelta = 0

  if (centroid !== null && rotationLimit > 0) {
    const desiredDelta = normalizeAngle(targetBiasAngle - centroid)
    rotationDelta = clamp(desiredDelta, -rotationLimit, rotationLimit)
  }

  const rotation = normalizeAngle(previousRotation + rotationDelta)
  const centers = positionCenters(order, extents, rotation)

  return {
    angles: centers,
    extents,
    snapshot: {
      order: [...order],
      centers: copyMap(centers),
      extents: copyMap(extents),
      rotation,
      clusteredOutcomeIds: Array.from(clusteredOutcomeIds),
    }
  }
}

export function getAngularDelta(a: number, b: number): number {
  return Math.abs(normalizeAngle(a - b))
}
