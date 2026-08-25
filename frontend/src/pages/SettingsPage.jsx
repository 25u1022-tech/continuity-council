import React, { useState, useEffect } from "react";
import { toast } from "sonner";
import { useTheme } from "../context/ThemeContext";
import { getHealth, getCountryFactor } from "../lib/api";
import { Pill } from "../components/badges";
import { safeStorage } from "../lib/storage";
import {
  Settings,
  Sun,
  Moon,
  Compass,
  DollarSign,
  Sliders,
  Database,
  Globe,
  Check,
  RefreshCw,
  Layers,
  Cpu,
  ShieldCheck,
  Zap,
  Volume2,
} from "lucide-react";

export default function SettingsPage() {
  const { theme, toggleTheme } = useTheme();
  const [health, setHealth] = useState(null);
  const [loading, setLoading] = useState(false);

  // User Settings State (Persisted in localStorage safely)
  const [units, setUnits] = useState(() => safeStorage.getItem("cc_units", "miles"));
  const [baseCurrency, setBaseCurrency] = useState(
    () => safeStorage.getItem("cc_base_currency", "USD")
  );
  const [density, setDensity] = useState(() => safeStorage.getItem("cc_density", "default"));
  const [bottomUpWeight, setBottomUpWeight] = useState(
    () => Number(safeStorage.getItem("cc_bottom_up_weight", "70")) || 70
  );
  const [tier1Mult, setTier1Mult] = useState(
    () => Number(safeStorage.getItem("cc_tier_1_mult", "1.0")) || 1.0
  );
  const [tier2Mult, setTier2Mult] = useState(
    () => Number(safeStorage.getItem("cc_tier_2_mult", "0.5")) || 0.5
  );
  const [tier3Mult, setTier3Mult] = useState(
    () => Number(safeStorage.getItem("cc_tier_3_mult", "0.35")) || 0.35
  );
  const [ttsEnabled, setTtsEnabled] = useState(
    () => safeStorage.getItem("cc_tts_enabled", "true") === "true"
  );

  useEffect(() => {
    getHealth().then(setHealth).catch(() => {});
  }, []);

  const saveSetting = (key, val, setter) => {
    setter(val);
    safeStorage.setItem(key, String(val));
    toast.success("Settings updated");
  };

  const resetDefaults = () => {
    saveSetting("cc_units", "miles", setUnits);
    saveSetting("cc_base_currency", "USD", setBaseCurrency);
    saveSetting("cc_density", "default", setDensity);
    saveSetting("cc_bottom_up_weight", 70, setBottomUpWeight);
    saveSetting("cc_tier_1_mult", 1.0, setTier1Mult);
    saveSetting("cc_tier_2_mult", 0.5, setTier2Mult);
    saveSetting("cc_tier_3_mult", 0.35, setTier3Mult);
    toast.success("Settings restored to defaults");
  };

  const chConnected = health?.clickhouse?.connected;

  return (
    <div className="cc-fade-up space-y-8 max-w-5xl" data-testid="settings-page">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <div className="text-[12px] font-semibold uppercase tracking-wider text-[var(--cc-text-tertiary)]">
            Preferences & Configuration
          </div>
          <h1 className="font-display mt-1 text-[30px] font-semibold leading-tight tracking-tight text-[var(--cc-text-primary)]">
            System Settings
          </h1>
          <p className="mt-1 max-w-2xl text-[14px] text-[var(--cc-text-secondary)]">
            Configure appearance, measurement units, macroeconomic costing formulas, ClickHouse cache TTLs, and live open data integrations.
          </p>
        </div>
        <button
          type="button"
          data-testid="reset-settings-defaults-btn"
          onClick={resetDefaults}
          className="flex items-center gap-1.5 rounded-[9px] border border-[var(--cc-border)] bg-[var(--cc-surface)] px-3 py-1.5 text-[12px] font-medium text-[var(--cc-text-secondary)] hover:text-[var(--cc-text-primary)] hover:bg-[var(--cc-surface-hover)] cc-transition shadow-sm"
        >
          <RefreshCw size={12} />
          Reset to Defaults
        </button>
      </div>

      {/* Section 1: Appearance */}
      <div className="cc-card p-6 md:p-7 space-y-5" data-testid="settings-section-appearance">
        <div className="flex items-center gap-3 border-b border-[var(--cc-border)] pb-4">
          <div className="flex h-9 w-9 items-center justify-center rounded-[9px] border border-[var(--cc-border)] bg-[var(--cc-surface-hover)] text-[var(--cc-text-primary)]">
            {theme === "dark" ? <Moon size={16} /> : <Sun size={16} />}
          </div>
          <div>
            <h2 className="text-[16px] font-semibold text-[var(--cc-text-primary)]">Appearance & Theme</h2>
            <p className="text-[12px] text-[var(--cc-text-secondary)]">
              Customize interface color palette and layout density.
            </p>
          </div>
        </div>

        <div className="grid grid-cols-1 md:grid-cols-2 gap-6 pt-1">
          {/* Theme Selector */}
          <div className="space-y-2">
            <label className="text-[13px] font-medium text-[var(--cc-text-primary)]">Theme Mode</label>
            <div className="flex gap-2">
              <button
                type="button"
                data-testid="settings-theme-light"
                onClick={() => theme !== "light" && toggleTheme()}
                className={`flex-1 flex items-center justify-center gap-2 rounded-[10px] border p-2.5 text-[13px] font-medium cc-transition ${
                  theme === "light"
                    ? "border-[var(--cc-text-primary)] bg-[var(--cc-text-primary)] text-[var(--cc-canvas)] shadow-sm"
                    : "border-[var(--cc-border)] bg-[var(--cc-surface-sunken)] text-[var(--cc-text-secondary)] hover:text-[var(--cc-text-primary)]"
                }`}
              >
                <Sun size={14} /> Light
              </button>
              <button
                type="button"
                data-testid="settings-theme-dark"
                onClick={() => theme !== "dark" && toggleTheme()}
                className={`flex-1 flex items-center justify-center gap-2 rounded-[10px] border p-2.5 text-[13px] font-medium cc-transition ${
                  theme === "dark"
                    ? "border-[var(--cc-text-primary)] bg-[var(--cc-text-primary)] text-[var(--cc-canvas)] shadow-sm"
                    : "border-[var(--cc-border)] bg-[var(--cc-surface-sunken)] text-[var(--cc-text-secondary)] hover:text-[var(--cc-text-primary)]"
                }`}
              >
                <Moon size={14} /> Dark
              </button>
            </div>
          </div>

          {/* Density Selector */}
          <div className="space-y-2">
            <label className="text-[13px] font-medium text-[var(--cc-text-primary)]">Layout Density</label>
            <div className="flex gap-2">
              {["default", "compact"].map((d) => (
                <button
                  key={d}
                  type="button"
                  data-testid={`settings-density-${d}`}
                  onClick={() => saveSetting("cc_density", d, setDensity)}
                  className={`flex-1 flex items-center justify-center gap-1.5 rounded-[10px] border p-2.5 text-[13px] capitalize font-medium cc-transition ${
                    density === d
                      ? "border-[var(--cc-text-primary)] bg-[var(--cc-surface-hover)] text-[var(--cc-text-primary)] shadow-sm font-semibold"
                      : "border-[var(--cc-border)] bg-[var(--cc-surface-sunken)] text-[var(--cc-text-secondary)] hover:text-[var(--cc-text-primary)]"
                  }`}
                >
                  {d}
                </button>
              ))}
            </div>
          </div>

          {/* TTS Toggle */}
          <div className="space-y-2">
            <label className="text-[13px] font-medium text-[var(--cc-text-primary)]">Text-to-Speech</label>
            <div className="flex gap-2">
              <button
                type="button"
                data-testid="settings-tts-toggle"
                onClick={() => {
                  const next = !ttsEnabled;
                  setTtsEnabled(next);
                  safeStorage.setItem("cc_tts_enabled", String(next));
                  toast.success(next ? "Text-to-speech enabled" : "Text-to-speech disabled");
                }}
                className={`flex-1 flex items-center justify-center gap-1.5 rounded-[10px] border p-2.5 text-[13px] font-medium cc-transition ${
                  ttsEnabled
                    ? "border-[var(--cc-text-primary)] bg-[var(--cc-surface-hover)] text-[var(--cc-text-primary)] shadow-sm font-semibold"
                    : "border-[var(--cc-border)] bg-[var(--cc-surface-sunken)] text-[var(--cc-text-secondary)] hover:text-[var(--cc-text-primary)]"
                }`}
              >
                <Volume2 size={14} />
                {ttsEnabled ? "Enabled" : "Disabled"}
              </button>
            </div>
            <p className="text-[11px] text-[var(--cc-text-tertiary)]">
              Gemini TTS voice for chatbot responses (accessibility)
            </p>
          </div>
        </div>
      </div>

      {/* Section 2: Units & Geographics */}
      <div className="cc-card p-6 md:p-7 space-y-5" data-testid="settings-section-units">
        <div className="flex items-center gap-3 border-b border-[var(--cc-border)] pb-4">
          <div className="flex h-9 w-9 items-center justify-center rounded-[9px] border border-[var(--cc-border)] bg-[var(--cc-surface-hover)] text-[var(--cc-text-primary)]">
            <Compass size={16} />
          </div>
          <div>
            <h2 className="text-[16px] font-semibold text-[var(--cc-text-primary)]">Units & Geographics</h2>
            <p className="text-[12px] text-[var(--cc-text-secondary)]">
              Configure distance measurement units and default reporting currency.
            </p>
          </div>
        </div>

        <div className="grid grid-cols-1 md:grid-cols-2 gap-6 pt-1">
          {/* Distance Units */}
          <div className="space-y-2">
            <label className="text-[13px] font-medium text-[var(--cc-text-primary)]">Distance Units</label>
            <div className="flex gap-2">
              {[
                { id: "miles", label: "Statute Miles (mi)" },
                { id: "km", label: "Kilometers (km)" },
              ].map((u) => (
                <button
                  key={u.id}
                  type="button"
                  data-testid={`settings-units-${u.id}`}
                  onClick={() => saveSetting("cc_units", u.id, setUnits)}
                  className={`flex-1 flex items-center justify-center gap-1.5 rounded-[10px] border p-2.5 text-[13px] font-medium cc-transition ${
                    units === u.id
                      ? "border-[var(--cc-text-primary)] bg-[var(--cc-surface-hover)] text-[var(--cc-text-primary)] shadow-sm font-semibold"
                      : "border-[var(--cc-border)] bg-[var(--cc-surface-sunken)] text-[var(--cc-text-secondary)] hover:text-[var(--cc-text-primary)]"
                  }`}
                >
                  {u.label}
                </button>
              ))}
            </div>
          </div>

          {/* Base Accounting Currency */}
          <div className="space-y-2">
            <label className="text-[13px] font-medium text-[var(--cc-text-primary)]">Base Accounting Currency</label>
            <select
              data-testid="settings-currency-select"
              value={baseCurrency}
              onChange={(e) => saveSetting("cc_base_currency", e.target.value, setBaseCurrency)}
              className="w-full h-10 rounded-[10px] border border-[var(--cc-border)] bg-[var(--cc-surface-hover)] px-3 text-[13px] text-[var(--cc-text-primary)] focus:outline-none focus:border-[var(--cc-text-primary)] font-mono"
            >
              <option value="USD">USD ($) — United States Dollar</option>
              <option value="EUR">EUR (€) — Euro</option>
              <option value="GBP">GBP (£) — British Pound</option>
              <option value="INR">INR (₹) — Indian Rupee</option>
              <option value="CAD">CAD (C$) — Canadian Dollar</option>
              <option value="AUD">AUD (A$) — Australian Dollar</option>
              <option value="BRL">BRL (R$) — Brazilian Real</option>
              <option value="JPY">JPY (¥) — Japanese Yen</option>
              <option value="AED">AED (د.إ) — UAE Dirham</option>
            </select>
          </div>
        </div>
      </div>

      {/* Section 3: Cost Model & Macroeconomic Calibration */}
      <div className="cc-card p-6 md:p-7 space-y-5" data-testid="settings-section-cost-model">
        <div className="flex items-center gap-3 border-b border-[var(--cc-border)] pb-4">
          <div className="flex h-9 w-9 items-center justify-center rounded-[9px] border border-[var(--cc-border)] bg-[var(--cc-surface-hover)] text-[var(--cc-text-primary)]">
            <Sliders size={16} />
          </div>
          <div>
            <h2 className="text-[16px] font-semibold text-[var(--cc-text-primary)]">Cost Model & Geo Multipliers</h2>
            <p className="text-[12px] text-[var(--cc-text-secondary)]">
              Fine-tune the 70/30 empirical calibration blend and city tier multipliers.
            </p>
          </div>
        </div>

        {/* 70/30 Slider */}
        <div className="space-y-3 pt-1">
          <div className="flex items-center justify-between text-[13px]">
            <span className="font-medium text-[var(--cc-text-primary)]">Calibration Weight Ratio</span>
            <span className="font-mono font-semibold text-[var(--cc-text-primary)]">
              {bottomUpWeight}% Rate Card / {100 - bottomUpWeight}% ClickHouse MV
            </span>
          </div>
          <input
            type="range"
            min="30"
            max="90"
            step="5"
            value={bottomUpWeight}
            data-testid="settings-weight-slider"
            onChange={(e) => saveSetting("cc_bottom_up_weight", Number(e.target.value), setBottomUpWeight)}
            className="w-full h-2 rounded-lg bg-[var(--cc-surface-sunken)] appearance-none cursor-pointer accent-[var(--cc-text-primary)]"
          />
          <div className="flex justify-between text-[11px] text-[var(--cc-text-tertiary)]">
            <span>More Historical Weight</span>
            <span>Balanced Benchmark (70/30)</span>
            <span>More Itemized Rate Card</span>
          </div>
        </div>

        {/* Tier Multipliers Grid */}
        <div className="pt-2">
          <div className="text-[13px] font-medium text-[var(--cc-text-primary)] mb-2.5">
            City Tier Multipliers (OSM Demographics)
          </div>
          <div className="grid grid-cols-1 sm:grid-cols-3 gap-3">
            <div className="rounded-[10px] border border-[var(--cc-border)] bg-[var(--cc-surface-sunken)] p-3 space-y-1.5">
              <div className="text-[12px] font-medium text-[var(--cc-text-primary)]">Tier 1 (Metro / ≥5M)</div>
              <div className="text-[11px] text-[var(--cc-text-secondary)]">Multiplier: <span className="font-mono font-semibold text-[var(--cc-text-primary)]">{tier1Mult}x</span></div>
              <div className="text-[10px] text-[var(--cc-text-tertiary)]">Full baseline production scale</div>
            </div>

            <div className="rounded-[10px] border border-[var(--cc-border)] bg-[var(--cc-surface-sunken)] p-3 space-y-1.5">
              <div className="text-[12px] font-medium text-[var(--cc-text-primary)]">Tier 2 (Regional / 200k–1M)</div>
              <div className="text-[11px] text-[var(--cc-text-secondary)]">Multiplier: <span className="font-mono font-semibold text-[var(--cc-text-primary)]">{tier2Mult}x</span></div>
              <div className="text-[10px] text-[var(--cc-text-tertiary)]">Secondary regional hubs</div>
            </div>

            <div className="rounded-[10px] border border-[var(--cc-border)] bg-[var(--cc-surface-sunken)] p-3 space-y-1.5">
              <div className="text-[12px] font-medium text-[var(--cc-text-primary)]">Tier 3 (Small / &lt;200k)</div>
              <div className="text-[11px] text-[var(--cc-text-secondary)]">Multiplier: <span className="font-mono font-semibold text-[var(--cc-text-primary)]">{tier3Mult}x</span></div>
              <div className="text-[10px] text-[var(--cc-text-tertiary)]">Outposts & rural terrains</div>
            </div>
          </div>
        </div>
      </div>

      {/* Section 4: Data & ClickHouse Cloud */}
      <div className="cc-card p-6 md:p-7 space-y-5" data-testid="settings-section-data">
        <div className="flex items-center gap-3 border-b border-[var(--cc-border)] pb-4">
          <div className="flex h-9 w-9 items-center justify-center rounded-[9px] border border-[var(--cc-border)] bg-[var(--cc-surface-hover)] text-[var(--cc-text-primary)]">
            <Database size={16} />
          </div>
          <div>
            <h2 className="text-[16px] font-semibold text-[var(--cc-text-primary)]">ClickHouse Storage & Caching</h2>
            <p className="text-[12px] text-[var(--cc-text-secondary)]">
              Database connection status, schema versioning, and cache retention policies.
            </p>
          </div>
        </div>

        <div className="grid grid-cols-1 sm:grid-cols-2 md:grid-cols-4 gap-3 pt-1">
          <div className="rounded-[10px] border border-[var(--cc-border)] bg-[var(--cc-surface-sunken)] p-3.5 space-y-1">
            <div className="text-[11px] text-[var(--cc-text-tertiary)]">Connection Status</div>
            <div className="flex items-center gap-1.5 font-medium text-[13px] text-[var(--cc-text-primary)]">
              <span className={`h-2 w-2 rounded-full ${chConnected ? "bg-[var(--cc-green-dot)]" : "bg-[var(--cc-red-dot)]"}`} />
              <span>{chConnected ? "Connected" : "Offline"}</span>
            </div>
          </div>

          <div className="rounded-[10px] border border-[var(--cc-border)] bg-[var(--cc-surface-sunken)] p-3.5 space-y-1">
            <div className="text-[11px] text-[var(--cc-text-tertiary)]">Historical Cases</div>
            <div className="font-mono text-[14px] font-semibold text-[var(--cc-text-primary)]">
              {(health?.clickhouse?.history_rows || 0).toLocaleString()}
            </div>
          </div>

          <div className="rounded-[10px] border border-[var(--cc-border)] bg-[var(--cc-surface-sunken)] p-3.5 space-y-1">
            <div className="text-[11px] text-[var(--cc-text-tertiary)]">Geo Index Cache</div>
            <div className="font-mono text-[13px] text-[var(--cc-text-secondary)]">30-day TTL</div>
          </div>

          <div className="rounded-[10px] border border-[var(--cc-border)] bg-[var(--cc-surface-sunken)] p-3.5 space-y-1">
            <div className="text-[11px] text-[var(--cc-text-tertiary)]">Tenant Cold-Start</div>
            <div className="font-mono text-[13px] text-[var(--cc-text-secondary)]">200 Cases</div>
          </div>
        </div>
      </div>

      {/* Section 5: Integrations & Attributions */}
      <div className="cc-card p-6 md:p-7 space-y-5" data-testid="settings-section-integrations">
        <div className="flex items-center gap-3 border-b border-[var(--cc-border)] pb-4">
          <div className="flex h-9 w-9 items-center justify-center rounded-[9px] border border-[var(--cc-border)] bg-[var(--cc-surface-hover)] text-[var(--cc-text-primary)]">
            <Globe size={16} />
          </div>
          <div>
            <h2 className="text-[16px] font-semibold text-[var(--cc-text-primary)]">Open Data Integrations & Attributions</h2>
            <p className="text-[12px] text-[var(--cc-text-secondary)]">
              Keyless open data feeds queried with deterministic fallbacks.
            </p>
          </div>
        </div>

        <div className="space-y-2.5 pt-1 text-[13px]">
          {[
            { name: "World Bank API (NY.GDP.PCAP.PP.CD)", status: "Active", attr: "World Bank open data (CC-BY 4.0)" },
            { name: "OpenStreetMap & Nominatim", status: "Active", attr: "© OpenStreetMap contributors (ODbL)" },
            { name: "Open-Meteo Weather Risk Engine", status: "Active", attr: "Weather data by Open-Meteo (CC-BY 4.0)" },
            { name: "Frankfurter / ECB FX Spot Rates", status: "Active", attr: "European Central Bank reference rates" },
            { name: "Official mcp-clickhouse Server", status: "Active", attr: "Model Context Protocol stdio transport" },
          ].map((item, i) => (
            <div
              key={i}
              className="flex items-center justify-between rounded-[9px] border border-[var(--cc-border)] bg-[var(--cc-surface-sunken)] px-3.5 py-2.5"
            >
              <div className="space-y-0.5">
                <div className="font-medium text-[var(--cc-text-primary)]">{item.name}</div>
                <div className="text-[11px] text-[var(--cc-text-tertiary)]">{item.attr}</div>
              </div>
              <Pill tone="green">{item.status}</Pill>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}
