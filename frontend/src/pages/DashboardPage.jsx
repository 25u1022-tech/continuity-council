import React, { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import { Skeleton } from "../components/ui/skeleton";
import { Button } from "../components/ui/button";
import { StatusBadge, SeverityBadge, Pill } from "../components/badges";
import { useCountUp } from "../hooks/useCountUp";
import { getProduction, getHealth, timeAgo, sentenceCase } from "../lib/api";
import { useProduction } from "../context/ProductionContext";
import { dayLabel } from "../lib/days";
import {
  CalendarDays, Film, Database, Siren, MapPin, Users, ArrowRight, CircleCheck, CircleX, Upload, Sparkles,
} from "lucide-react";
import { ScheduleImportModal } from "../components/ScheduleImportModal";

const Stat = ({ icon: Icon, label, value, animate = true, testId, accent }) => {
  const n = useCountUp(typeof value === "number" ? value : 0, { enabled: animate });
  const display = typeof value === "number" ? n.toLocaleString("en-US") : value;
  return (
    <div data-testid={testId} className="cc-card p-6">
      <div className="flex items-center justify-between">
        <span className="text-[13px] text-[var(--cc-text-secondary)]">{label}</span>
        <Icon size={16} strokeWidth={1.5} className={accent || "text-[var(--cc-text-tertiary)]"} />
      </div>
      <div className="font-display tabular mt-3 text-[28px] font-semibold leading-none text-[var(--cc-text-primary)]">
        {display}
      </div>
    </div>
  );
};

export default function DashboardPage({ activeCaseId }) {
  const navigate = useNavigate();
  const { selectedId } = useProduction();
  const [bundle, setBundle] = useState(null);
  const [health, setHealth] = useState(null);
  const [error, setError] = useState(null);
  const [loading, setLoading] = useState(true);
  const [importModalOpen, setImportModalOpen] = useState(false);

  useEffect(() => {
    if (!selectedId) return undefined;
    let alive = true;
    setLoading(true);
    setError(null);
    getHealth().then(async (h) => {
      if (!alive) return;
      setHealth(h);
      if (!h?.clickhouse?.connected) {
        setBundle(null);
        setError("ClickHouse Cloud is not connected. Add credentials to load this production.");
        setLoading(false);
        return;
      }
      try {
        const b = await getProduction(selectedId);
        if (!alive) return;
        setBundle(b);
      } catch (err) {
        if (!alive) return;
        setError(err.message || "Failed to load production");
      } finally {
        if (alive) setLoading(false);
      }
    }).catch((err) => {
      if (!alive) return;
      setError(err.message || "Failed to load health");
      setLoading(false);
    });
    return () => { alive = false; };
  }, [selectedId]);

  if (loading) {
    return (
      <div className="space-y-6" data-testid="dashboard-loading-skeleton">
        <Skeleton className="h-10 w-72 rounded-[8px]" />
        <div className="grid grid-cols-2 gap-4 lg:grid-cols-4">
          {[...Array(4)].map((_, i) => (
            <Skeleton key={i} className="h-28 rounded-[12px]" />
          ))}
        </div>
        <div className="grid grid-cols-12 gap-6">
          <Skeleton className="col-span-12 h-96 rounded-[12px] xl:col-span-8" />
          <Skeleton className="col-span-12 h-96 rounded-[12px] xl:col-span-4" />
        </div>
      </div>
    );
  }

  if (error || !bundle?.production) {
    return (
      <div className="cc-card p-10 text-center" data-testid="dashboard-error-state">
        <div className="mx-auto flex h-12 w-12 items-center justify-center rounded-[10px] bg-[var(--cc-accent-rose)]/10 text-[var(--cc-accent-rose)]">
          <Siren size={24} />
        </div>
        <h2 className="mt-4 text-[18px] font-semibold text-[var(--cc-text-primary)]">Unable to load production</h2>
        <p className="mt-1 text-[13px] text-[var(--cc-text-secondary)]">{error || "Production not found"}</p>
        <Button
          onClick={() => window.location.reload()}
          className="mt-6 rounded-[8px] bg-[var(--cc-text-primary)] text-[var(--cc-canvas)]"
        >
          Retry
        </Button>
      </div>
    );
  }

  const { production, scenes, locations, cast_members, location_availability, cast_availability, active_cases } = bundle;
  const days = Array.from({ length: production.total_shoot_days }, (_, i) => i + 1);
  const locAvail = {};
  location_availability.forEach((a) => { locAvail[`${a.location_id}_${a.shoot_day}`] = a; });
  const castAvail = {};
  cast_availability.forEach((a) => { castAvail[`${a.cast_id}_${a.shoot_day}`] = a; });
  const locName = Object.fromEntries(locations.map((l) => [l.location_id, l.name]));
  const castName = Object.fromEntries(cast_members.map((c) => [c.cast_id, c.name.split(" ")[0]]));

  const th = "px-5 pb-3 text-left text-[12px] font-medium text-[var(--cc-text-secondary)]";

  return (
    <div className="cc-fade-up space-y-8" data-testid="production-dashboard-page">
      {/* Page Header */}
      <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4">
        <div>
          <div className="text-[12px] font-semibold uppercase tracking-wider text-[var(--cc-text-tertiary)]">
            Now shooting
          </div>
          <h1 className="font-display mt-1 text-[30px] font-semibold leading-tight tracking-tight text-[var(--cc-text-primary)]">
            {production.title}
          </h1>
          <p className="mt-1.5 text-[14px] text-[var(--cc-text-secondary)]">
            {production.total_shoot_days}-day shoot · {scenes.length} scenes · {locations.length} locations · starts {production.start_date}
          </p>
        </div>

        <div className="flex items-center gap-3">
          <Button
            data-testid="import-schedule-pdf-btn"
            variant="outline"
            onClick={() => setImportModalOpen(true)}
            className="rounded-[8px] border-[var(--cc-border)] bg-[var(--cc-surface)] text-[var(--cc-text-primary)] hover:bg-[var(--cc-surface-hover)] flex items-center gap-2 shadow-sm"
          >
            <Upload size={14} />
            <span>Import schedule (PDF)</span>
          </Button>
          <Button
            data-testid="dashboard-report-disruption-btn"
            onClick={() => navigate("/report")}
            className="rounded-[8px] bg-[var(--cc-text-primary)] text-[var(--cc-canvas)] hover:bg-[var(--cc-text-primary)]/90 shadow-sm"
          >
            Report disruption
          </Button>
        </div>
      </div>

      {/* KPI Cards */}
      <div className="grid grid-cols-2 gap-4 lg:grid-cols-4">
        <Stat testId="kpi-shoot-days" icon={CalendarDays} label="Shoot days" value={production.total_shoot_days} />
        <Stat testId="kpi-scenes" icon={Film} label="Scheduled scenes" value={scenes.length} />
        <Stat
          testId="kpi-history-rows"
          icon={Database}
          label="ClickHouse history"
          value={health?.clickhouse?.history_rows || 0}
        />
        <Stat
          testId="kpi-active-disruptions"
          icon={Siren}
          label="Active disruptions"
          value={active_cases.length}
          accent={active_cases.length ? "text-[var(--cc-red-dot)]" : "text-[var(--cc-text-tertiary)]"}
        />
      </div>

      <div className="grid grid-cols-12 gap-6">
        {/* Shooting Schedule Table */}
        <div className="cc-card col-span-12 min-w-0 overflow-hidden xl:col-span-8">
          <div className="border-b border-[var(--cc-border)] px-6 py-4">
            <span className="text-[15px] font-semibold text-[var(--cc-text-primary)]">Shooting schedule</span>
          </div>
          <div className="overflow-x-auto">
            <table data-testid="schedule-table" className="w-full border-collapse">
              <thead>
                <tr className="border-b border-[var(--cc-border)]">
                  <th className={`${th} w-24 pt-4`}>Day</th>
                  <th className={`${th} w-20 pt-4`}>Scene</th>
                  <th className={`${th} pt-4`}>Title</th>
                  <th className={`${th} pt-4`}>Location</th>
                  <th className={`${th} pt-4`}>Cast</th>
                  <th className={`${th} pt-4 text-right`}>Status</th>
                </tr>
              </thead>
              <tbody>
                {scenes.map((s) => (
                  <tr
                    key={s.scene_id}
                    data-testid={`schedule-row-${s.scene_id}`}
                    className="cc-transition h-[52px] border-b border-[var(--cc-border)] last:border-b-0 hover:bg-[var(--cc-surface-hover)]"
                  >
                    <td className="tabular px-5 text-[13px] font-medium whitespace-nowrap text-[var(--cc-text-primary)]">
                      {dayLabel(production, s.shoot_day)}
                    </td>
                    <td className="px-5 font-mono text-xs text-[var(--cc-text-tertiary)]">{s.scene_id}</td>
                    <td className="px-5 text-[14px] font-medium text-[var(--cc-text-primary)]">
                      {s.scene_title}
                      {s.is_cover_scene ? (
                        <Pill tone="neutral" className="ml-2">Cover</Pill>
                      ) : null}
                    </td>
                    <td className="px-5 text-[13px] text-[var(--cc-text-secondary)]">{locName[s.location_id] || s.location_id}</td>
                    <td className="px-5 text-[13px] text-[var(--cc-text-secondary)]">
                      {s.required_cast.map((c) => castName[c] || c).join(", ")}
                    </td>
                    <td className="px-5 text-right">
                      <Pill tone={s.status === "moved" ? "yellow" : "gray"}>
                        {s.status === "moved" ? "Moved" : "Scheduled"}
                      </Pill>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>

        {/* Right Rail: Cast / Location / Disruptions */}
        <div className="col-span-12 min-w-0 space-y-5 xl:col-span-4">
          <div className="cc-card min-w-0 overflow-hidden p-6" data-testid="cast-availability-card">
            <div className="mb-4 flex items-center gap-2">
              <Users size={15} strokeWidth={1.5} className="text-[var(--cc-text-tertiary)]" />
              <span className="text-[15px] font-semibold text-[var(--cc-text-primary)]">Cast availability</span>
            </div>
            <AvailabilityGrid
              rows={cast_members.map((c) => ({ id: c.cast_id, label: c.name, sub: c.role_type }))}
              days={days}
              lookup={(id, d) => castAvail[`${id}_${d}`]?.available !== false}
            />
          </div>

          <div className="cc-card min-w-0 overflow-hidden p-6" data-testid="location-availability-card">
            <div className="mb-4 flex items-center gap-2">
              <MapPin size={15} strokeWidth={1.5} className="text-[var(--cc-text-tertiary)]" />
              <span className="text-[15px] font-semibold text-[var(--cc-text-primary)]">Location availability</span>
            </div>
            <AvailabilityGrid
              rows={locations.map((l) => ({ id: l.location_id, label: l.name, sub: l.location_type }))}
              days={days}
              lookup={(id, d) => locAvail[`${id}_${d}`]?.available !== false}
            />
          </div>

          <div className="cc-card p-6" data-testid="active-disruptions-card">
            <div className="mb-4 flex items-center gap-2">
              <Siren size={15} strokeWidth={1.5} className="text-[var(--cc-text-tertiary)]" />
              <span className="text-[15px] font-semibold text-[var(--cc-text-primary)]">Active disruptions</span>
            </div>
            {active_cases.length === 0 ? (
              <p className="py-3 text-center text-[13px] text-[var(--cc-text-secondary)]">All departments nominal.</p>
            ) : (
              <div className="space-y-2.5">
                {active_cases.map((c) => (
                  <button
                    key={c.case_id}
                    type="button"
                    data-testid={`active-case-${c.case_id}`}
                    onClick={() => {
                      localStorage.setItem("cc_active_case", c.case_id);
                      navigate(c.status === "options_ready" ? "/options" : "/investigation");
                      window.location.reload();
                    }}
                    className="cc-transition flex w-full items-center justify-between rounded-[10px] border border-[var(--cc-border)] bg-[var(--cc-surface-hover)] px-4 py-3 text-left hover:bg-[var(--cc-surface-active)]"
                  >
                    <div>
                      <div className="text-[13px] font-semibold text-[var(--cc-text-primary)]">{sentenceCase(c.disruption_type)}</div>
                      <div className="mt-0.5 text-[11px] text-[var(--cc-text-secondary)]">
                        Day {c.affected_day} · <span className="font-mono">{c.case_id}</span> · {timeAgo(c.created_at)}
                      </div>
                    </div>
                    <div className="flex items-center gap-2">
                      <SeverityBadge severity={c.severity} />
                      <StatusBadge status={c.status} />
                      <ArrowRight size={13} className="text-[var(--cc-text-tertiary)]" />
                    </div>
                  </button>
                ))}
              </div>
            )}
          </div>
        </div>
      </div>

      <ScheduleImportModal
        open={importModalOpen}
        onOpenChange={setImportModalOpen}
        productionId={selectedId}
        currentSceneCount={scenes ? scenes.length : 0}
        onImportComplete={async () => {
          try {
            const updated = await getProduction(selectedId);
            setBundle(updated);
          } catch (e) {
            console.error("Failed to refresh production after schedule import", e);
          }
        }}
      />
    </div>
  );
}

const AvailabilityGrid = ({ rows, days, lookup }) => (
  <div className="overflow-x-auto">
    <div className="min-w-full space-y-3">
      <div className="flex items-center justify-between gap-2 pb-1">
        <div className="sticky left-0 min-w-[110px] max-w-[130px] shrink-0 bg-[var(--cc-surface)]" />
        <div className="flex shrink-0 items-center gap-2 pr-1">
          {days.map((d) => (
            <span key={d} className="tabular w-8 text-center text-[11px] font-medium text-[var(--cc-text-tertiary)]">D{d}</span>
          ))}
        </div>
      </div>
      {rows.map((r) => (
        <div key={r.id} className="flex items-center justify-between gap-2 border-b border-[var(--cc-border-subtle)] pb-2 last:border-b-0">
          <div className="sticky left-0 min-w-[110px] max-w-[130px] shrink-0 bg-[var(--cc-surface)] pr-2">
            <div className="truncate text-[13px] font-medium text-[var(--cc-text-primary)]">{r.label}</div>
            <div className="text-[11px] capitalize text-[var(--cc-text-secondary)]">{r.sub}</div>
          </div>
          <div className="flex shrink-0 items-center gap-2 pr-1">
            {days.map((d) => {
              const ok = lookup(r.id, d);
              return (
                <span key={d} className="flex w-8 justify-center">
                  {ok ? (
                    <CircleCheck size={15} strokeWidth={1.75} className="text-[var(--cc-green-dot)]" />
                  ) : (
                    <CircleX size={15} strokeWidth={1.75} className="text-[var(--cc-red-dot)]" />
                  )}
                </span>
              );
            })}
          </div>
        </div>
      ))}
    </div>
  </div>
);
