"""
API request/response schemas.

This file keeps API contracts clear and typed.
"""

from typing import Any, Literal, Optional

from pydantic import BaseModel, Field

from code.models import Assignment, RepairRequest, Technician

MethodName = Literal["greedy", "hungarian", "min_cost_flow", "milp"]


class GenerateScenarioRequest(BaseModel):
    technician_count: int = Field(default=12, ge=1, le=200)
    job_count: int = Field(default=10, ge=1, le=500)
    technician_seed: Optional[int] = None
    job_seed: Optional[int] = None
    priority_distribution: Optional[dict[int, int]] = None


class GenerateScenarioResponse(BaseModel):
    technicians: list[Technician]
    jobs: list[RepairRequest]


class AllocateRequest(BaseModel):
    method: MethodName = "greedy"
    technicians: list[Technician]
    jobs: list[RepairRequest]
    objective_weights: Optional[dict[str, float]] = None
    hard_constraints: Optional[dict[str, float]] = None


class AllocateResponse(BaseModel):
    method: MethodName
    assignments: list[Assignment]
    unassigned_job_ids: list[str]
    objective_value: float
    notes: list[str]


ToolName = Literal[
    "generate_scenario",
    "set_method",
    "run_single",
    "run_compare",
    "explain_assigned",
    "explain_unassigned",
    "set_weights",
    "set_hard_constraints",
    "what_if",
    "diagnose_request",
    "regenerate_until_target",
    "export_scenario",
    "import_scenario",
]


class AgentToolCall(BaseModel):
    tool_name: ToolName
    arguments: dict[str, Any] = Field(default_factory=dict)
    status: Literal["ok", "error"] = "ok"
    message: str = ""


class AgentState(BaseModel):
    method: MethodName = "greedy"
    technicians: list[Technician] = Field(default_factory=list)
    jobs: list[RepairRequest] = Field(default_factory=list)
    comparison_results: dict[str, AllocateResponse] = Field(default_factory=dict)
    selected_method: Optional[MethodName] = None
    objective_weights: dict[str, float] = Field(default_factory=dict)
    hard_constraints: dict[str, float] = Field(default_factory=dict)


class AgentChatRequest(BaseModel):
    message: str
    session_id: Optional[str] = None
    state: Optional[AgentState] = None
    llm_api_key: Optional[str] = None
    llm_model: Optional[str] = None


class AgentChatResponse(BaseModel):
    session_id: str
    assistant_message: str
    actions: list[AgentToolCall] = Field(default_factory=list)
    state: AgentState
