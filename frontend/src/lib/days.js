/**
 * Shared Shooting Day & Calendar Utility
 *
 * Converts between 1-based shooting day numbers and physical calendar dates,
 * providing globally consistent labels across the entire application.
 *
 * Guard: If a production has no valid start_date, gracefully falls back to "Day N".
 */

/**
 * Parse a YYYY-MM-DD string into a timezone-agnostic UTC timestamp (midnight).
 * Avoids browser timezone offset errors.
 */
function parseIsoUtc(isoDate) {
  if (!isoDate || typeof isoDate !== "string") return null;
  const parts = isoDate.split("T")[0].split("-");
  if (parts.length !== 3) return null;
  const [y, m, d] = parts.map(Number);
  if (isNaN(y) || isNaN(m) || isNaN(d)) return null;
  return new Date(Date.UTC(y, m - 1, d));
}

/**
 * Format a Date object to YYYY-MM-DD string in UTC.
 */
function toIsoDateString(date) {
  if (!date || !(date instanceof Date) || isNaN(date.getTime())) return null;
  const y = date.getUTCFullYear();
  const m = String(date.getUTCMonth() + 1).padStart(2, "0");
  const d = String(date.getUTCDate()).padStart(2, "0");
  return `${y}-${m}-${d}`;
}

/**
 * Convert shooting day number (1-based) to ISO date string (YYYY-MM-DD).
 * @param {object} production - Production object with start_date
 * @param {number} dayNumber - 1-based shoot day
 * @returns {string|null} ISO date string or null
 */
export function dayToDate(production, dayNumber) {
  if (!production?.start_date || !dayNumber || isNaN(dayNumber)) return null;
  const base = parseIsoUtc(production.start_date);
  if (!base) return null;
  const n = parseInt(dayNumber, 10);
  const target = new Date(base.getTime() + (n - 1) * 86400000);
  return toIsoDateString(target);
}

/**
 * Convert ISO date string (YYYY-MM-DD) to 1-based shooting day number.
 * @param {object} production - Production object with start_date
 * @param {string} isoDate - Date string
 * @returns {number|null} 1-based shoot day number or null
 */
export function dateToDay(production, isoDate) {
  if (!production?.start_date || !isoDate) return null;
  const base = parseIsoUtc(production.start_date);
  const target = parseIsoUtc(isoDate);
  if (!base || !target) return null;
  const diffDays = Math.round((target.getTime() - base.getTime()) / 86400000);
  return diffDays + 1;
}

/**
 * Return formatted day label, e.g. "Day 12 · Tue, Mar 3".
 * If production lacks start_date, falls back to "Day 12".
 * @param {object} production - Production object
 * @param {number} dayNumber - 1-based shoot day
 * @returns {string} Formatted label
 */
export function dayLabel(production, dayNumber) {
  if (dayNumber === undefined || dayNumber === null || isNaN(dayNumber)) {
    return "Day -";
  }
  const n = parseInt(dayNumber, 10);
  const iso = dayToDate(production, n);
  if (!iso) {
    return `Day ${n}`;
  }
  const dt = parseIsoUtc(iso);
  if (!dt) return `Day ${n}`;

  // Formatter: "Tue, Mar 3"
  const weekday = dt.toLocaleDateString("en-US", { weekday: "short", timeZone: "UTC" });
  const month = dt.toLocaleDateString("en-US", { month: "short", timeZone: "UTC" });
  const day = dt.getUTCDate();

  return `Day ${n} · ${weekday}, ${month} ${day}`;
}

/**
 * Return date boundaries for a production shoot.
 * @param {object} production
 * @returns {{ start: string|null, end: string|null }}
 */
export function getShootDateRange(production) {
  if (!production?.start_date) return { start: null, end: null };
  const start = production.start_date.split("T")[0];
  const totalDays = production.total_shoot_days || 1;
  const end = dayToDate(production, totalDays) || start;
  return { start, end };
}

/**
 * Format a bare ISO date string for display (e.g. "Aug 19, 2026").
 */
export function formatDateDisplay(isoDate) {
  const dt = parseIsoUtc(isoDate);
  if (!dt) return isoDate || "";
  return dt.toLocaleDateString("en-US", {
    month: "short",
    day: "numeric",
    year: "numeric",
    timeZone: "UTC",
  });
}
