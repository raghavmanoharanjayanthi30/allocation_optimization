"""
Shared lightweight types used across optimization approaches.
"""

from dataclasses import dataclass, field

from ..models import Assignment, RepairRequest, Technician, TimeWindow


@dataclass
class Candidate:
    """
    A feasible technician-request option before final optimization.
    """

    technician: Technician
    request: RepairRequest
    slot: TimeWindow
    score: float
    reason: str = ""


@dataclass
class OptimizationResult:
    """
    Generic result container for any optimizer.
    """

    assignments: list[Assignment] = field(default_factory=list)
    unassigned_request_ids: list[str] = field(default_factory=list)
    objective_value: float = 0.0
    notes: list[str] = field(default_factory=list)

