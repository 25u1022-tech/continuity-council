"""In-memory live case store (polling-friendly).

ClickHouse remains the immutable event store (disruption_cases, decision_ledger,
schedule_changes); this dict holds hot state for the active demo session.
"""
from __future__ import annotations

from typing import Dict, List, Optional

from models import CaseState

_CASES: Dict[str, CaseState] = {}


def put(case: CaseState) -> None:
    _CASES[case.case_id] = case


def get(case_id: str) -> Optional[CaseState]:
    return _CASES.get(case_id)


def all_cases() -> List[CaseState]:
    return sorted(_CASES.values(), key=lambda c: c.created_at, reverse=True)


def clear(production_id: Optional[str] = None) -> int:
    """Demo reset: drop in-memory cases. With `production_id`, only that
    production's cases are removed. Returns the number removed."""
    global _CASES
    if production_id is None:
        n = len(_CASES)
        _CASES.clear()
        return n
    to_remove = [cid for cid, c in _CASES.items() if c.production_id == production_id]
    for cid in to_remove:
        del _CASES[cid]
    return len(to_remove)
