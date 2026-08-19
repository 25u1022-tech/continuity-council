import React from "react";
import { Check, TriangleAlert } from "lucide-react";
import { Pill } from "./badges";

const AGENT_BLURB = {
  orchestrator: "Coordinates the council, merges findings, ranks options",
  schedule_optimizer: "Rearranges scenes, days and locations",
  budget_sentinel: "Queries ClickHouse history via MCP for cost evidence",
  continuity_memory: "Guards costume, narrative and emotional continuity",
  compliance: "Validates availability, day limits and working hours",
  auditor: "Writes the immutable decision ledger",
};

const AGENT_ORDER = [
  "orchestrator",
  "schedule_optimizer",
  "budget_sentinel",
  "continuity_memory",
  "compliance",
  "auditor",
];

const Dot = ({ status }) => {
  if (status === "complete")
    return (
      <span className="flex h-[22px] w-[22px] items-center justify-center rounded-full bg-[var(--cc-green-bg)]">
        <Check size={12} strokeWidth={2.4} className="text-[var(--cc-green-dot)]" />
      </span>
    );
  if (status === "running")
    return (
      <span className="cc-ring-pulse flex h-[22px] w-[22px] items-center justify-center rounded-full bg-[var(--cc-yellow-bg)]">
        <span className="cc-pulse-dot h-2 w-2 rounded-full bg-[var(--cc-yellow-dot)]" />
      </span>
    );
  if (status === "error")
    return (
      <span className="flex h-[22px] w-[22px] items-center justify-center rounded-full bg-[var(--cc-red-bg)]">
        <TriangleAlert size={11} className="text-[var(--cc-red-dot)]" />
      </span>
    );
  return (
    <span className="flex h-[22px] w-[22px] items-center justify-center rounded-full bg-[var(--cc-surface-hover)] border border-[var(--cc-border)]">
      <span className="h-1.5 w-1.5 rounded-full bg-[var(--cc-text-quaternary)]" />
    </span>
  );
};

const StatePill = ({ status, durationMs }) => {
  if (status === "running") return <Pill tone="yellow">Running</Pill>;
  if (status === "complete")
    return (
      <Pill tone="green">
        Done{durationMs ? <span className="tabular">{` · ${(durationMs / 1000).toFixed(1)}s`}</span> : ""}
      </Pill>
    );
  if (status === "error") return <Pill tone="red">Error</Pill>;
  return <Pill tone="gray">Waiting</Pill>;
};

/** Elegant vertical timeline of the six agents. Quiet, Apple Minimalist aesthetic. */
export const AgentTimeline = ({ agents }) => (
  <div className="cc-card p-3 md:p-4" data-testid="agent-timeline">
    {AGENT_ORDER.map((key, idx) => {
      const a = agents?.[key];
      if (!a) return null;
      const isLast = idx === AGENT_ORDER.length - 1;
      return (
        <div
          key={key}
          data-testid={`agent-status-${key.replace(/_/g, "-")}-card`}
          className="cc-transition relative flex gap-4 rounded-[10px] px-3 py-3.5 hover:bg-[var(--cc-surface-hover)]"
        >
          {/* timeline spine */}
          <div className="relative flex w-[22px] shrink-0 flex-col items-center">
            <Dot status={a.status} />
            {!isLast && (
              <span
                className={`mt-1 w-px flex-1 ${
                  a.status === "complete" ? "bg-[var(--cc-green-dot)]/30" : "bg-[var(--cc-border)]"
                }`}
              />
            )}
          </div>

          <div className="min-w-0 flex-1 pb-1">
            <div className="flex items-center justify-between gap-3">
              <div className="flex items-baseline gap-2.5">
                <span className="text-[14px] font-semibold text-[var(--cc-text-primary)]">{a.display_name}</span>
                <span className="hidden text-[12px] text-[var(--cc-text-secondary)] md:inline">{AGENT_BLURB[key]}</span>
              </div>
              <StatePill status={a.status} durationMs={a.duration_ms} />
            </div>
            <p className="mt-1 min-h-[18px] text-[13px] leading-5 text-[var(--cc-text-secondary)]">
              {a.status === "pending" ? (
                <span className="text-[var(--cc-text-tertiary)]">Awaiting dispatch</span>
              ) : (
                <span className={a.status === "error" ? "text-[var(--cc-red-text)]" : ""}>{a.summary}</span>
              )}
            </p>
          </div>
        </div>
      );
    })}
  </div>
);
