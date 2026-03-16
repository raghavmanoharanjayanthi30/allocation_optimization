"""
Service layer for backend routes.

Keeping logic here keeps endpoints small and easy to read.
"""

import json
import os
import re
import uuid
from collections import Counter
from typing import Any, Optional, TypedDict

from langgraph.graph import END, StateGraph  # type: ignore[reportMissingImports]

from code.constraints.hard_constraints import can_assign
from code.constraints.scoring import ObjectiveWeights
from code.data_generator import generate_repair_requests, generate_technicians
from code.models import RepairRequest, Technician
from code.optimization.scheduler import Scheduler

from .schemas import (
    AgentChatRequest,
    AgentChatResponse,
    AgentState,
    AgentToolCall,
    AllocateRequest,
    AllocateResponse,
    GenerateScenarioRequest,
    GenerateScenarioResponse,
)

# In-memory session store for agent state (process-local).
# This is enough for local development. For production, replace with Redis/DB.
AGENT_SESSION_STORE: dict[str, AgentState] = {}
AGENT_METHODS = ["greedy", "hungarian", "min_cost_flow", "milp"]


def generate_scenario(payload: GenerateScenarioRequest) -> GenerateScenarioResponse:
    technicians = generate_technicians(
        count=payload.technician_count,
        seed=payload.technician_seed,
    )
    jobs = generate_repair_requests(
        count=payload.job_count,
        seed=payload.job_seed,
        priority_distribution=payload.priority_distribution,
    )
    return GenerateScenarioResponse(technicians=technicians, jobs=jobs)


def run_allocation(payload: AllocateRequest) -> AllocateResponse:
    scheduler = Scheduler()
    method = payload.method
    objective_weights = payload.objective_weights or {}
    hard_constraints = payload.hard_constraints or {}
    weights = ObjectiveWeights(
        revenue_weight=float(objective_weights.get("revenue_weight", 0.5)),
        distance_weight=float(objective_weights.get("distance_weight", 0.5)),
        skill_weight=float(objective_weights.get("skill_weight", 0.25)),
    )
    min_hours_per_week = float(hard_constraints.get("min_hours_per_week", 40.0))
    max_travel_distance_cap = hard_constraints.get("max_travel_distance")
    technicians = payload.technicians
    if max_travel_distance_cap is not None:
        cap = float(max_travel_distance_cap)
        technicians = [t.copy(deep=True) for t in payload.technicians]
        for technician in technicians:
            if technician.max_travel_distance is None:
                technician.max_travel_distance = cap
            else:
                technician.max_travel_distance = min(float(technician.max_travel_distance), cap)

    # Simple dispatcher; later this can become config-driven.
    if method == "greedy":
        result = scheduler.greedy_assign(
            technicians,
            payload.jobs,
            weights=weights,
            min_hours_per_week=min_hours_per_week,
        )
    elif method == "hungarian":
        result = scheduler.hungarian_assign(
            technicians,
            payload.jobs,
            weights=weights,
            min_hours_per_week=min_hours_per_week,
        )
    elif method == "min_cost_flow":
        result = scheduler.min_cost_flow_assign(
            technicians,
            payload.jobs,
            weights=weights,
            min_hours_per_week=min_hours_per_week,
        )
    elif method == "milp":
        result = scheduler.milp_assign(
            technicians,
            payload.jobs,
            weights=weights,
            min_hours_per_week=min_hours_per_week,
        )
    else:
        # Should not happen because of Literal typing.
        raise ValueError(f"Unsupported method: {method}")

    return AllocateResponse(
        method=method,
        assignments=result.assignments,
        unassigned_job_ids=result.unassigned_request_ids,
        objective_value=result.objective_value,
        notes=result.notes,
    )


def _run_single_method(
    method: str,
    technicians,
    jobs,
    objective_weights: Optional[dict[str, float]] = None,
    hard_constraints: Optional[dict[str, float]] = None,
) -> AllocateResponse:
    request = AllocateRequest(
        method=method,
        technicians=technicians,
        jobs=jobs,
        objective_weights=objective_weights,
        hard_constraints=hard_constraints,
    )
    return run_allocation(request)


def _extract_first_int(text: str) -> Optional[int]:
    m = re.search(r"(\d+)", text)
    if not m:
        return None
    return int(m.group(1))


def _explain_assigned(
    state: AgentState,
    method: Optional[str],
    request_id: Optional[str],
    technician_id: Optional[str],
    top_k: Optional[int],
) -> str:
    methods_to_explain = _methods_to_explain(state, method)
    if not methods_to_explain:
        return "No optimization results available yet. Run a method first (or run all methods)."

    lines: list[str] = []
    for selected_method in methods_to_explain:
        data = state.comparison_results.get(selected_method)
        if not data:
            continue
        assignments = data.assignments or []
        if request_id:
            matches = [a for a in assignments if a.request_id == request_id]
        elif technician_id:
            matches = [a for a in assignments if a.technician_id == technician_id]
        else:
            matches = assignments if top_k is None else assignments[:top_k]

        lines.append(
            f"Assigned explanation for method '{selected_method}' "
            f"(assigned={len(assignments)}, unassigned={len(data.unassigned_job_ids or [])}):"
        )
        if not matches:
            lines.append("- No matching assignments found for that filter.")
            continue

        selected_matches = matches if top_k is None else matches[:top_k]
        for a in selected_matches:
            lines.append(
                f"- request {a.request_id} -> technician {a.technician_id}; "
                f"reason: {a.explanation or 'feasible and selected by optimizer'}"
            )
    return "\n".join(lines)


def _methods_to_explain(state: AgentState, method: Optional[str]) -> list[str]:
    if method == "all":
        return sorted(state.comparison_results.keys())
    if method:
        return [method]
    if state.comparison_results:
        return sorted(state.comparison_results.keys())
    if state.selected_method:
        return [state.selected_method]
    if state.method:
        return [state.method]
    return []


def _reason_label(reason_code: str) -> str:
    mapping = {
        "available_hours_per_week_below_minimum": "minimum weekly hours",
        "missing_required_skill_or_level": "skill/level mismatch",
        "distance_exceeds_technician_limit": "distance limit",
        "no_non_overlapping_slot_in_time_window": "time-window/overlap",
    }
    return mapping.get(reason_code, reason_code)


def _diagnose_unassigned_request(state: AgentState, request_id: str) -> str:
    request = next((job for job in state.jobs if job.id == request_id), None)
    if request is None:
        return f"- {request_id}: not found in current scenario."

    reason_counter: Counter[str] = Counter()
    combo_counter: Counter[str] = Counter()
    feasible_technicians = 0
    for technician in state.technicians:
        is_feasible, reasons, _slot = can_assign(technician, request, existing_bookings=None)
        if is_feasible:
            feasible_technicians += 1
            continue
        unique_reasons = sorted(set(reasons))
        for reason in unique_reasons:
            reason_counter[reason] += 1
        combo_counter[" + ".join(_reason_label(r) for r in unique_reasons)] += 1

    if feasible_technicians > 0:
        return (
            f"- {request_id}: has {feasible_technicians} technically feasible technician(s); "
            "this is likely optimizer trade-off/capacity competition with other jobs."
        )

    if not reason_counter:
        return f"- {request_id}: no feasible technicians and no diagnosable reason."

    reason_breakdown = ", ".join(
        f"{_reason_label(reason)}={count}" for reason, count in reason_counter.most_common()
    )
    combo_breakdown = ", ".join(f"{combo} ({count})" for combo, count in combo_counter.most_common(3))
    return (
        f"- {request_id}: no feasible technician under hard constraints. "
        f"Reason counts across technicians: {reason_breakdown}. "
        f"Most common combinations: {combo_breakdown}."
    )


def _explain_unassigned(state: AgentState, method: Optional[str], top_k: int) -> str:
    methods_to_explain = _methods_to_explain(state, method)
    if not methods_to_explain:
        return "No optimization results available yet. Run a method first (or run all methods)."

    lines: list[str] = []
    for selected_method in methods_to_explain:
        data = state.comparison_results.get(selected_method)
        if not data:
            continue
        unassigned = data.unassigned_job_ids or []
        if not unassigned:
            lines.append(f"Unassigned explanation for method '{selected_method}': all jobs are assigned.")
            continue
        lines.append(
            f"Unassigned explanation for method '{selected_method}' "
            f"(showing up to {top_k} of {len(unassigned)}):"
        )
        for request_id in unassigned[:top_k]:
            lines.append(_diagnose_unassigned_request(state, request_id))
    return "\n".join(lines)


class AgentGraphState(TypedDict):
    message: str
    state: AgentState
    llm_api_key: Optional[str]
    llm_model: Optional[str]
    planned_actions: list[dict[str, Any]]
    actions: list[AgentToolCall]
    assistant_message: str


def _state_summary_for_planner(state: AgentState) -> dict[str, Any]:
    return {
        "method": state.method,
        "selected_method": state.selected_method,
        "technician_count": len(state.technicians),
        "job_count": len(state.jobs),
        "comparison_methods_available": sorted(list(state.comparison_results.keys())),
        "objective_weights": state.objective_weights,
        "hard_constraints": state.hard_constraints,
    }


def _sanitize_planned_actions(raw_actions: Any) -> list[dict[str, Any]]:
    if not isinstance(raw_actions, list):
        return []
    sanitized: list[dict[str, Any]] = []
    for action in raw_actions:
        if not isinstance(action, dict):
            continue
        tool_name = action.get("tool_name")
        arguments = action.get("arguments", {})
        if tool_name not in {
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
        }:
            continue
        if not isinstance(arguments, dict):
            arguments = {}
        sanitized.append({"tool_name": tool_name, "arguments": arguments})
    return sanitized


def _extract_generate_counts(message: str) -> Optional[tuple[int, int]]:
    lower = message.lower()
    technician_match = re.search(r"(\d+)\s*(workers?|techs?|technicians?)", lower)
    job_match = re.search(r"(\d+)\s*jobs?", lower)
    if technician_match and job_match:
        return (max(1, int(technician_match.group(1))), max(1, int(job_match.group(1))))

    nums = [int(x) for x in re.findall(r"\d+", lower)]
    if len(nums) >= 2:
        return (max(1, nums[0]), max(1, nums[1]))
    return None


def _extract_priority_distribution(message: str) -> Optional[dict[int, int]]:
    lower = message.lower()
    distribution: dict[int, int] = {}

    # Pattern: "2 jobs is 1", optionally preceded by "priority"
    for jobs_str, priority_str in re.findall(
        r"(?:priority\s*(?:of\s*)?)?(\d+)\s*jobs?\s*(?:is|=|at|with)?\s*(\d)",
        lower,
    ):
        jobs_count = int(jobs_str)
        priority = int(priority_str)
        if 1 <= priority <= 5 and jobs_count > 0:
            distribution[priority] = distribution.get(priority, 0) + jobs_count

    # Pattern: "priority 1 is 2 jobs" or "priority 1: 2 jobs"
    for priority_str, jobs_str in re.findall(
        r"priority\s*(\d)\s*(?:is|=|:)?\s*(\d+)\s*jobs?",
        lower,
    ):
        jobs_count = int(jobs_str)
        priority = int(priority_str)
        if 1 <= priority <= 5 and jobs_count > 0:
            distribution[priority] = distribution.get(priority, 0) + jobs_count

    return distribution or None


def _extract_weight_overrides(message: str) -> dict[str, float]:
    lower = message.lower()
    weights: dict[str, float] = {}
    patterns = {
        "revenue_weight": r"(?:revenue|fee|money)\s*(?:weight)?\s*(?:=|is|to)?\s*([0-9]*\.?[0-9]+)",
        "distance_weight": r"distance\s*(?:weight)?\s*(?:=|is|to)?\s*([0-9]*\.?[0-9]+)",
        "skill_weight": r"skill\s*(?:weight)?\s*(?:=|is|to)?\s*([0-9]*\.?[0-9]+)",
    }
    for key, pattern in patterns.items():
        match = re.search(pattern, lower)
        if match:
            weights[key] = float(match.group(1))
    return weights


def _extract_hard_constraint_overrides(message: str) -> dict[str, float]:
    lower = message.lower()
    hard: dict[str, float] = {}
    min_hours_match = re.search(
        r"(?:min(?:imum)?\s*(?:weekly\s*)?hours|hours\s*(?:threshold|min))\s*(?:=|is|to)?\s*([0-9]*\.?[0-9]+)",
        lower,
    )
    if min_hours_match:
        hard["min_hours_per_week"] = float(min_hours_match.group(1))
    max_distance_match = re.search(
        r"(?:max(?:imum)?\s*(?:travel\s*)?distance|distance\s*limit)\s*(?:=|is|to)?\s*([0-9]*\.?[0-9]+)",
        lower,
    )
    if max_distance_match:
        hard["max_travel_distance"] = float(max_distance_match.group(1))
    return hard


def _extract_requested_method(message: str) -> Optional[str]:
    lower = message.lower()
    if any(token in lower for token in ["all methods", "all optimizers", "across methods"]):
        return "all"
    method_aliases = {
        "greedy": ["greedy", "greedy sequential"],
        "hungarian": ["hungarian", "hungarian batch"],
        "min_cost_flow": ["min_cost_flow", "min cost flow", "min-cost flow", "min cost", "flow scheduler"],
        "milp": ["milp", "mixed integer", "mixed-integer", "linear programming"],
    }
    for method_name, aliases in method_aliases.items():
        if any(alias in lower for alias in aliases):
            return method_name
    return None


def _extract_top_k(message: str) -> Optional[int]:
    lower = message.lower()
    match = re.search(r"(?:top|first|show)\s*(\d+)", lower)
    if not match:
        return None
    return max(1, int(match.group(1)))


def _summarize_results(results_by_method: dict[str, AllocateResponse]) -> str:
    if not results_by_method:
        return "No optimization results available."
    lines = []
    for method in sorted(results_by_method.keys()):
        result = results_by_method[method]
        assigned = len(result.assignments or [])
        unassigned = len(result.unassigned_job_ids or [])
        lines.append(f"- {method}: assigned={assigned}, unassigned={unassigned}, objective={result.objective_value:.3f}")
    return "\n".join(lines)


def _normalize_planned_actions(message: str, planned: list[dict[str, Any]]) -> list[dict[str, Any]]:
    counts = _extract_generate_counts(message)
    priority_distribution = _extract_priority_distribution(message)
    weight_overrides = _extract_weight_overrides(message)
    hard_overrides = _extract_hard_constraint_overrides(message)
    requested_method = _extract_requested_method(message)
    top_k = _extract_top_k(message)
    normalized: list[dict[str, Any]] = []
    for action in planned:
        if not isinstance(action, dict):
            continue
        tool_name = action.get("tool_name")
        arguments = action.get("arguments", {})
        if not isinstance(arguments, dict):
            arguments = {}
        if tool_name == "generate_scenario":
            if counts is not None:
                arguments["technician_count"], arguments["job_count"] = counts
            else:
                arguments["technician_count"] = int(arguments.get("technician_count", 12))
                arguments["job_count"] = int(arguments.get("job_count", 10))
            if priority_distribution is not None:
                arguments["priority_distribution"] = priority_distribution
        elif tool_name == "set_weights" and weight_overrides:
            arguments.update(weight_overrides)
        elif tool_name == "set_hard_constraints" and hard_overrides:
            arguments.update(hard_overrides)
        elif tool_name in {"explain_assigned", "explain_unassigned", "diagnose_request"}:
            if requested_method is not None and arguments.get("method") is None:
                arguments["method"] = requested_method
            if top_k is not None and arguments.get("top_k") is None:
                arguments["top_k"] = top_k
        if tool_name in {"set_method", "run_single", "explain_assigned", "explain_unassigned", "diagnose_request"}:
            method_arg = arguments.get("method")
            if isinstance(method_arg, str):
                normalized_method = _extract_requested_method(method_arg)
                if normalized_method is not None:
                    arguments["method"] = normalized_method
        normalized.append({"tool_name": tool_name, "arguments": arguments})
    return normalized


def _llm_plan_actions(
    message: str,
    state: AgentState,
    llm_api_key: Optional[str],
    llm_model: Optional[str],
) -> list[dict[str, Any]]:
    api_key = llm_api_key or os.getenv("OPENAI_API_KEY")
    if not api_key:
        return []
    try:
        from openai import OpenAI  # type: ignore
    except Exception:
        return []

    client = OpenAI(api_key=api_key)
    model = llm_model or os.getenv("AGENT_LLM_MODEL", "gpt-4o-mini")
    prompt = {
        "task": "Plan tool calls for a field-service optimization assistant.",
        "must_return_json_only": True,
        "required_shape": {
            "tool_calls": [
                {"tool_name": "generate_scenario|set_method|run_single|run_compare|explain_assigned|explain_unassigned|set_weights|set_hard_constraints|what_if|diagnose_request|regenerate_until_target|export_scenario|import_scenario", "arguments": {}}
            ]
        },
        "rules": [
            "Return only tool calls, ordered.",
            "Use only allowed tools.",
            "If user asks to explain assignments and no method selected, use selected_method or method from state.",
            "If user asks to run all methods, include run_compare.",
            "If user asks to run a specific method, include set_method then run_single.",
            "If user asks to generate N workers/jobs, include generate_scenario with counts.",
            "If user specifies job priority split (for example, 2 jobs priority 1, 2 jobs priority 2), include priority_distribution in generate_scenario arguments.",
            "If user asks to change objective weights, use set_weights.",
            "If user asks to tune hard constraints, use set_hard_constraints.",
            "Use diagnose_request for detailed per-request diagnostics.",
            "Use regenerate_until_target to search scenarios meeting assignment-rate goals.",
            "Use export_scenario/import_scenario for scenario persistence tasks.",
            "Keep arguments minimal and valid.",
        ],
        "state_summary": _state_summary_for_planner(state),
        "user_message": message,
    }
    resp = client.chat.completions.create(
        model=model,
        temperature=0.0,
        response_format={"type": "json_object"},
        messages=[
            {"role": "system", "content": "You are a planning engine that outputs strict JSON only."},
            {"role": "user", "content": json.dumps(prompt)},
        ],
    )
    content = (resp.choices[0].message.content or "").strip()
    if not content:
        return []
    try:
        parsed = json.loads(content)
    except Exception:
        return []
    return _sanitize_planned_actions(parsed.get("tool_calls", []))


def _plan_actions(message: str, state: AgentState) -> list[dict[str, Any]]:
    """
    Planner node output:
    ordered tool calls with arguments.

    This keeps a clear seam for future LLM-based planning.
    """
    lower = message.lower()
    planned: list[dict[str, Any]] = []

    # generate_scenario
    if "generate" in lower or "random" in lower or "scenario" in lower:
        count = _extract_first_int(lower)
        tech_count = count or 12
        nums = [int(x) for x in re.findall(r"\d+", lower)]
        if len(nums) >= 2:
            tech_count = nums[0]
            job_count = nums[1]
        else:
            job_count = max(8, tech_count)
        planned.append(
            {
                "tool_name": "generate_scenario",
                "arguments": {
                    "technician_count": max(1, tech_count),
                    "job_count": max(1, job_count),
                },
            }
        )

    # set_method
    explicit_method = _extract_requested_method(lower)
    if explicit_method and explicit_method in AGENT_METHODS:
        planned.append(
            {
                "tool_name": "set_method",
                "arguments": {"method": explicit_method},
            }
        )

    # run_compare
    if "run all" in lower or "compare" in lower or "all methods" in lower:
        planned.append({"tool_name": "run_compare", "arguments": {}})

    # run_single
    if "run" in lower and not any(k in lower for k in ["run all", "all methods", "compare"]):
        planned.append(
            {
                "tool_name": "run_single",
                "arguments": {"method": explicit_method if explicit_method in AGENT_METHODS else state.method},
            }
        )

    # explain_assigned
    if ("explain" in lower and "assigned" in lower) or ("why" in lower and "assigned" in lower):
        request_id_match = re.search(r"r\d{3}", lower)
        technician_id_match = re.search(r"t\d{3}", lower)
        request_id = request_id_match.group(0).upper() if request_id_match else None
        technician_id = technician_id_match.group(0).upper() if technician_id_match else None
        explicit_method = _extract_requested_method(lower)
        top_k = _extract_top_k(lower)
        planned.append(
            {
                "tool_name": "explain_assigned",
                "arguments": {
                    "method": explicit_method,
                    "request_id": request_id,
                    "technician_id": technician_id,
                    **({"top_k": top_k} if top_k is not None else {}),
                },
            }
        )

    # explain_unassigned
    if ("explain" in lower and "unassigned" in lower) or ("why" in lower and "unassigned" in lower):
        explicit_method = _extract_requested_method(lower)
        top_k = _extract_top_k(lower)
        planned.append(
            {
                "tool_name": "explain_unassigned",
                "arguments": {"method": explicit_method, **({"top_k": top_k} if top_k is not None else {})},
            }
        )

    # set_weights
    if "weight" in lower and any(x in lower for x in ["revenue", "fee", "distance", "skill"]):
        planned.append(
            {
                "tool_name": "set_weights",
                "arguments": _extract_weight_overrides(lower),
            }
        )

    # set_hard_constraints
    if any(x in lower for x in ["hard constraint", "constraint"]) and any(
        x in lower for x in ["hours", "distance"]
    ):
        planned.append(
            {
                "tool_name": "set_hard_constraints",
                "arguments": _extract_hard_constraint_overrides(lower),
            }
        )

    # what_if
    if "what if" in lower:
        planned.append({"tool_name": "what_if", "arguments": {"run_compare": True}})

    # diagnose_request
    if "diagnose" in lower and ("request" in lower or re.search(r"r\d{3}", lower)):
        req_match = re.search(r"r\d{3}", lower)
        planned.append(
            {
                "tool_name": "diagnose_request",
                "arguments": {"request_id": req_match.group(0).upper() if req_match else None},
            }
        )

    # regenerate_until_target
    if "regenerate" in lower and ("target" in lower or "assignment rate" in lower):
        rate_match = re.search(r"([0-9]*\.?[0-9]+)\s*(?:assignment rate|rate|%)", lower)
        target_rate = 0.8
        if rate_match:
            raw = float(rate_match.group(1))
            target_rate = raw / 100.0 if raw > 1.0 else raw
        planned.append(
            {
                "tool_name": "regenerate_until_target",
                "arguments": {"target_assignment_rate": target_rate, "max_attempts": 20},
            }
        )

    # export/import scenario
    if "export scenario" in lower:
        planned.append({"tool_name": "export_scenario", "arguments": {}})
    if "import scenario" in lower:
        planned.append({"tool_name": "import_scenario", "arguments": {}})

    if not planned:
        planned.append(
            {
                "tool_name": "run_single",
                "arguments": {"method": state.method},
                "force_error": True,
            }
        )
    return planned


def _execute_tool_action(state: AgentState, action: dict[str, Any]) -> AgentToolCall:
    tool_name = action.get("tool_name")
    arguments = action.get("arguments", {})

    if action.get("force_error"):
        return AgentToolCall(
            tool_name="run_single",
            arguments={"method": state.method},
            status="error",
            message=(
                "I could not map your request to a tool. "
                "Try: 'generate 12 workers 10 jobs', 'run all methods', "
                "'run milp', 'explain unassigned', 'set revenue weight to 0.7'."
            ),
        )

    if tool_name == "generate_scenario":
        scenario = generate_scenario(
            GenerateScenarioRequest(
                technician_count=arguments.get("technician_count", 12),
                job_count=arguments.get("job_count", 10),
                technician_seed=arguments.get("technician_seed"),
                job_seed=arguments.get("job_seed"),
                priority_distribution=arguments.get("priority_distribution"),
            )
        )
        state.technicians = scenario.technicians
        state.jobs = scenario.jobs
        state.comparison_results = {}
        state.selected_method = None
        return AgentToolCall(
            tool_name="generate_scenario",
            arguments=arguments,
            status="ok",
            message=f"Generated scenario with {len(state.technicians)} technicians and {len(state.jobs)} jobs.",
        )

    if tool_name == "set_method":
        method_name = arguments.get("method")
        if method_name not in AGENT_METHODS:
            return AgentToolCall(
                tool_name="set_method",
                arguments=arguments,
                status="error",
                message=f"Unsupported method '{method_name}'.",
            )
        state.method = method_name  # type: ignore[assignment]
        return AgentToolCall(
            tool_name="set_method",
            arguments=arguments,
            status="ok",
            message=f"Set active method to {method_name}.",
        )

    if tool_name == "run_compare":
        if not state.technicians or not state.jobs:
            return AgentToolCall(
                tool_name="run_compare",
                arguments=arguments,
                status="error",
                message="No technicians/jobs in state.",
            )
        for method_name in AGENT_METHODS:
            result = _run_single_method(
                method_name,
                state.technicians,
                state.jobs,
                objective_weights=state.objective_weights,
                hard_constraints=state.hard_constraints,
            )
            state.comparison_results[method_name] = result
        state.selected_method = "greedy"
        return AgentToolCall(
            tool_name="run_compare",
            arguments=arguments,
            status="ok",
            message="Ran all methods and updated comparison.",
        )

    if tool_name == "run_single":
        if not state.technicians or not state.jobs:
            return AgentToolCall(
                tool_name="run_single",
                arguments=arguments,
                status="error",
                message="No technicians/jobs in state.",
            )
        method_name = arguments.get("method") or state.method
        result = _run_single_method(
            method_name,
            state.technicians,
            state.jobs,
            objective_weights=state.objective_weights,
            hard_constraints=state.hard_constraints,
        )
        state.comparison_results[method_name] = result
        state.selected_method = method_name
        return AgentToolCall(
            tool_name="run_single",
            arguments={"method": method_name},
            status="ok",
            message=f"Ran method {method_name}.",
        )

    if tool_name == "explain_assigned":
        method_name = arguments.get("method")
        top_k_value = arguments.get("top_k")
        text = _explain_assigned(
            state=state,
            method=method_name,
            request_id=arguments.get("request_id"),
            technician_id=arguments.get("technician_id"),
            top_k=int(top_k_value) if top_k_value is not None else None,
        )
        return AgentToolCall(
            tool_name="explain_assigned",
            arguments=arguments,
            status="ok",
            message=text,
        )

    if tool_name == "explain_unassigned":
        method_name = arguments.get("method")
        text = _explain_unassigned(state, method_name, int(arguments.get("top_k", 10)))
        return AgentToolCall(
            tool_name="explain_unassigned",
            arguments=arguments,
            status="ok",
            message=text,
        )

    if tool_name == "set_weights":
        next_weights = dict(state.objective_weights)
        for key in ["revenue_weight", "distance_weight", "skill_weight"]:
            if key in arguments and arguments.get(key) is not None:
                next_weights[key] = float(arguments[key])
        state.objective_weights = next_weights
        return AgentToolCall(
            tool_name="set_weights",
            arguments=arguments,
            status="ok",
            message=(
                "Updated objective weights: "
                f"revenue_weight={state.objective_weights.get('revenue_weight', 0.5)}, "
                f"distance_weight={state.objective_weights.get('distance_weight', 0.5)}, "
                f"skill_weight={state.objective_weights.get('skill_weight', 0.25)}."
            ),
        )

    if tool_name == "set_hard_constraints":
        next_constraints = dict(state.hard_constraints)
        if arguments.get("min_hours_per_week") is not None:
            next_constraints["min_hours_per_week"] = float(arguments["min_hours_per_week"])
        if arguments.get("max_travel_distance") is not None:
            next_constraints["max_travel_distance"] = float(arguments["max_travel_distance"])
        state.hard_constraints = next_constraints
        return AgentToolCall(
            tool_name="set_hard_constraints",
            arguments=arguments,
            status="ok",
            message=(
                "Updated hard constraints: "
                f"min_hours_per_week={state.hard_constraints.get('min_hours_per_week', 40.0)}, "
                f"max_travel_distance={state.hard_constraints.get('max_travel_distance', 'per-technician defaults')}."
            ),
        )

    if tool_name == "what_if":
        if not state.technicians or not state.jobs:
            return AgentToolCall(
                tool_name="what_if",
                arguments=arguments,
                status="error",
                message="No technicians/jobs in state.",
            )
        sandbox = state.copy(deep=True)
        if isinstance(arguments.get("weights"), dict):
            for key in ["revenue_weight", "distance_weight", "skill_weight"]:
                if key in arguments["weights"]:
                    sandbox.objective_weights[key] = float(arguments["weights"][key])
        if isinstance(arguments.get("hard_constraints"), dict):
            if "min_hours_per_week" in arguments["hard_constraints"]:
                sandbox.hard_constraints["min_hours_per_week"] = float(arguments["hard_constraints"]["min_hours_per_week"])
            if "max_travel_distance" in arguments["hard_constraints"]:
                sandbox.hard_constraints["max_travel_distance"] = float(arguments["hard_constraints"]["max_travel_distance"])
        run_compare = bool(arguments.get("run_compare", True))
        if run_compare:
            sandbox.comparison_results = {}
            for method_name in AGENT_METHODS:
                sandbox.comparison_results[method_name] = _run_single_method(
                    method_name,
                    sandbox.technicians,
                    sandbox.jobs,
                    objective_weights=sandbox.objective_weights,
                    hard_constraints=sandbox.hard_constraints,
                )
        else:
            method_name = arguments.get("method") or sandbox.selected_method or sandbox.method
            sandbox.comparison_results[method_name] = _run_single_method(
                method_name,
                sandbox.technicians,
                sandbox.jobs,
                objective_weights=sandbox.objective_weights,
                hard_constraints=sandbox.hard_constraints,
            )
        if bool(arguments.get("commit", False)):
            state.objective_weights = sandbox.objective_weights
            state.hard_constraints = sandbox.hard_constraints
            state.comparison_results = sandbox.comparison_results
            state.selected_method = sandbox.selected_method
            message_prefix = "What-if executed and committed.\n"
        else:
            message_prefix = "What-if executed in sandbox (not committed).\n"
        return AgentToolCall(
            tool_name="what_if",
            arguments=arguments,
            status="ok",
            message=message_prefix + _summarize_results(sandbox.comparison_results),
        )

    if tool_name == "diagnose_request":
        request_id = (arguments.get("request_id") or "").upper()
        if not request_id:
            return AgentToolCall(
                tool_name="diagnose_request",
                arguments=arguments,
                status="error",
                message="Missing request_id (example: R005).",
            )
        method_name = arguments.get("method")
        methods = _methods_to_explain(state, method_name)
        if not methods:
            return AgentToolCall(
                tool_name="diagnose_request",
                arguments=arguments,
                status="error",
                message="No optimization results available to diagnose.",
            )
        lines = [f"Diagnostic for request {request_id}:"]
        for m in methods:
            data = state.comparison_results.get(m)
            if not data:
                continue
            assigned = next((a for a in (data.assignments or []) if a.request_id == request_id), None)
            if assigned:
                lines.append(
                    f"- {m}: assigned to {assigned.technician_id}; reason: "
                    f"{assigned.explanation or 'selected by optimizer'}"
                )
            elif request_id in (data.unassigned_job_ids or []):
                lines.append(f"- {m}: unassigned.")
                lines.append(_diagnose_unassigned_request(state, request_id))
            else:
                lines.append(f"- {m}: request not present in this result set.")
        return AgentToolCall(
            tool_name="diagnose_request",
            arguments=arguments,
            status="ok",
            message="\n".join(lines),
        )

    if tool_name == "regenerate_until_target":
        target_rate = float(arguments.get("target_assignment_rate", 0.8))
        target_rate = min(max(target_rate, 0.0), 1.0)
        max_attempts = max(1, int(arguments.get("max_attempts", 20)))
        tech_count = max(1, int(arguments.get("technician_count", len(state.technicians) or 12)))
        job_count = max(1, int(arguments.get("job_count", len(state.jobs) or 10)))
        method_name = arguments.get("method") or state.selected_method or state.method
        best_rate = -1.0
        best_result: Optional[AllocateResponse] = None
        best_state_snapshot: Optional[tuple[list[Any], list[Any]]] = None
        for _attempt in range(max_attempts):
            scenario = generate_scenario(
                GenerateScenarioRequest(technician_count=tech_count, job_count=job_count)
            )
            result = _run_single_method(
                method_name,
                scenario.technicians,
                scenario.jobs,
                objective_weights=state.objective_weights,
                hard_constraints=state.hard_constraints,
            )
            assigned = len(result.assignments or [])
            rate = assigned / float(max(1, len(scenario.jobs)))
            if rate > best_rate:
                best_rate = rate
                best_result = result
                best_state_snapshot = (scenario.technicians, scenario.jobs)
            if rate >= target_rate:
                break
        if best_state_snapshot is None or best_result is None:
            return AgentToolCall(
                tool_name="regenerate_until_target",
                arguments=arguments,
                status="error",
                message="Unable to generate/evaluate scenarios.",
            )
        state.technicians, state.jobs = best_state_snapshot
        state.comparison_results[method_name] = best_result
        state.selected_method = method_name
        state.method = method_name  # type: ignore[assignment]
        return AgentToolCall(
            tool_name="regenerate_until_target",
            arguments=arguments,
            status="ok",
            message=(
                f"Regenerated scenarios and selected best for method '{method_name}'. "
                f"Best assignment rate={best_rate:.2%} (target={target_rate:.2%})."
            ),
        )

    if tool_name == "export_scenario":
        payload = {
            "technicians": [t.dict() for t in state.technicians],
            "jobs": [j.dict() for j in state.jobs],
            "objective_weights": state.objective_weights,
            "hard_constraints": state.hard_constraints,
        }
        return AgentToolCall(
            tool_name="export_scenario",
            arguments=arguments,
            status="ok",
            message=json.dumps(payload),
        )

    if tool_name == "import_scenario":
        raw = arguments.get("scenario_json")
        if not isinstance(raw, str) or not raw.strip():
            return AgentToolCall(
                tool_name="import_scenario",
                arguments=arguments,
                status="error",
                message="Missing scenario_json string.",
            )
        try:
            parsed = json.loads(raw)
            state.technicians = [Technician(**item) for item in parsed.get("technicians", [])]
            state.jobs = [RepairRequest(**item) for item in parsed.get("jobs", [])]
            state.objective_weights = parsed.get("objective_weights", {}) or {}
            state.hard_constraints = parsed.get("hard_constraints", {}) or {}
            state.comparison_results = {}
            state.selected_method = None
            return AgentToolCall(
                tool_name="import_scenario",
                arguments=arguments,
                status="ok",
                message=(
                    f"Imported scenario with {len(state.technicians)} technicians and {len(state.jobs)} jobs."
                ),
            )
        except Exception as exc:
            return AgentToolCall(
                tool_name="import_scenario",
                arguments=arguments,
                status="error",
                message=f"Failed to import scenario JSON: {exc}",
            )

    return AgentToolCall(
        tool_name="run_single",
        arguments={"method": state.method},
        status="error",
        message=f"Unknown tool '{tool_name}'.",
    )


def _planner_node(graph_state: AgentGraphState) -> AgentGraphState:
    planned = _llm_plan_actions(
        message=graph_state["message"],
        state=graph_state["state"],
        llm_api_key=graph_state.get("llm_api_key"),
        llm_model=graph_state.get("llm_model"),
    )
    fallback_planned = _plan_actions(graph_state["message"], graph_state["state"])
    has_generate_request = any(x in graph_state["message"].lower() for x in ["generate", "random", "scenario"])
    if has_generate_request and not any(a.get("tool_name") == "generate_scenario" for a in planned):
        generate_fallback = next((a for a in fallback_planned if a.get("tool_name") == "generate_scenario"), None)
        if generate_fallback is not None:
            planned = [generate_fallback, *planned]
    if not planned:
        planned = fallback_planned
    planned = _normalize_planned_actions(graph_state["message"], planned)
    graph_state["planned_actions"] = planned
    return graph_state


def _executor_node(graph_state: AgentGraphState) -> AgentGraphState:
    state = graph_state["state"]
    executed: list[AgentToolCall] = []
    for action in graph_state.get("planned_actions", []):
        executed.append(_execute_tool_action(state, action))
    graph_state["actions"] = executed
    graph_state["assistant_message"] = "\n".join([f"- {a.message}" for a in executed])
    graph_state["state"] = state
    return graph_state


def _build_agent_graph():
    graph = StateGraph(AgentGraphState)
    graph.add_node("planner", _planner_node)
    graph.add_node("executor", _executor_node)
    graph.set_entry_point("planner")
    graph.add_edge("planner", "executor")
    graph.add_edge("executor", END)
    return graph.compile()


_AGENT_GRAPH = _build_agent_graph()


def run_agent_chat(payload: AgentChatRequest) -> AgentChatResponse:
    """
    Lightweight agent executor:
    - Parses user intent with simple rules
    - Executes only allowlisted tools
    - Returns updated state + human-readable summary
    """
    msg = (payload.message or "").strip()

    # Memory model:
    # - If session_id exists and no state passed, continue from stored server-side state.
    # - If state is passed, it becomes the state source for this turn.
    # - If neither exists, start from empty default state.
    session_id = payload.session_id or str(uuid.uuid4())
    if payload.state is not None:
        state = payload.state.copy(deep=True)
    elif session_id in AGENT_SESSION_STORE:
        state = AGENT_SESSION_STORE[session_id].copy(deep=True)
    else:
        state = AgentState()
    graph_input: AgentGraphState = {
        "message": msg,
        "state": state,
        "llm_api_key": payload.llm_api_key,
        "llm_model": payload.llm_model,
        "planned_actions": [],
        "actions": [],
        "assistant_message": "",
    }
    graph_output = _AGENT_GRAPH.invoke(graph_input)
    state = graph_output["state"]
    actions = graph_output.get("actions", [])
    assistant_message = graph_output.get("assistant_message", "")

    # Persist memory for next turn.
    AGENT_SESSION_STORE[session_id] = state.copy(deep=True)

    return AgentChatResponse(
        session_id=session_id,
        assistant_message=assistant_message,
        actions=actions,
        state=state,
    )
