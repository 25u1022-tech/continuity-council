"""Continuity Council — strictly typed Pydantic models (state machine + API)."""
from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List, Literal, Optional

from pydantic import BaseModel, Field, model_validator


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


def short_id(prefix: str) -> str:
    return f"{prefix}_{uuid.uuid4().hex[:8]}"


DisruptionType = Literal[
    "lead_actor_unavailable",
    "supporting_actor_unavailable",
    "location_unavailable",
    "equipment_failure",
    "weather_delay",
    "permit_issue",
]

Severity = Literal["low", "medium", "high"]

CaseStatus = Literal["open", "investigating", "options_ready", "approved", "closed", "error"]

AgentStatus = Literal["pending", "running", "complete", "error"]

AGENT_KEYS = [
    "orchestrator",
    "schedule_optimizer",
    "budget_sentinel",
    "continuity_memory",
    "compliance",
    "auditor",
]

AGENT_DISPLAY = {
    "orchestrator": "Orchestrator",
    "schedule_optimizer": "Schedule Optimizer",
    "budget_sentinel": "Budget Sentinel",
    "continuity_memory": "Continuity Memory",
    "compliance": "Compliance",
    "auditor": "Auditor",
}


# ---------------------------------------------------------------------------
# Requests
# ---------------------------------------------------------------------------
class DisruptionReport(BaseModel):
    production_id: str = Field("prod_001", min_length=3, max_length=64, pattern=r"^[a-zA-Z0-9_\-]+$")
    disruption_type: DisruptionType
    affected_day: int = Field(ge=1, le=3650)
    affected_cast_id: str = ""
    affected_location_id: str = ""
    severity: Severity = "high"
    notes: str = ""

    @model_validator(mode="after")
    def validate_affected_resource(self):
        if self.disruption_type == "location_unavailable" and not self.affected_location_id.strip():
            raise ValueError("affected_location_id is required for location_unavailable")
        if self.disruption_type in ("lead_actor_unavailable", "supporting_actor_unavailable") and not self.affected_cast_id.strip():
            raise ValueError("affected_cast_id is required for actor-unavailable disruptions")
        return self


class ApprovalRequest(BaseModel):
    option_id: str
    approved_by: str = "producer"


class ChatSource(BaseModel):
    type: str = "mcp_query"
    query: str
    result_summary: str


class ChatRequest(BaseModel):
    message: str = Field(min_length=1, max_length=2000)
    production_id: str = Field("prod_001", min_length=1, max_length=64)
    case_id: Optional[str] = None
    conversation_history: Optional[List[Dict[str, Any]]] = None


class ChatResponse(BaseModel):
    answer: str
    sources: List[ChatSource] = []


class ParseNLDisruptionRequest(BaseModel):
    description: str = Field(..., min_length=1, max_length=2000)
    production_id: str = Field("prod_001", min_length=1, max_length=64)


class ParseNLDisruptionResponse(BaseModel):
    confidence: Literal["high", "medium", "low"] = "medium"
    disruption_type: str = "lead_actor_unavailable"
    severity: str = "medium"
    affected_day: int = 1
    affected_date: str = ""
    affected_cast_id: str = ""
    affected_cast_name: str = ""
    affected_location_id: str = ""
    affected_location_name: str = ""
    notes: str = ""
    scene_ids: List[str] = []
    reasoning: str = ""


# ---------------------------------------------------------------------------
# Production onboarding (create-your-own production)
# ---------------------------------------------------------------------------
class CastInput(BaseModel):
    name: str = Field(min_length=1, max_length=120)
    role: str = "supporting"            # lead | supporting | background | free text
    available_days: List[int] = []      # 1-based shoot days this member is available; empty = all


class LocationInput(BaseModel):
    name: str = Field(min_length=1, max_length=120)
    location_type: str = "interior"     # interior | exterior | stage | studio ...
    permit_notes: str = ""              # permit / constraint text
    available_days: List[int] = []      # 1-based shoot days available; empty = all
    latitude: Optional[float] = None
    longitude: Optional[float] = None
    country_code: Optional[str] = None
    city_tier: Optional[str] = None
    currency_code: Optional[str] = None
    geo_mult: Optional[float] = None


class CreateProductionRequest(BaseModel):
    name: str = Field(min_length=1, max_length=160)
    shoot_start: str                    # ISO date YYYY-MM-DD
    shoot_end: str                      # ISO date YYYY-MM-DD
    director: str = ""
    cast: List[CastInput] = []
    locations: List[LocationInput] = []


# ---------------------------------------------------------------------------
# Agent workflow state
# ---------------------------------------------------------------------------
class AgentState(BaseModel):
    key: str
    display_name: str
    status: AgentStatus = "pending"
    summary: str = ""
    detail: str = ""
    started_at: Optional[datetime] = None
    finished_at: Optional[datetime] = None
    duration_ms: Optional[int] = None


class MCPCall(BaseModel):
    id: str = Field(default_factory=lambda: short_id("mcp"))
    timestamp: datetime = Field(default_factory=utcnow)
    agent: str = "budget_sentinel"
    tool: str = "run_query"
    template_id: str = ""
    sql: str = ""
    rows_returned: int = 0
    latency_ms: int = 0
    status: Literal["success", "error"] = "success"
    error: str = ""


class EvidenceRow(BaseModel):
    resolution_strategy: str
    avg_cost_overrun_usd: float = 0
    avg_delay_hours: float = 0
    avg_continuity_risk: float = 0
    avg_compliance_risk: float = 0
    avg_success_score: float = 0
    past_cases: int = 0
    studio_id: str = "global"
    is_blended: bool = False
    blend_weight: float = 1.0
    footnote: str = ""


class BudgetSentinelResult(BaseModel):
    studio_id: str = "global"
    evidence_cohort: str = "global"
    evidence_footnote: str = ""
    evidence_narrative: str = ""
    evidence_rows: List[EvidenceRow] = []
    mcp_calls: List[MCPCall] = []


class SceneChange(BaseModel):
    scene_id: str
    scene_title: str = ""
    from_day: int
    to_day: int
    from_location: str = ""
    to_location: str = ""
    change_type: str = "move_scene_day"


class ContinuityRisk(BaseModel):
    scene_ids: List[str] = []
    risk: str
    level: Literal["low", "medium", "high"] = "medium"


class CostLineItem(BaseModel):
    line: str
    amount_usd: int
    source: str = "Rate card benchmark"


class CostBreakdown(BaseModel):
    total_usd: int = 0
    currency: str = "USD"
    breakdown: List[CostLineItem] = []
    fx_rate_applied: float = 1.0
    weather_risk: int = 0
    transit_distance_miles: float = 0.0
    historical_sample_size: int = 0
    calibration_method: str = "70% bottom-up rate card + 30% ClickHouse historical evidence"


class RecoveryOption(BaseModel):
    option_id: str
    name: str
    strategy: str
    description: str = ""
    scene_changes: List[SceneChange] = []
    estimated_cost_usd: int = 0
    estimated_delay_hours: float = 0
    continuity_risk_score: float = 0.0
    continuity_risks: List[ContinuityRisk] = []
    compliance_valid: bool = True
    compliance_warnings: List[str] = []
    compliance_risk_score: float = 0.0
    evidence: Optional[EvidenceRow] = None
    cost_breakdown: Optional[CostBreakdown] = None
    weather_risk: int = 0
    weather_summary: str = ""
    fx_summary: str = ""
    transit_summary: str = ""
    transit_distance_miles: float = 0.0
    score: float = 0.0
    rank: int = 0
    recommended: bool = False
    justification: str = ""


class StageEvent(BaseModel):
    stage: str
    at: datetime = Field(default_factory=utcnow)


class CaseState(BaseModel):
    case_id: str
    production_id: str
    disruption: DisruptionReport
    status: CaseStatus = "open"
    stages: List[StageEvent] = []
    agents: Dict[str, AgentState] = {}
    mcp_calls: List[MCPCall] = []
    options: List[RecoveryOption] = []
    evidence_rows: List[EvidenceRow] = []
    evidence_narrative: str = ""
    evidence_footnote: str = ""
    evidence_cohort: str = "global"
    studio_id: str = "global"
    recommendation_rationale: str = ""
    affected_scene_ids: List[str] = []
    approved_option_id: str = ""
    decision_id: str = ""
    error: str = ""
    llm_mode: str = "gemini"  # "gemini" | "deterministic" (quota fallback)
    created_at: datetime = Field(default_factory=utcnow)

    def touch_stage(self, stage: str) -> None:
        if not any(s.stage == stage for s in self.stages):
            self.stages.append(StageEvent(stage=stage))

    def agent(self, key: str) -> AgentState:
        return self.agents[key]

    def agent_start(self, key: str, summary: str = "") -> None:
        a = self.agents[key]
        a.status = "running"
        a.started_at = utcnow()
        if summary:
            a.summary = summary

    def agent_complete(self, key: str, summary: str, detail: str = "") -> None:
        a = self.agents[key]
        a.status = "complete"
        a.finished_at = utcnow()
        if a.started_at:
            a.duration_ms = int((a.finished_at - a.started_at).total_seconds() * 1000)
        a.summary = summary
        if detail:
            a.detail = detail

    def agent_error(self, key: str, message: str) -> None:
        a = self.agents[key]
        a.status = "error"
        a.finished_at = utcnow()
        if a.started_at:
            a.duration_ms = int((a.finished_at - a.started_at).total_seconds() * 1000)
        a.summary = message


def new_case(report: DisruptionReport) -> CaseState:
    case = CaseState(
        case_id=short_id("case"),
        production_id=report.production_id,
        disruption=report,
        agents={k: AgentState(key=k, display_name=AGENT_DISPLAY[k]) for k in AGENT_KEYS},
    )
    case.touch_stage("DISRUPTION_REPORTED")
    case.touch_stage("CASE_CREATED")
    return case


class ScheduleImportJobResponse(BaseModel):
    job_id: str
    production_id: str
    filename: str
    file_size_bytes: int
    status: Literal["pending", "processing", "ready", "failed", "confirmed"]
    created_at: str
    preview: Optional[Dict[str, Any]] = None
    error: Optional[str] = None


class ScheduleImportConfirmResponse(BaseModel):
    success: bool
    production_id: str
    days_count: int = 0
    scenes_count: int = 0
    cast_count: int = 0
    locations_count: int = 0

