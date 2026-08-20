/**
 * Continuity Council — External Data Sources & Methodology Specification
 *
 * Provides structured documentation and metadata for all live signals,
 * rate-card benchmark methodologies, caching tiers, and legal attributions.
 */

export const DATA_SOURCES = [
  {
    id: "world-bank-ppp",
    name: "World Bank GDP PPP Index",
    tagline: "Global purchasing power parity and localized economic multiplier",
    icon: "Globe",
    provider: "World Bank Group",
    attribution: "World Bank open data (CC-BY 4.0)",
    attributionUrl: "https://data.worldbank.org/indicator/NY.GDP.PCAP.PP.CD",
    endpoint: "https://api.worldbank.org/v2/country/{code}/indicator/NY.GDP.PCAP.PP.CD",
    whatWeFetch: "Latest GDP per capita (PPP, current international $) for the filming host nation (NY.GDP.PCAP.PP.CD).",
    howUsed: "Calculates the country multiplier: clamp((GDP_PPP / US_GDP_PPP) ** 0.6, 0.25, 1.10). Combined with OSM population city tiers (tier 1: 1.0x, tier 2: 0.5x, tier 3: 0.35x) to scale crew day burn, location fees, and municipal permits.",
    cacheTtl: "30 days in ClickHouse geo_cost_index + memory cache",
    timeout: "3.0 seconds hard timeout",
    fallback: "Embedded static benchmark table of 40+ countries (India: 0.29x, UK: 0.83x, Brazil: 0.44x, Nigeria: 0.25x; unknown: 1.0x with warning badge).",
  },
  {
    id: "open-meteo",
    name: "Open-Meteo Historical Weather",
    tagline: "High-resolution historical precipitation and wind risk modeling",
    icon: "CloudRain",
    provider: "Open-Meteo GmbH",
    attribution: "Weather data by Open-Meteo (CC-BY 4.0)",
    attributionUrl: "https://open-meteo.com/",
    endpoint: "https://archive-api.open-meteo.com/v1/archive",
    whatWeFetch: "5-year historical daily precipitation sums, maximum wind gusts, and precipitation probabilities for the shoot month at exact location coordinates.",
    howUsed: "Calculates an environmental disruption risk score (0-100). When outdoor exterior scenes are moved or scheduled with high rain risk (>40%), Budget Sentinel adds a calibrated weather contingency buffer (tents, cover sets, rain insurance).",
    cacheTtl: "7 days in-memory (keyed by rounded lat/lon + calendar month)",
    timeout: "3.0 seconds hard timeout",
    fallback: "Default climate baseline calibrated by geographical biome (desert: 5%, temperate: 25%, coastal: 35%).",
  },
  {
    id: "openstreetmap",
    name: "OpenStreetMap & Nominatim",
    tagline: "Global geographic coordinate resolver and Haversine transit calculator",
    icon: "MapPin",
    provider: "OpenStreetMap Foundation",
    attribution: "© OpenStreetMap contributors (ODbL)",
    attributionUrl: "https://www.openstreetmap.org/copyright",
    endpoint: "https://nominatim.openstreetmap.org/search",
    whatWeFetch: "Precise latitude, longitude, and OSM population tag for production locations, soundstages, and remote desert/coastal units.",
    howUsed: "Used to determine city tier (≥5M: tier 1, 200k-1M: tier 2, <200k: tier 3) and by the Compliance Agent to calculate Haversine great-circle distances between locations. If an emergency relocation requires crew transport >100 miles within a single shoot window, the option is hard-failed as physically impossible.",
    cacheTtl: "Permanent per resolved location in ClickHouse",
    timeout: "3.0 seconds hard timeout with rate-limiting respect (1 req/s)",
    fallback: "Production base city coordinates or soundstage default coordinates.",
  },
  {
    id: "frankfurter-ecb",
    name: "Frankfurter / European Central Bank FX",
    tagline: "Live interbank foreign exchange reference rates",
    icon: "Coins",
    provider: "Frankfurter API / European Central Bank",
    attribution: "Rates by Frankfurter, source: European Central Bank",
    attributionUrl: "https://www.frankfurter.app/",
    endpoint: "https://api.frankfurter.app/latest",
    whatWeFetch: "Live reference foreign exchange spot rates for international filming currencies (GBP, EUR, CAD, AED, JOD, INR, BRL, USD).",
    howUsed: "Converts local location daily fees, municipal permits, and international cast day-rates into the production's base accounting currency in real time.",
    cacheTtl: "24 hours in-memory",
    timeout: "3.0 seconds hard timeout",
    fallback: "Last-known benchmark exchange rates (EUR: 1.08, GBP: 1.28, CAD: 0.74, AED: 0.27, JOD: 1.41, INR: 0.012).",
  },
  {
    id: "clickhouse-mcp",
    name: "ClickHouse Cloud & Model Context Protocol",
    tagline: "Columnar analytical historical evidence store and state engine",
    icon: "Database",
    provider: "ClickHouse, Inc. & Anthropic MCP",
    attribution: "ClickHouse Cloud columnar analytical engine & Model Context Protocol (stdio)",
    attributionUrl: "https://clickhouse.com/",
    endpoint: "Official mcp-clickhouse stdio server",
    whatWeFetch: "Aggregated empirical cost overruns, delay hours, and continuity scores across 200,000+ historical disruption records via strategy_performance_mv.",
    howUsed: "Calibrates bottom-up rate card estimates (0.7 bottom-up + 0.3 historical average) to ground option pricing in real empirical evidence.",
    cacheTtl: "10-minute TTL in-memory cache + persistent warm MCP session (<200ms latency)",
    timeout: "6.0 seconds hard timeout",
    fallback: "Pre-aggregated fallback priors with deterministic taxonomy rankings.",
  },
];

export const SIGNAL_IMPACTS = [
  {
    signal: "Global Purchasing Power & City Tier (World Bank + OSM)",
    affectedAgent: "Budget Sentinel",
    impactDescription: "Calculates compound geo multiplier (country factor × city tier) to ground crew rates, stage fees, and municipal permits in localized reality worldwide.",
  },
  {
    signal: "Rain & Wind Probability (Open-Meteo)",
    affectedAgent: "Budget Sentinel & Schedule Optimizer",
    impactDescription: "Applies weather contingency insurance costs on exterior relocations and penalizes outdoor moves on stormy days.",
  },
  {
    signal: "Transit Distance > 100 Miles (Nominatim / Haversine)",
    affectedAgent: "Compliance Agent",
    impactDescription: "Triggers hard compliance rejection (score penalized by 0.25x and badge flagged 'INVALID: Transit > 100mi') due to physical impossibility.",
  },
  {
    signal: "International Currency Discrepancy (Frankfurter / ECB)",
    affectedAgent: "Budget Sentinel",
    impactDescription: "Dynamically applies live exchange rates on foreign location permits and overseas stage rentals.",
  },
  {
    signal: "Historical Cohort Aggregation (ClickHouse MV)",
    affectedAgent: "Budget Sentinel & Auditor",
    impactDescription: "Calibrates bottom-up itemized cost model with 30% empirical historical weighting and logs audit proof.",
  },
];

export const RATE_CARD_BENCHMARKS = [
  { tier: "Indie ($1M-$5M)", crewDay: "$40,000 / day", leadScale: "$1,100 / day", soundstage: "$5,000 / day", permit: "$500 / day" },
  { tier: "Mid-Budget ($15M-$50M)", crewDay: "$150,000 / day", leadScale: "$3,500 / day", soundstage: "$10,000 / day", permit: "$1,500 / day" },
  { tier: "Tentpole ($100M-$250M+)", crewDay: "$500,000 / day", leadScale: "$15,000 / day", soundstage: "$25,000 / day", permit: "$5,000 / day" },
];

export const GEO_EXAMPLE_CITIES = [
  { city: "Dharwad", country: "India (IN)", tier: "tier-2 (0.50x)", countryMult: "0.29x", geoMult: "0.15x", currency: "INR (₹)", exampleFee: "$750 / day" },
  { city: "Hubballi", country: "India (IN)", tier: "tier-2 (0.50x)", countryMult: "0.29x", geoMult: "0.15x", currency: "INR (₹)", exampleFee: "$750 / day" },
  { city: "Mumbai", country: "India (IN)", tier: "tier-1 (1.00x)", countryMult: "0.29x", geoMult: "0.29x", currency: "INR (₹)", exampleFee: "$1,450 / day" },
  { city: "London", country: "United Kingdom (GB)", tier: "tier-1 (1.00x)", countryMult: "0.83x", geoMult: "0.83x", currency: "GBP (£)", exampleFee: "$4,150 / day" },
  { city: "Sao Paulo", country: "Brazil (BR)", tier: "tier-1 (1.00x)", countryMult: "0.44x", geoMult: "0.44x", currency: "BRL (R$)", exampleFee: "$2,200 / day" },
  { city: "Lagos", country: "Nigeria (NG)", tier: "tier-1 (1.00x)", countryMult: "0.25x", geoMult: "0.25x", currency: "NGN (₦)", exampleFee: "$1,250 / day" },
];
