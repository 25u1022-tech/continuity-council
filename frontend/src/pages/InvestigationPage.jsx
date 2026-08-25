import React, { useEffect, useRef } from "react";
import { useNavigate, Link } from "react-router-dom";
import { toast } from "sonner";
import { Button } from "../components/ui/button";
import { Skeleton } from "../components/ui/skeleton";
import { AgentTimeline } from "../components/AgentTimeline";
import { MCPCallLog } from "../components/MCPCallLog";
import { StatusBadge, SeverityBadge, Pill } from "../components/badges";
import { useCasePolling } from "../hooks/useCasePolling";
import { Check, ArrowRight, Radar, TriangleAlert, ExternalLink, Activity } from "lucide-react";
import { sentenceCase } from "../lib/api";
import { dayLabel } from "../lib/days";
import { useProduction } from "../context/ProductionContext";

const STAGES = [
  { key: "DISRUPTION_REPORTED", label: "Reported" },
  { key: "CASE_CREATED", label: "Case created" },
  { key: "AGENTS_INVESTIGATING", label: "Investigating" },
  { key: "OPTIONS_READY", label: "Options ready" },
  { key: "OPTION_APPROVED", label: "Approved" },
  { key: "DECISION_RECORDED", label: "Recorded" },
];

export default function InvestigationPage({ caseId, onCaseUpdate }) {
  const navigate = useNavigate();
  const { selected } = useProduction();
  const { caseData, error } = useCasePolling(caseId);
  const redirected = useRef(false);
  const initialStatus = useRef(null);

  useEffect(() => {
    if (caseData && onCaseUpdate) onCaseUpdate(caseData);
  }, [caseData, onCaseUpdate]);

  useEffect(() => {
    if (!caseData) return undefined;
    if (initialStatus.current === null) {
      initialStatus.current = caseData.status;
      return undefined;
    }
    if (caseData.status === "options_ready" && !redirected.current) {
      redirected.current = true;
      toast.success("Recovery options ready", { duration: 2200 });
      const t = setTimeout(() => navigate("/options"), 1600);
      return () => clearTimeout(t);
    }
    return undefined;
  }, [caseData, navigate]);

  if (!caseId) {
    return (
      <EmptyState
        title="No active investigation"
        subtitle="Report a disruption to dispatch the council of agents."
        cta={{ label: "Report disruption", to: "/report" }}
      />
    );
  }

  if (error && !caseData) {
    return <EmptyState title="Case not found" subtitle={String(error)} cta={{ label: "Report disruption", to: "/report" }} />;
  }

  if (!caseData) {
    return (
      <div className="space-y-6">
        <Skeleton className="cc-shimmer h-24 w-full" />
        <Skeleton className="cc-shimmer h-32 w-full" />
        <Skeleton className="cc-shimmer h-72 w-full" />
        <Skeleton className="cc-shimmer h-48 w-full" />
      </div>
    );
  }

  const stageIdx = STAGES.reduce(
    (acc, s, i) => (caseData.stages?.some((x) => x.stage === s.key) ? i : acc), 0
  );

  return (
    <div className="cc-fade-up space-y-8" data-testid="agent-investigation-page">
      <div className="flex flex-wrap items-end justify-between gap-4">
        <div>
          <div className="text-[12px] font-semibold uppercase tracking-wider text-[var(--cc-text-tertiary)]">
            Multi-agent investigation
          </div>
          <h1 className="font-display mt-1 flex items-center gap-3 text-[30px] font-semibold leading-tight tracking-tight text-[var(--cc-text-primary)]">
            Case <span className="font-mono text-[22px] text-[var(--cc-text-primary)]">{caseData.case_id}</span>
            <StatusBadge status={caseData.status} testId="case-status-badge" />
          </h1>
          <p className="mt-1.5 flex flex-wrap items-center gap-2 text-[14px] text-[var(--cc-text-secondary)]">
            <span>{sentenceCase(caseData.disruption?.disruption_type)}</span>
            <span>·</span>
            <span className="font-medium text-[var(--cc-text-primary)]">{dayLabel(selected, caseData.disruption?.affected_day)}</span>
            <SeverityBadge severity={caseData.disruption?.severity} />
            {caseData.llm_mode === "deterministic" && (
              <Pill tone="yellow" testId="llm-fallback-badge">
                Gemini quota reached: deterministic reasoning
              </Pill>
            )}
          </p>
        </div>
        {caseData.status === "options_ready" && (
          <Button
            data-testid="view-recovery-options-button"
            onClick={() => navigate("/options")}
            className="h-10 gap-2 rounded-[10px] bg-primary text-primary-foreground px-5 text-[14px] font-medium shadow-sm hover:opacity-90"
          >
            View recovery options <ArrowRight size={15} />
          </Button>
        )}
      </div>

      {/* Live Signals Ingestion Strip */}
      <div className="flex flex-wrap items-center justify-between gap-3 rounded-[12px] border border-[var(--cc-border)] bg-[var(--cc-surface)] px-5 py-3 shadow-sm">
        <div className="flex items-center gap-2.5 text-[13px] text-[var(--cc-text-secondary)]">
          <Activity size={15} className="text-[var(--cc-text-primary)]" />
          <span>
            <span className="font-medium text-[var(--cc-text-primary)]">Live Signals Active:</span> Open-Meteo climate risk · OpenStreetMap Nominatim geo · Frankfurter/ECB FX · ClickHouse 200k MV
          </span>
        </div>
        <Link
          to="/methodology"
          data-testid="investigation-methodology-link"
          className="flex items-center gap-1 text-[12px] font-medium text-[var(--cc-text-primary)] hover:underline"
        >
          <span>Methodology</span>
          <ExternalLink size={12} />
        </Link>
      </div>

      {/* Stage tracker */}
      <div className="cc-card px-6 py-5 md:px-8" data-testid="stage-tracker">
        <div className="flex items-center">
          {STAGES.map((s, i) => {
            const done = i <= stageIdx;
            const isCurrent = i === stageIdx && caseData.status !== "approved";
            return (
              <React.Fragment key={s.key}>
                {i > 0 && (
                  <div className={`h-px flex-1 ${i <= stageIdx ? "bg-[var(--cc-text-primary)]" : "bg-[var(--cc-border)]"}`} />
                )}
                <div className="flex flex-col items-center gap-1.5 px-1.5">
                  <div
                    className={`tabular flex h-6 w-6 items-center justify-center rounded-full text-[11px] font-medium transition-all ${
                      done
                        ? "bg-[var(--cc-text-primary)] text-[var(--cc-canvas)]"
                        : "bg-[var(--cc-surface-sunken)] text-[var(--cc-text-tertiary)] border border-[var(--cc-border)]"
                    } ${isCurrent ? "cc-pulse-dot ring-2 ring-[var(--cc-text-primary)]/30 ring-offset-2" : ""}`}
                  >
                    {done ? <Check size={12} strokeWidth={2.2} /> : i + 1}
                  </div>
                  <span className={`whitespace-nowrap text-[11px] ${done ? "font-medium text-[var(--cc-text-primary)]" : "text-[var(--cc-text-tertiary)]"}`}>
                    {s.label}
                  </span>
                </div>
              </React.Fragment>
            );
          })}
        </div>
      </div>

      {caseData.status === "error" && (
        <div className="flex items-center gap-3 rounded-[12px] border border-[var(--cc-red-dot)]/20 bg-[var(--cc-red-bg)] p-4" data-testid="case-error-banner">
          <TriangleAlert size={17} className="text-[var(--cc-red-text)] shrink-0" />
          <div>
            <div className="text-[14px] font-semibold text-[var(--cc-red-text)]">Investigation failed</div>
            <div className="text-[12px] text-[var(--cc-text-secondary)]">{caseData.error}</div>
          </div>
        </div>
      )}

      {/* Agent timeline */}
      <AgentTimeline agents={caseData.agents} />

      {/* MCP console */}
      <MCPCallLog calls={caseData.mcp_calls} connected />
    </div>
  );
}

const EmptyState = ({ title, subtitle, cta }) => {
  const navigate = useNavigate();
  return (
    <div className="cc-card mx-auto mt-16 max-w-md p-8 text-center">
      <Radar size={28} strokeWidth={1.5} className="mx-auto text-[var(--cc-text-tertiary)]" />
      <h2 className="font-display mt-4 text-[18px] font-semibold text-[var(--cc-text-primary)]">{title}</h2>
      <p className="mt-1.5 text-[13px] text-[var(--cc-text-secondary)]">{subtitle}</p>
      {cta && (
        <Button
          data-testid="empty-state-cta"
          onClick={() => navigate(cta.to)}
          className="mt-5 rounded-[10px]"
        >
          {cta.label}
        </Button>
      )}
    </div>
  );
};
