"""
Run all optimization methods and print side-by-side comparison metrics.

Run from project root:
  python3 -m code.run_optimizers_demo

Or from the code/ directory:
  python3 run_optimizers_demo.py
"""

import sys
from pathlib import Path

if __name__ == "__main__":
    _file = Path(__file__).resolve()
    _code_dir = _file.parent
    if _code_dir.name == "code" and str(_code_dir.parent) not in sys.path:
        sys.path.insert(0, str(_code_dir.parent))

from code import Scheduler
from code.data_generator import generate_repair_requests, generate_technicians


def main() -> None:
    seed_tech = 101
    seed_req = 202
    use_random_data = True

    if use_random_data:
        technicians = generate_technicians(count=12, seed=None)
        jobs = generate_repair_requests(count=10, seed=None)
        seed_label = "random (seed=None)"
    else:
        technicians = generate_technicians(count=12, seed=seed_tech)
        jobs = generate_repair_requests(count=10, seed=seed_req)
        seed_label = f"technicians={seed_tech}, requests={seed_req}"
    scheduler = Scheduler()

    methods = [
        ("greedy", scheduler.greedy_assign),
        ("hungarian", scheduler.hungarian_assign),
        ("min_cost_flow", scheduler.min_cost_flow_assign),
        ("milp", scheduler.milp_assign),
    ]

    print("=== Optimizer Comparison Demo ===")
    print(f"Technicians={len(technicians)} | Jobs={len(jobs)}")
    print(f"Seeds: {seed_label}\n")
    print(f"{'method':<14} {'assigned':>8} {'unassigned':>11} {'objective':>11}")
    print("-" * 48)

    for name, fn in methods:
        result = fn(technicians, jobs)
        print(
            f"{name:<14} "
            f"{len(result.assignments):>8} "
            f"{len(result.unassigned_request_ids):>11} "
            f"{result.objective_value:>11.4f}"
        )

    print("\nDone.")


if __name__ == "__main__":
    main()

