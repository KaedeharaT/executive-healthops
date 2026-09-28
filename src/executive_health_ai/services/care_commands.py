"""Transactional UI/API commands over existing human-reviewed care services.

Callers own the transaction. No parallel UI-only facts or workflow models.
"""
import os
from sqlalchemy import select
from executive_health_ai.models import HealthJourney, HealthProgram
from executive_health_ai.services import chronic_care as care


def publish_progress(session, *, event_type, member_id, source_type, source_id, summary, actor):
    if not any(os.getenv(name, "false").lower() in {"1", "true", "yes"} for name in ("AGENT_SUPERVISOR_ENABLED", "PORTFOLIO_DEMO")):
        return
    from executive_health_ai.services.event_service import EventService
    from executive_health_ai.agent.supervisor import HealthOpsAgentSupervisor
    event, _ = EventService().publish(session, event_type=event_type, member_id=member_id, source_type=source_type, source_id=str(source_id), payload_summary=summary, metadata={"actor": actor})
    HealthOpsAgentSupervisor().receive_event(session, event)


def record_outcome(session, program, **values):
    for field in ("metric", "baseline_value", "current_value", "evaluator", "evidence"):
        if not str(values.get(field, "")).strip():
            raise ValueError("请填写指标、前后数值、记录人和结果依据。")
    outcome = care.record_outcome_evaluation(session, program, **values)
    publish_progress(session, event_type="OUTCOME_RECORDED", member_id=program.patient_id, source_type="outcome", source_id=outcome.id, summary="阶段结果已人工回写", actor=values["evaluator"])
    return outcome


def confirm_report_candidate(session, candidate, actor):
    """UI/API share the existing confirm → baseline draft → progress path."""
    from sqlalchemy import func
    from executive_health_ai.models import ReportExtractionCandidate
    from executive_health_ai.services.report_parsing import ReportParsingService
    from executive_health_ai.services.longitudinal import HealthAssessmentService
    observation = ReportParsingService().confirm_candidate(session, candidate, actor)
    pending = session.scalar(select(func.count(ReportExtractionCandidate.id)).where(
        ReportExtractionCandidate.document_id == candidate.document_id,
        ReportExtractionCandidate.status == "PENDING_REVIEW"))
    if not pending:
        try:
            HealthAssessmentService().create_draft_from_report(session, candidate.patient_id, candidate.document_id, created_by=actor)
        except ValueError as error:
            # A frozen baseline is never overwritten when another report arrives.
            if "正式健康基线" not in str(error):
                raise
        publish_progress(session, event_type="REPORT_CONFIRMED", member_id=candidate.patient_id,
            source_type="document", source_id=candidate.document_id,
            summary="体检报告候选资料已完成人工确认", actor=actor)
    return observation


def save_program(session, patient_id, *, title, goal, owner, start, end, program_id=None, program_type="NINETY_DAY", reason="", assessment_risk=None):
    if not all(str(v).strip() for v in (title, goal, owner)) or end < start:
        raise ValueError("请填写计划名称、目标和负责人，结束日期不能早于开始日期。")
    if program_id:
        program = session.get(HealthProgram, program_id)
        if program is None or program.patient_id != patient_id:
            raise ValueError("未找到此成员的计划。")
        if not reason.strip():
            raise ValueError("调整计划需要填写原因。")
        before = {"title": program.title, "goal": program.main_goal, "owner": program.owner}
        program.title, program.main_goal, program.owner = title.strip(), goal.strip(), owner.strip()
        # Dates of existing phase plans remain fixed; rescheduling is a separate workflow.
        care._audit(session, patient_id, owner, "health_manager", "adjusted_health_program", program, {"reason": reason.strip(), "before": before})
        care.record_weekly_review(session, program, 1, "人工调整", "按已有资料核对", reason.strip(), goal.strip(), owner, adjustment=reason.strip())
        return program
    journey = session.scalar(select(HealthJourney).where(HealthJourney.patient_id == patient_id).order_by(HealthJourney.updated_at.desc()))
    if journey is None:
        if assessment_risk not in care.RISK_LEVELS:
            raise ValueError("首次计划需由健康管理师明确人工评估层级。")
        journey = care.create_assessment(session, patient_id, reason or goal, goal, assessment_risk, [], {}, owner)
    return care.create_program(session, journey, program_type, title, goal, [], start, owner, end_date=end)


def schedule_followup(session, program, *, title, instruction, due_at, owner, role="health_manager"):
    if not all(str(v).strip() for v in (title, instruction, owner)):
        raise ValueError("请填写行动、执行说明和负责人。")
    if role not in {"member", "health_manager"}:
        raise ValueError("请选择成员或健康管理师。")
    task = care.create_program_task(session, program, title.strip(), instruction.strip(), due_at, owner.strip(), "健康管理师")
    task.responsible_role = role
    return task


def complete_review(session, review, doctor, department, opinion, instruction, due_at):
    from executive_health_ai.services.risk_operations import RiskOperationsService
    if review is None:
        raise ValueError("未找到待复核事项。")
    from executive_health_ai.models import AgentGoal
    for profile_goal in session.scalars(select(AgentGoal).where(AgentGoal.member_id==review.patient_id, AgentGoal.goal_type=='PROFILE_INTAKE')):
        if profile_goal.context_json.get('review_id')==str(review.id):
            from executive_health_ai.services.profile_ingestion import ProfileIngestionService
            return ProfileIngestionService().complete_review(session,profile_goal,review,doctor,department,opinion,instruction)
    from executive_health_ai.agent.post_checkup import goal_for_review
    care_goal = goal_for_review(session, review.id, review.patient_id)
    if care_goal:
        from executive_health_ai.services.post_checkup import PostCheckupCareService
        PostCheckupCareService().submit_review(session, care_goal, actor=doctor, role='DOCTOR',
            judgement=opinion, recommendation=instruction, recheck=False, suggested_date=due_at.date())
        return review, None
    if review.risk_event_id:
        stored, task = RiskOperationsService().complete_doctor_review(session, review.id, doctor, department, opinion, instruction, due_at)
    else:
        task = care.complete_outcome_doctor_review(session, review, doctor, department, opinion, instruction, due_at)
        stored = review
    publish_progress(session, event_type="DOCTOR_REVIEW_COMPLETED", member_id=stored.patient_id, source_type="doctor_review", source_id=stored.id, summary="医生已完成人工医学复核", actor=doctor)
    from executive_health_ai.models.management_workflow import IntakeAssessment
    intake = session.scalar(select(IntakeAssessment).where(IntakeAssessment.patient_id == stored.patient_id,
        IntakeAssessment.doctor_review_id == stored.id))
    if intake:
        from executive_health_ai.services.management_workflow import task as management_task
        from executive_health_ai.models.base import utc_now
        program = session.scalar(select(HealthProgram).where(HealthProgram.patient_id == stored.patient_id, HealthProgram.cycle_year == intake.cycle_year))
        management_task(session, stored.patient_id, program.id if program else None, "接收医生复核结论", "核对医生结论，确认后续执行事项和负责人。", program.owner if program else "健康管理师", utc_now(), f"doctor_handoff:{stored.id}")
    return stored, task
