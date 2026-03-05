/**
 * WorldMap — Choropleth background layer showing QOL score by country or region.
 *
 * Renders TopoJSON world geometry colored by QoL V1 (0-1 HDI-calibrated) values.
 * Sits behind the graph as a subtle background, toggleable to foreground via M key.
 *
 * Supports two view modes:
 * - **Country**: each country colored by its own QoL score (default)
 * - **Regional**: all countries in a region share one color (region-mean QoL),
 *   with thicker inter-region boundaries and thinner intra-region borders.
 *
 * Smooth transitions: pre-interpolates all iso3→year scores on data load so
 * timeline scrubbing never flickers.  Years outside the data range are filled
 * with the nearest available value.
 */

import { useEffect, useRef, useMemo, useCallback } from 'react'
import * as d3 from 'd3'
import * as topojson from 'topojson-client'
import type { Topology, GeometryCollection } from 'topojson-specification'
import type { QolScoresByCountry, IncomeStratum, AllClassifications } from '../services/api'
import { ISO3_TO_REGION, REGION_DISPLAY_NAMES, type RegionKey } from '../constants/regions'

/**
 * ISO 3166-1 numeric → ISO 3166-1 alpha-3 mapping.
 * The world-110m.json uses numeric IDs; our QOL data uses alpha-3 (iso3).
 */
const NUMERIC_TO_ISO3: Record<string, string> = {
  '4': 'AFG', '8': 'ALB', '12': 'DZA', '24': 'AGO', '32': 'ARG',
  '36': 'AUS', '40': 'AUT', '50': 'BGD', '56': 'BEL', '204': 'BEN',
  '64': 'BTN', '68': 'BOL', '70': 'BIH', '72': 'BWA', '76': 'BRA',
  '96': 'BRN', '100': 'BGR', '854': 'BFA', '108': 'BDI', '116': 'KHM',
  '120': 'CMR', '124': 'CAN', '140': 'CAF', '148': 'TCD', '152': 'CHL',
  '156': 'CHN', '170': 'COL', '178': 'COG', '180': 'COD', '188': 'CRI',
  '384': 'CIV', '191': 'HRV', '192': 'CUB', '196': 'CYP', '203': 'CZE',
  '208': 'DNK', '262': 'DJI', '214': 'DOM', '218': 'ECU', '818': 'EGY',
  '222': 'SLV', '226': 'GNQ', '232': 'ERI', '233': 'EST', '231': 'ETH',
  '242': 'FJI', '246': 'FIN', '250': 'FRA', '266': 'GAB', '270': 'GMB',
  '268': 'GEO', '276': 'DEU', '288': 'GHA', '300': 'GRC', '320': 'GTM',
  '324': 'GIN', '624': 'GNB', '328': 'GUY', '332': 'HTI', '340': 'HND',
  '348': 'HUN', '352': 'ISL', '356': 'IND', '360': 'IDN', '364': 'IRN',
  '368': 'IRQ', '372': 'IRL', '376': 'ISR', '380': 'ITA', '388': 'JAM',
  '392': 'JPN', '400': 'JOR', '398': 'KAZ', '404': 'KEN', '408': 'PRK',
  '410': 'KOR', '414': 'KWT', '417': 'KGZ', '418': 'LAO', '428': 'LVA',
  '422': 'LBN', '426': 'LSO', '430': 'LBR', '434': 'LBY', '440': 'LTU',
  '442': 'LUX', '807': 'MKD', '450': 'MDG', '454': 'MWI', '458': 'MYS',
  '466': 'MLI', '478': 'MRT', '484': 'MEX', '496': 'MNG', '499': 'MNE',
  '504': 'MAR', '508': 'MOZ', '104': 'MMR', '516': 'NAM', '524': 'NPL',
  '528': 'NLD', '554': 'NZL', '558': 'NIC', '562': 'NER', '566': 'NGA',
  '578': 'NOR', '512': 'OMN', '586': 'PAK', '591': 'PAN', '598': 'PNG',
  '600': 'PRY', '604': 'PER', '608': 'PHL', '616': 'POL', '620': 'PRT',
  '634': 'QAT', '642': 'ROU', '643': 'RUS', '646': 'RWA', '682': 'SAU',
  '686': 'SEN', '688': 'SRB', '694': 'SLE', '702': 'SGP', '703': 'SVK',
  '705': 'SVN', '706': 'SOM', '710': 'ZAF', '724': 'ESP', '144': 'LKA',
  '729': 'SDN', '740': 'SUR', '748': 'SWZ', '752': 'SWE', '756': 'CHE',
  '760': 'SYR', '158': 'TWN', '762': 'TJK', '834': 'TZA', '764': 'THA',
  '626': 'TLS', '768': 'TGO', '780': 'TTO', '788': 'TUN', '792': 'TUR',
  '795': 'TKM', '800': 'UGA', '804': 'UKR', '784': 'ARE', '826': 'GBR',
  '840': 'USA', '858': 'URY', '860': 'UZB', '862': 'VEN', '704': 'VNM',
  '887': 'YEM', '894': 'ZMB', '716': 'ZWE', '10': 'ATA',
  '304': 'GRL', '630': 'PRI', '275': 'PSE', '732': 'ESH',
  '90': 'SLB', '548': 'VUT', '174': 'COM', '480': 'MUS',
  '728': 'SSD', '-99': 'XKX',
  '44': 'BHS', '84': 'BLZ', '51': 'ARM', '112': 'BLR',
  '498': 'MDA', '31': 'AZE', '238': 'FLK', '260': 'ATF', '540': 'NCL'
}

/** Full year range we support for timeline playback. */
const YEAR_MIN = 1990
const YEAR_MAX = 2030

/** Normalize TopoJSON feature id (may be zero-padded string like "004" or number) */
function normalizeId(id: string | number | undefined): string {
  if (id == null) return ''
  const n = Number(id)
  return isNaN(n) ? String(id) : String(n)
}

/** Get region key for a TopoJSON feature. */
function featureRegion(d: GeoJSON.Feature): RegionKey | undefined {
  const numId = normalizeId(d.id)
  const iso3 = NUMERIC_TO_ISO3[numId]
  return iso3 ? ISO3_TO_REGION[iso3] as RegionKey | undefined : undefined
}

interface WorldMapProps {
  foreground: boolean
  qolScores: Record<string, QolScoresByCountry> | null
  currentYear: number
  selectedStratum: IncomeStratum | 'unified'
  classificationsCache: AllClassifications | null
  simAdjustments?: Record<string, number>
  onCountrySelect?: (name: string) => void
  onCountryHover?: (name: string | null) => void
  selectedCountryIso3?: string | null
  mapViewMode: 'country' | 'regional'
  onRegionSelect?: (regionKey: string) => void
  selectedRegion?: string | null
  /** Enable pinch-zoom / pan on the map (touch devices, mobile) */
  enableZoom?: boolean
  /** Position map in bottom 2/3 of viewport (mobile stacked layout) */
  mobileLayout?: boolean
}

/**
 * Build Set<iso3> of countries belonging to the selected stratum.
 * Returns null when stratum is 'unified' (show all).
 */
function buildStratumIso3s(
  classifications: AllClassifications | null,
  stratum: IncomeStratum | 'unified',
): Set<string> | null {
  if (stratum === 'unified' || !classifications) return null
  const allowed = new Set<string>()
  const targetLabel = stratum.charAt(0).toUpperCase() + stratum.slice(1)
  for (const [, countryData] of Object.entries(classifications.classifications)) {
    const iso3 = countryData.iso3
    if (!iso3) continue
    const byYear = countryData.by_year as Record<string, { classification_3tier?: string }>
    for (const yearInfo of Object.values(byYear)) {
      if (yearInfo?.classification_3tier === targetLabel) {
        allowed.add(iso3)
        break
      }
    }
  }
  return allowed
}

/**
 * Pre-interpolate QoL scores for every iso3 across the full year range.
 */
function buildInterpolatedScores(
  scores: Record<string, QolScoresByCountry>
): Map<string, Map<number, number>> {
  const result = new Map<string, Map<number, number>>()

  for (const [, data] of Object.entries(scores)) {
    const iso3 = data.iso3
    if (!iso3) continue

    const known: Array<[number, number]> = []
    for (const [yStr, val] of Object.entries(data.by_year)) {
      if (val != null) known.push([Number(yStr), val])
    }
    if (known.length === 0) continue
    known.sort((a, b) => a[0] - b[0])

    const yearMap = new Map<number, number>()
    const firstYear = known[0][0]
    const firstVal = known[0][1]
    const lastYear = known[known.length - 1][0]
    const lastVal = known[known.length - 1][1]

    let ki = 0
    for (let y = YEAR_MIN; y <= YEAR_MAX; y++) {
      if (y <= firstYear) {
        yearMap.set(y, firstVal)
      } else if (y >= lastYear) {
        yearMap.set(y, lastVal)
      } else {
        while (ki < known.length - 2 && known[ki + 1][0] <= y) ki++
        const [y0, v0] = known[ki]
        const [y1, v1] = known[ki + 1]
        if (y1 === y0) {
          yearMap.set(y, v0)
        } else {
          const t = (y - y0) / (y1 - y0)
          yearMap.set(y, v0 + t * (v1 - v0))
        }
      }
    }

    result.set(iso3, yearMap)
  }

  return result
}

/**
 * Build iso3→score map for a given year from pre-interpolated data,
 * with optional stratum filtering and simulation adjustments.
 */
function buildYearMapFromInterpolated(
  interpolated: Map<string, Map<number, number>>,
  year: number,
  stratumIso3s: Set<string> | null,
  simAdjustments?: Record<string, number>
): Map<string, number> {
  const map = new Map<string, number>()
  for (const [iso3, yearScores] of interpolated) {
    if (stratumIso3s && !stratumIso3s.has(iso3)) continue
    const value = yearScores.get(year)
    if (value != null) {
      const adj = simAdjustments?.[iso3] ?? 0
      const adjusted = value + adj
      map.set(iso3, Math.max(0, Math.min(1, adjusted)))
    }
  }
  return map
}

/**
 * Build region→mean QoL map by averaging country scores within each region.
 */
function buildRegionalYearMap(
  countryYearMap: Map<string, number>
): Map<RegionKey, number> {
  const sums = new Map<RegionKey, { total: number; count: number }>()
  for (const [iso3, score] of countryYearMap) {
    const region = ISO3_TO_REGION[iso3] as RegionKey | undefined
    if (!region) continue
    const entry = sums.get(region) ?? { total: 0, count: 0 }
    entry.total += score
    entry.count += 1
    sums.set(region, entry)
  }
  const result = new Map<RegionKey, number>()
  for (const [region, { total, count }] of sums) {
    result.set(region, total / count)
  }
  return result
}

/** Transition duration for fill color changes (ms). */
const COLOR_TRANSITION_MS = 400

export function WorldMap({
  foreground, qolScores, currentYear, selectedStratum, classificationsCache,
  simAdjustments, onCountrySelect, onCountryHover, selectedCountryIso3,
  mapViewMode, onRegionSelect, selectedRegion, enableZoom = false,
  mobileLayout = false,
}: WorldMapProps) {
  const containerRef = useRef<HTMLDivElement>(null)
  const svgRef = useRef<SVGSVGElement>(null)
  const topoRef = useRef<Topology | null>(null)
  const projectionRef = useRef<d3.GeoProjection | null>(null)
  const pathGenRef = useRef<d3.GeoPath | null>(null)
  const featuresRef = useRef<GeoJSON.Feature[]>([])
  const initializedRef = useRef(false)
  const prevYearRef = useRef<number | null>(null)
  const hoveredRegionKeyRef = useRef<string | null>(null)
  const zoomBehaviorRef = useRef<d3.ZoomBehavior<SVGSVGElement, unknown> | null>(null)
  const currentTransformRef = useRef<d3.ZoomTransform>(d3.zoomIdentity)

  // Stable refs for callbacks
  const onCountrySelectRef = useRef(onCountrySelect)
  onCountrySelectRef.current = onCountrySelect
  const onCountryHoverRef = useRef(onCountryHover)
  onCountryHoverRef.current = onCountryHover
  const onRegionSelectRef = useRef(onRegionSelect)
  onRegionSelectRef.current = onRegionSelect
  const foregroundRef = useRef(foreground)
  foregroundRef.current = foreground
  const selectedCountryIso3Ref = useRef(selectedCountryIso3)
  selectedCountryIso3Ref.current = selectedCountryIso3
  const mapViewModeRef = useRef(mapViewMode)
  mapViewModeRef.current = mapViewMode
  const selectedRegionRef = useRef(selectedRegion)
  selectedRegionRef.current = selectedRegion
  // Build iso3→country name reverse map from qolScores
  const iso3ToName = useMemo(() => {
    const map = new Map<string, string>()
    if (!qolScores) return map
    for (const [countryKey, data] of Object.entries(qolScores)) {
      if (data.iso3) map.set(data.iso3, countryKey)
    }
    return map
  }, [qolScores])

  // Color scale: QoL V1 (HDI-calibrated) — green for high, red for low
  const colorScale = useMemo(
    () => d3.scaleSequential(d3.interpolateRdYlGn).domain([0.3, 0.95]),
    []
  )

  // Pre-interpolate all scores once when data loads
  const interpolated = useMemo(
    () => qolScores ? buildInterpolatedScores(qolScores) : new Map<string, Map<number, number>>(),
    [qolScores]
  )

  // Build stratum filter (null = show all)
  const stratumIso3s = useMemo(
    () => buildStratumIso3s(classificationsCache, selectedStratum),
    [classificationsCache, selectedStratum]
  )

  // Build iso3→value map for current year
  const yearMap = useMemo(
    () => buildYearMapFromInterpolated(interpolated, currentYear, stratumIso3s, simAdjustments),
    [interpolated, currentYear, stratumIso3s, simAdjustments]
  )

  // Build region→mean QoL for regional view mode
  const regionalYearMap = useMemo(
    () => mapViewMode === 'regional' ? buildRegionalYearMap(yearMap) : null,
    [yearMap, mapViewMode]
  )

  /** Resolve fill color for a TopoJSON feature. */
  const fillColor = useCallback((d: GeoJSON.Feature): string => {
    const numId = normalizeId(d.id)
    const iso3 = NUMERIC_TO_ISO3[numId]
    if (!iso3) return '#1a1a2e'

    if (mapViewMode === 'regional' && regionalYearMap) {
      const region = ISO3_TO_REGION[iso3] as RegionKey | undefined
      if (!region) return '#1a1a2e'
      const val = regionalYearMap.get(region)
      return val != null ? colorScale(val) : '#1a1a2e'
    }

    const val = yearMap.get(iso3)
    return val != null ? colorScale(val) : '#1a1a2e'
  }, [yearMap, regionalYearMap, colorScale, mapViewMode])

  /** Apply per-path opacity + selection/region outline to all paths. */
  const applySelectionStyle = useCallback(() => {
    const svg = svgRef.current
    if (!svg || !initializedRef.current) return
    const sel = selectedCountryIso3Ref.current
    const hasSelection = !!sel
    const isFg = foregroundRef.current
    const isRegional = mapViewModeRef.current === 'regional'
    const selRegion = selectedRegionRef.current

    d3.select(svg).select('g.map-content').selectAll<SVGPathElement, GeoJSON.Feature>('path.country')
      .each(function (d) {
        const numId = normalizeId(d.id)
        const iso3 = NUMERIC_TO_ISO3[numId]
        const isSelected = iso3 && iso3 === sel
        const el = d3.select(this)

        const region = iso3 ? ISO3_TO_REGION[iso3] : undefined
        const isRegionSelected = isRegional && selRegion && region === selRegion

        let pathOpacity: number
        if (isFg) {
          if (isRegional && selRegion) {
            pathOpacity = isRegionSelected ? 1 : 0.3
          } else {
            pathOpacity = hasSelection ? (isSelected ? 1 : 0.3) : 1
          }
        } else {
          pathOpacity = hasSelection ? (isSelected ? 0.45 : 0.03) : 0.07
        }

        // In regional mode, borders within a region are thin; between regions are thick
        const defaultStroke = isRegional ? '#444' : '#555'
        const defaultStrokeWidth = isRegional ? 0.15 : 0.3

        el.attr('stroke', isSelected ? '#00E5FF' : (isRegionSelected ? '#00E5FF' : defaultStroke))
          .attr('stroke-width', isSelected ? 2 : (isRegionSelected ? 0.8 : defaultStrokeWidth))
          .style('opacity', pathOpacity)
          .style('filter', (!isFg && isSelected) ? 'saturate(7) brightness(1.15)' : 'none')

        if (isSelected) el.raise()
      })

    // Update region boundary mesh stroke
    d3.select(svg).select('g.map-content').selectAll<SVGPathElement, unknown>('path.region-boundary')
      .attr('stroke', '#333')
      .attr('stroke-width', isRegional ? 1.5 : 0)
      .attr('stroke-opacity', isRegional && isFg ? 0.6 : 0)
  }, [])

  // Load TopoJSON once
  useEffect(() => {
    if (topoRef.current) return
    fetch(`${import.meta.env.BASE_URL}data/world-110m.json`)
      .then(res => res.json())
      .then((topo: Topology) => {
        topoRef.current = topo
        const geom = topo.objects.countries as GeometryCollection
        featuresRef.current = (topojson.feature(topo, geom) as GeoJSON.FeatureCollection).features
        renderMap()
      })
      .catch(err => console.warn('Failed to load world map:', err))
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [])

  const renderMap = useCallback(() => {
    const svg = svgRef.current
    const container = containerRef.current
    if (!svg || !container || featuresRef.current.length === 0) return

    const { width, height } = container.getBoundingClientRect()
    if (width === 0 || height === 0) return

    svg.setAttribute('width', String(width))
    svg.setAttribute('height', String(height))

    const projection = d3.geoNaturalEarth1()
    // On mobile, exclude Antarctica (id "010") to reclaim vertical space
    const features = mobileLayout
      ? featuresRef.current.filter(f => f.id !== '010')
      : featuresRef.current

    if (mobileLayout) {
      // Use filtered features for initial fit, then manually scale up and re-center on Africa
      projection.fitSize([width, height], { type: 'FeatureCollection', features })
      const baseScale = projection.scale()
      const scaleFactor = 1.15
      projection.scale(baseScale * scaleFactor)
      // Center on Africa (lon ~20, lat ~5)
      projection.translate([width / 2, height / 2])
      projection.center([20, 5])
    } else {
      projection.fitSize([width, height], { type: 'FeatureCollection', features })
    }
    projectionRef.current = projection

    const pathGen = d3.geoPath().projection(projection)
    pathGenRef.current = pathGen

    const sel = d3.select(svg)
    sel.selectAll('*').remove()

    // Wrap all content in a <g> for zoom transform
    const contentG = sel.append('g').attr('class', 'map-content')
    // Restore persisted transform if zoom is active
    if (enableZoom) {
      contentG.attr('transform', currentTransformRef.current.toString())
    }

    // Country paths
    contentG.selectAll('path.country')
      .data(features)
      .enter()
      .append('path')
      .attr('class', 'country')
      .attr('d', d => pathGen(d) || '')
      .attr('fill', fillColor)
      .attr('stroke', '#555')
      .attr('stroke-width', 0.3)
      .style('cursor', 'pointer')
      .on('mouseover', function (_event: MouseEvent, d: GeoJSON.Feature) {
        if (!foregroundRef.current) return
        // Regional hover is handled at SVG level (mousemove below) — skip per-path
        if (mapViewModeRef.current === 'regional') return

        d3.select(this).attr('stroke', '#fff').attr('stroke-width', 1.5).raise()

        const numId = normalizeId(d.id)
        const iso3 = NUMERIC_TO_ISO3[numId]
        const name = iso3 ? iso3ToName.get(iso3) : undefined
        if (name) onCountryHoverRef.current?.(name)
      })
      .on('mouseout', function (_event: MouseEvent, d: GeoJSON.Feature) {
        if (!foregroundRef.current) return
        if (mapViewModeRef.current === 'regional') return

        onCountryHoverRef.current?.(null)
        const numId = normalizeId(d.id)
        const iso3 = NUMERIC_TO_ISO3[numId]
        const isSelected = iso3 && iso3 === selectedCountryIso3Ref.current
        d3.select(this)
          .attr('stroke', isSelected ? '#00E5FF' : '#555')
          .attr('stroke-width', isSelected ? 2 : 0.3)
      })
      .on('click', function (_event: MouseEvent, d: GeoJSON.Feature) {
        if (!foregroundRef.current) return
        const numId = normalizeId(d.id)
        const iso3 = NUMERIC_TO_ISO3[numId]
        if (!iso3) return

        if (mapViewModeRef.current === 'regional') {
          const region = ISO3_TO_REGION[iso3]
          if (region) onRegionSelectRef.current?.(region)
        } else {
          const name = iso3ToName.get(iso3)
          if (name) onCountrySelectRef.current?.(name)
        }
      })
      // Touch tap detection: D3 zoom swallows click on first touch, so detect taps manually
      .on('touchstart', function (event: TouchEvent) {
        if (event.touches.length !== 1) return
        const t = event.touches[0]
        ;(this as SVGPathElement).dataset.tapX = String(t.clientX)
        ;(this as SVGPathElement).dataset.tapY = String(t.clientY)
        ;(this as SVGPathElement).dataset.tapTime = String(Date.now())
      }, { passive: true })
      .on('touchend', function (event: TouchEvent, d: GeoJSON.Feature) {
        const el = this as SVGPathElement
        const startX = Number(el.dataset.tapX)
        const startY = Number(el.dataset.tapY)
        const startTime = Number(el.dataset.tapTime)
        if (!startTime) return

        const ct = event.changedTouches[0]
        const dx = ct.clientX - startX
        const dy = ct.clientY - startY
        const dt = Date.now() - startTime

        // Only count as tap if short duration and minimal movement
        if (dt < 300 && Math.abs(dx) < 10 && Math.abs(dy) < 10) {
          if (!foregroundRef.current) return
          const numId = normalizeId(d.id)
          const iso3 = NUMERIC_TO_ISO3[numId]
          if (!iso3) return

          if (mapViewModeRef.current === 'regional') {
            const region = ISO3_TO_REGION[iso3]
            if (region) onRegionSelectRef.current?.(region)
          } else {
            const name = iso3ToName.get(iso3)
            if (name) onCountrySelectRef.current?.(name)
          }
        }
        // Clean up
        delete el.dataset.tapX
        delete el.dataset.tapY
        delete el.dataset.tapTime
      }, { passive: true })

    // Region boundary mesh (rendered on top, no fill, just strokes)
    const topo = topoRef.current
    if (topo) {
      const geom = topo.objects.countries as GeometryCollection
      const regionMesh = topojson.mesh(topo, geom, (a, b) => {
        const rA = featureRegion(a as unknown as GeoJSON.Feature)
        const rB = featureRegion(b as unknown as GeoJSON.Feature)
        return a !== b && rA !== rB
      })
      contentG.append('path')
        .attr('class', 'region-boundary')
        .datum(regionMesh)
        .attr('d', pathGen)
        .attr('fill', 'none')
        .attr('stroke', '#333')
        .attr('stroke-width', 0)
        .attr('stroke-opacity', 0)
        .style('pointer-events', 'none')
    }

    initializedRef.current = true
    applySelectionStyle()
  }, [fillColor, iso3ToName, applySelectionStyle, mobileLayout, enableZoom])

  // Render on mount and resize
  useEffect(() => {
    renderMap()

    const container = containerRef.current
    if (!container) return

    const ro = new ResizeObserver(() => renderMap())
    ro.observe(container)
    return () => ro.disconnect()
  }, [renderMap])

  // Attach/detach d3.zoom when enableZoom changes
  useEffect(() => {
    const svg = svgRef.current
    if (!svg) return

    const svgSel = d3.select<SVGSVGElement, unknown>(svg)

    if (enableZoom) {
      const zoom = d3.zoom<SVGSVGElement, unknown>()
        .scaleExtent([1, 5])
        .on('zoom', (event: d3.D3ZoomEvent<SVGSVGElement, unknown>) => {
          currentTransformRef.current = event.transform
          svgSel.select('g.map-content').attr('transform', event.transform.toString())
        })

      zoomBehaviorRef.current = zoom
      svgSel.call(zoom)
      // Restore persisted transform
      if (currentTransformRef.current !== d3.zoomIdentity) {
        svgSel.call(zoom.transform, currentTransformRef.current)
      }
    } else {
      // Remove zoom behavior, reset transform
      svgSel.on('.zoom', null)
      zoomBehaviorRef.current = null
      currentTransformRef.current = d3.zoomIdentity
      svgSel.select('g.map-content').attr('transform', null)
    }

    return () => {
      svgSel.on('.zoom', null)
    }
  }, [enableZoom])

  // Reset zoom to identity when crossing the 1024px threshold (enableZoom toggles)
  const prevEnableZoomRef = useRef(enableZoom)
  useEffect(() => {
    if (prevEnableZoomRef.current && !enableZoom) {
      currentTransformRef.current = d3.zoomIdentity
    }
    prevEnableZoomRef.current = enableZoom
  }, [enableZoom])

  // Re-apply selection style when selection, foreground, or view mode changes
  useEffect(() => {
    applySelectionStyle()
  }, [selectedCountryIso3, selectedRegion, foreground, mapViewMode, applySelectionStyle])

  // Smooth color transition when year/sim data changes
  useEffect(() => {
    const svg = svgRef.current
    if (!svg || !initializedRef.current) return

    const isFirstPaint = prevYearRef.current === null
    prevYearRef.current = currentYear

    const paths = d3.select(svg).select('g.map-content').selectAll<SVGPathElement, GeoJSON.Feature>('path.country')

    if (isFirstPaint) {
      paths.attr('fill', fillColor)
    } else {
      paths
        .transition()
        .duration(COLOR_TRANSITION_MS)
        .attr('fill', fillColor)
    }
  }, [fillColor, currentYear])

  // Region label tooltip + regional hover highlight (SVG-level to avoid per-path flicker)
  const hoveredRegionRef = useRef<string | null>(null)
  const tooltipRef = useRef<HTMLDivElement>(null)

  useEffect(() => {
    if (mapViewMode !== 'regional' || !foreground) {
      // Clear any lingering hover state when leaving regional mode
      if (hoveredRegionKeyRef.current) {
        hoveredRegionKeyRef.current = null
        applySelectionStyle()
      }
      return
    }

    const svg = svgRef.current
    if (!svg) return

    const handleMove = (e: MouseEvent) => {
      const rect = svg.getBoundingClientRect()
      const x = e.clientX - rect.left
      const y = e.clientY - rect.top
      const proj = projectionRef.current
      if (!proj) return

      const inverted = proj.invert?.([x, y])
      if (!inverted) {
        // Mouse over ocean/outside map
        if (hoveredRegionKeyRef.current) {
          hoveredRegionKeyRef.current = null
          hoveredRegionRef.current = null
          applySelectionStyle()
          onCountryHoverRef.current?.(null)
        }
        if (tooltipRef.current) tooltipRef.current.style.opacity = '0'
        return
      }

      // Hit-test: find which feature the mouse is over
      let foundRegion: string | null = null
      let foundName: string | undefined
      for (const feat of featuresRef.current) {
        if (pathGenRef.current && d3.geoContains(feat, inverted)) {
          const numId = normalizeId(feat.id)
          const iso3 = NUMERIC_TO_ISO3[numId]
          if (iso3) {
            foundRegion = ISO3_TO_REGION[iso3] ?? null
            foundName = iso3ToName.get(iso3)
          }
          break
        }
      }

      // Update hover name for sidebar
      if (foundName) {
        onCountryHoverRef.current?.(foundName)
      } else if (hoveredRegionKeyRef.current) {
        onCountryHoverRef.current?.(null)
      }

      // Tooltip
      hoveredRegionRef.current = foundRegion
      if (tooltipRef.current && foundRegion) {
        const displayName = REGION_DISPLAY_NAMES[foundRegion as RegionKey] ?? foundRegion
        tooltipRef.current.textContent = displayName
        tooltipRef.current.style.opacity = '1'
        tooltipRef.current.style.left = `${e.clientX - rect.left + 12}px`
        tooltipRef.current.style.top = `${e.clientY - rect.top - 8}px`
      } else if (tooltipRef.current) {
        tooltipRef.current.style.opacity = '0'
      }

      // Region highlight: only update when region changes
      if (foundRegion !== hoveredRegionKeyRef.current) {
        hoveredRegionKeyRef.current = foundRegion
        if (foundRegion) {
          d3.select(svg).select('g.map-content').selectAll<SVGPathElement, GeoJSON.Feature>('path.country')
            .each(function (fd) {
              const fIso3 = NUMERIC_TO_ISO3[normalizeId(fd.id)]
              const fRegion = fIso3 ? ISO3_TO_REGION[fIso3] : undefined
              const inHovered = fRegion === foundRegion
              d3.select(this)
                .style('opacity', inHovered ? 1 : 0.35)
                .attr('stroke', inHovered ? '#fff' : '#444')
                .attr('stroke-width', inHovered ? 0.6 : 0.15)
            })
        } else {
          applySelectionStyle()
        }
      }
    }

    const handleLeave = () => {
      hoveredRegionKeyRef.current = null
      hoveredRegionRef.current = null
      applySelectionStyle()
      onCountryHoverRef.current?.(null)
      if (tooltipRef.current) tooltipRef.current.style.opacity = '0'
    }

    svg.addEventListener('mousemove', handleMove)
    svg.addEventListener('mouseleave', handleLeave)
    return () => {
      svg.removeEventListener('mousemove', handleMove)
      svg.removeEventListener('mouseleave', handleLeave)
    }
  }, [mapViewMode, foreground, iso3ToName, applySelectionStyle])

  return (
    <div
      ref={containerRef}
      style={{
        position: 'absolute',
        top: mobileLayout ? '30%' : 0,
        left: 0,
        width: '100%',
        height: mobileLayout ? '70%' : '100%',
        zIndex: foreground ? 50 : 0,
        pointerEvents: foreground ? 'auto' : 'none',
        opacity: foreground ? 1 : 0.45,
        filter: foreground ? 'none' : 'saturate(0.15) brightness(0.9)',
        transition: 'opacity 0.5s cubic-bezier(0.4, 0, 0.2, 1), filter 0.5s cubic-bezier(0.4, 0, 0.2, 1)',
        willChange: 'opacity, filter',
        overflow: mobileLayout ? 'visible' : undefined,
      }}
    >
      <svg ref={svgRef} style={{ width: '100%', height: '100%' }} />

      {/* Region tooltip (regional mode only) */}
      {mapViewMode === 'regional' && foreground && (
        <div
          ref={tooltipRef}
          style={{
            position: 'absolute',
            pointerEvents: 'none',
            background: 'rgba(0,0,0,0.75)',
            color: '#fff',
            padding: '3px 8px',
            borderRadius: 4,
            fontSize: 11,
            fontWeight: 500,
            opacity: 0,
            transition: 'opacity 0.1s ease',
            whiteSpace: 'nowrap',
            zIndex: 70,
          }}
        />
      )}
    </div>
  )
}

export default WorldMap
