/**
 * Continuity Council — External Data Sources & Methodology Specification
 *
 * Provides structured documentation and metadata for all live signals,
 * rate-card benchmark methodologies, caching tiers, and legal attributions.
 */

export const DATA_SOURCES = [
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
    whatWeFetch: "Precise latitude and longitude coordinates for production locations, soundstages, and remote desert/coastal units.",
    howUsed: "Used by the Compliance Agent to calculate Haversine great-circle distances between locations. If an emergency relocation requires crew transport >100 miles within a single shoot window, the option is hard-failed as physically impossible.",
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
    whatWeFetch: "Live reference foreign exchange spot rates for international filming currencies (GBP, EUR, CAD, AED, JOD, USD).",
    howUsed: "Converts local location daily fees, municipal permits, and international cast day-rates into the production's base accounting currency in real time.",
    cacheTtl: "24 hours in-memory",
    timeout: "3.0 seconds hard timeout",
    fallback: "Last-known benchmark exchange rates (EUR: 1.08, GBP: 1.28, CAD: 0.74, AED: 0.27, JOD: 1.41).",
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
