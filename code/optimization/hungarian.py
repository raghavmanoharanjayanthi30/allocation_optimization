"""
Hungarian batch optimizer (skeleton).

Key concept:
- Build a cost matrix over feasible technician-request pairs.
- Minimize total cost globally in one batch.
"""

from typing import Optional

from ..constraints.hard_constraints import can_assign, sort_requests_for_allocation
from ..constraints.scoring import ObjectiveWeights, explain_score, weighted_utility
from ..models import Assignment, RepairRequest, Technician, TimeWindow
from .types import OptimizationResult

UNASSIGNED_COST = 0.60
BIG_M = 10_000.0


def _build_hungarian_cost_matrix(
    technicians: list[Technician],
    jobs: list[RepairRequest],
    weights: Optional[ObjectiveWeights] = None,
    min_hours_per_week: float = 40.0,
) -> tuple[list[list[float]], dict[tuple[int, int], tuple[float, TimeWindow]], list[RepairRequest]]:
    """
    Build request x (technicians + dummy columns) matrix.

    Cost convention:
    - feasible real pair: cost = -utility
    - infeasible real pair: BIG_M
    - dummy column: UNASSIGNED_COST
    """
    sorted_jobs = sort_requests_for_allocation(jobs)
    n_req = len(sorted_jobs)
    n_tech = len(technicians)
    n_dummy = n_req  # allow any number of unassigned jobs
    total_cols = n_tech + n_dummy
    matrix = [[UNASSIGNED_COST for _ in range(total_cols)] for _ in range(n_req)]

    # Keep pair metadata for reconstruction.
    feasible_pairs: dict[tuple[int, int], tuple[float, TimeWindow]] = {}
    for i, req in enumerate(sorted_jobs):
        for j, tech in enumerate(technicians):
            feasible, _reasons, slot = can_assign(tech, req, existing_bookings=[], min_hours_per_week=min_hours_per_week)
            if not feasible or slot is None:
                matrix[i][j] = BIG_M
                continue
            utility = weighted_utility(tech, req, weights=weights or ObjectiveWeights())
            matrix[i][j] = -utility
            feasible_pairs[(i, j)] = (utility, slot)

    return matrix, feasible_pairs, sorted_jobs


def _solve_assignment(cost_matrix: list[list[float]]) -> tuple[list[int], list[int]]:
    """
    Solve linear assignment.
    """
    try:
        from scipy.optimize import linear_sum_assignment  # type: ignore

        import numpy as np  # type: ignore

        row_ind, col_ind = linear_sum_assignment(np.array(cost_matrix, dtype=float))
        return row_ind.tolist(), col_ind.tolist()
    except ImportError as exc:
        raise ImportError(
            "Hungarian assignment requires scipy (and numpy). "
            "Install with: pip install scipy numpy"
        ) from exc


def hungarian_assign(
    technicians,
    jobs,
    weights: Optional[ObjectiveWeights] = None,
    min_hours_per_week: float = 40.0,
) -> OptimizationResult:
    """
    Batch global optimizer using Hungarian assignment.

    Note:
    - one job per technician in this batch formulation
    - unassigned jobs handled via dummy columns
    """
    if not jobs:
        return OptimizationResult(notes=["No jobs provided."])

    cost_matrix, feasible_pairs, sorted_jobs = _build_hungarian_cost_matrix(
        technicians,
        jobs,
        weights=weights,
        min_hours_per_week=min_hours_per_week,
    )
    row_ind, col_ind = _solve_assignment(cost_matrix)

    assignments: list[Assignment] = []
    unassigned: list[str] = []
    objective_value = 0.0

    for i, c in zip(row_ind, col_ind):
        req = sorted_jobs[i]
        if c >= len(technicians):
            unassigned.append(req.id)
            continue
        pair_key = (i, c)
        if pair_key not in feasible_pairs:
            unassigned.append(req.id)
            continue
        tech = technicians[c]
        utility, slot = feasible_pairs[pair_key]
        objective_value += utility
        assignments.append(
            Assignment(
                technician_id=tech.id,
                request_id=req.id,
                score=utility,
                explanation=f"Hungarian pick: {explain_score(tech, req, utility)}",
                estimated_travel_distance=tech.location.distance_to(req.location),
                expected_revenue=req.service_fee,
                slot_start=slot.start,
            )
        )

    return OptimizationResult(
        assignments=assignments,
        unassigned_request_ids=unassigned,
        objective_value=objective_value,
        notes=["Hungarian batch assignment completed."],
    )

