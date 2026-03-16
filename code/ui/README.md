# UI + Backend Learning Workspace

This folder contains a beginner-friendly full-stack starter for your allocation project:

- `backend/` -> FastAPI API server
- `frontend/` -> React app (Vite)
- `tutorials/` -> learning notes + notebooks

## What this gives you

- Run any scheduler method (`greedy`, `hungarian`, `min_cost_flow`, `milp`) from an API.
- Generate sample technicians/jobs from the backend.
- Paste your own JSON data from the frontend and run allocation.
- Learn both stacks with commented code and tutorial files.
- Use an agentic chat panel to run tool-based actions with natural language.

## Quick start

From project root (`allocation_optimization`):

1) Backend

```bash
python3 -m venv .venv
.venv/bin/pip install -r code/ui/backend/requirements.txt
.venv/bin/python -m uvicorn code.ui.backend.app.main:app --reload --port 8000
```

2) Frontend (new terminal)

```bash
cd code/ui/frontend
npm install
npm run dev
```

Then open the URL printed by Vite (usually `http://localhost:5173`).

## Agent chat examples

In the UI chat box, try:

- `generate 14 workers 10 jobs`
- `run all methods`
- `run milp`
- `explain unassigned`
- `explain assigned R005`

## Agent memory behavior

- Chat now uses a backend `session_id` to retain memory across turns.
- First chat message seeds server memory from current UI state.
- If you manually edit tables or run non-chat actions, session resets so chat memory stays consistent with visible UI.

## LLM planner mode

- In chat UI, enable **LLM planner** to let LangGraph planner use an LLM for tool sequencing.
- Provide API key in UI, or set env var `OPENAI_API_KEY` for backend process.
- Optional model override is supported (default `gpt-4o-mini`).

## Learning path

1. Read `tutorials/FASTAPI_TUTORIAL.md`
2. Read `tutorials/REACT_TUTORIAL.md`
3. Run both notebooks in `tutorials/`
