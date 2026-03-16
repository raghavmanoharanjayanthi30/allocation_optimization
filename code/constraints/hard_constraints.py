"""
Hard constraints for field service assignment feasibility.
"""

from datetime import timedelta
from typing import Optional

from ..models import RepairRequest, Technician, TimeWindow


def has_min_available_hours(technician: Technician, min_hours_per_week: float = 40.0) -> bool:
    return technician.available_hours_per_week >= min_hours_per_week


def has_required_skill_levels(technician: Technician, request: RepairRequest) -> bool:
    for skill, min_level in request.required_skills.items():
        if technician.skills.get(skill, 0) < min_level:
            return False
    return True


def is_within_max_distance(technician: Technician, request: RepairRequest) -> bool:
    if technician.max_travel_distance is None:
        return True
    return technician.location.distance_to(request.location) <= technician.max_travel_distance


def _candidate_window(availability: TimeWindow, request_window: TimeWindow, duration_mins: float) -> Optional[TimeWindow]:
    start = max(availability.start, request_window.start)
    end_limit = min(availability.end, request_window.end)
    end = start + timedelta(minutes=duration_mins)
    if end <= end_limit:
        return TimeWindow(start=start, end=end)
    return None


def find_feasible_slot(
    technician: Technician,
    request: RepairRequest,
    existing_bookings: Optional[list[TimeWindow]] = None,
) -> Optional[TimeWindow]:
    bookings = existing_bookings or []
    for avail in technician.availability:
        candidate = _candidate_window(avail, request.time_window, request.estimated_duration)
        if candidate is None:
            continue
        if any(candidate.overlaps(booked) for booked in bookings):
            continue
        return candidate
    return None


def can_assign(
    technician: Technician,
    request: RepairRequest,
    existing_bookings: Optional[list[TimeWindow]] = None,
    min_hours_per_week: float = 40.0,
) -> tuple[bool, list[str], Optional[TimeWindow]]:
    """
    Return (is_feasible, reasons_if_not_feasible, slot_if_feasible).
    """
    reasons: list[str] = []
    if not has_min_available_hours(technician, min_hours_per_week=min_hours_per_week):
        reasons.append("available_hours_per_week_below_minimum")
    if not has_required_skill_levels(technician, request):
        reasons.append("missing_required_skill_or_level")
    if not is_within_max_distance(technician, request):
        reasons.append("distance_exceeds_technician_limit")
    slot = find_feasible_slot(technician, request, existing_bookings=existing_bookings)
    if slot is None:
        reasons.append("no_non_overlapping_slot_in_time_window")
    return (len(reasons) == 0, reasons, slot)


def sort_requests_for_allocation(requests: list[RepairRequest]) -> list[RepairRequest]:
    """
    Sequential allocation order:
    - Higher priority first
    - Then earlier deadline
    """
    return sorted(requests, key=lambda r: (-r.priority, r.time_window.end, r.id))
