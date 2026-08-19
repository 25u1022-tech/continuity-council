import React, { useEffect, useMemo, useRef, useState } from "react";
import { toast } from "sonner";
import {
  Dialog, DialogContent, DialogHeader, DialogTitle, DialogDescription,
} from "./ui/dialog";
import { Button } from "./ui/button";
import { Label } from "./ui/label";
import { Input } from "./ui/input";
import {
  createProduction, importHistoryCsv, parseCsv, parseDays, downloadCsv,
  CAST_CSV_TEMPLATE, LOCATION_CSV_TEMPLATE,
} from "../lib/api";
import { LocationMapPicker } from "./LocationMapPicker";
import {
  Clapperboard, Users, MapPin, Plus, Trash2, Upload, Download,
  ArrowRight, ArrowLeft, Loader2, Check, FileText, Database,
  AlertCircle, ChevronDown, ChevronUp, Map,
} from "lucide-react";

const labelCls = "text-[13px] font-medium text-[var(--cc-text-secondary)]";
const inputCls =
  "h-10 rounded-[10px] border border-[var(--cc-border)] bg-[var(--cc-surface-hover)] text-[14px] text-[var(--cc-text-primary)] placeholder:text-[var(--cc-text-quaternary)] shadow-sm focus:border-[var(--cc-text-primary)]";

const ROLE_OPTIONS = ["lead", "supporting", "background"];
const TYPE_OPTIONS = ["interior", "exterior", "stage", "studio"];

const todayISO = (offset = 0) => {
  const d = new Date();
  d.setDate(d.getDate() + offset);
  return d.toISOString().slice(0, 10);
};

const daysBetween = (a, b) => {
  const s = new Date(a);
  const e = new Date(b);
  if (isNaN(s) || isNaN(e) || e < s) return 0;
  return Math.round((e - s) / 86400000) + 1;
};

// --- small segmented control -------------------------------------------------
const Segmented = ({ options, value, onChange, testId }) => (
  <div data-testid={testId} className="inline-flex gap-1 rounded-[10px] border border-[var(--cc-border)] bg-[var(--cc-surface-sunken)] p-1">
    {options.map((o) => (
      <button
        key={o}
        type="button"
        onClick={() => onChange(o)}
        className={`cc-transition rounded-[7px] px-2.5 py-1 text-[12px] capitalize font-medium ${
          value === o
            ? "bg-[var(--cc-surface)] text-[var(--cc-text-primary)] shadow-sm"
            : "text-[var(--cc-text-secondary)] hover:text-[var(--cc-text-primary)]"
        }`}
      >
        {o}
      </button>
    ))}
  </div>
);

// --- day availability toggles ------------------------------------------------
const DayToggles = ({ totalDays, selected, onToggle }) => (
  <div className="flex flex-wrap items-center gap-1.5">
    {Array.from({ length: totalDays }, (_, i) => i + 1).map((d) => {
      const on = selected.includes(d);
      return (
        <button
          key={d}
          type="button"
          onClick={() => onToggle(d)}
          className={`tabular cc-transition h-7 w-9 rounded-[7px] text-[12px] font-medium border ${
            on
              ? "bg-[var(--cc-text-primary)] text-[var(--cc-canvas)] border-[var(--cc-text-primary)]"
              : "bg-[var(--cc-surface)] text-[var(--cc-text-secondary)] border-[var(--cc-border)] hover:bg-[var(--cc-surface-hover)]"
          }`}
        >
          D{d}
        </button>
      );
    })}
  </div>
);

const StepDots = ({ step }) => (
  <div className="flex items-center gap-1.5">
    {[1, 2, 3, 4].map((s) => (
      <span
        key={s}
        className={`h-1.5 rounded-full cc-transition ${
          s === step ? "w-6 bg-[var(--cc-text-primary)]" : s < step ? "w-1.5 bg-[var(--cc-text-primary)]/50" : "w-1.5 bg-[var(--cc-border)]"
        }`}
      />
    ))}
  </div>
);

export const CreateProductionWizard = ({ open, onOpenChange, onCreated }) => {
  const [step, setStep] = useState(1);
  const [submitting, setSubmitting] = useState(false);
  const [details, setDetails] = useState({
    name: "",
    shoot_start: todayISO(0),
    shoot_end: todayISO(2),
    director: "",
  });
  const [cast, setCast] = useState([]);
  const [locations, setLocations] = useState([]);
  const [historyFile, setHistoryFile] = useState(null);
  const [historyValidation, setHistoryValidation] = useState(null);
  const [isValidatingHistory, setIsValidatingHistory] = useState(false);
  const [expandedMapIdx, setExpandedMapIdx] = useState(null);

  const castFileRef = useRef(null);
  const locFileRef = useRef(null);
  const historyFileRef = useRef(null);

  const totalDays = useMemo(
    () => daysBetween(details.shoot_start, details.shoot_end),
    [details.shoot_start, details.shoot_end]
  );
  const allDays = useMemo(
    () => Array.from({ length: totalDays }, (_, i) => i + 1),
    [totalDays]
  );

  // Reset everything each time the wizard opens.
  useEffect(() => {
    if (open) {
      setStep(1);
      setSubmitting(false);
      setDetails({ name: "", shoot_start: todayISO(0), shoot_end: todayISO(2), director: "" });
      setCast([]);
      setLocations([]);
      setHistoryFile(null);
      setHistoryValidation(null);
      setExpandedMapIdx(null);
    }
  }, [open]);

  // Keep availability selections within the current shoot span.
  useEffect(() => {
    setCast((rows) => rows.map((r) => ({ ...r, days: r.days.filter((d) => d <= totalDays) })));
    setLocations((rows) => rows.map((r) => ({ ...r, days: r.days.filter((d) => d <= totalDays) })));
  }, [totalDays]);

  const setDetail = (k) => (v) => setDetails((d) => ({ ...d, [k]: v }));

  const addCast = () =>
    setCast((r) => [...r, { name: "", role: "supporting", days: [...allDays] }]);
  const addLocation = () => {
    const nextIdx = locations.length;
    setLocations((r) => [
      ...r,
      {
        name: "",
        location_type: "interior",
        permit_notes: "",
        days: [...allDays],
        latitude: 34.0522,
        longitude: -118.2437,
      },
    ]);
    setExpandedMapIdx(nextIdx);
  };

  const updateCast = (i, patch) =>
    setCast((r) => r.map((row, idx) => (idx === i ? { ...row, ...patch } : row)));
  const updateLocation = (i, patch) =>
    setLocations((r) => r.map((row, idx) => (idx === i ? { ...row, ...patch } : row)));
  const removeCast = (i) => setCast((r) => r.filter((_, idx) => idx !== i));
  const removeLocation = (i) => {
    setLocations((r) => r.filter((_, idx) => idx !== i));
    if (expandedMapIdx === i) setExpandedMapIdx(null);
  };

  const toggleCastDay = (i, d) =>
    setCast((r) =>
      r.map((row, idx) =>
        idx === i
          ? { ...row, days: row.days.includes(d) ? row.days.filter((x) => x !== d) : [...row.days, d].sort((a, b) => a - b) }
          : row
      )
    );
  const toggleLocDay = (i, d) =>
    setLocations((r) =>
      r.map((row, idx) =>
        idx === i
          ? { ...row, days: row.days.includes(d) ? row.days.filter((x) => x !== d) : [...row.days, d].sort((a, b) => a - b) }
          : row
      )
    );

  // --- CSV importing for cast & locations -------------------------------------
  const importCsv = (file, target) => {
    const reader = new FileReader();
    reader.onload = (e) => {
      try {
        const text = e.target.result;
        const { rows } = parseCsv(text);
        if (!rows || rows.length === 0) {
          toast.error("CSV file is empty or formatted incorrectly");
          return;
        }
        if (target === "cast") {
          const imported = rows
            .map((r) => ({
              name: r.name || "",
              role: ROLE_OPTIONS.includes((r.role || "").toLowerCase())
                ? r.role.toLowerCase()
                : "supporting",
              days: parseDays(r.available_days, totalDays),
            }))
            .filter((r) => r.name.trim() !== "");
          if (imported.length === 0) {
            toast.error("No valid cast rows found (needs 'name' column)");
            return;
          }
          setCast((prev) => [...prev, ...imported]);
          toast.success(`Imported ${imported.length} cast member${imported.length === 1 ? "" : "s"}`);
        } else if (target === "location") {
          const imported = rows
            .map((r) => ({
              name: r.name || "",
              location_type: TYPE_OPTIONS.includes((r.type || r.location_type || "").toLowerCase())
                ? (r.type || r.location_type).toLowerCase()
                : "interior",
              permit_notes: r.permit_notes || "",
              days: parseDays(r.available_days, totalDays),
              latitude: parseFloat(r.latitude || r.lat) || 34.0522,
              longitude: parseFloat(r.longitude || r.lng || r.lon) || -118.2437,
            }))
            .filter((r) => r.name.trim() !== "");
          if (imported.length === 0) {
            toast.error("No valid location rows found (needs 'name' column)");
            return;
          }
          setLocations((prev) => [...prev, ...imported]);
          toast.success(`Imported ${imported.length} location${imported.length === 1 ? "" : "s"}`);
        }
      } catch (err) {
        toast.error(`CSV parse error: ${err.message}`);
      }
    };
    reader.readAsText(file);
  };

  // --- Historical Data CSV parsing & staging ----------------------------------
  const handleHistoryFileSelect = (file) => {
    if (!file) return;
    setHistoryFile(file);
    setIsValidatingHistory(true);
    const reader = new FileReader();
    reader.onload = (e) => {
      try {
        const text = e.target.result;
        const { headers, rows } = parseCsv(text);
        const accepted = rows.filter(
          (r) => (r.disruption_type || r.type) && (r.strategy || r.resolution_strategy)
        ).length;
        const rejected = rows.length - accepted;
        setHistoryValidation({
          total: rows.length,
          accepted,
          rejected,
          filename: file.name,
        });
      } catch (err) {
        toast.error(`CSV validation error: ${err.message}`);
      } finally {
        setIsValidatingHistory(false);
      }
    };
    reader.readAsText(file);
  };

  // --- Validations -----------------------------------------------------------
  const step1Valid = details.name.trim().length > 0 && totalDays >= 1 && totalDays <= 30;
  const step1Error =
    totalDays < 1
      ? "Shoot end must be after shoot start."
      : totalDays > 30
      ? "Shoots are capped at 30 days for this prototype."
      : null;

  const step2Valid = cast.length > 0 && cast.every((c) => c.name.trim().length > 0);
  const step2Error =
    cast.length === 0
      ? "Add at least one cast member."
      : !step2Valid
      ? "All cast members need a name."
      : null;

  const step3Valid =
    locations.length > 0 && locations.every((l) => l.name.trim().length > 0);
  const step3Error =
    locations.length === 0
      ? "Add at least one location."
      : !step3Valid
      ? "All locations need a name."
      : null;

  // --- Submission ------------------------------------------------------------
  const submit = async () => {
    if (!step1Valid || !step2Valid || !step3Valid) return;
    setSubmitting(true);
    try {
      const payload = {
        name: details.name.trim(),
        shoot_start: details.shoot_start,
        shoot_end: details.shoot_end,
        director: details.director.trim(),
        cast: cast.map((c) => ({
          name: c.name.trim(),
          role: c.role,
          available_days: c.days,
        })),
        locations: locations.map((l) => ({
          name: l.name.trim(),
          location_type: l.location_type,
          permit_notes: l.permit_notes.trim(),
          available_days: l.days,
          latitude: l.latitude || 34.0522,
          longitude: l.longitude || -118.2437,
        })),
      };

      const res = await createProduction(payload);
      const newPid = res.production_id;

      // Ingest historical CSV if attached
      if (historyFile && newPid) {
        try {
          await importHistoryCsv(newPid, historyFile);
          toast.success("Historical studio data imported & isolated in ClickHouse.");
        } catch (impErr) {
          toast.error(`Historical import warning: ${impErr.message}`);
        }
      }

      toast.success(`Production created (${res.scene_count} scenes generated across ${totalDays} days)`);
      onOpenChange(false);
      if (onCreated) onCreated(newPid);
    } catch (err) {
      toast.error(err.response?.data?.detail || err.message || "Failed to create production");
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="max-w-2xl max-h-[90vh] flex flex-col p-0 gap-0 overflow-hidden bg-[var(--cc-surface)] border-[var(--cc-border)] shadow-xl">
        {/* header */}
        <DialogHeader className="border-b border-[var(--cc-border)] px-6 py-4 flex flex-row items-center justify-between">
          <div>
            <DialogTitle className="text-[17px] font-semibold text-[var(--cc-text-primary)]">
              {step === 1 && "Create a Production"}
              {step === 2 && "Add Cast & Crew"}
              {step === 3 && "Add Locations & Map Coordinates"}
              {step === 4 && "Import Historical Data (Optional)"}
            </DialogTitle>
            <DialogDescription className="text-[13px] text-[var(--cc-text-secondary)]">
              {step === 1 && "Define shoot dates and production scope."}
              {step === 2 && "Specify key cast members and their shooting days."}
              {step === 3 && "Pin locations and set open-source map coordinates."}
              {step === 4 && "Upload studio disruption history for tenant-isolated Bayesian blending."}
            </DialogDescription>
          </div>
          <StepDots step={step} />
        </DialogHeader>

        {/* body */}
        <div className="flex-1 overflow-y-auto p-6 space-y-4">
          {/* STEP 1 — details */}
          {step === 1 && (
            <div className="space-y-4" data-testid="wizard-step-details">
              <div className="space-y-2">
                <Label className={labelCls}>Production name</Label>
                <Input
                  data-testid="wizard-name-input"
                  value={details.name}
                  onChange={(e) => setDetail("name")(e.target.value)}
                  placeholder="e.g. Neon Horizon"
                  className={inputCls}
                  autoFocus
                />
              </div>
              <div className="grid grid-cols-2 gap-3">
                <div className="space-y-2">
                  <Label className={labelCls}>Shoot start</Label>
                  <Input
                    data-testid="wizard-start-input"
                    type="date"
                    value={details.shoot_start}
                    onChange={(e) => setDetail("shoot_start")(e.target.value)}
                    className={inputCls}
                  />
                </div>
                <div className="space-y-2">
                  <Label className={labelCls}>Shoot end</Label>
                  <Input
                    data-testid="wizard-end-input"
                    type="date"
                    value={details.shoot_end}
                    min={details.shoot_start}
                    onChange={(e) => setDetail("shoot_end")(e.target.value)}
                    className={inputCls}
                  />
                </div>
              </div>
              <div className="space-y-2">
                <Label className={labelCls}>Director</Label>
                <Input
                  data-testid="wizard-director-input"
                  value={details.director}
                  onChange={(e) => setDetail("director")(e.target.value)}
                  placeholder="e.g. Kai Tanaka"
                  className={inputCls}
                />
              </div>
              <div className="rounded-[10px] border border-[var(--cc-border)] bg-[var(--cc-surface-hover)] px-4 py-3 text-[13px] text-[var(--cc-text-secondary)]">
                {totalDays >= 1 && totalDays <= 30 ? (
                  <>
                    <span className="font-semibold text-[var(--cc-text-primary)]">{totalDays}-day shoot.</span>{" "}
                    {"We'll generate about 10 scenes across these days after you add cast and locations."}
                  </>
                ) : (
                  <span className="font-medium text-[var(--cc-red-text)]">{step1Error}</span>
                )}
              </div>
            </div>
          )}

          {/* STEP 2 — cast */}
          {step === 2 && (
            <div className="space-y-4" data-testid="wizard-step-cast">
              <div className="flex items-center justify-between">
                <span className="text-[13px] text-[var(--cc-text-secondary)]">
                  {cast.length} cast member{cast.length === 1 ? "" : "s"}
                </span>
                <div className="flex items-center gap-2">
                  <button
                    type="button"
                    onClick={() => downloadCsv("cast_template.csv", CAST_CSV_TEMPLATE)}
                    className="cc-transition flex items-center gap-1.5 text-[12px] font-medium text-[var(--cc-text-secondary)] hover:text-[var(--cc-text-primary)]"
                  >
                    <Download size={12} /> Sample CSV
                  </button>
                  <input
                    ref={castFileRef}
                    type="file"
                    accept=".csv,text/csv"
                    className="hidden"
                    onChange={(e) => {
                      if (e.target.files?.[0]) importCsv(e.target.files[0], "cast");
                      e.target.value = "";
                    }}
                  />
                  <Button
                    type="button"
                    size="sm"
                    variant="outline"
                    data-testid="wizard-cast-csv-button"
                    onClick={() => castFileRef.current?.click()}
                    className="h-8 gap-1.5 rounded-[8px] text-[12px]"
                  >
                    <Upload size={12} /> Import CSV
                  </Button>
                </div>
              </div>

              {cast.length === 0 && (
                <div className="rounded-[10px] border border-dashed border-[var(--cc-border)] py-8 text-center">
                  <Users size={22} strokeWidth={1.5} className="mx-auto text-[var(--cc-text-tertiary)]" />
                  <p className="mt-2 text-[13px] font-medium text-[var(--cc-text-primary)]">No cast yet.</p>
                  <p className="text-[12px] text-[var(--cc-text-secondary)]">Add manually or import a CSV.</p>
                </div>
              )}

              <div className="space-y-3">
                {cast.map((c, i) => (
                  <div key={i} className="rounded-[10px] border border-[var(--cc-border)] bg-[var(--cc-surface-hover)] space-y-3 p-4" data-testid={`wizard-cast-row-${i}`}>
                    <div className="flex items-center gap-3">
                      <Input
                        value={c.name}
                        onChange={(e) => updateCast(i, { name: e.target.value })}
                        placeholder="Cast member name"
                        data-testid={`wizard-cast-name-${i}`}
                        className={`${inputCls} flex-1`}
                      />
                      <Segmented
                        options={ROLE_OPTIONS}
                        value={c.role}
                        onChange={(v) => updateCast(i, { role: v })}
                      />
                      <button
                        type="button"
                        onClick={() => removeCast(i)}
                        data-testid={`wizard-cast-remove-${i}`}
                        className="cc-transition rounded-[8px] p-2 text-[var(--cc-text-tertiary)] hover:bg-[var(--cc-surface-sunken)] hover:text-[var(--cc-red-dot)]"
                      >
                        <Trash2 size={15} />
                      </button>
                    </div>
                    <div className="flex items-center justify-between gap-3">
                      <span className="text-[12px] font-medium text-[var(--cc-text-secondary)]">Available days</span>
                      <DayToggles totalDays={totalDays} selected={c.days} onToggle={(d) => toggleCastDay(i, d)} />
                    </div>
                  </div>
                ))}
              </div>

              <Button
                type="button"
                variant="outline"
                onClick={addCast}
                data-testid="wizard-add-cast-button"
                className="h-9 w-full gap-1.5 rounded-[10px] text-[13px]"
              >
                <Plus size={14} /> Add cast member
              </Button>
              {step2Error && <p className="text-[12px] font-medium text-[var(--cc-red-text)]">{step2Error}</p>}
            </div>
          )}

          {/* STEP 3 — locations */}
          {step === 3 && (
            <div className="space-y-4" data-testid="wizard-step-locations">
              <div className="flex items-center justify-between">
                <span className="text-[13px] text-[var(--cc-text-secondary)]">
                  {locations.length} location{locations.length === 1 ? "" : "s"}
                </span>
                <div className="flex items-center gap-2">
                  <button
                    type="button"
                    onClick={() => downloadCsv("locations_template.csv", LOCATION_CSV_TEMPLATE)}
                    className="cc-transition flex items-center gap-1.5 text-[12px] font-medium text-[var(--cc-text-secondary)] hover:text-[var(--cc-text-primary)]"
                  >
                    <Download size={12} /> Sample CSV
                  </button>
                  <input
                    ref={locFileRef}
                    type="file"
                    accept=".csv,text/csv"
                    className="hidden"
                    onChange={(e) => {
                      if (e.target.files?.[0]) importCsv(e.target.files[0], "location");
                      e.target.value = "";
                    }}
                  />
                  <Button
                    type="button"
                    size="sm"
                    variant="outline"
                    data-testid="wizard-loc-csv-button"
                    onClick={() => locFileRef.current?.click()}
                    className="h-8 gap-1.5 rounded-[8px] text-[12px]"
                  >
                    <Upload size={12} /> Import CSV
                  </Button>
                </div>
              </div>

              {locations.length === 0 && (
                <div className="rounded-[10px] border border-dashed border-[var(--cc-border)] py-8 text-center">
                  <MapPin size={22} strokeWidth={1.5} className="mx-auto text-[var(--cc-text-tertiary)]" />
                  <p className="mt-2 text-[13px] font-medium text-[var(--cc-text-primary)]">No locations yet.</p>
                  <p className="text-[12px] text-[var(--cc-text-secondary)]">Add manually or import a CSV.</p>
                </div>
              )}

              <div className="space-y-3">
                {locations.map((l, i) => (
                  <div key={i} className="rounded-[10px] border border-[var(--cc-border)] bg-[var(--cc-surface-hover)] space-y-3 p-4" data-testid={`wizard-loc-row-${i}`}>
                    <div className="flex items-center gap-3">
                      <Input
                        value={l.name}
                        onChange={(e) => updateLocation(i, { name: e.target.value })}
                        placeholder="Location name"
                        data-testid={`wizard-loc-name-${i}`}
                        className={`${inputCls} flex-1`}
                      />
                      <Segmented
                        options={TYPE_OPTIONS}
                        value={l.location_type}
                        onChange={(v) => updateLocation(i, { location_type: v })}
                      />
                      <button
                        type="button"
                        onClick={() => removeLocation(i)}
                        data-testid={`wizard-loc-remove-${i}`}
                        className="cc-transition rounded-[8px] p-2 text-[var(--cc-text-tertiary)] hover:bg-[var(--cc-surface-sunken)] hover:text-[var(--cc-red-dot)]"
                      >
                        <Trash2 size={15} />
                      </button>
                    </div>

                    <div className="grid grid-cols-1 sm:grid-cols-2 gap-2">
                      <Input
                        value={l.permit_notes}
                        onChange={(e) => updateLocation(i, { permit_notes: e.target.value })}
                        placeholder="Permit constraints (optional)"
                        className={inputCls}
                      />
                      <button
                        type="button"
                        onClick={() => setExpandedMapIdx(expandedMapIdx === i ? null : i)}
                        className={`flex items-center justify-between px-3 h-10 rounded-[10px] border text-[13px] font-medium cc-transition ${
                          expandedMapIdx === i
                            ? "border-[var(--cc-text-primary)] bg-[var(--cc-surface)] text-[var(--cc-text-primary)]"
                            : "border-[var(--cc-border)] bg-[var(--cc-surface-sunken)] text-[var(--cc-text-secondary)] hover:text-[var(--cc-text-primary)]"
                        }`}
                      >
                        <span className="flex items-center gap-1.5">
                          <Map size={14} /> Map Coordinates: {l.latitude ? `${l.latitude.toFixed(2)}, ${l.longitude.toFixed(2)}` : "Set Pin"}
                        </span>
                        {expandedMapIdx === i ? <ChevronUp size={14} /> : <ChevronDown size={14} />}
                      </button>
                    </div>

                    {/* Expandable Theme-Aware Map Picker */}
                    {expandedMapIdx === i && (
                      <div className="pt-2 animate-fadeIn">
                        <LocationMapPicker
                          latitude={l.latitude || 34.0522}
                          longitude={l.longitude || -118.2437}
                          locationName={l.name}
                          height="220px"
                          onChange={(coords) => updateLocation(i, { latitude: coords.lat, longitude: coords.lng })}
                        />
                      </div>
                    )}

                    <div className="flex items-center justify-between gap-3 pt-1">
                      <span className="text-[12px] font-medium text-[var(--cc-text-secondary)]">Available days</span>
                      <DayToggles totalDays={totalDays} selected={l.days} onToggle={(d) => toggleLocDay(i, d)} />
                    </div>
                  </div>
                ))}
              </div>

              <Button
                type="button"
                variant="outline"
                onClick={addLocation}
                data-testid="wizard-add-loc-button"
                className="h-9 w-full gap-1.5 rounded-[10px] text-[13px]"
              >
                <Plus size={14} /> Add location
              </Button>
              {step3Error && <p className="text-[12px] font-medium text-[var(--cc-red-text)]">{step3Error}</p>}
            </div>
          )}

          {/* STEP 4 — historical data import (optional) */}
          {step === 4 && (
            <div className="space-y-4" data-testid="wizard-step-history">
              <div className="rounded-[10px] border border-[var(--cc-border)] bg-[var(--cc-surface-hover)] p-4 space-y-3">
                <div className="flex items-start justify-between">
                  <div className="space-y-1">
                    <h4 className="text-[14px] font-semibold text-[var(--cc-text-primary)] flex items-center gap-1.5">
                      <Database className="h-4 w-4 text-[var(--cc-text-secondary)]" /> Studio Disruption History
                    </h4>
                    <p className="text-[12px] text-[var(--cc-text-secondary)]">
                      Ingest your studio's past production logs to personalize recovery calibrations.
                      If sample size is under 200 rows, our Bayesian engine blends your data with the industry baseline.
                    </p>
                  </div>
                  <a
                    href="/api/templates/disruption-history.csv"
                    download="disruption-history-template.csv"
                    className="cc-transition flex items-center gap-1 text-[12px] font-medium text-[var(--cc-text-primary)] underline hover:opacity-80"
                  >
                    <Download size={12} /> CSV Template
                  </a>
                </div>

                {/* Upload Dropzone */}
                <div
                  onClick={() => historyFileRef.current?.click()}
                  className="rounded-[10px] border-2 border-dashed border-[var(--cc-border)] hover:border-[var(--cc-text-primary)]/40 bg-[var(--cc-surface)] p-6 text-center cursor-pointer cc-transition"
                >
                  <input
                    ref={historyFileRef}
                    type="file"
                    accept=".csv,text/csv"
                    className="hidden"
                    onChange={(e) => {
                      if (e.target.files?.[0]) handleHistoryFileSelect(e.target.files[0]);
                      e.target.value = "";
                    }}
                  />
                  <Upload className="h-6 w-6 mx-auto text-[var(--cc-text-tertiary)]" />
                  <p className="mt-2 text-[13px] font-medium text-[var(--cc-text-primary)]">
                    {historyFile ? historyFile.name : "Drop your studio CSV here or click to browse"}
                  </p>
                  <p className="text-[11px] text-[var(--cc-text-secondary)] mt-0.5">
                    Supports EUR, GBP, CAD, USD with automatic ECB exchange rate normalization.
                  </p>
                </div>

                {/* Live Validation Report */}
                {historyValidation && (
                  <div className="rounded-[9px] border border-[var(--cc-border)] bg-[var(--cc-surface-sunken)] p-3 space-y-2">
                    <div className="flex items-center justify-between text-[12px]">
                      <span className="font-medium text-[var(--cc-text-primary)]">Validation Summary</span>
                      <span className="text-[var(--cc-text-secondary)]">{historyValidation.total} total rows parsed</span>
                    </div>
                    <div className="grid grid-cols-2 gap-2 text-[12px]">
                      <div className="rounded-[6px] bg-[var(--cc-green-bg)] text-[var(--cc-green-text)] px-2.5 py-1.5 flex items-center gap-1.5 font-medium">
                        <Check size={14} /> {historyValidation.accepted} rows ready to ingest
                      </div>
                      <div className={`rounded-[6px] px-2.5 py-1.5 flex items-center gap-1.5 font-medium ${
                        historyValidation.rejected > 0
                          ? "bg-[var(--cc-red-bg)] text-[var(--cc-red-text)]"
                          : "bg-[var(--cc-surface)] text-[var(--cc-text-tertiary)]"
                      }`}>
                        <AlertCircle size={14} /> {historyValidation.rejected} invalid/filtered
                      </div>
                    </div>
                  </div>
                )}
              </div>
            </div>
          )}
        </div>

        {/* footer */}
        <div className="border-t border-[var(--cc-border)] flex items-center justify-between px-6 py-4 bg-[var(--cc-surface-hover)]">
          <Button
            type="button"
            variant="ghost"
            disabled={submitting}
            onClick={() => (step === 1 ? onOpenChange(false) : setStep(step - 1))}
            className="h-9 gap-1.5 rounded-[10px] text-[13px]"
          >
            {step === 1 ? "Cancel" : <><ArrowLeft size={14} /> Back</>}
          </Button>

          {step < 4 ? (
            <Button
              type="button"
              data-testid="wizard-next-button"
              disabled={step === 1 ? !step1Valid : step === 2 ? !step2Valid : !step3Valid}
              onClick={() => setStep(step + 1)}
              className="h-9 gap-1.5 rounded-[10px]"
            >
              Continue <ArrowRight size={14} />
            </Button>
          ) : (
            <Button
              type="button"
              data-testid="wizard-create-button"
              disabled={!step3Valid || submitting}
              onClick={submit}
              className="h-9 gap-1.5 rounded-[10px]"
            >
              {submitting ? <Loader2 size={14} className="animate-spin" /> : <Check size={14} />}
              {submitting ? "Creating…" : historyFile ? "Import & Create Production" : "Create Production"}
            </Button>
          )}
        </div>
      </DialogContent>
    </Dialog>
  );
};

export default CreateProductionWizard;
