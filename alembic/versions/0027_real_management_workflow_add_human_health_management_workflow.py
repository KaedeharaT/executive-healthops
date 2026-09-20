"""add human health management workflow

Revision ID: 0027_real_management_workflow
Revises: 0026_strengthen_health_baseline
Create Date: 2026-09-20 22:49:22.159752

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = '0027_real_management_workflow'
down_revision: Union[str, Sequence[str], None] = '0026_strengthen_health_baseline'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table('family_relations',
    sa.Column('id', sa.Uuid(), nullable=False),
    sa.Column('patient_id', sa.Uuid(), nullable=False),
    sa.Column('related_patient_id', sa.Uuid(), nullable=True),
    sa.Column('relationship', sa.String(length=64), nullable=False),
    sa.Column('contact_name', sa.String(length=128), nullable=False),
    sa.Column('contact', sa.String(length=200), nullable=False),
    sa.Column('emergency', sa.Boolean(), nullable=False),
    sa.Column('shared_entitlement', sa.Boolean(), nullable=False),
    sa.ForeignKeyConstraint(['patient_id'], ['patients.id'], ),
    sa.ForeignKeyConstraint(['related_patient_id'], ['patients.id'], ),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_family_relations_patient_id'), 'family_relations', ['patient_id'], unique=False)
    op.create_table('consultation_cases',
    sa.Column('id', sa.Uuid(), nullable=False),
    sa.Column('patient_id', sa.Uuid(), nullable=False),
    sa.Column('program_id', sa.Uuid(), nullable=True),
    sa.Column('encounter_id', sa.Uuid(), nullable=False),
    sa.Column('requested_at', sa.DateTime(timezone=True), nullable=False),
    sa.Column('scheduled_at', sa.DateTime(timezone=True), nullable=False),
    sa.Column('location', sa.String(length=200), nullable=False),
    sa.Column('participants', sa.JSON(), nullable=False),
    sa.Column('evidence', sa.Text(), nullable=False),
    sa.Column('status', sa.String(length=32), nullable=False),
    sa.Column('owner', sa.String(length=128), nullable=False),
    sa.Column('conclusion', sa.Text(), nullable=False),
    sa.Column('concluded_by', sa.String(length=128), nullable=True),
    sa.Column('action_drafts', sa.JSON(), nullable=False),
    sa.Column('confirmed_by', sa.String(length=128), nullable=True),
    sa.Column('confirmed_at', sa.DateTime(timezone=True), nullable=True),
    sa.ForeignKeyConstraint(['encounter_id'], ['encounters.id'], ),
    sa.ForeignKeyConstraint(['patient_id'], ['patients.id'], ),
    sa.ForeignKeyConstraint(['program_id'], ['health_programs.id'], ),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('encounter_id')
    )
    op.create_index(op.f('ix_consultation_cases_patient_id'), 'consultation_cases', ['patient_id'], unique=False)
    op.create_table('stage_reviews',
    sa.Column('id', sa.Uuid(), nullable=False),
    sa.Column('patient_id', sa.Uuid(), nullable=False),
    sa.Column('program_id', sa.Uuid(), nullable=False),
    sa.Column('phase_id', sa.Uuid(), nullable=False),
    sa.Column('content', sa.JSON(), nullable=False),
    sa.Column('decision', sa.String(length=32), nullable=False),
    sa.Column('owner', sa.String(length=128), nullable=False),
    sa.Column('reviewed_at', sa.DateTime(timezone=True), nullable=False),
    sa.ForeignKeyConstraint(['patient_id'], ['patients.id'], ),
    sa.ForeignKeyConstraint(['phase_id'], ['program_phases.id'], ),
    sa.ForeignKeyConstraint(['program_id'], ['health_programs.id'], ),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('phase_id')
    )
    op.create_index(op.f('ix_stage_reviews_patient_id'), 'stage_reviews', ['patient_id'], unique=False)
    op.create_index(op.f('ix_stage_reviews_program_id'), 'stage_reviews', ['program_id'], unique=False)
    op.create_table('intake_assessments',
    sa.Column('id', sa.Uuid(), nullable=False),
    sa.Column('patient_id', sa.Uuid(), nullable=False),
    sa.Column('cycle_year', sa.Integer(), nullable=False),
    sa.Column('version', sa.String(length=40), nullable=False),
    sa.Column('status', sa.String(length=32), nullable=False),
    sa.Column('responses', sa.JSON(), nullable=False),
    sa.Column('member_concern', sa.Text(), nullable=False),
    sa.Column('professional_focus', sa.Text(), nullable=False),
    sa.Column('review_status', sa.String(length=32), nullable=False),
    sa.Column('review', sa.JSON(), nullable=False),
    sa.Column('reviewed_by', sa.String(length=128), nullable=True),
    sa.Column('doctor_review_id', sa.Uuid(), nullable=True),
    sa.Column('submitted_at', sa.DateTime(timezone=True), nullable=True),
    sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
    sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
    sa.ForeignKeyConstraint(['doctor_review_id'], ['doctor_reviews.id'], ),
    sa.ForeignKeyConstraint(['patient_id'], ['patients.id'], ),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('patient_id', 'cycle_year', name='uq_intake_member_year')
    )
    op.create_index(op.f('ix_intake_assessments_patient_id'), 'intake_assessments', ['patient_id'], unique=False)
    op.create_table('recheck_plans',
    sa.Column('id', sa.Uuid(), nullable=False),
    sa.Column('patient_id', sa.Uuid(), nullable=False),
    sa.Column('program_id', sa.Uuid(), nullable=False),
    sa.Column('title', sa.String(length=200), nullable=False),
    sa.Column('reason', sa.Text(), nullable=False),
    sa.Column('planned_at', sa.DateTime(timezone=True), nullable=False),
    sa.Column('owner', sa.String(length=128), nullable=False),
    sa.Column('provider', sa.String(length=200), nullable=False),
    sa.Column('status', sa.String(length=32), nullable=False),
    sa.Column('result', sa.Text(), nullable=False),
    sa.Column('next_recheck_at', sa.DateTime(timezone=True), nullable=True),
    sa.Column('document_id', sa.Uuid(), nullable=True),
    sa.Column('doctor_review_id', sa.Uuid(), nullable=True),
    sa.Column('evidence', sa.Text(), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
    sa.ForeignKeyConstraint(['doctor_review_id'], ['doctor_reviews.id'], ),
    sa.ForeignKeyConstraint(['document_id'], ['documents.id'], ),
    sa.ForeignKeyConstraint(['patient_id'], ['patients.id'], ),
    sa.ForeignKeyConstraint(['program_id'], ['health_programs.id'], ),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_recheck_plans_patient_id'), 'recheck_plans', ['patient_id'], unique=False)
    op.create_index(op.f('ix_recheck_plans_planned_at'), 'recheck_plans', ['planned_at'], unique=False)
    op.create_index(op.f('ix_recheck_plans_program_id'), 'recheck_plans', ['program_id'], unique=False)
    op.create_table('management_logs',
    sa.Column('id', sa.Uuid(), nullable=False),
    sa.Column('patient_id', sa.Uuid(), nullable=False),
    sa.Column('program_id', sa.Uuid(), nullable=False),
    sa.Column('occurred_at', sa.DateTime(timezone=True), nullable=False),
    sa.Column('category', sa.String(length=40), nullable=False),
    sa.Column('channel', sa.String(length=40), nullable=False),
    sa.Column('member_issue', sa.Text(), nullable=False),
    sa.Column('manager_action', sa.Text(), nullable=False),
    sa.Column('result', sa.Text(), nullable=False),
    sa.Column('next_action', sa.Text(), nullable=False),
    sa.Column('follow_up_at', sa.DateTime(timezone=True), nullable=True),
    sa.Column('owner', sa.String(length=128), nullable=False),
    sa.Column('service_type', sa.String(length=100), nullable=False),
    sa.Column('provider', sa.String(length=200), nullable=False),
    sa.Column('department', sa.String(length=128), nullable=False),
    sa.Column('expert', sa.String(length=128), nullable=False),
    sa.Column('evidence', sa.Text(), nullable=False),
    sa.Column('related_task_id', sa.Uuid(), nullable=True),
    sa.Column('related_risk_id', sa.Uuid(), nullable=True),
    sa.Column('related_doctor_review_id', sa.Uuid(), nullable=True),
    sa.Column('related_service_id', sa.Uuid(), nullable=True),
    sa.Column('related_document_id', sa.Uuid(), nullable=True),
    sa.Column('follow_up_task_id', sa.Uuid(), nullable=True),
    sa.Column('request_key', sa.String(length=64), nullable=False),
    sa.Column('created_by', sa.String(length=128), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
    sa.ForeignKeyConstraint(['follow_up_task_id'], ['tasks.id'], ),
    sa.ForeignKeyConstraint(['patient_id'], ['patients.id'], ),
    sa.ForeignKeyConstraint(['program_id'], ['health_programs.id'], ),
    sa.ForeignKeyConstraint(['related_doctor_review_id'], ['doctor_reviews.id'], ),
    sa.ForeignKeyConstraint(['related_document_id'], ['documents.id'], ),
    sa.ForeignKeyConstraint(['related_risk_id'], ['risk_events.id'], ),
    sa.ForeignKeyConstraint(['related_service_id'], ['service_requests.id'], ),
    sa.ForeignKeyConstraint(['related_task_id'], ['tasks.id'], ),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('follow_up_task_id'),
    sa.UniqueConstraint('request_key')
    )
    op.create_index(op.f('ix_management_logs_patient_id'), 'management_logs', ['patient_id'], unique=False)
    op.create_index(op.f('ix_management_logs_program_id'), 'management_logs', ['program_id'], unique=False)
    op.add_column('health_programs', sa.Column('cycle_year', sa.Integer(), nullable=True))
    op.add_column('health_programs', sa.Column('customer_advisor', sa.String(128), nullable=True))
    op.create_index('ix_health_programs_cycle_year', 'health_programs', ['cycle_year'])
    for name, kind in [('management_content', sa.Text()), ('result_feedback', sa.Text()), ('completed_at', sa.DateTime(timezone=True)), ('owner', sa.String(128))]:
        op.add_column('program_phases', sa.Column(name, kind, nullable=True))
    with op.batch_alter_table('service_requests') as batch:
        for name, target in [('program_id','health_programs'),('phase_id','program_phases'),('management_task_id','tasks')]:
            batch.add_column(sa.Column(name, sa.Uuid(), nullable=True))
            batch.create_foreign_key('fk_service_requests_'+name, target, [name], ['id'])
        batch.create_index('ix_service_requests_program_id', ['program_id'])


def downgrade() -> None:
    with op.batch_alter_table('service_requests') as batch:
        batch.drop_index('ix_service_requests_program_id')
        for name in ['program_id','phase_id','management_task_id']:
            batch.drop_constraint('fk_service_requests_'+name, type_='foreignkey')
            batch.drop_column(name)
    for name in ['management_content','result_feedback','completed_at','owner']:
        op.drop_column('program_phases', name)
    op.drop_index('ix_health_programs_cycle_year', table_name='health_programs')
    op.drop_column('health_programs','customer_advisor')
    op.drop_column('health_programs','cycle_year')
    for name in ['management_logs','recheck_plans','intake_assessments','stage_reviews','consultation_cases','family_relations']:
        op.drop_table(name)
