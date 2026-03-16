"""
Phase 1 demo: generate synthetic technicians and repair requests, then print a summary.

Run from project root:
  python3 -m code.run_phase1_demo

Or from the code/ directory:
  python3 run_phase1_demo.py
"""

import sys
from pathlib import Path

if __name__ == "__main__":
    _file = Path(__file__).resolve()
    _code_dir = _file.parent
    if _code_dir.name == "code" and str(_code_dir.parent) not in sys.path:
        sys.path.insert(0, str(_code_dir.parent))

from code.data_generator import generate_repair_requests, generate_technicians


def main() -> None:
    seed = 42
    technicians = generate_technicians(count=8, seed=seed)
    requests = generate_repair_requests(count=12, seed=seed)

    print("=== Field Service Allocation Engine — Data + Constraints Seed Demo ===\n")
    print(f"Generated {len(technicians)} technicians and {len(requests)} repair requests (seed={seed}).\n")

    print("Technicians (sample):")
    for t in technicians[:3]:
        print(
            f"  {t.id}: skills={t.skills}, available_hours={t.available_hours_per_week}, "
            f"max_distance={t.max_travel_distance}"
        )

    print("\nRepair requests (sample):")
    for r in requests[:3]:
        print(
            f"  {r.id}: required_skills={r.required_skills}, priority={r.priority}, "
            f"fee={r.service_fee}, duration={r.estimated_duration}"
        )

    print("\nReady for Phase 2 constraints and scoring.")


if __name__ == "__main__":
    main()
