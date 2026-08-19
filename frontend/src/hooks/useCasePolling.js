import { useEffect, useRef, useState } from "react";
import { getCase } from "../lib/api";

export function useCasePolling(caseId, intervalMs = 1000) {
  const [caseData, setCaseData] = useState(null);
  const [error, setError] = useState(null);
  const timer = useRef(null);

  useEffect(() => {
    if (!caseId) return undefined;
    let alive = true;

    const tick = async () => {
      try {
        const data = await getCase(caseId);
        if (alive) {
          setCaseData(data);
          setError(null);
        }
      } catch (e) {
        if (alive) setError(e?.response?.data?.detail || e.message);
      }
    };

    tick();
    timer.current = setInterval(tick, intervalMs);
    return () => {
      alive = false;
      if (timer.current) clearInterval(timer.current);
    };
  }, [caseId, intervalMs]);

  return { caseData, error };
}
