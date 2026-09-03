"""Add governed offline AI feedback and model registry.

Revision ID: 0023_add_ai_feedback_governance
Revises: 0022_add_knowledge_source_governance
"""

from alembic import op
import sqlalchemy as sa


revision = "0023_add_ai_feedback_governance"
down_revision = "0022_add_knowledge_source_governance"
branch_labels = None
depends_on = None


def upgrade() -> None:
    inspector = sa.inspect(op.get_bind())
    usage_columns = {column["name"] for column in inspector.get_columns("knowledge_use_records")}
    if "external_chunk_ids" not in usage_columns or not next(column for column in inspector.get_columns("knowledge_use_records") if column["name"] == "knowledge_document_id")["nullable"]:
        with op.batch_alter_table("knowledge_use_records") as batch:
            if "external_chunk_ids" not in usage_columns:
                batch.add_column(sa.Column("external_chunk_ids", sa.JSON(), nullable=False, server_default=sa.text("'[]'")))
            batch.alter_column("knowledge_document_id", existing_type=sa.Uuid(), nullable=True)

    if not inspector.has_table("feedback_records"):
        op.create_table(
            "feedback_records",
            sa.Column("id", sa.Uuid(), primary_key=True),
            sa.Column("feedback_type", sa.String(40), nullable=False),
            sa.Column("feature", sa.String(80), nullable=False),
            sa.Column("source_entity_type", sa.String(80), nullable=False),
            sa.Column("source_entity_id", sa.String(128), nullable=False),
            sa.Column("member_id", sa.Uuid(), sa.ForeignKey("patients.id")),
            sa.Column("model_provider", sa.String(64)),
            sa.Column("model_name", sa.String(128)),
            sa.Column("model_version", sa.String(64)),
            sa.Column("prompt_version", sa.String(64)),
            sa.Column("input_hash", sa.String(64), nullable=False),
            sa.Column("prediction_summary", sa.Text()),
            sa.Column("human_correction", sa.Text()),
            sa.Column("feedback_label", sa.String(64), nullable=False),
            sa.Column("feedback_reason", sa.Text()),
            sa.Column("evidence_refs", sa.JSON(), nullable=False, server_default=sa.text("'[]'")),
            sa.Column("created_by", sa.String(128), nullable=False),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
            sa.Column("review_status", sa.String(32), nullable=False, server_default="CAPTURED"),
            sa.Column("reviewed_by", sa.String(128)),
            sa.Column("reviewed_at", sa.DateTime(timezone=True)),
            sa.Column("eligible_for_training", sa.Boolean(), nullable=False, server_default=sa.false()),
            sa.Column("deidentified", sa.Boolean(), nullable=False, server_default=sa.false()),
        )
        for column in ("feedback_type", "feature", "source_entity_id", "member_id", "input_hash", "feedback_label", "review_status", "eligible_for_training"):
            op.create_index(f"ix_feedback_records_{column}", "feedback_records", [column])

    if not inspector.has_table("feedback_dataset_versions"):
        op.create_table(
            "feedback_dataset_versions",
            sa.Column("id", sa.Uuid(), primary_key=True),
            sa.Column("dataset_id", sa.String(128), nullable=False),
            sa.Column("dataset_version", sa.Integer(), nullable=False),
            sa.Column("schema_version", sa.String(32), nullable=False, server_default="1.0"),
            sa.Column("feature", sa.String(80)),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
            sa.Column("record_count", sa.Integer(), nullable=False),
            sa.Column("source_feedback_count", sa.Integer(), nullable=False),
            sa.Column("content_hash", sa.String(64), nullable=False),
            sa.Column("records_json", sa.JSON(), nullable=False, server_default=sa.text("'[]'")),
            sa.UniqueConstraint("dataset_id", "dataset_version", name="uq_feedback_dataset_version"),
        )
        op.create_index("ix_feedback_dataset_versions_dataset_id", "feedback_dataset_versions", ["dataset_id"])
        op.create_index("ix_feedback_dataset_versions_feature", "feedback_dataset_versions", ["feature"])

    if not inspector.has_table("model_version_registry"):
        op.create_table(
            "model_version_registry",
            sa.Column("id", sa.Uuid(), primary_key=True),
            sa.Column("provider", sa.String(64), nullable=False),
            sa.Column("base_model", sa.String(128), nullable=False),
            sa.Column("model_version", sa.String(64), nullable=False),
            sa.Column("training_dataset_version", sa.String(128)),
            sa.Column("prompt_version", sa.String(64)),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
            sa.Column("status", sa.String(32), nullable=False, server_default="CANDIDATE"),
            sa.Column("evaluation_report", sa.JSON(), nullable=False, server_default=sa.text("'{}'")),
            sa.Column("approved_by", sa.String(128)),
            sa.Column("approved_at", sa.DateTime(timezone=True)),
            sa.Column("activated_at", sa.DateTime(timezone=True)),
            sa.Column("retired_at", sa.DateTime(timezone=True)),
            sa.UniqueConstraint("provider", "model_version", name="uq_model_provider_version"),
        )
        op.create_index("ix_model_version_registry_model_version", "model_version_registry", ["model_version"])
        op.create_index("ix_model_version_registry_status", "model_version_registry", ["status"])

    if not inspector.has_table("risk_rule_review_candidates"):
        op.create_table(
            "risk_rule_review_candidates",
            sa.Column("id", sa.Uuid(), primary_key=True),
            sa.Column("risk_rule_id", sa.Uuid(), sa.ForeignKey("risk_rules.id"), nullable=False),
            sa.Column("risk_event_id", sa.Uuid(), sa.ForeignKey("risk_events.id")),
            sa.Column("feedback_record_id", sa.Uuid(), sa.ForeignKey("feedback_records.id"), nullable=False, unique=True),
            sa.Column("feedback_type", sa.String(48), nullable=False),
            sa.Column("reason", sa.Text(), nullable=False),
            sa.Column("supporting_evidence", sa.JSON(), nullable=False, server_default=sa.text("'[]'")),
            sa.Column("review_status", sa.String(32), nullable=False, server_default="PENDING_REVIEW"),
            sa.Column("reviewed_by", sa.String(128)),
            sa.Column("reviewed_at", sa.DateTime(timezone=True)),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        )
        for column in ("risk_rule_id", "risk_event_id", "review_status"):
            op.create_index(f"ix_risk_rule_review_candidates_{column}", "risk_rule_review_candidates", [column])


def downgrade() -> None:
    for column in ("review_status", "risk_event_id", "risk_rule_id"):
        op.drop_index(f"ix_risk_rule_review_candidates_{column}", table_name="risk_rule_review_candidates")
    op.drop_table("risk_rule_review_candidates")
    op.drop_index("ix_model_version_registry_status", table_name="model_version_registry")
    op.drop_index("ix_model_version_registry_model_version", table_name="model_version_registry")
    op.drop_table("model_version_registry")
    op.drop_index("ix_feedback_dataset_versions_feature", table_name="feedback_dataset_versions")
    op.drop_index("ix_feedback_dataset_versions_dataset_id", table_name="feedback_dataset_versions")
    op.drop_table("feedback_dataset_versions")
    for column in ("eligible_for_training", "review_status", "feedback_label", "input_hash", "member_id", "source_entity_id", "feature", "feedback_type"):
        op.drop_index(f"ix_feedback_records_{column}", table_name="feedback_records")
    op.drop_table("feedback_records")
    op.execute("DELETE FROM knowledge_use_records WHERE knowledge_document_id IS NULL")
    with op.batch_alter_table("knowledge_use_records") as batch:
        batch.drop_column("external_chunk_ids")
        batch.alter_column("knowledge_document_id", existing_type=sa.Uuid(), nullable=False)
