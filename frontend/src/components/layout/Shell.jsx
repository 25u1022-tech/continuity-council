import React, { useEffect, useState } from "react";
import { NavLink, useLocation, useNavigate, Link } from "react-router-dom";
import { toast } from "sonner";
import { Button } from "../ui/button";
import { StatusBadge, Pill } from "../badges";
import {
  AlertDialog, AlertDialogAction, AlertDialogCancel, AlertDialogContent,
  AlertDialogDescription, AlertDialogFooter, AlertDialogHeader, AlertDialogTitle,
} from "../ui/alert-dialog";
import {
  DropdownMenu, DropdownMenuTrigger, DropdownMenuContent, DropdownMenuItem,
  DropdownMenuLabel, DropdownMenuSeparator,
} from "../ui/dropdown-menu";
import { getHealth, resetDemo } from "../../lib/api";
import { ActivityTicker } from "../ActivityTicker";
import { useProduction } from "../../context/ProductionContext";
import { useTheme } from "../../context/ThemeContext";
import { CreateProductionWizard } from "../CreateProductionWizard";
import {
  Clapperboard,
  LayoutDashboard,
  Siren,
  Radar,
  GitCompareArrows,
  ScrollText,
  UserRound,
  RotateCcw,
  ChevronsUpDown,
  Check,
  Plus,
  BookOpen,
  Settings,
  Sun,
  Moon,
} from "lucide-react";

const NAV = [
  { to: "/", label: "Production dashboard", icon: LayoutDashboard, id: "production-dashboard", end: true },
  { to: "/report", label: "Report disruption", icon: Siren, id: "report-disruption" },
  { to: "/investigation", label: "Agent investigation", icon: Radar, id: "agent-investigation" },
  { to: "/options", label: "Recovery options", icon: GitCompareArrows, id: "recovery-options" },
  { to: "/ledger", label: "Decision ledger", icon: ScrollText, id: "decision-ledger" },
  { to: "/methodology", label: "Data & methodology", icon: BookOpen, id: "data-methodology" },
  { to: "/settings", label: "Settings", icon: Settings, id: "settings" },
];

export const Shell = ({ children, activeCase }) => {
  const navigate = useNavigate();
  const location = useLocation();
  const { theme, toggleTheme } = useTheme();
  const { productions, selectedId, selected, select, refresh } = useProduction();
  const [health, setHealth] = useState(null);
  const [confirmReset, setConfirmReset] = useState(false);
  const [resetting, setResetting] = useState(false);
  const [wizardOpen, setWizardOpen] = useState(false);

  useEffect(() => {
    let alive = true;
    const load = () => getHealth().then((h) => alive && setHealth(h)).catch(() => {});
    load();
    const t = setInterval(load, 15000);
    return () => {
      alive = false;
      clearInterval(t);
    };
  }, [location.pathname]);

  const chConnected = health?.clickhouse?.connected;

  const doReset = async () => {
    setResetting(true);
    try {
      await resetDemo(selectedId);
      localStorage.removeItem("cc_active_case");
      toast.success("Reset — baseline schedule restored");
      setTimeout(() => {
        window.location.href = "/";
      }, 700);
    } catch (e) {
      toast.error(e?.response?.data?.detail || "Reset failed");
      setResetting(false);
      setConfirmReset(false);
    }
  };

  const handleCreated = async (res) => {
    if (res?.production_id) select(res.production_id);
    await refresh();
    navigate("/");
  };

  return (
    <div className="flex min-h-screen cc-base text-[var(--cc-text-primary)]">
      {/* Sidebar — 240px macOS System Settings Minimalist aesthetic */}
      <aside className="sticky top-0 flex h-screen w-[240px] shrink-0 flex-col border-r border-[var(--cc-border)] bg-[var(--cc-surface-elevated)]">
        {/* Brand Header */}
        <div className="flex items-center gap-3 px-5 pb-4 pt-5">
          <div className="flex h-8 w-8 items-center justify-center rounded-[8px] bg-[var(--cc-surface-sunken)] border border-[var(--cc-border)] text-[var(--cc-text-primary)]">
            <Clapperboard size={16} strokeWidth={1.75} />
          </div>
          <div>
            <div className="font-display text-[14px] font-semibold tracking-tight text-[var(--cc-text-primary)]">
              Continuity Council
            </div>
            <div className="text-[11px] text-[var(--cc-text-tertiary)]">Production recovery</div>
          </div>
        </div>

        {/* Production switcher + create */}
        <div className="space-y-2 px-3 pb-3">
          <DropdownMenu>
            <DropdownMenuTrigger asChild>
              <button
                type="button"
                data-testid="production-switcher"
                className="cc-transition flex w-full items-center justify-between gap-2 rounded-[10px] border border-[var(--cc-border)] bg-[var(--cc-surface)] px-3 py-2 text-left shadow-sm hover:bg-[var(--cc-surface-hover)]"
              >
                <div className="min-w-0">
                  <div className="truncate text-[13px] font-medium text-[var(--cc-text-primary)]">
                    {selected?.title || "Select production"}
                  </div>
                  <div className="truncate text-[11px] text-[var(--cc-text-secondary)]">
                    {selected
                      ? `${selected.total_shoot_days}-day · ${selected.scene_count} scenes`
                      : "No production selected"}
                  </div>
                </div>
                <ChevronsUpDown size={14} strokeWidth={1.5} className="shrink-0 text-[var(--cc-text-tertiary)]" />
              </button>
            </DropdownMenuTrigger>
            <DropdownMenuContent
              align="start"
              data-testid="production-switcher-menu"
              className="w-[216px] border border-[var(--cc-border)] bg-[var(--cc-surface)] text-[var(--cc-text-primary)] shadow-lg rounded-[12px] p-1.5"
            >
              <DropdownMenuLabel className="px-2 py-1 text-[11px] font-medium uppercase tracking-wider text-[var(--cc-text-tertiary)]">
                Productions
              </DropdownMenuLabel>
              {productions.length === 0 && (
                <div className="px-2 py-4 text-center text-[12px] text-[var(--cc-text-secondary)]">
                  No productions yet
                </div>
              )}
              {productions.map((p) => (
                <DropdownMenuItem
                  key={p.production_id}
                  data-testid={`production-option-${p.production_id}`}
                  onClick={() => select(p.production_id)}
                  className="cursor-pointer gap-2 rounded-[8px] px-2.5 py-1.5 text-[13px] hover:bg-[var(--cc-surface-hover)] focus:bg-[var(--cc-surface-hover)]"
                >
                  <Check
                    size={13}
                    className={p.production_id === selectedId ? "text-[var(--cc-text-primary)]" : "opacity-0"}
                  />
                  <span className="flex-1 truncate">{p.title}</span>
                  <Pill tone="gray">{p.total_shoot_days}d</Pill>
                  {p.is_demo && <Pill tone="neutral">Demo</Pill>}
                </DropdownMenuItem>
              ))}
              <DropdownMenuSeparator className="my-1 bg-[var(--cc-border)]" />
              <DropdownMenuItem
                data-testid="create-production-menu-item"
                onClick={() => setWizardOpen(true)}
                className="cursor-pointer gap-2 rounded-[8px] px-2.5 py-1.5 text-[13px] font-medium text-[var(--cc-text-primary)] hover:bg-[var(--cc-surface-hover)] focus:bg-[var(--cc-surface-hover)]"
              >
                <Plus size={13} /> Create production
              </DropdownMenuItem>
            </DropdownMenuContent>
          </DropdownMenu>

          <Button
            type="button"
            data-testid="create-production-button"
            variant="outline"
            onClick={() => setWizardOpen(true)}
            className="h-9 w-full gap-1.5 rounded-[10px] text-[13px] font-medium"
          >
            <Plus size={14} strokeWidth={2} /> Create production
          </Button>
        </div>

        {/* Navigation links */}
        <nav className="flex-1 space-y-0.5 px-3 py-2">
          {NAV.map((item) => (
            <NavLink
              key={item.to}
              to={item.to}
              end={item.end}
              data-testid={`sidebar-nav-${item.id}`}
              className={({ isActive }) =>
                `cc-transition group flex items-center gap-3 rounded-[10px] px-3 py-2 text-[13px] ${
                  isActive
                    ? "bg-[var(--cc-surface-hover)] font-medium text-[var(--cc-text-primary)] shadow-sm border border-[var(--cc-border)]"
                    : "text-[var(--cc-text-secondary)] hover:bg-[var(--cc-surface-hover)] hover:text-[var(--cc-text-primary)]"
                }`
              }
            >
              <item.icon size={16} strokeWidth={1.75} className="shrink-0" />
              <span>{item.label}</span>
            </NavLink>
          ))}
        </nav>

        {/* Sidebar Footer with ClickHouse status, Theme Switcher & Reset */}
        <div className="space-y-3 border-t border-[var(--cc-border)] px-4 py-3.5 bg-[var(--cc-surface-sunken)]/40">
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-2">
              <span
                data-testid="clickhouse-connection-dot"
                className={`inline-block h-2 w-2 rounded-full ${
                  health === null ? "bg-[var(--cc-gray-dot)]" : chConnected ? "bg-[var(--cc-green-dot)]" : "bg-[var(--cc-red-dot)]"
                }`}
              />
              <span className="text-[11px] leading-4 text-[var(--cc-text-secondary)]">
                {health === null
                  ? "Checking ClickHouse"
                  : chConnected
                  ? `ClickHouse · ${(health.clickhouse.history_rows || 0).toLocaleString()} rows`
                  : "ClickHouse offline"}
              </span>
            </div>

            {/* Theme Toggle Button */}
            <button
              type="button"
              data-testid="theme-toggle-button"
              onClick={toggleTheme}
              title={`Switch to ${theme === "dark" ? "Light" : "Dark"} Mode`}
              className="cc-transition flex h-7 w-7 items-center justify-center rounded-[8px] border border-[var(--cc-border)] bg-[var(--cc-surface)] text-[var(--cc-text-secondary)] hover:text-[var(--cc-text-primary)] hover:bg-[var(--cc-surface-hover)]"
            >
              {theme === "dark" ? <Sun size={13} strokeWidth={1.75} /> : <Moon size={13} strokeWidth={1.75} />}
            </button>
          </div>

          <div className="flex items-center justify-between pt-0.5">
            <button
              type="button"
              data-testid="reset-demo-button"
              onClick={() => setConfirmReset(true)}
              className="cc-transition flex items-center gap-1.5 text-[11px] text-[var(--cc-text-secondary)] hover:text-[var(--cc-text-primary)]"
            >
              <RotateCcw size={11} strokeWidth={1.75} />
              Reset demo
            </button>
            <span className="text-[10px] text-[var(--cc-text-quaternary)]">v0.1.0</span>
          </div>
        </div>
      </aside>

      {/* Main Content Area */}
      <div className="flex min-w-0 flex-1 flex-col">
        <header className="sticky top-0 z-20 flex h-14 items-center justify-between border-b border-[var(--cc-border)] bg-[var(--cc-canvas)]/85 px-6 backdrop-blur">
          <div className="flex items-center gap-3">
            <span className="text-[13px] text-[var(--cc-text-secondary)]" data-testid="header-production-label">
              {selected ? (
                <>
                  <span className="font-mono text-[12px]">{selected.production_id}</span> ·{" "}
                  <span className="font-medium text-[var(--cc-text-primary)]">{selected.title}</span>
                </>
              ) : (
                <span className="text-[var(--cc-text-tertiary)]">No production selected</span>
              )}
            </span>
            {activeCase && <StatusBadge status={activeCase.status} testId="header-case-status" />}
          </div>
          <div className="flex min-w-0 items-center gap-3">
            <ActivityTicker />
            <Button
              data-testid="header-report-disruption-button"
              size="sm"
              onClick={() => navigate("/report")}
              className="h-8 gap-1.5 rounded-[9px] bg-primary text-primary-foreground text-[13px] font-medium shadow-sm hover:opacity-90"
            >
              <Siren size={13} strokeWidth={1.75} />
              Report disruption
            </Button>
            <div className="flex items-center gap-2 rounded-full border border-[var(--cc-border)] bg-[var(--cc-surface)] py-1 pl-1.5 pr-3 shadow-sm">
              <div className="flex h-6 w-6 items-center justify-center rounded-full bg-[var(--cc-surface-hover)] text-[var(--cc-text-primary)]">
                <UserRound size={12} strokeWidth={1.75} />
              </div>
              <span className="text-xs font-medium text-[var(--cc-text-primary)]">Producer</span>
            </div>
          </div>
        </header>

        <main className="mx-auto flex w-full max-w-[1560px] flex-1 flex-col justify-between px-6 py-8">
          <div>{children}</div>
          <footer className="mt-16 border-t border-[var(--cc-border)] pt-6 pb-2 text-center text-[12px] text-[var(--cc-text-secondary)]">
            Live data: <span className="text-[var(--cc-text-primary)] font-medium">Open-Meteo</span> · <span className="text-[var(--cc-text-primary)] font-medium">OpenStreetMap</span> · <span className="text-[var(--cc-text-primary)] font-medium">World Bank (CC-BY 4.0)</span> · <span className="text-[var(--cc-text-primary)] font-medium">ECB</span> —{" "}
            <Link to="/methodology" data-testid="footer-methodology-link" className="text-[var(--cc-text-primary)] font-medium underline underline-offset-2 hover:opacity-80">
              methodology
            </Link>
          </footer>

        </main>
      </div>

      <AlertDialog open={confirmReset} onOpenChange={(v) => !resetting && setConfirmReset(v)}>
        <AlertDialogContent className="cc-card border border-[var(--cc-border)] p-6">
          <AlertDialogHeader>
            <AlertDialogTitle className="font-display text-[17px]">
              Reset {selected?.title || "this production"}?
            </AlertDialogTitle>
            <AlertDialogDescription className="text-[13px] leading-relaxed text-[var(--cc-text-secondary)]">
              {"Restores this production's baseline schedule and clears its cases, decisions and schedule changes. Other productions and historical data stay intact."}
            </AlertDialogDescription>
          </AlertDialogHeader>
          <AlertDialogFooter className="mt-4">
            <AlertDialogCancel
              data-testid="reset-cancel-button"
              className="rounded-[10px]"
            >
              Cancel
            </AlertDialogCancel>
            <AlertDialogAction
              data-testid="reset-confirm-button"
              disabled={resetting}
              onClick={(e) => {
                e.preventDefault();
                doReset();
              }}
              className="rounded-[10px] bg-primary text-primary-foreground font-medium"
            >
              {resetting ? "Resetting…" : "Reset demo"}
            </AlertDialogAction>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>

      <CreateProductionWizard
        open={wizardOpen}
        onOpenChange={setWizardOpen}
        onCreated={handleCreated}
      />
    </div>
  );
};
