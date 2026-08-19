import React, { useState } from "react";
import { MonoPill } from "./badges";
import { EvidenceDrilldown } from "./EvidenceDrilldown";
import { fmtMoney, fmtHours, sentenceCase } from "../lib/api";
import { Database, ChevronRight } from "lucide-react";

/**
 * Historical Evidence (ClickHouse) — Apple Health-style horizontal metric bars.
 * Clean, hairline dividers, high contrast data labels.
 */
export const EvidenceTable = ({ rows = [], narrative = "", mcpCalls = [], disruptionType = "", severity = "" }) => {
  const [drill, setDrill] = useState(null);
  const okCalls = mcpCalls.filter((c) => c.status === "success");
  const avgLatency = okCalls.length
    ? Math.round(okCalls.reduce((a, c) => a + c.latency_ms, 0) / okCalls.length)
    : null;
  const totalCases = rows.reduce((a, r) => a + (r.past_cases || 0), 0);
  const maxCost = Math.max(...rows.map((r) => r.avg_cost_overrun_usd || 0), 1);
  const maxDelay = Math.max(...rows.map((r) => r.avg_delay_hours || 0), 1);

  return (
    <div data-testid="clickhouse-evidence-table" className="cc-card overflow-hidden">
      <div className="flex items-center justify-between gap-2 border-b border-[var(--cc-border)] px-6 py-4">
        <div className="flex items-center gap-2.5">
          <Database size={15} strokeWidth={1.75} className="text-[var(--cc-text-primary)]" />
          <span className="font-display text-[15px] font-semibold text-[var(--cc-text-primary)]">
            Historical Evidence (ClickHouse)
          </span>
        </div>
        <MonoPill tone="neutral">{totalCases.toLocaleString()} past cases</MonoPill>
      </div>

      {narrative ? (
        <p
          data-testid="evidence-narrative"
          className="border-b border-[var(--cc-border)] px-6 py-4 text-[13px] leading-relaxed text-[var(--cc-text-secondary)]"
        >
          {narrative}
        </p>
      ) : null}

      <div className="space-y-4 px-6 py-5">
        {rows.length === 0 && (
          <p className="py-4 text-center text-[13px] text-[var(--cc-text-secondary)]">No evidence rows returned.</p>
        )}
        {rows.map((r, idx) => (
          <button
            type="button"
            key={r.resolution_strategy}
            data-testid={`evidence-row-${r.resolution_strategy}`}
            onClick={() => disruptionType && setDrill(r.resolution_strategy)}
            disabled={!disruptionType}
            className="cc-transition group block w-full rounded-[10px] p-2 text-left hover:bg-[var(--cc-surface-hover)] focus-visible:bg-[var(--cc-surface-hover)] focus-visible:outline-none disabled:cursor-default disabled:hover:bg-transparent"
            aria-label={`Inspect raw ClickHouse rows for ${sentenceCase(r.resolution_strategy)}`}
          >
            <div className="flex items-baseline justify-between">
              <span className="flex items-center gap-1 text-[13px] font-medium text-[var(--cc-text-primary)]">
                {sentenceCase(r.resolution_strategy)}
                {disruptionType && (
                  <ChevronRight
                    size={12}
                    strokeWidth={1.8}
                    className="cc-transition text-[var(--cc-text-tertiary)] opacity-0 group-hover:opacity-100 group-focus-visible:opacity-100"
                  />
                )}
              </span>
              <span className="tabular text-[11px] text-[var(--cc-text-secondary)]">
                {r.past_cases.toLocaleString()} cases · {(r.avg_success_score * 100).toFixed(0)}% success
              </span>
            </div>
            {/* cost bar */}
            <div className="mt-2 flex items-center gap-3">
              <div className="h-[6px] flex-1 overflow-hidden rounded-full bg-[var(--cc-surface-sunken)] border border-[var(--cc-border-subtle)]">
                <div
                  className="cc-bar-in h-full rounded-full bg-[var(--cc-text-primary)]"
                  style={{
                    width: `${Math.max(4, (r.avg_cost_overrun_usd / maxCost) * 100)}%`,
                    animationDelay: `${idx * 70}ms`,
                  }}
                />
              </div>
              <span className="w-[84px] shrink-0 text-right tabular text-[13px] font-semibold text-[var(--cc-text-primary)]">
                {fmtMoney(r.avg_cost_overrun_usd)}
              </span>
            </div>
            {/* delay bar */}
            <div className="mt-1.5 flex items-center gap-3">
              <div className="h-[3px] flex-1 overflow-hidden rounded-full bg-[var(--cc-surface-sunken)]">
                <div
                  className="cc-bar-in h-full rounded-full bg-[var(--cc-text-tertiary)]"
                  style={{
                    width: `${Math.max(3, (r.avg_delay_hours / maxDelay) * 100)}%`,
                    animationDelay: `${idx * 70 + 60}ms`,
                  }}
                />
              </div>
              <span className="w-[84px] shrink-0 text-right tabular text-[11px] text-[var(--cc-text-secondary)]">
                {fmtHours(r.avg_delay_hours)}
              </span>
            </div>
          </button>
        ))}
      </div>

      {/* Blended Cohort Footnote */}
      {(rows[0]?.footnote || rows[0]?.is_blended) && (
        <div className="border-t border-[var(--cc-border)] px-6 py-2.5 bg-[var(--cc-yellow-bg)] text-[var(--cc-yellow-text)] text-[12px] flex items-center justify-between">
          <span>{rows[0]?.footnote || "blended with industry baseline"}</span>
          <span className="font-mono text-[11px]">Cold-Start Weight: {rows[0]?.blend_weight ? `${(rows[0].blend_weight * 100).toFixed(0)}%` : "Active"}</span>
        </div>
      )}

      {okCalls.length > 0 && (
        <div className="border-t border-[var(--cc-border)] px-6 py-3 text-[11px] text-[var(--cc-text-secondary)] bg-[var(--cc-surface-sunken)]/50 flex items-center justify-between">
          <div>
            Queried live via mcp-clickhouse · {okCalls.length} call{okCalls.length !== 1 ? "s" : ""}
            {avgLatency !== null ? ` · ${avgLatency} ms average` : ""}
            {disruptionType ? " · click a strategy to inspect raw rows" : ""}
          </div>
          {rows[0]?.studio_id && rows[0].studio_id !== "global" && (
            <span className="font-mono text-[10px] text-[var(--cc-text-tertiary)]">
              Cohort: {rows[0].studio_id}
            </span>
          )}
        </div>
      )}

      <EvidenceDrilldown
        open={!!drill}
        onOpenChange={(v) => !v && setDrill(null)}
        strategy={drill || ""}
        disruptionType={disruptionType}
        severity={severity}
      />
    </div>
  );
};
