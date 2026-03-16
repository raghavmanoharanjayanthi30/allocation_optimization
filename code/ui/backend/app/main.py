"""
FastAPI app entrypoint.

Run from project root:
  python3 -m uvicorn code.ui.backend.app.main:app --reload --port 8000
"""

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware

from .schemas import (
    AgentChatRequest,
    AgentChatResponse,
    AllocateRequest,
    AllocateResponse,
    GenerateScenarioRequest,
    GenerateScenarioResponse,
    MethodName,
)
from .services import generate_scenario, run_agent_chat, run_allocation

app = FastAPI(
    title="Field Service Allocation API",
    description="Backend API for optimization methods and scenario generation.",
    version="0.1.0",
)

# Allow local frontend development.
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.get("/methods")
def methods() -> dict[str, list[MethodName]]:
    return {"methods": ["greedy", "hungarian", "min_cost_flow", "milp"]}


@app.post("/generate-scenario", response_model=GenerateScenarioResponse)
def generate_scenario_route(payload: GenerateScenarioRequest) -> GenerateScenarioResponse:
    try:
        return generate_scenario(payload)
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Scenario generation failed: {exc}") from exc


@app.post("/allocate", response_model=AllocateResponse)
def allocate_route(payload: AllocateRequest) -> AllocateResponse:
    try:
        return run_allocation(payload)
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Allocation failed: {exc}") from exc


@app.post("/agent/chat", response_model=AgentChatResponse)
def agent_chat_route(payload: AgentChatRequest) -> AgentChatResponse:
    try:
        return run_agent_chat(payload)
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Agent chat failed: {exc}") from exc
