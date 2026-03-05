/**
 * Breadcrumb Navigation Component
 *
 * Always visible, subtle grey styling.
 * Hover to see domain colors, click to navigate.
 */

import { useMemo, Fragment, useState } from 'react'

interface BreadcrumbNode {
  id: string
  label: string
  ring: number
  domain: string
}

interface BreadcrumbProps {
  nodeId: string | null
  nodeMap: Map<string, { id: string; label: string; ring: number; domain: string; parentId: string | null }>
  onNavigate: (nodeId: string) => void
  domainColors: Record<string, string>
}

/**
 * Build path from root to target node
 */
function buildPath(
  nodeId: string | null,
  nodeMap: Map<string, { id: string; label: string; ring: number; domain: string; parentId: string | null }>
): BreadcrumbNode[] {
  if (!nodeId) return []

  const path: BreadcrumbNode[] = []
  let current = nodeMap.get(nodeId)

  while (current) {
    path.unshift({
      id: current.id,
      label: current.label,
      ring: current.ring,
      domain: current.domain
    })

    if (current.parentId) {
      current = nodeMap.get(current.parentId)
    } else {
      break
    }
  }

  return path
}

export function Breadcrumb({ nodeId, nodeMap, onNavigate, domainColors }: BreadcrumbProps) {
  const path = useMemo(() => buildPath(nodeId, nodeMap), [nodeId, nodeMap])
  const [hoveredId, setHoveredId] = useState<string | null>(null)

  // Always show at least "Quality of Life" when no node selected
  const displayPath = path.length > 0 ? path : [{
    id: 'root',
    label: 'Quality of Life',
    ring: 0,
    domain: ''
  }]

  return (
    <div
      style={{
        display: 'flex',
        alignItems: 'center',
        gap: 4,
        fontSize: 12,
        color: '#767676'
      }}
    >
      {displayPath.map((node, i) => {
        const isHovered = hoveredId === node.id
        const isLast = i === displayPath.length - 1
        const color = domainColors[node.domain] || '#666'

        return (
          <Fragment key={node.id}>
            <button
              onClick={() => onNavigate(node.id)}
              onMouseEnter={() => setHoveredId(node.id)}
              onMouseLeave={() => setHoveredId(null)}
              title={`Go to ${node.label}`}
              style={{
                padding: '2px 4px',
                fontSize: 12,
                cursor: 'pointer',
                border: 'none',
                borderRadius: 3,
                background: isHovered ? 'rgba(0,0,0,0.05)' : 'transparent',
                color: isHovered || isLast ? color : '#aaa',
                fontWeight: isLast ? 500 : 400,
                whiteSpace: 'nowrap',
                transition: 'color 0.15s, background 0.15s'
              }}
            >
              {node.label}
            </button>
            {i < displayPath.length - 1 && (
              <span style={{ color: '#bcc3d4', fontSize: 10 }}>›</span>
            )}
          </Fragment>
        )
      })}
    </div>
  )
}

export default Breadcrumb
