"""
Scoring helpers for soft objectives:
- maximize money (service fee)
- minimize distance traveled
- prefer higher skill match when multiple technicians qualify
"""

from dataclasses import dataclass

from ..models import RepairRequest, Technician


@dataclass
class ObjectiveWeights:
    revenue_weight: float = 0.5
    distance_weight: float = 0.5
    skill_weight: float = 0.25


def distance(technician: Technician, request: RepairRequest) -> float:
    return technician.location.distance_to(request.location)


def skill_match_strength(technician: Technician, request: RepairRequest) -> float:
    """
    Positive value means technician is stronger than minimum required levels.
    Assumes feasibility has already been validated.
    """
    if not request.required_skills:
        return 0.0
    total_excess = 0.0
    for skill, min_level in request.required_skills.items():
        total_excess += max(0, technician.skills.get(skill, 0) - min_level)
    return total_excess / len(request.required_skills)


def weighted_utility(
    technician: Technician,
    request: RepairRequest,
    weights: ObjectiveWeights = ObjectiveWeights(),
    distance_ref: float = 0.50,
    fee_ref: float = 400.0,
) -> float:
    """
    Higher is better.
    """
    dist_component = min(1.0, distance(technician, request) / max(0.001, distance_ref))
    revenue_component = min(1.0, request.service_fee / max(1.0, fee_ref))
    # skill strength is roughly excess levels. Normalize by 10 for a bounded term.
    skill_component = min(1.0, skill_match_strength(technician, request) / 10.0)

    return (
        weights.revenue_weight * revenue_component
        - weights.distance_weight * dist_component
        + weights.skill_weight * skill_component
    )


def explain_score(
    technician: Technician,
    request: RepairRequest,
    score: float,
) -> str:
    return (
        f"score={score:.3f}; fee={request.service_fee:.2f}, "
        f"distance={distance(technician, request):.3f}, "
        f"skill_excess={skill_match_strength(technician, request):.2f}"
    )
