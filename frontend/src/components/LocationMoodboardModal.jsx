import React, { useEffect, useState } from "react";
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogDescription } from "./ui/dialog";
import { Button } from "./ui/button";
import { Skeleton } from "./ui/skeleton";
import { getLocationMoodboard } from "../lib/api";
import { Sparkles, Image as ImageIcon, Zap, AlertCircle, X } from "lucide-react";

export function LocationMoodboardModal({ open, onOpenChange, locationId, locationName, sceneId }) {
  const [loading, setLoading] = useState(false);
  const [moodboard, setMoodboard] = useState(null);
  const [unavailable, setUnavailable] = useState(false);
  const [showPrompt, setShowPrompt] = useState(false);

  useEffect(() => {
    if (!open || !locationId) {
      setMoodboard(null);
      setUnavailable(false);
      setLoading(false);
      return;
    }

    let active = true;
    setLoading(true);
    setUnavailable(false);
    setMoodboard(null);

    getLocationMoodboard(locationId, sceneId)
      .then((res) => {
        if (!active) return;
        if (res && res.status === "ready" && res.image_base64) {
          setMoodboard(res);
          setUnavailable(false);
        } else {
          setUnavailable(true);
        }
      })
      .catch(() => {
        if (!active) return;
        setUnavailable(true);
      })
      .finally(() => {
        if (active) setLoading(false);
      });

    return () => {
      active = false;
    };
  }, [open, locationId, sceneId]);

  const displayLocName = moodboard?.location_name || locationName || locationId || "Alternate Location";

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent
        data-testid="location-moodboard-modal"
        className="max-w-2xl overflow-hidden rounded-[16px] border border-[var(--cc-border)] bg-[var(--cc-surface-card)] p-0 shadow-2xl"
      >
        <DialogHeader className="border-b border-[var(--cc-border)] px-6 pt-5 pb-4">
          <div className="flex items-center gap-2 text-[11px] font-semibold uppercase tracking-wider text-[var(--cc-text-tertiary)]">
            <Sparkles size={12} className="text-[var(--cc-yellow-dot)]" />
            <span>AI Mood-Board Preview (Imagen 3)</span>
          </div>
          <DialogTitle className="font-display mt-1 text-[20px] font-semibold text-[var(--cc-text-primary)]">
            {displayLocName}
          </DialogTitle>
          <DialogDescription className="text-[13px] text-[var(--cc-text-secondary)]">
            On-demand cinematic atmosphere & lighting preview before committing recovery schedule moves.
          </DialogDescription>
        </DialogHeader>

        <div className="p-6">
          {loading && (
            <div className="space-y-3" data-testid="moodboard-loading-state">
              <div className="relative aspect-video w-full overflow-hidden rounded-[12px] border border-[var(--cc-border)] bg-[var(--cc-surface-sunken)]">
                <Skeleton className="cc-shimmer h-full w-full" />
                <div className="absolute inset-0 flex flex-col items-center justify-center gap-2 text-center p-4">
                  <Sparkles size={24} className="animate-spin text-[var(--cc-yellow-dot)]" />
                  <p className="text-[13px] font-medium text-[var(--cc-text-primary)]">
                    Generating cinematic still with Imagen 3...
                  </p>
                  <p className="text-[11px] text-[var(--cc-text-tertiary)]">
                    Calibrating volumetric lighting and location metadata
                  </p>
                </div>
              </div>
            </div>
          )}

          {!loading && moodboard?.image_base64 && (
            <div className="space-y-4" data-testid="moodboard-ready-state">
              <div className="relative aspect-video w-full overflow-hidden rounded-[12px] border border-[var(--cc-border)] bg-black shadow-inner">
                <img
                  src={`data:image/jpeg;base64,${moodboard.image_base64}`}
                  alt={`AI-generated preview (Imagen 3): ${displayLocName}`}
                  data-testid="moodboard-image"
                  className="h-full w-full object-cover transition-opacity duration-300"
                />
                <div className="absolute bottom-2.5 left-2.5 rounded-[6px] bg-black/60 backdrop-blur-md border border-white/10 px-2.5 py-1 text-[10.5px] font-medium text-white/90">
                  AI-generated preview (Imagen 3): {displayLocName}
                </div>
                {moodboard.cached && (
                  <div className="absolute top-2.5 right-2.5 flex items-center gap-1 rounded-[6px] bg-black/60 backdrop-blur-md border border-white/10 px-2 py-0.5 text-[10px] font-medium text-emerald-300">
                    <Zap size={10} />
                    <span>Cached</span>
                  </div>
                )}
              </div>

              <div className="flex items-center justify-between text-[11px] text-[var(--cc-text-tertiary)]">
                <span className="flex items-center gap-1.5">
                  <span className="h-1.5 w-1.5 rounded-full bg-[var(--cc-green-dot)]" />
                  Photorealistic 16:9 Panavision still
                </span>
                <button
                  type="button"
                  onClick={() => setShowPrompt(!showPrompt)}
                  className="text-[var(--cc-text-secondary)] hover:text-[var(--cc-text-primary)] underline transition-colors"
                >
                  {showPrompt ? "Hide prompt" : "Inspect prompt"}
                </button>
              </div>

              {showPrompt && moodboard.prompt && (
                <div className="rounded-[8px] border border-[var(--cc-border)] bg-[var(--cc-surface-sunken)] p-3 font-mono text-[11px] leading-relaxed text-[var(--cc-text-secondary)]">
                  {moodboard.prompt}
                </div>
              )}
            </div>
          )}

          {!loading && unavailable && (
            <div
              data-testid="moodboard-unavailable-state"
              className="rounded-[12px] border border-[var(--cc-border)] bg-[var(--cc-surface-sunken)] p-6 text-center"
            >
              <AlertCircle size={28} className="mx-auto text-[var(--cc-text-tertiary)]" />
              <h4 className="mt-3 text-[14px] font-semibold text-[var(--cc-text-primary)]">
                Visual preview currently unavailable
              </h4>
              <p className="mt-1 text-[12.5px] text-[var(--cc-text-secondary)]">
                We couldn't generate an Imagen 3 preview right now. You can still select and execute this recovery option.
              </p>
            </div>
          )}
        </div>

        <div className="flex items-center justify-end border-t border-[var(--cc-border)] bg-[var(--cc-surface-sunken)]/50 px-6 py-3.5">
          <Button
            type="button"
            variant="outline"
            onClick={() => onOpenChange(false)}
            className="rounded-[8px] text-[13px]"
          >
            Close
          </Button>
        </div>
      </DialogContent>
    </Dialog>
  );
}
