"""
Min-cost flow scheduler (skeleton).

Why this approach:
- supports richer multi-job sequencing
- handles capacities naturally
- often strong for large structured dispatch problems
"""

from ..constraints.hard_constraints import can_assign, sort_requests_for_allocation
from typing import Optional

from ..constraints.scoring import ObjectiveWeights, explain_score, weighted_utility
from ..models import Assignment, RepairRequest, Technician, TimeWindow
from .types import OptimizationResult

UNASSIGNED_PENALTY = 600  # integer cost units (scaled)
COST_SCALE = 1000


def build_flow_network(
    technicians,
    jobs,
    weights: Optional[ObjectiveWeights] = None,
    min_hours_per_week: float = 40.0,
):
    """
    Build flow network for one-to-one batch assignment.

    Graph structure:
    source -> request_i -> tech_j -> sink
                       -> unassigned -> sink
    """
    try:
        import networkx as nx  # type: ignore
    except ImportError as exc:
        raise ImportError("Min-cost flow requires networkx. Install with: pip install networkx") from exc

    sorted_jobs = sort_requests_for_allocation(jobs)
    G = nx.DiGraph()
    source = "source"
    sink = "sink"
    unassigned = "unassigned"
    G.add_node(source)
    G.add_node(sink)
    G.add_node(unassigned)

    # Store pair metadata for decoding chosen edges.
    pair_info: dict[tuple[str, str], tuple[float, TimeWindow, Technician, RepairRequest]] = {}

    for req in sorted_jobs:
        req_node = f"req::{req.id}"
        G.add_edge(source, req_node, capacity=1, weight=0)
        # Unassigned fallback edge.
        G.add_edge(req_node, unassigned, capacity=1, weight=UNASSIGNED_PENALTY)

        for tech in technicians:
            feasible, _reasons, slot = can_assign(tech, req, existing_bookings=[], min_hours_per_week=min_hours_per_week)
            if not feasible or slot is None:
                continue
            tech_node = f"tech::{tech.id}"
            utility = weighted_utility(tech, req, weights=weights or ObjectiveWeights())
            # Min-cost formulation: lower is better -> cost = -utility (scaled and shifted)
            edge_cost = int(round(-utility * COST_SCALE))
            G.add_edge(req_node, tech_node, capacity=1, weight=edge_cost)
            pair_info[(req_node, tech_node)] = (utility, slot, tech, req)

    for tech in technicians:
        tech_node = f"tech::{tech.id}"
        if tech_node not in G:
            G.add_node(tech_node)
        # One job per technician in this batch flow.
        G.add_edge(tech_node, sink, capacity=1, weight=0)

    # Unassigned aggregator can absorb all jobs.
    G.add_edge(unassigned, sink, capacity=len(sorted_jobs), weight=0)

    return G, pair_info, sorted_jobs, source, sink


def min_cost_flow_assign(
    technicians,
    jobs,
    weights: Optional[ObjectiveWeights] = None,
    min_hours_per_week: float = 40.0,
) -> OptimizationResult:
    """
    Min-cost flow batch assignment implementation.
    """
    if not jobs:
        return OptimizationResult(notes=["No jobs provided."])

    G, pair_info, sorted_jobs, source, sink = build_flow_network(
        technicians,
        jobs,
        weights=weights,
        min_hours_per_week=min_hours_per_week,
    )
    try:
        import networkx as nx  # type: ignore
    except ImportError as exc:
        raise ImportError("Min-cost flow requires networkx. Install with: pip install networkx") from exc

    flow = nx.max_flow_min_cost(G, source, sink, capacity="capacity", weight="weight")

    assignments: list[Assignment] = []
    unassigned: list[str] = []
    objective_value = 0.0

    # Decode selected request -> (tech/unassigned) edges.
    req_to_job = {f"req::{r.id}": r for r in sorted_jobs}
    for req_node, req in req_to_job.items():
        outgoing = flow.get(req_node, {})
        chosen_tech_node = None
        for target, value in outgoing.items():
            if value <= 0:
                continue
            if target == "unassigned":
                chosen_tech_node = None
                break
            if target.startswith("tech::"):
                chosen_tech_node = target
                break

        if chosen_tech_node is None:
            unassigned.append(req.id)
            continue

        info_key = (req_node, chosen_tech_node)
        if info_key not in pair_info:
            unassigned.append(req.id)
            continue
        utility, slot, tech, _req = pair_info[info_key]
        objective_value += utility
        assignments.append(
            Assignment(
                technician_id=tech.id,
                request_id=req.id,
                score=utility,
                explanation=f"Min-cost-flow pick: {explain_score(tech, req, utility)}",
                estimated_travel_distance=tech.location.distance_to(req.location),
                expected_revenue=req.service_fee,
                slot_start=slot.start,
            )
        )

    return OptimizationResult(
        assignments=assignments,
        unassigned_request_ids=unassigned,
        objective_value=objective_value,
        notes=["Min-cost flow batch assignment completed."],
    )

