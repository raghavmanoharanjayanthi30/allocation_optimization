"""
Scoring layer wrapper.

This file keeps a clear extension point for:
- hand-crafted weighted utility (current baseline)
- future ML-based scoring model
"""

from ..constraints.scoring import weighted_utility
from ..models import RepairRequest, Technician


def score_candidate(technician: Technician, request: RepairRequest) -> float:
    """
    Baseline scoring function.

    Swap this function later with a learned model if needed:
    - predicted success probability
    - expected completion time
    - expected customer satisfaction
    """
    return weighted_utility(technician, request)

