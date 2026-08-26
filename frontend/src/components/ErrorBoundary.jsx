import React from "react";
import { AlertCircle, RotateCcw } from "lucide-react";
import { safeStorage } from "../lib/storage";

export class ErrorBoundary extends React.Component {
  constructor(props) {
    super(props);
    this.state = { hasError: false, error: null, errorInfo: null };
  }

  static getDerivedStateFromError(error) {
    return { hasError: true, error };
  }

  componentDidCatch(error, errorInfo) {
    console.error("ErrorBoundary caught runtime error:", error, errorInfo);
    this.setState({ error, errorInfo });
  }

  handleReload = () => {
    window.location.reload();
  };

  handleReset = () => {
    safeStorage.removeItem("cc_active_case");
    window.location.href = "/dashboard";
  };

  render() {
    if (this.state.hasError) {
      const errorMsg =
        this.state.error?.message ||
        (typeof this.state.error === "string"
          ? this.state.error
          : "An unexpected runtime error occurred");
      const errorStack = this.state.error?.stack || "";

      return (
        <div
          data-testid="root-error-boundary"
          className="flex min-h-screen items-center justify-center p-6 bg-[var(--cc-canvas,#0a0a0c)] text-[var(--cc-text-primary,#f4f4f6)] font-sans antialiased"
        >
          <div className="w-full max-w-md rounded-[16px] border border-[var(--cc-border,#27272a)] bg-[var(--cc-surface,#121215)] p-6 shadow-2xl backdrop-blur">
            <div className="flex items-center gap-3">
              <div className="flex h-10 w-10 shrink-0 items-center justify-center rounded-[10px] bg-red-500/10 text-red-400 border border-red-500/20">
                <AlertCircle size={20} strokeWidth={2} />
              </div>
              <div>
                <h1 className="font-display text-[16px] font-semibold tracking-tight text-[var(--cc-text-primary,#f4f4f6)]">
                  Something went wrong
                </h1>
                <p className="text-[12px] text-[var(--cc-text-secondary,#a1a1aa)]">
                  Continuity Council encountered a render error
                </p>
              </div>
            </div>

            <div className="mt-4 rounded-[10px] border border-[var(--cc-border,#27272a)] bg-[var(--cc-surface-sunken,#09090b)] p-3.5">
              <div className="text-[11px] font-medium uppercase tracking-wider text-[var(--cc-text-tertiary,#71717a)]">
                Error Details
              </div>
              <div className="mt-1 font-mono text-[12px] text-red-400 break-words whitespace-pre-wrap leading-relaxed">
                {errorMsg}
              </div>
              {errorStack && (
                <details className="mt-2 text-[10px] text-[var(--cc-text-tertiary,#71717a)]">
                  <summary className="cursor-pointer hover:underline">View stack trace</summary>
                  <pre className="mt-1.5 max-h-32 overflow-auto font-mono text-[10px] leading-tight text-[var(--cc-text-secondary,#a1a1aa)]">
                    {errorStack}
                  </pre>
                </details>
              )}
            </div>

            <div className="mt-5 flex items-center gap-2.5">
              <button
                type="button"
                onClick={this.handleReload}
                className="flex-1 inline-flex items-center justify-center gap-2 rounded-[10px] bg-[var(--cc-primary,#ffffff)] px-4 py-2.5 text-[13px] font-medium text-[var(--cc-primary-foreground,#09090b)] shadow-sm hover:opacity-90 transition-opacity cursor-pointer"
              >
                <RotateCcw size={14} strokeWidth={2} />
                Reload
              </button>
              <button
                type="button"
                onClick={this.handleReset}
                className="rounded-[10px] border border-[var(--cc-border,#27272a)] bg-[var(--cc-surface-hover,#1c1c21)] px-3 py-2.5 text-[13px] font-medium text-[var(--cc-text-secondary,#a1a1aa)] hover:text-[var(--cc-text-primary,#f4f4f6)] transition-colors cursor-pointer"
              >
                Go to Dashboard
              </button>
            </div>
          </div>
        </div>
      );
    }

    return this.props.children;
  }
}

export default ErrorBoundary;
