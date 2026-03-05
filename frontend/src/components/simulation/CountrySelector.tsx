/**
 * CountrySelector - Enhanced searchable input for selecting a country
 *
 * Features:
 * - Country flags (emoji from ISO codes)
 * - Region grouping (World Bank regions)
 * - Development stage badges (Developing/Emerging/Advanced)
 * - Direct search input with abbreviation support
 * - Coverage indicator (% of edges with data)
 * - Loading states
 * - Clear selection button
 */

import { useState, useEffect, useRef, useMemo } from 'react'
import { useSimulationStore } from '../../stores/simulationStore'
import type { Country } from '../../services/api'
import { type RegionKey, REGION_DISPLAY_NAMES, REGION_ICONS, ISO3_TO_REGION, REGION_KEYS } from '../../constants/regions'

// ============================================
// Country Metadata (ISO codes, regions)
// ============================================

// ISO 3166-1 alpha-3 to alpha-2 mapping for flag emojis
const ISO3_TO_ISO2: Record<string, string> = {
  AFG: 'AF', ALB: 'AL', DZA: 'DZ', AND: 'AD', AGO: 'AO', ATG: 'AG', ARG: 'AR', ARM: 'AM', AUS: 'AU', AUT: 'AT',
  AZE: 'AZ', BHS: 'BS', BHR: 'BH', BGD: 'BD', BRB: 'BB', BLR: 'BY', BEL: 'BE', BLZ: 'BZ', BEN: 'BJ', BTN: 'BT',
  BOL: 'BO', BIH: 'BA', BWA: 'BW', BRA: 'BR', BRN: 'BN', BGR: 'BG', BFA: 'BF', BDI: 'BI', CPV: 'CV', KHM: 'KH',
  CMR: 'CM', CAN: 'CA', CAF: 'CF', TCD: 'TD', CHL: 'CL', CHN: 'CN', COL: 'CO', COM: 'KM', COG: 'CG', COD: 'CD',
  CRI: 'CR', CIV: 'CI', HRV: 'HR', CUB: 'CU', CYP: 'CY', CZE: 'CZ', DNK: 'DK', DJI: 'DJ', DMA: 'DM', DOM: 'DO',
  ECU: 'EC', EGY: 'EG', SLV: 'SV', GNQ: 'GQ', ERI: 'ER', EST: 'EE', SWZ: 'SZ', ETH: 'ET', FJI: 'FJ', FIN: 'FI',
  FRA: 'FR', GAB: 'GA', GMB: 'GM', GEO: 'GE', DEU: 'DE', GHA: 'GH', GRC: 'GR', GRD: 'GD', GTM: 'GT', GIN: 'GN',
  GNB: 'GW', GUY: 'GY', HTI: 'HT', HND: 'HN', HUN: 'HU', ISL: 'IS', IND: 'IN', IDN: 'ID', IRN: 'IR', IRQ: 'IQ',
  IRL: 'IE', ISR: 'IL', ITA: 'IT', JAM: 'JM', JPN: 'JP', JOR: 'JO', KAZ: 'KZ', KEN: 'KE', KIR: 'KI', PRK: 'KP',
  KOR: 'KR', KWT: 'KW', KGZ: 'KG', LAO: 'LA', LVA: 'LV', LBN: 'LB', LSO: 'LS', LBR: 'LR', LBY: 'LY', LIE: 'LI',
  LTU: 'LT', LUX: 'LU', MDG: 'MG', MWI: 'MW', MYS: 'MY', MDV: 'MV', MLI: 'ML', MLT: 'MT', MHL: 'MH', MRT: 'MR',
  MUS: 'MU', MEX: 'MX', FSM: 'FM', MDA: 'MD', MCO: 'MC', MNG: 'MN', MNE: 'ME', MAR: 'MA', MOZ: 'MZ', MMR: 'MM',
  NAM: 'NA', NRU: 'NR', NPL: 'NP', NLD: 'NL', NZL: 'NZ', NIC: 'NI', NER: 'NE', NGA: 'NG', MKD: 'MK', NOR: 'NO',
  OMN: 'OM', PAK: 'PK', PLW: 'PW', PAN: 'PA', PNG: 'PG', PRY: 'PY', PER: 'PE', PHL: 'PH', POL: 'PL', PRT: 'PT',
  QAT: 'QA', ROU: 'RO', RUS: 'RU', RWA: 'RW', KNA: 'KN', LCA: 'LC', VCT: 'VC', WSM: 'WS', SMR: 'SM', STP: 'ST',
  SAU: 'SA', SEN: 'SN', SRB: 'RS', SYC: 'SC', SLE: 'SL', SGP: 'SG', SVK: 'SK', SVN: 'SI', SLB: 'SB', SOM: 'SO',
  ZAF: 'ZA', SSD: 'SS', ESP: 'ES', LKA: 'LK', SDN: 'SD', SUR: 'SR', SWE: 'SE', CHE: 'CH', SYR: 'SY', TWN: 'TW',
  TJK: 'TJ', TZA: 'TZ', THA: 'TH', TLS: 'TL', TGO: 'TG', TON: 'TO', TTO: 'TT', TUN: 'TN', TUR: 'TR', TKM: 'TM',
  TUV: 'TV', UGA: 'UG', UKR: 'UA', ARE: 'AE', GBR: 'GB', USA: 'US', URY: 'UY', UZB: 'UZ', VUT: 'VU', VEN: 'VE',
  VNM: 'VN', YEM: 'YE', ZMB: 'ZM', ZWE: 'ZW', PSE: 'PS', XKX: 'XK', HKG: 'HK', MAC: 'MO', PRI: 'PR'
}

// World Bank region mapping
const COUNTRY_REGIONS: Record<string, string> = {
  // East Asia & Pacific
  'Australia': 'East Asia & Pacific', 'Brunei Darussalam': 'East Asia & Pacific', 'Cambodia': 'East Asia & Pacific',
  'China': 'East Asia & Pacific', 'Fiji': 'East Asia & Pacific', 'Hong Kong SAR, China': 'East Asia & Pacific',
  'Indonesia': 'East Asia & Pacific', 'Japan': 'East Asia & Pacific', 'Kiribati': 'East Asia & Pacific',
  "Korea, Dem. People's Rep.": 'East Asia & Pacific', 'Korea, Rep.': 'East Asia & Pacific',
  "Lao PDR": 'East Asia & Pacific', 'Macao SAR, China': 'East Asia & Pacific', 'Malaysia': 'East Asia & Pacific',
  'Marshall Islands': 'East Asia & Pacific', 'Micronesia, Fed. Sts.': 'East Asia & Pacific', 'Mongolia': 'East Asia & Pacific',
  'Myanmar': 'East Asia & Pacific', 'Nauru': 'East Asia & Pacific', 'New Zealand': 'East Asia & Pacific',
  'Palau': 'East Asia & Pacific', 'Papua New Guinea': 'East Asia & Pacific', 'Philippines': 'East Asia & Pacific',
  'Samoa': 'East Asia & Pacific', 'Singapore': 'East Asia & Pacific', 'Solomon Islands': 'East Asia & Pacific',
  'Thailand': 'East Asia & Pacific', 'Timor-Leste': 'East Asia & Pacific', 'Tonga': 'East Asia & Pacific',
  'Tuvalu': 'East Asia & Pacific', 'Vanuatu': 'East Asia & Pacific', 'Vietnam': 'East Asia & Pacific',
  'Taiwan, China': 'East Asia & Pacific',

  // Europe & Central Asia
  'Albania': 'Europe & Central Asia', 'Andorra': 'Europe & Central Asia', 'Armenia': 'Europe & Central Asia',
  'Austria': 'Europe & Central Asia', 'Azerbaijan': 'Europe & Central Asia', 'Belarus': 'Europe & Central Asia',
  'Belgium': 'Europe & Central Asia', 'Bosnia and Herzegovina': 'Europe & Central Asia', 'Bulgaria': 'Europe & Central Asia',
  'Croatia': 'Europe & Central Asia', 'Cyprus': 'Europe & Central Asia', 'Czech Republic': 'Europe & Central Asia',
  'Denmark': 'Europe & Central Asia', 'Estonia': 'Europe & Central Asia', 'Finland': 'Europe & Central Asia',
  'France': 'Europe & Central Asia', 'Georgia': 'Europe & Central Asia', 'Germany': 'Europe & Central Asia',
  'Greece': 'Europe & Central Asia', 'Hungary': 'Europe & Central Asia', 'Iceland': 'Europe & Central Asia',
  'Ireland': 'Europe & Central Asia', 'Italy': 'Europe & Central Asia', 'Kazakhstan': 'Europe & Central Asia',
  'Kosovo': 'Europe & Central Asia', 'Kyrgyz Republic': 'Europe & Central Asia', 'Latvia': 'Europe & Central Asia',
  'Liechtenstein': 'Europe & Central Asia', 'Lithuania': 'Europe & Central Asia', 'Luxembourg': 'Europe & Central Asia',
  'Moldova': 'Europe & Central Asia', 'Monaco': 'Europe & Central Asia', 'Montenegro': 'Europe & Central Asia',
  'Netherlands': 'Europe & Central Asia', 'North Macedonia': 'Europe & Central Asia', 'Norway': 'Europe & Central Asia',
  'Poland': 'Europe & Central Asia', 'Portugal': 'Europe & Central Asia', 'Romania': 'Europe & Central Asia',
  'Russian Federation': 'Europe & Central Asia', 'San Marino': 'Europe & Central Asia', 'Serbia': 'Europe & Central Asia',
  'Slovak Republic': 'Europe & Central Asia', 'Slovenia': 'Europe & Central Asia', 'Spain': 'Europe & Central Asia',
  'Sweden': 'Europe & Central Asia', 'Switzerland': 'Europe & Central Asia', 'Tajikistan': 'Europe & Central Asia',
  'Turkey': 'Europe & Central Asia', 'Turkmenistan': 'Europe & Central Asia', 'Ukraine': 'Europe & Central Asia',
  'United Kingdom': 'Europe & Central Asia', 'Uzbekistan': 'Europe & Central Asia',

  // Latin America & Caribbean
  'Antigua and Barbuda': 'Latin America & Caribbean', 'Argentina': 'Latin America & Caribbean',
  'Bahamas, The': 'Latin America & Caribbean', 'Barbados': 'Latin America & Caribbean', 'Belize': 'Latin America & Caribbean',
  'Bolivia': 'Latin America & Caribbean', 'Brazil': 'Latin America & Caribbean', 'Chile': 'Latin America & Caribbean',
  'Colombia': 'Latin America & Caribbean', 'Costa Rica': 'Latin America & Caribbean', 'Cuba': 'Latin America & Caribbean',
  'Dominica': 'Latin America & Caribbean', 'Dominican Republic': 'Latin America & Caribbean', 'Ecuador': 'Latin America & Caribbean',
  'El Salvador': 'Latin America & Caribbean', 'Grenada': 'Latin America & Caribbean', 'Guatemala': 'Latin America & Caribbean',
  'Guyana': 'Latin America & Caribbean', 'Haiti': 'Latin America & Caribbean', 'Honduras': 'Latin America & Caribbean',
  'Jamaica': 'Latin America & Caribbean', 'Mexico': 'Latin America & Caribbean', 'Nicaragua': 'Latin America & Caribbean',
  'Panama': 'Latin America & Caribbean', 'Paraguay': 'Latin America & Caribbean', 'Peru': 'Latin America & Caribbean',
  'Puerto Rico': 'Latin America & Caribbean', 'St. Kitts and Nevis': 'Latin America & Caribbean',
  'St. Lucia': 'Latin America & Caribbean', 'St. Vincent and the Grenadines': 'Latin America & Caribbean',
  'Suriname': 'Latin America & Caribbean', 'Trinidad and Tobago': 'Latin America & Caribbean',
  'Uruguay': 'Latin America & Caribbean', 'Venezuela, RB': 'Latin America & Caribbean',

  // Middle East & North Africa
  'Algeria': 'Middle East & North Africa', 'Bahrain': 'Middle East & North Africa', 'Djibouti': 'Middle East & North Africa',
  'Egypt, Arab Rep.': 'Middle East & North Africa', 'Iran, Islamic Rep.': 'Middle East & North Africa',
  'Iraq': 'Middle East & North Africa', 'Israel': 'Middle East & North Africa', 'Jordan': 'Middle East & North Africa',
  'Kuwait': 'Middle East & North Africa', 'Lebanon': 'Middle East & North Africa', 'Libya': 'Middle East & North Africa',
  'Malta': 'Middle East & North Africa', 'Morocco': 'Middle East & North Africa', 'Oman': 'Middle East & North Africa',
  'Qatar': 'Middle East & North Africa', 'Saudi Arabia': 'Middle East & North Africa',
  'Syrian Arab Republic': 'Middle East & North Africa', 'Tunisia': 'Middle East & North Africa',
  'United Arab Emirates': 'Middle East & North Africa', 'West Bank and Gaza': 'Middle East & North Africa',
  'Yemen, Rep.': 'Middle East & North Africa',

  // North America
  'Canada': 'North America', 'United States': 'North America',

  // South Asia
  'Afghanistan': 'South Asia', 'Bangladesh': 'South Asia', 'Bhutan': 'South Asia', 'India': 'South Asia',
  'Maldives': 'South Asia', 'Nepal': 'South Asia', 'Pakistan': 'South Asia', 'Sri Lanka': 'South Asia',

  // Sub-Saharan Africa
  'Angola': 'Sub-Saharan Africa', 'Benin': 'Sub-Saharan Africa', 'Botswana': 'Sub-Saharan Africa',
  'Burkina Faso': 'Sub-Saharan Africa', 'Burundi': 'Sub-Saharan Africa', 'Cabo Verde': 'Sub-Saharan Africa',
  'Cameroon': 'Sub-Saharan Africa', 'Central African Republic': 'Sub-Saharan Africa', 'Chad': 'Sub-Saharan Africa',
  'Comoros': 'Sub-Saharan Africa', 'Congo, Dem. Rep.': 'Sub-Saharan Africa', 'Congo, Rep.': 'Sub-Saharan Africa',
  "Cote d'Ivoire": 'Sub-Saharan Africa', 'Equatorial Guinea': 'Sub-Saharan Africa', 'Eritrea': 'Sub-Saharan Africa',
  'Eswatini': 'Sub-Saharan Africa', 'Ethiopia': 'Sub-Saharan Africa', 'Gabon': 'Sub-Saharan Africa',
  'Gambia, The': 'Sub-Saharan Africa', 'Ghana': 'Sub-Saharan Africa', 'Guinea': 'Sub-Saharan Africa',
  'Guinea-Bissau': 'Sub-Saharan Africa', 'Kenya': 'Sub-Saharan Africa', 'Lesotho': 'Sub-Saharan Africa',
  'Liberia': 'Sub-Saharan Africa', 'Madagascar': 'Sub-Saharan Africa', 'Malawi': 'Sub-Saharan Africa',
  'Mali': 'Sub-Saharan Africa', 'Mauritania': 'Sub-Saharan Africa', 'Mauritius': 'Sub-Saharan Africa',
  'Mozambique': 'Sub-Saharan Africa', 'Namibia': 'Sub-Saharan Africa', 'Niger': 'Sub-Saharan Africa',
  'Nigeria': 'Sub-Saharan Africa', 'Rwanda': 'Sub-Saharan Africa', 'Sao Tome and Principe': 'Sub-Saharan Africa',
  'Senegal': 'Sub-Saharan Africa', 'Seychelles': 'Sub-Saharan Africa', 'Sierra Leone': 'Sub-Saharan Africa',
  'Somalia': 'Sub-Saharan Africa', 'South Africa': 'Sub-Saharan Africa', 'South Sudan': 'Sub-Saharan Africa',
  'Sudan': 'Sub-Saharan Africa', 'Tanzania': 'Sub-Saharan Africa', 'Togo': 'Sub-Saharan Africa',
  'Uganda': 'Sub-Saharan Africa', 'Zambia': 'Sub-Saharan Africa', 'Zimbabwe': 'Sub-Saharan Africa'
}

// Common abbreviations/aliases for search
const COUNTRY_ALIASES: Record<string, string[]> = {
  'United States': ['USA', 'US', 'America'],
  'United Kingdom': ['UK', 'Britain', 'England'],
  'Korea, Rep.': ['South Korea', 'Korea'],
  "Korea, Dem. People's Rep.": ['North Korea', 'DPRK'],
  'Russian Federation': ['Russia'],
  'Iran, Islamic Rep.': ['Iran'],
  'Egypt, Arab Rep.': ['Egypt'],
  'Venezuela, RB': ['Venezuela'],
  'Congo, Dem. Rep.': ['DRC', 'Democratic Republic of Congo'],
  'Congo, Rep.': ['Republic of Congo'],
  "Cote d'Ivoire": ['Ivory Coast'],
  'Lao PDR': ['Laos'],
  'Syrian Arab Republic': ['Syria'],
  'Yemen, Rep.': ['Yemen'],
  'Gambia, The': ['Gambia'],
  'Bahamas, The': ['Bahamas'],
  'Czech Republic': ['Czechia'],
  'Slovak Republic': ['Slovakia'],
  'Kyrgyz Republic': ['Kyrgyzstan'],
  'Cabo Verde': ['Cape Verde'],
  'Eswatini': ['Swaziland'],
  'North Macedonia': ['Macedonia'],
  'Myanmar': ['Burma'],
  'Timor-Leste': ['East Timor'],
  'United Arab Emirates': ['UAE'],
  'Saudi Arabia': ['KSA'],
  'West Bank and Gaza': ['Palestine', 'Palestinian Territories'],
  'Hong Kong SAR, China': ['Hong Kong', 'HK'],
  'Macao SAR, China': ['Macao', 'Macau'],
  'Taiwan, China': ['Taiwan'],
  'Bosnia and Herzegovina': ['Bosnia'],
  'Trinidad and Tobago': ['Trinidad'],
  'St. Kitts and Nevis': ['Saint Kitts'],
  'St. Lucia': ['Saint Lucia'],
  'St. Vincent and the Grenadines': ['Saint Vincent'],
  'Sao Tome and Principe': ['Sao Tome'],
  'Central African Republic': ['CAR']
}

// Convert ISO alpha-2 to flag emoji
function getCountryFlag(_countryName: string, iso3?: string): string {
  const iso2 = iso3 ? ISO3_TO_ISO2[iso3] : null
  if (!iso2) return '🌍'
  // Convert to regional indicator symbols (flag emoji)
  return String.fromCodePoint(...[...iso2].map(c => 0x1F1E6 + c.charCodeAt(0) - 65))
}

// Get stratum color
function getStratumColor(stratum: string | null): string {
  switch (stratum?.toLowerCase()) {
    case 'developing': return '#EF5350'
    case 'emerging': return '#FFA726'
    case 'advanced': return '#66BB6A'
    default: return '#888'
  }
}

// Get stratum badge style
function getStratumBadgeStyle(stratum: string | null): React.CSSProperties {
  const color = getStratumColor(stratum)
  return {
    display: 'inline-block',
    padding: '2px 6px',
    borderRadius: 4,
    fontSize: 10,
    fontWeight: 600,
    color: 'white',
    background: color,
    textTransform: 'capitalize' as const
  }
}


// ============================================
// Component
// ============================================

interface CountryWithMeta extends Country {
  flag: string
  region: string
  stratum: string | null
  iso3: string | null
}

/**
 * Enhanced searchable country selector
 */
export function CountrySelector() {
  const {
    countries,
    countriesLoading,
    countriesLoadFailed,
    selectedCountry,
    countryLoading,
    loadCountries,
    setCountry,
    clearCountry,
    classificationsCache,
    loadAllClassifications,
    historicalTimeline,
    currentYearIndex,
    selectedRegion,
    setSelectedRegion
  } = useSimulationStore()

  const mapHoveredCountry = useSimulationStore(s => s.mapHoveredCountry)
  const mapForeground = useSimulationStore(s => s.mapForeground)

  const [searchTerm, setSearchTerm] = useState('')
  const [isFocused, setIsFocused] = useState(false)
  const [activeIndex, setActiveIndex] = useState(-1)
  const listboxId = 'country-selector-listbox'
  const containerRef = useRef<HTMLDivElement>(null)
  const inputRef = useRef<HTMLInputElement>(null)
  const listRef = useRef<HTMLDivElement>(null)
  const hoverTimeoutRef = useRef<ReturnType<typeof setTimeout> | null>(null)
  const mapHoverCloseRef = useRef<ReturnType<typeof setTimeout> | null>(null)
  const firstMapHoverRef = useRef(true)
  const mapSelectLockRef = useRef(false) // Suppress hover-open after map click

  // Load countries and classifications on mount (with failure guard to prevent infinite retry)
  useEffect(() => {
    if (countries.length === 0 && !countriesLoading && !countriesLoadFailed) {
      loadCountries()
    }
    loadAllClassifications()
  }, [countries.length, countriesLoading, countriesLoadFailed, loadCountries, loadAllClassifications])

  // Reset flags when map foreground toggles
  useEffect(() => {
    if (mapForeground) {
      firstMapHoverRef.current = true
      mapSelectLockRef.current = false
    } else {
      // Map went to background — close dropdown, clear lock
      setIsFocused(false)
      mapSelectLockRef.current = false
    }
  }, [mapForeground])

  // React to map hover: auto-open dropdown and scroll to hovered country
  useEffect(() => {
    // After a map click selection, suppress hover from reopening the dropdown
    if (mapSelectLockRef.current) return

    if (mapHoveredCountry) {
      if (mapHoverCloseRef.current) {
        clearTimeout(mapHoverCloseRef.current)
        mapHoverCloseRef.current = null
      }
      setIsFocused(true)
      const scrollSmooth = firstMapHoverRef.current
      if (scrollSmooth) firstMapHoverRef.current = false
      // Scroll hovered country to center of the dropdown
      requestAnimationFrame(() => {
        const listEl = listRef.current
        if (!listEl) return
        const items = listEl.querySelectorAll<HTMLElement>('.country-option')
        for (const item of items) {
          if (item.textContent?.includes(mapHoveredCountry)) {
            const targetTop = item.offsetTop - listEl.offsetTop - (listEl.clientHeight / 2) + (item.offsetHeight / 2)
            listEl.scrollTo({ top: targetTop, behavior: scrollSmooth ? 'smooth' : 'instant' })
            break
          }
        }
      })
    } else {
      // Close after delay (same pattern as mouse leave)
      if (mapHoverCloseRef.current) clearTimeout(mapHoverCloseRef.current)
      mapHoverCloseRef.current = setTimeout(() => {
        setIsFocused(false)
      }, 900)
    }
  }, [mapHoveredCountry])

  // When a country is selected while map is foregrounded, lock out hover-open
  useEffect(() => {
    if (selectedCountry && mapForeground) {
      mapSelectLockRef.current = true
      setIsFocused(false)
      if (mapHoverCloseRef.current) {
        clearTimeout(mapHoverCloseRef.current)
        mapHoverCloseRef.current = null
      }
    }
  }, [selectedCountry, mapForeground])

  // When country is cleared, unlock so hover works again
  useEffect(() => {
    if (!selectedCountry) {
      mapSelectLockRef.current = false
    }
  }, [selectedCountry])

  useEffect(() => {
    return () => {
      if (mapHoverCloseRef.current) clearTimeout(mapHoverCloseRef.current)
    }
  }, [])

  // Get current year for classification lookup
  const currentYear = historicalTimeline?.years?.[currentYearIndex] || 2020

  // Enrich countries with metadata (flags, regions, strata)
  const enrichedCountries = useMemo((): CountryWithMeta[] => {
    return countries.map(country => {
      // Get classification data for this country
      // eslint-disable-next-line @typescript-eslint/no-explicit-any
      const countryClassification = classificationsCache?.classifications?.[country.name] as any
      const iso3 = countryClassification?.iso3 || null
      const yearData = countryClassification?.by_year?.[String(currentYear)]
      const stratum = yearData?.classification_3tier?.toLowerCase() || null

      return {
        ...country,
        flag: getCountryFlag(country.name, iso3),
        region: COUNTRY_REGIONS[country.name] || 'Other',
        stratum,
        iso3
      }
    })
  }, [countries, classificationsCache, currentYear])

  // Group countries by backend region key (using ISO3_TO_REGION)
  const groupedByBackendRegion = useMemo(() => {
    const groups = new Map<RegionKey | 'other', CountryWithMeta[]>()

    // Initialize in display order
    for (const rk of REGION_KEYS) {
      groups.set(rk, [])
    }
    groups.set('other', [])

    for (const country of enrichedCountries) {
      const regionKey = country.iso3 ? ISO3_TO_REGION[country.iso3] : undefined
      if (regionKey && groups.has(regionKey)) {
        groups.get(regionKey)!.push(country)
      } else {
        groups.get('other')!.push(country)
      }
    }

    // Sort within each group
    for (const [, countries] of groups) {
      countries.sort((a, b) => a.name.localeCompare(b.name))
    }

    return groups
  }, [enrichedCountries])

  // Region search aliases for common abbreviations
  const REGION_ALIASES: Record<RegionKey, string[]> = {
    east_asia_pacific: ['EAP', 'Asia Pacific', 'East Asia'],
    europe_central_asia: ['ECA'],
    latin_america_caribbean: ['LAC', 'Latin America', 'Caribbean'],
    middle_east_north_africa: ['MENA', 'Middle East', 'North Africa'],
    north_america: ['NA'],
    south_asia: ['SA'],
    sub_saharan_africa: ['SSA', 'Sub-Saharan', 'Africa'],
    western_europe: ['WE', 'West Europe'],
    eastern_europe: ['EE', 'East Europe'],
    central_asia: ['CA'],
    southeast_asia: ['SEA', 'SE Asia', 'ASEAN'],
  }

  // Regions that match current search term
  const matchedRegionKeys = useMemo((): Set<RegionKey> => {
    if (!searchTerm.trim()) return new Set()
    const term = searchTerm.toLowerCase().trim()
    const matched = new Set<RegionKey>()
    for (const rk of REGION_KEYS) {
      const displayName = REGION_DISPLAY_NAMES[rk]
      if (displayName.toLowerCase().includes(term)) { matched.add(rk); continue }
      if (rk.includes(term)) { matched.add(rk); continue }
      const aliases = REGION_ALIASES[rk] || []
      if (aliases.some(a => a.toLowerCase().includes(term))) matched.add(rk)
    }
    return matched
  }, [searchTerm])

  // Filter countries by search term (with alias support)
  const filteredCountries = useMemo(() => {
    if (!searchTerm.trim()) return enrichedCountries

    const term = searchTerm.toLowerCase().trim()

    return enrichedCountries.filter(country => {
      // Direct name match
      if (country.name.toLowerCase().includes(term)) return true

      // Alias match
      const aliases = COUNTRY_ALIASES[country.name] || []
      if (aliases.some(alias => alias.toLowerCase().includes(term))) return true

      // Region match — include all countries in matched regions
      if (country.iso3) {
        const regionKey = ISO3_TO_REGION[country.iso3]
        if (regionKey && matchedRegionKeys.has(regionKey)) return true
      }

      return false
    })
  }, [enrichedCountries, searchTerm, matchedRegionKeys])

  // Get selected country's metadata
  const selectedCountryMeta = useMemo(() => {
    if (!selectedCountry) return null
    return enrichedCountries.find(c => c.name === selectedCountry) || null
  }, [selectedCountry, enrichedCountries])

  // Close dropdown when clicking outside
  useEffect(() => {
    const handleClickOutside = (event: MouseEvent) => {
      if (containerRef.current && !containerRef.current.contains(event.target as Node)) {
        setIsFocused(false)
        inputRef.current?.blur()
      }
    }
    document.addEventListener('click', handleClickOutside, true)
    return () => document.removeEventListener('click', handleClickOutside, true)
  }, [])

  // Handle mouse leave with delay
  const handleMouseLeave = () => {
    if (hoverTimeoutRef.current) clearTimeout(hoverTimeoutRef.current)
    hoverTimeoutRef.current = setTimeout(() => {
      setIsFocused(false)
    }, 900)
  }

  const handleMouseEnter = () => {
    if (hoverTimeoutRef.current) {
      clearTimeout(hoverTimeoutRef.current)
      hoverTimeoutRef.current = null
    }
  }

  useEffect(() => {
    return () => {
      if (hoverTimeoutRef.current) clearTimeout(hoverTimeoutRef.current)
    }
  }, [])

  const showDropdown = isFocused && !countriesLoading && !countryLoading

  /** Flat list of selectable items for arrow-key navigation. */
  type FlatOption = { type: 'country'; country: CountryWithMeta } | { type: 'region'; key: RegionKey }
  const flatOptions = useMemo((): FlatOption[] => {
    const result: FlatOption[] = []
    if (searchTerm) {
      // Matched regions first, then remaining countries
      const shownNames = new Set<string>()
      for (const rk of REGION_KEYS) {
        if (!matchedRegionKeys.has(rk)) continue
        result.push({ type: 'region', key: rk })
        const regionCountries = groupedByBackendRegion.get(rk) || []
        for (const c of regionCountries) {
          result.push({ type: 'country', country: c })
          shownNames.add(c.name)
        }
      }
      for (const c of filteredCountries) {
        if (!shownNames.has(c.name)) result.push({ type: 'country', country: c })
      }
    } else {
      for (const [regionKey, countries] of groupedByBackendRegion.entries()) {
        if (countries.length === 0) continue
        if (regionKey !== 'other') result.push({ type: 'region', key: regionKey as RegionKey })
        for (const c of countries) result.push({ type: 'country', country: c })
      }
    }
    return result
  }, [searchTerm, matchedRegionKeys, filteredCountries, groupedByBackendRegion])

  // Reset active index when list changes
  useEffect(() => { setActiveIndex(-1) }, [flatOptions])

  const handleSelect = (country: CountryWithMeta) => {
    setCountry(country.name)
    setSearchTerm('')
    setIsFocused(false)
  }

  const handleClear = () => {
    clearCountry()
    setSearchTerm('')
    inputRef.current?.focus()
  }

  /** Scroll the option at idx into view in the listbox. */
  const scrollOptionIntoView = (idx: number) => {
    const el = listRef.current?.querySelector(`[data-option-index="${idx}"]`) as HTMLElement | null
    el?.scrollIntoView({ block: 'nearest' })
  }

  const selectFlatOption = (opt: FlatOption) => {
    if (opt.type === 'region') {
      setSelectedRegion(opt.key)
      setSearchTerm('')
      setIsFocused(false)
    } else {
      handleSelect(opt.country)
    }
  }

  const activeOptionId = activeIndex >= 0 ? `country-option-${activeIndex}` : undefined

  const handleInputKeyDown = (event: React.KeyboardEvent<HTMLInputElement>) => {
    if (event.key === 'ArrowDown') {
      event.preventDefault()
      if (!isFocused) { setIsFocused(true); return }
      setActiveIndex(prev => {
        const next = Math.min(prev + 1, flatOptions.length - 1)
        requestAnimationFrame(() => scrollOptionIntoView(next))
        return next
      })
      return
    }
    if (event.key === 'ArrowUp') {
      event.preventDefault()
      setActiveIndex(prev => {
        const next = Math.max(prev - 1, 0)
        requestAnimationFrame(() => scrollOptionIntoView(next))
        return next
      })
      return
    }
    if (event.key === 'Home') {
      event.preventDefault()
      setActiveIndex(0)
      requestAnimationFrame(() => scrollOptionIntoView(0))
      return
    }
    if (event.key === 'End') {
      event.preventDefault()
      const last = flatOptions.length - 1
      setActiveIndex(last)
      requestAnimationFrame(() => scrollOptionIntoView(last))
      return
    }
    if (event.key === 'Escape') {
      setIsFocused(false)
      return
    }
    if (event.key === 'Enter') {
      event.preventDefault()
      // If an option is highlighted via arrow keys, select it
      if (activeIndex >= 0 && activeIndex < flatOptions.length) {
        selectFlatOption(flatOptions[activeIndex])
        return
      }
      // Single region match with no individual country matches → select region
      if (matchedRegionKeys.size === 1 && filteredCountries.length === 0) {
        const rk = Array.from(matchedRegionKeys)[0]
        setSelectedRegion(rk)
        setSearchTerm('')
        setIsFocused(false)
        return
      }
      // Single country match → select country
      if (filteredCountries.length === 1 && matchedRegionKeys.size === 0) {
        handleSelect(filteredCountries[0])
      }
    }
  }

  // Coverage bar component
  const CoverageBar = ({ coverage }: { coverage: number }) => {
    const percent = Math.round(coverage * 100)
    return (
      <div style={{ display: 'flex', alignItems: 'center', gap: 4 }}>
        <div
          style={{
            width: 40,
            height: 3,
            background: '#d0d5e0',
            borderRadius: 2,
            overflow: 'hidden'
          }}
        >
          <div
            style={{
              width: `${percent}%`,
              height: '100%',
              background: percent > 70 ? '#4CAF50' : percent > 40 ? '#FF9800' : '#F44336',
              borderRadius: 2
            }}
          />
        </div>
        <span style={{ fontSize: 10, color: '#767676' }}>{percent}%</span>
      </div>
    )
  }

  // Track option index across render calls for keyboard nav
  const optionIndexCounter = useRef(0)

  // Render country row in dropdown
  const renderCountryRow = (country: CountryWithMeta) => {
    const isMapHovered = mapHoveredCountry === country.name
    const idx = optionIndexCounter.current++
    const isActive = idx === activeIndex
    return (
    <div
      key={country.name}
      id={`country-option-${idx}`}
      data-option-index={idx}
      className="country-option"
      onClick={() => handleSelect(country)}
      onMouseEnter={(e) => {
        setActiveIndex(idx)
        e.currentTarget.style.background = isMapHovered ? '#bbdefb' : '#eef0f6'
      }}
      onMouseLeave={(e) => { e.currentTarget.style.background = isMapHovered ? '#e3f2fd' : 'white' }}
      role="option"
      aria-selected={selectedCountry === country.name}
      tabIndex={-1}
      style={{
        padding: '8px 12px',
        cursor: 'pointer',
        borderBottom: '1px solid #e8e8e8',
        transition: 'background 0.1s ease',
        display: 'flex',
        alignItems: 'center',
        gap: 8,
        background: isActive ? '#eef4ff' : isMapHovered ? '#e3f2fd' : 'white'
      }}
    >
      {/* Flag */}
      <span style={{ fontSize: 16 }}>{country.flag}</span>

      {/* Country info */}
      <div style={{ flex: 1, minWidth: 0 }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
          <span style={{ fontSize: 13, fontWeight: 500 }}>{country.name}</span>
          {country.stratum && (
            <span style={getStratumBadgeStyle(country.stratum)}>
              {country.stratum}
            </span>
          )}
        </div>
        <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginTop: 2 }}>
          <span style={{ fontSize: 10, color: '#767676' }}>
            {country.n_edges.toLocaleString()} edges
          </span>
          <CoverageBar coverage={country.coverage} />
        </div>
      </div>
    </div>
  )
  }

  // Determine header content
  const renderHeader = () => {
    if (countryLoading) {
      return <span style={{ fontSize: 12, fontWeight: 600, color: '#666' }}>
        {selectedRegion ? 'Loading regional graph...' : 'Loading country graph...'}
      </span>
    }

    if (selectedRegion) {
      return (
        <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
          <span style={{ fontSize: 16 }}>{REGION_ICONS[selectedRegion] ?? '🌐'}</span>
          <div>
            <div style={{ fontSize: 10, color: '#767676', fontWeight: 500 }}>Regional</div>
            <div style={{ fontSize: 12, fontWeight: 600, color: '#7C3AED' }}>
              {REGION_DISPLAY_NAMES[selectedRegion] ?? selectedRegion}
            </div>
          </div>
        </div>
      )
    }

    if (selectedCountryMeta) {
      return (
        <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
          <span style={{ fontSize: 16 }}>{selectedCountryMeta.flag}</span>
          <div>
            <div style={{ fontSize: 12, fontWeight: 600, color: '#3B82F6' }}>
              {selectedCountryMeta.name}
            </div>
            {selectedCountryMeta.stratum && (
              <span style={{ ...getStratumBadgeStyle(selectedCountryMeta.stratum), marginTop: 2 }}>
                {selectedCountryMeta.stratum}
              </span>
            )}
          </div>
        </div>
      )
    }

    return <span style={{ fontSize: 12, fontWeight: 600, color: '#555' }}>Unified model (203 countries)</span>
  }

  // Reset option index counter each render so indices match flatOptions
  optionIndexCounter.current = 0

  return (
    <div
      ref={containerRef}
      onMouseEnter={handleMouseEnter}
      onMouseLeave={handleMouseLeave}
      style={{ position: 'relative', width: '100%' }}
    >
      {/* Header showing current state */}
      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: 8 }}>
        {renderHeader()}
        {(selectedCountry || selectedRegion) && !countryLoading && (
          <button
            onClick={() => {
              if (selectedRegion) setSelectedRegion(null)
              handleClear()
            }}
            aria-label={selectedRegion ? "Clear selected region" : "Clear selected country"}
            style={{
              background: '#FFEBEE',
              borderWidth: 1,
              borderStyle: 'solid',
              borderColor: '#FFCDD2',
              borderRadius: 4,
              cursor: 'pointer',
              fontSize: 11,
              color: '#C62828',
              fontWeight: 500,
              padding: '3px 8px',
              transition: 'all 0.15s ease'
            }}
            onMouseEnter={(e) => {
              e.currentTarget.style.background = '#FFCDD2'
              e.currentTarget.style.borderColor = '#EF9A9A'
            }}
            onMouseLeave={(e) => {
              e.currentTarget.style.background = '#FFEBEE'
              e.currentTarget.style.borderColor = '#FFCDD2'
            }}
            title={selectedRegion ? "Clear region selection" : "Clear country selection"}
          >
            ✕ Clear
          </button>
        )}
      </div>

      {/* Search input */}
      <div style={{ position: 'relative' }}>
        <input
          ref={inputRef}
          id="country-search"
          name="country-search"
          type="text"
          value={searchTerm}
          onChange={(e) => setSearchTerm(e.target.value)}
          onFocus={() => setIsFocused(true)}
          onKeyDown={handleInputKeyDown}
          placeholder={countriesLoading ? 'Loading...' : 'Search countries or regions (e.g., USA, MENA, SSA)...'}
          disabled={countriesLoading || countryLoading}
          role="combobox"
          aria-autocomplete="list"
          aria-expanded={showDropdown}
          aria-controls={listboxId}
          aria-label="Search and select country"
          aria-activedescendant={activeOptionId}
          style={{
            width: '100%',
            padding: '8px 32px 8px 12px',
            borderWidth: 1,
            borderStyle: 'solid',
            borderColor: '#d0d5e0',
            borderRadius: 6,
            fontSize: 13,
            boxSizing: 'border-box',
            background: countriesLoading || countryLoading ? '#eef0f6' : 'white',
            cursor: countriesLoading || countryLoading ? 'wait' : 'text',
            transition: 'border-color 0.15s ease',
            ...(isFocused && { borderColor: '#3B82F6' })
          }}
        />
        {/* Dropdown caret */}
        <button
          className="touch-target-44"
          onClick={() => {
            setIsFocused(!isFocused)
            // Only auto-focus input on desktop to avoid mobile keyboard popup
            if (!isFocused && window.innerWidth >= 768) inputRef.current?.focus()
          }}
          aria-label={isFocused ? 'Close country list' : 'Open country list'}
          aria-expanded={showDropdown}
          aria-controls={listboxId}
          disabled={countriesLoading || countryLoading}
          style={{
            position: 'absolute',
            right: 4,
            top: '50%',
            transform: 'translateY(-50%)',
            background: 'none',
            border: 'none',
            cursor: countriesLoading || countryLoading ? 'wait' : 'pointer',
            padding: '4px 6px',
            display: 'flex',
            alignItems: 'center',
            color: '#767676'
          }}
          tabIndex={-1}
        >
          <svg
            width="12" height="12" viewBox="0 0 12 12" fill="none"
            stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"
            style={{ transform: isFocused ? 'rotate(180deg)' : 'rotate(0deg)', transition: 'transform 0.15s ease' }}
          >
            <polyline points="2 4 6 8 10 4" />
          </svg>
        </button>
      </div>

      {/* Dropdown */}
      {showDropdown && (
        <div
          id={listboxId}
          role="listbox"
          aria-label="Country options"
          onMouseEnter={handleMouseEnter}
          onMouseLeave={handleMouseLeave}
          style={{
            position: 'absolute',
            top: '100%',
            left: 0,
            right: 0,
            marginTop: 4,
            background: 'white',
            border: '1px solid #d0d5e0',
            borderRadius: 6,
            boxShadow: '0 4px 12px rgba(0,0,0,0.15)',
            zIndex: 1000,
            maxHeight: 320,
            overflow: 'hidden',
            display: 'flex',
            flexDirection: 'column'
          }}
        >
          {/* Country list */}
          <div ref={listRef} style={{ flex: 1, overflowY: 'auto', maxHeight: 280 }}>
            {filteredCountries.length === 0 && matchedRegionKeys.size === 0 ? (
              <div style={{ padding: 16, textAlign: 'center', color: '#767676', fontSize: 13 }}>
                No countries or regions found
              </div>
            ) : searchTerm ? (
              // When searching, show matched regions (with their countries) + individually matched countries
              (() => {
                const elements: React.ReactNode[] = []
                const shownCountryNames = new Set<string>()

                // First: matched regions with their countries
                for (const rk of REGION_KEYS) {
                  if (!matchedRegionKeys.has(rk)) continue
                  const regionCountries = groupedByBackendRegion.get(rk) || []
                  const isRegionSelected = selectedRegion === rk
                  const regionIdx = optionIndexCounter.current++
                  const isRegionActive = regionIdx === activeIndex
                  elements.push(
                    <div key={`region-${rk}`} role="presentation">
                      <div
                        id={`country-option-${regionIdx}`}
                        data-option-index={regionIdx}
                        className="country-option"
                        onClick={() => { setSelectedRegion(rk); setIsFocused(false) }}
                        onMouseEnter={() => setActiveIndex(regionIdx)}
                        role="option"
                        aria-selected={isRegionSelected}
                        tabIndex={-1}
                        style={{
                          padding: '8px 12px',
                          cursor: 'pointer',
                          borderBottom: '1px solid #e8e8e8',
                          transition: 'background 0.1s ease',
                          display: 'flex',
                          alignItems: 'center',
                          gap: 8,
                          background: isRegionActive ? '#eef4ff' : isRegionSelected ? '#F3E8FF' : '#f9f9fb',
                        }}
                      >
                        <span style={{ fontSize: 16 }}>{REGION_ICONS[rk] ?? '🌐'}</span>
                        <div style={{ flex: 1, minWidth: 0 }}>
                          <div style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
                            <span style={{ fontSize: 13, fontWeight: 600, color: isRegionSelected ? '#7C3AED' : '#444' }}>
                              {REGION_DISPLAY_NAMES[rk]}
                            </span>
                            <span style={{ fontSize: 10, fontWeight: 500, color: '#767676' }}>
                              {regionCountries.length} countries
                            </span>
                          </div>
                        </div>
                      </div>
                      {regionCountries.map(c => {
                        shownCountryNames.add(c.name)
                        return renderCountryRow(c)
                      })}
                    </div>
                  )
                }

                // Then: individually matched countries not already shown via region
                const remainingCountries = filteredCountries.filter(c => !shownCountryNames.has(c.name))
                if (remainingCountries.length > 0) {
                  elements.push(...remainingCountries.slice(0, 50).map(renderCountryRow))
                }

                return elements
              })()
            ) : (
              // When not searching, show grouped by backend region: region row → countries
              Array.from(groupedByBackendRegion.entries())
                .filter(([, countries]) => countries.length > 0)
                .map(([regionKey, countries]) => {
                  const isRegionSelected = selectedRegion === regionKey
                  const displayName = regionKey === 'other'
                    ? 'Other'
                    : REGION_DISPLAY_NAMES[regionKey as RegionKey] ?? regionKey
                  const regionIdx = regionKey !== 'other' ? optionIndexCounter.current++ : -1
                  const isRegionActive = regionIdx === activeIndex
                  return (
                  <div key={regionKey} role="presentation">
                    {/* Region row — clickable, styled like country rows */}
                    {regionKey !== 'other' && (
                      <div
                        id={`country-option-${regionIdx}`}
                        data-option-index={regionIdx}
                        className="country-option"
                        onClick={() => {
                          setSelectedRegion(regionKey as RegionKey)
                          setIsFocused(false)
                        }}
                        onMouseEnter={() => setActiveIndex(regionIdx)}
                        role="option"
                        aria-selected={isRegionSelected}
                        tabIndex={-1}
                        style={{
                          padding: '8px 12px',
                          cursor: 'pointer',
                          borderBottom: '1px solid #e8e8e8',
                          transition: 'background 0.1s ease',
                          display: 'flex',
                          alignItems: 'center',
                          gap: 8,
                          background: isRegionActive ? '#eef4ff' : isRegionSelected ? '#F3E8FF' : '#f9f9fb',
                          position: 'sticky',
                          top: 0,
                          zIndex: 1,
                        }}
                      >
                        <span style={{ fontSize: 16 }}>{REGION_ICONS[regionKey as RegionKey] ?? '🌐'}</span>
                        <div style={{ flex: 1, minWidth: 0 }}>
                          <div style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
                            <span style={{ fontSize: 13, fontWeight: 600, color: isRegionSelected ? '#7C3AED' : '#444' }}>
                              {displayName}
                            </span>
                            <span style={{
                              fontSize: 10,
                              fontWeight: 500,
                              color: '#767676',
                            }}>
                              {countries.length} countries
                            </span>
                          </div>
                        </div>
                      </div>
                    )}
                    {regionKey === 'other' && (
                      <div style={{
                        padding: '6px 12px',
                        background: '#f4f5fa',
                        fontSize: 11,
                        fontWeight: 600,
                        color: '#666',
                        borderBottom: '1px solid #d0d5e0',
                      }}>
                        {displayName} ({countries.length})
                      </div>
                    )}
                    {countries.map(renderCountryRow)}
                  </div>
                  )
                })
            )}
          </div>

          {/* Footer */}
          <div style={{
            padding: '8px 12px',
            borderTop: '1px solid #e2e6ee',
            background: '#f4f5fa',
            fontSize: 11,
            color: '#767676'
          }}>
            {searchTerm && matchedRegionKeys.size > 0
              ? `${matchedRegionKeys.size} region${matchedRegionKeys.size > 1 ? 's' : ''} + ${filteredCountries.length} countries`
              : `${filteredCountries.length} of ${countries.length} countries`
            }
          </div>
        </div>
      )}

    </div>
  )
}

export default CountrySelector
