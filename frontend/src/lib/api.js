const BACKEND_URL = process.env.REACT_APP_BACKEND_URL || "";
export const API = `${BACKEND_URL}/api`;

const COLD_START_EVENT = "cc:cold-start";
let firstRequest = true;
let coldStartDetected = false;

const announceColdStart = () => {
  coldStartDetected = true;
  if (typeof window !== "undefined") {
    window.dispatchEvent(new Event(COLD_START_EVENT));
  }
};

export const hasColdStart = () => coldStartDetected;

export const PRODUCTION_ID = "prod_001";

// Native fetch wrapper (axios-compatible error shape: err.response.data.detail)
const requestOnce = async (path, { method = "GET", body } = {}, timeoutMs = 0) => {
  const controller = timeoutMs ? new AbortController() : null;
  const timer = timeoutMs ? setTimeout(() => controller.abort(), timeoutMs) : null;
  let res;
  try {
    res = await fetch(`${API}${path}`, {
    method,
    headers: body ? { "Content-Type": "application/json" } : undefined,
    body: body ? JSON.stringify(body) : undefined,
      signal: controller?.signal,
    });
  } finally {
    if (timer) clearTimeout(timer);
  }
  let data = null;
  try {
    data = await res.json();
  } catch {
    data = null;
  }
  if (!res.ok) {
    const err = new Error((data && data.detail) || `HTTP ${res.status}`);
    err.response = { status: res.status, data };
    throw err;
  }
  return data;
};

const request = async (path, options = {}) => {
  const isFirstRequest = firstRequest;
  firstRequest = false;
  try {
    return await requestOnce(path, options, isFirstRequest ? 4000 : 0);
  } catch (error) {
    if (!isFirstRequest) throw error;
    announceColdStart();
    return requestOnce(path, options);
  }
};

export const onColdStart = (listener) => {
  if (typeof window === "undefined") return () => {};
  window.addEventListener(COLD_START_EVENT, listener);
  return () => window.removeEventListener(COLD_START_EVENT, listener);
};

export const getHealth = () => request("/health");
export const getProduction = (pid = PRODUCTION_ID) => request(`/productions/${pid}`);
export const getImpactPreview = (params) => {
  const qs = new URLSearchParams(params);
  return request(`/disruptions/impact-preview?${qs.toString()}`);
};
export const reportDisruption = (payload) =>
  request("/disruptions", { method: "POST", body: payload });
export const getCase = (caseId) => request(`/cases/${caseId}`);
export const approveOption = (caseId, optionId, approvedBy = "producer") =>
  request(`/cases/${caseId}/approve`, {
    method: "POST",
    body: { option_id: optionId, approved_by: approvedBy },
  });
export const getAudit = (pid = PRODUCTION_ID) => request(`/audit/${pid}`);
export const getActivity = (limit = 1) => request(`/activity?limit=${limit}`);
export const getEvidenceDrilldown = (disruptionType, strategy, severity, limit = 40) => {
  const qs = new URLSearchParams({ disruption_type: disruptionType, strategy, limit: String(limit) });
  if (severity) qs.set("severity", severity);
  return request(`/evidence/drilldown?${qs.toString()}`);
};
export const resetDemo = (productionId) =>
  request(
    `/demo/reset${productionId ? `?production_id=${encodeURIComponent(productionId)}` : ""}`,
    { method: "POST" }
  );

export const sendChatMessage = ({ message, production_id, case_id }) =>
  request("/chat", {
    method: "POST",
    body: { message, production_id, case_id: case_id || undefined },
  });

// --- Production onboarding ---------------------------------------------------
export const listProductions = () => request("/productions");
export const createProduction = (payload) =>
  request("/productions", { method: "POST", body: payload });
export const importHistoryCsv = async (productionId, file) => {
  const formData = new FormData();
  formData.append("file", file);
  const res = await fetch(`${API}/productions/${encodeURIComponent(productionId)}/import-history`, {
    method: "POST",
    body: formData,
  });
  const data = await res.json();
  if (!res.ok) {
    const err = new Error((data && data.detail) || `HTTP ${res.status}`);
    err.response = { status: res.status, data };
    throw err;
  }
  return data;
};
export const getStudioCohort = (productionId) =>
  request(`/productions/${encodeURIComponent(productionId)}/studio-cohort`);

export const resolveGeoEconomics = (query, lat, lon) => {
  const qs = new URLSearchParams({ query });
  if (lat !== undefined && lat !== null) qs.set("lat", String(lat));
  if (lon !== undefined && lon !== null) qs.set("lon", String(lon));
  return request(`/geo/resolve?${qs.toString()}`);
};

export const getCountryFactor = (countryCode) =>
  request(`/geo/country-factor?country_code=${encodeURIComponent(countryCode)}`);

export const CAST_CSV_TEMPLATE =
  "name,role,available_days\n" +
  "Aria Blackwood,lead,all\n" +
  "Marcus Reed,supporting,1 2\n" +
  "Nina Cole,supporting,2 3\n";

export const LOCATION_CSV_TEMPLATE =
  "name,type,permit_notes,available_days\n" +
  "Rooftop Bar,exterior,Permit covers Day 1-2 only,1 2\n" +
  "Subway Platform,interior,,all\n" +
  "Warehouse Loft,stage,,all\n";

export const downloadCsv = (filename, content) => {
  const blob = new Blob([content], { type: "text/csv;charset=utf-8" });
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = filename;
  document.body.appendChild(a);
  a.click();
  document.body.removeChild(a);
  URL.revokeObjectURL(url);
};

// Minimal CSV parser (handles quoted fields with embedded commas).
export const parseCsv = (text) => {
  const lines = String(text || "")
    .replace(/\r\n/g, "\n")
    .replace(/\r/g, "\n")
    .split("\n")
    .filter((l) => l.trim() !== "");
  if (lines.length === 0) return { headers: [], rows: [] };
  const parseLine = (line) => {
    const out = [];
    let cur = "";
    let inQ = false;
    for (let i = 0; i < line.length; i++) {
      const ch = line[i];
      if (inQ) {
        if (ch === '"') {
          if (line[i + 1] === '"') {
            cur += '"';
            i++;
          } else {
            inQ = false;
          }
        } else {
          cur += ch;
        }
      } else if (ch === '"') {
        inQ = true;
      } else if (ch === ",") {
        out.push(cur);
        cur = "";
      } else {
        cur += ch;
      }
    }
    out.push(cur);
    return out.map((c) => c.trim());
  };
  const headers = parseLine(lines[0]).map((h) => h.toLowerCase());
  const rows = lines.slice(1).map((line) => {
    const cells = parseLine(line);
    const obj = {};
    headers.forEach((h, i) => {
      obj[h] = cells[i] !== undefined ? cells[i] : "";
    });
    return obj;
  });
  return { headers, rows };
};

// Convert an available_days cell ("all" | "1 2 3" | "1;2") to an int[] within range.
export const parseDays = (raw, totalDays) => {
  const s = String(raw || "").trim().toLowerCase();
  const allDays = Array.from({ length: totalDays }, (_, i) => i + 1);
  if (!s || s === "all") return allDays;
  const nums = (s.match(/\d+/g) || []).map(Number).filter((n) => n >= 1 && n <= totalDays);
  return Array.from(new Set(nums)).sort((a, b) => a - b);
};

export const DISRUPTION_TYPES = [
  { value: "lead_actor_unavailable", label: "Lead actor unavailable" },
  { value: "supporting_actor_unavailable", label: "Supporting actor unavailable" },
  { value: "location_unavailable", label: "Location unavailable" },
  { value: "equipment_failure", label: "Equipment failure" },
  { value: "weather_delay", label: "Weather delay" },
  { value: "permit_issue", label: "Permit issue" },
];

export const fmtMoney = (n) =>
  n === null || n === undefined
    ? "—"
    : `$${Math.round(Number(n)).toLocaleString("en-US")}`;

export const fmtHours = (n) =>
  n === null || n === undefined ? "—" : `${Number(n).toFixed(1)}h`;

export const riskLabel = (score) => {
  if (score === null || score === undefined) return "—";
  if (score < 0.2) return "Low";
  if (score < 0.45) return "Medium";
  return "High";
};

export const sentenceCase = (s) => {
  if (!s) return "";
  const t = String(s).replace(/_/g, " ");
  return t.charAt(0).toUpperCase() + t.slice(1);
};

export const timeAgo = (iso) => {
  if (!iso) return "";
  const s = Math.max(0, (Date.now() - new Date(iso).getTime()) / 1000);
  if (s < 60) return `${Math.floor(s)}s ago`;
  if (s < 3600) return `${Math.floor(s / 60)}m ago`;
  return `${Math.floor(s / 3600)}h ago`;
};
