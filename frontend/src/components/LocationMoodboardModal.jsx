import React, { useEffect, useState } from "react";
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogDescription } from "./ui/dialog";
import { Button } from "./ui/button";
import { Skeleton } from "./ui/skeleton";
import { getLocationMoodboard, getLocationMoodboardImageUrl } from "../lib/api";
import { Sparkles, Zap, AlertCircle } from "lucide-react";

export function LocationMoodboardModal({ open, onOpenChange, locationId, locationName, sceneId }) {
  const [loading, setLoading] = useState(false);
  const [imgLoading, setImgLoading] = useState(true);
  const [imgError, setImgError] = useState(false);
  const [moodboard, setMoodboard] = useState(null);
  const [unavailable, setUnavailable] = useState(false);
  const [showPrompt, setShowPrompt] = useState(false);

  useEffect(() => {
    if (!open || !locationId) {
      setMoodboard(null);
      setUnavailable(false);
      setLoading(false);
      setImgLoading(true);
      setImgError(false);
      return;
    }

    let active = true;
    setLoading(true);
    setImgLoading(true);
    setImgError(false);
    setUnavailable(false);
    setMoodboard(null);

    getLocationMoodboard(locationId, sceneId)
      .then((res) => {
        if (!active) return;
        if (res && res.status === "ready" && (res.image_url || res.image_base64)) {
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
  const imageUrl =
    moodboard?.image_url ||
    (locationId && typeof getLocationMoodboardImageUrl === "function"
      ? getLocationMoodboardImageUrl(locationId)
      : locationId
      ? `/api/locations/${encodeURIComponent(locationId)}/moodboard/image`
      : "");
  const isFailed = unavailable || imgError;

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent
        data-testid="location-moodboard-modal"
        className="max-w-2xl overflow-hidden rounded-[16px] border border-[var(--cc-border)] bg-[var(--cc-surface-card)] p-0 shadow-2xl"
      >
        <DialogHeader className="border-b border-[var(--cc-border)] px-6 pt-5 pb-4">
          <div className="flex items-center gap-2 text-[11px] font-semibold uppercase tracking-wider text-[var(--cc-text-tertiary)]">
            <Sparkles size={12} className="text-[var(--cc-yellow-dot)]" />
            <span>AI Mood-Board Preview (Gemini)</span>
          </div>
          <DialogTitle className="font-display mt-1 text-[20px] font-semibold text-[var(--cc-text-primary)]">
            {displayLocName}
          </DialogTitle>
          <DialogDescription className="text-[13px] text-[var(--cc-text-secondary)]">
            On-demand cinematic atmosphere & lighting preview before committing recovery schedule moves.
          </DialogDescription>
        </DialogHeader>

        <div className="p-6">
          {/* Metadata loading state */}
          {loading && (
            <div className="space-y-3" data-testid="moodboard-loading-state">
              <div className="relative aspect-video w-full overflow-hidden rounded-[12px] border border-[var(--cc-border)] bg-[var(--cc-surface-sunken)]">
                <Skeleton className="cc-shimmer h-full w-full" />
                <div className="absolute inset-0 flex flex-col items-center justify-center gap-2 text-center p-4">
                  <Sparkles size={24} className="animate-spin text-[var(--cc-yellow-dot)]" />
                  <p className="text-[13px] font-medium text-[var(--cc-text-primary)]">
                    Generating cinematic still with Gemini image generation...
                  </p>
                  <p className="text-[11px] text-[var(--cc-text-tertiary)]">
                    Calibrating volumetric lighting and location metadata
                  </p>
                </div>
              </div>
            </div>
          )}

          {/* Ready state with URL-based image rendering */}
          {!loading && moodboard && !isFailed && (
            <div className="space-y-4" data-testid="moodboard-ready-state">
              <div className="relative aspect-video w-full overflow-hidden rounded-[12px] border border-[var(--cc-border)] bg-black shadow-inner">
                {imgLoading && (
                  <div className="absolute inset-0 z-10">
                    <Skeleton className="cc-shimmer h-full w-full" />
                  </div>
                )}
                <img
                  src={imageUrl}
                  alt={`AI-generated preview (Gemini image generation) — ${displayLocName}`}
                  data-testid="moodboard-image"
                  onLoad={() => setImgLoading(false)}
                  onError={() => {
                    setImgError(true);
                    setImgLoading(false);
                  }}
                  className={`h-full w-full object-cover transition-opacity duration-300 ${
                    imgLoading ? "opacity-0" : "opacity-100"
                  }`}
                />
                <div className="absolute bottom-2.5 left-2.5 rounded-[6px] bg-black/60 backdrop-blur-md border border-white/10 px-2.5 py-1 text-[10.5px] font-medium text-white/90">
                  AI-generated preview (Gemini image generation) — {displayLocName}
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

          {/* Graceful fallback state on 202/error/404 */}
          {!loading && isFailed && (
            <div
              data-testid="moodboard-unavailable-state"
              className="rounded-[12px] border border-[var(--cc-border)] bg-[var(--cc-surface-sunken)] p-6 text-center"
            >
              <AlertCircle size={28} className="mx-auto text-[var(--cc-text-tertiary)]" />
              <h4 className="mt-3 text-[14px] font-semibold text-[var(--cc-text-primary)]">
                Visual preview currently unavailable
              </h4>
              <p className="mt-1 text-[12.5px] text-[var(--cc-text-secondary)]">
                We couldn't generate a visual preview right now. You can still select and execute this recovery option.
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
