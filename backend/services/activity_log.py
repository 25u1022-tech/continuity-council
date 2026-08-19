"""In-memory ring buffer of recent ClickHouse / MCP activity.

Feeds the Live MCP Ticker in the UI top bar so judges can see real database
activity on every screen. Thread-safe, capped, zero persistence (demo-scale).
"""
from __future__ import annotations

import itertools
import threading
from collections import deque
from datetime import datetime, timezone
from typing import Any, Dict, List

_events: deque = deque(maxlen=50)
_lock = threading.Lock()
_ids = itertools.count(1)


def record(source: str, label: str, rows: int | None = None, latency_ms: int | None = None) -> None:
    """Record one activity event.

    source: 'mcp-clickhouse' (MCP round trips) or 'clickhouse' (direct client).
    label:  short human-readable description, e.g. 'run_query · strategy_performance'.
    """
    event = {
        "id": next(_ids),
        "ts": datetime.now(timezone.utc).isoformat(),
        "source": source,
        "label": label[:120],
        "rows": rows,
        "latency_ms": latency_ms,
    }
    with _lock:
        _events.append(event)


def recent(limit: int = 10) -> List[Dict[str, Any]]:
    with _lock:
        items = list(_events)
    items.reverse()  # newest first
    return items[: max(1, min(50, limit))]
