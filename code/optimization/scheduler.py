"""
Class-based scheduling interface.

This provides a stable surface for future agent tools:
- Scheduler.greedy_assign(...)
- Scheduler.hungarian_assign(...)
- Scheduler.milp_assign(...)
- Scheduler.min_cost_flow_assign(...)
"""

from ..models import RepairRequest, Technician
from ..constraints.scoring import ObjectiveWeights
from typing import Optional
from .greedy import greedy_assign as greedy_assign_impl
from .hungarian import hungarian_assign as hungarian_assign_impl
from .milp import milp_assign as milp_assign_impl
from .min_cost_flow import min_cost_flow_assign as min_cost_flow_assign_impl
from .types import OptimizationResult


class Scheduler:
    """Unified class entrypoint for assignment approaches."""

    def greedy_assign(
        self,
        technicians: list[Technician],
        jobs: list[RepairRequest],
        weights: Optional[ObjectiveWeights] = None,
        min_hours_per_week: float = 40.0,
    ) -> OptimizationResult:
        return greedy_assign_impl(
            technicians=technicians,
            requests=jobs,
            weights=weights or ObjectiveWeights(),
            min_hours_per_week=min_hours_per_week,
        )

    def hungarian_assign(
        self,
        technicians: list[Technician],
        jobs: list[RepairRequest],
        weights: Optional[ObjectiveWeights] = None,
        min_hours_per_week: float = 40.0,
    ) -> OptimizationResult:
        return hungarian_assign_impl(
            technicians=technicians,
            jobs=jobs,
            weights=weights or ObjectiveWeights(),
            min_hours_per_week=min_hours_per_week,
        )

    def milp_assign(
        self,
        technicians: list[Technician],
        jobs: list[RepairRequest],
        weights: Optional[ObjectiveWeights] = None,
        min_hours_per_week: float = 40.0,
    ) -> OptimizationResult:
        return milp_assign_impl(
            technicians=technicians,
            jobs=jobs,
            weights=weights or ObjectiveWeights(),
            min_hours_per_week=min_hours_per_week,
        )

    def min_cost_flow_assign(
        self,
        technicians: list[Technician],
        jobs: list[RepairRequest],
        weights: Optional[ObjectiveWeights] = None,
        min_hours_per_week: float = 40.0,
    ) -> OptimizationResult:
        return min_cost_flow_assign_impl(
            technicians=technicians,
            jobs=jobs,
            weights=weights or ObjectiveWeights(),
            min_hours_per_week=min_hours_per_week,
        )

