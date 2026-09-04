# Cost Methodology & Calibration Engine

Continuity Council calculates recovery option cost overruns using a **dual-layer calibrated economic engine** with **universal global geo-awareness**:

$$\text{Final Option Estimate} = 0.70 \times \text{Bottom-Up Rate Card Cost} + 0.30 \times \text{ClickHouse Historical Average}$$

This hybrid approach ensures that cost estimates are grounded in **actual production asset rate cards scaled by localized macroeconomic reality** while being calibrated against **200,000+ empirical historical disruption outcomes** stored in ClickHouse Cloud.

---

## 1. Global Geo-Aware Costing Engine (World Bank + OSM)

To accurately price production relocations, municipal permits, and crew burn rates in **any country and any city worldwide**, Continuity Council resolves macroeconomic and demographic indices **once** upon location onboarding and stores them on the location record:

$$\text{Geo Multiplier} = \text{Country Multiplier} \times \text{City Tier Multiplier}$$

$$\text{Location Adjusted Cost} = \text{Base Cost} \times \text{Geo Multiplier}$$

### A. Country Multiplier ($\text{Country Mult}$)
Live-queried from the World Bank API indicator `NY.GDP.PCAP.PP.CD` (GDP per capita, PPP in current international \$) and cached for 30 days in ClickHouse table `continuity_council.geo_cost_index`:

$$\text{country\_mult} = \text{clamp}\left(\left(\frac{\text{GDP}_{\text{PPP}}}{\text{US GDP}_{\text{PPP}}}\right)^{0.6}, 0.25, 1.10\right)$$

- **Benchmark**: $\text{US GDP}_{\text{PPP}} = \$80,000$.
- **Bounding**: Clamped to $[0.25, 1.10]$ to prevent distortion for developing or ultra-high micro-states.
- **Embedded Fallback**: 40+ country static fallback matrix for network failure; unknown countries default to $1.0\times$ with a warning badge.

### B. City Tier Multiplier ($\text{Tier Mult}$)
Determined from OpenStreetMap (OSM) Nominatim metadata (population tag & capital status):

| City Tier | Multiplier | Population Threshold & Classification |
| :--- | :--- | :--- |
| **Tier 1 (Metro / Megacity)** | **1.00x** | Population $\ge 5,000,000$ OR Sovereign Capital / Megacity |
| **Tier 2 (Regional Hub)** | **0.50x** | Population $200,000 - 1,000,000$ OR non-capital $1\text{M}-5\text{M}$ |
| **Tier 3 (Small Town / Rural)** | **0.35x** | Population $< 200,000$ (Outposts, rural filming terrains) |

*Fallback when population is missing:* Sovereign capitals and curated global megacities assign to **Tier 1 (1.0x)**; all other municipalities assign to **Tier 2 (0.5x)**.

### C. Zero Runtime Latency Guarantee ($\le 2.1\text{s}$ Sacred SLA)
Geo economics are resolved **ONCE** during production or location onboarding and stored directly on the `continuity_council.locations` row (`country_code`, `country_mult`, `city_tier`, `geo_mult`, `currency_code`). During active multi-agent disruption investigations, the Budget Sentinel reads precomputed local indices in **0 ms**, guaranteeing compliance with the sub-2.1 second response requirement.

### D. Global City Pricing Benchmark Examples

| City | Country | OSM Demographics | Country Factor | Compound Geo Mult | Local Currency | Example Stage Fee / Day |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| **Dharwad** | India (IN) | Tier 2 (Regional, ~550k pop) | 0.29x | **0.15x** | INR (₹) | \$750 / day |
| **Hubballi** | India (IN) | Tier 2 (Regional, ~900k pop) | 0.29x | **0.15x** | INR (₹) | \$750 / day |
| **Mumbai** | India (IN) | Tier 1 (Megacity, 12.5M pop) | 0.29x | **0.29x** | INR (₹) | \$1,450 / day |
| **London** | United Kingdom (GB) | Tier 1 (Capital, 8.9M pop) | 0.83x | **0.83x** | GBP (£) | \$4,150 / day |
| **Lagos** | Nigeria (NG) | Tier 1 (Megacity, 15M pop) | 0.25x | **0.25x** | NGN (₦) | \$1,250 / day |
| **Sao Paulo** | Brazil (BR) | Tier 1 (Megacity, 12.3M pop) | 0.44x | **0.44x** | BRL (R$) | \$2,200 / day |

---

## 2. Bottom-Up Rate Card Model (70% Weight)

When a disruption occurs, the Budget Sentinel agent calculates the itemized operational cost of the proposed recovery strategy:

$$\text{Bottom-Up Cost} = C_{\text{crew}} + C_{\text{cast}} + C_{\text{location}} + C_{\text{equipment}} + C_{\text{weather}}$$

### A. Crew Burn Rate ($C_{\text{crew}}$)
Crew burn represents the baseline daily operating cost of the full production unit (IATSE, DGA, Teamsters, camera, grip, electric, and sound departments), scaled by the host location's `geo_mult`:

- **Formula**: $\text{Crew Day Rate}(\text{Tier}) \times \Delta \text{Crew Days} \times \text{Geo Mult}$
- **Industry Benchmark Rate Cards (US Baseline)**:
  - **Indie (\$1M-\$5M budget)**: \$40,000 / day
  - **Mid-Budget (\$15M-\$50M budget)**: \$150,000 / day
  - **Tentpole (\$100M-\$250M+ budget)**: \$500,000 / day

### B. Principal Cast Holding ($C_{\text{cast}}$)
If principal talent is placed on standby or held for rescheduled shooting days:
- **Formula**: $\sum (\text{Day Rate of Affected Cast Members})$
- **Rates**: Lead cast scale (\$3,500 - \$25,000 / day) and supporting cast scale (\$1,100 - \$5,000 / day).

### C. Target Location Daily Fees & Live FX ($C_{\text{location}}$)
When scenes are moved or rescheduled to a different location or soundstage:
- **Formula**: $\text{Daily Location Fee} \times \text{Geo Mult} \times \text{Live Foreign Exchange Multiplier}$
- **Real-Time FX**: If an international location operates in local currency (e.g. INR, GBP, EUR, BRL, NGN, CAD, AED, JOD), live spot rates from the European Central Bank (via Frankfurter) convert the fee to the production's base currency (USD).

### D. Equipment & Camera Package Days ($C_{\text{equipment}}$)
Rental extension fees for specialized large-format cameras, anamorphic lenses, cranes, and grip packages (\$1,200 - \$3,500 / day).

### E. Environmental Risk & Weather Contingency ($C_{\text{weather}}$)
For exterior relocations where Open-Meteo predicts elevated precipitation risk (>35%):
- **Formula**: $0.05 \times C_{\text{crew}}$ weather contingency buffer for rain covers, canopy rigging, and localized weather insurance.

---

## 3. Empirical Historical Evidence Calibration (30% Weight)

To avoid naive theoretical rate calculations, the Budget Sentinel queries ClickHouse Cloud via `mcp-clickhouse`:

$$\text{Historical Prior} = \text{SELECT avgMerge(avg\_cost) FROM strategy\_performance\_mv WHERE strategy = :s}$$

This empirical anchor adjusts theoretical numbers based on real historical friction (unexpected overtime, turnaround penalties, and schedule slippage observed across 200,000+ past cases).

> **Note on Historical Corpus Provenance**: The 200,000-row `disruption_history` corpus is synthetic but rigorously grounded in real public archives: 60 global filming hubs, daily Open-Meteo historical weather (2019–2024), published SAG-AFTRA/IATSE day rates, and IMDb/TMDB budget percentiles. It exhibits real geographic and seasonal dynamics (such as the documented monsoon disruption spike in Mumbai from June to September) while maintaining strict deterministic reproducibility (`random.seed(42)`).

---

## 4. Production Studio & UI Overrides

While benchmark rate cards and geo indices are automatically derived:
- **LocationMapPicker**: Producers can review the computed `<Country> · <tier> · x<mult>` chip and immediately override the city tier (`tier_1`, `tier_2`, `tier_3`) with instant live multiplier recalculation.
- **Settings Page (`/settings`)**: Configurable rate card weights, distance units (miles/km), base currency, and ClickHouse cache policies.
- **Auditable Breakdown**: Every generated recovery option includes a transparent `Geo adjustment x{mult} ({country}, {tier})` line item in its budget breakdown.

---

## 5. Attributions & Open Data Standards

- **World Bank Open Data**: GDP per capita (PPP) data provided by the World Bank under the [Creative Commons Attribution 4.0 International license (CC-BY 4.0)](https://datacatalog.worldbank.org/public-licenses).
- **OpenStreetMap**: Map data and Nominatim geocoding © [OpenStreetMap contributors](https://www.openstreetmap.org/copyright) under the Open Database License (ODbL).
- **European Central Bank**: Foreign exchange spot rates provided via Frankfurter open API.
- **Open-Meteo**: High-resolution meteorological risk modeled under CC-BY 4.0.
