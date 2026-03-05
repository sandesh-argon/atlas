/**
 * Type definitions for the semantic hierarchy visualization
 */

export interface SemanticPath {
  domain: string
  subdomain: string
  fine_cluster: string
  full_path: string
}

export interface RawNodeV21 {
  id: string | number
  label: string
  description?: string
  layer: number
  node_type: 'root' | 'outcome_category' | 'coarse_domain' | 'fine_domain' | 'indicator'
  domain: string | null
  subdomain: string | null
  shap_importance: number
  importance: number  // Normalized SHAP importance (0-1) for node sizing
  shap_raw?: number   // Raw aggregated SHAP value before normalization
  in_degree: number
  out_degree: number
  label_source: string
  parent?: string | number
  children?: (string | number)[]
  indicator_count?: number
}

export interface RawEdge {
  source: string
  target: string
  weight?: number
  relationship?: 'causal' | 'hierarchical'
}

export interface GraphDataV21 {
  nodes: RawNodeV21[]
  edges: RawEdge[]
  hierarchy: Record<string, unknown>
  outcomes?: unknown
  metadata: {
    version: string
    statistics: {
      total_nodes: number
      layers: Record<string, number>
    }
  }
}

export interface PositionedNode {
  id: string
  label: string
  description: string
  semanticPath: SemanticPath
  isDriver: boolean
  isOutcome: boolean
  shapImportance: number
  degree: number
  ring: number
  x: number
  y: number
}

export interface StructuralEdge {
  sourceId: string
  targetId: string
  sourceRing: number
  targetRing: number
}

export interface CausalEdge {
  sourceId: string
  targetId: string
  weight: number  // β coefficient (effect size)
}

export interface RingConfig {
  radius: number
  label: string
}

// ============================================
// Local View Types
// ============================================

/** View mode for the application */
export type ViewMode = 'global' | 'local' | 'split'

/** Shape types for different node roles in Local View */
export type LocalNodeShape = 'pill' | 'rectangle' | 'hexagon'

/** Flow direction for Local View layout */
export type FlowDirection = 'horizontal' | 'vertical'

/** A node in the Local View */
export interface LocalViewNode {
  id: string
  label: string
  sector: string        // Ring 1 ancestor (outcome category)
  sectorColor: string   // Domain color for the sector
  ring: number
  importance: number
  isTarget: boolean     // Is this a selected target node?
  isInput: boolean      // Is this an input (cause) to a target?
  isOutput: boolean     // Is this an output (effect) of a target?
  depth: number         // Depth level: 1 = direct, 2 = indirect, 3 = 2nd indirect
  shape: LocalNodeShape // Shape based on role: pill (input), rectangle (target), hexagon (output)
  beta?: number         // Original beta value from direct edge (for display)
  visualBeta: number    // Propagated beta for sizing (parent's visualBeta × edge beta)
  parentId?: string     // ID of parent node in the causal tree (for tree layout)
  hasMoreInputs?: boolean   // Has unexpanded causes
  hasMoreOutputs?: boolean  // Has unexpanded effects
  isInputExpanded?: boolean  // Are this node's causes shown?
  isOutputExpanded?: boolean // Are this node's effects shown?
  canExpand?: boolean        // Has any children at current threshold (for dimming)
  hasChildren?: boolean      // Has hierarchical children (for drill-down)
  childIds?: string[]        // IDs of hierarchical children
}

/** A causal edge in the Local View */
export interface LocalViewEdge {
  source: string
  target: string
  beta: number          // Effect size (β coefficient)
  sourceSector: string  // Sector of source node
  targetSector: string  // Sector of target node
  isAggregated?: boolean     // True if this is an aggregated edge from children
  pathwayCount?: number      // Number of child pathways (for aggregated edges)
  pathways?: EdgePathway[]   // Detailed pathways (for expansion)
}

/** A pathway through child nodes (for aggregated edges) */
export interface EdgePathway {
  childSource: string   // Child indicator that is the source
  childTarget: string   // Child indicator that is the target
  beta: number          // Beta value for this specific pathway
}

/** Mode for Local View data */
export type LocalViewMode = 'direct' | 'aggregated' | 'empty'

/** Aggregated data for Local View */
export interface LocalViewData {
  targets: LocalViewNode[]
  inputs: LocalViewNode[]
  outputs: LocalViewNode[]
  edges: LocalViewEdge[]
}

/** State for Local View */
export interface LocalViewState {
  targetIds: string[]           // Selected target node IDs
  betaThreshold: number         // Filter threshold (default: 0.5)
  expandedSectors: Set<string>  // Which sector groups are expanded
  sectorFilter: string[]        // Filter by sectors (empty = all)
}
