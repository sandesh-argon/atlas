/**
 * JavaScript Example: Loading and Using the Causal Graph Schema
 *
 * This example demonstrates how to load and work with the causal graph schema
 * in a web application (React, Vue, vanilla JS, etc.)
 *
 * Author: V2.0 Global Causal Discovery Team
 * Date: November 21, 2025
 */

// ============================================================================
// Example 1: Loading the Schema (Fetch API)
// ============================================================================

async function loadSchema() {
  try {
    const response = await fetch('data/causal_graph_v2_final.json');
    const schema = await response.json();

    console.log('✅ Schema loaded successfully');
    console.log(`   Mechanisms: ${schema.mechanisms.length}`);
    console.log(`   Outcomes: ${schema.outcomes.length}`);
    console.log(`   Graph levels: ${Object.keys(schema.graphs).join(', ')}`);

    return schema;
  } catch (error) {
    console.error('❌ Error loading schema:', error);
    throw error;
  }
}

// ============================================================================
// Example 2: Accessing Graph Data
// ============================================================================

function accessGraphData(schema) {
  // Get full graph
  const fullGraph = schema.graphs.full;
  console.log(`Full graph: ${fullGraph.nodes.length} nodes, ${fullGraph.edges.length} edges`);

  // Get professional graph
  const professionalGraph = schema.graphs.professional;
  console.log(`Professional graph: ${professionalGraph.nodes.length} nodes, ${professionalGraph.edges.length} edges`);

  // Get simplified graph
  const simplifiedGraph = schema.graphs.simplified;
  console.log(`Simplified graph: ${simplifiedGraph.nodes.length} nodes, ${simplifiedGraph.edges.length} edges`);
}

// ============================================================================
// Example 3: Filtering Mechanisms by Domain
// ============================================================================

function filterByDomain(schema, domain) {
  const mechanisms = schema.mechanisms.filter(m => m.domain === domain);
  console.log(`${domain} mechanisms: ${mechanisms.length}`);

  // Get top 5 by SHAP score
  const topBySHAP = mechanisms
    .filter(m => m.shap_available)
    .sort((a, b) => b.shap_score - a.shap_score)
    .slice(0, 5);

  console.log(`Top 5 ${domain} mechanisms by SHAP:`);
  topBySHAP.forEach((m, i) => {
    console.log(`  ${i + 1}. ${m.label} (SHAP: ${m.shap_score.toFixed(4)})`);
  });

  return mechanisms;
}

// ============================================================================
// Example 4: Finding Causal Paths
// ============================================================================

function findCausalPaths(schema, sourceId, targetId) {
  const fullGraph = schema.graphs.full;
  const edges = fullGraph.edges;

  // Build adjacency list
  const adjacency = {};
  edges.forEach(edge => {
    if (!adjacency[edge.source]) adjacency[edge.source] = [];
    adjacency[edge.source].push({
      target: edge.target,
      effect: edge.effect,
      lag: edge.lag
    });
  });

  // Simple BFS to find paths (not exhaustive, just direct paths)
  const directPaths = adjacency[sourceId]?.filter(e => e.target === targetId) || [];

  if (directPaths.length > 0) {
    console.log(`Direct path found: ${sourceId} → ${targetId}`);
    directPaths.forEach(path => {
      console.log(`  Effect: ${path.effect.toFixed(3)}, Lag: ${path.lag} years`);
    });
  } else {
    console.log(`No direct path found: ${sourceId} → ${targetId}`);
  }

  return directPaths;
}

// ============================================================================
// Example 5: Using Dashboard Filters
// ============================================================================

function getDashboardFilters(schema) {
  const filters = schema.dashboard_metadata.filters;

  console.log('Available filters:');
  console.log(`  Domains: ${filters.domains.join(', ')}`);
  console.log(`  Subdomains: ${filters.subdomains.length} total`);
  console.log(`  Layers: ${filters.layers.join(', ')}`);
  console.log(`  SHAP range: ${filters.shap_range.min} - ${filters.shap_range.max}`);
  console.log(`  SHAP baseline: ${filters.shap_range.baseline}`);
  console.log(`  Graph levels: ${filters.graph_level.join(', ')}`);

  return filters;
}

// ============================================================================
// Example 6: Getting Tooltips
// ============================================================================

function getTooltip(schema, nodeId) {
  const tooltip = schema.dashboard_metadata.tooltips.find(t => t.id === nodeId);

  if (tooltip) {
    console.log(`Tooltip for ${nodeId}:`);
    console.log(`  Short: ${tooltip.text}`);
    console.log(`  Full: ${tooltip.full_text}`);
    return tooltip;
  } else {
    console.log(`No tooltip found for ${nodeId}`);
    return null;
  }
}

// ============================================================================
// Example 7: D3.js Integration (Pseudocode)
// ============================================================================

/*
// Render with D3.js (requires d3.js library)
import * as d3 from 'd3';

function renderGraph(schema, graphLevel = 'simplified') {
  const graph = schema.graphs[graphLevel];
  const width = 800;
  const height = 600;

  // Create SVG
  const svg = d3.select('#graph-container')
    .append('svg')
    .attr('width', width)
    .attr('height', height);

  // Create force simulation
  const simulation = d3.forceSimulation(graph.nodes)
    .force('link', d3.forceLink(graph.edges).id(d => d.id))
    .force('charge', d3.forceManyBody().strength(-100))
    .force('center', d3.forceCenter(width / 2, height / 2));

  // Render edges
  const link = svg.append('g')
    .selectAll('line')
    .data(graph.edges)
    .enter().append('line')
    .attr('stroke', '#999')
    .attr('stroke-width', d => Math.abs(d.effect) * 5);

  // Render nodes
  const node = svg.append('g')
    .selectAll('circle')
    .data(graph.nodes)
    .enter().append('circle')
    .attr('r', 8)
    .attr('fill', d => domainColor(d.domain))
    .call(d3.drag()
      .on('start', dragstarted)
      .on('drag', dragged)
      .on('end', dragended));

  // Add labels
  const label = svg.append('g')
    .selectAll('text')
    .data(graph.nodes)
    .enter().append('text')
    .text(d => d.label)
    .attr('font-size', 10);

  // Simulation tick
  simulation.on('tick', () => {
    link
      .attr('x1', d => d.source.x)
      .attr('y1', d => d.source.y)
      .attr('x2', d => d.target.x)
      .attr('y2', d => d.target.y);

    node
      .attr('cx', d => d.x)
      .attr('cy', d => d.y);

    label
      .attr('x', d => d.x + 10)
      .attr('y', d => d.y + 3);
  });

  function domainColor(domain) {
    const colors = {
      'Governance': '#4A90E2',
      'Education': '#F5A623',
      'Economic': '#7ED321',
      'Mixed': '#BD10E0'
    };
    return colors[domain] || '#999';
  }
}
*/

// ============================================================================
// Main Usage Example
// ============================================================================

async function main() {
  console.log('='.repeat(80));
  console.log('CAUSAL GRAPH SCHEMA - JAVASCRIPT EXAMPLE');
  console.log('='.repeat(80));
  console.log();

  // Load schema
  const schema = await loadSchema();
  console.log();

  // Access graph data
  accessGraphData(schema);
  console.log();

  // Filter by domain
  filterByDomain(schema, 'Education');
  console.log();

  // Find causal paths (example)
  // findCausalPaths(schema, 'SE.PRM.ENRR', 'Factor_2');
  // console.log();

  // Get dashboard filters
  getDashboardFilters(schema);
  console.log();

  // Get tooltip (example)
  // getTooltip(schema, 'SE.PRM.ENRR');
}

// Run if in browser environment
if (typeof window !== 'undefined') {
  main();
}

// Export for module usage
if (typeof module !== 'undefined' && module.exports) {
  module.exports = {
    loadSchema,
    accessGraphData,
    filterByDomain,
    findCausalPaths,
    getDashboardFilters,
    getTooltip
  };
}
