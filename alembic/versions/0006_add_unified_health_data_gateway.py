"""Add unified health-data gateway provenance and ingestion jobs.

Revision ID: 0006_add_unified_health_data_gateway
Revises: 0005_add_chronic_care_program_operations
Create Date: 2026-08-15
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "0006_add_unified_health_data_gateway"
down_revision: Union[str, Sequence[str], None] = "0005_add_chronic_care_program_operations"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _id() -> sa.Uuid:
    return sa.Uuid()


def upgrade() -> None:
    op.create_table("ingestion_jobs", sa.Column("id", _id(), primary_key=True), sa.Column("source_system", sa.String(128), nullable=False), sa.Column("source_type", sa.String(32), nullable=False), sa.Column("patient_id", _id()), sa.Column("status", sa.String(32), nullable=False), sa.Column("records_received", sa.Integer(), nullable=False), sa.Column("records_valid", sa.Integer(), nullable=False), sa.Column("records_invalid", sa.Integer(), nullable=False), sa.Column("records_duplicate", sa.Integer(), nullable=False), sa.Column("records_created", sa.Integer(), nullable=False), sa.Column("records_updated", sa.Integer(), nullable=False), sa.Column("error_count", sa.Integer(), nullable=False), sa.Column("created_by", sa.String(128), nullable=False), sa.Column("started_at", sa.DateTime(timezone=True), nullable=False), sa.Column("completed_at", sa.DateTime(timezone=True)), sa.Column("created_at", sa.DateTime(timezone=True), nullable=False), sa.ForeignKeyConstraint(["patient_id"], ["patients.id"]))
    for name, cols in (("ix_ingestion_jobs_source_system", ["source_system"]), ("ix_ingestion_jobs_patient_id", ["patient_id"]), ("ix_ingestion_jobs_status", ["status"])): op.create_index(name, "ingestion_jobs", cols)
    op.create_table("external_identities", sa.Column("id", _id(), primary_key=True), sa.Column("patient_id", _id(), nullable=False), sa.Column("provider", sa.String(128), nullable=False), sa.Column("external_id", sa.String(256), nullable=False), sa.Column("identity_type", sa.String(64), nullable=False), sa.Column("status", sa.String(32), nullable=False), sa.Column("created_at", sa.DateTime(timezone=True), nullable=False), sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False), sa.ForeignKeyConstraint(["patient_id"], ["patients.id"]), sa.UniqueConstraint("provider", "external_id", name="uq_external_identity_provider_value"))
    op.create_index("ix_external_identities_patient_id", "external_identities", ["patient_id"])
    op.create_table("raw_ingestion_records", sa.Column("id", _id(), primary_key=True), sa.Column("job_id", _id(), nullable=False), sa.Column("patient_id", _id()), sa.Column("raw_data_id", _id()), sa.Column("source_system", sa.String(128), nullable=False), sa.Column("source_type", sa.String(32), nullable=False), sa.Column("source_record_id", sa.String(256), nullable=False), sa.Column("payload_json", sa.JSON(), nullable=False), sa.Column("observed_at", sa.DateTime(timezone=True)), sa.Column("received_at", sa.DateTime(timezone=True), nullable=False), sa.Column("adapter_name", sa.String(128), nullable=False), sa.Column("adapter_version", sa.String(64), nullable=False), sa.Column("status", sa.String(32), nullable=False), sa.Column("error_message", sa.Text()), sa.Column("normalization_json", sa.JSON(), nullable=False), sa.Column("created_at", sa.DateTime(timezone=True), nullable=False), sa.ForeignKeyConstraint(["job_id"], ["ingestion_jobs.id"]), sa.ForeignKeyConstraint(["patient_id"], ["patients.id"]), sa.ForeignKeyConstraint(["raw_data_id"], ["raw_data.id"]), sa.UniqueConstraint("job_id", "source_record_id", name="uq_ingestion_job_source_record"))
    for name, cols in (("ix_raw_ingestion_records_job_id", ["job_id"]), ("ix_raw_ingestion_records_patient_id", ["patient_id"]), ("ix_raw_ingestion_records_status", ["status"])): op.create_index(name, "raw_ingestion_records", cols)
    with op.batch_alter_table("observations") as batch:
        batch.drop_constraint("ck_observations_quality_flag", type_="check")
        batch.add_column(sa.Column("ingestion_job_id", _id()))
        batch.add_column(sa.Column("source_record_id", sa.String(256)))
        batch.add_column(sa.Column("quality_notes", sa.String(512)))
        batch.create_index("ix_observations_ingestion_job_id", ["ingestion_job_id"])
        batch.create_foreign_key("fk_observations_ingestion_job_id", "ingestion_jobs", ["ingestion_job_id"], ["id"])
        batch.create_check_constraint("ck_observations_quality_flag", "quality_flag IN ('valid', 'questionable', 'invalid', 'missing_context', 'suspect', 'duplicate', 'manually_corrected')")


def downgrade() -> None:
    with op.batch_alter_table("observations") as batch:
        batch.drop_constraint("fk_observations_ingestion_job_id", type_="foreignkey")
        batch.drop_index("ix_observations_ingestion_job_id")
        batch.drop_column("quality_notes"); batch.drop_column("source_record_id"); batch.drop_column("ingestion_job_id")
    op.drop_table("raw_ingestion_records"); op.drop_table("external_identities"); op.drop_table("ingestion_jobs")
