import React, { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import { Button } from "../components/ui/button";
import { Skeleton } from "../components/ui/skeleton";
import { MonoPill, Pill } from "../components/badges";
import { getAudit, getHealth, fmtMoney, fmtHours, sentenceCase } from "../lib/api";
import { useProduction } from "../context/ProductionContext";
import { dayLabel } from "../lib/days";
import { ScrollText, Copy, Check, ChevronDown, ArrowRight } from "lucide-react";

export default function DecisionLedgerPage() {
  const navigate = useNavigate();
  const { selectedId, selected } = useProduction();
  const [audit, setAudit] = useState(null);
  const [error, setError] = useState(null);
  const [expanded, setExpanded] = useState(null);

  useEffect(() => {
    if (!selectedId) return;
    setAudit(null);
    setError(null);
    getHealth()
      .then((health) => {
        if (!health?.clickhouse?.connected) throw new Error("ClickHouse Cloud is not connected. Add credentials to load the ledger.");
        return getAudit(selectedId);
      })
      .then(setAudit)
      .catch((e) => setError(e?.response?.data?.detail || e.message || "Could not load the ledger."));
  }, [selectedId]);

  if (error) {
    return (
      <div className="cc-card mx-auto mt-16 max-w-md p-8 text-center">
        <ScrollText size={26} strokeWidth={1.5} className="mx-auto text-[var(--cc-text-tertiary)]" />
        <h2 className="font-display mt-4 text-[17px] font-semibold text-[var(--cc-text-primary)]">Ledger unavailable</h2>
        <p className="mt-1 text-[13px] text-[var(--cc-text-secondary)]">{String(error)}</p>
        <Button type="button" onClick={() => window.location.reload()} className="mt-5 rounded-[10px]">Try again</Button>
      </div>
    );
  }

  if (!audit) {
    return (
      <div className="space-y-4">
        <Skeleton className="cc-shimmer h-16 w-full" />
        <Skeleton className="cc-shimmer h-64 w-full" />
      </div>
    );
  }

  const changesByDecision = {};
  (audit.schedule_changes || []).forEach((c) => {
    (changesByDecision[c.decision_id] = changesByDecision[c.decision_id] || []).push(c);
  });

  const th = "px-5 pb-3 text-left text-[12px] font-medium text-[var(--cc-text-secondary)]";

  return (
    <div className="cc-fade-up space-y-8" data-testid="decision-ledger-page">
      <div className="flex flex-wrap items-end justify-between gap-4">
        <div>
          <div className="text-[12px] font-semibold uppercase tracking-wider text-[var(--cc-text-tertiary)]">
            Audit trail
          </div>
          <h1 className="font-display mt-1 text-[30px] font-semibold leading-tight tracking-tight text-[var(--cc-text-primary)]">
            Decision ledger
          </h1>
          <p className="mt-1.5 text-[14px] text-[var(--cc-text-secondary)]">
            The immutable record of every approved recovery decision, written to ClickHouse.
          </p>
        </div>
        <MonoPill tone="neutral">continuity_council.decision_ledger</MonoPill>
      </div>

      <div className="cc-card overflow-hidden">
        <div className="overflow-x-auto">
          <table data-testid="decision-ledger-table" className="w-full border-collapse">
            <thead>
              <tr className="border-b border-[var(--cc-border)]">
                <th className={`${th} pt-4`}>Decision</th>
                <th className={`${th} pt-4`}>Case</th>
                <th className={`${th} pt-4`}>Disruption</th>
                <th className={`${th} pt-4`}>Selected option</th>
                <th className={`${th} pt-4 text-right`}>Est. cost</th>
                <th className={`${th} pt-4 text-right`}>Est. delay</th>
                <th className={`${th} pt-4`}>Approved by</th>
                <th className={`${th} pt-4 text-right`}>Timestamp</th>
                <th className="w-10 pt-4" />
              </tr>
            </thead>
            <tbody>
              {audit.decisions.length === 0 && (
                <tr>
                  <td colSpan={9} className="border-t border-[var(--cc-border)] py-12 text-center text-[13px] text-[var(--cc-text-secondary)]">
                    <div>No decisions recorded yet. Approve a recovery option to write the first ledger entry.</div>
                    <Button type="button" onClick={() => navigate("/report")} className="mt-4 rounded-[10px]">Report disruption</Button>
                  </td>
                </tr>
              )}
              {audit.decisions.map((d) => (
                <React.Fragment key={d.decision_id}>
                  <tr
                    data-testid={`ledger-row-${d.decision_id}`}
                    className="cc-transition h-[52px] cursor-pointer border-b border-[var(--cc-border)] hover:bg-[var(--cc-surface-hover)]"
                    onClick={() => setExpanded(expanded === d.decision_id ? null : d.decision_id)}
                  >
                    <td className="px-5"><DecisionId id={d.decision_id} /></td>
                    <td className="px-5 font-mono text-xs text-[var(--cc-text-secondary)]">{d.case_id}</td>
                    <td className="px-5 text-[13px] text-[var(--cc-text-primary)]">{sentenceCase(d.disruption_type)}</td>
                    <td className="px-5"><MonoPill tone="neutral">{d.selected_option}</MonoPill></td>
                    <td className="tabular px-5 text-right text-[14px] font-semibold text-[var(--cc-text-primary)]">{fmtMoney(d.estimated_cost_usd)}</td>
                    <td className="tabular px-5 text-right text-[13px] text-[var(--cc-text-secondary)]">{fmtHours(d.estimated_delay_hours)}</td>
                    <td className="px-5"><Pill tone="gray">{d.approved_by}</Pill></td>
                    <td className="tabular px-5 text-right font-mono text-xs text-[var(--cc-text-secondary)]">
                      {new Date(d.approved_at + "Z").toLocaleString("en-US", { hour12: false })}
                    </td>
                    <td className="px-4">
                      <ChevronDown
                        size={14}
                        className={`cc-transition text-[var(--cc-text-tertiary)] ${expanded === d.decision_id ? "rotate-180" : ""}`}
                      />
                    </td>
                  </tr>
                  {expanded === d.decision_id && (
                    <tr className="border-b border-[var(--cc-border)] bg-[var(--cc-surface-sunken)]/60">
                      <td colSpan={9} className="px-8 py-6">
                        <ExpandedDecision d={d} changes={changesByDecision[d.decision_id] || []} production={selected} />
                      </td>
                    </tr>
                  )}
                </React.Fragment>
              ))}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  );
}

const DecisionId = ({ id }) => {
  const [copied, setCopied] = useState(false);
  return (
    <span className="flex items-center gap-1.5">
      <span className="font-mono text-xs font-semibold text-[var(--cc-text-primary)]">{id}</span>
      <Button
        variant="ghost"
        size="sm"
        data-testid={`copy-decision-${id}`}
        className="h-6 w-6 rounded-[6px] p-0 text-[var(--cc-text-tertiary)] hover:bg-[var(--cc-surface-hover)] hover:text-[var(--cc-text-primary)]"
        onClick={async (e) => {
          e.stopPropagation();
          try {
            await navigator.clipboard.writeText(id);
            setCopied(true);
            setTimeout(() => setCopied(false), 1200);
          } catch { /* noop */ }
        }}
      >
        {copied ? <Check size={11} /> : <Copy size={11} />}
      </Button>
    </span>
  );
};

const ExpandedDecision = ({ d, changes, production }) => {
  let evidence = null;
  try {
    evidence = JSON.parse(d.evidence_json);
  } catch { /* noop */ }

  return (
    <div className="grid grid-cols-12 gap-8" data-testid="ledger-expanded-detail">
      <div className="col-span-12 lg:col-span-6">
        <div className="text-[13px] font-semibold text-[var(--cc-text-primary)]">Option summary</div>
        <p className="mt-1 text-[13px] leading-relaxed text-[var(--cc-text-secondary)]">{d.option_summary}</p>
        {evidence?.narrative && (
          <>
            <div className="mt-5 text-[13px] font-semibold text-[var(--cc-text-primary)]">Evidence summary (ClickHouse)</div>
            <p className="mt-1 text-[13px] leading-relaxed text-[var(--cc-text-secondary)]">{evidence.narrative}</p>
          </>
        )}
        <div className="tabular mt-4 flex flex-wrap gap-5 font-mono text-[11px] text-[var(--cc-text-tertiary)]">
          <span>continuity risk {d.continuity_risk_score.toFixed(2)}</span>
          <span>compliance risk {d.compliance_risk_score.toFixed(2)}</span>
          {evidence?.mcp_calls?.length ? <span>{evidence.mcp_calls.length} MCP calls</span> : null}
        </div>
      </div>
      <div className="col-span-12 lg:col-span-6">
        <div className="text-[13px] font-semibold text-[var(--cc-text-primary)]">
          Schedule changes ({changes.length})
        </div>
        <div className="mt-2 space-y-1.5">
          {changes.length === 0 && <p className="text-[13px] text-[var(--cc-text-secondary)]">No scene moves for this decision.</p>}
          {changes.map((c) => (
            <div key={c.change_id} className="flex h-10 items-center justify-between rounded-[8px] border border-[var(--cc-border)] bg-[var(--cc-surface)] px-4 font-mono text-[11px]">
              <span className="text-[var(--cc-text-primary)] font-medium">{c.scene_id}</span>
              <span className="tabular flex items-center gap-1.5 text-[var(--cc-text-secondary)]">
                <span className="text-[var(--cc-text-primary)]">{dayLabel(production, c.old_shoot_day)}</span>
                <ArrowRight size={10} />
                <span className="text-[var(--cc-green-text)] font-medium">{dayLabel(production, c.new_shoot_day)}</span>
                <Pill tone="gray" className="ml-2">{c.change_type.replace(/_/g, " ")}</Pill>
              </span>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
};
