from contextlib import asynccontextmanager
from typing import Literal

from fastapi import Depends, FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from .config import get_settings
from .database import engine, get_db, init_schema
from .service import MemoryGraphService, task_view


class CreateSessionRequest(BaseModel):
    title: str = Field(min_length=1, max_length=160)


class CreateTaskRequest(BaseModel):
    prompt: str = Field(min_length=3, max_length=10_000)


class TaskResponse(BaseModel):
    id: str
    session_id: str
    prompt: str
    state: Literal["pending", "running", "stopped", "completed", "failed"]
    next_agent_index: int = Field(ge=0, le=5)


class StepResponse(TaskResponse):
    event: dict


@asynccontextmanager
async def lifespan(_: FastAPI):
    if engine.dialect.name == "sqlite":
        init_schema()
    yield


app = FastAPI(title="MemoryGraph AI", version="0.1.0", lifespan=lifespan)
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])


def service(db: Session = Depends(get_db)) -> MemoryGraphService:
    return MemoryGraphService(db, get_settings())


def translate(call):
    try:
        return call()
    except LookupError as error:
        raise HTTPException(status_code=404, detail=str(error)) from error
    except ValueError as error:
        raise HTTPException(status_code=409, detail=str(error)) from error


@app.get("/health")
def health() -> dict:
    return {"status": "ok", "database_dialect": engine.dialect.name, "mock_llm": get_settings().mock_llm}


@app.post("/api/sessions", status_code=201)
def create_session(payload: CreateSessionRequest, svc: MemoryGraphService = Depends(service)) -> dict:
    item = svc.create_session(payload.title)
    return {"id": item.id, "title": item.title, "created_at": item.created_at}


@app.post("/api/sessions/{session_id}/tasks", response_model=TaskResponse, status_code=201)
def create_task(session_id: str, payload: CreateTaskRequest, svc: MemoryGraphService = Depends(service)) -> dict:
    return translate(lambda: task_view(svc.create_task(session_id, payload.prompt)))


@app.post("/api/tasks/{task_id}/run-step", response_model=StepResponse)
def run_step(task_id: str, svc: MemoryGraphService = Depends(service)) -> dict:
    task, event = translate(lambda: svc.run_step(task_id))
    return {**task_view(task), "event": {"id": event.id, "agent_name": event.agent_name, "event_type": event.event_type, "payload": event.payload}}


@app.post("/api/tasks/{task_id}/stop", response_model=TaskResponse)
def stop_task(task_id: str, svc: MemoryGraphService = Depends(service)) -> dict:
    return translate(lambda: task_view(svc.stop(task_id)))


@app.post("/api/tasks/{task_id}/resume", response_model=TaskResponse)
def resume_task(task_id: str, svc: MemoryGraphService = Depends(service)) -> dict:
    return translate(lambda: task_view(svc.resume(task_id)))


@app.get("/api/sessions/{session_id}/memories/search")
def search_memory(session_id: str, query: str = Query(min_length=1, max_length=10_000), limit: int = Query(8, ge=1, le=50), svc: MemoryGraphService = Depends(service)) -> dict:
    return translate(lambda: {"results": svc.search(session_id, query, limit)})


@app.get("/api/sessions/{session_id}/dashboard")
def dashboard(session_id: str, svc: MemoryGraphService = Depends(service)) -> dict:
    return translate(lambda: svc.dashboard(session_id))
