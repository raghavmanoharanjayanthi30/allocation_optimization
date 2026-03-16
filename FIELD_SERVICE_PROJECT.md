# Field Service Allocation Engine — Project Plan

**Domain:** Field Service — Technicians assigned to repair/maintenance requests  
**Purpose:** Portfolio project optimized for AI Engineer / ML Engineer roles

---

## 1. Project Description

A resource allocation engine that assigns technicians to repair requests with:
- hard constraints (availability, no overlap, required skills at required proficiency, distance limits),
- sequential assignment order by priority,
- and a weighted objective to balance revenue and distance.

### Current Modeling Choices

- **Skill levels:** `1-10` for technicians.
- **Request skill requirements:** per-skill minimum level (dictionary).
- **Fee:** each repair request has `service_fee`.
- **Technician hours:** `available_hours_per_week` with minimum baseline check (`>= 40`).
- **Distance cap:** each technician has `max_travel_distance`.
- **Objective:** maximize weighted utility, default 0.5 revenue and 0.5 distance (plus small skill-strength tie-break term).

---

## 2. Implementation Steps

### Phase 1: Data Model & Core Types

- [x] **1.1** Technician includes `skills` with levels, availability windows, `available_hours_per_week`, and `max_travel_distance`.
- [x] **1.2** RepairRequest includes required skill levels, `service_fee`, priority, and duration.
- [x] **1.3** Assignment model includes score and travel/revenue metadata.
- [x] **1.4** Synthetic data generator produces technician/request data from a global skill pool.

### Phase 2: Constraints & Scoring

- [x] **2.1** **Hard constraints module created** in `code/constraints/hard_constraints.py`:
  - technician weekly hours baseline (`>= 40`)
  - required skill-level match
  - max distance compliance
  - feasible non-overlapping slot in time window
- [x] **2.2** **Soft scoring module created** in `code/constraints/scoring.py`:
  - weighted utility from fee and distance
  - stronger skill-level match preference as tie-break/boost
- [x] **2.3** Feasibility API added: `can_assign(...)` returns feasibility, reasons, and feasible slot.

### Phase 3: Allocation Algorithms (next)

- [ ] **3.1** Greedy allocation in request priority order.
- [ ] **3.2** Hungarian batch version.
- [ ] **3.3** ML-based scoring strategy.
- [ ] **3.4** Shared interface returning assignments + metrics + explanations.

---

## 3. Resume Framing

### Project title

- **Field Service Allocation Engine** — technician assignment with hard constraints and weighted objective scoring.

### Resume bullets (examples)

- Built a field service assignment engine with hard constraints on availability windows, skill proficiency, non-overlapping bookings, and per-technician travel limits.
- Modeled technician skill proficiency and request minimum skill levels (1-10), and implemented weighted objective scoring to maximize revenue while minimizing travel distance.
- Created reusable feasibility and scoring modules to support multiple allocation strategies (greedy, Hungarian, ML-based) and interpretable assignment rationale.

# Field Service Allocation Engine — Project Plan

**Domain:** Field Service — Technicians assigned to repair/maintenance requests  
**Purpose:** Portfolio project optimized for AI Engineer / ML Engineer roles

---

## 1. Project Description

A resource allocation engine that assigns technicians to repair requests with:
- hard constraints (availability, no overlap, required skills at required proficiency, distance limits),
- sequential assignment order by priority,
- and a weighted objective to balance revenue and distance.

### Current Modeling Choices

- **Skill levels:** `1-10` for technicians.
- **Request skill requirements:** per-skill minimum level (dictionary).
- **Fee:** each repair request has `service_fee`.
- **Technician hours:** `available_hours_per_week` with minimum baseline check (`>= 40`).
- **Distance cap:** each technician has `max_travel_distance`.
- **Objective:** maximize weighted utility, default 0.5 revenue and 0.5 distance (plus small skill-strength tie-break term).

---

## 2. Implementation Steps

### Phase 1: Data Model & Core Types

- [x] **1.1** Technician includes `skills` with levels, availability windows, `available_hours_per_week`, and `max_travel_distance`.
- [x] **1.2** RepairRequest includes required skill levels, `service_fee`, priority, and duration.
- [x] **1.3** Assignment model includes score and travel/revenue metadata.
- [x] **1.4** Synthetic data generator produces technician/request data from a global skill pool.

### Phase 2: Constraints & Scoring

- [x] **2.1** **Hard constraints module created** in `code/constraints/hard_constraints.py`:
  - technician weekly hours baseline (`>= 40`)
  - required skill-level match
  - max distance compliance
  - feasible non-overlapping slot in time window
- [x] **2.2** **Soft scoring module created** in `code/constraints/scoring.py`:
  - weighted utility from fee and distance
  - stronger skill-level match preference as tie-break/boost
- [x] **2.3** Feasibility API added: `can_assign(...)` returns feasibility, reasons, and feasible slot.

### Phase 3: Allocation Algorithms (next)

- [ ] **3.1** Greedy allocation in request priority order.
- [ ] **3.2** Hungarian batch version.
- [ ] **3.3** ML-based scoring strategy.
- [ ] **3.4** Shared interface returning assignments + metrics + explanations.

---

## 3. Resume Framing

### Project title

- **Field Service Allocation Engine** — technician assignment with hard constraints and weighted objective scoring.

### Resume bullets (examples)

- Built a field service assignment engine with hard constraints on availability windows, skill proficiency, non-overlapping bookings, and per-technician travel limits.
- Modeled technician skill proficiency and request minimum skill levels (1-10), and implemented weighted objective scoring to maximize revenue while minimizing travel distance.
- Created reusable feasibility and scoring modules to support multiple allocation strategies (greedy, Hungarian, ML-based) and interpretable assignment rationale.

# Field Service Allocation Engine — Project Plan

**Domain:** Field Service — Technicians assigned to repair/maintenance requests  
**Purpose:** Portfolio project optimized for AI Engineer / ML Engineer roles

---

## 1. Project Description

### What We're Building

A **Resource Allocation Engine** for field service operations: the system assigns **technicians** (mobile resources) to **repair requests** (jobs) in an optimal way. Technicians have locations, skills, and availability windows; requests have location, required skills, priority, and time windows. The engine produces **assignments** (technician–request pairings) that satisfy constraints and optimize objectives such as total travel time, workload balance, and job completion likelihood.

### Why Field Service for AI/ML

- **Data-driven:** Assignment success, job duration, and technician performance can be learned from historical data.
- **Multiple strategies:** Easy to compare classical methods (greedy, Hungarian) with an ML-based strategy (e.g., learned cost or success model).
- **Explainability:** "Why this technician?" can be grounded in skills match, distance, and historical success — strong talking point for production ML.
- **Business impact:** Clear metrics (cost, utilization, unassigned jobs) that map to real-world KPIs.

### High-Level Flow

1. **Input:** A set of technicians (location, skills, availability) and a set of repair requests (location, required skills, time window, priority).
2. **Process:** Run one or more allocation algorithms (Greedy, Hungarian, ML-based) subject to hard and soft constraints.
3. **Output:** Assignments with explanations, plus metrics for comparison (total distance, # assigned/unassigned, utilization, etc.).
4. **Visualization:** Web UI with map view, side-by-side algorithm comparison, and metrics.

---

## 2. Implementation Steps

### Phase 1: Data Model & Core Types

- [x] **1.1** Define **Technician** (resource): `id`, `location` (lat/lng or x,y), `skills` (list of skill IDs or levels), `availability` (e.g., list of time windows or start/end), optional `max_daily_jobs`, `home_base`.
- [x] **1.2** Define **RepairRequest** (request): `id`, `location`, `required_skills`, `time_window` (earliest/latest), `priority` (e.g., 1–5), optional `estimated_duration`, `customer_id` (for "prefer same technician" soft constraint).
- [x] **1.3** Define **Assignment**: `technician_id`, `request_id`, optional `score`, `explanation` (why this pairing), `estimated_travel_time`, `slot_start`.
- [x] **1.4** Add **synthetic data generator** (or fixed seed data) for technicians and requests so you can run and compare algorithms without external APIs.

### Phase 2: Constraints & Scoring

- [ ] **2.1** **Hard constraints:** (a) Technician available in request time window, (b) Technician has all required skills, (c) No double-booking (each technician assigned at most one request per time slot / no overlapping jobs).
- [ ] **2.2** **Soft constraints / scoring:** (a) Minimize travel distance or time, (b) Prefer higher-skill match when multiple technicians qualify, (c) Optional: prefer same technician for same customer, (d) Optional: balance workload (e.g., prefer less-loaded technicians).
- [ ] **2.3** Implement a **feasibility check** (can this technician serve this request?) and a **score function** (how good is this pairing?) used by all algorithms.

### Phase 3: Allocation Algorithms

- [ ] **3.1** **Greedy:** For each request (e.g., by priority or deadline), assign the best available technician by score; mark technician as used for that time. Provide per-assignment explanation (e.g., "Closest available technician with required skills").
- [ ] **3.2** **Hungarian (batch):** Build cost matrix (request × technician; infeasible = large constant). Use SciPy `linear_sum_assignment` (or equivalent). Map result to assignments; generate explanations from cost components (distance, skill match). Handle unassigned requests explicitly.
- [ ] **3.3** **ML-based (optional but recommended for resume):** Train a simple model (e.g., sklearn GradientBoosting or small neural net) on synthetic "historical" data: features = (distance, skill match, technician load, etc.), target = assignment success or inverse cost. Use model to score pairs and run greedy (or batch) with ML scores. Document "when ML beats Hungarian" in the write-up.
- [ ] **3.4** **Shared interface:** Single entry point that runs a chosen algorithm and returns `Assignments`, `metrics`, `explanations` so the API and UI can switch strategies easily.

### Phase 4: Backend API

- [ ] **4.1** Set up **FastAPI** (or Django) app; define Pydantic models for Technician, RepairRequest, Assignment, and algorithm choice.
- [ ] **4.2** Endpoints: e.g., `POST /allocate` (body: technicians, requests, algorithm) → assignments + metrics; optional `GET /algorithms` for list; health check.
- [ ] **4.3** Ensure CORS and JSON responses are suitable for the React frontend. Keep logic in a separate module so it’s testable without the server.

### Phase 5: Frontend (React)

- [ ] **5.1** **Map view:** Use Leaflet + OpenStreetMap (or canvas/SVG). Plot technicians and requests as markers; draw lines or colors for assignments. Toggle by algorithm if needed.
- [ ] **5.2** **Algorithm comparison:** Two panels (or tabs) showing results for Algorithm A vs Algorithm B (same input), with metrics side-by-side.
- [ ] **5.3** **Metrics display:** Total distance, # assigned / unassigned, utilization %, average travel time, etc. Per-algorithm.
- [ ] **5.4** (Optional) Controls to add/remove technicians or requests and re-run allocation.

### Phase 6: Testing & Documentation

- [ ] **6.1** **Unit tests:** Feasibility and scoring; each algorithm returns valid assignments (hard constraints satisfied); metrics are consistent.
- [ ] **6.2** **Comparison tests:** Same instance → different algorithms; assert metrics differ where expected and document tradeoffs.
- [ ] **6.3** **README:** Setup (Python venv, `pip install`, `npm install`), how to run backend and frontend, how to run tests. Short overview: "Field service allocation with Greedy, Hungarian, and ML-based strategies."
- [ ] **6.4** **Algorithm write-up:** 1–2 pages: when does Greedy vs Hungarian vs ML win? What did you learn? (Example: Greedy can be suboptimal when many requests compete for the same technicians; Hungarian gives global optimum for linear cost; ML can capture non-linear patterns from data.)

### Phase 7: Polish & Submission

- [ ] **7.1** `requirements.txt` or `pyproject.toml`; `package.json`; exclude `node_modules` from zip/repo.
- [ ] **7.2** Ensure app runs locally with no API keys or paid services. Verify README instructions end-to-end.

---

## 3. Resume Framing

Use these as inspiration for bullets and project descriptions. Adjust wording to fit your style and space.

### Project title (one line)

- **Field Service Resource Allocation Engine** — Optimal assignment of technicians to repair requests using Greedy, Hungarian, and ML-based strategies; React + FastAPI.

### Bullet points (pick 2–4)

- Designed and implemented a **resource allocation engine** for field service that assigns technicians to repair requests under hard constraints (availability, skills) and soft objectives (minimize travel, balance workload).
- Implemented **three allocation strategies** (greedy, Hungarian batch optimization, ML-based scoring) and compared performance on synthetic data; documented when each approach performs best and why.
- Built **interpretable assignment explanations** (e.g., skill match, distance, historical success) and reported metrics (utilization, total distance, unassigned count) to support decision transparency and algorithm comparison.
- Developed a **full-stack web app** (React + Leaflet, FastAPI backend) with map visualization, side-by-side algorithm comparison, and metrics dashboards; included unit tests and a brief analysis write-up comparing algorithms.

### Short paragraph (for "Projects" section or cover letter)

*Built a Field Service Resource Allocation Engine that optimally assigns technicians to repair requests. Implemented greedy sequential assignment, Hungarian algorithm for batch optimal matching, and an ML-based strategy that learns assignment quality from synthetic historical data. The system enforces hard constraints (availability, skills) and optimizes for travel time and workload balance, with explainable decisions and metrics. Delivered a React + FastAPI application with map-based visualization and side-by-side algorithm comparison, plus tests and a write-up analyzing when each approach performs best. Designed for AI/ML portfolio relevance: classical OR methods vs. data-driven assignment.*

### Keywords to include (where natural)

- Resource allocation, assignment problem, optimization  
- Greedy algorithm, Hungarian algorithm, batch optimization  
- Constraint satisfaction, hard/soft constraints  
- ML-based scoring, interpretability, decision explanation  
- React, FastAPI, Leaflet, OpenStreetMap  
- Metrics, utilization, comparison of algorithms  

---

## 4. Quick Reference

| Item | Choice |
|------|--------|
| Domain | Field Service (technicians ↔ repair requests) |
| Backend | FastAPI (or Django) |
| Frontend | React + Leaflet (OpenStreetMap) |
| Algorithms | Greedy, Hungarian, ML-based (recommended) |
| Data | Synthetic / generated (no paid APIs) |
| Deliverables | Code, working app, README, tests, algorithm comparison write-up |

You can track progress by checking off the steps in Section 2 as you go.
