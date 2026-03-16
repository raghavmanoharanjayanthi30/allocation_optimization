"""
Greedy assignment approach.

Idea:
- process requests in priority order
- pick the highest-score feasible candidate at each step
- update bookings to prevent overlap
"""

from collections import defaultdict
from typing import Optional

from ..constraints.scoring import ObjectiveWeights
from ..constraints.hard_constraints import sort_requests_for_allocation
from ..models import Assignment, RepairRequest, Technician, TimeWindow
from .candidate_generation import generate_candidates
from .types import OptimizationResult


def greedy_assign(
    technicians: list[Technician],
    requests: list[RepairRequest],
    weights: Optional[ObjectiveWeights] = None,
    min_hours_per_week: float = 40.0,
) -> OptimizationResult:
    """
    Greedy baseline optimizer.

    Why useful:
    - very fast
    - easy to explain
    - strong baseline for comparisons
    """
    sorted_requests = sort_requests_for_allocation(requests)
    bookings: dict[str, list[TimeWindow]] = defaultdict(list)
    assignments: list[Assignment] = []
    assigned_request_ids: set[str] = set()

    for request in sorted_requests:
        candidates = generate_candidates(
            technicians=technicians,
            requests=[request],
            bookings_by_technician=bookings,
            weights=weights,
            min_hours_per_week=min_hours_per_week,
        )
        if not candidates:
            continue

        # Highest utility candidate wins for this request.
        best = max(candidates, key=lambda c: c.score)
        bookings[best.technician.id].append(best.slot)
        assigned_request_ids.add(request.id)
        assignments.append(
            Assignment(
                technician_id=best.technician.id,
                request_id=request.id,
                score=best.score,
                explanation=f"Greedy pick: {best.reason}",
                estimated_travel_distance=best.technician.location.distance_to(request.location),
                expected_revenue=request.service_fee,
                slot_start=best.slot.start,
            )
        )

    unassigned = [r.id for r in sorted_requests if r.id not in assigned_request_ids]
    objective = sum(a.score or 0.0 for a in assignments)
    return OptimizationResult(
        assignments=assignments,
        unassigned_request_ids=unassigned,
        objective_value=objective,
        notes=["Greedy sequential assignment completed."],
    )

