import React, { useCallback, useEffect, useState } from "react";
import {
  Dialog, DialogContent, DialogHeader, DialogTitle, DialogDescription,
} from "./ui/dialog";
import { Button } from "./ui/button";
import { Skeleton } from "./ui/skeleton";
import { MonoPill } from "./badges";
import { getEvidenceDrilldown, fmtMoney, sentenceCase } from "../lib/api";
import { Database, ChevronDown, TriangleAlert, RotateCw } from "lucide-react";

/**
 * Evidence Drilldown — Apple-style sheet showing the raw ClickHouse rows
 * behind one historical evidence bar (disruption_type × resolution_strategy).
 */

const sevTone = {
  high: "bg-[var(--cc-red-bg)] text-[var(--cc-red-text)]",
  medium: "bg-[var(--cc-yellow-bg)] text-[var(--cc-yellow-text)]",
  low: "bg-[var(--cc-green-bg)] text-[var(--cc-green-text)]",
};

const fmtDate = (iso) => {
  if (!iso) return "—";
  const d = new Date(iso);
  return d.toLocaleDateString("en-US", { month: "short", day: "numeric", year: "numeric" });
};

export const EvidenceDrilldown = ({ open, onOpenChange, strategy, disruptionType, severity }) => {
  const [state, setState] = useState({ loading: false, error: null, data: null });
  const [showSql, setShowSql] = useState(false);

  const fetchRows = useCallback(async () => {
    if (!strategy || !disruptionType) return;
    setState({ loading: true, error: null, data: null });
    try {
      const data = await getEvidenceDrilldown(disruptionType, strategy, severity, 40);
      setState({ loading: false, error: null, data });
    } catch (e) {
      setState({ loading: false, error: e?.response?.data?.detail || e.message || "Query failed", data: null });
    }
  }, [strategy, disruptionType, severity]);

  useEffect(() => {
    if (open) {
      setShowSql(false);
      fetchRows();
    }
  }, [open, fetchRows]);

  const meta = state.data?.query_meta;
  const prov = state.data?.provenance;
  const rows = state.data?.rows || [];

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent
        data-testid="evidence-drilldown-modal"
        className="cc-card max-h-[82vh] w-[92vw] max-w-3xl overflow-hidden border border-[var(--cc-border)] p-0 shadow-xl"
      >
        <DialogHeader className="border-b border-[var(--cc-border)] space-y-1.5 px-6 pb-4 pt-6 text-left">
          <div className="flex items-center gap-2.5">
            <Database size={16} strokeWidth={1.75} className="text-[var(--cc-text-primary)]" />
            <DialogTitle className="font-display text-[17px] font-semibold tracking-tight text-[var(--cc-text-primary)]">
              {sentenceCase(strategy)} — raw evidence rows
            </DialogTitle>
          </div>
          <DialogDescription className="text-[13px] text-[var(--cc-text-secondary)]">
            The individual ClickHouse history rows this evidence bar is built from ·{" "}
            {sentenceCase(disruptionType)}{severity ? ` · ${sentenceCase(severity)} severity` : ""}
          </DialogDescription>
        </DialogHeader>

        {/* Provenance strip */}
        <div
          data-testid="evidence-drilldown-provenance"
          className="border-b border-[var(--cc-border)] flex flex-wrap items-center gap-2 px-6 py-3 bg-[var(--cc-surface-hover)]"
        >
          <MonoPill tone="neutral">{prov?.source || "ClickHouse Cloud (live)"}</MonoPill>
          <span className="font-mono text-[11px] text-[var(--cc-text-tertiary)]">
            {(prov?.database || "continuity_council")}.{prov?.table || "disruption_history"}
          </span>
          {meta && (
            <span className="tabular font-mono text-[11px] text-[var(--cc-text-secondary)]">
              {meta.row_count} rows · {meta.latency_ms} ms
            </span>
          )}
          {meta?.sql && (
            <button
              type="button"
              data-testid="evidence-drilldown-sql-toggle"
              onClick={() => setShowSql((s) => !s)}
              className="cc-transition ml-auto flex items-center gap-1 text-[11px] font-medium text-[var(--cc-text-secondary)] hover:text-[var(--cc-text-primary)]"
            >
              <ChevronDown size={11} className={`cc-transition ${showSql ? "rotate-180" : ""}`} />
              Show query
            </button>
          )}
        </div>

        {showSql && meta?.sql && (
          <pre
            data-testid="evidence-drilldown-sql"
            className="border-b border-[var(--cc-border)] whitespace-pre-wrap break-words bg-[var(--cc-surface-sunken)] px-6 py-3 font-mono text-[11px] leading-5 text-[var(--cc-text-secondary)]"
          >
            {meta.sql}
          </pre>
        )}

        {/* Body */}
        <div className="overflow-y-auto px-6 pb-6" style={{ maxHeight: "48vh" }}>
          {state.loading && (
            <div className="space-y-2.5 pt-4" data-testid="evidence-drilldown-loading">
              {[...Array(6)].map((_, i) => (
                <Skeleton key={i} className="h-9 w-full rounded-[8px]" />
              ))}
            </div>
          )}

          {state.error && (
            <div className="py-10 text-center" data-testid="evidence-drilldown-error">
              <TriangleAlert size={20} strokeWidth={1.5} className="mx-auto text-[var(--cc-red-dot)]" />
              <p className="mt-3 text-[13px] text-[var(--cc-text-secondary)]">{state.error}</p>
              <Button
                data-testid="evidence-drilldown-retry"
                size="sm"
                variant="outline"
                onClick={fetchRows}
                className="mt-4 gap-1.5 rounded-[10px]"
              >
                <RotateCw size={12} /> Retry query
              </Button>
            </div>
          )}

          {!state.loading && !state.error && rows.length === 0 && (
            <p className="py-10 text-center text-[13px] text-[var(--cc-text-secondary)]" data-testid="evidence-drilldown-empty">
              No matching history rows in ClickHouse.
            </p>
          )}

          {!state.loading && !state.error && rows.length > 0 && (
            <table className="w-full border-collapse" data-testid="evidence-drilldown-table">
              <thead>
                <tr className="border-b border-[var(--cc-border)] text-left text-[11px] text-[var(--cc-text-secondary)]">
                  <th className="py-2.5 pr-3 font-medium">Case</th>
                  <th className="py-2.5 pr-3 font-medium">Severity</th>
                  <th className="py-2.5 pr-3 text-right font-medium">Scenes</th>
                  <th className="py-2.5 pr-3 text-right font-medium">Cost overrun</th>
                  <th className="py-2.5 pr-3 text-right font-medium">Delay</th>
                  <th className="py-2.5 pr-3 text-right font-medium">Success</th>
                  <th className="py-2.5 text-right font-medium">Date</th>
                </tr>
              </thead>
              <tbody>
                {rows.map((r, i) => (
                  <tr
                    key={r.disruption_id || i}
                    data-testid={`evidence-drilldown-row-${i}`}
                    className="cc-transition border-b border-[var(--cc-border)] last:border-b-0 hover:bg-[var(--cc-surface-hover)]"
                    title={r.notes || ""}
                  >
                    <td className="py-2.5 pr-3 font-mono text-[11px] text-[var(--cc-text-secondary)]">{r.disruption_id}</td>
                    <td className="py-2.5 pr-3">
                      <span className={`rounded-full px-2 py-0.5 text-[10px] font-medium ${sevTone[r.severity] || "bg-[var(--cc-gray-bg)] text-[var(--cc-gray-text)]"}`}>
                        {sentenceCase(r.severity)}
                      </span>
                    </td>
                    <td className="tabular py-2.5 pr-3 text-right text-[12px] text-[var(--cc-text-primary)]">{r.affected_scene_count}</td>
                    <td className="tabular py-2.5 pr-3 text-right text-[12px] font-medium text-[var(--cc-text-primary)]">
                      {fmtMoney(r.cost_overrun_usd)}
                    </td>
                    <td className="tabular py-2.5 pr-3 text-right text-[12px] text-[var(--cc-text-secondary)]">
                      {Number(r.schedule_delay_hours).toFixed(1)}h
                    </td>
                    <td className="tabular py-2.5 pr-3 text-right text-[12px] text-[var(--cc-text-secondary)]">
                      {(Number(r.success_score) * 100).toFixed(0)}%
                    </td>
                    <td className="tabular py-2.5 text-right font-mono text-[11px] text-[var(--cc-text-tertiary)]">
                      {fmtDate(r.created_at)}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          )}
        </div>
      </DialogContent>
    </Dialog>
  );
};
