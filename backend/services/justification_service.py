"""Explainability Layer: Natural-language justification engine for recovery options.

Every recovery option receives a one-line, plain-English justification explaining
WHY it ranked where it did, citing trade-offs and empirical ClickHouse evidence.

SLA GUARANTEE:
- Parallel execution via asyncio.gather with a strict 1.5s hard timeout.
- Instant deterministic fallback if Gemini times out, throws, or quota is hit.
- Investigation total latency SLA (<=2.1s) is strictly preserved.
"""
from __future__ import annotations

import asyncio
import logging
from typing import Any, Dict, List, Optional, Union

from services import gemini_client

logger = logging.getLogger("continuity.justification")


def _get_field(obj: Any, field: str, default: Any = None) -> Any:
    if isinstance(obj, dict):
        return obj.get(field, default)
    return getattr(obj, field, default)


def _get_evidence_sample_size(opt: Any, evidence: Optional[Union[Dict, List]] = None) -> int:
    evidence_obj = _get_field(opt, "evidence")
    if evidence_obj:
        cases = _get_field(evidence_obj, "past_cases", 0)
        if cases and int(cases) > 0:
            return int(cases)

    cost_bd = _get_field(opt, "cost_breakdown")
    if cost_bd:
        sample = _get_field(cost_bd, "historical_sample_size", 0)
        if sample and int(sample) > 0:
            return int(sample)

    strategy = _get_field(opt, "strategy", "")
    if isinstance(evidence, dict) and strategy in evidence:
        ev = evidence[strategy]
        cases = _get_field(ev, "past_cases", 0)
        if cases and int(cases) > 0:
            return int(cases)
    elif isinstance(evidence, list):
        for ev in evidence:
            strat = _get_field(ev, "resolution_strategy", "") or _get_field(ev, "strategy", "")
            if strat == strategy:
                cases = _get_field(ev, "past_cases", 0)
                if cases and int(cases) > 0:
                    return int(cases)

    return 0


def format_deterministic_fallback(opt: Any, evidence: Optional[Union[Dict, List]] = None) -> str:
    """Deterministic fallback justification template conforming to spec."""
    rank = _get_field(opt, "rank", 1) or 1
    cost = int(_get_field(opt, "estimated_cost_usd", 0) or 0)
    delay = float(_get_field(opt, "estimated_delay_hours", 0.0) or 0.0)
    sample_size = _get_evidence_sample_size(opt, evidence)

    cost_str = f"{cost:,}"
    delay_str = f"{delay:.1f}" if delay % 1 != 0 else f"{int(delay)}"
    sample_str = f"{sample_size:,}" if sample_size > 0 else "multiple"

    return f"Ranked #{rank}: ${cost_str} avg cost and {delay_str}h delay based on {sample_str} similar historical cases."


async def _generate_single_justification(opt: Any, evidence: Optional[Union[Dict, List]] = None) -> str:
    """Prompt Gemini for a concise, one-sentence plain-English justification for an option."""
    rank = _get_field(opt, "rank", 1) or 1
    name = _get_field(opt, "name", "Recovery Option")
    strategy = _get_field(opt, "strategy", "strategy")
    cost = int(_get_field(opt, "estimated_cost_usd", 0) or 0)
    delay = float(_get_field(opt, "estimated_delay_hours", 0.0) or 0.0)
    sample_size = _get_evidence_sample_size(opt, evidence)
    valid = _get_field(opt, "compliance_valid", True)
    recommended = _get_field(opt, "recommended", False)

    fallback = format_deterministic_fallback(opt, evidence)

    if not gemini_client.is_configured() or gemini_client.quota_hit():
        return fallback

    valid_text = "passes all compliance rules" if valid else "blocked by compliance constraints"
    rec_text = " (top recommendation)" if recommended else ""
    sample_text = f"{sample_size:,} past ClickHouse cases" if sample_size > 0 else "historical disruption data"

    prompt = (
        f"Write a concise, one-sentence plain-English justification for why Option '{name}' ({strategy}){rec_text} is ranked #{rank}. "
        f"Mention key trade-offs (${cost:,} estimated cost overrun, {delay:.1f}h schedule delay, {valid_text}) "
        f"and the empirical evidence base ({sample_text}). "
        f"Rules: Maximum 25 words. Plain natural text only. No quotes, no markdown, no bullets."
    )

    try:
        text = await gemini_client.generate_text(prompt, timeout=1.4, temperature=0.2)
        if text:
            cleaned = text.strip().strip('"').strip("'").replace("\n", " ")
            import re
            cleaned = re.sub(r"(\d+\.\d{2,})h", lambda m: f"{float(m.group(1)):.1f}h", cleaned)
            cleaned = re.sub(r"\$(\d+\.\d{2,})k", lambda m: f"${float(m.group(1)):.1f}k", cleaned)
            if len(cleaned) > 10 and not cleaned.lower().startswith("error"):
                return cleaned
    except Exception as exc:  # noqa: BLE001
        logger.debug("Gemini justification generation failed for option %s: %s", name, exc)

    return fallback


async def generate_justifications(
    options: List[Any],
    evidence: Optional[Union[Dict, List]] = None,
) -> Dict[str, str]:
    """Generate plain-English justifications for a list of recovery options in parallel.

    Guarantees completion within 1.5s by using asyncio.wait_for and instant deterministic fallbacks.
    Attaches the `justification` attribute/key to each option in-place and returns a map.
    """
    if not options:
        return {}

    tasks = [_generate_single_justification(opt, evidence) for opt in options]

    try:
        results = await asyncio.wait_for(
            asyncio.gather(*tasks, return_exceptions=True),
            timeout=1.5,
        )
    except (asyncio.TimeoutError, Exception) as exc:
        logger.warning("Justification service timeout/error (%s) — applying deterministic fallbacks", exc)
        results = [format_deterministic_fallback(opt, evidence) for opt in options]

    justifications_map: Dict[str, str] = {}
    for idx, opt in enumerate(options):
        res = results[idx] if idx < len(results) else None
        if isinstance(res, Exception) or not res or not isinstance(res, str):
            justification = format_deterministic_fallback(opt, evidence)
        else:
            justification = res.strip()

        opt_id = _get_field(opt, "option_id", str(idx))
        justifications_map[opt_id] = justification

        if isinstance(opt, dict):
            opt["justification"] = justification
        else:
            try:
                setattr(opt, "justification", justification)
            except Exception:
                pass

    return justifications_map
