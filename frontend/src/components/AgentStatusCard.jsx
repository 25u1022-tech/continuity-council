import React from "react";
import { Card } from "./ui/card";
import { Pill } from "./badges";
import {
  Crown,
  CalendarClock,
  Database,
  Drama,
  ShieldCheck,
  ScrollText,
  Check,
  CircleDashed,
  TriangleAlert,
} from "lucide-react";

const AGENT_ICONS = {
  orchestrator: Crown,
  schedule_optimizer: CalendarClock,
  budget_sentinel: Database,
  continuity_memory: Drama,
  compliance: ShieldCheck,
  auditor: ScrollText,
};

const AGENT_BLURB = {
  orchestrator: "Coordinates the council, merges findings, ranks options",
  schedule_optimizer: "Rearranges scenes, days and locations",
  budget_sentinel: "Queries ClickHouse history via MCP for cost evidence",
  continuity_memory: "Guards costume, narrative and emotional continuity",
  compliance: "Validates availability, day limits, working hours",
  auditor: "Writes the immutable decision ledger",
};

export const AgentStatusCard = ({ agent }) => {
  const Icon = AGENT_ICONS[agent.key] || CircleDashed;
  const isRunning = agent.status === "running";
  const isError = agent.status === "error";

  return (
    <Card
      data-testid={`agent-status-${agent.key.replace(/_/g, "-")}-card`}
      className="relative overflow-hidden p-4"
    >
      <div className="flex items-start justify-between gap-3">
        <div className="flex items-center gap-3">
          <div className="flex h-9 w-9 items-center justify-center rounded-[8px] border border-[var(--cc-border)] bg-[var(--cc-surface-hover)] text-[var(--cc-text-primary)]">
            <Icon size={16} strokeWidth={1.75} />
          </div>
          <div>
            <div className="font-display text-[14px] font-semibold tracking-tight text-[var(--cc-text-primary)]">
              {agent.display_name}
            </div>
            <div className="text-[11px] text-[var(--cc-text-secondary)]">{AGENT_BLURB[agent.key]}</div>
          </div>
        </div>
        <AgentStateBadge status={agent.status} durationMs={agent.duration_ms} />
      </div>

      <div className="mt-3 min-h-[34px] text-xs leading-5 text-[var(--cc-text-secondary)]">
        {agent.status === "pending" ? (
          <span className="italic text-[var(--cc-text-tertiary)]">Awaiting dispatch…</span>
        ) : (
          <span className={isError ? "text-[var(--cc-red-text)] font-medium" : ""}>{agent.summary}</span>
        )}
      </div>

      {isRunning && (
        <div className="absolute bottom-0 left-0 h-[2px] w-full overflow-hidden bg-[var(--cc-border)]">
          <div className="cc-bar-in h-full w-full bg-[var(--cc-text-primary)]" />
        </div>
      )}
    </Card>
  );
};

const AgentStateBadge = ({ status, durationMs }) => {
  if (status === "running")
    return (
      <Pill tone="yellow">
        <span className="cc-pulse-dot inline-block h-1.5 w-1.5 rounded-full bg-[var(--cc-yellow-dot)]" />
        Running
      </Pill>
    );
  if (status === "complete")
    return (
      <Pill tone="green">
        <Check size={11} strokeWidth={2.5} />
        Done{durationMs ? ` · ${(durationMs / 1000).toFixed(1)}s` : ""}
      </Pill>
    );
  if (status === "error")
    return (
      <Pill tone="red">
        <TriangleAlert size={11} />
        Error
      </Pill>
    );
  return (
    <Pill tone="gray">
      Pending
    </Pill>
  );
};
