/**
 * API Service Layer for V3.0 Simulation Backend
 * Provides type-safe access to country data, graphs, and simulation endpoints
 *
 * Configure API base via Vite env:
 * - VITE_API_BASE: explicit base URL (e.g., http://localhost:8000)
 * - VITE_API_MODE: 'local' or 'public' (fallback)
 * - VITE_PUBLIC_API_BASE: public base URL (fallback)
 */
import { INTERVENTION_YEAR_MAX } from '../constants/time';

// ============================================
// API Configuration - Toggle here to switch
// ============================================
type ApiMode = 'local' | 'public';

const getApiBase = (): string => {
  const explicit = import.meta.env.VITE_API_BASE as string | undefined;
  if (explicit && explicit.length > 0) return explicit;

  const publicBase = import.meta.env.VITE_PUBLIC_API_BASE as string | undefined;
  const mode = (import.meta.env.VITE_API_MODE as ApiMode | undefined) ?? 'local';
  if (mode === 'public' && publicBase) return publicBase;

  // Default to local API on same host (LAN-friendly)
  const hostname = typeof window !== 'undefined' ? window.location.hostname : 'localhost';
  return `http://${hostname}:8000`;
};

const API_BASE = getApiBase();

// ============================================
// Performance Diagnostics (view in browser console)
// ============================================
const PERF_DEBUG = import.meta.env.VITE_API_PERF === 'true';
const PERF_INCLUDE_BODY_SIZE = import.meta.env.VITE_API_PERF_BODY_SIZE === 'true';

interface PerfEntry {
  endpoint: string;
  start: number;
  end?: number;
  duration?: number;
  size?: number;
  status?: number;
}

const perfLog: PerfEntry[] = [];

const logPerf = (entry: PerfEntry) => {
  if (!PERF_DEBUG) return;
  perfLog.push(entry);
  const duration = entry.duration?.toFixed(0) || '?';
  const size = entry.size ? `${(entry.size / 1024).toFixed(1)}KB` : '';
  // Performance logs are intentionally opt-in to keep dev console quiet.
  console.log(`[API] ${entry.endpoint} ${duration}ms ${size}`.trim());
};

// Expose to window for console access
if (PERF_DEBUG && typeof window !== 'undefined') {
  (window as unknown as { __apiPerf: PerfEntry[]; __perfSummary: () => void }).__apiPerf = perfLog;
  (window as unknown as { __perfSummary: () => void }).__perfSummary = () => {
    console.table(perfLog.slice(-20).map(e => ({
      endpoint: e.endpoint.replace(API_BASE, ''),
      ms: e.duration?.toFixed(0),
      kb: e.size ? (e.size / 1024).toFixed(1) : '-'
    })));
  };
  console.log('[Perf] API diagnostics enabled. Run __perfSummary() to see recent calls.');
}

/**
 * Fetch wrapper with performance logging
 */
const fetchWithPerf = async (url: string, options?: RequestInit): Promise<Response> => {
  const entry: PerfEntry = { endpoint: url, start: performance.now() };
  try {
    const res = await fetch(url, options);
    entry.end = performance.now();
    entry.duration = entry.end - entry.start;
    entry.status = res.status;

    const contentLength = res.headers.get('content-length');
    if (contentLength) {
      const parsed = Number(contentLength);
      if (!Number.isNaN(parsed)) entry.size = parsed;
    }

    if (PERF_INCLUDE_BODY_SIZE && entry.size === undefined) {
      // Optional and disabled by default: cloning adds measurable overhead.
      const clone = res.clone();
      clone.text().then(text => {
        entry.size = text.length;
        logPerf(entry);
      });
    } else {
      logPerf(entry);
    }
    return res;
  } catch (err) {
    entry.end = performance.now();
    entry.duration = entry.end - entry.start;
    entry.status = 0;
    logPerf(entry);
    throw err;
  }
};

// ============================================
// Type Definitions (matching actual V3.0 API)
// ============================================

/** Country summary from /api/countries */
export interface Country {
  name: string;
  n_edges: number;
  n_edges_with_data: number;
  coverage: number;
}

/** Response from /api/countries */
export interface CountriesResponse {
  total: number;
  countries: Country[];
}

/** Intervention request payload */
export interface Intervention {
  indicator: string;
  change_percent: number;
  year?: number;  // Year to apply this intervention (1990-2024). If undefined, uses base_year.
  // UI-only fields (not sent to API)
  id?: string;
  indicatorLabel?: string;
  domain?: string;
}

/** Single temporal effect with year context */
export interface TemporalEffect {
  baseline: number;
  simulated: number;
  absolute_change: number;
  percent_change: number;
}

/** QoL delta summary (baseline vs simulated). */
export interface QolDelta {
  baseline: number;
  simulated: number;
  delta: number;
  n_indicators: number;
  n_domains: number;
}

/** Causal path entry for a single affected indicator */
export interface CausalPathEntry {
  /** Distance from intervention node (0=intervention, 1=direct effect, etc.) */
  hop: number;
  /** Immediate causal parent node ID (highest |beta * source_change| contributor) */
  source: string;
  /** Beta coefficient on the edge from source → this node */
  beta: number;
}

/** Single spillover effect on a receiving region */
export interface SpilloverEffect {
  effect: number;
  spillover_strength: number;
  direct_effect: number;
  region?: string;
}

/** Spillover results from country-level simulation */
export interface SpilloverResults {
  regional: Record<string, SpilloverEffect>;
  global: Record<string, SpilloverEffect>;
  is_global_power: boolean;
  region_info?: { region_key: string; name: string; spillover_strength: number };
}

/** Response from POST /api/simulate/v31/temporal */
export interface TemporalResults {
  status: string;
  country: string | null;
  horizon_years: number;
  base_year: number;
  view_type: string;
  scope_used?: string;
  region_used?: string | null;
  interventions: Array<Record<string, unknown>>;
  timeline: Record<string, Record<string, number>>;
  effects: Record<string, Record<string, TemporalEffect>>;
  /** Causal path for each affected indicator: hop distance, immediate source, edge beta */
  causal_paths?: Record<string, CausalPathEntry>;
  affected_per_year: Record<string, number>;
  graphs_used: Record<string, string>;
  qol_timeline?: Record<string, QolDelta>;
  spillovers?: SpilloverResults;
  warnings?: string[];
  metadata: Record<string, unknown>;
}

/** Edge from country graph */
export interface CountryGraphEdge {
  source: string;
  target: string;
  beta: number;
  ci_lower: number;
  ci_upper: number;
  global_beta: number;
  data_available: boolean;
  lag: number;
  lag_pvalue: number;
  lag_significant: boolean;
  // Extended stats from V3.1 temporal graphs
  std?: number;
  p_value?: number;
  r_squared?: number;
  n_samples?: number;
  n_bootstrap?: number;
  relationship_type?: string;
}

/** Response from GET /api/graph/{country} */
export interface CountryGraph {
  country: string;
  n_edges: number;
  n_edges_with_data: number;
  edges: CountryGraphEdge[];
  baseline: Record<string, number>;  // indicator ID → baseline value
  shap_importance: Record<string, number>;  // indicator ID → SHAP importance (0-1 normalized)
}

/** Response from GET /api/graph/{country}/timeline */
export interface CountryTimeline {
  country: string;
  start_year: number;
  end_year: number;
  years: number[];
  values: Record<string, Record<string, number>>;  // year (string) → indicator → value
  n_indicators: number;
}

/** Indicator info from /api/indicators */
export interface IndicatorInfo {
  id: string;
  label: string;
  domain: string;
  importance?: number;
}

/** Response from GET /api/indicators */
export interface IndicatorsResponse {
  total: number;
  indicators: IndicatorInfo[];
}

/** Response from GET /api/metadata */
export interface MetadataResponse {
  version: string;
  total_countries: number;
  total_indicators: number;
  total_edges: number;
  graphs_with_lags: number;
  significant_lags: number;
}

/** Response from GET /health */
export interface HealthResponse {
  status: string;
  version: string;
}

// ============================================
// V3.1 Temporal Data Types
// ============================================

/** Response from GET /api/temporal/status */
export interface TemporalDataStatus {
  temporal_shap: {
    status: 'mock' | 'real';
    unified: boolean;
    countries: number;
    country_list: string[];
  };
  temporal_graphs: {
    status: string;
    unified: boolean;
    countries: number;
  };
  development_clusters: {
    status: string;
    unified: boolean;
    countries: number;
  };
  years: {
    min: number;
    max: number;
  };
  targets: string[];
}

/** SHAP value with uncertainty bounds (V3.1 real data format) */
export interface ShapValueWithCI {
  mean: number;
  std: number;
  ci_lower: number;
  ci_upper: number;
}

/** Type guard to check if SHAP value has CI bounds */
export function hasShapCI(value: ShapValueWithCI | number): value is ShapValueWithCI {
  return typeof value === 'object' && 'mean' in value;
}

/** Get importance value from SHAP (handles both old format and new CI format) */
export function getShapImportance(value: ShapValueWithCI | number): number {
  if (hasShapCI(value)) {
    return value.mean;
  }
  return value;
}

/** Response from GET /api/temporal/shap/{target}/timeline */
export interface TemporalShapTimeline {
  country: string | null;
  target: string;
  years: number[];
  shap_by_year: Record<string, Record<string, ShapValueWithCI | number>>;  // year (string) → node_id → importance (with CI)
  is_mock: boolean;
}

/** Response from GET /api/temporal/shap/stratified/{stratum}/{target}/timeline */
export interface StratifiedShapTimeline {
  stratum: string;
  target: string;
  years: number[];
  shap_by_year: Record<string, Record<string, ShapValueWithCI>>;  // year → node_id → SHAP with CI
  countries_by_year: Record<string, string[]>;  // year → country list (dynamic membership)
}

/** Response from GET /api/temporal/shap/{target}/{year} */
export interface TemporalShapYear {
  stratum?: string;
  stratum_name?: string;
  target: string;
  target_name?: string;
  year: number;
  stratification?: {
    countries_in_stratum: string[];
    n_countries: number;
    note?: string;
  };
  shap_importance: Record<string, ShapValueWithCI>;  // node_id → SHAP with CI
  metadata: {
    n_samples?: number;
    n_countries?: number;
    n_indicators?: number;
    n_bootstrap?: number;
    r2_mean?: number;
    r2_std?: number;
    year_range?: [number, number];
    computation_time_sec?: number;
    is_mock_data?: boolean;
  };
  data_quality?: {
    mean_ci_width: number;
  };
  provenance?: {
    computation_date: string;
    code_version: string;
    model: string;
    hyperparameters?: Record<string, number | string>;
  };
}

/** Income strata for stratified views */
export type IncomeStratum = 'developing' | 'emerging' | 'advanced';

/** Income classification for a country/year */
export interface IncomeClassification {
  group_4tier: string;  // 'Low income', 'Lower middle income', 'Upper middle income', 'High income'
  group_3tier: string;  // 'Developing', 'Emerging', 'Advanced'
  gni_per_capita: number | null;
}

/** Raw yearly classification payload used by /api/temporal/classifications */
export interface ClassificationByYear {
  classification_4tier: string;
  classification_3tier: string;
  gni_per_capita: number | null;
}

export interface CountryClassifications {
  iso3: string;
  by_year: Record<string, ClassificationByYear>;
}

/** Response from GET /api/temporal/classifications/{year} */
export interface StratumCounts {
  year: number;
  counts: Record<IncomeStratum, number>;  // { developing: 71, emerging: 45, advanced: 55 }
  total: number;
}

/** Response from GET /api/temporal/classifications (all years) */
export interface AllClassifications {
  total_countries: number;
  classifications: Record<string, CountryClassifications>;
}

/** Available strata info */
export interface StrataInfo {
  strata: IncomeStratum[];
  descriptions: Record<IncomeStratum, string>;
}

/** Data quality for a single year */
export interface YearDataQuality {
  quality: 'complete' | 'partial' | 'sparse';
  indicators: number;
  observed: number;
  observed_pct: number;
  imputed_pct: number;
}

/** Response from GET /api/temporal/data-quality/{country} */
export interface CountryDataQuality {
  country: string;
  total_indicators: number;
  coverage_pct: number;
  observed_pct: number;
  imputed_pct: number;
  confidence: 'high' | 'medium' | 'low';
  by_year: Record<string, YearDataQuality>;  // year (string) → quality
}

/** Aggregated year quality for unified/stratified views */
export interface AggregatedYearQuality {
  quality: 'complete' | 'partial' | 'sparse';
  n_countries: number;
  avg_indicators: number;
  observed_pct: number;
  imputed_pct: number;
}

/** Response from GET /api/temporal/data-quality/unified */
export interface UnifiedDataQuality {
  view: 'unified';
  n_countries: number;
  total_indicators: number;
  avg_coverage_pct: number;
  avg_observed_pct: number;
  avg_imputed_pct: number;
  confidence: 'high' | 'medium' | 'low';
  by_year: Record<string, AggregatedYearQuality>;
}

/** Response from GET /api/temporal/data-quality/stratified/{stratum} */
export interface StratifiedDataQuality {
  view: 'stratified';
  stratum: IncomeStratum;
  n_countries: number;
  countries: string[];
  total_indicators: number;
  avg_coverage_pct: number;
  avg_observed_pct: number;
  avg_imputed_pct: number;
  confidence: 'high' | 'medium' | 'low';
  by_year: Record<string, AggregatedYearQuality>;
}

/** Country info within stratum distribution */
export interface StratumCountryInfo {
  name: string;
  gni_per_capita: number | null;
  position_in_stratum: number;  // 0-1 (how far through the tier)
  distance_to_next: number | null;  // GNI gap to next tier
  progress_pct: number;  // % toward next tier
}

/** Distribution stats for a single stratum */
export interface StratumDistributionStats {
  count: number;
  percentage: number;
}

/** Response from GET /api/temporal/distribution/{year} */
export interface StratumDistribution {
  year: number;
  thresholds: {
    developing_to_emerging: number;
    emerging_to_advanced: number;
  };
  distribution: Record<IncomeStratum, StratumDistributionStats>;
  total_countries: number;
  countries: Record<IncomeStratum, StratumCountryInfo[]>;
}

/** QOL scores for all countries across all years */
export interface QolScoresByCountry {
  iso3: string;
  by_year: Record<string, number>;
}

export interface QolScoresAllResponse {
  definition_id: string;
  year_min?: number;
  year_max?: number;
  scale_min: number;
  scale_max: number;
  calibrated_to: string;
  scores: Record<string, QolScoresByCountry>;
}

// ============================================
// API Client
// ============================================

export const simulationAPI = {
  /**
   * List all countries with graph availability info
   * GET /api/countries
   */
  getCountries: async (signal?: AbortSignal): Promise<CountriesResponse> => {
    const res = await fetchWithPerf(`${API_BASE}/api/countries`, { signal });
    if (!res.ok) {
      throw new Error(`Failed to fetch countries: ${res.status}`);
    }
    return res.json();
  },

  /**
   * Get country-specific causal graph with beta coefficients and lag info
   * GET /api/graph/{country}
   */
  getCountryGraph: async (country: string, signal?: AbortSignal): Promise<CountryGraph> => {
    const res = await fetchWithPerf(`${API_BASE}/api/graph/${encodeURIComponent(country)}`, { signal });
    if (!res.ok) {
      if (res.status === 404) {
        throw new Error(`Graph not found for country: ${country}`);
      }
      throw new Error(`Failed to fetch country graph: ${res.status}`);
    }
    return res.json();
  },

  /**
   * Get historical timeline of indicator values for a country
   * GET /api/graph/{country}/timeline
   */
  getCountryTimeline: async (
    country: string,
    startYear?: number,
    endYear?: number,
    signal?: AbortSignal
  ): Promise<CountryTimeline> => {
    const params = new URLSearchParams();
    if (startYear !== undefined) params.set('start_year', String(startYear));
    if (endYear !== undefined) params.set('end_year', String(endYear));
    const query = params.toString() ? `?${params.toString()}` : '';

    const res = await fetchWithPerf(`${API_BASE}/api/graph/${encodeURIComponent(country)}/timeline${query}`, { signal });
    if (!res.ok) {
      if (res.status === 404) {
        throw new Error(`Timeline not found for country: ${country}`);
      }
      throw new Error(`Failed to fetch country timeline: ${res.status}`);
    }
    return res.json();
  },

  /**
   * Get regional graph data (edges, baseline, SHAP importance)
   * GET /api/graph/region/{region}
   */
  getRegionalGraph: async (region: string, signal?: AbortSignal, year?: number): Promise<CountryGraph> => {
    const params = year !== undefined ? `?year=${year}` : '';
    const res = await fetchWithPerf(`${API_BASE}/api/graph/region/${encodeURIComponent(region)}${params}`, { signal });
    if (!res.ok) {
      if (res.status === 404) {
        throw new Error(`Graph not found for region: ${region}`);
      }
      throw new Error(`Failed to fetch regional graph: ${res.status}`);
    }
    return res.json();
  },

  /**
   * Get regional timeline of indicator values (from baselines)
   * GET /api/graph/region/{region}/timeline
   */
  getRegionalTimeline: async (
    region: string,
    startYear?: number,
    endYear?: number,
    signal?: AbortSignal
  ): Promise<CountryTimeline> => {
    const params = new URLSearchParams();
    if (startYear !== undefined) params.set('start_year', String(startYear));
    if (endYear !== undefined) params.set('end_year', String(endYear));
    const query = params.toString() ? `?${params.toString()}` : '';

    const res = await fetchWithPerf(`${API_BASE}/api/graph/region/${encodeURIComponent(region)}/timeline${query}`, { signal });
    if (!res.ok) {
      if (res.status === 404) {
        throw new Error(`Timeline not found for region: ${region}`);
      }
      throw new Error(`Failed to fetch regional timeline: ${res.status}`);
    }
    return res.json();
  },

  /**
   * Get regional SHAP timeline for all years
   * GET /api/temporal/shap/region/{region}/{target}/timeline
   */
  getRegionalShapTimeline: async (
    region: string,
    target: string,
    startYear?: number,
    endYear?: number,
    signal?: AbortSignal
  ): Promise<TemporalShapTimeline> => {
    const params = new URLSearchParams();
    if (startYear !== undefined) params.set('start_year', String(startYear));
    if (endYear !== undefined) params.set('end_year', String(endYear));
    const query = params.toString() ? `?${params.toString()}` : '';

    const res = await fetchWithPerf(
      `${API_BASE}/api/temporal/shap/region/${encodeURIComponent(region)}/${encodeURIComponent(target)}/timeline${query}`,
      { signal }
    );
    if (!res.ok) {
      if (res.status === 404) {
        throw new Error(`SHAP timeline not found for region ${region}/${target}`);
      }
      throw new Error(`Failed to fetch regional SHAP timeline: ${res.status}`);
    }
    return res.json();
  },

  /**
   * Run temporal simulation with multi-year projection
   * POST /api/simulate/v31/temporal
   */
  runTemporalSimulation: async (
    country: string | null,
    interventions: Intervention[],
    horizonYears: number = 5,
    baseYear?: number,
    viewType: 'country' | 'stratified' | 'unified' | 'regional' = 'country',
    region?: string,
    signal?: AbortSignal
  ): Promise<TemporalResults> => {
    // Map frontend field names to V3.1 API field names
    const apiInterventions = interventions.map(({ indicator, change_percent, year }) => ({
      indicator,
      change_percent,
      ...(year !== undefined ? { year } : {})
    }));

    const res = await fetchWithPerf(`${API_BASE}/api/simulate/v31/temporal`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      signal,
      body: JSON.stringify({
        country,
        ...(region ? { region } : {}),
        interventions: apiInterventions,
        base_year: baseYear ?? INTERVENTION_YEAR_MAX,
        horizon_years: horizonYears,
        top_n_effects: 500,
        view_type: viewType,
      })
    });

    if (!res.ok) {
      const error = await res.json().catch(() => ({ detail: 'Unknown error' }));
      throw new Error(error.detail || `Temporal simulation failed: ${res.status}`);
    }
    return res.json();
  },

  /**
   * Get list of all indicators for intervention dropdown
   * GET /api/indicators
   */
  getIndicators: async (signal?: AbortSignal): Promise<IndicatorsResponse> => {
    const res = await fetchWithPerf(`${API_BASE}/api/indicators?limit=3000`, { signal });
    if (!res.ok) {
      throw new Error(`Failed to fetch indicators: ${res.status}`);
    }
    return res.json();
  },

  /**
   * Get single indicator details
   * GET /api/indicators/{indicator_id}
   */
  getIndicator: async (indicatorId: string, signal?: AbortSignal): Promise<IndicatorInfo> => {
    const res = await fetchWithPerf(`${API_BASE}/api/indicators/${encodeURIComponent(indicatorId)}`, { signal });
    if (!res.ok) {
      if (res.status === 404) {
        throw new Error(`Indicator not found: ${indicatorId}`);
      }
      throw new Error(`Failed to fetch indicator: ${res.status}`);
    }
    return res.json();
  },

  /**
   * Get API metadata and statistics
   * GET /api/metadata
   */
  getMetadata: async (signal?: AbortSignal): Promise<MetadataResponse> => {
    const res = await fetchWithPerf(`${API_BASE}/api/metadata`, { signal });
    if (!res.ok) {
      throw new Error(`Failed to fetch metadata: ${res.status}`);
    }
    return res.json();
  },

  // ============================================
  // V3.1 Temporal Data Endpoints
  // ============================================

  /**
   * Get temporal data status (available data, mock vs real)
   * GET /api/temporal/status
   */
  getTemporalStatus: async (signal?: AbortSignal): Promise<TemporalDataStatus> => {
    const res = await fetchWithPerf(`${API_BASE}/api/temporal/status`, { signal });
    if (!res.ok) {
      throw new Error(`Failed to fetch temporal status: ${res.status}`);
    }
    return res.json();
  },

  /**
   * Get unified (global) SHAP timeline for all years
   * GET /api/temporal/shap/{target}/timeline
   */
  getUnifiedShapTimeline: async (
    target: string,
    startYear?: number,
    endYear?: number,
    signal?: AbortSignal
  ): Promise<TemporalShapTimeline> => {
    const params = new URLSearchParams();
    if (startYear !== undefined) params.set('start_year', String(startYear));
    if (endYear !== undefined) params.set('end_year', String(endYear));
    const query = params.toString() ? `?${params.toString()}` : '';

    const res = await fetchWithPerf(`${API_BASE}/api/temporal/shap/${encodeURIComponent(target)}/timeline${query}`, { signal });
    if (!res.ok) {
      if (res.status === 404) {
        throw new Error(`SHAP timeline not found for target: ${target}`);
      }
      throw new Error(`Failed to fetch SHAP timeline: ${res.status}`);
    }
    return res.json();
  },

  /**
   * Get country-specific SHAP timeline for all years
   * GET /api/temporal/shap/{country}/{target}/timeline
   */
  getCountryShapTimeline: async (
    country: string,
    target: string,
    startYear?: number,
    endYear?: number,
    signal?: AbortSignal
  ): Promise<TemporalShapTimeline> => {
    const params = new URLSearchParams();
    if (startYear !== undefined) params.set('start_year', String(startYear));
    if (endYear !== undefined) params.set('end_year', String(endYear));
    const query = params.toString() ? `?${params.toString()}` : '';

    const res = await fetchWithPerf(
      `${API_BASE}/api/temporal/shap/${encodeURIComponent(country)}/${encodeURIComponent(target)}/timeline${query}`,
      { signal }
    );
    if (!res.ok) {
      if (res.status === 404) {
        throw new Error(`SHAP timeline not found for ${country}/${target}`);
      }
      throw new Error(`Failed to fetch country SHAP timeline: ${res.status}`);
    }
    return res.json();
  },

  /**
   * Get SHAP importance for a specific year (unified or country)
   * GET /api/temporal/shap/{target}/{year} or GET /api/temporal/shap/{country}/{target}/{year}
   */
  getShapYear: async (
    target: string,
    year: number,
    country?: string,
    signal?: AbortSignal
  ): Promise<TemporalShapYear> => {
    const path = country
      ? `/api/temporal/shap/${encodeURIComponent(country)}/${encodeURIComponent(target)}/${year}`
      : `/api/temporal/shap/${encodeURIComponent(target)}/${year}`;

    const res = await fetchWithPerf(`${API_BASE}${path}`, { signal });
    if (!res.ok) {
      if (res.status === 404) {
        throw new Error(`SHAP data not found for ${country || 'unified'}/${target}/${year}`);
      }
      throw new Error(`Failed to fetch SHAP year: ${res.status}`);
    }
    return res.json();
  },

  // ============================================
  // V3.1 Stratified SHAP Endpoints
  // ============================================

  /**
   * Get available income strata
   * GET /api/temporal/shap/strata
   */
  getAvailableStrata: async (signal?: AbortSignal): Promise<StrataInfo> => {
    const res = await fetchWithPerf(`${API_BASE}/api/temporal/shap/strata`, { signal });
    if (!res.ok) {
      throw new Error(`Failed to fetch strata: ${res.status}`);
    }
    return res.json();
  },

  /**
   * Get stratified SHAP timeline for all years
   * GET /api/temporal/shap/stratified/{stratum}/{target}/timeline
   */
  getStratifiedShapTimeline: async (
    stratum: IncomeStratum,
    target: string,
    startYear?: number,
    endYear?: number,
    signal?: AbortSignal
  ): Promise<StratifiedShapTimeline> => {
    const params = new URLSearchParams();
    if (startYear !== undefined) params.set('start_year', String(startYear));
    if (endYear !== undefined) params.set('end_year', String(endYear));
    const query = params.toString() ? `?${params.toString()}` : '';

    const res = await fetchWithPerf(
      `${API_BASE}/api/temporal/shap/stratified/${encodeURIComponent(stratum)}/${encodeURIComponent(target)}/timeline${query}`,
      { signal }
    );
    if (!res.ok) {
      if (res.status === 404) {
        throw new Error(`Stratified SHAP timeline not found for ${stratum}/${target}`);
      }
      throw new Error(`Failed to fetch stratified SHAP timeline: ${res.status}`);
    }
    return res.json();
  },

  /**
   * Get stratified SHAP for a specific year
   * GET /api/temporal/shap/stratified/{stratum}/{target}/{year}
   */
  getStratifiedShapYear: async (
    stratum: IncomeStratum,
    target: string,
    year: number,
    signal?: AbortSignal
  ): Promise<TemporalShapYear> => {
    const res = await fetchWithPerf(
      `${API_BASE}/api/temporal/shap/stratified/${encodeURIComponent(stratum)}/${encodeURIComponent(target)}/${year}`,
      { signal }
    );
    if (!res.ok) {
      if (res.status === 404) {
        throw new Error(`Stratified SHAP not found for ${stratum}/${target}/${year}`);
      }
      throw new Error(`Failed to fetch stratified SHAP: ${res.status}`);
    }
    return res.json();
  },

  // ============================================
  // V3.1 Income Classification Endpoints
  // ============================================

  /**
   * Get stratum counts for a specific year (for tab badges)
   * GET /api/temporal/classifications/{year}
   */
  getStratumCounts: async (year: number, signal?: AbortSignal): Promise<StratumCounts> => {
    const res = await fetchWithPerf(`${API_BASE}/api/temporal/classifications/${year}`, { signal });
    if (!res.ok) {
      if (res.status === 404) {
        throw new Error(`Classifications not found for year ${year}`);
      }
      throw new Error(`Failed to fetch stratum counts: ${res.status}`);
    }
    return res.json();
  },

  /**
   * Get income classification for a specific country/year
   * GET /api/temporal/classifications/{country}/{year}
   */
  getCountryClassification: async (
    country: string,
    year: number,
    signal?: AbortSignal
  ): Promise<{ country: string; year: number; classification: IncomeClassification }> => {
    const res = await fetchWithPerf(
      `${API_BASE}/api/temporal/classifications/${encodeURIComponent(country)}/${year}`,
      { signal }
    );
    if (!res.ok) {
      if (res.status === 404) {
        throw new Error(`Classification not found for ${country}/${year}`);
      }
      throw new Error(`Failed to fetch country classification: ${res.status}`);
    }
    return res.json();
  },

  /**
   * Get all income classifications (for all countries/years) - cached on frontend
   * GET /api/temporal/classifications
   */
  getAllClassifications: async (signal?: AbortSignal): Promise<AllClassifications> => {
    const res = await fetchWithPerf(`${API_BASE}/api/temporal/classifications`, { signal });
    if (!res.ok) {
      throw new Error(`Failed to fetch all classifications: ${res.status}`);
    }
    return res.json();
  },

  // ============================================
  // V3.1 Stratified Graph Endpoints
  // ============================================

  /**
   * Get stratified causal graph for a specific stratum/year
   * GET /api/temporal/graph/stratified/{stratum}/{year}
   */
  getStratifiedGraph: async (
    stratum: IncomeStratum,
    year: number,
    signal?: AbortSignal
  ): Promise<{ stratum: string; year: number; edges: CountryGraphEdge[]; metadata: Record<string, unknown> }> => {
    const res = await fetchWithPerf(
      `${API_BASE}/api/temporal/graph/stratified/${encodeURIComponent(stratum)}/${year}`,
      { signal }
    );
    if (!res.ok) {
      if (res.status === 404) {
        throw new Error(`Stratified graph not found for ${stratum}/${year}`);
      }
      throw new Error(`Failed to fetch stratified graph: ${res.status}`);
    }
    return res.json();
  },

  /**
   * Get unified (global) causal graph for a specific year
   * GET /api/temporal/graph/{year}
   */
  getUnifiedGraph: async (
    year: number,
    signal?: AbortSignal
  ): Promise<{ year: number; edges: CountryGraphEdge[]; n_edges: number }> => {
    const res = await fetchWithPerf(`${API_BASE}/api/temporal/graph/${year}`, { signal });
    if (!res.ok) {
      if (res.status === 404) {
        throw new Error(`Unified graph not found for year ${year}`);
      }
      throw new Error(`Failed to fetch unified graph: ${res.status}`);
    }
    return res.json();
  },

  /**
   * Get country-specific causal graph for a specific year
   * GET /api/temporal/graph/{country}/{year}
   */
  getCountryTemporalGraph: async (
    country: string,
    year: number,
    signal?: AbortSignal
  ): Promise<{ country: string; year: number; edges: CountryGraphEdge[]; n_edges: number }> => {
    const res = await fetchWithPerf(
      `${API_BASE}/api/temporal/graph/${encodeURIComponent(country)}/${year}`,
      { signal }
    );
    if (!res.ok) {
      if (res.status === 404) {
        throw new Error(`Graph not found for ${country}/${year}`);
      }
      throw new Error(`Failed to fetch country temporal graph: ${res.status}`);
    }
    return res.json();
  },

  /**
   * Get available years for a country's temporal graphs
   * GET /api/temporal/graph/{country}/years
   */
  getCountryGraphYears: async (
    country: string,
    signal?: AbortSignal
  ): Promise<{ country: string; years: number[]; total: number }> => {
    const res = await fetchWithPerf(
      `${API_BASE}/api/temporal/graph/${encodeURIComponent(country)}/years`,
      { signal }
    );
    if (!res.ok) {
      if (res.status === 404) {
        throw new Error(`Country '${country}' not found`);
      }
      throw new Error(`Failed to fetch country graph years: ${res.status}`);
    }
    return res.json();
  },

  /**
   * Get income bracket transitions for a specific country
   * GET /api/temporal/transitions/{country}
   */
  getCountryTransitions: async (
    country: string,
    signal?: AbortSignal
  ): Promise<{
    country: string;
    has_transitions: boolean;
    iso3?: string;
    current_stratum?: string;
    transitions?: Array<{
      year: number;
      from: string;
      to: string;
      gni_at_transition: number | null;
    }>;
  }> => {
    const res = await fetchWithPerf(
      `${API_BASE}/api/temporal/transitions/${encodeURIComponent(country)}`,
      { signal }
    );
    if (!res.ok) {
      throw new Error(`Failed to fetch country transitions: ${res.status}`);
    }
    return res.json();
  },

  // ============================================
  // V3.1 Data Quality Endpoints
  // ============================================

  /**
   * Get data quality metrics for a specific country
   * GET /api/temporal/data-quality/{country}
   */
  getCountryDataQuality: async (country: string, signal?: AbortSignal): Promise<CountryDataQuality> => {
    const res = await fetchWithPerf(
      `${API_BASE}/api/temporal/data-quality/${encodeURIComponent(country)}`,
      { signal }
    );
    if (!res.ok) {
      if (res.status === 404) {
        throw new Error(`Data quality not found for ${country}`);
      }
      throw new Error(`Failed to fetch data quality: ${res.status}`);
    }
    return res.json();
  },

  /**
   * Get aggregated data quality for unified (all countries) view
   * GET /api/temporal/data-quality/unified
   */
  getUnifiedDataQuality: async (signal?: AbortSignal): Promise<UnifiedDataQuality> => {
    const res = await fetchWithPerf(`${API_BASE}/api/temporal/data-quality/unified`, { signal });
    if (!res.ok) {
      throw new Error(`Failed to fetch unified data quality: ${res.status}`);
    }
    return res.json();
  },

  /**
   * Get aggregated data quality for a specific income stratum
   * GET /api/temporal/data-quality/stratified/{stratum}
   */
  getStratifiedDataQuality: async (
    stratum: IncomeStratum,
    year: number = 2020,
    signal?: AbortSignal
  ): Promise<StratifiedDataQuality> => {
    const res = await fetchWithPerf(
      `${API_BASE}/api/temporal/data-quality/stratified/${encodeURIComponent(stratum)}?year=${year}`,
      { signal }
    );
    if (!res.ok) {
      if (res.status === 404) {
        throw new Error(`Data quality not found for stratum ${stratum}`);
      }
      throw new Error(`Failed to fetch stratified data quality: ${res.status}`);
    }
    return res.json();
  },

  // ============================================
  // V3.1 Stratum Distribution Endpoints
  // ============================================

  /**
   * Get detailed stratum distribution for a given year
   * GET /api/temporal/distribution/{year}
   *
   * Returns pie chart data, full country lists, GNI positions,
   * and how close each country is to transitioning tiers.
   */
  getStratumDistribution: async (year: number, signal?: AbortSignal): Promise<StratumDistribution> => {
    const res = await fetchWithPerf(`${API_BASE}/api/temporal/distribution/${year}`, { signal });
    if (!res.ok) {
      if (res.status === 400) {
        throw new Error(`Invalid year: ${year}`);
      }
      throw new Error(`Failed to fetch stratum distribution: ${res.status}`);
    }
    return res.json();
  },

  // ============================================
  // Map QOL Scores Endpoints
  // ============================================

  /**
   * Get precomputed QoL scores for all countries across all years.
   * GET /api/map/qol-scores/all
   */
  getQolScoresAll: async (signal?: AbortSignal): Promise<QolScoresAllResponse> => {
    const res = await fetchWithPerf(`${API_BASE}/api/map/qol-scores/all`, { signal });
    if (!res.ok) {
      throw new Error(`Failed to fetch QOL scores: ${res.status}`);
    }
    return res.json();
  }
};

// ============================================
// Utility Functions
// ============================================

/**
 * Check if the API server is reachable
 * GET /health
 */
export async function checkAPIHealth(): Promise<boolean> {
  try {
    const res = await fetchWithPerf(`${API_BASE}/health`, {
      method: 'GET',
      signal: AbortSignal.timeout(5000)
    });
    return res.ok;
  } catch {
    return false;
  }
}

/**
 * Get detailed health info
 * GET /health
 */
export async function getAPIHealth(): Promise<HealthResponse> {
  const res = await fetchWithPerf(`${API_BASE}/health`);
  if (!res.ok) {
    throw new Error(`Health check failed: ${res.status}`);
  }
  return res.json();
}

/**
 * Get API base URL (useful for debugging)
 */
export function getAPIBaseURL(): string {
  return API_BASE;
}
