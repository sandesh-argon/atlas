/**
 * Simulation State Management (Zustand)
 *
 * Manages all state for the Phase 2 simulation feature:
 * - Panel visibility
 * - Country selection and data
 * - Interventions (max 5)
 * - Simulation results
 */

import { create } from 'zustand';
import {
  simulationAPI,
  type Country,
  type CountryGraph,
  type CountryTimeline,
  type Intervention,
  type TemporalResults,
  type IndicatorInfo,
  type TemporalShapTimeline,
  type StratifiedShapTimeline,
  type IncomeStratum,
  type StratumCounts,
  type AllClassifications,
  type QolScoresByCountry,
  getShapImportance
} from '../services/api';
import type { ScenarioTemplate } from '../types/scenarioTemplate';
import type { RegionKey } from '../constants/regions';
import { debug } from '../utils/debug';
import {
  DATA_YEAR_MAX,
  DATA_YEAR_MIN,
  INTERVENTION_YEAR_MAX,
  SIMULATION_YEAR_MAX,
  SIMULATION_YEAR_MIN,
} from '../constants/time';

// ============================================
// Saved Scenarios (localStorage)
// ============================================

const SCENARIOS_STORAGE_KEY = 'globalviz_saved_scenarios';

export interface SavedScenario {
  id: string;
  name: string;
  country: string;
  interventions: Intervention[];
  simulationStartYear: number;
  simulationEndYear: number;
  savedAt: number; // timestamp
}

function loadScenariosFromStorage(): SavedScenario[] {
  try {
    const raw = localStorage.getItem(SCENARIOS_STORAGE_KEY);
    return raw ? JSON.parse(raw) : [];
  } catch {
    return [];
  }
}

function saveScenariosToStorage(scenarios: SavedScenario[]): void {
  try {
    localStorage.setItem(SCENARIOS_STORAGE_KEY, JSON.stringify(scenarios));
  } catch {
    // Storage full or unavailable — silent fail
  }
}

// ============================================
// Simulation result cache (avoids repeat API calls)
// ============================================
const simCache = new Map<string, TemporalResults>()

function makeSimCacheKey(
  country: string | null,
  interventions: Intervention[],
  baseYear: number,
  horizon: number,
  viewType: 'country' | 'stratified' | 'unified' | 'regional',
  stratum: IncomeStratum | 'unified',
  region: RegionKey | null = null
): string {
  const intKey = interventions
    .map(i => `${i.indicator}:${i.change_percent}:${i.year ?? 0}`)
    .sort()
    .join('|')
  return `${viewType}:${stratum}:${region ?? ''}::${country ?? 'null'}::${intKey}::${baseYear}::${horizon}`
}

// ============================================
// State Interface
// ============================================

type PlaybackMode = 'historical' | 'simulation';

interface SimulationState {
  // Panel visibility
  isPanelOpen: boolean;

  // Countries list
  countries: Country[];
  countriesLoading: boolean;

  // Selected country data
  selectedCountry: string | null;
  countryGraph: CountryGraph | null;
  countryLoading: boolean;

  // Historical timeline for playback (raw indicator values)
  historicalTimeline: CountryTimeline | null;
  timelineLoading: boolean;

  // Temporal SHAP timeline (year-specific importance values)
  temporalShapTimeline: TemporalShapTimeline | null;
  shapTimelineLoading: boolean;
  selectedTarget: string;  // Default target for SHAP (quality_of_life)

  // Cached unified SHAP (persists across country selections)
  cachedUnifiedShap: TemporalShapTimeline | null;
  cachedUnifiedTimeline: CountryTimeline | null;

  // Stratified SHAP (income-based views)
  selectedStratum: IncomeStratum | 'unified';  // 'unified', 'developing', 'emerging', 'advanced'
  stratifiedShapTimeline: StratifiedShapTimeline | null;
  stratumCounts: StratumCounts | null;  // Country counts per stratum for current year

  // Cached classifications (loaded once, used to compute stratum counts)
  classificationsCache: AllClassifications | null;
  stratumCountsCache: Map<number, StratumCounts>;  // year -> counts

  // Indicators for dropdown
  indicators: IndicatorInfo[];
  indicatorsLoading: boolean;
  indicatorsLoadFailed: boolean;

  // Countries load failure
  countriesLoadFailed: boolean;

  // Interventions (max 5)
  interventions: Intervention[];

  // Simulation scope: which graph level to simulate on

  // Simulation state
  isSimulating: boolean;
  temporalResults: TemporalResults | null;

  // Playback state (works for both historical and simulation)
  playbackMode: PlaybackMode;
  currentYearIndex: number;  // Index into years array
  isPlaying: boolean;
  layoutReady: boolean;  // True once D3 render + transitions complete after sim results arrive
  simulationRunToken: number;  // Monotonic token used to detect true new simulation runs
  playbackFinishedToken: number;  // Increments when simulation playback reaches the final year

  // Legacy fields for simulation temporal playback
  currentYear: number;
  horizonYears: number;
  baseYear: number;

  // Simulation timeline range (user-configurable)
  simulationStartYear: number;
  simulationEndYear: number;

  // Effect display filter (percentile threshold 0–1, e.g. 0.5 = top 50%)
  effectFilterPct: number;

  // Target number of visible effects (user-configurable before running sim)
  targetVisibleEffects: number;

  // Highlighted indicator from results table click
  highlightedIndicator: string | null;

  // Saved scenarios
  savedScenarios: SavedScenario[];

  // Policy templates
  templates: ScenarioTemplate[];
  templatesLoaded: boolean;
  templatesLoading: boolean;
  templatesError: string | null;
  activeTemplate: ScenarioTemplate | null;
  templateModified: boolean;

  // Regional views
  selectedRegion: RegionKey | null;
  mapViewMode: 'country' | 'regional';

  // Map layer
  mapForeground: boolean;
  mapHoveredCountry: string | null;
  qolScores: Record<string, QolScoresByCountry> | null;
  qolScoresLoading: boolean;

  // Error handling
  error: string | null;

  // Actions - Regional
  setSelectedRegion: (region: RegionKey | null) => Promise<void>;
  setMapViewMode: (mode: 'country' | 'regional') => void;

  // Actions - Map
  toggleMapForeground: () => void;
  setMapHoveredCountry: (name: string | null) => void;
  loadQolScores: () => Promise<void>;

  // Actions - Panel
  openPanel: () => void;
  closePanel: () => void;
  togglePanel: () => void;

  // Actions - Countries
  loadCountries: () => Promise<void>;
  setCountry: (name: string) => Promise<void>;
  clearCountry: () => void;

  // Actions - Temporal SHAP
  loadTemporalShapTimeline: (country?: string, target?: string) => Promise<void>;
  loadUnifiedTimeline: () => Promise<void>;  // Load unified SHAP for global view
  setTarget: (target: string) => void;

  // Actions - Stratified SHAP
  setStratum: (stratum: IncomeStratum | 'unified') => void;
  loadStratifiedShapTimeline: (stratum: IncomeStratum, target?: string) => Promise<void>;
  loadAllClassifications: () => Promise<void>;  // Load once, cache for all years
  getStratumCountsForYear: (year: number) => StratumCounts | null;  // Lookup from cache

  // Actions - Indicators
  loadIndicators: () => Promise<void>;

  // Actions - Interventions
  addIntervention: (intervention: Intervention) => void;
  updateIntervention: (index: number, intervention: Partial<Intervention>) => void;
  removeIntervention: (index: number) => void;
  clearInterventions: () => void;
  setInterventions: (interventions: Intervention[]) => void;

  // Actions - Simulation Scope

  // Actions - Simulation
  runTemporalSimulation: (horizonYears?: number | undefined) => Promise<void>;
  clearResults: () => void;

  // Actions - Temporal Playback
  setCurrentYear: (year: number) => void;
  setCurrentYearIndex: (index: number) => void;
  play: () => void;
  pause: () => void;
  resetPlayback: () => void;
  setPlaybackMode: (mode: PlaybackMode) => void;
  setLayoutReady: (ready: boolean) => void;
  markPlaybackFinished: () => void;

  // Actions - Simulation Timeline
  setSimulationStartYear: (year: number) => void;
  setSimulationEndYear: (year: number) => void;

  // Actions - Effect Filter
  setEffectFilterPct: (pct: number) => void;
  setTargetVisibleEffects: (count: number) => void;

  // Actions - Highlight
  setHighlightedIndicator: (id: string | null) => void;

  // Actions - Templates
  loadTemplates: () => Promise<void>;
  applyTemplate: (id: string) => void;
  resetTemplate: () => void;
  clearTemplate: () => void;

  // Actions - Scenarios
  saveScenario: (name: string) => void;
  loadScenario: (id: string) => void;
  deleteScenario: (id: string) => void;

  // Actions - Error
  clearError: () => void;
  setError: (error: string) => void;
}

// ============================================
// Constants
// ============================================

const MAX_INTERVENTIONS = 5;
let countryLoadRequestId = 0;
let countryLoadController: AbortController | null = null;
let regionLoadRequestId = 0;
let regionLoadController: AbortController | null = null;

const isAbortError = (error: unknown): boolean => {
  return (
    (error instanceof DOMException && error.name === 'AbortError') ||
    (error instanceof Error && error.name === 'AbortError')
  );
};

// ============================================
// Store Implementation
// ============================================

export const useSimulationStore = create<SimulationState>((set, get) => ({
  // Initial state
  isPanelOpen: false,
  countries: [],
  countriesLoading: false,
  selectedCountry: null,
  countryGraph: null,
  countryLoading: false,
  historicalTimeline: null,
  timelineLoading: true,
  temporalShapTimeline: null,
  shapTimelineLoading: true,
  selectedTarget: 'quality_of_life',
  cachedUnifiedShap: null,
  cachedUnifiedTimeline: null,
  selectedStratum: 'unified',
  stratifiedShapTimeline: null,
  stratumCounts: null,
  classificationsCache: null,
  stratumCountsCache: new Map(),
  indicators: [],
  indicatorsLoading: false,
  indicatorsLoadFailed: false,
  countriesLoadFailed: false,
  interventions: [],
  isSimulating: false,
  temporalResults: null,
  playbackMode: 'historical',
  currentYearIndex: 0,
  isPlaying: false,
  layoutReady: true,
  simulationRunToken: 0,
  playbackFinishedToken: 0,
  currentYear: 0,
  horizonYears: 5,
  baseYear: 2020,
  simulationStartYear: 2020,
  simulationEndYear: 2029,
  effectFilterPct: 0.5,
  targetVisibleEffects: 15,
  highlightedIndicator: null,
  savedScenarios: loadScenariosFromStorage(),
  templates: [],
  templatesLoaded: false,
  templatesLoading: false,
  templatesError: null,
  activeTemplate: null,
  templateModified: false,
  error: null,

  // Regional views
  selectedRegion: null,
  mapViewMode: 'country' as const,

  // Map layer
  mapForeground: false,
  mapHoveredCountry: null,
  qolScores: null,
  qolScoresLoading: false,

  // Regional actions
  setSelectedRegion: async (region) => {
    const { selectedTarget } = get();
    const requestId = ++regionLoadRequestId;

    // Abort any in-flight country or region loads
    if (countryLoadController) {
      countryLoadController.abort();
      countryLoadController = null;
    }
    if (regionLoadController) {
      regionLoadController.abort();
    }
    const controller = new AbortController();
    regionLoadController = controller;

    if (region === null) {
      const { cachedUnifiedShap, cachedUnifiedTimeline } = get();
      set({
        selectedRegion: null,
        selectedCountry: null,
        mapViewMode: 'country',
        countryGraph: null,
        countryLoading: false,
        timelineLoading: false,
        shapTimelineLoading: false,
        historicalTimeline: cachedUnifiedTimeline,
        temporalShapTimeline: cachedUnifiedShap,
        temporalResults: null,
        playbackMode: 'historical',
        currentYearIndex: cachedUnifiedShap ? cachedUnifiedShap.years.length - 1 : 0,
        isPlaying: false,
      });

      if (!cachedUnifiedShap || !cachedUnifiedTimeline) {
        get().loadUnifiedTimeline();
      }

      if (regionLoadController === controller) {
        regionLoadController = null;
      }
      return;
    }

    set({
      selectedRegion: region,
      selectedCountry: null,
      mapViewMode: 'regional',
      countryLoading: true,
      timelineLoading: true,
      shapTimelineLoading: true,
      error: null,
      temporalResults: null,
      historicalTimeline: null,
      temporalShapTimeline: null,
      countryGraph: null,
      playbackMode: 'historical',
      currentYearIndex: 0,
      isPlaying: false,
    });

    try {
      // Fetch regional graph and timeline in parallel
      const [regionGraph, timeline] = await Promise.all([
        simulationAPI.getRegionalGraph(region, controller.signal),
        simulationAPI.getRegionalTimeline(region, undefined, undefined, controller.signal),
      ]);

      if (controller.signal.aborted || requestId !== regionLoadRequestId) return;

      // Fetch regional SHAP timeline
      let shapTimeline: TemporalShapTimeline;
      try {
        shapTimeline = await simulationAPI.getRegionalShapTimeline(
          region,
          selectedTarget,
          undefined,
          undefined,
          controller.signal
        );
      } catch (error) {
        if (isAbortError(error) || controller.signal.aborted || requestId !== regionLoadRequestId) {
          return;
        }
        // Fall back to unified SHAP
        const { cachedUnifiedShap } = get();
        if (cachedUnifiedShap) {
          shapTimeline = cachedUnifiedShap;
        } else {
          shapTimeline = await simulationAPI.getUnifiedShapTimeline(
            selectedTarget,
            undefined,
            undefined,
            controller.signal
          );
        }
      }

      if (controller.signal.aborted || requestId !== regionLoadRequestId) return;

      // Filter SHAP timeline to years with actual data
      const yearsWithData = shapTimeline.years.filter(year => {
        const yearData = shapTimeline.shap_by_year[String(year)];
        if (!yearData) return false;
        return Object.values(yearData).some(v => {
          const mean = typeof v === 'object' && 'mean' in v ? v.mean : v;
          return mean !== 0 && mean !== null && mean !== undefined;
        });
      });

      const effectiveYears = yearsWithData.length > 0 ? yearsWithData : timeline.years;
      const effectiveTimeline: CountryTimeline = {
        ...timeline,
        years: effectiveYears,
        start_year: effectiveYears[0] || timeline.start_year,
        end_year: effectiveYears[effectiveYears.length - 1] || timeline.end_year,
      };

      set({
        countryGraph: regionGraph,
        countryLoading: false,
        historicalTimeline: effectiveTimeline,
        timelineLoading: false,
        temporalShapTimeline: shapTimeline,
        shapTimelineLoading: false,
        currentYearIndex: effectiveTimeline.years.length - 1,
      });
    } catch (err) {
      if (isAbortError(err) || controller.signal.aborted || requestId !== regionLoadRequestId) {
        return;
      }
      set({
        error: err instanceof Error ? err.message : 'Failed to load regional data',
        countryLoading: false,
        timelineLoading: false,
        shapTimelineLoading: false,
        countryGraph: null,
        historicalTimeline: null,
        temporalShapTimeline: null,
      });
    } finally {
      if (regionLoadController === controller) {
        regionLoadController = null;
      }
    }
  },
  setMapViewMode: (mode) => set({ mapViewMode: mode }),

  // Map actions
  toggleMapForeground: () => set((state) => ({ mapForeground: !state.mapForeground })),
  setMapHoveredCountry: (name) => set({ mapHoveredCountry: name }),
  loadQolScores: async () => {
    if (get().qolScores || get().qolScoresLoading) return;
    set({ qolScoresLoading: true });
    try {
      const response = await simulationAPI.getQolScoresAll();
      set({ qolScores: response.scores, qolScoresLoading: false });
    } catch (err) {
      debug.warn('Failed to load QOL scores:', err);
      set({ qolScoresLoading: false });
    }
  },

  // Panel actions
  openPanel: () => set({ isPanelOpen: true }),
  closePanel: () => set({ isPanelOpen: false }),
  togglePanel: () => set((state) => ({ isPanelOpen: !state.isPanelOpen })),

  // Country actions
  loadCountries: async () => {
    const { countriesLoading } = get();
    if (countriesLoading) return;

    set({ countriesLoading: true, countriesLoadFailed: false, error: null });
    try {
      const response = await simulationAPI.getCountries();
      set({ countries: response.countries, countriesLoading: false, countriesLoadFailed: false });
    } catch (err) {
      set({
        error: err instanceof Error ? err.message : 'Failed to load countries',
        countriesLoading: false,
        countriesLoadFailed: true
      });
    }
  },

  setCountry: async (name: string) => {
    const { selectedTarget } = get();
    const requestId = ++countryLoadRequestId;

    if (countryLoadController) {
      countryLoadController.abort();
    }
    const controller = new AbortController();
    countryLoadController = controller;

    // Abort any in-flight region load
    if (regionLoadController) {
      regionLoadController.abort();
      regionLoadController = null;
    }

    set({
      selectedCountry: name,
      selectedRegion: null,
      mapViewMode: 'country',
      countryLoading: true,
      timelineLoading: true,
      shapTimelineLoading: true,
      error: null,
      // Clear previous results when country changes
      temporalResults: null,
      historicalTimeline: null,
      temporalShapTimeline: null,
      // Reset playback to historical mode
      playbackMode: 'historical',
      currentYearIndex: 0,
      isPlaying: false
    });

    try {
      // Fetch graph, raw timeline, and SHAP timeline in parallel
      const [countryGraph, timeline] = await Promise.all([
        simulationAPI.getCountryGraph(name, controller.signal),
        simulationAPI.getCountryTimeline(name, undefined, undefined, controller.signal)
      ]);

      if (controller.signal.aborted || requestId !== countryLoadRequestId) return;

      // Fetch SHAP timeline separately (may fallback to unified)
      let shapTimeline: TemporalShapTimeline;
      try {
        shapTimeline = await simulationAPI.getCountryShapTimeline(
          name,
          selectedTarget,
          undefined,
          undefined,
          controller.signal
        );
      } catch (error) {
        if (isAbortError(error) || controller.signal.aborted || requestId !== countryLoadRequestId) {
          return;
        }
        // Country not available for SHAP, use cached unified if available
        const { cachedUnifiedShap } = get();
        if (cachedUnifiedShap) {
          shapTimeline = cachedUnifiedShap;
        } else {
          shapTimeline = await simulationAPI.getUnifiedShapTimeline(
            selectedTarget,
            undefined,
            undefined,
            controller.signal
          );
        }
      }

      if (controller.signal.aborted || requestId !== countryLoadRequestId) return;

      // Filter SHAP timeline to only include years with actual data (non-zero values)
      // This prevents showing years like 1999-2009 where country SHAP is all zeros
      const yearsWithData = shapTimeline.years.filter(year => {
        const yearData = shapTimeline.shap_by_year[String(year)];
        if (!yearData) return false;
        // Check if any indicator has non-zero SHAP value
        return Object.values(yearData).some(v => {
          const mean = typeof v === 'object' && 'mean' in v ? v.mean : v;
          return mean !== 0 && mean !== null && mean !== undefined;
        });
      });

      // Use filtered years for timeline (min year with data to max year)
      const effectiveYears = yearsWithData.length > 0 ? yearsWithData : timeline.years;
      const effectiveTimeline: CountryTimeline = {
        ...timeline,
        years: effectiveYears,
        start_year: effectiveYears[0] || timeline.start_year,
        end_year: effectiveYears[effectiveYears.length - 1] || timeline.end_year
      };

      set({
        countryGraph,
        countryLoading: false,
        historicalTimeline: effectiveTimeline,
        timelineLoading: false,
        temporalShapTimeline: shapTimeline,
        shapTimelineLoading: false,
        // Start at the latest year
        currentYearIndex: effectiveTimeline.years.length - 1
      });
    } catch (err) {
      if (isAbortError(err) || controller.signal.aborted || requestId !== countryLoadRequestId) {
        return;
      }
      set({
        error: err instanceof Error ? err.message : 'Failed to load country data',
        countryLoading: false,
        timelineLoading: false,
        shapTimelineLoading: false,
        countryGraph: null,
        historicalTimeline: null,
        temporalShapTimeline: null
      });
    } finally {
      if (countryLoadController === controller) {
        countryLoadController = null;
      }
    }
  },

  clearCountry: () => {
    countryLoadRequestId += 1;
    if (countryLoadController) {
      countryLoadController.abort();
      countryLoadController = null;
    }
    const { cachedUnifiedShap, cachedUnifiedTimeline } = get();

    // Clear country-specific data and restore unified timeline from cache
    set({
      selectedCountry: null,
      countryGraph: null,
      temporalResults: null,
      interventions: [],
      activeTemplate: null,
      templateModified: false,
      playbackMode: 'historical',
      isPlaying: false,
      // Restore unified from cache (instant, no loading)
      temporalShapTimeline: cachedUnifiedShap,
      historicalTimeline: cachedUnifiedTimeline,
      currentYearIndex: cachedUnifiedShap ? cachedUnifiedShap.years.length - 1 : 0
    });

    // Only fetch if not cached (shouldn't happen normally)
    if (!cachedUnifiedShap) {
      get().loadUnifiedTimeline();
    }
  },

  // Temporal SHAP actions
  loadTemporalShapTimeline: async (country?: string, target?: string) => {
    const state = get();
    const targetToUse = target || state.selectedTarget;

    set({ shapTimelineLoading: true });

    try {
      let timeline: TemporalShapTimeline;
      if (country) {
        // Try country-specific first, fallback to cached unified
        try {
          timeline = await simulationAPI.getCountryShapTimeline(country, targetToUse);
        } catch {
          // Country not available, use cached unified if available
          const { cachedUnifiedShap } = get();
          if (cachedUnifiedShap) {
            timeline = cachedUnifiedShap;
          } else {
            timeline = await simulationAPI.getUnifiedShapTimeline(targetToUse);
          }
        }
      } else {
        // Use unified (global) timeline
        timeline = await simulationAPI.getUnifiedShapTimeline(targetToUse);
      }

      set({
        temporalShapTimeline: timeline,
        shapTimelineLoading: false
      });
    } catch (err) {
      if (!isAbortError(err)) {
        debug.error('simulation-store', 'Failed to load temporal SHAP timeline:', err);
      }
      set({
        shapTimelineLoading: false,
        temporalShapTimeline: null
      });
    }
  },

  // Load unified SHAP timeline for global view (no country selected)
  // Uses cache if available to avoid refetching on country clear
  loadUnifiedTimeline: async () => {
    const { selectedTarget, cachedUnifiedShap, cachedUnifiedTimeline } = get();

    // Use cached data if available
    if (cachedUnifiedShap && cachedUnifiedTimeline) {
      set({
        temporalShapTimeline: cachedUnifiedShap,
        historicalTimeline: cachedUnifiedTimeline,
        timelineLoading: false,
        shapTimelineLoading: false,
        currentYearIndex: cachedUnifiedShap.years.length - 1,
        playbackMode: 'historical'
      });
      return;
    }

    set({
      timelineLoading: true,
      shapTimelineLoading: true
    });

    try {
      const shapTimeline = await simulationAPI.getUnifiedShapTimeline(selectedTarget);

      // Create a pseudo historicalTimeline from SHAP years for playback
      const unifiedHistoricalTimeline: CountryTimeline = {
        country: 'unified',
        start_year: shapTimeline.years[0] || DATA_YEAR_MIN,
        end_year: shapTimeline.years[shapTimeline.years.length - 1] || DATA_YEAR_MAX,
        years: shapTimeline.years,
        values: {},  // No indicator values for unified view
        n_indicators: 0
      };

      set({
        temporalShapTimeline: shapTimeline,
        historicalTimeline: unifiedHistoricalTimeline,
        // Cache for later use
        cachedUnifiedShap: shapTimeline,
        cachedUnifiedTimeline: unifiedHistoricalTimeline,
        timelineLoading: false,
        shapTimelineLoading: false,
        // Start at the latest year
        currentYearIndex: shapTimeline.years.length - 1,
        playbackMode: 'historical'
      });
    } catch (err) {
      if (!isAbortError(err)) {
        debug.error('simulation-store', 'Failed to load unified timeline:', err);
      }
      set({
        timelineLoading: false,
        shapTimelineLoading: false,
        temporalShapTimeline: null,
        historicalTimeline: null
      });
    }
  },

  setTarget: (target: string) => {
    const { selectedCountry, selectedStratum, loadTemporalShapTimeline, loadStratifiedShapTimeline } = get();
    set({ selectedTarget: target });
    // Reload SHAP timeline with new target
    if (selectedStratum !== 'unified') {
      loadStratifiedShapTimeline(selectedStratum, target);
    } else {
      loadTemporalShapTimeline(selectedCountry || undefined, target);
    }
  },

  // Stratified SHAP actions
  setStratum: (stratum: IncomeStratum | 'unified') => {
    debug.log('simulation-store', `Switching stratum: ${stratum}`);
    const { selectedTarget, loadStratifiedShapTimeline, loadTemporalShapTimeline, historicalTimeline, currentYearIndex } = get();
    set({ selectedStratum: stratum });

    if (stratum !== 'unified') {
      // Load stratified SHAP timeline
      loadStratifiedShapTimeline(stratum, selectedTarget);
    } else {
      // Clear stratified data and use unified
      set({ stratifiedShapTimeline: null });
      loadTemporalShapTimeline(undefined, selectedTarget);
    }

    // Update stratum counts from cache for current year
    const { stratumCountsCache } = get();
    if (historicalTimeline && historicalTimeline.years[currentYearIndex]) {
      const counts = stratumCountsCache.get(historicalTimeline.years[currentYearIndex]);
      if (counts) {
        set({ stratumCounts: counts });
      }
    }
  },

  loadStratifiedShapTimeline: async (stratum: IncomeStratum, target?: string) => {
    const state = get();
    const targetToUse = target || state.selectedTarget;
    const startTime = performance.now();
    debug.log('simulation-store', `Loading ${stratum} SHAP timeline...`);

    set({ shapTimelineLoading: true });

    try {
      const timeline = await simulationAPI.getStratifiedShapTimeline(stratum, targetToUse);
      const duration = performance.now() - startTime;
      debug.log('simulation-store', `${stratum} SHAP loaded in ${duration.toFixed(0)}ms`);
      set({
        stratifiedShapTimeline: timeline,
        shapTimelineLoading: false
      });
    } catch (err) {
      if (!isAbortError(err)) {
        debug.error('simulation-store', 'Failed to load stratified SHAP timeline:', err);
      }
      set({
        shapTimelineLoading: false,
        stratifiedShapTimeline: null
      });
    }
  },

  /**
   * Load all classifications once and precompute stratum counts for all years.
   * This should be called once at app startup.
   */
  loadAllClassifications: async () => {
    // Skip if already loaded
    if (get().classificationsCache) return;

    try {
      const allClassifications = await simulationAPI.getAllClassifications();

      // Precompute stratum counts for all years (1990-2024)
      const countsCache = new Map<number, StratumCounts>();

      for (let year = DATA_YEAR_MIN; year <= DATA_YEAR_MAX; year++) {
        const counts: Record<IncomeStratum, number> = {
          developing: 0,
          emerging: 0,
          advanced: 0
        };

        // Count countries in each stratum for this year
        for (const [_country, countryData] of Object.entries(allClassifications.classifications)) {
          // eslint-disable-next-line @typescript-eslint/no-explicit-any
          const byYear = (countryData as any).by_year;
          const classification = byYear?.[String(year)];
          if (classification?.classification_3tier) {
            const stratum = classification.classification_3tier.toLowerCase() as IncomeStratum;
            if (stratum in counts) {
              counts[stratum]++;
            }
          }
        }

        const total = counts.developing + counts.emerging + counts.advanced;
        countsCache.set(year, { year, counts, total });
      }

      set({
        classificationsCache: allClassifications,
        stratumCountsCache: countsCache
      });
    } catch (err) {
      debug.error('simulation-store', 'Failed to load classifications:', err);
    }
  },

  /**
   * Get stratum counts for a specific year from cache.
   * Returns null if cache not loaded yet.
   */
  getStratumCountsForYear: (year: number): StratumCounts | null => {
    const { stratumCountsCache } = get();
    return stratumCountsCache.get(year) || null;
  },

  // Indicator actions
  loadIndicators: async () => {
    const { indicatorsLoading } = get();
    if (indicatorsLoading) return;

    set({ indicatorsLoading: true, indicatorsLoadFailed: false, error: null });
    try {
      const response = await simulationAPI.getIndicators();
      set({ indicators: response.indicators, indicatorsLoading: false, indicatorsLoadFailed: false });
    } catch (err) {
      set({
        error: err instanceof Error ? err.message : 'Failed to load indicators',
        indicatorsLoading: false,
        indicatorsLoadFailed: true
      });
    }
  },

  // Intervention actions
  addIntervention: (intervention: Intervention) => {
    const { interventions, activeTemplate } = get();
    if (interventions.length >= MAX_INTERVENTIONS) {
      set({ error: `Maximum ${MAX_INTERVENTIONS} interventions allowed` });
      return;
    }
    const updated = [...interventions, intervention];
    const newState: Partial<SimulationState> = { interventions: updated };
    // Sync start year to earliest intervention year
    const years = updated.map(i => i.year).filter((y): y is number => y !== undefined);
    if (years.length > 0) {
      newState.simulationStartYear = Math.min(...years);
    }
    if (activeTemplate) {
      newState.templateModified = true;
    }
    set(newState);
  },

  updateIntervention: (index: number, updates: Partial<Intervention>) => {
    const { interventions, activeTemplate } = get();
    if (index < 0 || index >= interventions.length) return;

    const updated = [...interventions];
    updated[index] = { ...updated[index], ...updates };

    const newState: Partial<SimulationState> = { interventions: updated };
    // Sync start year to earliest intervention year
    if (updates.year !== undefined) {
      const years = updated.map(i => i.year).filter((y): y is number => y !== undefined);
      if (years.length > 0) {
        newState.simulationStartYear = Math.min(...years);
      }
    }
    if (activeTemplate) {
      newState.templateModified = true;
    }
    set(newState);
  },

  removeIntervention: (index: number) => {
    const { interventions, activeTemplate } = get();
    const updated = interventions.filter((_, i) => i !== index);
    const newState: Partial<SimulationState> = { interventions: updated };
    // Sync start year to earliest remaining intervention year
    const years = updated.map(i => i.year).filter((y): y is number => y !== undefined);
    if (years.length > 0) {
      newState.simulationStartYear = Math.min(...years);
    }
    if (activeTemplate) {
      newState.templateModified = true;
    }
    set(newState);
  },

  clearInterventions: () => set({
    interventions: [],
    activeTemplate: null,
    templateModified: false
  }),

  setInterventions: (interventions: Intervention[]) => set({
    interventions: interventions.slice(0, MAX_INTERVENTIONS),
    activeTemplate: null,
    templateModified: false
  }),

  // Simulation actions
  runTemporalSimulation: async (horizonYears?: number) => {
    const { selectedCountry, selectedRegion, selectedStratum, interventions, isSimulating, historicalTimeline, currentYearIndex, simulationStartYear, simulationEndYear } = get();

    if (isSimulating) return;

    // Derive view type from current graph view + country/region selection
    const viewType: 'country' | 'stratified' | 'unified' | 'regional' =
      selectedRegion ? 'regional'
        : selectedCountry ? 'country'
        : selectedStratum === 'unified' ? 'unified'
        : 'stratified';

    if (viewType === 'country' && !selectedCountry) {
      set({ error: 'Please select a country first' });
      return;
    }
    if (interventions.length === 0) {
      set({ error: 'Please add interventions first' });
      return;
    }

    // Default intervention year = simulationStartYear (user-set), fallback to timeline position
    const fallbackYear = historicalTimeline?.years[currentYearIndex] ?? INTERVENTION_YEAR_MAX;
    const defaultYear = simulationStartYear ?? fallbackYear;
    const interventionsWithYear = interventions.map(intv => ({
      ...intv,
      year: intv.year ?? defaultYear
    }));

    // Ensure base_year is at least 1 year before the earliest intervention
    const earliestIntervention = Math.min(...interventionsWithYear.map(i => i.year));
    const effectiveBaseYear = Math.max(
      SIMULATION_YEAR_MIN,
      Math.min(simulationStartYear, earliestIntervention - 1)
    );

    // Compute horizon: from effective base year to the simulation end year
    const effectiveHorizon = horizonYears ?? Math.max(1, simulationEndYear - effectiveBaseYear);

    // For strata/unified, use a representative country (backend needs one for routing)
    const STRATA_REPRESENTATIVE: Record<string, string> = {
      developing: 'India',
      emerging: 'China',
      advanced: 'United States',
    };
    let apiCountry: string | null = selectedCountry || 'United States';
    if (viewType === 'regional') {
      apiCountry = null;
    } else if (viewType === 'unified') {
      apiCountry = null;
    } else if (viewType === 'stratified') {
      apiCountry = STRATA_REPRESENTATIVE[selectedStratum] || 'India';
    }

    // Helper to apply results (shared between cache hit and API response)
    const applyResults = (results: TemporalResults) => {
      const nextRunToken = get().simulationRunToken + 1;

      debug.log('simulation-store', `Simulation complete: ${results.horizon_years} years, base=${results.base_year}, effects keys=${Object.keys(results.effects).length}`);
      set({
        temporalResults: results,
        isSimulating: false,
        horizonYears: results.horizon_years,
        baseYear: results.base_year,
        currentYear: 1,
        currentYearIndex: 1,  // Skip base year (index 0), start at first intervention year
        playbackMode: 'simulation',
        isPlaying: false,
        // Note: targetVisibleEffects is NOT reset here — user's slider choice persists across re-runs
        highlightedIndicator: null,
        layoutReady: false,  // Will be set true by App.tsx after D3 render settles
        simulationRunToken: nextRunToken
      });
    };

    // Check cache before making API call
    const cacheKey = makeSimCacheKey(
      apiCountry,
      interventionsWithYear,
      effectiveBaseYear,
      effectiveHorizon,
      viewType,
      selectedStratum,
      selectedRegion
    );
    const cached = simCache.get(cacheKey);
    if (cached) {
      debug.log('simulation-store', `Cache hit for simulation`);
      applyResults(cached);
      return;
    }

    set({ isSimulating: true, error: null });

    try {
      const results = await simulationAPI.runTemporalSimulation(
        apiCountry,
        interventionsWithYear,
        effectiveHorizon,
        effectiveBaseYear,
        viewType,
        selectedRegion ?? undefined
      );

      // Store in cache
      simCache.set(cacheKey, results);
      applyResults(results);
    } catch (err) {
      const rawMsg = err instanceof Error ? err.message : 'Temporal simulation failed';
      const enriched = /no valid interventions/i.test(rawMsg)
        ? `${rawMsg} — baseline loaded from year ${effectiveBaseYear}. Try adjusting the simulation start year or intervention year.`
        : rawMsg;
      set({
        error: enriched,
        isSimulating: false
      });
    }
  },

  clearResults: () => set({
    temporalResults: null,
    interventions: [],
    currentYear: 0,
    isPlaying: false,
    playbackMode: 'historical',
    highlightedIndicator: null,
    activeTemplate: null,
    templateModified: false,
  }),

  // Temporal playback actions
  setCurrentYear: (year: number) => {
    const { horizonYears } = get();
    set({ currentYear: Math.max(0, Math.min(year, horizonYears)) });
  },

  setCurrentYearIndex: (index: number) => {
    const { historicalTimeline, playbackMode, horizonYears } = get();
    if (playbackMode === 'historical' && historicalTimeline) {
      const maxIndex = historicalTimeline.years.length - 1;
      set({ currentYearIndex: Math.max(0, Math.min(index, maxIndex)) });
    } else {
      // Simulation mode: currentYearIndex is source of truth, derive currentYear
      const clamped = Math.max(0, Math.min(index, horizonYears));
      set({ currentYearIndex: clamped, currentYear: clamped });
    }
  },

  play: () => set({ isPlaying: true }),

  pause: () => set({ isPlaying: false }),

  resetPlayback: () => {
    const { historicalTimeline, playbackMode } = get();
    if (playbackMode === 'historical' && historicalTimeline) {
      // Reset to latest year in historical mode
      set({ currentYearIndex: historicalTimeline.years.length - 1, isPlaying: false });
    } else {
      set({ currentYear: 0, currentYearIndex: 0, isPlaying: false });
    }
  },

  setLayoutReady: (ready: boolean) => set({ layoutReady: ready }),
  markPlaybackFinished: () => set(s => ({ playbackFinishedToken: s.playbackFinishedToken + 1 })),

  setPlaybackMode: (mode: PlaybackMode) => {
    const { historicalTimeline } = get();
    if (mode === 'historical' && historicalTimeline) {
      set({
        playbackMode: mode,
        currentYearIndex: historicalTimeline.years.length - 1,
        isPlaying: false
      });
    } else {
      set({
        playbackMode: mode,
        currentYearIndex: 0,
        currentYear: 0,
        isPlaying: false
      });
    }
  },

  // Simulation timeline actions
  setSimulationStartYear: (year: number) => {
    const { simulationEndYear } = get();
    const clamped = Math.max(SIMULATION_YEAR_MIN, Math.min(simulationEndYear - 1, year));
    set({ simulationStartYear: clamped });
  },

  setSimulationEndYear: (year: number) => {
    const { simulationStartYear } = get();
    const clamped = Math.max(simulationStartYear + 1, Math.min(SIMULATION_YEAR_MAX, year));
    set({ simulationEndYear: clamped });
  },

  // Effect filter actions
  setEffectFilterPct: (pct: number) => {
    set({ effectFilterPct: Math.max(0, Math.min(1, pct)) });
  },

  setTargetVisibleEffects: (count: number) => {
    set({ targetVisibleEffects: Math.max(1, Math.min(50, count)) });
  },

  // Highlight actions
  setHighlightedIndicator: (id: string | null) => set({ highlightedIndicator: id }),

  // Template actions
  loadTemplates: async () => {
    const { templatesLoaded, templatesLoading } = get();
    if (templatesLoaded || templatesLoading) return;
    set({ templatesLoading: true, templatesError: null });

    try {
      const resp = await fetch(`${import.meta.env.BASE_URL}data/scenario-templates.json`);
      if (!resp.ok) {
        throw new Error(`Template fetch failed (${resp.status})`);
      }
      const data = await resp.json();
      set({
        templates: data.templates || [],
        templatesLoaded: true,
        templatesLoading: false,
        templatesError: null
      });
    } catch (err) {
      debug.error('simulation-store', 'Failed to load templates:', err);
      set({
        templatesLoading: false,
        templatesLoaded: false,
        templatesError: err instanceof Error ? err.message : 'Failed to load templates'
      });
    }
  },

  applyTemplate: (id: string) => {
    const { templates, historicalTimeline, simulationEndYear } = get();
    const template = templates.find(t => t.id === id);
    if (!template) return;

    const clampedStart = Math.max(SIMULATION_YEAR_MIN, Math.min(SIMULATION_YEAR_MAX - 1, template.year));
    const clampedEnd = Math.max(clampedStart + 1, Math.min(SIMULATION_YEAR_MAX, simulationEndYear));
    const historicalIndex = historicalTimeline ? historicalTimeline.years.length - 1 : 0;

    const interventions: Intervention[] = template.interventions
      .slice(0, MAX_INTERVENTIONS)
      .map((ti, idx) => ({
        id: `template-${template.id}-${idx}`,
        indicator: ti.indicator_id,
        indicatorLabel: ti.indicator_name,
        change_percent: ti.change_percent,
        domain: '',
        year: clampedStart
      }));

    set({
      interventions,
      activeTemplate: template,
      templateModified: false,
      temporalResults: null,
      currentYear: 0,
      currentYearIndex: historicalIndex,
      playbackMode: 'historical',
      isPlaying: false,
      layoutReady: true,
      highlightedIndicator: null,
      simulationStartYear: clampedStart,
      simulationEndYear: clampedEnd
    });
  },

  resetTemplate: () => {
    const { activeTemplate, historicalTimeline, simulationEndYear } = get();
    if (!activeTemplate) return;

    const clampedStart = Math.max(SIMULATION_YEAR_MIN, Math.min(SIMULATION_YEAR_MAX - 1, activeTemplate.year));
    const clampedEnd = Math.max(clampedStart + 1, Math.min(SIMULATION_YEAR_MAX, simulationEndYear));
    const historicalIndex = historicalTimeline ? historicalTimeline.years.length - 1 : 0;

    const interventions: Intervention[] = activeTemplate.interventions
      .slice(0, MAX_INTERVENTIONS)
      .map((ti, idx) => ({
        id: `template-${activeTemplate.id}-${idx}`,
        indicator: ti.indicator_id,
        indicatorLabel: ti.indicator_name,
        change_percent: ti.change_percent,
        domain: '',
        year: clampedStart
      }));

    set({
      interventions,
      templateModified: false,
      temporalResults: null,
      currentYear: 0,
      currentYearIndex: historicalIndex,
      playbackMode: 'historical',
      isPlaying: false,
      layoutReady: true,
      highlightedIndicator: null,
      simulationStartYear: clampedStart,
      simulationEndYear: clampedEnd
    });
  },

  clearTemplate: () => {
    set({
      activeTemplate: null,
      templateModified: false,
      interventions: []
    });
  },

  // Scenario save/load actions
  saveScenario: (name: string) => {
    const { selectedCountry, interventions, simulationStartYear, simulationEndYear, savedScenarios } = get();
    if (!selectedCountry || interventions.length === 0) return;

    const scenario: SavedScenario = {
      id: `${Date.now()}_${Math.random().toString(36).slice(2, 8)}`,
      name,
      country: selectedCountry,
      interventions: interventions.map(({ indicator, change_percent, year, indicatorLabel, domain }) => ({
        indicator, change_percent, year, indicatorLabel, domain
      })),
      simulationStartYear,
      simulationEndYear,
      savedAt: Date.now()
    };

    const updated = [scenario, ...savedScenarios];
    saveScenariosToStorage(updated);
    set({ savedScenarios: updated });
  },

  loadScenario: (id: string) => {
    const { savedScenarios, setCountry } = get();
    const scenario = savedScenarios.find(s => s.id === id);
    if (!scenario) return;

    // Restore interventions and range immediately
    set({
      interventions: scenario.interventions,
      simulationStartYear: scenario.simulationStartYear,
      simulationEndYear: scenario.simulationEndYear,
      temporalResults: null
    });

    // Load country (async — triggers graph + timeline fetch)
    setCountry(scenario.country);
  },

  deleteScenario: (id: string) => {
    const { savedScenarios } = get();
    const updated = savedScenarios.filter(s => s.id !== id);
    saveScenariosToStorage(updated);
    set({ savedScenarios: updated });
  },

  // Error actions
  clearError: () => set({ error: null }),
  setError: (error: string) => set({ error })
}));

// ============================================
// Selector Hooks (for optimized re-renders)
// ============================================

/** Get just the panel open state */
export const useIsPanelOpen = () => useSimulationStore((state) => state.isPanelOpen);

/** Get selected country name */
export const useSelectedCountry = () => useSimulationStore((state) => state.selectedCountry);

/** Check if currently simulating */
export const useIsSimulating = () => useSimulationStore((state) => state.isSimulating);

/** Get current error */
export const useSimulationError = () => useSimulationStore((state) => state.error);

/** Get intervention count */
export const useInterventionCount = () => useSimulationStore((state) => state.interventions.length);

/** Check if can run simulation — always possible if interventions are set (scope derived from current view) */
export const useCanRunSimulation = () => useSimulationStore((state) => {
  return (
    state.interventions.length > 0 &&
    state.interventions.every(i => i.indicator) &&
    !state.isSimulating
  );
});

/** Get historical timeline */
export const useHistoricalTimeline = () => useSimulationStore((state) => state.historicalTimeline);

/** Get playback mode */
export const usePlaybackMode = () => useSimulationStore((state) => state.playbackMode);

/** Get current year index */
export const useCurrentYearIndex = () => useSimulationStore((state) => state.currentYearIndex);

/** Get current actual year based on mode */
export const useCurrentActualYear = () => useSimulationStore((state) => {
  if (state.playbackMode === 'historical' && state.historicalTimeline) {
    return state.historicalTimeline.years[state.currentYearIndex] || null;
  }
  return state.baseYear + state.currentYearIndex;
});

/** Check if timeline is available */
export const useHasTimeline = () => useSimulationStore((state) =>
  state.historicalTimeline !== null && state.historicalTimeline.years.length > 0
);

/** Get temporal SHAP timeline */
export const useTemporalShapTimeline = () => useSimulationStore((state) => state.temporalShapTimeline);

/** Get selected target */
export const useSelectedTarget = () => useSimulationStore((state) => state.selectedTarget);

/** Get SHAP importance for current year from temporal timeline (returns mean values) */
export const useCurrentYearShapImportance = () => useSimulationStore((state) => {
  const {
    historicalTimeline,
    currentYearIndex,
    selectedCountry,
    selectedStratum,
    temporalShapTimeline,
    stratifiedShapTimeline
  } = state;

  if (!historicalTimeline) return null;
  const currentYear = historicalTimeline.years[currentYearIndex];
  if (!currentYear) return null;

  // Country playback always uses country SHAP timeline.
  const timeline = selectedCountry
    ? temporalShapTimeline
    : selectedStratum !== 'unified' && stratifiedShapTimeline
    ? stratifiedShapTimeline
    : temporalShapTimeline;

  if (!timeline) return null;

  const yearData = timeline.shap_by_year[String(currentYear)];
  if (!yearData) return null;

  // Convert SHAP values to mean-only format for backwards compatibility
  const importanceMap: Record<string, number> = {};
  for (const [nodeId, value] of Object.entries(yearData)) {
    importanceMap[nodeId] = getShapImportance(value);
  }

  return importanceMap;
});

/** Get selected stratum */
export const useSelectedStratum = () => useSimulationStore((state) => state.selectedStratum);

/** Get stratum counts for current year */
export const useStratumCounts = () => useSimulationStore((state) => state.stratumCounts);

/** Get stratified SHAP timeline */
export const useStratifiedShapTimeline = () => useSimulationStore((state) => state.stratifiedShapTimeline);

/** Get simulation view type */

/** Get effect filter percentage */
export const useEffectFilterPct = () => useSimulationStore((state) => state.effectFilterPct);

// Export types
export type { PlaybackMode };
