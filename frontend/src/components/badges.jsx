import React from "react";

/**
 * Apple Minimal Badges & Status Pills
 * Understated, 8-14% tinted pill backgrounds with high-contrast text meeting WCAG AA.
 */

const pillBase =
  "inline-flex items-center gap-1.5 rounded-[5px] px-2 py-0.5 text-[11.5px] font-medium leading-4 tracking-tight whitespace-nowrap cc-transition";

export const Pill = ({ tone = "gray", children, testId, className = "" }) => {
  const toneClasses = {
    gray: "bg-[var(--cc-gray-bg)] text-[var(--cc-gray-text)] border border-[var(--cc-border-subtle)]",
    green: "bg-[var(--cc-green-bg)] text-[var(--cc-green-text)]",
    red: "bg-[var(--cc-red-bg)] text-[var(--cc-red-text)]",
    yellow: "bg-[var(--cc-yellow-bg)] text-[var(--cc-yellow-text)]",
    amber: "bg-[var(--cc-yellow-bg)] text-[var(--cc-yellow-text)]",
    blue: "bg-[var(--cc-blue-bg)] text-[var(--cc-blue-text)]",
    neutral: "bg-[var(--cc-gray-bg)] text-[var(--cc-text-secondary)] border border-[var(--cc-border)]",
    gold: "bg-[var(--cc-gray-bg)] text-[var(--cc-text-primary)] border border-[var(--cc-border)] font-medium",
  };

  return (
    <span
      data-testid={testId}
      className={`${pillBase} ${toneClasses[tone] || toneClasses.gray} ${className}`}
    >
      {children}
    </span>
  );
};

const STATUS_TONE = {
  open: "gray",
  investigating: "yellow",
  options_ready: "yellow",
  approved: "green",
  closed: "gray",
  error: "red",
};

const STATUS_LABEL = {
  open: "Open",
  investigating: "Investigating",
  options_ready: "Options ready",
  approved: "Approved",
  closed: "Closed",
  error: "Error",
};

export const StatusBadge = ({ status, testId }) => (
  <Pill
    tone={STATUS_TONE[status] || "gray"}
    testId={testId || `status-badge-${status}`}
  >
    <span
      className={`h-1.5 w-1.5 rounded-full ${
        status === "approved"
          ? "bg-[var(--cc-green-dot)]"
          : status === "investigating" || status === "options_ready"
          ? "bg-[var(--cc-yellow-dot)] cc-pulse-dot"
          : status === "error"
          ? "bg-[var(--cc-red-dot)]"
          : "bg-[var(--cc-gray-dot)]"
      }`}
    />
    {STATUS_LABEL[status] || status}
  </Pill>
);

const SEVERITY_TONE = { low: "green", medium: "yellow", high: "red" };

export const SeverityBadge = ({ severity }) => (
  <Pill
    tone={SEVERITY_TONE[severity] || "yellow"}
    testId={`severity-badge-${severity}`}
  >
    {severity ? severity.charAt(0).toUpperCase() + severity.slice(1) : "-"}
  </Pill>
);

export const RiskBadge = ({ score }) => {
  const label = score < 0.2 ? "Low" : score < 0.45 ? "Medium" : "High";
  const tone = label === "Low" ? "green" : label === "Medium" ? "yellow" : "red";
  return (
    <Pill tone={tone}>
      {label} · <span className="tabular font-medium">{Number(score).toFixed(2)}</span>
    </Pill>
  );
};

export const ComplianceBadge = ({ valid }) => (
  <Pill
    tone={valid ? "green" : "red"}
    testId={valid ? "compliance-badge-valid" : "compliance-badge-invalid"}
  >
    {valid ? "Valid" : "Invalid"}
  </Pill>
);

export const MonoPill = ({ children, tone = "gray", testId }) => (
  <Pill tone={tone} testId={testId} className="font-mono text-[11px]">
    {children}
  </Pill>
);

// Kept for API compatibility with earlier imports
export const ClickHouseBadge = ({ children = "ClickHouse" }) => (
  <MonoPill tone="gray">{children}</MonoPill>
);
