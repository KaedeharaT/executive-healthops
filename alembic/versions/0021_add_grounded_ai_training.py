"""Add grounded AI usage audit and training sessions.

Revision ID: 0021_add_grounded_ai_training
Revises: 0020_add_knowledge_center_governance
"""

from alembic import op
import sqlalchemy as sa


revision = "0021_add_grounded_ai_training"
down_revision = "0020_add_knowledge_center_governance"
branch_labels = None
depends_on = None


def upgrade() -> None:
    inspector = sa.inspect(op.get_bind())
    usage_columns = {item["name"] for item in inspector.get_columns("knowledge_use_records")}
    usage_indexes = {item["name"] for item in inspector.get_indexes("knowledge_use_records")}
    additions = {
        "session_id": sa.Column("session_id", sa.String(128)),
        "conversation_id": sa.Column("conversation_id", sa.String(128)),
        "answer_id": sa.Column("answer_id", sa.String(64)),
        "retrieved_at": sa.Column("retrieved_at", sa.DateTime(timezone=True)),
        "used_at": sa.Column("used_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        "citation_snapshot_json": sa.Column("citation_snapshot_json", sa.JSON(), nullable=False, server_default=sa.text("'[]'")),
    }
    if set(additions) - usage_columns:
        with op.batch_alter_table("knowledge_use_records") as batch:
            for name, column in additions.items():
                if name not in usage_columns:
                    batch.add_column(column)
            for name in ("session_id", "conversation_id", "answer_id"):
                index_name = f"ix_knowledge_use_records_{name}"
                if index_name not in usage_indexes:
                    batch.create_index(index_name, [name])

    if not inspector.has_table("training_sessions"):
        op.create_table(
            "training_sessions",
            sa.Column("id", sa.Uuid(), primary_key=True),
            sa.Column("mode", sa.String(32), nullable=False),
            sa.Column("case_id", sa.String(64)),
            sa.Column("step", sa.Integer(), nullable=False, server_default="0"),
            sa.Column("status", sa.String(32), nullable=False, server_default="IN_PROGRESS"),
            sa.Column("trainee_messages", sa.JSON(), nullable=False, server_default=sa.text("'[]'")),
            sa.Column("coach_answers", sa.JSON(), nullable=False, server_default=sa.text("'[]'")),
            sa.Column("citations", sa.JSON(), nullable=False, server_default=sa.text("'[]'")),
            sa.Column("score_result", sa.JSON(), nullable=False, server_default=sa.text("'{}'")),
            sa.Column("started_at", sa.DateTime(timezone=True), nullable=False),
            sa.Column("completed_at", sa.DateTime(timezone=True)),
        )
        op.create_index("ix_training_sessions_mode", "training_sessions", ["mode"])
        op.create_index("ix_training_sessions_case_id", "training_sessions", ["case_id"])
        op.create_index("ix_training_sessions_status", "training_sessions", ["status"])


def downgrade() -> None:
    op.drop_index("ix_training_sessions_status", table_name="training_sessions")
    op.drop_index("ix_training_sessions_case_id", table_name="training_sessions")
    op.drop_index("ix_training_sessions_mode", table_name="training_sessions")
    op.drop_table("training_sessions")
    with op.batch_alter_table("knowledge_use_records") as batch:
        for name in ("answer_id", "conversation_id", "session_id"):
            batch.drop_index(f"ix_knowledge_use_records_{name}")
        for name in ("citation_snapshot_json", "used_at", "retrieved_at", "answer_id", "conversation_id", "session_id"):
            batch.drop_column(name)
