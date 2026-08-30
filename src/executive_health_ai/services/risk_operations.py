"""Human operations for YELLOW observation-driven risk events.

This service records decisions made by people.  It deliberately contains no
clinical thresholds, diagnosis, prescribing, messaging connector, or LLM call.
"""
from __future__ import annotations

from datetime import datetime
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from executive_health_ai.models import AuditLog, DoctorReview, FollowUp, HealthProblem, HealthProgram, RiskEvent, RiskRule, ServiceEvent, Task
from executive_health_ai.models.base import utc_now


ACTIVE_YELLOW = {"NEW", "ACKNOWLEDGED", "IN_REVIEW", "MONITORING", "ESCALATED_TO_DOCTOR", "WAITING_MEMBER", "FOLLOW_UP"}


class RiskOperationsService:
    """One audited, explicit human action at a time for a Yellow RiskEvent."""

    @staticmethod
    def _event(session: Session, event_id: UUID, *, allow_closed: bool = False) -> RiskEvent:
        event = session.get(RiskEvent, event_id)
        if event is None:
            raise ValueError("RiskEvent not found.")
        if event.risk_level != "YELLOW":
            raise ValueError("Yellow operations are only available for YELLOW RiskEvent.")
        if not allow_closed and event.status not in ACTIVE_YELLOW:
            raise ValueError("This Yellow risk event is already closed and cannot be changed.")
        return event

    @staticmethod
    def _audit(session: Session, event: RiskEvent, actor: str, action: str, detail: dict[str, object] | None = None) -> None:
        session.add(AuditLog(
            patient_id=event.patient_id, actor=actor, actor_role="health_manager",
            action=action, entity_type="RiskEvent", entity_id=str(event.id), detail_json=detail or {},
        ))

    @staticmethod
    def _event_detail(event: RiskEvent) -> str:
        evidence = event.evidence_json or {}
        metric = event.canonical_code or evidence.get("metric") or "相关健康数据"
        matched = evidence.get("matched_count")
        return f"触发规则：{evidence.get('rule_code', '已审核风险规则')}；相关指标：{metric}" + (f"；匹配记录：{matched} 项" if matched else "")

    def acknowledge(self, session: Session, event_id: UUID, actor: str, note: str) -> RiskEvent:
        event = self._event(session, event_id)
        if event.status == "NEW":
            event.status = "ACKNOWLEDGED"
            event.acknowledged_by = actor
            event.acknowledged_at = utc_now()
            self._audit(session, event, actor, "yellow_acknowledged", {"note": note})
            session.add(ServiceEvent(patient_id=event.patient_id, event_type="yellow_risk", status="acknowledged", owner=actor, detail=note, source="risk_operations"))
        return event

    def continue_monitoring(self, session: Session, event_id: UUID, actor: str, reason: str, due_at: datetime) -> Task:
        if not reason.strip():
            raise ValueError("Monitoring reason is required.")
        if due_at is None:
            raise ValueError("Next review time is required.")
        event = self.acknowledge(session, event_id, actor, reason)
        event.status = "MONITORING"
        existing = session.scalar(select(Task).where(Task.risk_event_id == event.id, Task.status.not_in(["COMPLETED", "CANCELLED"])).order_by(Task.created_at.desc()))
        if existing is not None:
            existing.due_at = due_at
            task = existing
        else:
            program = session.scalar(select(HealthProgram).where(HealthProgram.patient_id == event.patient_id, HealthProgram.status == "ACTIVE").order_by(HealthProgram.created_at.desc()))
            task = Task(patient_id=event.patient_id, program_id=program.id if program else None, risk_event_id=event.id, title="复核需要关注的健康风险", instruction=reason, priority="MEDIUM", assignee=actor, responsible_role="health_manager", due_at=due_at, source="yellow_risk_monitoring")
            session.add(task)
            session.flush()
        self._audit(session, event, actor, "yellow_monitoring_selected", {"reason": reason, "due_at": due_at.isoformat(), "task_id": str(task.id)})
        session.add(ServiceEvent(patient_id=event.patient_id, event_type="yellow_risk_monitoring", status="scheduled", owner=actor, detail=reason, source="risk_operations"))
        return task

    def record_contact(self, session: Session, event_id: UUID, actor: str, method: str, result: str, note: str, due_at: datetime | None = None) -> RiskEvent:
        if method not in {"电话", "微信", "当面", "其他"} or result not in {"已联系", "未接通", "待回访"}:
            raise ValueError("Invalid contact record.")
        event = self.acknowledge(session, event_id, actor, note or "已记录联系成员")
        if not due_at and result in {"未接通", "待回访"}:
            event.status = "WAITING_MEMBER"
        self._audit(session, event, actor, "yellow_member_contact_recorded", {"method": method, "result": result, "note": note, "due_at": due_at.isoformat() if due_at else None})
        session.add(ServiceEvent(patient_id=event.patient_id, event_type="member_contact", status=result, owner=actor, detail=note, source="risk_operations"))
        if due_at:
            self.continue_monitoring(session, event.id, actor, f"联系成员后复核：{note or result}", due_at)
        return event

    def mark_data_issue(self, session: Session, event_id: UUID, actor: str, reason: str) -> RiskEvent:
        if not reason.strip():
            raise ValueError("Data issue reason is required.")
        event = self._event(session, event_id)
        event.status = "DISMISSED_DATA_ISSUE"
        event.resolved_at = utc_now()
        self._audit(session, event, actor, "yellow_data_issue_recorded", {"reason": reason, "original_observation_preserved": True})
        session.add(ServiceEvent(patient_id=event.patient_id, event_type="yellow_risk", status="data_issue_closed", owner=actor, detail=reason, source="risk_operations"))
        return event

    def adjust_management(self, session: Session, event_id: UUID, actor: str, adjustment: str, reason: str, due_at: datetime | None = None) -> Task:
        if not adjustment.strip() or not reason.strip():
            raise ValueError("Adjustment and reason are required.")
        event = self.acknowledge(session, event_id, actor, reason)
        program = session.scalar(select(HealthProgram).where(HealthProgram.patient_id == event.patient_id, HealthProgram.status == "ACTIVE").order_by(HealthProgram.created_at.desc()))
        task = Task(patient_id=event.patient_id, program_id=program.id if program else None, risk_event_id=event.id, title="执行健康管理调整", instruction=adjustment, priority="MEDIUM", assignee=actor, responsible_role="health_manager", due_at=due_at, source="yellow_risk_management_adjustment")
        session.add(task); session.flush()
        event.status = "IN_REVIEW"
        self._audit(session, event, actor, "yellow_management_adjusted", {"adjustment": adjustment, "reason": reason, "task_id": str(task.id)})
        return task

    def escalate_to_doctor(self, session: Session, event_id: UUID, actor: str, question: str, department: str = "全科/健康管理") -> DoctorReview:
        if not question.strip():
            raise ValueError("Question for doctor is required.")
        event = self.acknowledge(session, event_id, actor, question)
        existing = session.scalar(select(DoctorReview).where(DoctorReview.risk_event_id == event.id, DoctorReview.status == "PENDING").order_by(DoctorReview.created_at.desc()))
        if existing is not None:
            return existing
        problem = session.scalar(select(HealthProblem).where(HealthProblem.patient_id == event.patient_id, HealthProblem.source == "yellow_risk_event", HealthProblem.status != "CLOSED", HealthProblem.description.contains(str(event.id))).order_by(HealthProblem.created_at.desc()))
        if problem is None:
            program = session.scalar(select(HealthProgram).where(HealthProgram.patient_id == event.patient_id, HealthProgram.status == "ACTIVE").order_by(HealthProgram.created_at.desc()))
            problem = HealthProblem(patient_id=event.patient_id, program_id=program.id if program else None, title="需要医生复核的健康数据风险", description=f"来源：Yellow RiskEvent {event.id}。{self._event_detail(event)}。这不是系统诊断。", severity="MEDIUM", responsible_role="doctor", source="yellow_risk_event")
            session.add(problem); session.flush()
        review = DoctorReview(patient_id=event.patient_id, program_id=problem.program_id, health_problem_id=problem.id, risk_event_id=event.id, doctor_name="待分配医生", department=department, doctor_brief=self._event_detail(event), question_for_doctor=question, opinion="待医生人工填写", status="PENDING")
        session.add(review); session.flush()
        event.status = "ESCALATED_TO_DOCTOR"; event.requires_doctor_review = True
        self._audit(session, event, actor, "yellow_doctor_review_requested", {"question": question, "doctor_review_id": str(review.id), "health_problem_id": str(problem.id)})
        session.add(ServiceEvent(patient_id=event.patient_id, event_type="doctor_review", status="requested", owner=actor, detail=question, source="risk_operations"))
        return review

    def complete_doctor_review(self, session: Session, review_id: UUID, doctor: str, department: str, opinion: str, follow_up_instruction: str, due_at: datetime | None = None) -> tuple[DoctorReview, Task]:
        review = session.get(DoctorReview, review_id)
        if review is None or review.risk_event_id is None:
            raise ValueError("Yellow DoctorReview not found.")
        if review.status != "PENDING":
            raise ValueError("DoctorReview is already completed.")
        if not doctor.strip() or not opinion.strip() or not follow_up_instruction.strip():
            raise ValueError("Doctor opinion and follow-up instruction are required.")
        event = self._event(session, review.risk_event_id)
        review.doctor_name, review.department, review.opinion, review.status, review.reviewed_at = doctor, department, opinion, "CONFIRMED", utc_now()
        task = Task(patient_id=event.patient_id, program_id=review.program_id, health_problem_id=review.health_problem_id, risk_event_id=event.id, title="完成医生复核后的跟进", instruction=follow_up_instruction, priority="HIGH", assignee="health_manager", responsible_role="health_manager", due_at=due_at, source="yellow_risk_doctor_followup")
        session.add(task); session.flush()
        event.status = "FOLLOW_UP"
        self._audit(session, event, doctor, "yellow_doctor_review_completed", {"doctor_review_id": str(review.id), "task_id": str(task.id)})
        return review, task

    def record_follow_up(self, session: Session, event_id: UUID, actor: str, outcome: str, task_id: UUID | None = None) -> FollowUp:
        if not outcome.strip():
            raise ValueError("Follow-up outcome is required.")
        event = self._event(session, event_id)
        task = session.get(Task, task_id) if task_id else session.scalar(select(Task).where(Task.risk_event_id == event.id, Task.status.not_in(["COMPLETED", "CANCELLED"])).order_by(Task.created_at.desc()))
        if task is not None:
            task.status, task.completed_at = "COMPLETED", utc_now()
        review = session.scalar(select(DoctorReview).where(DoctorReview.risk_event_id == event.id).order_by(DoctorReview.created_at.desc()))
        if review is None:
            raise ValueError("A linked doctor review is required before this follow-up.")
        followup = FollowUp(patient_id=event.patient_id, health_problem_id=review.health_problem_id, task_id=task.id if task else None, status="COMPLETED", completed_at=utc_now(), outcome=outcome, reviewed_by=actor, source="yellow_risk_follow_up")
        session.add(followup); session.flush()
        event.status = "FOLLOW_UP"
        self._audit(session, event, actor, "yellow_followup_recorded", {"followup_id": str(followup.id), "task_id": str(task.id) if task else None})
        return followup

    def complete_monitoring_task(self, session: Session, event_id: UUID, actor: str, outcome: str, task_id: UUID | None = None) -> Task:
        """Complete a manager monitoring task without inventing a clinical FollowUp."""
        if not outcome.strip():
            raise ValueError("Monitoring follow-up outcome is required.")
        event = self._event(session, event_id)
        task = session.get(Task, task_id) if task_id else session.scalar(select(Task).where(Task.risk_event_id == event.id, Task.status.not_in(["COMPLETED", "CANCELLED"])).order_by(Task.created_at.desc()))
        if task is None:
            raise ValueError("No active monitoring task found.")
        task.status, task.completed_at = "COMPLETED", utc_now()
        event.status = "IN_REVIEW"
        self._audit(session, event, actor, "yellow_monitoring_followup_completed", {"task_id": str(task.id), "outcome": outcome})
        session.add(ServiceEvent(patient_id=event.patient_id, event_type="yellow_risk_monitoring", status="completed", owner=actor, detail=outcome, source="risk_operations"))
        return task

    def close(self, session: Session, event_id: UUID, actor: str, reason: str) -> RiskEvent:
        if not reason.strip():
            raise ValueError("Close reason is required.")
        event = self._event(session, event_id)
        outstanding = session.scalar(select(Task).where(Task.risk_event_id == event.id, Task.status.not_in(["COMPLETED", "CANCELLED"])).limit(1))
        if outstanding is not None:
            raise ValueError("Complete or cancel the linked follow-up task before closing this event.")
        event.status, event.resolved_at = "CLOSED", utc_now()
        self._audit(session, event, actor, "yellow_closed", {"reason": reason})
        session.add(ServiceEvent(patient_id=event.patient_id, event_type="yellow_risk", status="closed", owner=actor, detail=reason, source="risk_operations"))
        return event
