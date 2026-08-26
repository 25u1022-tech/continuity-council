import React, { useEffect, useRef, useState } from "react";
import { getActivity, timeAgo } from "../lib/api";
import { Database } from "lucide-react";

/**
 * Live MCP Ticker — quiet, always-on proof of ClickHouse activity in the top bar.
 * Shows the most recent MCP / ClickHouse event with clean Apple Minimal styling.
 */
export const ActivityTicker = () => {
  const [event, setEvent] = useState(null);
  const [now, setNow] = useState(Date.now());
  const alive = useRef(true);

  useEffect(() => {
    alive.current = true;
    const load = () =>
      getActivity(1)
        .then((d) => {
          if (alive.current && d?.events?.length) setEvent(d.events[0]);
        })
        .catch(() => {});
    load();
    const poll = setInterval(load, 4000);
    const clock = setInterval(() => alive.current && setNow(Date.now()), 4000);
    return () => {
      alive.current = false;
      clearInterval(poll);
      clearInterval(clock);
    };
  }, []);

  const fresh = event && now - new Date(event.ts).getTime() < 15000;

  return (
    <div
      data-testid="mcp-activity-ticker"
      className="hidden min-w-0 items-center gap-2 rounded-[7px] border border-[var(--cc-border)] bg-[var(--cc-surface)] px-3 py-1 lg:flex shadow-sm"
      title={event ? `${event.source} · ${event.label}` : "ClickHouse activity"}
    >
      <span
        data-testid="mcp-activity-dot"
        className={`inline-block h-1.5 w-1.5 shrink-0 rounded-full ${
          fresh ? "cc-pulse-dot bg-[var(--cc-yellow-dot)]" : event ? "bg-[var(--cc-green-dot)]" : "bg-[var(--cc-text-quaternary)]"
        }`}
      />
      <Database size={12} strokeWidth={1.75} className="shrink-0 text-[var(--cc-text-tertiary)]" />
      {event ? (
        <span
          key={event.id}
          data-testid="mcp-activity-label"
          className="cc-fade-up tabular truncate font-mono text-[11px] text-[var(--cc-text-secondary)]"
        >
          {event.label}
          {event.rows !== null && event.rows !== undefined ? ` · ${event.rows} rows` : ""}
          {event.latency_ms !== null && event.latency_ms !== undefined ? ` · ${event.latency_ms} ms` : ""}
          <span className="text-[var(--cc-text-tertiary)]"> · {timeAgo(event.ts)}</span>
        </span>
      ) : (
        <span data-testid="mcp-activity-label" className="font-mono text-[11px] text-[var(--cc-text-tertiary)]">
          ClickHouse idle
        </span>
      )}
    </div>
  );
};
