import React, { useEffect, useRef, useState } from "react";
import { toast } from "sonner";
import {
  Dialog, DialogContent, DialogHeader, DialogTitle, DialogDescription,
} from "./ui/dialog";
import { Button } from "./ui/button";
import {
  uploadSchedulePDF,
  getScheduleImportJob,
  confirmScheduleImport,
} from "../lib/api";
import {
  Upload, FileText, Loader2, CheckCircle2, AlertCircle, Sparkles,
  Calendar, MapPin, Users, Film, ArrowRight, RefreshCw, X,
} from "lucide-react";

export const ScheduleImportModal = ({
  open,
  onOpenChange,
  productionId,
  onImportComplete,
}) => {
  const [file, setFile] = useState(null);
  const [dragActive, setDragActive] = useState(false);
  const [stage, setStage] = useState("idle"); // idle | uploading | processing | ready | confirming | success | failed
  const [jobId, setJobId] = useState(null);
  const [preview, setPreview] = useState(null);
  const [errorMsg, setErrorMsg] = useState("");
  const fileInputRef = useRef(null);
  const pollTimerRef = useRef(null);

  // Clean up timer on unmount or dialog close
  useEffect(() => {
    return () => {
      if (pollTimerRef.current) clearInterval(pollTimerRef.current);
    };
  }, []);

  const resetState = () => {
    if (pollTimerRef.current) clearInterval(pollTimerRef.current);
    setFile(null);
    setStage("idle");
    setJobId(null);
    setPreview(null);
    setErrorMsg("");
  };

  const handleOpenChange = (isOpen) => {
    if (!isOpen) {
      resetState();
    }
    onOpenChange(isOpen);
  };

  const handleDrag = (e) => {
    e.preventDefault();
    e.stopPropagation();
    if (e.type === "dragenter" || e.type === "dragover") {
      setDragActive(true);
    } else if (e.type === "dragleave") {
      setDragActive(false);
    }
  };

  const handleDrop = (e) => {
    e.preventDefault();
    e.stopPropagation();
    setDragActive(false);
    if (e.dataTransfer.files && e.dataTransfer.files[0]) {
      handleFileSelected(e.dataTransfer.files[0]);
    }
  };

  const handleFileSelected = (selectedFile) => {
    if (!selectedFile) return;
    if (!selectedFile.name.toLowerCase().endsWith(".pdf")) {
      toast.error("Please select a PDF file (.pdf)");
      return;
    }
    if (selectedFile.size > 10 * 1024 * 1024) {
      toast.error("File exceeds 10MB limit");
      return;
    }
    setFile(selectedFile);
    startUploadAndParse(selectedFile);
  };

  const startUploadAndParse = async (pdfFile) => {
    setStage("uploading");
    setErrorMsg("");
    try {
      const resp = await uploadSchedulePDF(productionId, pdfFile);
      const newJobId = resp.job_id;
      setJobId(newJobId);
      setStage("processing");

      // Start polling for extraction results
      if (pollTimerRef.current) clearInterval(pollTimerRef.current);
      pollTimerRef.current = setInterval(async () => {
        try {
          const job = await getScheduleImportJob(newJobId);
          if (job.status === "ready") {
            clearInterval(pollTimerRef.current);
            setPreview(job.preview);
            setStage("ready");
          } else if (job.status === "failed") {
            clearInterval(pollTimerRef.current);
            setErrorMsg(job.error || "We couldn't read this schedule. You can still enter it manually or via CSV.");
            setStage("failed");
          }
        } catch (err) {
          logger_warn(err);
        }
      }, 1500);
    } catch (err) {
      setStage("failed");
      setErrorMsg(err?.response?.data?.detail || err?.message || "Failed to upload PDF file");
    }
  };

  const logger_warn = (err) => {
    // Silent catch for intermittent network hiccup during poll
  };

  const handleConfirm = async () => {
    if (!jobId) return;
    setStage("confirming");
    try {
      const res = await confirmScheduleImport(jobId);
      setStage("success");
      toast.success("Schedule imported successfully into ClickHouse!");
      if (onImportComplete) {
        onImportComplete(res);
      }
      setTimeout(() => {
        handleOpenChange(false);
      }, 1600);
    } catch (err) {
      setStage("failed");
      setErrorMsg(err?.response?.data?.detail || err?.message || "Failed to confirm and import schedule");
      toast.error("Failed to commit schedule changes");
    }
  };

  return (
    <Dialog open={open} onOpenChange={handleOpenChange}>
      <DialogContent
        data-testid="schedule-import-modal"
        className="max-w-2xl overflow-hidden rounded-[20px] border border-[var(--cc-border)] bg-[var(--cc-surface)] p-0 shadow-2xl text-[var(--cc-text-primary)]"
      >
        <DialogHeader className="border-b border-[var(--cc-border)] px-6 py-5">
          <div className="flex items-center gap-2 text-[12px] font-semibold uppercase tracking-wider text-[var(--cc-text-tertiary)]">
            <Sparkles size={14} className="text-[var(--cc-accent-amber)]" />
            <span>Document Understanding</span>
          </div>
          <DialogTitle className="mt-1 font-display text-[22px] font-semibold text-[var(--cc-text-primary)]">
            Import shooting schedule (PDF)
          </DialogTitle>
          <DialogDescription className="text-[13px] text-[var(--cc-text-secondary)]">
            Gemini extracts shoot days, scenes, cast, and filming locations automatically into ClickHouse.
          </DialogDescription>
        </DialogHeader>

        <div className="p-6">
          {/* STAGE 1: Dropzone */}
          {stage === "idle" && (
            <div
              data-testid="pdf-dropzone"
              onDragEnter={handleDrag}
              onDragLeave={handleDrag}
              onDragOver={handleDrag}
              onDrop={handleDrop}
              onClick={() => fileInputRef.current?.click()}
              className={`cc-transition group flex cursor-pointer flex-col items-center justify-center rounded-[16px] border-2 border-dashed p-10 text-center ${
                dragActive
                  ? "border-[var(--cc-text-primary)] bg-[var(--cc-surface-hover)]"
                  : "border-[var(--cc-border)] bg-[var(--cc-surface-sunken)] hover:border-[var(--cc-text-tertiary)] hover:bg-[var(--cc-surface-hover)]"
              }`}
            >
              <input
                ref={fileInputRef}
                type="file"
                accept=".pdf,application/pdf"
                data-testid="schedule-pdf-input"
                className="hidden"
                onChange={(e) => {
                  if (e.target.files && e.target.files[0]) {
                    handleFileSelected(e.target.files[0]);
                  }
                }}
              />
              <div className="flex h-14 w-14 items-center justify-center rounded-full bg-[var(--cc-surface)] shadow-sm text-[var(--cc-text-primary)] group-hover:scale-105 cc-transition">
                <Upload size={24} strokeWidth={1.75} />
              </div>
              <h4 className="mt-4 text-[15px] font-medium text-[var(--cc-text-primary)]">
                Drop your shooting schedule or call sheet PDF here
              </h4>
              <p className="mt-1 text-[13px] text-[var(--cc-text-secondary)]">
                or click to browse your computer
              </p>
              <div className="mt-4 flex items-center gap-3 text-[11px] text-[var(--cc-text-tertiary)]">
                <span>PDF up to 10MB</span>
                <span>•</span>
                <span>Max 20 pages</span>
                <span>•</span>
                <span>One-liner call sheets & one-liners</span>
              </div>
            </div>
          )}

          {/* STAGE 2: Uploading & Processing */}
          {(stage === "uploading" || stage === "processing") && (
            <div className="flex flex-col items-center justify-center py-12 text-center">
              <div className="relative flex h-16 w-16 items-center justify-center">
                <div className="absolute inset-0 rounded-full border-2 border-[var(--cc-border)]" />
                <Loader2 size={32} className="animate-spin text-[var(--cc-text-primary)]" />
              </div>
              <h4 className="mt-5 font-display text-[17px] font-semibold text-[var(--cc-text-primary)]">
                {stage === "uploading" ? "Uploading document..." : "Extracting schedule with Gemini..."}
              </h4>
              <p className="mt-1.5 max-w-sm text-[13px] text-[var(--cc-text-secondary)]">
                Analyzing scenes, shoot days, cast breakdowns, and locations. This usually takes 5–15 seconds.
              </p>
              {file && (
                <div className="mt-4 inline-flex items-center gap-2 rounded-full border border-[var(--cc-border)] bg-[var(--cc-surface-sunken)] px-3 py-1 text-[12px] text-[var(--cc-text-tertiary)]">
                  <FileText size={13} />
                  <span>{file.name} ({(file.size / 1024).toFixed(0)} KB)</span>
                </div>
              )}
            </div>
          )}

          {/* STAGE 3: Extraction Ready / Preview */}
          {stage === "ready" && preview && (
            <div data-testid="schedule-preview-container" className="space-y-5">
              {/* Summary Stats Grid */}
              <div className="grid grid-cols-2 gap-3 sm:grid-cols-4">
                <div className="rounded-[12px] border border-[var(--cc-border)] bg-[var(--cc-surface-sunken)] p-3.5">
                  <div className="flex items-center gap-1.5 text-[11px] font-medium text-[var(--cc-text-secondary)]">
                    <Calendar size={13} className="text-[var(--cc-text-tertiary)]" />
                    <span>Shoot Days</span>
                  </div>
                  <div className="tabular mt-1 text-[22px] font-semibold text-[var(--cc-text-primary)]">
                    {preview.days_count}
                  </div>
                </div>

                <div className="rounded-[12px] border border-[var(--cc-border)] bg-[var(--cc-surface-sunken)] p-3.5">
                  <div className="flex items-center gap-1.5 text-[11px] font-medium text-[var(--cc-text-secondary)]">
                    <Film size={13} className="text-[var(--cc-text-tertiary)]" />
                    <span>Scenes</span>
                  </div>
                  <div className="tabular mt-1 text-[22px] font-semibold text-[var(--cc-text-primary)]">
                    {preview.scenes_count}
                  </div>
                </div>

                <div className="rounded-[12px] border border-[var(--cc-border)] bg-[var(--cc-surface-sunken)] p-3.5">
                  <div className="flex items-center gap-1.5 text-[11px] font-medium text-[var(--cc-text-secondary)]">
                    <Users size={13} className="text-[var(--cc-text-tertiary)]" />
                    <span>Cast Members</span>
                  </div>
                  <div className="tabular mt-1 text-[22px] font-semibold text-[var(--cc-text-primary)]">
                    {preview.cast_count}
                  </div>
                </div>

                <div className="rounded-[12px] border border-[var(--cc-border)] bg-[var(--cc-surface-sunken)] p-3.5">
                  <div className="flex items-center gap-1.5 text-[11px] font-medium text-[var(--cc-text-secondary)]">
                    <MapPin size={13} className="text-[var(--cc-text-tertiary)]" />
                    <span>Locations</span>
                  </div>
                  <div className="tabular mt-1 text-[22px] font-semibold text-[var(--cc-text-primary)]">
                    {preview.locations_count}
                  </div>
                </div>
              </div>

              {/* Sample Scenes Table */}
              <div>
                <div className="flex items-center justify-between mb-2">
                  <span className="text-[12px] font-semibold uppercase tracking-wider text-[var(--cc-text-tertiary)]">
                    Extracted Scene Breakdown (Sample)
                  </span>
                  <span className="text-[11px] text-[var(--cc-text-quaternary)]">
                    Showing {Math.min(preview.sample_scenes?.length || 0, 6)} of {preview.scenes_count} scenes
                  </span>
                </div>
                <div className="max-h-48 overflow-y-auto rounded-[12px] border border-[var(--cc-border)] bg-[var(--cc-surface-sunken)]">
                  <table className="w-full text-left text-[12px]">
                    <thead className="border-b border-[var(--cc-border)] bg-[var(--cc-surface)] text-[11px] font-medium text-[var(--cc-text-secondary)]">
                      <tr>
                        <th className="py-2 px-3">Scene</th>
                        <th className="py-2 px-3">Title / Setting</th>
                        <th className="py-2 px-3">Location</th>
                        <th className="py-2 px-3 text-right">Day</th>
                      </tr>
                    </thead>
                    <tbody className="divide-y divide-[var(--cc-border)] font-sans">
                      {preview.sample_scenes?.map((sc, idx) => (
                        <tr key={idx} className="hover:bg-[var(--cc-surface-hover)]">
                          <td className="py-2 px-3 font-semibold text-[var(--cc-text-primary)]">
                            {sc.scene_number || `sc_${idx + 1}`}
                          </td>
                          <td className="py-2 px-3 text-[var(--cc-text-secondary)]">
                            <span className="mr-1.5 inline-block rounded bg-[var(--cc-border)] px-1 py-0.5 text-[10px] font-medium uppercase text-[var(--cc-text-primary)]">
                              {sc.int_ext || "INT"}
                            </span>
                            {sc.scene_title}
                          </td>
                          <td className="py-2 px-3 text-[var(--cc-text-secondary)]">
                            {sc.location_name || "Stage A"}
                          </td>
                          <td className="py-2 px-3 text-right tabular text-[var(--cc-text-primary)]">
                            Day {sc.shoot_day}
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              </div>

              {/* Sample Cast & Locations Chips */}
              <div className="grid grid-cols-2 gap-3 text-[12px]">
                <div className="rounded-[12px] border border-[var(--cc-border)] p-3">
                  <span className="text-[11px] font-medium text-[var(--cc-text-tertiary)] block mb-1.5">
                    Cast ({preview.sample_cast?.length || 0}):
                  </span>
                  <div className="flex flex-wrap gap-1">
                    {preview.sample_cast?.map((name, i) => (
                      <span key={i} className="rounded-full bg-[var(--cc-surface-sunken)] border border-[var(--cc-border)] px-2 py-0.5 text-[11px] text-[var(--cc-text-secondary)]">
                        {name}
                      </span>
                    ))}
                  </div>
                </div>

                <div className="rounded-[12px] border border-[var(--cc-border)] p-3">
                  <span className="text-[11px] font-medium text-[var(--cc-text-tertiary)] block mb-1.5">
                    Locations ({preview.sample_locations?.length || 0}):
                  </span>
                  <div className="flex flex-wrap gap-1">
                    {preview.sample_locations?.map((loc, i) => (
                      <span key={i} className="rounded-full bg-[var(--cc-surface-sunken)] border border-[var(--cc-border)] px-2 py-0.5 text-[11px] text-[var(--cc-text-secondary)]">
                        {loc}
                      </span>
                    ))}
                  </div>
                </div>
              </div>
            </div>
          )}

          {/* STAGE 4: Success */}
          {stage === "success" && (
            <div className="flex flex-col items-center justify-center py-10 text-center">
              <div className="flex h-14 w-14 items-center justify-center rounded-full bg-[var(--cc-accent-emerald)]/10 text-[var(--cc-accent-emerald)]">
                <CheckCircle2 size={32} />
              </div>
              <h4 className="mt-4 font-display text-[18px] font-semibold text-[var(--cc-text-primary)]">
                Schedule successfully imported
              </h4>
              <p className="mt-1 text-[13px] text-[var(--cc-text-secondary)]">
                Your scenes, cast, and filming locations have landed in ClickHouse.
              </p>
            </div>
          )}

          {/* STAGE 5: Failed / Error */}
          {stage === "failed" && (
            <div data-testid="schedule-import-error" className="space-y-4">
              <div className="flex items-start gap-3 rounded-[14px] border border-[var(--cc-accent-rose)]/20 bg-[var(--cc-accent-rose)]/5 p-4 text-[var(--cc-text-primary)]">
                <AlertCircle size={20} className="mt-0.5 shrink-0 text-[var(--cc-accent-rose)]" />
                <div>
                  <h5 className="text-[14px] font-semibold">
                    We couldn't read this schedule
                  </h5>
                  <p className="mt-1 text-[13px] text-[var(--cc-text-secondary)]">
                    {errorMsg || "We couldn't read this schedule. You can still enter it manually or via CSV."}
                  </p>
                </div>
              </div>

              <div className="rounded-[14px] border border-[var(--cc-border)] bg-[var(--cc-surface-sunken)] p-4 text-[13px] text-[var(--cc-text-secondary)]">
                <p className="font-medium text-[var(--cc-text-primary)]">What you can do:</p>
                <ul className="mt-2 list-inside list-disc space-y-1">
                  <li>Try another PDF format (one-liner schedule, call sheet, or scene breakdown).</li>
                  <li>Import your schedule via standard CSV in Production Settings.</li>
                  <li>Use the manual production setup wizard to configure scenes and cast.</li>
                </ul>
              </div>
            </div>
          )}
        </div>

        {/* Footer Actions */}
        <div className="flex items-center justify-between border-t border-[var(--cc-border)] bg-[var(--cc-surface-sunken)] px-6 py-4">
          {stage === "idle" && (
            <>
              <Button
                variant="ghost"
                onClick={() => handleOpenChange(false)}
                className="text-[13px] text-[var(--cc-text-secondary)]"
              >
                Cancel
              </Button>
              <Button
                disabled={!file}
                onClick={() => file && startUploadAndParse(file)}
                className="bg-[var(--cc-text-primary)] text-[var(--cc-canvas)] hover:bg-[var(--cc-text-primary)]/90"
              >
                Upload & parse
              </Button>
            </>
          )}

          {(stage === "uploading" || stage === "processing") && (
            <div className="w-full flex justify-end">
              <Button
                variant="ghost"
                onClick={resetState}
                className="text-[13px] text-[var(--cc-text-secondary)]"
              >
                Cancel
              </Button>
            </div>
          )}

          {stage === "ready" && (
            <>
              <Button
                variant="ghost"
                onClick={resetState}
                className="text-[13px] text-[var(--cc-text-secondary)] flex items-center gap-1.5"
              >
                <RefreshCw size={13} />
                Upload different file
              </Button>
              <Button
                data-testid="confirm-schedule-import-btn"
                onClick={handleConfirm}
                className="bg-[var(--cc-text-primary)] text-[var(--cc-canvas)] hover:bg-[var(--cc-text-primary)]/90 flex items-center gap-2"
              >
                <span>Confirm import</span>
                <ArrowRight size={14} />
              </Button>
            </>
          )}

          {stage === "confirming" && (
            <div className="w-full flex items-center justify-center gap-2 text-[13px] text-[var(--cc-text-secondary)]">
              <Loader2 size={16} className="animate-spin text-[var(--cc-text-primary)]" />
              <span>Saving schedule to ClickHouse...</span>
            </div>
          )}

          {stage === "failed" && (
            <>
              <Button
                variant="ghost"
                onClick={() => handleOpenChange(false)}
                className="text-[13px] text-[var(--cc-text-secondary)]"
              >
                Close
              </Button>
              <Button
                onClick={resetState}
                className="bg-[var(--cc-text-primary)] text-[var(--cc-canvas)] hover:bg-[var(--cc-text-primary)]/90 flex items-center gap-1.5"
              >
                <RefreshCw size={13} />
                <span>Try again</span>
              </Button>
            </>
          )}

          {stage === "success" && (
            <div className="w-full flex justify-end">
              <Button
                onClick={() => handleOpenChange(false)}
                className="bg-[var(--cc-text-primary)] text-[var(--cc-canvas)]"
              >
                Done
              </Button>
            </div>
          )}
        </div>
      </DialogContent>
    </Dialog>
  );
};
