import React from "react";
import { DATA_SOURCES, SIGNAL_IMPACTS, RATE_CARD_BENCHMARKS, GEO_EXAMPLE_CITIES } from "../lib/dataSources";
import { Pill } from "../components/badges";
import {
  Database,
  CloudRain,
  MapPin,
  Coins,
  ShieldCheck,
  Layers,
  ExternalLink,
  Globe,
  TrendingDown,
} from "lucide-react";

const ICON_MAP = {
  CloudRain: CloudRain,
  MapPin: MapPin,
  Coins: Coins,
  Database: Database,
  Globe: Globe,
};

export default function DataMethodologyPage() {
  return (
    <div className="cc-fade-up space-y-10" data-testid="data-methodology-page">
      {/* Header */}
      <div>
        <div className="text-[12px] font-semibold uppercase tracking-wider text-[var(--cc-text-tertiary)]">
          Architecture & Transparency
        </div>
        <h1 className="font-display mt-1 text-[30px] font-semibold leading-tight tracking-tight text-[var(--cc-text-primary)]">
          Data sources & cost methodology
        </h1>
        <p className="mt-1.5 max-w-3xl text-[14px] text-[var(--cc-text-secondary)]">
          Continuity Council combines ClickHouse Cloud analytical history with keyless World Bank macroeconomic data,
          OpenStreetMap geographic demographics, and ECB spot exchange rates to ground option pricing in reality worldwide.
        </p>
      </div>

      {/* NEW: Global Geo-Aware Costing Model Card */}
      <div className="cc-card p-6 md:p-8" data-testid="geo-costing-card">
        <div className="flex items-center gap-3.5">
          <div className="flex h-10 w-10 items-center justify-center rounded-[10px] border border-[var(--cc-border)] bg-[var(--cc-surface-hover)] text-[var(--cc-text-primary)]">
            <Globe size={18} strokeWidth={1.75} />
          </div>
          <div>
            <div className="flex items-center gap-2">
              <h2 className="text-[18px] font-semibold text-[var(--cc-text-primary)]">
                Global Geo-Aware Costing Engine
              </h2>
              <Pill tone="blue">World Bank + OSM</Pill>
            </div>
            <p className="text-[13px] text-[var(--cc-text-secondary)]">
              Universal macroeconomic scaling for ANY country and ANY city worldwide with transparent formula and instant user overrides.
            </p>
          </div>
        </div>

        {/* Formula Box */}
        <div className="mt-6 rounded-[12px] border border-[var(--cc-border)] bg-[var(--cc-surface-sunken)] p-5 font-mono text-[14px] leading-relaxed">
          <div className="font-semibold text-[var(--cc-text-primary)]">
            Geo Multiplier = Country Multiplier (World Bank) × City Tier Multiplier (OSM)
          </div>
          <div className="mt-3 text-[12px] text-[var(--cc-text-secondary)] leading-6">
            <div className="font-medium text-[var(--cc-text-primary)]">1. Country Multiplier Formula:</div>
            <div className="pl-4 py-1">
              <code>country_mult = clamp((GDP_PPP / US_GDP_PPP)^0.6, 0.25, 1.10)</code>
              <br />
              <span className="text-[11px] text-[var(--cc-text-tertiary)]">
                * Live-queried from World Bank indicator <code>NY.GDP.PCAP.PP.CD</code> and cached 30 days in ClickHouse <code>geo_cost_index</code>.
              </span>
            </div>

            <div className="font-medium text-[var(--cc-text-primary)] mt-2">2. OSM City Tier Determination:</div>
            <div className="pl-4 space-y-0.5 text-[12px]">
              <div>• <span className="font-medium text-[var(--cc-text-primary)]">Tier 1 (1.00x):</span> Population ≥ 5,000,000 OR Sovereign Capital / Megacity (e.g. Mumbai, London, Tokyo, Lagos, Sao Paulo)</div>
              <div>• <span className="font-medium text-[var(--cc-text-primary)]">Tier 2 (0.50x):</span> Population 200,000 to 1,000,000 OR non-capital 1M–5M (e.g. Dharwad, Hubballi, Lyon, Valencia)</div>
              <div>• <span className="font-medium text-[var(--cc-text-primary)]">Tier 3 (0.35x):</span> Population &lt; 200,000 (Small towns, rural outposts, remote exterior terrain)</div>
            </div>

            <div className="font-medium text-[var(--cc-text-primary)] mt-2">3. Zero Live Latency Guarantee:</div>
            <div className="pl-4 text-[11px] text-[var(--cc-text-tertiary)]">
              Resolved ONCE upon location onboarding and persisted to the <code>locations</code> ClickHouse record. Agent investigation queries read local geo indices in 0ms (≤2.1s sacred SLA).
            </div>
          </div>
        </div>

        {/* Global Cities Benchmarks Table */}
        <div className="mt-6">
          <h3 className="text-[14px] font-semibold text-[var(--cc-text-primary)]">Global City Pricing Benchmarks</h3>
          <div className="mt-3 overflow-x-auto">
            <table className="w-full text-left text-[13px] border-collapse" data-testid="geo-cities-table">
              <thead>
                <tr className="border-b border-[var(--cc-border)] text-[12px] text-[var(--cc-text-secondary)]">
                  <th className="pb-3 font-medium">City</th>
                  <th className="pb-3 font-medium">Country</th>
                  <th className="pb-3 font-medium">City Tier</th>
                  <th className="pb-3 font-medium">Country Factor</th>
                  <th className="pb-3 font-medium">Compound Geo Mult</th>
                  <th className="pb-3 font-medium">Currency</th>
                  <th className="pb-3 font-medium">Posh Stage Example</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-[var(--cc-border)]">
                {GEO_EXAMPLE_CITIES.map((c) => (
                  <tr key={c.city} className="text-[var(--cc-text-primary)] hover:bg-[var(--cc-surface-hover)]">
                    <td className="py-3 font-semibold text-[var(--cc-text-primary)]">{c.city}</td>
                    <td className="py-3 text-[var(--cc-text-secondary)]">{c.country}</td>
                    <td className="py-3 font-mono text-[var(--cc-text-secondary)]">{c.tier}</td>
                    <td className="py-3 font-mono text-[var(--cc-text-secondary)]">{c.countryMult}</td>
                    <td className="py-3 font-mono font-semibold text-[var(--cc-text-primary)]">{c.geoMult}</td>
                    <td className="py-3 font-mono text-[var(--cc-text-secondary)]">{c.currency}</td>
                    <td className="py-3 font-mono font-medium text-[var(--cc-text-primary)]">{c.exampleFee}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      </div>

      {/* Cost Methodology Formula Card */}
      <div className="cc-card p-6 md:p-8">
        <div className="flex items-center gap-3.5">
          <div className="flex h-10 w-10 items-center justify-center rounded-[10px] border border-[var(--cc-border)] bg-[var(--cc-surface-hover)] text-[var(--cc-text-primary)]">
            <Layers size={18} strokeWidth={1.75} />
          </div>
          <div>
            <h2 className="text-[18px] font-semibold text-[var(--cc-text-primary)]">Grounded 70/30 Cost Calibration Model</h2>
            <p className="text-[13px] text-[var(--cc-text-secondary)]">
              Blends bottom-up rate cards with ClickHouse columnar aggregates to eliminate synthetic hallucination.
            </p>
          </div>
        </div>

        <div className="mt-6 rounded-[12px] border border-[var(--cc-border)] bg-[var(--cc-surface-sunken)] p-5 font-mono text-[14px] leading-relaxed">
          <div className="font-semibold text-[var(--cc-text-primary)]">Final Option Estimate ($) = 0.70 × Bottom-Up Cost + 0.30 × Historical MV Average</div>
          <div className="mt-3 text-[12px] text-[var(--cc-text-secondary)] leading-6">
            Where:
            <br />
            • <span className="font-medium text-[var(--cc-text-primary)]">Bottom-Up Cost</span> = (Crew Day Burn × Tier Rate × Geo Mult) + (Principal Cast Holding × Scale) + (Target Location Fee × Live FX × Geo Mult) + Equipment Days + Weather Contingency
            <br />
            • <span className="font-medium text-[var(--cc-text-primary)]">Historical MV Average</span> = Empirical average cost overrun from ClickHouse <code className="rounded bg-[var(--cc-surface)] border border-[var(--cc-border)] px-1.5 py-0.5 text-[var(--cc-text-primary)] font-medium">strategy_performance_mv</code> across 200,000+ past productions
          </div>
        </div>

        {/* Rate Card Benchmarks Table */}
        <div className="mt-6">
          <h3 className="text-[14px] font-semibold text-[var(--cc-text-primary)]">Industry Rate Card Benchmarks (Configurable)</h3>
          <div className="mt-3 overflow-x-auto">
            <table className="w-full text-left text-[13px] border-collapse">
              <thead>
                <tr className="border-b border-[var(--cc-border)] text-[12px] text-[var(--cc-text-secondary)]">
                  <th className="pb-3 font-medium">Production Tier</th>
                  <th className="pb-3 font-medium">Crew Burn Rate</th>
                  <th className="pb-3 font-medium">Lead Cast Scale</th>
                  <th className="pb-3 font-medium">Soundstage / Day</th>
                  <th className="pb-3 font-medium">Municipal Permit</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-[var(--cc-border)]">
                {RATE_CARD_BENCHMARKS.map((b) => (
                  <tr key={b.tier} className="text-[var(--cc-text-primary)] hover:bg-[var(--cc-surface-hover)]">
                    <td className="py-3 font-semibold text-[var(--cc-text-primary)]">{b.tier}</td>
                    <td className="py-3 font-mono text-[var(--cc-text-secondary)]">{b.crewDay}</td>
                    <td className="py-3 font-mono text-[var(--cc-text-secondary)]">{b.leadScale}</td>
                    <td className="py-3 font-mono text-[var(--cc-text-secondary)]">{b.soundstage}</td>
                    <td className="py-3 font-mono text-[var(--cc-text-secondary)]">{b.permit}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      </div>

      {/* Studio Tenant Ingestion & Cold-Start Blending Card */}
      <div className="cc-card p-6 md:p-8" data-testid="studio-blending-card">
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-3.5">
            <div className="flex h-10 w-10 items-center justify-center rounded-[10px] border border-[var(--cc-border)] bg-[var(--cc-surface-hover)] text-[var(--cc-text-primary)]">
              <Database size={18} strokeWidth={1.75} />
            </div>
            <div>
              <h2 className="text-[18px] font-semibold text-[var(--cc-text-primary)]">Studio Data Ingestion & Cold-Start Blending</h2>
              <p className="text-[13px] text-[var(--cc-text-secondary)]">
                Tenant-isolated ClickHouse storage with adaptive 200-sample cohort convergence.
              </p>
            </div>
          </div>
          <a
            href="/api/templates/disruption-history.csv"
            download="disruption-history-template.csv"
            className="hidden sm:flex items-center gap-1.5 rounded-[9px] border border-[var(--cc-border)] bg-[var(--cc-surface)] px-3 py-1.5 text-[12px] font-medium text-[var(--cc-text-primary)] shadow-sm hover:bg-[var(--cc-surface-hover)] cc-transition"
          >
            Download CSV Template
          </a>
        </div>

        <div className="mt-6 grid grid-cols-1 md:grid-cols-2 gap-5">
          <div className="rounded-[12px] border border-[var(--cc-border)] bg-[var(--cc-surface-sunken)] p-5 font-mono text-[13px] leading-relaxed">
            <div className="font-semibold text-[var(--cc-text-primary)]">Cold-Start Weighting Function</div>
            <div className="mt-2 text-[12px] text-[var(--cc-text-secondary)] space-y-2">
              <div>
                • <span className="font-medium text-[var(--cc-text-primary)]">If N &lt; 200:</span> weight <code className="bg-[var(--cc-surface)] px-1 rounded">w = N / 200</code>
              </div>
              <div>
                • <span className="font-medium text-[var(--cc-text-primary)]">Blended Metric:</span> <code className="bg-[var(--cc-surface)] px-1 rounded">(w × Studio_Avg) + ((1 - w) × Global_Avg)</code>
              </div>
              <div>
                • <span className="font-medium text-[var(--cc-text-primary)]">If N &ge; 200:</span> 100% Studio Cohort (<code className="bg-[var(--cc-surface)] px-1 rounded">w = 1.0</code>)
              </div>
            </div>
          </div>

          <div className="rounded-[12px] border border-[var(--cc-border)] bg-[var(--cc-surface-sunken)] p-5 text-[13px] leading-relaxed text-[var(--cc-text-secondary)]">
            <div className="font-semibold text-[var(--cc-text-primary)] mb-1.5">Tenant Isolation & Privacy Guarantee</div>
            <p>
              Imported rows are tagged with your unique <code className="font-mono text-[var(--cc-text-primary)]">studio_id</code>.
              Your past disruption costs, vendor fees, and delay logs are strictly quarantined in ClickHouse.
              Other studios only access the anonymized global industry baseline.
            </p>
          </div>
        </div>
      </div>

      {/* External Data Sources Grid */}
      <div>
        <h2 className="text-[20px] font-semibold text-[var(--cc-text-primary)]">Live External Data Sources</h2>
        <p className="mt-1 text-[13px] text-[var(--cc-text-secondary)]">
          Real-time and cached signals queried during agent investigation under strict 3.0s SLA timeouts.
        </p>

        <div className="mt-5 grid grid-cols-1 gap-6 md:grid-cols-2">
          {DATA_SOURCES.map((src) => {
            const Icon = ICON_MAP[src.icon] || Database;
            return (
              <div key={src.id} className="cc-card flex flex-col justify-between p-6">
                <div className="space-y-4">
                  <div className="flex items-start justify-between">
                    <div className="flex items-center gap-3">
                      <div className="flex h-10 w-10 items-center justify-center rounded-[10px] border border-[var(--cc-border)] bg-[var(--cc-surface-hover)] text-[var(--cc-text-primary)]">
                        <Icon size={18} strokeWidth={1.75} />
                      </div>
                      <div>
                        <h3 className="font-semibold text-[15px] text-[var(--cc-text-primary)]">{src.name}</h3>
                        <p className="text-[12px] text-[var(--cc-text-tertiary)]">{src.provider}</p>
                      </div>
                    </div>
                    {src.attributionUrl && (
                      <a
                        href={src.attributionUrl}
                        target="_blank"
                        rel="noreferrer"
                        className="text-[var(--cc-text-secondary)] hover:text-[var(--cc-text-primary)] cc-transition"
                      >
                        <ExternalLink size={14} />
                      </a>
                    )}
                  </div>

                  <p className="text-[13px] font-medium text-[var(--cc-text-primary)]">{src.tagline}</p>

                  <div className="space-y-2 text-[12px] text-[var(--cc-text-secondary)] leading-relaxed">
                    <div>
                      <span className="font-semibold text-[var(--cc-text-primary)]">What we fetch:</span>{" "}
                      {src.whatWeFetch}
                    </div>
                    <div>
                      <span className="font-semibold text-[var(--cc-text-primary)]">How it impacts agents:</span>{" "}
                      {src.howUsed}
                    </div>
                    <div>
                      <span className="font-semibold text-[var(--cc-text-primary)]">Caching & Hardening:</span>{" "}
                      {src.cacheTtl} · {src.timeout}
                    </div>
                    <div>
                      <span className="font-semibold text-[var(--cc-text-primary)]">Fallback behavior:</span>{" "}
                      {src.fallback}
                    </div>
                  </div>
                </div>

                <div className="mt-4 pt-3 border-t border-[var(--cc-border)] flex items-center justify-between text-[11px] text-[var(--cc-text-tertiary)]">
                  <span>{src.attribution}</span>
                </div>
              </div>
            );
          })}
        </div>
      </div>
    </div>
  );
}
