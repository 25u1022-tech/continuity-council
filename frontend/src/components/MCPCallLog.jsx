import React, { useState } from "react";
import { Button } from "./ui/button";
import { Collapsible, CollapsibleContent, CollapsibleTrigger } from "./ui/collapsible";
import { Pill, MonoPill } from "./badges";
import { Database, ChevronDown, Copy, Check } from "lucide-react";

const LogRow = ({ call, isNew }) => {
  const [open, setOpen] = useState(false);
  const [copied, setCopied] = useState(false);

  const copySql = async (e) => {
    e.stopPropagation();
    try {
      await navigator.clipboard.writeText(call.sql);
      setCopied(true);
      setTimeout(() => setCopied(false), 1200);
    } catch {
      /* clipboard unavailable */
    }
  };

  return (
    <Collapsible open={open} onOpenChange={setOpen}>
      <div data-testid="mcp-call-log-row" className="border-b border-[var(--cc-border)] last:border-b-0">
        <CollapsibleTrigger asChild>
          <button
            type="button"
            className="cc-transition flex h-[52px] w-full items-center gap-3 px-5 text-left hover:bg-[var(--cc-surface-hover)]"
          >
            <span className="font-mono tabular text-[11px] text-[var(--cc-text-tertiary)] shrink-0">
              {new Date(call.timestamp).toLocaleTimeString("en-US", { hour12: false })}
            </span>
            <MonoPill tone="neutral">{call.tool}</MonoPill>
            <span className="min-w-0 flex-1 truncate font-mono text-xs text-[var(--cc-text-secondary)]">{call.sql}</span>
            {call.status === "error" ? (
              <Pill tone="red">Error</Pill>
            ) : (
              <span className="shrink-0 font-mono tabular text-[11px] text-[var(--cc-text-secondary)]">
                {call.latency_ms} ms · {call.rows_returned} rows
              </span>
            )}
            <ChevronDown
              size={14}
              className={`cc-transition shrink-0 text-[var(--cc-text-tertiary)] ${open ? "rotate-180" : ""}`}
            />
          </button>
        </CollapsibleTrigger>
        <CollapsibleContent>
          <div className="px-5 pb-4">
            <div className="relative rounded-[10px] bg-[var(--cc-surface-sunken)] p-4 border border-[var(--cc-border)]">
              <pre className="overflow-auto whitespace-pre-wrap font-mono text-[11px] leading-5 text-[var(--cc-text-primary)]">
                {call.sql}
              </pre>
              <Button
                data-testid="mcp-log-copy-sql-button"
                size="sm"
                variant="ghost"
                onClick={copySql}
                className="absolute right-2 top-2 h-7 gap-1 rounded-[8px] px-2 text-[11px]"
              >
                {copied ? <Check size={12} /> : <Copy size={12} />}
                {copied ? "Copied" : "Copy"}
              </Button>
              {call.error ? (
                <div className="mt-2 font-mono text-[11px] text-[var(--cc-red-text)]">{call.error}</div>
              ) : null}
            </div>
          </div>
        </CollapsibleContent>
      </div>
    </Collapsible>
  );
};

export const MCPCallLog = ({ calls = [], connected = true, compact = false }) => (
  <div data-testid="mcp-call-log" className="cc-card overflow-hidden">
    <div className="flex items-center justify-between border-b border-[var(--cc-border)] px-5 py-3.5 bg-[var(--cc-surface-hover)]">
      <div className="flex items-center gap-2.5">
        <Database size={15} strokeWidth={1.75} className="text-[var(--cc-text-secondary)]" />
        <span className="text-[13px] font-semibold text-[var(--cc-text-primary)]">Live MCP call log</span>
        <MonoPill tone="gray">mcp-clickhouse · stdio</MonoPill>
      </div>
      <div className="flex items-center gap-2">
        <span
          className={`inline-block h-1.5 w-1.5 rounded-full ${connected ? "bg-[var(--cc-green-dot)]" : "bg-[var(--cc-red-dot)]"}`}
        />
        <span className="text-[11px] font-medium text-[var(--cc-text-secondary)]">{connected ? "Connected" : "Offline"}</span>
      </div>
    </div>
    {calls.length === 0 ? (
      <div className="px-5 py-7 text-center text-[13px] text-[var(--cc-text-secondary)]">
        {compact
          ? "No MCP calls recorded."
          : "Waiting for Budget Sentinel to dispatch ClickHouse queries."}
      </div>
    ) : (
      calls.map((c, i) => <LogRow key={c.id} call={c} isNew={i === calls.length - 1} />)
    )}
  </div>
);
