# Implementation Guide

**Visualization Implementation Package - V2.0**
**Date:** November 21, 2025

---

## 📋 Table of Contents

1. [Overview](#overview)
2. [Phase 1: Setup & Validation](#phase-1-setup--validation)
3. [Phase 2: Core Visualization](#phase-2-core-visualization)
4. [Phase 3: Interactivity](#phase-3-interactivity)
5. [Phase 4: Polish & Deploy](#phase-4-polish--deploy)
6. [Technical Specifications](#technical-specifications)
7. [Design Patterns](#design-patterns)
8. [Performance Optimization](#performance-optimization)
9. [Testing Strategy](#testing-strategy)
10. [Deployment Checklist](#deployment-checklist)

---

## Overview

### What You're Building

An interactive causal network visualization dashboard with:
- **3 progressive disclosure levels**: Full (290 nodes), Professional (116), Simplified (167)
- **5 filter types**: Domain, subdomain, layer, SHAP importance, graph level
- **Interactive features**: Zoom, pan, tooltips, node selection, path highlighting
- **Export capabilities**: PNG, SVG, JSON, CSV
- **Citation system**: BibTeX, APA, Chicago, MLA

### Technology Stack Recommendations

**Frontend Framework**: React, Vue, or vanilla JS
**Visualization**: D3.js v7 (mature, flexible) or Cytoscape.js (graph-focused)
**State Management**: Redux, Zustand, or Context API
**Styling**: Tailwind CSS or Material-UI
**Build Tool**: Vite or Webpack

---

## Phase 1: Setup & Validation

**Duration:** 1 day

### Task 1.1: Environment Setup

```bash
# Create project
npm create vite@latest causal-dashboard -- --template react-ts
cd causal-dashboard

# Install dependencies
npm install d3 @types/d3 zustand
npm install tailwindcss postcss autoprefixer
```

### Task 1.2: Copy Data Files

```bash
# Copy visualization package to project
cp -r ../viz_implementation_package/data ./public/data
```

### Task 1.3: Validate Package Integrity

```bash
cd ../viz_implementation_package
python scripts/validate_visualization.py
```

**Success Criteria:**
- ✅ All data files present
- ✅ Schema parses without errors
- ✅ No orphan edges in any graph level
- ✅ Tooltip count matches node count

---

## Phase 2: Core Visualization

**Duration:** 3-5 days

### Task 2.1: Load and Parse Schema

```typescript
// src/lib/loadSchema.ts
export interface CausalSchema {
  metadata: {
    version: string;
    n_nodes: { full: number; professional: number; simplified: number };
  };
  mechanisms: Mechanism[];
  outcomes: Outcome[];
  graphs: {
    full: Graph;
    professional: Graph;
    simplified: Graph;
  };
  dashboard_metadata: DashboardMetadata;
}

export async function loadSchema(): Promise<CausalSchema> {
  const response = await fetch('/data/causal_graph_v2_final.json');
  if (!response.ok) throw new Error('Failed to load schema');
  return await response.json();
}
```

### Task 2.2: Implement Force-Directed Layout (D3.js)

```typescript
// src/components/GraphVisualization.tsx
import * as d3 from 'd3';

function GraphVisualization({ graph, width = 1200, height = 800 }) {
  const svgRef = useRef<SVGSVGElement>(null);

  useEffect(() => {
    if (!svgRef.current) return;

    const svg = d3.select(svgRef.current);
    svg.selectAll('*').remove(); // Clear previous

    // Create force simulation
    const simulation = d3.forceSimulation(graph.nodes)
      .force('link', d3.forceLink(graph.edges).id(d => d.id).distance(100))
      .force('charge', d3.forceManyBody().strength(-200))
      .force('center', d3.forceCenter(width / 2, height / 2))
      .force('collision', d3.forceCollide().radius(30));

    // Render edges
    const link = svg.append('g')
      .selectAll('line')
      .data(graph.edges)
      .join('line')
      .attr('stroke', '#999')
      .attr('stroke-opacity', 0.6)
      .attr('stroke-width', d => Math.abs(d.effect) * 3);

    // Render nodes
    const node = svg.append('g')
      .selectAll('circle')
      .data(graph.nodes)
      .join('circle')
      .attr('r', 8)
      .attr('fill', d => domainColor(d.domain))
      .call(drag(simulation));

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
    });
  }, [graph]);

  return <svg ref={svgRef} width={width} height={height} />;
}

function domainColor(domain: string): string {
  const colors = {
    'Governance': '#4A90E2',
    'Education': '#F5A623',
    'Economic': '#7ED321',
    'Mixed': '#BD10E0'
  };
  return colors[domain] || '#999';
}
```

### Task 2.3: Implement Zoom & Pan

```typescript
useEffect(() => {
  const svg = d3.select(svgRef.current);

  const zoom = d3.zoom()
    .scaleExtent([0.1, 10])
    .on('zoom', (event) => {
      svg.selectAll('g').attr('transform', event.transform);
    });

  svg.call(zoom);
}, []);
```

**Success Criteria:**
- ✅ Graph renders with 290 nodes (full) without freezing
- ✅ Nodes colored by domain
- ✅ Edges weighted by effect size
- ✅ Zoom in/out works smoothly
- ✅ Pan works smoothly

---

## Phase 3: Interactivity

**Duration:** 4-6 days

### Task 3.1: Implement Filters

```typescript
// src/store/useFilterStore.ts
import create from 'zustand';

interface FilterState {
  selectedDomains: string[];
  selectedGraphLevel: 'full' | 'professional' | 'simplified';
  minSHAP: number;
  setSelectedDomains: (domains: string[]) => void;
  setGraphLevel: (level: string) => void;
  setMinSHAP: (value: number) => void;
}

export const useFilterStore = create<FilterState>((set) => ({
  selectedDomains: ['Governance', 'Education', 'Economic', 'Mixed'],
  selectedGraphLevel: 'simplified',
  minSHAP: 0.0,
  setSelectedDomains: (domains) => set({ selectedDomains: domains }),
  setGraphLevel: (level) => set({ selectedGraphLevel: level }),
  setMinSHAP: (value) => set({ minSHAP: value })
}));
```

```typescript
// src/components/FilterPanel.tsx
function FilterPanel() {
  const { selectedDomains, setSelectedDomains, minSHAP, setMinSHAP } = useFilterStore();

  return (
    <div className="filter-panel">
      <h3>Filters</h3>

      {/* Domain filter */}
      <div>
        <label>Domains</label>
        <select
          multiple
          value={selectedDomains}
          onChange={e => setSelectedDomains(Array.from(e.target.selectedOptions, opt => opt.value))}
        >
          <option value="Governance">Governance</option>
          <option value="Education">Education</option>
          <option value="Economic">Economic</option>
          <option value="Mixed">Mixed</option>
        </select>
      </div>

      {/* SHAP threshold slider */}
      <div>
        <label>SHAP Importance (min: {minSHAP.toFixed(4)})</label>
        <input
          type="range"
          min={0}
          max={0.0134}
          step={0.0001}
          value={minSHAP}
          onChange={e => setMinSHAP(parseFloat(e.target.value))}
        />
      </div>
    </div>
  );
}
```

### Task 3.2: Implement Tooltips

```typescript
// src/components/Tooltip.tsx
function Tooltip({ node, x, y }) {
  const tooltip = useMemo(() =>
    schema.dashboard_metadata.tooltips.find(t => t.id === node.id),
    [node.id]
  );

  if (!tooltip) return null;

  return (
    <div
      className="tooltip"
      style={{ left: x + 10, top: y + 10 }}
    >
      <h4>{node.label}</h4>
      <p>{tooltip.text}</p>
      <div className="tooltip-meta">
        <span>Domain: {node.domain}</span>
        {node.shap_available && (
          <span>SHAP: {node.shap_score.toFixed(4)}</span>
        )}
      </div>
    </div>
  );
}
```

### Task 3.3: Implement Node Selection & Path Highlighting

```typescript
function handleNodeClick(node: Node) {
  setSelectedNode(node);

  // Highlight incoming and outgoing edges
  const connectedEdges = graph.edges.filter(e =>
    e.source.id === node.id || e.target.id === node.id
  );

  // Update edge styles
  svg.selectAll('line')
    .attr('stroke', e =>
      connectedEdges.includes(e) ? '#FF6B6B' : '#999'
    )
    .attr('stroke-width', e =>
      connectedEdges.includes(e) ? 4 : Math.abs(e.effect) * 3
    );
}
```

**Success Criteria:**
- ✅ Domain filter updates graph in real-time
- ✅ SHAP threshold slider filters nodes smoothly
- ✅ Graph level switcher works (full/professional/simplified)
- ✅ Hover shows tooltip with node details
- ✅ Click highlights connected edges
- ✅ No lag with rapid filter changes

---

## Phase 4: Polish & Deploy

**Duration:** 2-3 days

### Task 4.1: Add Citations Display

```typescript
function CitationPanel() {
  const { citations } = schema.dashboard_metadata;

  return (
    <div className="citations">
      <h3>Data Sources</h3>
      <ul>
        {citations.sources.map(source => (
          <li key={source.name}>
            <a href={source.url} target="_blank">{source.name}</a>
          </li>
        ))}
      </ul>

      <h3>Methods</h3>
      <ul>
        {citations.methods.map(method => (
          <li key={method.name}>
            {method.name} ({method.reference})
          </li>
        ))}
      </ul>

      <button onClick={() => downloadBibTeX(citations.bibtex)}>
        Download BibTeX
      </button>
    </div>
  );
}
```

### Task 4.2: Export Functionality

```typescript
function exportToPNG() {
  const svg = svgRef.current;
  const canvas = document.createElement('canvas');
  const ctx = canvas.getContext('2d');

  // Serialize SVG
  const svgData = new XMLSerializer().serializeToString(svg);
  const img = new Image();
  img.onload = () => {
    ctx.drawImage(img, 0, 0);
    const pngUrl = canvas.toDataURL('image/png');
    const a = document.createElement('a');
    a.href = pngUrl;
    a.download = 'causal_graph.png';
    a.click();
  };
  img.src = 'data:image/svg+xml;base64,' + btoa(svgData);
}

function exportToJSON() {
  const filtered = filterGraph(graph, filters);
  const json = JSON.stringify(filtered, null, 2);
  const blob = new Blob([json], { type: 'application/json' });
  const url = URL.createObjectURL(blob);
  const a = document.createElement('a');
  a.href = url;
  a.download = 'filtered_graph.json';
  a.click();
}
```

### Task 4.3: Add User Tutorial (First-Time Onboarding)

```typescript
function TutorialOverlay() {
  const [step, setStep] = useState(0);
  const [show, setShow] = useState(!localStorage.getItem('tutorial_completed'));

  const steps = [
    { title: 'Welcome', text: 'This dashboard visualizes 290 causal mechanisms...' },
    { title: 'Graph Levels', text: 'Use the level switcher to see simplified versions...' },
    { title: 'Filters', text: 'Filter by domain, SHAP importance, or layer...' },
    { title: 'Interactions', text: 'Click nodes to highlight connections...' }
  ];

  if (!show) return null;

  return (
    <div className="tutorial-overlay">
      <div className="tutorial-card">
        <h3>{steps[step].title}</h3>
        <p>{steps[step].text}</p>
        <button onClick={() => step < steps.length - 1 ? setStep(step + 1) : completeTutorial()}>
          {step < steps.length - 1 ? 'Next' : 'Get Started'}
        </button>
      </div>
    </div>
  );

  function completeTutorial() {
    localStorage.setItem('tutorial_completed', 'true');
    setShow(false);
  }
}
```

**Success Criteria:**
- ✅ Citation panel displays all 6 sources and 4 methods
- ✅ BibTeX download works
- ✅ PNG export creates clean image
- ✅ JSON export includes filtered data only
- ✅ Tutorial shows on first visit
- ✅ Tutorial can be dismissed and won't show again

---

## Technical Specifications

### Performance Targets

| Metric | Target | Critical |
|--------|--------|----------|
| Initial load | < 2s | < 5s |
| Graph render (simplified) | < 500ms | < 1s |
| Graph render (full) | < 1.5s | < 3s |
| Filter update | < 100ms | < 300ms |
| Zoom/pan FPS | 60 FPS | 30 FPS |

### Browser Support

- **Modern**: Chrome 90+, Firefox 88+, Safari 14+, Edge 90+
- **Mobile**: iOS Safari 14+, Chrome Android 90+

### Accessibility

- **WCAG 2.1 Level AA** compliance
- Keyboard navigation for all interactions
- Screen reader support (ARIA labels)
- High contrast mode support

---

## Design Patterns

### Pattern 1: Lazy Loading Large Graphs

```typescript
function LazyGraph({ level }) {
  const [graph, setGraph] = useState(null);

  useEffect(() => {
    // Show loading spinner
    setGraph(null);

    // Load graph asynchronously
    setTimeout(() => {
      const loadedGraph = schema.graphs[level];
      setGraph(loadedGraph);
    }, 100); // Allow UI to update
  }, [level]);

  if (!graph) return <LoadingSpinner />;
  return <GraphVisualization graph={graph} />;
}
```

### Pattern 2: Debounced Filters

```typescript
import { useDebouncedCallback } from 'use-debounce';

function FilterPanel() {
  const debouncedFilter = useDebouncedCallback(
    (filters) => applyFilters(filters),
    300 // 300ms delay
  );

  return (
    <input
      onChange={e => debouncedFilter({ minSHAP: parseFloat(e.target.value) })}
    />
  );
}
```

### Pattern 3: Virtualization for Large Lists

```typescript
import { FixedSizeList } from 'react-window';

function MechanismList({ mechanisms }) {
  return (
    <FixedSizeList
      height={600}
      itemCount={mechanisms.length}
      itemSize={50}
    >
      {({ index, style }) => (
        <div style={style}>{mechanisms[index].label}</div>
      )}
    </FixedSizeList>
  );
}
```

---

## Performance Optimization

### Optimization 1: Canvas Rendering for Large Graphs

For 290+ nodes, consider switching from SVG to Canvas:

```typescript
function CanvasGraph({ graph }) {
  const canvasRef = useRef<HTMLCanvasElement>(null);

  useEffect(() => {
    const ctx = canvasRef.current.getContext('2d');

    function render() {
      ctx.clearRect(0, 0, width, height);

      // Draw edges
      graph.edges.forEach(edge => {
        ctx.beginPath();
        ctx.moveTo(edge.source.x, edge.source.y);
        ctx.lineTo(edge.target.x, edge.target.y);
        ctx.strokeStyle = '#999';
        ctx.lineWidth = Math.abs(edge.effect) * 3;
        ctx.stroke();
      });

      // Draw nodes
      graph.nodes.forEach(node => {
        ctx.beginPath();
        ctx.arc(node.x, node.y, 8, 0, 2 * Math.PI);
        ctx.fillStyle = domainColor(node.domain);
        ctx.fill();
      });
    }

    simulation.on('tick', render);
  }, [graph]);

  return <canvas ref={canvasRef} width={width} height={height} />;
}
```

### Optimization 2: Web Workers for Simulation

```typescript
// simulation.worker.ts
import * as d3 from 'd3';

self.onmessage = (e) => {
  const { nodes, edges } = e.data;

  const simulation = d3.forceSimulation(nodes)
    .force('link', d3.forceLink(edges).id(d => d.id))
    .force('charge', d3.forceManyBody())
    .force('center', d3.forceCenter(600, 400));

  simulation.on('tick', () => {
    self.postMessage({ nodes, edges });
  });
};
```

---

## Testing Strategy

### Unit Tests (Jest)

```typescript
describe('filterGraph', () => {
  it('filters nodes by domain', () => {
    const filtered = filterGraph(graph, { domains: ['Education'] });
    expect(filtered.nodes.every(n => n.domain === 'Education')).toBe(true);
  });

  it('filters nodes by SHAP threshold', () => {
    const filtered = filterGraph(graph, { minSHAP: 0.005 });
    expect(filtered.nodes.every(n => n.shap_score >= 0.005)).toBe(true);
  });
});
```

### Integration Tests (Cypress)

```typescript
describe('Dashboard', () => {
  it('loads and renders simplified graph', () => {
    cy.visit('/');
    cy.get('svg').should('exist');
    cy.get('circle').should('have.length', 167); // simplified graph
  });

  it('filters by domain', () => {
    cy.get('[data-testid="domain-filter"]').select('Education');
    cy.get('circle').should('have.length.lessThan', 167);
  });
});
```

---

## Deployment Checklist

### Pre-Deployment

- [ ] All tests pass
- [ ] Performance benchmarks met
- [ ] Accessibility audit complete (WAVE, axe)
- [ ] Cross-browser testing complete
- [ ] Mobile responsive on iOS/Android
- [ ] Data files optimized (gzip enabled)
- [ ] Error boundaries implemented
- [ ] Analytics integrated
- [ ] SEO metadata added

### Deployment

- [ ] Build production bundle (`npm run build`)
- [ ] Deploy to CDN (Netlify, Vercel, AWS S3)
- [ ] Configure caching headers (1 year for data files)
- [ ] Enable gzip/brotli compression
- [ ] Set up monitoring (Sentry, LogRocket)
- [ ] Create sitemap.xml
- [ ] Submit to Google Search Console

### Post-Deployment

- [ ] Verify production build loads
- [ ] Run Lighthouse audit (score > 90)
- [ ] Monitor error rates (< 0.1%)
- [ ] Check load times (p95 < 3s)
- [ ] Gather user feedback

---

**Version:** 2.0
**Last Updated:** November 21, 2025
**Status:** Production-ready
