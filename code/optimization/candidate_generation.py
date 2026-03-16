"""
Candidate generation layer.

Purpose:
- shrink the optimization problem before running any solver
- only keep feasible technician-request pairs
"""

from collections import defaultdict
from typing import Optional

from ..constraints.hard_constraints import can_assign
from ..constraints.scoring import ObjectiveWeights, explain_score, weighted_utility
from ..models import RepairRequest, Technician, TimeWindow
from .types import Candidate


def generate_candidates(
    technicians: list[Technician],
    requests: list[RepairRequest],
    bookings_by_technician: Optional[dict[str, list[TimeWindow]]] = None,
    weights: Optional[ObjectiveWeights] = None,
    min_hours_per_week: float = 40.0,
) -> list[Candidate]:
    """
    Build feasible candidates for all technician-request pairs.

    Notes:
    - Hard constraints are enforced here.
    - This keeps later optimizers small and focused.
    """
    bookings_by_technician = bookings_by_technician or defaultdict(list)
    candidates: list[Candidate] = []

    for request in requests:
        for technician in technicians:
            is_feasible, _reasons, slot = can_assign(
                technician,
                request,
                existing_bookings=bookings_by_technician.get(technician.id, []),
                min_hours_per_week=min_hours_per_week,
            )
            if not is_feasible or slot is None:
                continue

            score = weighted_utility(technician, request, weights=weights or ObjectiveWeights())
            reason = explain_score(technician, request, score)
            candidates.append(
                Candidate(
                    technician=technician,
                    request=request,
                    slot=slot,
                    score=score,
                    reason=reason,
                )
            )

    return candidates

