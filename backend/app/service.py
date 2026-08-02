from __future__ import annotations

from collections.abc import Iterable
from datetime import datetime
from typing import Any

from sqlalchemy import Select, func, select, text
from sqlalchemy.orm import Session as DbSession

from .agents import AGENTS, mock_result
from .config import Settings
from .memory import cosine_score, embed
from .models import AgentEvent, Artifact, AuditLog, Memory, MemoryEmbedding, Session, Task, TaskState
from .storage import ArtifactStore


def task_view(task: Task) -> dict[str, Any]:
    return {
        "id": task.id, "session_id": task.session_id, "prompt": task.prompt, "state": task.state,
        "next_agent_index": task.next_agent_index, "created_at": task.created_at, "updated_at": task.updated_at,
    }


class MemoryGraphService:
    def __init__(self, db: DbSession, settings: Settings):
        self.db, self.settings = db, settings
        self.artifacts = ArtifactStore(settings)

    def create_session(self, title: str) -> Session:
        item = Session(title=title)
        self.db.add(item)
        self.db.flush()  # Assign UUID before recording the immutable audit entry.
        self._audit(item.id, None, "session.created", "user", {"title": title})
        self.db.commit()
        self.db.refresh(item)
        return item

    def create_task(self, session_id: str, prompt: str) -> Task:
        self._session(session_id)
        task = Task(session_id=session_id, prompt=prompt)
        self.db.add(task)
        self.db.flush()
        self._audit(session_id, task.id, "task.created", "user", {"prompt": prompt})
        self.db.commit()
        self.db.refresh(task)
        return task

    def stop(self, task_id: str) -> Task:
        task = self._task(task_id)
        if task.state not in {TaskState.COMPLETED.value, TaskState.FAILED.value}:
            task.state = TaskState.STOPPED.value
            self._audit(task.session_id, task.id, "task.stopped", "user", {"next_agent_index": task.next_agent_index})
            self.db.commit()
        return task

    def resume(self, task_id: str) -> Task:
        task = self._task(task_id)
        if task.state == TaskState.COMPLETED.value:
            raise ValueError("completed tasks cannot be resumed")
        task.state = TaskState.RUNNING.value
        self._audit(task.session_id, task.id, "task.resumed", "user", {"next_agent_index": task.next_agent_index})
        self.db.commit()
        return task

    def run_step(self, task_id: str) -> tuple[Task, AgentEvent]:
        task = self._task(task_id)
        if task.state == TaskState.STOPPED.value:
            raise ValueError("task is stopped; resume it before running another step")
        if task.state == TaskState.COMPLETED.value:
            raise ValueError("task is already completed")
        agent = AGENTS[task.next_agent_index]
        previous_count = self.db.scalar(select(func.count(Memory.id)).where(Memory.session_id == task.session_id)) or 0
        output = mock_result(agent, task.prompt, int(previous_count))
        memory = Memory(session_id=task.session_id, task_id=task.id, agent_name=agent, content=output)
        self.db.add(memory)
        self.db.flush()
        self.db.add(MemoryEmbedding(memory_id=memory.id, session_id=task.session_id,
                                    embedding=embed(output, self.settings.embedding_dimensions)))
        artifact_uri = self.artifacts.put_json(task.session_id, f"{agent}-report", {
            "task_id": task.id, "agent": agent, "output": output, "mock_llm": self.settings.mock_llm,
        })
        self.db.add(Artifact(session_id=task.session_id, task_id=task.id, name=f"{agent}-report", uri=artifact_uri))
        event = AgentEvent(session_id=task.session_id, task_id=task.id, agent_name=agent,
                           event_type="step.completed", payload={"memory_id": memory.id, "artifact_uri": artifact_uri})
        self.db.add(event)
        task.next_agent_index += 1
        task.state = TaskState.COMPLETED.value if task.next_agent_index == len(AGENTS) else TaskState.RUNNING.value
        self._audit(task.session_id, task.id, "agent.step.completed", agent,
                    {"memory_id": memory.id, "next_agent_index": task.next_agent_index})
        self.db.commit()
        self.db.refresh(task)
        self.db.refresh(event)
        return task, event

    def search(self, session_id: str, query: str, limit: int = 8) -> list[dict[str, Any]]:
        self._session(session_id)
        vector = embed(query, self.settings.embedding_dimensions)
        if self.db.bind and self.db.bind.dialect.name != "sqlite":
            # CockroachDB vector-index query: session_id is the index prefix and <=> matches vector_cosine_ops.
            rows = self.db.execute(text("""
                SELECT m.id, m.agent_name, m.kind, m.content, m.created_at,
                       e.embedding <=> CAST(:query_vector AS VECTOR(64)) AS vector_distance
                FROM memory_embeddings AS e
                JOIN memories AS m ON m.id = e.memory_id
                WHERE e.session_id = :session_id
                ORDER BY e.embedding <=> CAST(:query_vector AS VECTOR(64)), m.created_at DESC, m.id ASC
                LIMIT :limit
            """), {"session_id": session_id, "query_vector": _literal(vector), "limit": limit}).mappings().all()
            return [{**dict(row), "score": round(1 - float(row["vector_distance"]), 8)} for row in rows]
        rows = self.db.execute(
            select(Memory, MemoryEmbedding).join(MemoryEmbedding, MemoryEmbedding.memory_id == Memory.id)
            .where(MemoryEmbedding.session_id == session_id)
        ).all()
        ranked = [{"id": memory.id, "agent_name": memory.agent_name, "kind": memory.kind,
                   "content": memory.content, "created_at": memory.created_at,
                   "score": round(cosine_score(vector, embedding.embedding), 8)} for memory, embedding in rows]
        return sorted(ranked, key=lambda item: (-item["score"], item["created_at"], item["id"]))[:limit]

    def dashboard(self, session_id: str) -> dict[str, Any]:
        session = self._session(session_id)
        tasks = self.db.scalars(select(Task).where(Task.session_id == session_id).order_by(Task.created_at.desc())).all()
        memories = self.db.scalars(select(Memory).where(Memory.session_id == session_id).order_by(Memory.created_at.desc())).all()
        events = self.db.scalars(select(AgentEvent).where(AgentEvent.session_id == session_id).order_by(AgentEvent.created_at.desc()).limit(30)).all()
        nodes = [{"id": f"session:{session_id}", "label": session.title, "type": "session"}]
        edges: list[dict[str, str]] = []
        for memory in memories:
            agent_id = f"agent:{memory.agent_name}"
            nodes.extend(({"id": agent_id, "label": memory.agent_name, "type": "agent"},
                          {"id": f"memory:{memory.id}", "label": memory.content[:72], "type": "memory"}))
            edges.extend(({"source": f"session:{session_id}", "target": f"memory:{memory.id}", "type": "owns"},
                          {"source": agent_id, "target": f"memory:{memory.id}", "type": "created"}))
        return {"session": {"id": session.id, "title": session.title, "created_at": session.created_at},
                "tasks": [task_view(item) for item in tasks],
                "memories": [_memory_view(item) for item in memories],
                "events": [_event_view(item) for item in events],
                "graph": {"nodes": _unique_nodes(nodes), "edges": edges},
                "retrieval": self.search(session_id, tasks[0].prompt if tasks else session.title),
                "system": {"database": "CockroachDB" if self.db.bind and self.db.bind.dialect.name != "sqlite" else "SQLite local test mode",
                           "mock_llm": self.settings.mock_llm,
                           "artifact_store": "S3" if self.settings.s3_bucket else "local filesystem"}}

    def _session(self, session_id: str) -> Session:
        item = self.db.get(Session, session_id)
        if not item:
            raise LookupError("session not found")
        return item

    def _task(self, task_id: str) -> Task:
        item = self.db.get(Task, task_id)
        if not item:
            raise LookupError("task not found")
        return item

    def _audit(self, session_id: str, task_id: str | None, action: str, actor: str, details: dict) -> None:
        self.db.add(AuditLog(session_id=session_id, task_id=task_id, action=action, actor=actor, details=details))


def _literal(vector: list[float]) -> str:
    return "[" + ",".join(f"{value:.10f}" for value in vector) + "]"


def _memory_view(memory: Memory) -> dict[str, Any]:
    return {"id": memory.id, "task_id": memory.task_id, "agent_name": memory.agent_name,
            "kind": memory.kind, "content": memory.content, "metadata": memory.attributes, "created_at": memory.created_at}


def _event_view(event: AgentEvent) -> dict[str, Any]:
    return {"id": event.id, "task_id": event.task_id, "agent_name": event.agent_name,
            "event_type": event.event_type, "payload": event.payload, "created_at": event.created_at}


def _unique_nodes(nodes: Iterable[dict[str, str]]) -> list[dict[str, str]]:
    return list({node["id"]: node for node in nodes}.values())
