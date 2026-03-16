"""
MILP optimizer (optional advanced approach, skeleton).

Why include:
- very expressive for constraints
- strong showcase of exact optimization modeling
"""

from typing import Optional

import numpy as np
from scipy.optimize import Bounds, LinearConstraint, milp

from ..constraints.hard_constraints import can_assign, sort_requests_for_allocation
from ..constraints.scoring import ObjectiveWeights, explain_score, weighted_utility
from ..models import Assignment, TimeWindow
from .types import OptimizationResult

UNASSIGNED_PENALTY = 0.60


def build_milp_model(
    technicians,
    jobs,
    weights: Optional[ObjectiveWeights] = None,
    min_hours_per_week: float = 40.0,
):
    """
    Build a compact MILP:
    - x[i,j] = 1 if request i assigned to technician j
    - y[i] = 1 if request i unassigned

    Constraints:
    - each request assigned once or marked unassigned
    - each technician handles at most one job (batch setting)
    """
    sorted_jobs = sort_requests_for_allocation(jobs)
    feasible: dict[tuple[int, int], tuple[float, TimeWindow]] = {}
    for i, req in enumerate(sorted_jobs):
        for j, tech in enumerate(technicians):
            ok, _reasons, slot = can_assign(tech, req, existing_bookings=[], min_hours_per_week=min_hours_per_week)
            if not ok or slot is None:
                continue
            feasible[(i, j)] = (weighted_utility(tech, req, weights=weights or ObjectiveWeights()), slot)

    x_keys = list(feasible.keys())
    n_x = len(x_keys)
    n_req = len(sorted_jobs)
    n_vars = n_x + n_req  # x vars + y vars

    # Minimize negative utility + unassigned penalties.
    c = np.zeros(n_vars, dtype=float)
    for k, key in enumerate(x_keys):
        c[k] = -feasible[key][0]
    for i in range(n_req):
        c[n_x + i] = UNASSIGNED_PENALTY

    constraints: list[LinearConstraint] = []

    # Each request: sum x(i,*) + y_i = 1
    for i in range(n_req):
        row = np.zeros(n_vars, dtype=float)
        for k, (ii, _j) in enumerate(x_keys):
            if ii == i:
                row[k] = 1.0
        row[n_x + i] = 1.0
        constraints.append(LinearConstraint(row, lb=1.0, ub=1.0))

    # Each technician: sum x(*,j) <= 1
    for j in range(len(technicians)):
        row = np.zeros(n_vars, dtype=float)
        for k, (_i, jj) in enumerate(x_keys):
            if jj == j:
                row[k] = 1.0
        constraints.append(LinearConstraint(row, lb=-np.inf, ub=1.0))

    integrality = np.ones(n_vars, dtype=int)
    bounds = Bounds(lb=np.zeros(n_vars), ub=np.ones(n_vars))
    return c, constraints, integrality, bounds, x_keys, feasible, sorted_jobs


def milp_assign(
    technicians,
    jobs,
    weights: Optional[ObjectiveWeights] = None,
    min_hours_per_week: float = 40.0,
) -> OptimizationResult:
    """
    MILP assignment implementation via scipy.optimize.milp.
    """
    if not jobs:
        return OptimizationResult(notes=["No jobs provided."])

    c, constraints, integrality, bounds, x_keys, feasible, sorted_jobs = build_milp_model(
        technicians,
        jobs,
        weights=weights,
        min_hours_per_week=min_hours_per_week,
    )
    result = milp(
        c=c,
        integrality=integrality,
        bounds=bounds,
        constraints=constraints,
    )
    if not result.success or result.x is None:
        raise RuntimeError(f"MILP solve failed: {result.message}")

    assignments: list[Assignment] = []
    unassigned: list[str] = []
    objective = 0.0
    n_x = len(x_keys)
    x_sol = result.x

    for i, req in enumerate(sorted_jobs):
        if x_sol[n_x + i] > 0.5:
            unassigned.append(req.id)
            continue
        chosen = None
        for k, (ii, j) in enumerate(x_keys):
            if ii == i and x_sol[k] > 0.5:
                chosen = j
                break
        if chosen is None:
            unassigned.append(req.id)
            continue
        tech = technicians[chosen]
        utility, slot = feasible[(i, chosen)]
        objective += utility
        assignments.append(
            Assignment(
                technician_id=tech.id,
                request_id=req.id,
                score=utility,
                explanation=f"MILP pick: {explain_score(tech, req, utility)}",
                estimated_travel_distance=tech.location.distance_to(req.location),
                expected_revenue=req.service_fee,
                slot_start=slot.start,
            )
        )

    return OptimizationResult(
        assignments=assignments,
        unassigned_request_ids=unassigned,
        objective_value=objective,
        notes=["MILP batch assignment completed."],
    )

