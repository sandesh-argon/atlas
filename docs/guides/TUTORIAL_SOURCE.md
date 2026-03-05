# Tutorial Flow & Interaction Guide

**Purpose**: Complete reference for UI/UX designers creating an interactive onboarding tutorial, and for animators producing a walkthrough video. Documents every user interaction, visual feedback pattern, and recommended tutorial sequence.

**Last updated**: 2026-03-03

---

## Table of Contents

1. [First Impressions Flow](#1-first-impressions-flow)
2. [Complete Interaction Map](#2-complete-interaction-map)
3. [Recommended Tutorial Sequence](#3-recommended-tutorial-sequence)
4. [Key "Aha!" Moments](#4-key-aha-moments)
5. [Video Walkthrough Script Outline](#5-video-walkthrough-script-outline)
6. [Tutorial UI Recommendations](#6-tutorial-ui-recommendations)

---

## 1. First Impressions Flow

### What the User Sees on Load

The application loads into a full-viewport (`100vw x 100vh`) container with a `#fafafa` background. The loading sequence is:

1. **Loading spinner** (cyan spinning ring, `#00E5FF` border-top, 32x32px) appears centered on the QoL node position after a 200ms delay to avoid flash. Defined in the `LoadingSpinner` component at the top of `App.tsx`. Animation is `spin 0.8s linear infinite` with a `drop-shadow(0 0 4px rgba(0, 229, 255, 0.4))`.

2. **Data loads** (`v2_1_visualization_final.json` — the full hierarchy of 2,583 nodes), then temporal SHAP timeline and QoL scores load in parallel.

3. **Initial expansion**: The root "Quality of Life" node expands to reveal Ring 1 (Outcome categories). The camera animates to fit Ring 0 + Ring 1 with a 400ms transition.

4. **World Map** appears as a subtle background choropleth layer beneath the graph, colored by QoL scores per country. It is semi-transparent and non-interactive until toggled to foreground.

### Visual Anchors After Load

| Element | Position | Description |
|---------|----------|-------------|
| **QoL node** | Center of graph | Root node, always visible. Displays "Quality of Life" label. Size proportional to total SHAP importance (always the largest node). |
| **Ring 1 nodes** | First concentric ring | 5-9 Outcome categories (Health, Education, Economic, etc.). Each colored by its domain color. Sized by SHAP importance. |
| **Ring outlines** | Concentric circles | Light gray (`#e5e5e5`, 1.5px stroke) circle outlines marking each ring boundary. |
| **Structural edges** | Between rings | Lines connecting parent to child nodes. Gray (`#ccc`), 1px stroke. |
| **Search bar** | Top-left sidebar | White card with search icon, placeholder text "Search... (/)". |
| **Country Selector** | Below search | White card with country input field, flag emojis, region grouping. |
| **Rings panel** | Below country selector | Shows ring labels with node counts and +/- expand/collapse buttons. |
| **Domain legend** | Below rings panel | Color-coded dots with domain names and indicator counts (9 domains). |
| **View tabs** | Top-right | "Global / Split / Local" tab buttons. Split and Local are disabled (grayed) until a target is selected. |
| **Action buttons** | Below view tabs | "Clear (C)" (disabled), "Reset (R)", "Map (M)", "Share" buttons stacked vertically. |
| **Strata tabs** | Top-center | "Unified / Developing / Emerging / Advanced" income stratification tabs (visible only when no country/region selected). |
| **Simulate button** | Bottom-left sidebar | 48px round button with CPU/chip icon. White background, turns blue (#3B82F6) when panel open. |
| **Data Quality button** | Next to Simulate | 48px round button with Erlenmeyer flask icon. Turns green (#10B981) when panel open. |

### What Beckons Interaction

- **Nodes change cursor to pointer** on hover, signaling clickability. This is set via D3 `.style('cursor', 'pointer')` on `circle.node` elements.
- **Hover tooltip** appears at bottom-center of viewport: white card (220-420px wide) with breadcrumb path, node name, ring label badge, domain color badge, SHAP importance percentage, ring rank, and an expand hint ("Click to expand (N)").
- **Node size variation** draws the eye to the largest, most important nodes. Node radius is computed by `ViewportAwareLayout.getNodeRadius()` based on SHAP importance, with a minimum floor for visibility.
- **Domain colors** provide immediate visual clustering. The 9-color scheme (`DOMAIN_COLORS` in `App.tsx` line 257) maps: Health=#E91E63, Education=#FF9800, Economic=#4CAF50, Governance=#9C27B0, Environment=#00BCD4, Demographics=#795548, Security=#F44336, Development=#3F51B5, Research=#009688.
- **Search placeholder** text "Search... (/)" hints at the keyboard shortcut.
- **Country Selector** shows a text input with a subtle prompt to type a country name.
- **Mobile**: A `DesktopBanner` component (`DesktopBanner.tsx`) appears after 2 seconds on viewports below 768px, showing "This visualization works best on a larger screen" in a dark pill at the bottom of the screen, dismissible with an X button.

---

## 2. Complete Interaction Map

### 2.1 Radial Graph Interactions

#### Single-Click on a Node
- **Action**: Toggles expansion of the node (show/hide children)
- **Visual feedback**:
  - **Expand**: Children animate in from the parent's position (scale 0 to 1, opacity 0 to 1). Edges extend. Sibling nodes rotate to make room (260ms cubic-out). Camera auto-zooms to fit the new bounding box.
  - **Collapse**: Text fades first (120ms), then children collapse back to parent (160ms), then siblings rotate to fill the gap. All descendants are also collapsed recursively.
- **Implementation**: `toggleExpansion()` in `App.tsx` line 1701. Uses the D3 data-join pattern with enter/update/exit. Layout recomputed by `computeRadialLayout()`.
- **Structural lock**: 340ms lock prevents rapid-fire clicks from overlapping animations. Queued actions fire after lock expires.
- **Accessibility**: Nodes are focusable SVG circles (`circle.node`) with `tabindex`. Focus ring is 3px `#3B82F6` stroke. Screen reader announces node name, ring, and child count.

#### Double-Click on a Node
- **Action**: Adds the node as a target in Local View, switches view mode to Local (or stays in Local/Split)
- **Visual feedback**: View switches to the Local View flow chart showing causes (pills) -> target (rectangle) -> effects (hexagons)
- **Implementation**: `addToLocalView()` at line 938, triggered via `clickTimeoutRef` to distinguish single from double click
- **Disambiguation**: A 250ms delay timer distinguishes single-click (expand) from double-click (add to local view). If a second click arrives within the window, the single-click is cancelled and double-click fires instead.

#### Hover on a Node
- **Action**: Shows tooltip panel at bottom-center
- **Visual feedback**: Tooltip card (white, rounded, drop shadow) shows:
  - Breadcrumb path in monospace (e.g., "Quality of Life / Health / Disease Burden")
  - Node name (bold, 13px)
  - QoL score (for ring 0 only, showing country/region/stratum mean with year)
  - Ring label badge (gray), Domain color badge
  - SHAP importance percentage, ring rank ("#3 of 24"), current year
  - Simulation effect (if sim active): dark card with green/red accent showing % change
  - Description text
  - Expand hint: "Click to expand (N)" or "Click to collapse"
- **Implementation**: `setHoveredNode()` triggers tooltip rendering in JSX at line 7026. A `tooltipNodeRef` caches the last hovered node for smooth fade-out. Tooltip has `opacity` transition (0.2s ease) and `pointerEvents: none`.

#### Hover off a Node
- **Action**: Tooltip fades out
- **Visual feedback**: Opacity transitions to 0 over 200ms. The cached node keeps the tooltip content visible during the fade.

#### Pan and Zoom (Desktop)
- **Action**: Mouse wheel zooms, click-drag pans
- **Implementation**: D3 zoom behavior (`d3.zoom()`) attached to the SVG element. Zoom range configurable. Transform stored in `currentTransformRef`. Pan/zoom affects the `g.graph-container` group transform.

#### Double-Click on Empty Space
- **Action**: Fits view to all visible nodes
- **Implementation**: `fitToVisibleNodes()` at line 2564. Computes bounding box of all visible nodes, calculates scale to fit with 15% padding, animates transition (300ms).

### 2.2 Ring Expansion Controls

#### Expand Ring (+) Button
- **Action**: Expands all visible nodes in the specified ring layer
- **Visual feedback**: All children of that ring appear simultaneously. Uses "fast path" for bulk operations (no rotation animation, just instant placement with opacity fade).
- **Implementation**: `expandRing()` at line 1823. Activates "dots mode" for rings >= 3 (deep nodes render as lightweight dots without labels or glows).
- **Screen reader**: Announces "Expanded to [ring label]"

#### Collapse Ring (-) Button
- **Action**: Collapses all nodes in the specified ring and their descendants
- **Implementation**: `collapseRing()` at line 1847
- **Screen reader**: Announces "Collapsed to [ring label]"

### 2.3 Search

#### Activating Search
- **Trigger**: Click the search input, press `/`, or press `Ctrl/Cmd + K`
- **Visual feedback**: Input gains focus. If recent searches exist and input is empty, recent searches appear as gray pill buttons below the input (auto-hide after 5 seconds).

#### Typing a Search Query
- **Action**: Fuzzy search across all 2,583 nodes using Fuse.js
- **Visual feedback**: Results dropdown appears below the search bar (white card, up to 5 results). Each result shows:
  - Domain color dot (10x10px circle)
  - Node label (13px, bold)
  - Domain > Subdomain path (11px, gray)
  - Ring number
  - Importance badge (percentage, gray background)
- **Configuration**: Fuse.js with keys: label (weight 0.7), domain (0.2), subdomain (0.1). Threshold 0.4, minimum 2 characters.

#### Selecting a Search Result
- **Action**: Expands the path from root to the target node, highlights the path, zooms to frame the target
- **Visual feedback**:
  - Path nodes expand sequentially
  - Red glow circles (`circle.glow`, `#D32F2F` for target, `#FFCDD2` for ancestors) appear around highlighted nodes with blur filter
  - Camera pans to center on the target
  - Search query clears, dropdown closes
  - Term added to recent searches (max 5)
- **Implementation**: `jumpToNode()` at line 2776

#### Clearing Search
- **Action**: Click X button in search bar, or press `Escape`
- **Visual feedback**: Query clears, results dropdown closes, search input blurs

### 2.4 Country Selection

#### Via Sidebar CountrySelector
- **Action**: Type a country name in the input field (supports 203 countries)
- **Features**:
  - Fuzzy search with common abbreviations (USA, UK, South Korea, etc.)
  - Country flag emojis from ISO codes
  - Region grouping (World Bank regions: 7 groups)
  - Development stage badges (Developing/Emerging/Advanced)
  - Coverage indicator (% of edges with data)
  - Loading state while fetching country graph
- **Visual feedback on selection**:
  - Graph nodes resize based on country-specific SHAP importance
  - Uncovered nodes (no data for this country) are removed from the hierarchy
  - World map highlights the selected country with an outline
  - Strata tabs disappear (country has a fixed income tier)
  - Timeline reloads with country-specific years
  - Loading spinner appears on QoL node while data fetches

#### Via World Map (Foreground Mode)
- **Action**: Click a country on the choropleth map
- **Prerequisite**: Map must be in foreground mode (press M or click Map button)
- **Visual feedback**: Country highlights, same data loading as sidebar selection
- **Map view modes** (when foreground):
  - **Country mode**: Each country colored by its own QoL score (red-orange-green gradient)
  - **Regional mode**: Countries colored by region-mean QoL, thicker inter-region boundaries

#### Clearing Country
- **Action**: Click X button in country selector, or press R (full reset)
- **Visual feedback**: Reverts to unified (global) model. Strata tabs reappear. Map outline clears.

### 2.5 Region Selection

#### Via World Map (Regional Mode)
- **Action**: Switch map to Regional view, click a region (foreground mode required)
- **Regions**: East Asia & Pacific, Europe & Central Asia, Latin America & Caribbean, Middle East & North Africa, North America, South Asia, Sub-Saharan Africa
- **Visual feedback**: Graph shows region-aggregated causal structure. Region countries highlighted on map. Timeline loads region-specific data.

### 2.6 View Mode Switching

#### Global View (G)
- **Default view**. Radial hierarchy with concentric rings.
- **Tab**: Blue-highlighted "Global" button in ViewTabs
- **Keyboard**: Press `G`

#### Local View (L)
- **Requires**: At least one target node (via double-click or simulation)
- **Content**: Horizontal flow chart: Causes (pills) -> Target (rectangle) -> Effects (hexagons)
- **Controls**:
  - Beta threshold slider (filters edges by causal strength, default 0.5)
  - Input depth slider (causes of causes, 1-3 levels)
  - Output depth slider (effects of effects, 1-3 levels)
  - Remove target (X) button per target
  - "Show in Global" navigation link
  - Drill-down (double-click a node to replace target with its children)
  - Drill-up (undo drill-down)
- **Keyboard**: Press `L`
- **Shapes**: Causes = pills (rounded rectangles), Targets = rectangles with 3px border, Effects = octagons

#### Split View (S)
- **Requires**: At least one target AND viewport >= 1024px
- **Content**: Global view on the left, Local view on the right, separated by a draggable 6px divider
- **Divider**: Click-drag to resize (range: 20%-80% of viewport). Default split adapts to viewport: 67% at 1600px+, 60% at 1280px+, 55% at 1024px+
- **Keyboard**: Press `S`
- **Auto-switch**: If viewport drops below 1024px while in split mode, auto-switches to Local view

### 2.7 Income Strata Filtering

#### StrataTabs Component
- **Location**: Top-center of viewport (desktop), top-left (mobile)
- **Visibility**: Only when no country or region is selected
- **Tabs**: Unified (All, blue #3B82F6), Developing (Dev, red #EF5350), Emerging (Emrg, orange #FFA726), Advanced (Adv, green #66BB6A)
- **Action**: Changes the causal structure to show only relationships within the selected income tier
- **Visual feedback**: Active tab fills with its color. Graph recomputes with stratified SHAP values. World map filters to show only countries in the selected tier. Timeline loads stratum-specific data.
- **Tooltips**: GDP thresholds shown on hover (e.g., "Low + Lower-middle income economies, GNI < $4,500/capita")

### 2.8 Simulation Panel

#### Opening the Panel
- **Trigger**: Click the Simulate button (bottom-left, CPU icon) or use `togglePanel()`
- **Visual feedback**: Panel slides in as a draggable card (max 380x560px). On desktop, it appears near the bottom-right. On mobile, it's fullscreen.
- **Button state**: Turns blue (#3B82F6) with blue shadow when panel is open

#### Panel Contents (top to bottom)

1. **Country Selector** (collapsed by default): Searchable input to select scope (country, region, or stratum)
2. **Policy Templates** (`TemplateSelector`): Dropdown picker for pre-built scenarios
   - Categories: health, education, infrastructure, governance, economy, environment (with emoji icons)
   - Each template has difficulty badge (easy/moderate/hard) and feasibility badge (low/medium/high)
   - Selecting a template auto-fills interventions
   - "Modified" badge appears if user changes template values
3. **Intervention Builder** (`InterventionBuilder`): Build custom interventions
   - Add up to 5 interventions (MAX_INTERVENTIONS = 5)
   - Each intervention card:
     - Indicator dropdown (grouped by domain, color-coded)
     - Change % slider (-100% to +200%, with labeled marks)
     - Year slider (1997-2024)
     - Remove button (red X)
   - "Add Intervention" button (dashed border, centered)
4. **Simulation Runner** (`SimulationRunner`): Run and manage simulations
   - Year range selector (dual slider, 1997-2030)
   - "Run Simulation" button (blue, full-width)
   - Loading spinner during simulation
   - Error display
   - Results section:
     - Visible Effects slider (controls how many affected indicators appear on graph)
     - Results table with sortable columns (indicator, % change, domain)
     - CSV export (download/clipboard)
     - Saved scenarios (save/load/delete)

#### Panel Behavior
- **Draggable**: Desktop only. Click header to drag, clamped to viewport bounds.
- **Collapsible**: Click chevron in header to collapse to just the header bar.
- **Focus trap**: Tab cycles within panel. Escape closes.
- **Mobile**: Auto-minimizes when simulation starts so user can see the graph.

### 2.9 Running a Simulation

#### Prerequisites
- Country, region, or stratum must be selected
- At least 1 intervention must be configured (indicator + change %)

#### Running
- **Action**: Click "Run Simulation" button
- **Visual feedback**:
  1. Button shows loading spinner
  2. API call to `/api/simulate/v31/temporal`
  3. On success:
     - Graph collapses to show only root + intervention paths
     - Intervention nodes get cyan pulsing glow rings (`intervention-pulse` animation, synced to `SIM_MS_PER_YEAR = 1500ms`)
     - Timeline Player expands to full width at bottom-center
     - Playback auto-starts after 800ms delay (waits for `layoutReady` signal)

### 2.10 Timeline Playback

#### TimelinePlayer States
1. **Docked**: Bottom-left, just play button (matches simulate button style)
2. **Expanded**: Center, full timeline with year labels, scrubber track, and play/pause button
3. **Collapsed**: Center, play button + current year only
4. **Flow**: docked -> expanded (on play) -> collapsed (4s inactivity) -> docked (4s more)

#### Historical Timeline (default)
- **Years**: 1990-2024 (35 years unified, ~26 years country-specific)
- **Speed**: 300ms/year unified, 700ms/year country-specific
- **Visual**: Node sizes pulse as SHAP values change per year. World map colors update.

#### Simulation Timeline (after running simulation)
- **Years**: base_year to base_year + horizon_years (typically 2020-2029)
- **Speed**: 1500ms/year (`SIM_MS_PER_YEAR`)
- **Visual**:
  - Nodes progressively reveal as causal effects propagate
  - Affected nodes get green (#39FF14) or red (#FF1744) borders/glows based on effect direction
  - Edge ripple animation: edges pulse outward from intervention nodes, staggered by hop distance
    - Near intervention: `sim-edge-ripple-near` (thick, bright)
    - Mid distance: `sim-edge-ripple-mid`
    - Far from intervention: `sim-edge-ripple-far` (thin, soft)
  - Node flash: `sim-node-flash-pos` (green glow) / `sim-node-flash-neg` (red glow), timed to edge ripple arrival
  - QoL node gets cyan pass-through pulse (`qol-cyan-flash`) when ripple reaches root
  - Node sizes shift based on simulated percent_change

#### Scrubber Interaction
- **Click on track**: Jump to that year
- **Click-and-drag**: Smooth scrubbing with cursor tracking. Pauses playback during drag, resumes on release if was playing.
- **Keyboard**: Space bar toggles play/pause

### 2.11 Data Quality Panel

#### Opening
- **Trigger**: Click flask icon button (bottom-left, next to Simulate)
- **Visual feedback**: Panel slides in as a draggable card. Button turns green (#10B981).

#### Contents
- **Data coverage percentage** (overall coverage for selected scope)
- **Observed vs imputed data breakdown**
- **Confidence level** (high/medium/low with color coding)
- **Mini timeline**: Color-coded bar (1990-2024) showing data completeness per year (complete/partial/sparse)
- **Income transitions** (country mode only): Historical income classification changes
- **Stratum distribution** (unified/stratified mode): Pie chart showing developing/emerging/advanced country counts
- **CI Stats tab** (local view only): Confidence intervals for causal edge strengths

### 2.12 Keyboard Shortcuts

| Key | Action | Context |
|-----|--------|---------|
| `/` or `Ctrl+K` | Focus search bar | Global |
| `Escape` | Close search / close panel / blur input | Context-dependent |
| `R` or `Home` | Full reset to initial state | Global |
| `C` | Clear working context (preserves country/region/stratum) | Global |
| `G` | Switch to Global view | Global |
| `L` | Switch to Local view (if targets exist) | Global |
| `S` | Switch to Split view (if targets exist, viewport >= 1024px) | Global |
| `M` (tap) | Toggle map foreground/background | Global |
| `M` (hold >= 250ms) | Peek at map, revert on release | Global |
| `Space` | Toggle timeline play/pause | Global (not in inputs) |
| `+` or `=` | Expand next ring layer | Global |
| `-` or `_` | Collapse outermost ring layer | Global |
| `Tab` | Enter graph keyboard navigation (focus root node) | When no element focused |
| `Arrow Left/Right` | Navigate between sibling nodes | Graph nav active |
| `Enter` or `Space` | Expand/collapse focused node | Graph nav active |
| `Escape` | Navigate to parent node | Graph nav active |

### 2.13 URL Sharing

- **Trigger**: Click "Share" button (top-right action buttons)
- **Visual feedback**: Button text changes to "Copied!" with green background (#E8F5E9) for 2 seconds
- **What's encoded**: View mode, expanded nodes, local view targets, beta threshold, highlighted node, zoom transform, country, stratum, interventions (or template ID), simulation year range
- **Post-simulation nudge**: After simulation playback finishes, the Share button gets a cyan ripple animation (`share-nudge-ripple`) and scale pop (`share-nudge-pop`), repeated 3 times over 4 seconds, to encourage sharing the result.

### 2.14 Mobile-Specific Interactions

- **Hamburger menu**: Fixed top-left (44x44px), opens slide-in drawer (300px or 85vw) containing search, country selector, rings, domains
- **Drawer**: Backdrop overlay, slide-in animation (200ms), focus trap, Escape to close
- **Bottom buttons**: Fixed bottom-left: Data Quality + Simulate buttons (48x48px each)
- **Map button**: Fixed bottom-right (48x48px round button)
- **Strata tabs**: Top-left instead of center (compact mode with short labels: All/Dev/Emrg/Adv)
- **View tabs**: Compact mode (icon-only for action buttons), Split tab hidden below 1024px
- **SimulationPanel**: Fullscreen on mobile, no dragging. Auto-minimizes during simulation. Chevron button to minimize (hide panel but keep bottom button colored).
- **DataQualityPanel**: Same minimize pattern as SimulationPanel
- **Pinch zoom**: Map supports pinch-zoom on touch devices (`enableZoom` prop)
- **Graph**: Vertical anchor at 1/3 viewport height (top section) instead of center, to leave room for controls below

---

## 3. Recommended Tutorial Sequence

### Step 1: "The Web of Development"
- **What the user does**: Observes the initial view, hovers over the central QoL node
- **What they see**: The radial graph with QoL at center, Ring 1 outcome categories around it (Health, Education, Economic, etc.). Tooltip appears showing "Quality of Life" with the current QoL score (e.g., "QoL: 6.3/10 (global mean, 2020)").
- **What they learn**: This is a visualization of how everything connects to Quality of Life. The center is the outcome we care about, and the rings radiating outward represent increasingly specific factors.
- **Suggested tooltip/overlay text**: "Welcome to the Causal Web. This is Quality of Life -- the outcome that everything connects to. The rings around it represent the factors that drive it, from broad domains to specific indicators. Hover over any node to learn more."
- **Duration**: 15 seconds

### Step 2: "Explore the Hierarchy"
- **What the user does**: Clicks on a Ring 1 node (e.g., "Health")
- **What they see**: The Health node expands, revealing Ring 2 children (e.g., "Disease Burden", "Health Infrastructure", "Nutrition"). Other Ring 1 nodes rotate to accommodate. Camera zooms to frame the expanded section.
- **What they learn**: Each category contains sub-categories, and each of those contains even more specific indicators. The graph has 6 layers total, from QoL down to 2,583 individual indicators.
- **Suggested tooltip/overlay text**: "Click any node to expand it. Watch as the sub-categories appear and the graph rearranges. You can keep drilling down through 6 layers of detail, all the way to individual development indicators."
- **Duration**: 15 seconds

### Step 3: "Size Tells a Story"
- **What the user does**: Expands another Ring 1 node and compares node sizes between the two expanded domains
- **What they see**: Nodes are different sizes within each domain. Some are large and prominent, others are small dots.
- **What they learn**: Node size represents SHAP importance -- how much each factor contributes to Quality of Life in the causal model. Larger nodes have more influence.
- **Suggested tooltip/overlay text**: "Notice the different sizes? Larger nodes have more causal influence on Quality of Life, measured by SHAP importance values. Hover over a node to see its exact importance score and rank within its ring."
- **Duration**: 10 seconds

### Step 4: "Find Any Indicator"
- **What the user does**: Presses `/` to open search, types "GDP" or "infant mortality"
- **What they see**: Search results dropdown with fuzzy matches. Domain color dots, labels, ring numbers, and importance badges. Clicks a result.
- **What they learn**: They can search across all 2,583 indicators instantly. Selecting a result auto-expands the path from root to the target and highlights it with a red glow trail.
- **Suggested tooltip/overlay text**: "Press / to search across all 2,583 indicators. Try searching for 'GDP', 'education', or 'emissions'. The graph will expand to reveal the indicator and highlight its path from Quality of Life."
- **Duration**: 15 seconds

### Step 5: "See the Causal Chains"
- **What the user does**: Double-clicks a leaf indicator node (ring 5)
- **What they see**: View switches to Local View. A flow chart appears: causes on the left (pills), the target in the center (rectangle), effects on the right (hexagons). Edges show causal strength (beta values) and direction.
- **What they learn**: Every indicator has causes (what drives it) and effects (what it drives). The Local View reveals these causal pathways as a readable flow chart.
- **Suggested tooltip/overlay text**: "Double-click any node to see its causal neighborhood. Causes appear on the left, effects on the right. Edge thickness shows causal strength. This is the local view -- a focused look at one indicator's causal chains."
- **Duration**: 15 seconds

### Step 6: "Choose a Country"
- **What the user does**: Types a country name in the Country Selector (e.g., "India")
- **What they see**: Loading spinner on QoL node. Graph restructures: some nodes disappear (no data coverage for India), remaining nodes resize based on India-specific SHAP values. World map highlights India. QoL tooltip updates to show India's score.
- **What they learn**: The causal structure is different for each country. India's development drivers are different from Norway's or Nigeria's. The model has data for 203 countries.
- **Suggested tooltip/overlay text**: "Type a country name to see its unique causal structure. Each of the 203 countries has different drivers. Watch how the node sizes change -- what matters most varies dramatically between countries."
- **Duration**: 15 seconds

### Step 7: "Travel Through Time"
- **What the user does**: Presses Space to start the historical timeline playback
- **What they see**: The timeline player expands at the bottom. Year counter advances (1990 -> 2024). Node sizes pulse and shift as SHAP values change over time. World map colors update.
- **What they learn**: Causal relationships evolve over time. What drove Quality of Life in 1990 is different from what drives it today.
- **Suggested tooltip/overlay text**: "Press Space to play the timeline. Watch 35 years of causal evolution -- from 1990 to 2024. Node sizes shift as different factors gain or lose importance over time. You can scrub the timeline or click any year."
- **Duration**: 20 seconds

### Step 8: "Open the Simulation Lab"
- **What the user does**: Clicks the Simulate button (CPU icon, bottom-left)
- **What they see**: Simulation panel slides in. Country selector, policy templates, intervention builder, and simulation runner are visible.
- **What they learn**: This is where they can design hypothetical policy interventions and simulate their effects.
- **Suggested tooltip/overlay text**: "This is the Simulation Lab. Here you can design policy interventions -- like increasing education spending by 50% -- and simulate how the effects ripple through the causal web over 10 years."
- **Duration**: 10 seconds

### Step 9: "Design an Intervention"
- **What the user does**: Selects a policy template (e.g., "Bolsa Familia" or "Universal Healthcare") or manually adds an intervention by selecting an indicator and setting a change percentage
- **What they see**: Template auto-fills intervention cards. Each card shows: indicator name (color-coded by domain), change slider with percentage, year selector. Or manually: clicks "Add Intervention", selects from grouped dropdown, adjusts slider.
- **What they learn**: Interventions are specific, measurable changes to individual indicators. Templates represent real-world policies with realistic parameter values.
- **Suggested tooltip/overlay text**: "Choose a policy template for realistic defaults, or build your own. Set the indicator, the percentage change, and the year. You can add up to 5 interventions to combine multiple policies."
- **Duration**: 15 seconds

### Step 10: "Run the Simulation"
- **What the user does**: Clicks "Run Simulation"
- **What they see**:
  1. Loading spinner on the button
  2. Graph collapses to show only the intervention pathway
  3. Intervention nodes get pulsing cyan glow rings
  4. Timeline expands, playback auto-starts
  5. Effects propagate outward: edges ripple with staggered animations (near=thick/bright, far=thin/soft), affected nodes flash green (positive) or red (negative)
  6. New affected indicators progressively reveal (appear on the graph as effects cascade)
  7. QoL node gets a cyan flash when the ripple reaches the root
  8. QoL score in the tooltip updates with the simulated value and delta
- **What they learn**: Causal effects don't happen all at once. They ripple through the web, reaching different indicators at different times. Some effects are large and immediate, others are small and delayed.
- **Suggested tooltip/overlay text**: "Watch the effects ripple outward from your intervention. Green glows mean improvement, red means decline. Effects take time to propagate -- some arrive in 1 year, others take 5+. The QoL score at the center updates with the simulated result."
- **Duration**: 25 seconds (full simulation playback at 1.5s/year for 10 years)

### Step 11: "Compare Income Groups"
- **What the user does**: Clears the country (Reset), then clicks through the Strata tabs: Developing -> Emerging -> Advanced
- **What they see**: The graph restructures for each income tier. Different nodes become prominent. The causal structure visibly changes.
- **What they learn**: What drives Quality of Life is fundamentally different depending on a country's income level. In developing countries, basic health and infrastructure dominate. In advanced economies, governance and environmental factors matter more.
- **Suggested tooltip/overlay text**: "Click the income tabs at the top to see how causal structures differ by development stage. Developing, Emerging, and Advanced economies have fundamentally different drivers. Compare which nodes grow and shrink as you switch."
- **Duration**: 15 seconds

### Step 12: "Share Your Discovery"
- **What the user does**: Clicks the Share button
- **What they see**: Button text changes to "Copied!" (green). A shareable URL is in their clipboard containing the full state: view mode, expanded nodes, country, simulation parameters, zoom level.
- **What they learn**: Every state of the visualization is shareable. Colleagues can open the link and see exactly what they see.
- **Suggested tooltip/overlay text**: "Click Share to copy a link that captures your exact view -- country, expanded nodes, simulation, zoom level, everything. Send it to colleagues to show them what you found."
- **Duration**: 5 seconds

---

## 4. Key "Aha!" Moments

### Moment 1: "It's Alive" -- First Node Expansion
- **When**: User first clicks a Ring 1 node and children animate in
- **Why it works**: The smooth rotation of siblings + enter animation of children makes the graph feel organic and responsive. The user realizes this is a deeply interactive exploration tool, not a static chart.
- **Technical detail**: 260ms cubic-out rotation transition, 220ms enter with scale and opacity, auto-zoom to fit new bounds (340ms camera animation)

### Moment 2: "The Causal Web" -- First Local View
- **When**: User double-clicks an indicator and sees causes -> target -> effects as a flow chart
- **Why it works**: The abstract radial graph suddenly becomes a readable story: "X causes Y, which causes Z." The shapes (pills for causes, rectangles for targets, hexagons for effects) create immediate visual grammar.
- **Amplifier**: If in Split view, the user can see both the radial position (context) and the causal flow (detail) simultaneously. The Global view highlights the nodes with colored glow rings (cyan for target, orange for causes, purple for effects).

### Moment 3: "Ripple Effects" -- First Simulation Playback
- **When**: User runs a simulation and watches the edge ripple animation propagate outward from the intervention node
- **Why it works**: The staggered animation (120ms per hop) creates a visceral sense of causation flowing through the system. The progressive reveal of affected nodes (they literally appear as the effect reaches them) makes the cascade tangible.
- **Visual hierarchy**: Intervention node has bright cyan pulse -> near edges pulse thick and bright -> mid edges pulse moderately -> far edges pulse thin and soft -> QoL node flashes cyan. The green/red node flashes (positive/negative effects) arrive timed to the edge ripple, creating a wave of consequence.

### Moment 4: "Different Worlds" -- Switching Between Income Strata
- **When**: User clicks from "Developing" to "Advanced" strata tabs and sees the graph fundamentally restructure
- **Why it works**: The same hierarchy shows dramatically different SHAP importance values. Health indicators that were huge in developing countries become tiny in advanced economies. Governance indicators do the opposite. This is a direct visualization of the insight that "what matters depends on where you are."
- **Amplifier**: If the user then selects a specific developing country (e.g., Chad) and then an advanced country (e.g., Norway), the contrast is even more stark -- different nodes disappear entirely due to data coverage differences.

### Moment 5: "Time Changes Everything" -- Timeline Scrubbing
- **When**: User scrubs the timeline for a specific country and watches node sizes shift over decades
- **Why it works**: Seeing a country's causal structure evolve from 1990 to 2024 tells a development story. Education indicators that were tiny in 1990 become prominent by 2024 as a country develops. The World Map choropleth updating simultaneously provides geographic context.

---

## 5. Video Walkthrough Script Outline

### Scene 1: Opening Hook (0:00 - 0:15)
- **On screen**: Dark screen fades to the full radial graph, zooming out from the QoL node. The graph expands ring by ring in time-lapse.
- **Narration**: "What if you could see every factor that affects quality of life in a single picture -- and then change them to see what happens?"
- **Music/mood**: Ambient electronic, building. Think Tycho or Brian Eno. Subtle, warm.
- **Transition**: Quick zoom into QoL node, then pull back to full view.

### Scene 2: The Structure (0:15 - 0:40)
- **On screen**: Slow pan across the radial graph. Click to expand Health domain. Hover tooltips appear. Node sizes pulse.
- **Narration**: "This is 2,583 development indicators arranged by their causal relationship to quality of life. Each ring represents a level of specificity -- from broad domains like Health and Education, down to individual metrics like infant mortality and GDP per capita. The size of each node shows how much it actually matters, measured by SHAP importance values from machine learning models trained on 35 years of data across 178 countries."
- **Music/mood**: Continued ambient, steady.
- **Transition**: Search for "infant mortality" to demonstrate search.

### Scene 3: Causal Pathways (0:40 - 1:05)
- **On screen**: Double-click "Infant Mortality" to enter Local View. Show causes (pills) flowing into it, effects (hexagons) flowing out.
- **Narration**: "Double-click any indicator to see its causal neighborhood. What drives infant mortality? Nutrition, healthcare access, sanitation. What does reducing it improve? Life expectancy, human capital, economic productivity. Every arrow is a statistically validated causal relationship."
- **Music/mood**: Slightly more active. A subtle beat emerges.
- **Transition**: Switch to Split View to show both perspectives.

### Scene 4: Country Lens (1:05 - 1:30)
- **On screen**: Select India. Graph restructures. World map highlights India. Compare with Norway selection.
- **Narration**: "But causal structures aren't universal. Select India and the graph transforms -- different indicators matter, different pathways dominate. Switch to Norway and the picture changes again. What drives quality of life in a developing economy is fundamentally different from an advanced one."
- **Music/mood**: Contemplative. Musical shift on country switch.
- **Transition**: Quick montage of 3-4 country selections with rapid graph changes.

### Scene 5: The Simulation (1:30 - 2:15)
- **On screen**: Open Simulation Panel. Select policy template "Universal Primary Education." Show intervention cards. Click "Run Simulation."
- **Narration**: "Now the powerful part. Open the simulation lab. Choose a policy -- say, Universal Primary Education for India. The model simulates the causal cascade over 10 years."
- **On screen**: Simulation runs. Cyan pulse on intervention. Edge ripples propagate. Nodes flash green/red. Progressive reveal of affected indicators.
- **Narration**: "Watch the effects ripple outward. Education spending improves literacy, which improves employment, which improves income, which improves health outcomes -- and eventually, quality of life ticks upward by 0.3 points. But notice the red flashes too: some indicators decline as resources shift. Every policy has trade-offs."
- **Music/mood**: Building energy during simulation. Pulse syncs with SIM_MS_PER_YEAR rhythm.
- **Transition**: Timeline reaches final year. Share button glows.

### Scene 6: Share and Explore (2:15 - 2:40)
- **On screen**: Click Share button. Show URL copied. Then quick montage: income strata comparison, region selection on map, timeline scrubbing.
- **Narration**: "Share any state with a link. Compare income groups. Explore regions. Scrub 35 years of history. Every view is interactive, every state is shareable. This is development economics, made tangible."
- **Music/mood**: Triumphant resolution. Full, warm.
- **Transition**: Final zoom out to full graph, then fade.

### Scene 7: Call to Action (2:40 - 2:50)
- **On screen**: URL or logo centered. Graph fades to subtle background.
- **Narration**: "Explore the Causal Web of Development. Start at [URL]."
- **Music/mood**: Fade to silence.

---

## 6. Tutorial UI Recommendations

### 6.1 Tooltip/Overlay Placement

| Tutorial Step | Overlay Type | Position | Anchor Element |
|---------------|-------------|----------|----------------|
| Step 1 (QoL intro) | Spotlight + callout | Center, arrow pointing to QoL node | `circle.node` at ring 0 |
| Step 2 (Expand) | Pulsing ring around Ring 1 node | Over a Ring 1 node (suggest Health) | Any `circle.node` at ring 1 |
| Step 3 (Size) | Floating card | Top-right of viewport | None (general explanation) |
| Step 4 (Search) | Arrow pointing to search bar | Top-left, adjacent to search input | `.search-container` |
| Step 5 (Local View) | Highlight ring around a leaf node | Over a ring 5 node | Any `circle.node` at ring 5 |
| Step 6 (Country) | Arrow pointing to country input | Left sidebar, below search | `CountrySelector` container |
| Step 7 (Timeline) | Arrow pointing to play button | Bottom-center | `TimelinePlayer` component |
| Step 8 (Simulate) | Spotlight on simulate button | Bottom-left | Simulate button (48px circle) |
| Step 9 (Intervention) | Inside simulation panel | Within `SimulationPanel` | `InterventionBuilder` component |
| Step 10 (Run) | Full-viewport dim with spotlight on graph | Center, no blocking overlay | SVG container |
| Step 11 (Strata) | Arrow pointing to strata tabs | Top-center | `StrataTabs` component |
| Step 12 (Share) | Arrow pointing to share button | Top-right | `.share-btn-wrap` |

### 6.2 Progressive Disclosure Strategy

**Level 1 -- Essentials (Steps 1-5)**:
Focus on the core interaction loop: see the graph, click to explore, search to find, double-click for detail. These steps can be completed in 60 seconds and give the user autonomy.

**Level 2 -- Context (Steps 6-7)**:
Country selection and timeline add analytical depth. Show these only after the user has completed Level 1 or clicks "Show me more."

**Level 3 -- Power Features (Steps 8-12)**:
Simulation, strata comparison, and sharing are advanced features. Introduce them via a "Ready for more?" prompt after the user has explored for 30+ seconds, or through a persistent "Tutorial" menu item.

### 6.3 Skip/Exit Options

- **"Skip Tutorial" button**: Always visible in the top-right of the tutorial overlay. Persists the skip preference in `localStorage` so it's not shown again.
- **"X" close button**: On every individual tooltip. Closes that step and advances to the next.
- **"Restart Tutorial"**: Available in a settings/help menu (suggest adding a `?` button to the top-right action bar).
- **Progress indicator**: Dots or a step counter (e.g., "3 / 12") at the bottom of each tooltip.
- **Keyboard**: `Escape` to skip current step, `Enter` or click to advance.

### 6.4 "Show Me" vs "Let Me Try" Balance

| Step | Mode | Rationale |
|------|------|-----------|
| Step 1 (QoL intro) | **Show me**: Auto-highlight, no user action needed | First impression should be effortless |
| Step 2 (Expand) | **Let me try**: Pulsing ring invites click | Core interaction, must be learned by doing |
| Step 3 (Size) | **Show me**: Floating explanation card | Observation-based, no action needed |
| Step 4 (Search) | **Let me try**: Focus cursor in search bar, suggest a term | Search-by-doing is intuitive |
| Step 5 (Local View) | **Let me try**: Highlight a node, prompt double-click | Double-click is non-obvious, needs explicit prompt |
| Step 6 (Country) | **Let me try**: Focus country input, suggest typing | Input interaction |
| Step 7 (Timeline) | **Show me** first, then **let me try**: Auto-play for 3 seconds, then prompt user to scrub | Combined: see the effect, then control it |
| Step 8-9 (Simulation) | **Show me**: Auto-open panel, point to template | Panel is complex, guidance needed |
| Step 10 (Run) | **Let me try**: User clicks "Run Simulation" | The payoff moment must be user-initiated |
| Step 11 (Strata) | **Let me try**: Prompt to click tabs | Simple interaction |
| Step 12 (Share) | **Show me**: Highlight button, explain what it does | Low friction, last step |

### 6.5 Mobile vs Desktop Tutorial Differences

#### Desktop Tutorial (viewport >= 1024px)
- Full 12-step tutorial as described above
- Tooltips positioned adjacent to anchor elements
- Split View demonstrated in Step 5
- Simulation panel shown as draggable card
- All keyboard shortcuts mentioned

#### Tablet Tutorial (768px - 1023px)
- Skip Step 6 (Split View not available)
- Strata tabs shown in compact mode
- Simulation panel shown fullscreen
- Reduce keyboard shortcut mentions (users may not have a keyboard)

#### Mobile Tutorial (< 768px)
- Reduce to 6-7 steps:
  1. Pinch-zoom and pan the graph
  2. Tap a node to expand
  3. Use hamburger menu for search and country selection
  4. Tap the Map button (bottom-right) to see the world map
  5. Tap Simulate button (bottom-left) to open simulation
  6. Run a template simulation
  7. Share the result
- Show `DesktopBanner` recommendation first ("Best on desktop"), then proceed with mobile tutorial if user dismisses
- Tutorial tooltips positioned at top or bottom of viewport (avoid covering the graph center)
- Use larger touch targets (44x44px minimum, already enforced by `.touch-target-44` CSS class)
- Mention pinch-zoom and swipe gestures instead of mouse/keyboard
- No mention of keyboard shortcuts

### 6.6 Accessibility Considerations for Tutorial

- All tutorial overlays must have `role="dialog"` and `aria-modal="true"`
- Focus must be trapped within the current tutorial step
- Each tooltip must have a descriptive `aria-label`
- Progress must be announced to screen readers ("Step 3 of 12: Size Tells a Story")
- The `prefers-reduced-motion` media query (already implemented in `App.css` line 233) should suppress tutorial animations
- Tutorial text must meet WCAG 2.1 AA contrast ratios (use the existing `--text-muted: #767676` / `--text-subtle: #6b6b6b` tokens which are already AA-compliant)
- Skip link (`.skip-link` class, already in CSS) should include "Skip tutorial" as an option

---

## Appendix: Component Reference for Overlay Positioning

| Component | File | DOM Selector / Position |
|-----------|------|------------------------|
| Search bar | `App.tsx` line 6447 | `.search-container`, top-left sidebar |
| Country selector | `CountrySelector.tsx` | Within `.left-sidebar`, below search |
| Rings panel | `App.tsx` line 6600 | Within `.left-sidebar`, nav element |
| Domain legend | `App.tsx` line 6632 | Within `.left-sidebar`, bottom of header |
| View tabs | `ViewTabs.tsx` | `position: absolute; top: 16px; right: 10px` |
| Strata tabs | `StrataTabs.tsx` | `position: absolute; top: 4px; left: 50%; transform: translateX(-50%)` (desktop) or `top: 16px; left: 10px` (mobile) |
| Simulate button | `App.tsx` line 6692 | Bottom of `.left-sidebar` (desktop) or `position: fixed; bottom: 10px; left: 10px` (mobile) |
| Data Quality button | `App.tsx` line 6662 | Next to Simulate button |
| Share button | `ViewTabs.tsx` line 360 | `.share-btn-wrap`, within ViewTabs stack |
| Map button | `ViewTabs.tsx` line 304 | Within ViewTabs (desktop) or `position: fixed; bottom: 10px; right: 10px` (mobile) |
| SVG graph | `App.tsx` line 6939 | `svg[role="img"]` within `main#main-content .split-container` |
| Tooltip | `App.tsx` line 7064 | `position: absolute; bottom: 20px; left: 50%; transform: translateX(-50%)` |
| Simulation panel | `SimulationPanel.tsx` | Draggable `div`, default position near bottom-right |
| Data Quality panel | `DataQualityPanel.tsx` | Draggable `div`, default position bottom-left |
| Timeline player | `TimelinePlayer.tsx` | Bottom-center, transitions between docked/expanded/collapsed states |
| Local View | `LocalView/index.tsx` | Right pane in split view, or full viewport in local view |
| World Map | `WorldMap.tsx` | Full viewport, behind graph (z-index managed by `mapForeground` state) |
| Hamburger button | `SidebarDrawer.tsx` | `position: fixed; top: 16px; left: 10px` (mobile only) |
| Desktop banner | `DesktopBanner.tsx` | `position: fixed; bottom: 70px; left: 50%` (mobile only) |

---

## Appendix: CSS Animation Reference

| Animation Name | File | Used For | Duration |
|----------------|------|----------|----------|
| `spin` | `App.css` line 94 | Loading spinner rotation | 0.8s linear infinite |
| `intervention-pulse` | `App.css` line 135 | Intervention node cyan glow | `SIM_MS_PER_YEAR` (1500ms) ease-in-out infinite |
| `causal-edge-pulse` | `App.css` line 141 | Causal edge hop-staggered pulse | variable |
| `sim-edge-ripple-near` | `App.css` line 148 | Near-intervention edge ripple | `SIM_MS_PER_YEAR` |
| `sim-edge-ripple-mid` | `App.css` line 155 | Mid-distance edge ripple | `SIM_MS_PER_YEAR` |
| `sim-edge-ripple-far` | `App.css` line 162 | Far-from-intervention edge ripple | `SIM_MS_PER_YEAR` |
| `qol-cyan-flash` | `App.css` line 170 | QoL node pass-through pulse | `SIM_MS_PER_YEAR` |
| `sim-node-flash-pos` | `App.css` line 178 | Positive effect node glow (green) | `SIM_MS_PER_YEAR` |
| `sim-node-flash-neg` | `App.css` line 183 | Negative effect node glow (red) | `SIM_MS_PER_YEAR` |
| `share-nudge-ripple` | `App.css` line 200 | Share button post-sim glow | 1s ease-out, 3 repeats |
| `share-nudge-pop` | `App.css` line 221 | Share button scale bounce | 1s cubic-bezier, 3 repeats |

All animations respect `prefers-reduced-motion: reduce` (line 233) -- durations forced to 0.01ms.

---

## Appendix: Color Reference

### Domain Colors (nodes, legend, badges)
```
Health:       #E91E63 (pink)
Education:    #FF9800 (orange)
Economic:     #4CAF50 (green)
Governance:   #9C27B0 (purple)
Environment:  #00BCD4 (cyan)
Demographics: #795548 (brown)
Security:     #F44336 (red)
Development:  #3F51B5 (indigo)
Research:     #009688 (teal)
```

### Income Strata Colors
```
Unified:    #3B82F6 (blue)
Developing: #EF5350 (red)
Emerging:   #FFA726 (orange)
Advanced:   #66BB6A (green)
```

### Simulation Effect Colors
```
Positive:      #39FF14 (neon green)
Negative:      #FF1744 (neon red)
Intervention:  #00E5FF (cyan)
Search target: #D32F2F (dark red)
Search path:   #FFCDD2 (light pink)
Local target:  #00ACC1 (teal glow)
Local input:   #FF9800 (orange glow)
Local output:  #7C4DFF (purple glow)
```

### UI Colors
```
Active tab/button:  #3B82F6 (blue)
Panel open (sim):   #3B82F6 (blue)
Panel open (DQ):    #10B981 (green)
Focus ring:         #3B82F6 (blue, 2px)
Background:         #fafafa
Ring outlines:      #e5e5e5
Text muted:         #767676 (WCAG AA compliant)
Text subtle:        #6b6b6b (WCAG AA compliant)
```
