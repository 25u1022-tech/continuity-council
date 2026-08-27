import React, { useEffect, useState } from "react";
import { useNavigate, Link } from "react-router-dom";
import { toast } from "sonner";
import { Button } from "../components/ui/button";
import { Skeleton } from "../components/ui/skeleton";
import { Collapsible, CollapsibleContent, CollapsibleTrigger } from "../components/ui/collapsible";
import {
  AlertDialog, AlertDialogAction, AlertDialogCancel, AlertDialogContent,
  AlertDialogDescription, AlertDialogFooter, AlertDialogHeader, AlertDialogTitle,
} from "../components/ui/alert-dialog";
import { EvidenceTable } from "../components/EvidenceTable";
import { MCPCallLog } from "../components/MCPCallLog";
import { RiskBadge, ComplianceBadge, MonoPill, Pill } from "../components/badges";
import { useCasePolling } from "../hooks/useCasePolling";
import { useProduction } from "../context/ProductionContext";
import { approveOption, fmtMoney, fmtHours, sentenceCase } from "../lib/api";
import { dayLabel } from "../lib/days";
import {
  Crown,
  ChevronDown,
  TriangleAlert,
  Drama,
  Loader2,
  GitCompareArrows,
  CloudRain,
  Coins,
  MapPin,
  Info,
  Sparkles,
} from "lucide-react";
import { LocationMoodboardModal } from "../components/LocationMoodboardModal";

export default function RecoveryOptionsPage({ caseId, onCaseUpdate }) {
  const navigate = useNavigate();
  const { selected } = useProduction();
  const { caseData, error } = useCasePolling(caseId, 2500);
  const [confirming, setConfirming] = useState(null);
  const [approving, setApproving] = useState(false);
  const [previewLocation, setPreviewLocation] = useState(null);

  useEffect(() => {
    if (caseData && onCaseUpdate) onCaseUpdate(caseData);
  }, [caseData, onCaseUpdate]);

  if (!caseId || (caseData && caseData.status === "investigating")) {
    return (
      <div className="cc-card mx-auto mt-16 max-w-md p-8 text-center">
        <GitCompareArrows size={28} strokeWidth={1.5} className="mx-auto text-[var(--cc-text-tertiary)]" />
        <h2 className="font-display mt-4 text-[18px] font-semibold text-[var(--cc-text-primary)]">
          {caseId ? "Agents are still investigating" : "No case selected"}
        </h2>
        <p className="mt-1.5 text-[13px] text-[var(--cc-text-secondary)]">
          {caseId ? "Options appear the moment the Orchestrator ranks them." : "Report a disruption first."}
        </p>
        <Button
          data-testid="options-empty-cta"
          onClick={() => navigate(caseId ? "/investigation" : "/report")}
          className="mt-5 rounded-[10px]"
        >
          {caseId ? "Watch investigation" : "Report disruption"}
        </Button>
      </div>
    );
  }

  if (error && !caseData) {
    return (
      <div className="cc-card mx-auto mt-16 max-w-md p-8 text-center">
        <TriangleAlert size={26} className="mx-auto text-[var(--cc-text-primary)]" />
        <h2 className="mt-4 text-[17px] font-semibold text-[var(--cc-text-primary)]">Recovery options unavailable</h2>
        <p className="mt-2 text-[13px] text-[var(--cc-text-secondary)]">{String(error)}</p>
        <Button
          type="button"
          onClick={() => navigate("/investigation")}
          className="mt-5 rounded-[10px]"
        >
          View investigation
        </Button>
      </div>
    );
  }

  if (!caseData) {
    return (
      <div className="space-y-6">
        <Skeleton className="cc-shimmer h-24 w-full" />
        <Skeleton className="cc-shimmer h-64 w-full" />
        <Skeleton className="cc-shimmer h-64 w-full" />
      </div>
    );
  }

  const approved = caseData.status === "approved";

  const doApprove = async (option) => {
    setApproving(true);
    try {
      const res = await approveOption(caseData.case_id, option.option_id);
      if (onCaseUpdate) {
        onCaseUpdate({ ...caseData, status: "approved", decision_id: res.decision_id });
      }
      toast.success(`Decision ${res.decision_id} written to the ClickHouse ledger`, { duration: 3200 });
      setTimeout(() => navigate("/ledger"), 1100);
    } catch (e) {
      toast.error(e?.response?.data?.detail || "Approval failed");
    } finally {
      setApproving(false);
      setConfirming(null);
    }
  };

  return (
    <div className="cc-fade-up space-y-8" data-testid="recovery-options-page">
      <div>
        <div className="text-[12px] font-semibold uppercase tracking-wider text-[var(--cc-text-tertiary)]">
          Producer decision
        </div>
        <h1 className="font-display mt-1 text-[30px] font-semibold leading-tight tracking-tight text-[var(--cc-text-primary)]">
          Recovery options
        </h1>
        <p className="mt-1.5 text-[14px] text-[var(--cc-text-secondary)]">
          Ranked by multi-agent consensus · {sentenceCase(caseData.disruption?.disruption_type)} on{" "}
          <span className="font-medium text-[var(--cc-text-primary)]">{dayLabel(selected, caseData.disruption?.affected_day)}</span>
        </p>
      </div>

      {caseData.recommendation_rationale && (
        <div
          data-testid="orchestrator-rationale"
          className="flex items-start gap-3.5 rounded-[12px] border border-[var(--cc-border)] bg-[var(--cc-surface)] p-5 shadow-sm"
        >
          <div className="flex h-8 w-8 items-center justify-center rounded-[8px] bg-[var(--cc-surface-hover)] text-[var(--cc-text-primary)] shrink-0 mt-0.5">
            <Crown size={16} strokeWidth={1.75} />
          </div>
          <div>
            <div className="text-[13px] font-semibold text-[var(--cc-text-primary)]">Orchestrator recommendation</div>
            <p className="mt-1 text-[13px] leading-relaxed text-[var(--cc-text-secondary)]">{caseData.recommendation_rationale}</p>
          </div>
        </div>
      )}

      <div className="grid grid-cols-12 gap-6">
        <div className="col-span-12 space-y-5 xl:col-span-7">
          {caseData.options.map((o) => (
            <OptionCard
              key={o.option_id}
              option={o}
              production={selected}
              approved={approved}
              isSelected={caseData.approved_option_id === o.option_id}
              onApprove={() => setConfirming(o)}
              onPreviewLocation={(loc) => setPreviewLocation(loc)}
            />
          ))}
        </div>

        <div className="col-span-12 space-y-5 xl:col-span-5">
          <EvidenceTable
            rows={caseData.evidence_rows}
            narrative={caseData.evidence_narrative}
            mcpCalls={caseData.mcp_calls}
            disruptionType={caseData.disruption?.disruption_type}
            severity={caseData.disruption?.severity}
          />
          <MCPCallLog calls={caseData.mcp_calls} connected compact />
        </div>
      </div>

      <LocationMoodboardModal
        open={Boolean(previewLocation)}
        onOpenChange={(open) => !open && setPreviewLocation(null)}
        locationId={previewLocation?.locationId}
        locationName={previewLocation?.locationName}
        sceneId={previewLocation?.sceneId}
      />

      <AlertDialog open={!!confirming} onOpenChange={(v) => !v && setConfirming(null)}>
        <AlertDialogContent className="cc-card border border-[var(--cc-border)] p-6">
          <AlertDialogHeader>
            <AlertDialogTitle className="font-display text-[17px] text-[var(--cc-text-primary)]">
              Approve “{confirming?.name}”?
            </AlertDialogTitle>
            <AlertDialogDescription className="text-[13px] leading-relaxed text-[var(--cc-text-secondary)]">
              Estimated {fmtMoney(confirming?.estimated_cost_usd)} overrun · {fmtHours(confirming?.estimated_delay_hours)} delay ·{" "}
              {confirming?.scene_changes?.length || 0} scene move(s). The Auditor writes this decision to the
              ClickHouse ledger: this is the official production record.
            </AlertDialogDescription>
          </AlertDialogHeader>
          <AlertDialogFooter className="mt-4">
            <AlertDialogCancel
              data-testid="approve-cancel-button"
              className="rounded-[10px]"
            >
              Cancel
            </AlertDialogCancel>
            <AlertDialogAction
              data-testid="approve-confirm-button"
              disabled={approving}
              onClick={(e) => {
                e.preventDefault();
                doApprove(confirming);
              }}
              className="gap-2 rounded-[10px] bg-primary text-primary-foreground font-medium"
            >
              {approving ? <Loader2 size={13} className="animate-spin" /> : null}
              {approving ? "Writing ledger…" : "Approve & record"}
            </AlertDialogAction>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>
    </div>
  );
}

const OptionCard = ({ option, production, approved, isSelected, onApprove, onPreviewLocation }) => {
  const [showChanges, setShowChanges] = useState(false);
  const [showCostBreakdown, setShowCostBreakdown] = useState(false);

  const breakdown = option.cost_breakdown?.breakdown || [];

  const locationChange = option.scene_changes?.find(
    (c) => c.from_location && c.to_location && c.from_location !== c.to_location
  );
  const isLocationSwap =
    option.strategy === "swap_locations" ||
    Boolean(locationChange) ||
    Boolean(option.affected_location_id);

  const targetLocationName =
    locationChange?.to_location ||
    option.affected_location_id ||
    production?.locations?.[0]?.name ||
    "Alternate Filming Location";

  const targetLocationId =
    locationChange?.to_location ||
    option.affected_location_id ||
    production?.locations?.[0]?.location_id ||
    "loc_002";

  return (
    <div
      data-testid={`recovery-option-card-${option.option_id}`}
      className={`cc-card p-6 md:p-7 relative ${
        option.recommended ? "border-[var(--cc-text-primary)]/40 shadow-md ring-1 ring-[var(--cc-text-primary)]/10" : ""
      } ${isSelected ? "border-[var(--cc-green-dot)]/50 ring-1 ring-[var(--cc-green-dot)]/20" : ""}`}
    >
      <div className="flex items-start justify-between gap-4">
        <div className="flex items-center gap-3.5">
          <div className="font-display tabular flex h-10 w-10 items-center justify-center rounded-[10px] bg-[var(--cc-surface-sunken)] border border-[var(--cc-border)] text-[16px] font-semibold text-[var(--cc-text-primary)]">
            {option.rank}
          </div>
          <div>
            <div className="flex items-center gap-2">
              <h3 className="font-display text-[17px] font-semibold tracking-tight text-[var(--cc-text-primary)]">{option.name}</h3>
              {option.recommended && (
                <Pill tone="neutral" testId="recommended-badge" className="gap-1 border-[var(--cc-text-primary)]/30 font-semibold">
                  <Crown size={11} strokeWidth={2} /> Recommended
                </Pill>
              )}
              {isSelected && <Pill tone="green">Approved</Pill>}
            </div>
            <div className="mt-0.5 font-mono text-[11px] text-[var(--cc-text-tertiary)]">{option.strategy}</div>
          </div>
        </div>
        <div className="text-right">
          <div className="text-[11px] text-[var(--cc-text-tertiary)] uppercase tracking-wider font-medium">Score</div>
          <div className="tabular font-display text-[22px] font-bold text-[var(--cc-text-primary)]">
            {option.score.toFixed(2)}
          </div>
        </div>
      </div>

      {/* Explainability Layer: Justification Insight */}
      {option.justification && (
        <div
          data-testid={`option-justification-${option.option_id}`}
          className={`mt-3.5 rounded-[9px] px-3.5 py-2 text-[12.5px] leading-relaxed transition-colors ${
            option.justification.startsWith("Ranked #")
              ? "border border-[var(--cc-border)] bg-[var(--cc-surface-sunken)]/50 text-[var(--cc-text-secondary)] font-normal"
              : "border-l-2 border-l-[var(--cc-text-primary)]/70 border border-[var(--cc-border)] bg-[var(--cc-surface-hover)] text-[var(--cc-text-secondary)] italic shadow-sm"
          }`}
        >
          <span className="text-[var(--cc-text-secondary)]">{option.justification}</span>
        </div>
      )}

      <p className="mt-3 text-[13px] leading-relaxed text-[var(--cc-text-secondary)]">{option.description}</p>

      {/* Metrics Strip */}
      <div className="mt-5 grid grid-cols-2 gap-4 md:grid-cols-4 rounded-[12px] border border-[var(--cc-border)] bg-[var(--cc-surface-sunken)]/50 p-4">
        <div>
          <div className="text-[11px] font-medium text-[var(--cc-text-tertiary)]">Est. cost overrun</div>
          <div className="tabular font-display mt-1 text-[20px] font-semibold text-[var(--cc-text-primary)]">
            {fmtMoney(option.estimated_cost_usd)}
          </div>
        </div>
        <div>
          <div className="text-[11px] font-medium text-[var(--cc-text-tertiary)]">Est. delay</div>
          <div className="tabular font-display mt-1 text-[20px] font-semibold text-[var(--cc-text-primary)]">
            {fmtHours(option.estimated_delay_hours)}
          </div>
        </div>
        <div>
          <div className="text-[11px] font-medium text-[var(--cc-text-tertiary)]">Continuity risk</div>
          <div className="mt-1.5"><RiskBadge score={option.continuity_risk_score} /></div>
        </div>
        <div>
          <div className="text-[11px] font-medium text-[var(--cc-text-tertiary)]">Compliance</div>
          <div className="mt-1.5"><ComplianceBadge valid={option.compliance_valid} /></div>
        </div>
      </div>

      {/* Score bar */}
      <div className="mt-5 h-[4px] w-full overflow-hidden rounded-full bg-[var(--cc-surface-sunken)] border border-[var(--cc-border-subtle)]">
        <div
          className="cc-bar-in h-full rounded-full bg-[var(--cc-text-primary)]"
          style={{ width: `${Math.max(3, option.score * 100)}%` }}
        />
      </div>

      {/* Live Signals & Actions Strip */}
      <div className="mt-4 flex flex-wrap items-center gap-2">
        {/* Moodboard Preview Button for Location Moves */}
        {isLocationSwap && onPreviewLocation && (
          <button
            type="button"
            data-testid={`preview-look-btn-${option.option_id}`}
            onClick={() =>
              onPreviewLocation({
                locationId: targetLocationId,
                locationName: targetLocationName,
                sceneId: locationChange?.scene_id,
              })
            }
            className="flex items-center gap-1.5 rounded-[8px] border border-[var(--cc-border)] bg-[var(--cc-surface-hover)] px-2.5 py-1 text-[11px] font-medium text-[var(--cc-text-secondary)] hover:text-[var(--cc-text-primary)] hover:border-[var(--cc-text-primary)]/40 transition-all shadow-sm"
          >
            <Sparkles size={11} className="text-[var(--cc-yellow-dot)]" />
            <span>Preview look</span>
          </button>
        )}

        {option.weather_summary && (
          <div className="flex items-center gap-1.5 rounded-[8px] border border-[var(--cc-border)] bg-[var(--cc-surface-hover)] px-2.5 py-1 text-[11px] text-[var(--cc-text-secondary)] shadow-sm">
            <CloudRain size={12} className="text-[var(--cc-blue-dot)]" />
            <span>{option.weather_summary}</span>
            <Link to="/methodology" className="ml-1 text-[var(--cc-text-primary)] hover:underline" title="Details">
              <Info size={11} />
            </Link>
          </div>
        )}

        {option.fx_summary && (
          <div className="flex items-center gap-1.5 rounded-[8px] border border-[var(--cc-border)] bg-[var(--cc-surface-hover)] px-2.5 py-1 text-[11px] text-[var(--cc-text-secondary)] shadow-sm">
            <Coins size={12} className="text-[var(--cc-yellow-dot)]" />
            <span>{option.fx_summary}</span>
            <Link to="/methodology" className="ml-1 text-[var(--cc-text-primary)] hover:underline" title="Details">
              <Info size={11} />
            </Link>
          </div>
        )}

        {option.transit_summary && (
          <div className={`flex items-center gap-1.5 rounded-[8px] border border-[var(--cc-border)] px-2.5 py-1 text-[11px] shadow-sm ${
            option.transit_distance_miles > 100 ? "bg-[var(--cc-red-bg)] text-[var(--cc-red-text)]" : "bg-[var(--cc-surface-hover)] text-[var(--cc-text-secondary)]"
          }`}>
            <MapPin size={12} className={option.transit_distance_miles > 100 ? "text-[var(--cc-red-dot)]" : "text-[var(--cc-green-dot)]"} />
            <span>{option.transit_summary}</span>
            <Link to="/methodology" className="ml-1 text-[var(--cc-text-primary)] hover:underline" title="Details">
              <Info size={11} />
            </Link>
          </div>
        )}
      </div>

      {/* ClickHouse Evidence Summary */}
      {option.evidence && (
        <div className="mt-3 flex flex-wrap items-center gap-2 rounded-[10px] border border-[var(--cc-border)] bg-[var(--cc-surface-hover)] px-4 py-2.5">
          <MonoPill tone="neutral">{option.evidence.past_cases.toLocaleString()} past cases</MonoPill>
          <span className="tabular font-mono text-[11px] text-[var(--cc-text-secondary)]">
            historical avg {fmtMoney(option.evidence.avg_cost_overrun_usd)} · {fmtHours(option.evidence.avg_delay_hours)} · success {(option.evidence.avg_success_score * 100).toFixed(0)}%
          </span>
        </div>
      )}

      {/* Cost Breakdown Accordion */}
      {breakdown.length > 0 && (
        <Collapsible open={showCostBreakdown} onOpenChange={setShowCostBreakdown} className="mt-3">
          <CollapsibleTrigger asChild>
            <button
              type="button"
              data-testid={`toggle-cost-breakdown-${option.option_id}`}
              className="cc-transition flex items-center gap-1.5 text-[13px] font-medium text-[var(--cc-text-secondary)] hover:text-[var(--cc-text-primary)]"
            >
              <ChevronDown size={13} className={`cc-transition ${showCostBreakdown ? "rotate-180" : ""}`} />
              <span>Cost breakdown ({breakdown.length} line items)</span>
            </button>
          </CollapsibleTrigger>
          <CollapsibleContent>
            <div className="mt-2 space-y-2 rounded-[10px] border border-[var(--cc-border)] bg-[var(--cc-surface-sunken)] p-4 text-[12px]">
              <div className="divide-y divide-[var(--cc-border)]">
                {breakdown.map((item, idx) => (
                  <div key={idx} className="flex items-center justify-between py-2 first:pt-0 last:pb-0">
                    <div>
                      <div className="font-medium text-[var(--cc-text-primary)]">{item.line}</div>
                      <div className="text-[10px] text-[var(--cc-text-tertiary)]">{item.source}</div>
                    </div>
                    <div className="font-mono font-medium text-[var(--cc-text-primary)]">{fmtMoney(item.amount_usd)}</div>
                  </div>
                ))}
              </div>
              <div className="flex items-center justify-between border-t border-[var(--cc-border)] pt-2.5 font-semibold">
                <span className="text-[var(--cc-text-secondary)]">Calibrated Total (70% rate-card + 30% ClickHouse)</span>
                <span className="font-mono text-[var(--cc-text-primary)]">{fmtMoney(option.estimated_cost_usd)}</span>
              </div>
              <div className="pt-1 text-[11px] text-[var(--cc-text-tertiary)]">
                Rate card v1 benchmarks calibrated with empirical evidence:{" "}
                <Link to="/methodology" className="text-[var(--cc-text-primary)] underline hover:opacity-80">
                  see Cost Methodology
                </Link>
              </div>
            </div>
          </CollapsibleContent>
        </Collapsible>
      )}

      {/* Continuity Risks */}
      {option.continuity_risks.length > 0 && (
        <div className="mt-4 space-y-1.5">
          {option.continuity_risks.map((r, i) => (
            <div key={i} className="flex items-start gap-2 text-[13px] text-[var(--cc-text-secondary)]">
              <Drama size={13} strokeWidth={1.5} className="mt-0.5 shrink-0 text-[var(--cc-yellow-dot)]" />
              <span>
                {r.risk}{" "}
                {r.scene_ids.length > 0 && (
                  <span className="font-mono text-[11px] text-[var(--cc-text-tertiary)]">[{r.scene_ids.join(", ")}]</span>
                )}
              </span>
            </div>
          ))}
        </div>
      )}

      {/* Compliance Warnings */}
      {option.compliance_warnings.length > 0 && (
        <div className="mt-3 space-y-1.5">
          {option.compliance_warnings.map((w, i) => (
            <div key={i} className="flex items-start gap-2 text-[13px]">
              <TriangleAlert size={13} strokeWidth={1.5} className="mt-0.5 shrink-0 text-[var(--cc-red-dot)]" />
              <span className={option.compliance_valid ? "text-[var(--cc-text-secondary)]" : "text-[var(--cc-red-text)] font-medium"}>{w}</span>
            </div>
          ))}
        </div>
      )}

      {/* Scene Changes with Date-Aware Day Labels */}
      {option.scene_changes.length > 0 && (
        <Collapsible open={showChanges} onOpenChange={setShowChanges} className="mt-4">
          <CollapsibleTrigger asChild>
            <button
              type="button"
              data-testid={`toggle-scene-changes-${option.option_id}`}
              className="cc-transition flex items-center gap-1.5 text-[13px] font-medium text-[var(--cc-text-secondary)] hover:text-[var(--cc-text-primary)]"
            >
              <ChevronDown size={13} className={`cc-transition ${showChanges ? "rotate-180" : ""}`} />
              {option.scene_changes.length} scene change{option.scene_changes.length !== 1 ? "s" : ""}
            </button>
          </CollapsibleTrigger>
          <CollapsibleContent>
            <div className="mt-2 space-y-1 rounded-[10px] border border-[var(--cc-border)] bg-[var(--cc-surface-sunken)] p-4">
              {option.scene_changes.map((c) => (
                <div key={`${c.scene_id}-${c.to_day}`} className="flex flex-wrap items-center justify-between gap-2 py-1 font-mono text-[11px] border-b border-[var(--cc-border-subtle)] last:border-b-0">
                  <span className="text-[var(--cc-text-primary)]">{c.scene_id} · {c.scene_title}</span>
                  <span className="tabular text-[var(--cc-text-secondary)]">
                    <span className="text-[var(--cc-text-primary)] font-medium">{dayLabel(production, c.from_day)}</span>
                    <span className="mx-1.5">→</span>
                    <span className="text-[var(--cc-green-text)] font-medium">{dayLabel(production, c.to_day)}</span>
                    {c.from_location !== c.to_location ? ` · ${c.from_location} → ${c.to_location}` : ""}
                  </span>
                </div>
              ))}
            </div>
          </CollapsibleContent>
        </Collapsible>
      )}

      {!approved && (
        <Button
          data-testid={`recovery-option-approve-button-${option.option_id}`}
          onClick={onApprove}
          disabled={!option.compliance_valid}
          variant={option.recommended ? "default" : "outline"}
          className="mt-6 h-10 w-full rounded-[10px] text-[14px] font-semibold"
        >
          {option.compliance_valid ? `Approve ${option.name.toLowerCase()}` : "Blocked by compliance"}
        </Button>
      )}
    </div>
  );
};
