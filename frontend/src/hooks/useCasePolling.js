import { useEffect, useRef, useState } from "react";
import { getCase } from "../lib/api";

export const TERMINAL_STATUSES = new Set(["approved", "closed", "error", "options_ready"]);

export function useCasePolling(caseId, initialIntervalMs = 1000, maxIntervalMs = 15000, backoffFactor = 1.5) {
  const [caseData, setCaseData] = useState(null);
  const [error, setError] = useState(null);
  const timer = useRef(null);

  useEffect(() => {
    if (!caseId) {
      setCaseData(null);
      setError(null);
      return undefined;
    }

    let alive = true;
    let currentInterval = initialIntervalMs;

    const poll = async () => {
      try {
        const data = await getCase(caseId);
        if (!alive) return;

        setCaseData(data);
        setError(null);

        // Stop polling if the case reached a terminal state
        if (data?.status && TERMINAL_STATUSES.has(data.status)) {
          return;
        }

        // Apply exponential backoff for next poll while investigating / open
        timer.current = setTimeout(poll, currentInterval);
        currentInterval = Math.min(maxIntervalMs, currentInterval * backoffFactor);
      } catch (e) {
        if (!alive) return;
        setError(e?.response?.data?.detail || e.message);

        // Backoff on error as well
        timer.current = setTimeout(poll, currentInterval);
        currentInterval = Math.min(maxIntervalMs, currentInterval * backoffFactor);
      }
    };

    // Immediate first fetch
    poll();

    return () => {
      alive = false;
      if (timer.current) clearTimeout(timer.current);
    };
  }, [caseId, initialIntervalMs, maxIntervalMs, backoffFactor]);

  return { caseData, error };
}

