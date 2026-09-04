# External Data Sources & Attribution Specification

Continuity Council integrates four data providers to deliver real-time environmental, geographical, foreign exchange, and historical intelligence during disruption investigations.

---

## 1. Open-Meteo Weather API

- **Provider**: Open-Meteo GmbH
- **License / Attribution**: [Weather data by Open-Meteo (CC-BY 4.0)](https://open-meteo.com/)
- **Endpoint**: `https://api.open-meteo.com/v1/forecast` & `https://archive-api.open-meteo.com/v1/archive`
- **Data Ingested**: 5-year historical and short-term forecast precipitation probability, daily precipitation sums, and maximum 10m wind speeds for exact set coordinates.
- **Agent Integration**:
  - Informs the **Budget Sentinel** whether to append rain contingency line items.
  - Informs the **Schedule Optimizer** when evaluating exterior vs interior soundstage swaps.
- **Caching & SLA**:
  - **In-Memory TTL**: 7 days per `(round(lat, 2), round(lon, 2), month)`.
  - **Timeout**: 3.0 seconds strict timeout with deterministic biome fallback.

---

## 2. OpenStreetMap & Nominatim Geocoding

- **Provider**: OpenStreetMap Foundation
- **License / Attribution**: [© OpenStreetMap contributors (ODbL)](https://www.openstreetmap.org/copyright)
- **Endpoint**: `https://nominatim.openstreetmap.org/search`
- **Data Ingested**: Geographic latitude and longitude coordinates for production filming locations and remote units.
- **Agent Integration**:
  - Informs the **Compliance Agent** via the **Haversine Distance Rule**: Any proposed emergency relocation requiring crew transit $>100$ statute miles within a single shoot window is flagged as **physically impossible** and hard-failed.
- **Caching & SLA**:
  - **In-Memory TTL**: Permanent per location in ClickHouse.
  - **Timeout**: 3.0 seconds with rate-limiting respect (1 req/s) and custom User-Agent header `ContinuityCouncil-Hackathon/1.0`.

---

## 3. Frankfurter / European Central Bank Foreign Exchange

- **Provider**: Frankfurter API / European Central Bank
- **License / Attribution**: [Rates by Frankfurter, source: European Central Bank](https://www.frankfurter.app/)
- **Endpoint**: `https://api.frankfurter.app/latest`
- **Data Ingested**: Daily reference spot foreign exchange rates (EUR, GBP, CAD, AED, JOD to USD).
- **Agent Integration**:
  - Used by **Budget Sentinel** to convert overseas location daily fees, municipal permit costs, and international cast rates into the production base accounting currency.
- **Caching & SLA**:
  - **In-Memory TTL**: 24 hours.
  - **Timeout**: 3.0 seconds with benchmark ECB prior fallback.

---

## 4. ClickHouse Cloud & Model Context Protocol (MCP)

- **Provider**: ClickHouse, Inc. & Model Context Protocol (stdio)
- **License / Attribution**: ClickHouse Cloud columnar analytical engine & Model Context Protocol.
- **Data Ingested**: 200,000+ historical disruption records queried via `strategy_performance_mv` Materialized View.
- **Agent Integration**:
  - Supplies 30% empirical weighting for cost calibration and delay predictions.
- **Caching & SLA**:
  - **In-Memory TTL**: 10 minutes + persistent warm MCP session ($<200\text{ms}$ query latency).
  - **Timeout**: 6.0 seconds hard timeout.

## 5. Historical Corpus Provenance

The 200,000-row `disruption_history` analytical dataset is synthetic but grounded in real-world public data archives, ensuring realistic geographic, environmental, and budgetary distributions:

1. **Open-Meteo Historical Weather Archive (2019–2024)**:
   - **Source**: [Open-Meteo Historical Weather API](https://archive-api.open-meteo.com/v1/archive) (CC-BY 4.0)
   - **Usage**: Daily rainfall (`rain_sum`), maximum wind gust (`wind_speed_10m_max`), and maximum temperature (`temperature_2m_max`) across 6 years (2,192 days) for all 60 filming hubs. Weather disruption frequencies directly reflect real seasonal phenomena (e.g. Mumbai's monsoon season from June to September).
   - **Storage**: Committed offline cache in `scripts/data/weather_cache/{city_slug}.json`.

2. **Global Production Filming Hubs**:
   - **Source**: [OpenStreetMap & Nominatim](https://www.openstreetmap.org/)
   - **Usage**: 60 verified production centers worldwide across 8 geographical regions with verified lat/lon coordinates, country codes, local currencies, World Bank PPP factors, and urban density ratings in `scripts/data/real_locations.json`.

3. **Union Rate Card Benchmarks**:
   - **Source**: [SAG-AFTRA 2023–2026 Theatrical Agreement](https://www.sagaftra.org/contracts-industry-resources/theatrical-independent-film) & [IATSE Area Standards Agreement](https://iatse.net/)
   - **Usage**: Crew day burn rates ($40k indie, $150k mid, $500k tentpole), SAG principal performer scale ($1,082–$15,000/day), and background rates calibrated with localized purchasing power parity.

4. **Production Budget Percentiles**:
   - **Source**: [The Numbers / Nash Information Services](https://www.the-numbers.com/) & [Kaggle TMDB 5000 Movie Dataset](https://www.kaggle.com/datasets/tmdb/tmdb-movie-metadata)
   - **Usage**: Empirical budget distribution percentiles (P0–P25 indie, P25–P65 mid, P65–P90 mid-high, P90–P100 tentpole) governing equipment reliability and reserve contingency buffers.

---

## 6. Resilience & Offline Fallbacks

All external network operations adhere to the **15-Second Investigation Guarantee**:
- If any external API times out or the server runs in an air-gapped CI test runner, deterministic fallback estimators trigger immediately.
- Offline tests run with 100% mocked HTTP clients, guaranteeing deterministic test execution without network flake.

