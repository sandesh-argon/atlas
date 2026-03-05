# QOL Metrics Visualization App

**Modern, interactive visualization of Phase 2 Feature Importance results**

![Status](https://img.shields.io/badge/status-production-green)
![React](https://img.shields.io/badge/React-18.3-blue)
![Recharts](https://img.shields.io/badge/Recharts-2.15-purple)

---

## Overview

A sleek, futuristic React web application that displays the top 20 features for each of the 8 Quality of Life metrics from Phase 2 feature selection. The app features:

- ✨ **Smooth animations** - Fade-ins, slide-ins, and hover effects
- 🌍 **Futuristic globe background** - Animated particle network with floating gradient orbs
- 📊 **Interactive bar charts** - Horizontal bar charts with domain-based color coding
- 🎨 **Modern UI** - Dark theme with gradient accents and glassmorphism effects
- 🚀 **Fast & responsive** - Built with Vite for instant hot-reload

---

## Features

### 8 QOL Metrics (Ranked by Importance)

1. **Mean Years of Schooling** (R² = 0.974) - Tier 1: High Confidence
2. **Infant Mortality** (R² = 0.954) - Tier 1: High Confidence
3. **Undernourishment** (R² = 0.903) - Tier 1: High Confidence
4. **Life Expectancy** (R² = 0.958) - Tier 2: Good Confidence
5. **GDP per Capita** (R² = 0.859) - Tier 2: Good Confidence
6. **Internet Users** (R² = 0.941) - Tier 3: Exploratory
7. **Gini Coefficient** (R² = 0.765) - Tier 3: Exploratory
8. **Homicide Rate** (R² = 0.521) - Tier 3: Exploratory

### Visualization Features

- **Top 20 Features** per metric (from Phase 2 selection)
- **Relative Importance** (0-100% scale, normalized per metric)
- **Domain Color Coding** - 18 thematic domains with unique colors
- **Hover Tooltips** - Show exact importance percentages
- **Domain Legend** - Visual key for feature categories

### UI Enhancements

- **Animated Header** - Gradient text with floating effect
- **Staggered Button Animations** - Sequential slide-in on load
- **Hover Effects** - Shine animation on metric buttons
- **Glassmorphism** - Semi-transparent chart container with backdrop blur
- **Particle Network** - Interactive canvas-based particle system
- **Floating Orbs** - Large gradient orbs that pulse and float
- **Grid Overlay** - Futuristic grid pattern with subtle pulse

---

## Quick Start

### Installation

```bash
cd client
npm install
```

### Development Server

```bash
npm run dev
```

The app will be available at `http://localhost:5173/`

### Build for Production

```bash
npm run build
npm run preview
```

---

## Project Structure

```
client/
├── public/
│   └── data/                    # CSV files (8 metrics × top 25 features)
│       ├── mean_years_schooling_top25_features.csv
│       ├── infant_mortality_top25_features.csv
│       └── ... (6 more)
├── src/
│   ├── App.jsx                  # Main component
│   ├── App.css                  # Styles & animations
│   ├── GlobeBackground.jsx      # Particle network component
│   ├── GlobeBackground.css      # Globe styles
│   └── main.jsx                 # Entry point
├── package.json
└── vite.config.js
```

---

## Data Source

CSV files are generated from Phase 2 feature selection results:
- **Source**: `/Data/Processed/feature_selection/imputation_adjusted/`
- **Script**: `/Data/Scripts/create_visualization_datasets.py`
- **Format**: 25 rows × 9 columns per metric

### CSV Columns

| Column | Description |
|--------|-------------|
| `rank` | Feature ranking (1-25) |
| `feature_code` | World Bank indicator code |
| `feature_name` | Human-readable feature name |
| `feature_type` | base / lag_1-5 / temporal |
| `domain` | Thematic classification (18 categories) |
| `relative_importance_pct` | Normalized importance (0-100) |
| `borda_score` | Raw Borda count score |
| `observed_data_rate` | % of real (non-imputed) data |
| `description` | Full indicator description |

---

## Domain Color Mapping

| Domain | Color | Hex |
|--------|-------|-----|
| Economic Structure & Output | Blue | `#2563EB` |
| Energy & Climate | Red | `#DC2626` |
| International Trade | Green | `#059669` |
| Population & Demographics | Purple | `#7C3AED` |
| Agriculture & Food | Gold | `#CA8A04` |
| Infrastructure & Transport | Cyan | `#0891B2` |
| Health Systems | Pink | `#DB2777` |
| Urban Development | Orange | `#EA580C` |
| Education | Indigo | `#4F46E5` |
| Labor & Employment | Teal | `#0D9488` |
| Technology & Innovation | Violet | `#8B5CF6` |
| Government & Institutions | Blue-Violet | `#6366F1` |
| Financial Services | Emerald | `#10B981` |
| Environment & Resources | Forest | `#059669` |
| Social Protection | Hot Pink | `#EC4899` |
| Gender & Social Inclusion | Amber | `#F59E0B` |
| Water & Sanitation | Sky Blue | `#06B6D4` |
| Communication Systems | Light Blue | `#3B82F6` |

---

## Technologies

- **React 18.3** - UI library
- **Vite 7.1** - Build tool & dev server
- **Recharts 2.15** - Charting library
- **CSS3** - Animations & styling
- **Canvas API** - Particle network rendering

---

## Key Components

### `App.jsx`

Main application component featuring:
- Metric selection state management
- CSV parsing & data loading
- Bar chart rendering with Recharts
- Responsive layout

### `GlobeBackground.jsx`

Futuristic background component with:
- **Particle System** - 100 particles with physics
- **Connection Lines** - Draw lines between nearby particles
- **Gradient Orbs** - 3 large floating gradient spheres
- **Grid Overlay** - Subtle pulsing grid pattern
- **Canvas Animation** - 60fps particle movement

### Animations

Defined in `App.css`:
- `gradientShift` - Animated gradient colors (8s)
- `float` - Vertical floating motion (6s)
- `pulse` - Opacity pulsing (4s)
- `slideIn` - Slide up with fade (0.5s)
- `fadeIn` - Simple fade in (1s)

---

## Performance

- **Initial Load**: ~500ms
- **Chart Switch**: <100ms (instant CSV parsing)
- **Particle Animation**: 60 FPS (Canvas-based)
- **Hot Reload**: <1s (Vite HMR)

---

## Browser Support

- Chrome/Edge 90+
- Firefox 88+
- Safari 14+

Requires:
- CSS Grid
- CSS Custom Properties
- Canvas API
- ES6+ JavaScript

---

## Future Enhancements

Potential additions:
- [ ] Export chart as PNG/SVG
- [ ] Search/filter features
- [ ] Compare multiple metrics side-by-side
- [ ] Metric-to-metric relationship graph
- [ ] Mobile responsive layout
- [ ] Dark/light theme toggle
- [ ] Feature detail modal with full description

---

## License

Internal use only - Part of Global Development Indicators Causal Analysis Project

---

## Contact

For questions about this visualization:
- See main project: `/CLAUDE.md`
- Phase 2 Report: `/Documentation/phase_reports/phase2_report.md`
- Feature Data: `/Documentation/visualizations/feature_importance/`
