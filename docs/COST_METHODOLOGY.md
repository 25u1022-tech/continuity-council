# Cost Methodology & Calibration Engine

Continuity Council calculates recovery option cost overruns using a **dual-layer calibrated economic engine**:

$$\text{Final Option Estimate} = 0.70 \times \text{Bottom-Up Rate Card Cost} + 0.30 \times \text{ClickHouse Historical Average}$$

This hybrid approach ensures that cost estimates are grounded in **actual production asset rate cards** while being calibrated against **200,000+ empirical historical disruption outcomes** stored in ClickHouse Cloud.

---

## 1. Bottom-Up Rate Card Model (70% Weight)

When a disruption occurs, the Budget Sentinel agent calculates the itemized operational cost of the proposed recovery strategy:

$$\text{Bottom-Up Cost} = C_{\text{crew}} + C_{\text{cast}} + C_{\text{location}} + C_{\text{equipment}} + C_{\text{weather}}$$

### A. Crew Burn Rate ($C_{\text{crew}}$)
Crew burn represents the baseline daily operating cost of the full production unit (IATSE, DGA, Teamsters, camera, grip, electric, and sound departments).

- **Formula**: $\text{Crew Day Rate}(\text{Tier}) \times \Delta \text{Crew Days}$
- **Industry Benchmark Rate Cards**:
  - **Indie ($1M-$5M budget)**: \$40,000 / day
  - **Mid-Budget ($15M-$50M budget)**: \$150,000 / day
  - **Tentpole ($100M-$250M+ budget)**: \$500,000 / day

### B. Principal Cast Holding ($C_{\text{cast}}$)
If principal talent is placed on standby or held for rescheduled shooting days:
- **Formula**: $\sum (\text{Day Rate of Affected Cast Members})$
- **Rates**: Lead cast scale (\$3,500 - \$25,000 / day) and supporting cast scale (\$1,100 - \$5,000 / day).

### C. Target Location Daily Fees & Live FX ($C_{\text{location}}$)
When scenes are moved or rescheduled to a different location or soundstage:
- **Formula**: $\text{Daily Location Fee} \times \text{Live Foreign Exchange Multiplier}$
- **Real-Time FX**: If an international location operates in local currency (e.g. GBP, EUR, CAD, AED, JOD), live spot rates from the European Central Bank (via Frankfurter) convert the fee to the production's base currency (USD).

### D. Equipment & Camera Package Days ($C_{\text{equipment}}$)
Rental extension fees for specialized large-format cameras, anamorphic lenses, cranes, and grip packages (\$1,200 - \$3,500 / day).

### E. Environmental Risk & Weather Contingency ($C_{\text{weather}}$)
For exterior relocations where Open-Meteo predicts elevated precipitation risk (>35%):
- **Formula**: $0.05 \times C_{\text{crew}}$ weather contingency buffer for rain covers, canopy rigging, and localized weather insurance.

---

## 2. Empirical Historical Evidence Calibration (30% Weight)

To avoid naive theoretical rate calculations, the Budget Sentinel queries ClickHouse Cloud via `mcp-clickhouse`:

$$\text{Historical Prior} = \text{SELECT avgMerge(avg\_cost) FROM strategy\_performance\_mv WHERE strategy = :s}$$

This empirical anchor adjusts theoretical numbers based on real historical friction (unexpected overtime, turnaround turnaround penalties, and schedule slippage observed across 200,000+ past cases).

---

## 3. Production Studio Overrides

While benchmark rate cards are pre-seeded into `continuity_council.rate_cards`, studio finance teams can customize:
- Specific production tier assignments (`indie`, `mid`, `tentpole`).
- Custom location daily fees during production onboarding.
- Individual cast member contractual day rates.
