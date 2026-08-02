"""initial MemoryGraph schema with CockroachDB distributed vector index

Revision ID: 20260802_0001
Revises:
Create Date: 2026-08-02
"""
from alembic import op
import sqlalchemy as sa

revision = "20260802_0001"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    timestamp = sa.DateTime(timezone=True)
    op.create_table("sessions", sa.Column("id", sa.String(36), primary_key=True), sa.Column("title", sa.String(160), nullable=False),
                    sa.Column("created_at", timestamp, nullable=False), sa.Column("updated_at", timestamp, nullable=False))
    op.create_table("tasks", sa.Column("id", sa.String(36), primary_key=True), sa.Column("session_id", sa.String(36), sa.ForeignKey("sessions.id"), nullable=False),
                    sa.Column("prompt", sa.Text, nullable=False), sa.Column("state", sa.String(16), nullable=False), sa.Column("next_agent_index", sa.Integer, nullable=False),
                    sa.Column("created_at", timestamp, nullable=False), sa.Column("updated_at", timestamp, nullable=False))
    op.create_table("memories", sa.Column("id", sa.String(36), primary_key=True), sa.Column("session_id", sa.String(36), sa.ForeignKey("sessions.id"), nullable=False),
                    sa.Column("task_id", sa.String(36), sa.ForeignKey("tasks.id")), sa.Column("agent_name", sa.String(32), nullable=False), sa.Column("kind", sa.String(32), nullable=False),
                    sa.Column("content", sa.Text, nullable=False), sa.Column("metadata", sa.JSON, nullable=False), sa.Column("created_at", timestamp, nullable=False))
    op.create_table("memory_embeddings", sa.Column("id", sa.String(36), primary_key=True), sa.Column("memory_id", sa.String(36), sa.ForeignKey("memories.id"), nullable=False, unique=True),
                    sa.Column("session_id", sa.String(36), sa.ForeignKey("sessions.id"), nullable=False), sa.Column("created_at", timestamp, nullable=False))
    # VECTOR syntax and vector_cosine_ops are CockroachDB SQL, verified against its official vector-index documentation.
    op.execute("ALTER TABLE memory_embeddings ADD COLUMN embedding VECTOR(64) NOT NULL")
    op.create_table("agent_events", sa.Column("id", sa.String(36), primary_key=True), sa.Column("session_id", sa.String(36), sa.ForeignKey("sessions.id"), nullable=False),
                    sa.Column("task_id", sa.String(36), sa.ForeignKey("tasks.id"), nullable=False), sa.Column("agent_name", sa.String(32), nullable=False),
                    sa.Column("event_type", sa.String(32), nullable=False), sa.Column("payload", sa.JSON, nullable=False), sa.Column("created_at", timestamp, nullable=False))
    op.create_table("artifacts", sa.Column("id", sa.String(36), primary_key=True), sa.Column("session_id", sa.String(36), sa.ForeignKey("sessions.id"), nullable=False),
                    sa.Column("task_id", sa.String(36), sa.ForeignKey("tasks.id"), nullable=False), sa.Column("name", sa.String(160), nullable=False), sa.Column("uri", sa.Text, nullable=False),
                    sa.Column("content_type", sa.String(80), nullable=False), sa.Column("created_at", timestamp, nullable=False))
    op.create_table("audit_logs", sa.Column("id", sa.String(36), primary_key=True), sa.Column("session_id", sa.String(36), sa.ForeignKey("sessions.id"), nullable=False),
                    sa.Column("task_id", sa.String(36), sa.ForeignKey("tasks.id")), sa.Column("action", sa.String(64), nullable=False), sa.Column("actor", sa.String(64), nullable=False),
                    sa.Column("details", sa.JSON, nullable=False), sa.Column("created_at", timestamp, nullable=False))
    for table, columns in (("tasks", ["session_id", "state"]), ("memories", ["session_id", "created_at"]),
                           ("memory_embeddings", ["session_id"]), ("agent_events", ["session_id", "task_id"]),
                           ("artifacts", ["session_id", "task_id"]), ("audit_logs", ["session_id", "task_id", "action"])):
        for column in columns:
            op.create_index(f"ix_{table}_{column}", table, [column])
    op.execute("CREATE VECTOR INDEX memory_embeddings_session_embedding_idx ON memory_embeddings (session_id, embedding vector_cosine_ops)")


def downgrade() -> None:
    for table in ("audit_logs", "artifacts", "agent_events", "memory_embeddings", "memories", "tasks", "sessions"):
        op.drop_table(table)
