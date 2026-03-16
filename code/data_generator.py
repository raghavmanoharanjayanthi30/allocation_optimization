"""
Synthetic data generator for technicians and repair requests.

Uses a configurable seed for reproducibility. No external APIs required.
"""

import random
from datetime import datetime, timedelta
from typing import Optional

from .models import Location, RepairRequest, Technician, TimeWindow

# Global skill pool used for both technician skills and request requirements.
GLOBAL_SKILLS_POOL = [
    "HVAC",
    "Electrical",
    "Plumbing",
    "Appliances",
    "General",
    "Carpentry",
    "Locksmith",
    "Painting",
    "Flooring",
    "Roofing",
    "Landscaping",
    "Pest Control",
    "Safety Inspection",
    "Solar",
    "Smart Home",
]

DEFAULT_LAT_RANGE = (37.6, 37.8)
DEFAULT_LNG_RANGE = (-122.5, -122.2)
SHIFT_BLOCKS: list[tuple[int, int]] = [(8, 12), (12, 16), (16, 20)]


def _random_location(
    lat_range: tuple[float, float] = DEFAULT_LAT_RANGE,
    lng_range: tuple[float, float] = DEFAULT_LNG_RANGE,
    rng: Optional[random.Random] = None,
) -> Location:
    rng = rng or random.Random()
    return Location(lat=rng.uniform(*lat_range), lng=rng.uniform(*lng_range))


def _single_shift_window(
    date: datetime,
    start_hour: int,
    end_hour: int,
) -> TimeWindow:
    """
    Generate exactly one fixed shift window.
    """
    return TimeWindow(
        start=date.replace(hour=start_hour, minute=0, second=0, microsecond=0),
        end=date.replace(hour=end_hour, minute=0, second=0, microsecond=0),
    )


def _build_skill_levels(
    pool: list[str],
    min_skills: int,
    max_skills: int,
    min_level: int,
    max_level: int,
    rng: random.Random,
) -> dict[str, int]:
    min_count = max(1, min(min_skills, len(pool)))
    max_count = max(min_count, min(max_skills, len(pool)))
    num_skills = rng.randint(min_count, max_count)
    selected = rng.sample(pool, num_skills)
    return {skill: rng.randint(min_level, max_level) for skill in selected}


def generate_technicians(
    count: int = 10,
    skills_pool: Optional[list[str]] = None,
    seed: Optional[int] = None,
    base_date: Optional[datetime] = None,
    lat_range: tuple[float, float] = DEFAULT_LAT_RANGE,
    lng_range: tuple[float, float] = DEFAULT_LNG_RANGE,
) -> list[Technician]:
    """
    Generate technicians with location, skill levels, availability, and max distance.
    """
    pool = skills_pool or GLOBAL_SKILLS_POOL
    rng = random.Random(seed)
    base_date = base_date or datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
    technicians: list[Technician] = []

    for i in range(count):
        loc = _random_location(lat_range=lat_range, lng_range=lng_range, rng=rng)
        # Relaxed generation:
        # - more skills per technician
        # - generally higher technician skill levels
        skill_levels = _build_skill_levels(
            pool,
            min_skills=4,
            max_skills=8,
            min_level=3,
            max_level=10,
            rng=rng,
        )
        shift_start, shift_end = rng.choice(SHIFT_BLOCKS)
        # One call -> one window. Shift blocks are predefined and non-overlapping by design.
        availability = [_single_shift_window(base_date, start_hour=shift_start, end_hour=shift_end)]
        tech = Technician(
            id=f"T{i+1:03d}",
            location=loc,
            skills=skill_levels,
            availability=availability,
            available_hours_per_week=float(rng.randint(40, 55)),
            max_daily_jobs=rng.choice([None, 4, 5, 6, 8]),
            # Relax distance threshold to improve feasible candidate count.
            max_travel_distance=round(rng.uniform(0.30, 0.65), 3),
            home_base=loc,
        )
        technicians.append(tech)
    return technicians


def generate_repair_requests(
    count: int = 15,
    skills_pool: Optional[list[str]] = None,
    seed: Optional[int] = None,
    base_date: Optional[datetime] = None,
    lat_range: tuple[float, float] = DEFAULT_LAT_RANGE,
    lng_range: tuple[float, float] = DEFAULT_LNG_RANGE,
    priority_distribution: Optional[dict[int, int]] = None,
) -> list[RepairRequest]:
    """
    Generate repair requests with required minimum skill levels and service fee.
    """
    pool = skills_pool or GLOBAL_SKILLS_POOL
    rng = random.Random(seed)
    base_date = base_date or datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
    requests: list[RepairRequest] = []
    priority_plan: list[int] = []
    if priority_distribution:
        for priority, n_jobs in priority_distribution.items():
            if 1 <= int(priority) <= 5 and int(n_jobs) > 0:
                priority_plan.extend([int(priority)] * int(n_jobs))
    rng.shuffle(priority_plan)

    for i in range(count):
        loc = _random_location(lat_range=lat_range, lng_range=lng_range, rng=rng)
        # Relaxed request requirements:
        # - fewer required skills
        # - lower minimum levels on average
        required_skill_levels = _build_skill_levels(
            pool,
            min_skills=1,
            max_skills=2,
            min_level=1,
            max_level=4,
            rng=rng,
        )
        # Keep request windows aligned to shift blocks for better schedule feasibility.
        shift_start, shift_end = rng.choice(SHIFT_BLOCKS)
        shift_window = _single_shift_window(base_date, start_hour=shift_start, end_hour=shift_end)
        duration_mins = float(rng.randint(30, 90))
        latest_start = max(
            shift_window.start,
            shift_window.end - timedelta(minutes=duration_mins),
        )
        # Random start within the chosen shift while ensuring the job can finish.
        delta_minutes = int((latest_start - shift_window.start).total_seconds() // 60)
        start_offset = rng.randint(0, max(0, delta_minutes))
        window_start = shift_window.start + timedelta(minutes=start_offset)
        # Add moderate slack to represent customer flexibility.
        window_end = min(shift_window.end, window_start + timedelta(minutes=duration_mins + rng.randint(30, 90)))
        priority = priority_plan[i] if i < len(priority_plan) else rng.randint(1, 5)
        # Higher priority and longer jobs tend to pay more.
        service_fee = float(round(60 + duration_mins * 2.0 + priority * 35 + rng.uniform(-15, 35), 2))
        req = RepairRequest(
            id=f"R{i+1:03d}",
            location=loc,
            required_skills=required_skill_levels,
            time_window=TimeWindow(start=window_start, end=window_end),
            priority=priority,
            estimated_duration=duration_mins,
            service_fee=max(25.0, service_fee),
            customer_id=f"C{rng.randint(1, 20):02d}" if rng.random() > 0.4 else None,
        )
        requests.append(req)
    return requests
