import React from "react";
import { useNavigate, Link } from "react-router-dom";
import { Button } from "../components/ui/button";
import { useTheme } from "../context/ThemeContext";
import {
  Clapperboard,
  Radar,
  Database,
  CloudSun,
  Bot,
  ScrollText,
  ArrowRight,
  Sun,
  Moon,
  Sparkles,
  ArrowUpRight,
  FileText,
} from "lucide-react";

export default function LandingPage() {
  const navigate = useNavigate();
  const { theme, toggleTheme } = useTheme();

  const HIGHLIGHTS = [
    {
      icon: Radar,
      title: "Multi-Agent Council (Google ADK)",
      description:
        "Coordinated 6-agent pipeline featuring Orchestrator, Budget Sentinel, Compliance Sentinel, Continuity Memory, Schedule Optimizer, and Auditor agents working in sequence and parallel.",
      badge: "Google ADK",
    },
    {
      icon: Database,
      title: "Empirical Historical Grounding (ClickHouse)",
      description:
        "Candidate recovery options calibrated against 200,000+ historical disruption benchmarks and real union rate cards to minimize budget and delay risk.",
      badge: "ClickHouse Cloud",
    },
    {
      icon: CloudSun,
      title: "Live External Signals",
      description:
        "Real-time Open-Meteo weather forecasts, OpenStreetMap geographic intelligence with SAG-AFTRA transit validation, and European Central Bank currency conversion applied dynamically.",
      badge: "Live APIs",
    },
    {
      icon: Bot,
      title: "Interactive Production Chatbot & Voice",
      description:
        "Context-aware function-calling assistant powered by Google Gemini with on-demand voice audio briefings for executive recovery recommendations.",
      badge: "Gemini 3.6",
    },
    {
      icon: ScrollText,
      title: "Audited Decision Ledger",
      description:
        "An immutable, append-only ClickHouse ledger capturing approved recovery decisions, full evidence snapshots, and individual scene schedule changes.",
      badge: "Append-Only",
    },
    {
      icon: FileText,
      title: "AI Production Intake",
      description:
        "AI-powered PDF schedule parsing extracts scenes, shoot days, cast, and locations, while natural-language disruption intake resolves affected resources and production constraints.",
      badge: "Multimodal AI",
    },
  ];

  const WORKFLOW_STEPS = [
    {
      step: "01",
      title: "Incident Intake",
      description:
        "File disruptions via structured forms or natural language intake. The system extracts affected shoot days, cast members, and locations.",
    },
    {
      step: "02",
      title: "Agent Investigation",
      description:
        "The ADK council executes constraint validation, ClickHouse historical queries, and multi-factor scoring across delay, budget, and compliance.",
    },
    {
      step: "03",
      title: "Grounded Recovery",
      description:
        "Review ranked recovery strategies with empirical cost breakdowns, approve the optimal plan, and commit changes to the decision ledger.",
    },
  ];

  return (
    <div className="min-h-screen cc-base text-[var(--cc-text-primary)] flex flex-col justify-between" data-testid="landing-page">
      {/* Top Navigation Bar */}
      <header className="sticky top-0 z-50 border-b border-[var(--cc-border)] bg-[var(--cc-surface)]/85 backdrop-blur-md px-6 py-3.5">
        <div className="mx-auto flex max-w-[1240px] items-center justify-between">
          <div className="flex items-center gap-3">
            <div className="flex h-9 w-9 items-center justify-center rounded-[10px] bg-[var(--cc-surface-sunken)] border border-[var(--cc-border)] text-[var(--cc-text-primary)] shadow-sm">
              <Clapperboard size={18} strokeWidth={1.75} />
            </div>
            <div>
              <div className="font-display text-[15px] font-semibold tracking-tight text-[var(--cc-text-primary)]">
                Continuity Council
              </div>
              <div className="text-[11px] text-[var(--cc-text-tertiary)]">Production recovery system</div>
            </div>
          </div>

          <div className="flex items-center gap-2.5">
            <Button
              variant="ghost"
              size="icon"
              onClick={toggleTheme}
              className="h-9 w-9 rounded-[8px] text-[var(--cc-text-secondary)] hover:text-[var(--cc-text-primary)]"
              aria-label={`Switch to ${theme === "dark" ? "light" : "dark"} mode`}
            >
              {theme === "dark" ? <Sun size={16} /> : <Moon size={16} />}
            </Button>

            <Button
              onClick={() => navigate("/dashboard")}
              data-testid="header-launch-button"
              className="h-9 rounded-[10px] px-4 text-[13px] font-medium"
            >
              Launch Studio
              <ArrowRight size={14} className="ml-1" />
            </Button>
          </div>
        </div>
      </header>

      {/* Main Content */}
      <main className="mx-auto w-full max-w-[1240px] flex-1 px-6 py-12 md:py-16">
        {/* Hero Section */}
        <section className="text-center max-w-3xl mx-auto space-y-6">
          <div className="inline-flex items-center gap-2 rounded-[8px] border border-[var(--cc-border)] bg-[var(--cc-surface-hover)] px-3 py-1 text-[12px] font-medium text-[var(--cc-text-secondary)] shadow-sm">
            <Sparkles size={13} className="text-[var(--cc-text-primary)]" />
            <span>Autonomous Multi-Agent Film Recovery</span>
          </div>

          <h1 className="font-display text-[34px] sm:text-[44px] md:text-[50px] font-bold tracking-tight text-[var(--cc-text-primary)] leading-[1.12]">
            Continuity Council
          </h1>

          <p className="text-[17px] sm:text-[20px] font-medium text-[var(--cc-text-primary)] leading-snug">
            Real-time shoot recovery powered by Google ADK, ClickHouse intelligence, and Gemini.
          </p>

          <p className="text-[14px] sm:text-[15px] text-[var(--cc-text-secondary)] leading-relaxed max-w-2xl mx-auto">
            Continuity Council is an autonomous multi-agent platform designed to resolve film and television production disruptions in real time. When call sheet conflicts, actor illness, or weather delays threaten a shoot, the council coordinates six specialized agents to evaluate trade-offs, query historical benchmarks, and propose grounded recovery strategies with minimal financial overrun.
          </p>

          <div className="pt-3 flex flex-wrap items-center justify-center gap-3.5">
            <Button
              size="lg"
              data-testid="landing-cta-button"
              onClick={() => navigate("/dashboard")}
              className="h-11 rounded-[12px] px-6 text-[14.5px] font-semibold shadow-md"
            >
              Launch Production Council
              <ArrowRight size={16} className="ml-1.5" />
            </Button>

            <Button
              variant="outline"
              size="lg"
              onClick={() => navigate("/methodology")}
              className="h-11 rounded-[12px] px-5 text-[14px] font-medium"
            >
              Cost & Data Methodology
              <ArrowUpRight size={15} className="ml-1 text-[var(--cc-text-tertiary)]" />
            </Button>
          </div>
        </section>

        {/* Feature Highlights Grid */}
        <section className="mt-16 md:mt-24 space-y-6">
          <div className="text-center space-y-1.5">
            <div className="text-[12px] font-semibold uppercase tracking-wider text-[var(--cc-text-tertiary)]">
              Core Architecture
            </div>
            <h2 className="font-display text-[22px] sm:text-[26px] font-semibold text-[var(--cc-text-primary)]">
              Engineered for real-world studio continuity
            </h2>
          </div>

          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-5 pt-4">
            {HIGHLIGHTS.map((h, i) => {
              const Icon = h.icon;
              return (
                <div
                  key={i}
                  className="cc-card p-6 rounded-[14px] border border-[var(--cc-border)] bg-[var(--cc-surface)] shadow-sm hover:border-[var(--cc-text-tertiary)]/40 transition-colors duration-200 flex flex-col justify-between"
                >
                  <div className="space-y-3">
                    <div className="flex items-center justify-between">
                      <div className="flex h-9 w-9 items-center justify-center rounded-[9px] bg-[var(--cc-surface-sunken)] border border-[var(--cc-border)] text-[var(--cc-text-primary)]">
                        <Icon size={18} strokeWidth={1.75} />
                      </div>
                      <span className="text-[11px] font-medium font-mono px-2 py-0.5 rounded-[6px] bg-[var(--cc-surface-hover)] border border-[var(--cc-border)] text-[var(--cc-text-secondary)]">
                        {h.badge}
                      </span>
                    </div>
                    <h3 className="text-[15px] font-semibold text-[var(--cc-text-primary)]">
                      {h.title}
                    </h3>
                    <p className="text-[13px] leading-relaxed text-[var(--cc-text-secondary)]">
                      {h.description}
                    </p>
                  </div>
                </div>
              );
            })}
          </div>
        </section>

        {/* 3-Step Production Workflow */}
        <section className="mt-16 md:mt-24 rounded-[16px] border border-[var(--cc-border)] bg-[var(--cc-surface-elevated)] p-8 md:p-10 shadow-sm">
          <div className="text-center space-y-1.5 mb-8">
            <div className="text-[12px] font-semibold uppercase tracking-wider text-[var(--cc-text-tertiary)]">
              Disruption Protocol
            </div>
            <h2 className="font-display text-[22px] sm:text-[26px] font-semibold text-[var(--cc-text-primary)]">
              From incident report to approved call sheet in seconds
            </h2>
          </div>

          <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
            {WORKFLOW_STEPS.map((w, idx) => (
              <div key={idx} className="space-y-2.5">
                <div className="text-[12px] font-mono font-bold text-[var(--cc-text-tertiary)]">
                  STEP {w.step}
                </div>
                <h4 className="text-[15px] font-semibold text-[var(--cc-text-primary)]">
                  {w.title}
                </h4>
                <p className="text-[13px] leading-relaxed text-[var(--cc-text-secondary)]">
                  {w.description}
                </p>
              </div>
            ))}
          </div>
        </section>

        {/* Bottom Banner Callout */}
        <section className="mt-16 text-center space-y-4 py-8">
          <h3 className="font-display text-[20px] sm:text-[24px] font-semibold text-[var(--cc-text-primary)]">
            Ready to explore production recovery?
          </h3>
          <p className="text-[13.5px] text-[var(--cc-text-secondary)] max-w-md mx-auto">
            Test real-world scenarios across lead cast illness, location permit revocations, weather events, and equipment failures.
          </p>
          <div className="pt-2">
            <Button
              size="lg"
              onClick={() => navigate("/dashboard")}
              className="h-10 rounded-[10px] px-5 text-[13.5px] font-semibold"
            >
              Enter Studio Dashboard
              <ArrowRight size={15} className="ml-1" />
            </Button>
          </div>
        </section>
      </main>

      {/* Footer */}
      <footer className="border-t border-[var(--cc-border)] bg-[var(--cc-surface)] px-6 py-6 text-center text-[12px] text-[var(--cc-text-secondary)]">
        <div className="mx-auto max-w-[1240px] flex flex-col sm:flex-row items-center justify-between gap-3">
          <div>
            Continuity Council: Built for the "Lights. Camera. Code." Hackathon
          </div>
          <div className="flex items-center gap-4 text-[12px]">
            <Link to="/dashboard" className="hover:text-[var(--cc-text-primary)] transition-colors">
              Dashboard
            </Link>
            <span>·</span>
            <Link to="/methodology" className="hover:text-[var(--cc-text-primary)] transition-colors">
              Methodology
            </Link>
            <span>·</span>
            <Link to="/settings" className="hover:text-[var(--cc-text-primary)] transition-colors">
              Settings
            </Link>
          </div>
        </div>
      </footer>
    </div>
  );
}
