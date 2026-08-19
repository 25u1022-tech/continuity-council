import React from "react";
import { DATA_SOURCES, SIGNAL_IMPACTS, RATE_CARD_BENCHMARKS } from "../lib/dataSources";
import { Pill } from "../components/badges";
import {
  Database,
  CloudRain,
  MapPin,
  Coins,
  ShieldCheck,
  Layers,
  ExternalLink,
} from "lucide-react";

const ICON_MAP = {
  CloudRain: CloudRain,
  MapPin: MapPin,
  Coins: Coins,
  Database: Database,
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
          Continuity Council combines ClickHouse Cloud analytical history with live environmental,
          geographic, and currency signals to generate empirical, rate-card grounded recovery options.
        </p>
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
            • <span className="font-medium text-[var(--cc-text-primary)]">Bottom-Up Cost</span> = (Crew Day Burn × Tier Rate) + (Principal Cast Holding × Scale) + (Target Location Fee × Live FX) + Equipment Days + Weather Contingency
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
                        <h3 className="text-[16px] font-semibold text-[var(--cc-text-primary)]">{src.name}</h3>
                        <p className="text-[12px] text-[var(--cc-text-secondary)]">{src.tagline}</p>
                      </div>
                    </div>
                  </div>

                  <div className="space-y-2 text-[13px] text-[var(--cc-text-secondary)]">
                    <div>
                      <span className="font-medium text-[var(--cc-text-primary)]">What we fetch: </span>
                      {src.whatWeFetch}
                    </div>
                    <div>
                      <span className="font-medium text-[var(--cc-text-primary)]">Agent integration: </span>
                      {src.howUsed}
                    </div>
                  </div>

                  <div className="grid grid-cols-2 gap-2 pt-2 text-[11px] font-mono">
                    <div className="rounded-[8px] border border-[var(--cc-border)] bg-[var(--cc-surface-sunken)] p-2.5">
                      <div className="text-[var(--cc-text-tertiary)]">Cache TTL</div>
                      <div className="mt-0.5 font-medium text-[var(--cc-text-primary)]">{src.cacheTtl}</div>
                    </div>
                    <div className="rounded-[8px] border border-[var(--cc-border)] bg-[var(--cc-surface-sunken)] p-2.5">
                      <div className="text-[var(--cc-text-tertiary)]">SLA & Timeout</div>
                      <div className="mt-0.5 font-medium text-[var(--cc-text-primary)]">{src.timeout}</div>
                    </div>
                  </div>
                </div>

                <div className="mt-6 flex items-center justify-between border-t border-[var(--cc-border)] pt-4 text-[12px]">
                  <a
                    href={src.attributionUrl}
                    target="_blank"
                    rel="noreferrer"
                    className="flex items-center gap-1.5 font-medium text-[var(--cc-text-secondary)] hover:text-[var(--cc-text-primary)]"
                  >
                    <span>{src.attribution}</span>
                    <ExternalLink size={12} />
                  </a>
                  <Pill tone="green">Active</Pill>
                </div>
              </div>
            );
          })}
        </div>
      </div>

      {/* Signal Impact Matrix */}
      <div className="cc-card p-6 md:p-8">
        <h2 className="text-[18px] font-semibold text-[var(--cc-text-primary)]">How External Signals Drive Council Decisions</h2>
        <p className="mt-1 text-[13px] text-[var(--cc-text-secondary)]">
          Every signal feeds directly into specialist agents with zero hallucination.
        </p>

        <div className="mt-6 divide-y divide-[var(--cc-border)]">
          {SIGNAL_IMPACTS.map((sig, idx) => (
            <div key={idx} className="grid grid-cols-12 gap-4 py-4 text-[13px] first:pt-0 last:pb-0">
              <div className="col-span-12 font-semibold text-[var(--cc-text-primary)] md:col-span-4">
                {sig.signal}
              </div>
              <div className="col-span-12 font-mono text-[12px] text-[var(--cc-text-secondary)] md:col-span-3">
                {sig.affectedAgent}
              </div>
              <div className="col-span-12 text-[var(--cc-text-secondary)] md:col-span-5">
                {sig.impactDescription}
              </div>
            </div>
          ))}
        </div>
      </div>

      {/* Resilience & Offline Fallback Architecture */}
      <div className="cc-card p-6">
        <div className="flex items-start gap-3.5">
          <ShieldCheck size={22} className="text-[var(--cc-green-dot)] shrink-0 mt-0.5" />
          <div>
            <h3 className="text-[16px] font-semibold text-[var(--cc-text-primary)]">15-Second Resilience Guarantee</h3>
            <p className="mt-1 text-[13px] leading-relaxed text-[var(--cc-text-secondary)]">
              All external HTTP calls are guarded by strict 3.0s timeouts, in-memory TTL caching, and deterministic fallback models.
              If any external API is down or throttled, the council falls back to calibrated climate and FX baselines seamlessly,
              ensuring the 15-second investigation SLA is never breached.
            </p>
          </div>
        </div>
      </div>
    </div>
  );
}
