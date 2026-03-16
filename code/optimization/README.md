# Optimization Architecture (Field Service)

This folder documents and scaffolds the optimization pipeline for technician assignment.

## Why this architecture works

It separates concerns cleanly:

| Component | Purpose |
|---|---|
| Candidate filtering | Shrink the problem to feasible technician-job pairs |
| Scoring model | Evaluate relative quality of feasible options |
| Optimization | Choose assignments globally or sequentially |
| Re-optimization | Adapt as new jobs arrive during the day |

This separation makes the system easier to debug, explain in interviews, and extend.

## Suggested portfolio progression

1. `greedy.py` - first working baseline.
2. `hungarian.py` - stronger batch optimizer for side-by-side comparison.
3. `min_cost_flow.py` - scheduling-aware formulation for richer constraints.
4. `milp.py` (optional) - exact/near-exact formulation for advanced showcase.

## Interview framing

You can explain the system like this:

> The system first generates feasible technician-job candidates using spatial and scheduling constraints.  
> Each candidate pair is scored via weighted utility (revenue, distance, skill fit).  
> An optimization layer (greedy or global solver) then selects assignments.  
> The system runs in rolling horizon mode, periodically re-optimizing while locking near-term jobs for stability.

