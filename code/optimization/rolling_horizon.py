"""
Rolling-horizon orchestration (skeleton).

Purpose:
- periodically re-optimize as new jobs arrive
- keep near-term assignments locked to avoid churn
"""

from dataclasses import dataclass
from datetime import datetime, timedelta

from ..models import Assignment, RepairRequest, Technician
from .greedy import greedy_assign
from .types import OptimizationResult


@dataclass
class RollingHorizonConfig:
    replanning_interval_minutes: int = 30
    lock_horizon_minutes: int = 60


def split_locked_vs_reoptimizable(
    assignments: list[Assignment],
    now: datetime,
    lock_horizon_minutes: int,
) -> tuple[list[Assignment], list[Assignment]]:
    """
    Lock assignments that start soon, and allow later assignments to be re-optimized.
    """
    cutoff = now + timedelta(minutes=lock_horizon_minutes)
    locked: list[Assignment] = []
    reoptimizable: list[Assignment] = []
    for assignment in assignments:
        if assignment.slot_start is not None and assignment.slot_start <= cutoff:
            locked.append(assignment)
        else:
            reoptimizable.append(assignment)
    return locked, reoptimizable


def run_reoptimization_cycle(
    technicians: list[Technician],
    pending_requests: list[RepairRequest],
    existing_assignments: list[Assignment],
    now: datetime,
    config: RollingHorizonConfig = RollingHorizonConfig(),
) -> OptimizationResult:
    """
    Simple rolling-horizon sketch.

    Current behavior:
    - keep near-term assignments locked
    - re-run greedy on pending requests for demonstration

    Later:
    - choose optimizer dynamically (greedy/Hungarian/flow)
    - preserve booking state from locked assignments
    """
    locked, _reopt = split_locked_vs_reoptimizable(
        existing_assignments,
        now=now,
        lock_horizon_minutes=config.lock_horizon_minutes,
    )
    result = greedy_assign(technicians=technicians, requests=pending_requests)
    result.assignments = locked + result.assignments
    result.notes.append(
        f"Rolling horizon cycle at {now.isoformat()} with lock horizon {config.lock_horizon_minutes}m."
    )
    return result

