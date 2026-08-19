"""Option Scoring Model — exact weighted formula from the TRD.

score = 0.40 * cost_saving_score
      + 0.30 * delay_saving_score
      + 0.20 * continuity_safety_score
      + 0.10 * compliance_safety_score

cost/delay saving scores are normalized against the candidate set (grounded in
ClickHouse historical averages). Options failing hard compliance constraints
are heavily penalized and marked invalid.
"""
from __future__ import annotations

from typing import List

from models import RecoveryOption

W_COST = 0.40
W_DELAY = 0.30
W_CONTINUITY = 0.20
W_COMPLIANCE = 0.10
HARD_FAIL_PENALTY = 0.25  # multiplier applied when compliance hard-fails


def _normalize_inverse(value: float, lo: float, hi: float) -> float:
    """1.0 for the cheapest/fastest, 0.0 for the worst."""
    if hi <= lo:
        return 1.0
    return max(0.0, min(1.0, 1.0 - (value - lo) / (hi - lo)))


def score_options(options: List[RecoveryOption]) -> List[RecoveryOption]:
    if not options:
        return options

    costs = [o.estimated_cost_usd for o in options]
    delays = [o.estimated_delay_hours for o in options]
    lo_c, hi_c = min(costs), max(costs)
    lo_d, hi_d = min(delays), max(delays)

    for o in options:
        cost_saving = _normalize_inverse(o.estimated_cost_usd, lo_c, hi_c)
        delay_saving = _normalize_inverse(o.estimated_delay_hours, lo_d, hi_d)
        continuity_safety = 1.0 - max(0.0, min(1.0, o.continuity_risk_score))
        compliance_safety = 1.0 - max(0.0, min(1.0, o.compliance_risk_score))

        score = (
            W_COST * cost_saving
            + W_DELAY * delay_saving
            + W_CONTINUITY * continuity_safety
            + W_COMPLIANCE * compliance_safety
        )
        if not o.compliance_valid:
            score *= HARD_FAIL_PENALTY
        o.score = round(score, 3)

    # Invalid options always rank below every valid option (TRD: marked invalid
    # or heavily penalized) — then by weighted score descending.
    ranked = sorted(options, key=lambda o: (o.compliance_valid, o.score), reverse=True)
    for idx, o in enumerate(ranked, start=1):
        o.rank = idx
        o.recommended = False
    for o in ranked:
        if o.compliance_valid:
            o.recommended = True
            break
    if not any(o.recommended for o in ranked) and ranked:
        ranked[0].recommended = True
    return ranked
