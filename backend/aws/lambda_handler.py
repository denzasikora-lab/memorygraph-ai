"""AWS Lambda entrypoint for one durable agent step (EventBridge/SQS compatible)."""
from app.config import get_settings
from app.database import SessionLocal
from app.service import MemoryGraphService, task_view


def handler(event: dict, context: object) -> dict:
    task_id = event.get("task_id") or event.get("detail", {}).get("task_id")
    if not isinstance(task_id, str):
        raise ValueError("event.task_id is required")
    with SessionLocal() as db:
        task, agent_event = MemoryGraphService(db, get_settings()).run_step(task_id)
        return {"task": task_view(task), "event_id": agent_event.id}
