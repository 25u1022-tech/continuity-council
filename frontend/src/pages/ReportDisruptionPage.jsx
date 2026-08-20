import React, { useEffect, useMemo, useState } from "react";
import { useNavigate } from "react-router-dom";
import { toast } from "sonner";
import { Button } from "../components/ui/button";
import { Label } from "../components/ui/label";
import { Textarea } from "../components/ui/textarea";
import {
  Select, SelectContent, SelectItem, SelectTrigger, SelectValue,
} from "../components/ui/select";
import { Skeleton } from "../components/ui/skeleton";
import { Pill } from "../components/badges";
import { getHealth, getProduction, getImpactPreview, reportDisruption, DISRUPTION_TYPES } from "../lib/api";
import { useProduction } from "../context/ProductionContext";
import { useTheme } from "../context/ThemeContext";
import { dayToDate, dateToDay, dayLabel, getShootDateRange } from "../lib/days";
import { Siren, Loader2, TriangleAlert } from "lucide-react";

const ACTOR_TYPES = ["lead_actor_unavailable", "supporting_actor_unavailable"];
const LOCATION_TYPES = ["location_unavailable", "permit_issue"];

const labelCls = "text-[13px] font-medium text-[var(--cc-text-secondary)]";
const triggerCls = "h-10 rounded-[10px] border border-[var(--cc-border)] bg-[var(--cc-surface-hover)] text-[14px] text-[var(--cc-text-primary)] shadow-sm focus:border-[var(--cc-text-primary)]";

export default function ReportDisruptionPage({ setActiveCaseId }) {
  const navigate = useNavigate();
  const { theme } = useTheme();
  const { selectedId } = useProduction();
  const [bundle, setBundle] = useState(null);
  const [loading, setLoading] = useState(true);
  const [loadError, setLoadError] = useState(null);
  const [previewScenes, setPreviewScenes] = useState([]);
  const [submitting, setSubmitting] = useState(false);

  const [form, setForm] = useState({
    disruption_type: "lead_actor_unavailable",
    affected_day: "1",
    affected_cast_id: "",
    affected_location_id: "",
    severity: "high",
    notes: "",
  });

  useEffect(() => {
    if (!selectedId) return;
    setLoading(true);
    setLoadError(null);
    getHealth()
      .then((health) => {
        if (!health?.clickhouse?.connected) throw new Error("ClickHouse Cloud is not connected. Add credentials to load this production.");
        return getProduction(selectedId);
      })
      .then((b) => {
        setBundle(b);
        setForm((f) => {
          const castOk = b.cast_members?.some((c) => c.cast_id === f.affected_cast_id);
          const locOk = b.locations?.some((l) => l.location_id === f.affected_location_id);
          const firstLead =
            (b.cast_members || []).find((c) => c.role_type === "lead") || b.cast_members?.[0];
          return {
            ...f,
            affected_cast_id: castOk ? f.affected_cast_id : firstLead?.cast_id || "",
            affected_location_id: locOk ? f.affected_location_id : b.locations?.[0]?.location_id || "",
          };
        });
      })
      .catch((e) => {
        setBundle(null);
        setLoadError(e?.response?.data?.detail || e?.message || "Could not load this production.");
      })
      .finally(() => setLoading(false));
  }, [selectedId]);

  const isActor = ACTOR_TYPES.includes(form.disruption_type);
  const isLocation = LOCATION_TYPES.includes(form.disruption_type);

  const shootRange = useMemo(() => getShootDateRange(bundle?.production), [bundle]);

  const currentDateInput = useMemo(() => {
    const d = parseInt(form.affected_day, 10);
    return dayToDate(bundle?.production, d) || shootRange.start || "";
  }, [bundle, form.affected_day, shootRange]);

  const handleDateChange = (e) => {
    const val = e.target.value;
    if (!val) return;
    const calcDay = dateToDay(bundle?.production, val);
    if (calcDay !== null) {
      const bounded = Math.max(1, Math.min(calcDay, bundle?.production?.total_shoot_days || 365));
      setForm((f) => ({ ...f, affected_day: String(bounded) }));
    }
  };

  const localImpactedScenes = useMemo(() => {
    if (!bundle) return [];
    const day = parseInt(form.affected_day, 10);
    return bundle.scenes.filter((s) => {
      if (s.shoot_day !== day) return false;
      if (isActor && form.affected_cast_id) return s.required_cast.includes(form.affected_cast_id);
      if (isLocation && form.affected_location_id) return s.location_id === form.affected_location_id;
      return true;
    });
  }, [bundle, form, isActor, isLocation]);

  useEffect(() => {
    if (!isLocation || !selectedId || !form.affected_location_id) {
      setPreviewScenes(localImpactedScenes);
      return;
    }
    getImpactPreview({
      production_id: selectedId,
      disruption_type: form.disruption_type,
      affected_day: form.affected_day,
      affected_location_id: form.affected_location_id,
    })
      .then((res) => setPreviewScenes(res.scenes || []))
      .catch(() => setPreviewScenes(localImpactedScenes));
  }, [form.affected_day, form.affected_location_id, form.disruption_type, isLocation, localImpactedScenes, selectedId]);

  const submit = async () => {
    setSubmitting(true);
    try {
      const payload = {
        production_id: selectedId,
        disruption_type: form.disruption_type,
        affected_day: parseInt(form.affected_day, 10),
        severity: form.severity,
        notes: form.notes,
        ...(isActor
          ? { affected_cast_id: form.affected_cast_id }
          : { affected_location_id: form.affected_location_id }),
      };
      const res = await reportDisruption(payload);
      setActiveCaseId(res.case_id);
      toast.success(`Case ${res.case_id} created — council dispatched`);
      navigate("/investigation");
    } catch (e) {
      toast.error(e?.response?.data?.detail || "Failed to report disruption");
    } finally {
      setSubmitting(false);
    }
  };

  const set = (k) => (v) => setForm((f) => ({ ...f, [k]: v }));

  if (loading) {
    return (
      <div className="space-y-6">
        <Skeleton className="cc-shimmer h-24 w-full" />
        <div className="grid grid-cols-12 gap-6">
          <Skeleton className="cc-shimmer col-span-7 h-96" />
          <Skeleton className="cc-shimmer col-span-5 h-96" />
        </div>
      </div>
    );
  }

  if (loadError) {
    return (
      <div className="cc-card mx-auto mt-16 max-w-md p-8 text-center">
        <TriangleAlert size={26} className="mx-auto text-[var(--cc-text-primary)]" />
        <h2 className="mt-4 text-[17px] font-semibold text-[var(--cc-text-primary)]">Production unavailable</h2>
        <p className="mt-2 text-[13px] text-[var(--cc-text-secondary)]">{loadError}</p>
        <Button type="button" onClick={() => window.location.reload()} className="mt-5 rounded-[10px]">
          Try again
        </Button>
      </div>
    );
  }

  return (
    <div className="cc-fade-up space-y-8" data-testid="report-disruption-page">
      <div>
        <div className="text-[12px] font-semibold uppercase tracking-wider text-[var(--cc-text-tertiary)]">
          Incident intake
        </div>
        <h1 className="font-display mt-1 text-[30px] font-semibold leading-tight tracking-tight text-[var(--cc-text-primary)]">
          Report disruption
        </h1>
        <p className="mt-1.5 text-[14px] text-[var(--cc-text-secondary)]">
          File the incident — the council of six agents investigates immediately.
        </p>
      </div>

      <div className="grid grid-cols-12 gap-6">
        {/* Form Card */}
        <div className="cc-card col-span-12 p-6 md:p-8 lg:col-span-7">
          <div className="grid grid-cols-2 gap-5">
            <div className="col-span-2 space-y-2">
              <Label className={labelCls}>Disruption type</Label>
              <Select value={form.disruption_type} onValueChange={set("disruption_type")}>
                <SelectTrigger data-testid="disruption-type-select" className={triggerCls}>
                  <SelectValue />
                </SelectTrigger>
                <SelectContent className="border border-[var(--cc-border)] bg-[var(--cc-surface)] text-[var(--cc-text-primary)] shadow-lg rounded-[12px] p-1">
                  {DISRUPTION_TYPES.filter((t) =>
                    ["lead_actor_unavailable", "location_unavailable"].includes(t.value)
                  ).map((t) => (
                    <SelectItem key={t.value} value={t.value} data-testid={`disruption-type-${t.value}`}>
                      {t.label}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>

            {/* Date-Aware Shooting Day Input */}
            <div className="space-y-2">
              <div className="flex items-center justify-between">
                <Label className={labelCls}>Shoot date / day</Label>
                <span className="text-[12px] font-semibold text-[var(--cc-text-primary)]">
                  Day {form.affected_day}
                </span>
              </div>
              <div className="relative">
                <input
                  type="date"
                  data-testid="affected-date-input"
                  min={shootRange.start || undefined}
                  max={shootRange.end || undefined}
                  value={currentDateInput}
                  onChange={handleDateChange}
                  style={{ colorScheme: theme === "dark" ? "dark" : "light" }}
                  className="w-full rounded-[10px] border border-[var(--cc-border)] bg-[var(--cc-surface-hover)] px-3.5 py-2 text-[14px] text-[var(--cc-text-primary)] shadow-sm focus:outline-none focus:border-[var(--cc-text-primary)] focus:ring-1 focus:ring-[var(--cc-text-primary)]"
                />
              </div>
              <div className="text-[12px] text-[var(--cc-text-secondary)]">
                {dayLabel(bundle?.production, parseInt(form.affected_day, 10))}
              </div>
            </div>

            <div className="space-y-2">
              <Label className={labelCls}>Severity</Label>
              <Select value={form.severity} onValueChange={set("severity")}>
                <SelectTrigger data-testid="severity-select" className={triggerCls}>
                  <SelectValue />
                </SelectTrigger>
                <SelectContent className="border border-[var(--cc-border)] bg-[var(--cc-surface)] text-[var(--cc-text-primary)] shadow-lg rounded-[12px] p-1">
                  <SelectItem value="low">Low</SelectItem>
                  <SelectItem value="medium">Medium</SelectItem>
                  <SelectItem value="high">High</SelectItem>
                </SelectContent>
              </Select>
            </div>

            {isActor && (
              <div className="col-span-2 space-y-2">
                <Label className={labelCls}>Affected cast member</Label>
                <Select value={form.affected_cast_id} onValueChange={set("affected_cast_id")}>
                  <SelectTrigger data-testid="affected-cast-select" className={triggerCls}>
                    <SelectValue placeholder="Select cast member" />
                  </SelectTrigger>
                  <SelectContent className="border border-[var(--cc-border)] bg-[var(--cc-surface)] text-[var(--cc-text-primary)] shadow-lg rounded-[12px] p-1">
                    {(bundle?.cast_members || []).map((c) => (
                      <SelectItem key={c.cast_id} value={c.cast_id}>
                        {c.name} ({c.role_type}) — ${c.day_rate_usd ? c.day_rate_usd.toLocaleString() : "1,500"}/day
                      </SelectItem>
                    ))}
                  </SelectContent>
                </Select>
              </div>
            )}

            {isLocation && (
              <div className="col-span-2 space-y-2">
                <Label className={labelCls}>Affected location</Label>
                <Select value={form.affected_location_id} onValueChange={set("affected_location_id")}>
                  <SelectTrigger data-testid="affected-location-select" className={triggerCls}>
                    <SelectValue placeholder="Select location" />
                  </SelectTrigger>
                  <SelectContent className="border border-[var(--cc-border)] bg-[var(--cc-surface)] text-[var(--cc-text-primary)] shadow-lg rounded-[12px] p-1">
                    {(bundle?.locations || []).map((l) => (
                      <SelectItem key={l.location_id} value={l.location_id}>
                        {l.name} ({l.location_type}) — {l.currency_code || "USD"} ${(l.daily_fee_usd || 5000).toLocaleString()}/day
                      </SelectItem>
                    ))}
                  </SelectContent>
                </Select>
              </div>
            )}

            <div className="col-span-2 space-y-2">
              <Label className={labelCls}>Notes</Label>
              <Textarea
                data-testid="disruption-notes-input"
                value={form.notes}
                onChange={(e) => set("notes")(e.target.value)}
                rows={3}
                className="resize-none rounded-[10px] border border-[var(--cc-border)] bg-[var(--cc-surface-hover)] text-[14px] text-[var(--cc-text-primary)] placeholder:text-[var(--cc-text-quaternary)] shadow-sm focus:border-[var(--cc-text-primary)] focus:ring-1 focus:ring-[var(--cc-text-primary)]"
                placeholder="What happened?"
              />
            </div>
          </div>

          <div className="mt-8 flex items-center justify-between border-t border-[var(--cc-border)] pt-6">
            <div className="text-[13px] text-[var(--cc-text-secondary)]">
              {previewScenes.length} scene{previewScenes.length !== 1 ? "s" : ""} on {dayLabel(bundle?.production, parseInt(form.affected_day, 10))} impacted
            </div>
            <Button
              type="button"
              data-testid="dispatch-council-button"
              onClick={submit}
              disabled={submitting}
              className="gap-2 rounded-[10px] bg-primary text-primary-foreground px-5 text-[14px] font-medium shadow-sm hover:opacity-90"
            >
              {submitting ? (
                <>
                  <Loader2 className="animate-spin" size={16} />
                  Dispatching council…
                </>
              ) : (
                <>
                  <Siren size={16} strokeWidth={1.75} />
                  Dispatch council
                </>
              )}
            </Button>
          </div>
        </div>

        {/* Live impact preview panel */}
        <div className="cc-card col-span-12 p-6 md:p-8 lg:col-span-5">
          <div className="flex items-center justify-between">
            <div className="text-[15px] font-semibold text-[var(--cc-text-primary)]">Impact preview</div>
            <span className="text-[12px] font-mono text-[var(--cc-text-secondary)]">
              {dayLabel(bundle?.production, parseInt(form.affected_day, 10))}
            </span>
          </div>
          <p className="mt-1 text-[13px] text-[var(--cc-text-secondary)]">
            Scenes scheduled on this day matching the affected resource.
          </p>

          <div className="mt-5 space-y-3">
            {previewScenes.length === 0 ? (
              <div className="rounded-[10px] border border-dashed border-[var(--cc-border)] p-6 text-center text-[13px] text-[var(--cc-text-secondary)]">
                No scenes scheduled for this combination on {dayLabel(bundle?.production, parseInt(form.affected_day, 10))}.
              </div>
            ) : (
              previewScenes.map((s) => (
                <div
                  key={s.scene_id}
                  data-testid={`preview-scene-${s.scene_id}`}
                  className="rounded-[10px] border border-[var(--cc-border)] bg-[var(--cc-surface-hover)] p-3.5 shadow-sm"
                >
                  <div className="flex items-center justify-between">
                    <div className="flex items-center gap-2">
                      <span className="font-mono text-[12px] font-semibold text-[var(--cc-text-primary)]">{s.scene_id}</span>
                      <span className="text-[14px] font-medium text-[var(--cc-text-primary)]">{s.scene_title}</span>
                    </div>
                    <Pill tone={s.priority === 1 ? "yellow" : "neutral"}>
                      P{s.priority}
                    </Pill>
                  </div>
                  <div className="mt-2 flex flex-wrap gap-1.5 text-[12px] text-[var(--cc-text-secondary)]">
                    <span className="rounded-[6px] bg-[var(--cc-surface)] border border-[var(--cc-border)] px-2 py-0.5">
                      {s.scene_type}
                    </span>
                    <span className="rounded-[6px] bg-[var(--cc-surface)] border border-[var(--cc-border)] px-2 py-0.5">
                      Loc: {s.location_id}
                    </span>
                    <span className="rounded-[6px] bg-[var(--cc-surface)] border border-[var(--cc-border)] px-2 py-0.5">
                      Cast: {(s.required_cast || []).join(", ")}
                    </span>
                  </div>
                </div>
              ))
            )}
          </div>
        </div>
      </div>
    </div>
  );
}
