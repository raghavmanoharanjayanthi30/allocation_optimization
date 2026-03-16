# FastAPI Tutorial (for this project)

## 1) What FastAPI is

FastAPI is a Python web framework to build APIs quickly using typed request/response models.

In this project, it serves as the backend that:
- generates scenarios (`/generate-scenario`)
- runs optimization methods (`/allocate`)
- reports health/methods (`/health`, `/methods`)

## 2) File walkthrough

- `backend/app/main.py` -> route definitions
- `backend/app/schemas.py` -> request/response contracts
- `backend/app/services.py` -> business logic (calls scheduler)

## 3) How to run

From repo root:

```bash
.venv/bin/pip install -r code/ui/backend/requirements.txt
.venv/bin/python -m uvicorn code.ui.backend.app.main:app --reload --port 8000
```

Open docs:
- `http://localhost:8000/docs`

## 4) Learning checkpoints

1. Inspect `AllocateRequest` and `AllocateResponse` in `schemas.py`.
2. Add a tiny endpoint in `main.py` and see it in `/docs`.
3. Change response fields and observe schema updates.

## 5) Next mini exercise

Add a route:
- `POST /allocate-and-explain`
- returns top 3 assignments with just:
  - technician_id
  - request_id
  - explanation
