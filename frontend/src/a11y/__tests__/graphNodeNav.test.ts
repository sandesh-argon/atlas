import { describe, expect, it } from 'vitest'
import {
  buildGraphNavModel,
  formatAnnouncement,
  getFallbackFocus,
  getNextSibling,
  getParent,
  getPrevSibling,
  type GraphNavNode,
} from '../graphNodeNav'

const BASE_NODES: GraphNavNode[] = [
  {
    id: 'root',
    label: 'Quality of Life',
    ring: 0,
    angle: 0,
    parentId: null,
    domain: '',
    hasChildren: true,
  },
  {
    id: 'outcome-a',
    label: 'Health',
    ring: 1,
    angle: -Math.PI / 2,
    parentId: 'root',
    domain: 'Health',
    hasChildren: true,
  },
  {
    id: 'outcome-b',
    label: 'Education',
    ring: 1,
    angle: 0,
    parentId: 'root',
    domain: 'Education',
    hasChildren: true,
  },
  {
    id: 'outcome-c',
    label: 'Economic',
    ring: 1,
    angle: Math.PI / 2,
    parentId: 'root',
    domain: 'Economic',
    hasChildren: false,
  },
  {
    id: 'indicator-a1',
    label: 'Life expectancy',
    ring: 2,
    angle: -Math.PI / 3,
    parentId: 'outcome-a',
    domain: 'Health',
    hasChildren: false,
  },
]

describe('graphNodeNav utilities', () => {
  it('wraps sibling traversal by angle order', () => {
    const model = buildGraphNavModel(BASE_NODES)

    // Root siblings sorted by normalized angle: outcome-b (0), outcome-c (pi/2), outcome-a (3pi/2)
    expect(getNextSibling(model, 'outcome-a')?.id).toBe('outcome-b')
    expect(getPrevSibling(model, 'outcome-b')?.id).toBe('outcome-a')
    expect(getNextSibling(model, 'outcome-c')?.id).toBe('outcome-a')
  })

  it('resolves fallback to parent, then root, when focused node disappears', () => {
    const fullModel = buildGraphNavModel(BASE_NODES)
    const previousParentId = fullModel.nodesById.get('indicator-a1')?.parentId

    const withoutChild = BASE_NODES.filter(node => node.id !== 'indicator-a1')
    const modelWithoutChild = buildGraphNavModel(withoutChild)

    expect(
      getFallbackFocus(modelWithoutChild, {
        preferredNodeId: 'indicator-a1',
        preferredParentId: previousParentId,
      })?.id
    ).toBe('outcome-a')

    const rootOnly = buildGraphNavModel([BASE_NODES[0]])
    expect(
      getFallbackFocus(rootOnly, {
        preferredNodeId: 'indicator-a1',
        preferredParentId: previousParentId,
      })?.id
    ).toBe('root')
  })

  it('returns parent correctly for non-root nodes', () => {
    const model = buildGraphNavModel(BASE_NODES)
    expect(getParent(model, 'indicator-a1')?.id).toBe('outcome-a')
    expect(getParent(model, 'root')).toBeNull()
  })

  it('formats announcements with ring/domain context', () => {
    const announcement = formatAnnouncement(BASE_NODES[2], {
      ringLabels: ['Quality of Life', 'Outcomes', 'Domains'],
    })
    expect(announcement).toContain('Education')
    expect(announcement).toContain('Outcomes')
    expect(announcement).toContain('Education')
    expect(announcement).toContain('Expandable')

    const noDomain = formatAnnouncement({
      id: 'x',
      label: 'Unknown',
      ring: 3,
      angle: 0,
      parentId: 'outcome-a',
      domain: '',
      hasChildren: false,
    })
    expect(noDomain).toContain('Domain unavailable')
    expect(noDomain).toContain('No children')
  })
})
