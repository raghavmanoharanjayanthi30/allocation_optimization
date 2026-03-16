"""
Field Service Resource Allocation Engine — core types and data generation.
"""

from .data_generator import GLOBAL_SKILLS_POOL, generate_repair_requests, generate_technicians
from .models import Assignment, Location, RepairRequest, Technician, TimeWindow
from .optimization.greedy import greedy_assign
from .optimization.scheduler import Scheduler

__all__ = [
    "Assignment",
    "GLOBAL_SKILLS_POOL",
    "Location",
    "RepairRequest",
    "Technician",
    "TimeWindow",
    "generate_repair_requests",
    "generate_technicians",
    "greedy_assign",
    "Scheduler",
]
