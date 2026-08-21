import { useEffect, useRef, useState } from "react";
import { safeMatchMedia } from "../lib/storage";

/** Apple Health-style count-up for stat numbers. Respects reduced motion. */
export function useCountUp(target, { duration = 800, enabled = true } = {}) {
  const [value, setValue] = useState(0);
  const raf = useRef(null);

  useEffect(() => {
    const final = Number(target) || 0;
    const reduced = safeMatchMedia("(prefers-reduced-motion: reduce)").matches;
    if (!enabled || reduced || final === 0) {
      setValue(final);
      return undefined;
    }
    const t0 = performance.now();
    const tick = (now) => {
      const p = Math.min(1, (now - t0) / duration);
      const eased = 1 - Math.pow(1 - p, 3); // ease-out cubic
      setValue(Math.round(final * eased));
      if (p < 1) raf.current = requestAnimationFrame(tick);
    };
    raf.current = requestAnimationFrame(tick);
    return () => raf.current && cancelAnimationFrame(raf.current);
  }, [target, duration, enabled]);

  return value;
}
