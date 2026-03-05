const TAU = Math.PI * 2
const ROOT_PARENT_KEY = '__root__'

export interface GraphNavNode {
  id: string
  label: string
  ring: number
  angle: number
  parentId: string | null
  domain: string
  hasChildren: boolean
}

export interface GraphNavModel {
  nodesById: Map<string, GraphNavNode>
  orderedNodeIds: string[]
  siblingOrderByNodeId: Map<string, string[]>
  siblingIndexByNodeId: Map<string, number>
  rootId: string | null
}

export interface FallbackFocusOptions {
  preferredNodeId?: string | null
  preferredParentId?: string | null
}

export interface FormatAnnouncementOptions {
  action?: string
  ringLabels?: string[]
}

function normalizeAngle(angle: number): number {
  const normalized = angle % TAU
  return normalized < 0 ? normalized + TAU : normalized
}

function sortByAngle(a: GraphNavNode, b: GraphNavNode): number {
  const delta = normalizeAngle(a.angle) - normalizeAngle(b.angle)
  if (Math.abs(delta) > 1e-9) return delta
  return a.id.localeCompare(b.id)
}

function getSiblingNode(model: GraphNavModel, nodeId: string, direction: 1 | -1): GraphNavNode | null {
  const siblingIds = model.siblingOrderByNodeId.get(nodeId)
  const siblingIndex = model.siblingIndexByNodeId.get(nodeId)
  if (!siblingIds || siblingIds.length === 0 || siblingIndex === undefined) return null

  const nextIndex = (siblingIndex + direction + siblingIds.length) % siblingIds.length
  const nextId = siblingIds[nextIndex]
  return model.nodesById.get(nextId) ?? null
}

export function buildGraphNavModel(nodes: GraphNavNode[]): GraphNavModel {
  const nodesById = new Map<string, GraphNavNode>()
  const siblingsByParent = new Map<string, GraphNavNode[]>()

  nodes.forEach(node => {
    nodesById.set(node.id, node)
    const parentKey = node.parentId ?? ROOT_PARENT_KEY
    if (!siblingsByParent.has(parentKey)) siblingsByParent.set(parentKey, [])
    siblingsByParent.get(parentKey)!.push(node)
  })

  const orderedNodeIds = [...nodes]
    .sort((a, b) => {
      if (a.ring !== b.ring) return a.ring - b.ring
      return sortByAngle(a, b)
    })
    .map(node => node.id)

  const rootNode =
    nodes.find(node => node.ring === 0)
    ?? nodes.find(node => node.parentId === null)
    ?? (orderedNodeIds.length > 0 ? nodesById.get(orderedNodeIds[0]) ?? null : null)

  const siblingOrderByNodeId = new Map<string, string[]>()
  const siblingIndexByNodeId = new Map<string, number>()

  siblingsByParent.forEach(group => {
    const orderedGroup = [...group].sort(sortByAngle)
    const siblingIds = orderedGroup.map(node => node.id)

    siblingIds.forEach((id, index) => {
      siblingOrderByNodeId.set(id, siblingIds)
      siblingIndexByNodeId.set(id, index)
    })
  })

  return {
    nodesById,
    orderedNodeIds,
    siblingOrderByNodeId,
    siblingIndexByNodeId,
    rootId: rootNode?.id ?? null,
  }
}

export function getNextSibling(model: GraphNavModel, nodeId: string): GraphNavNode | null {
  return getSiblingNode(model, nodeId, 1)
}

export function getPrevSibling(model: GraphNavModel, nodeId: string): GraphNavNode | null {
  return getSiblingNode(model, nodeId, -1)
}

export function getParent(model: GraphNavModel, nodeId: string): GraphNavNode | null {
  const node = model.nodesById.get(nodeId)
  if (!node?.parentId) return null
  return model.nodesById.get(node.parentId) ?? null
}

export function getFallbackFocus(model: GraphNavModel, options: FallbackFocusOptions = {}): GraphNavNode | null {
  if (options.preferredNodeId) {
    const preferredNode = model.nodesById.get(options.preferredNodeId)
    if (preferredNode) return preferredNode
  }

  if (options.preferredParentId) {
    const preferredParent = model.nodesById.get(options.preferredParentId)
    if (preferredParent) return preferredParent
  }

  if (model.rootId) {
    const rootNode = model.nodesById.get(model.rootId)
    if (rootNode) return rootNode
  }

  const firstNodeId = model.orderedNodeIds[0]
  return firstNodeId ? model.nodesById.get(firstNodeId) ?? null : null
}

export function formatAnnouncement(node: GraphNavNode, options: FormatAnnouncementOptions = {}): string {
  const ringLabel = options.ringLabels?.[node.ring] ?? `Ring ${node.ring}`
  const domain = node.domain.trim().length > 0 ? node.domain : 'Domain unavailable'
  const expandability = node.hasChildren ? 'Expandable' : 'No children'
  const prefix = options.action ? `${options.action}. ` : ''
  return `${prefix}${node.label}, ${ringLabel}, ${domain}, ${expandability}`
}
