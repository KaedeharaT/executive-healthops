"""Task-oriented, de-duplicated read model for the HealthOps daily queue."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from executive_health_ai.models import DoctorReview, ManagementSignal, RiskEvent, ServiceCatalogItem, ServiceRequest, Task


ACTIVE_RISK_STATUSES = (
    "NEW", "ACKNOWLEDGED", "IN_REVIEW", "MONITORING", "ESCALATED_TO_DOCTOR", "WAITING_MEMBER", "FOLLOW_UP", "ESCALATED",
)
CLOSED_TASK_STATUSES = ("COMPLETED", "CANCELLED")


@dataclass(frozen=True)
class OperationalWorkItem:
    """One user-facing responsibility, regardless of its backing record."""

    member_id: UUID
    source_type: str
    source_id: UUID
    priority: int
    status: str
    title: str
    reason: str
    next_action: str
    due_at: datetime | None
    document_id: UUID | None = None
    owner: str = "待分配"
    route_target: str = "member_overview"
    created_at: datetime | None = None
    event_at: datetime | None = None

    @property
    def summary(self) -> str:
        return self.reason


def _risk_state(event: RiskEvent, review: DoctorReview | None, task: Task | None) -> tuple[int, str, str, str]:
    """Translate persistence status into the single operational state users act on."""
    owner = (task.assignee if task and task.assignee else None) or event.acknowledged_by or "健康管理师"
    if event.risk_level == "RED":
        if event.status == "NEW":
            return 0, "高风险", "立即人工核实并记录已接手", "待分配"
        return 0, "处理中", "确认人工紧急处置与后续医疗安排", owner
    if event.status == "NEW":
        return 1, "中风险", "接手并核实", "待分配"
    if event.status == "ESCALATED_TO_DOCTOR":
        doctor = review.doctor_name if review and review.doctor_name and review.doctor_name != "待分配医生" else "内部医生"
        return 4, "等待医生", "等待医生复核；健管跟踪交接", doctor
    if event.status == "WAITING_MEMBER":
        return 2, "等待成员", "等待成员补充或回复后继续复核", owner
    if event.status == "FOLLOW_UP":
        return 1, "待随访", task.instruction if task else "执行医生建议并记录随访", owner
    if event.status == "MONITORING":
        return 2, "处理中", task.instruction if task else "按期复核健康数据", owner
    if event.status == "ACKNOWLEDGED":
        return 2, "已接手", "联系成员或安排下一次复核", owner
    if event.status == "IN_REVIEW":
        return 2, "处理中", task.instruction if task else "完成健康管理调整", owner
    return 2, "处理中", "确认下一步人工处理", owner


class OperationalWorklistService:
    """Compose today's queue without materialising a second workflow table.

    RiskEvents remain the main work item when they own Tasks or DoctorReviews;
    linked rows enrich that responsibility rather than creating duplicates.
    """

    def list_items(self, session: Session, now: datetime) -> list[OperationalWorkItem]:
        items: list[OperationalWorkItem] = []
        active_tasks = list(session.scalars(select(Task).where(Task.status.not_in(CLOSED_TASK_STATUSES)).order_by(Task.due_at, Task.created_at.desc()).limit(150)))
        tasks_by_risk: dict[UUID, Task] = {}
        for task in active_tasks:
            if task.risk_event_id:
                tasks_by_risk.setdefault(task.risk_event_id, task)
        pending_reviews = list(session.scalars(select(DoctorReview).where(DoctorReview.status == "PENDING").order_by(DoctorReview.created_at.desc()).limit(100)))
        reviews_by_risk = {review.risk_event_id: review for review in pending_reviews if review.risk_event_id}

        active_risks = list(session.scalars(select(RiskEvent).where(RiskEvent.status.in_(ACTIVE_RISK_STATUSES)).order_by(RiskEvent.created_at.desc()).limit(100)))
        active_risk_ids = {event.id for event in active_risks}
        for event in active_risks:
            task, review = tasks_by_risk.get(event.id), reviews_by_risk.get(event.id)
            priority, status, next_action, owner = _risk_state(event, review, task)
            items.append(OperationalWorkItem(
                event.patient_id, "risk_event", event.id, priority, status, event.summary,
                "演示风险规则触发，需由人工核实。" if (event.evidence_json or {}).get("demo_flag") else "健康数据触发了已审核规则，需要人工核实。",
                next_action, task.due_at if task else None, owner=owner, route_target="member_risk",
                created_at=event.created_at, event_at=event.created_at,
            ))

        # A risk-linked task belongs to its primary risk item. All other tasks
        # remain independently actionable, including report and plan choices.
        for task in active_tasks:
            if task.risk_event_id in active_risk_ids:
                continue
            if task.due_at is not None and task.due_at.date() > now.date() and task.source != "member_plan_choice":
                continue
            is_overdue = bool(task.due_at and task.due_at.date() < now.date())
            status = "逾期" if is_overdue else "今日跟进"
            if task.source.startswith("member_report_upload:"):
                try:
                    document_id = UUID(task.source.rsplit(":", 1)[1])
                except (ValueError, IndexError):
                    document_id = None
                items.append(OperationalWorkItem(
                    task.patient_id, "report_review", task.id, 1, "待处理", task.title,
                    "成员上传的新体检报告已完成整理，等待健康管理团队核对。",
                    "审核报告并建立健康基线" if "建立健康基线" in task.instruction else "审核报告并进入长期比较",
                    task.due_at, document_id, task.assignee or "健康管理师", "report_review", task.created_at, task.created_at,
                ))
                continue
            if task.source == "member_plan_choice":
                status = "待处理" if task.responsible_role == "health_manager" else "今日跟进"
            items.append(OperationalWorkItem(
                task.patient_id, "task", task.id, 2 if is_overdue else 3, status, task.title, task.instruction,
                "完成跟进" if task.responsible_role == "member" else task.instruction,
                task.due_at, owner=task.assignee or "待分配", route_target="member_management",
                created_at=task.created_at, event_at=task.created_at,
            ))

        # Non-risk doctor reviews should be discoverable to the care team but
        # are not duplicated when the primary risk item already represents it.
        for review in pending_reviews:
            if review.risk_event_id in active_risk_ids:
                continue
            items.append(OperationalWorkItem(
                review.patient_id, "doctor_review", review.id, 4, "等待医生", "医生复核：" + (review.question_for_doctor or "需要医学判断"),
                review.doctor_brief or "健康管理师已提交需要医生判断的资料。", "等待医生复核", None,
                owner=review.doctor_name if review.doctor_name != "待分配医生" else "内部医生",
                route_target="doctor_review", created_at=review.created_at, event_at=review.created_at,
            ))

        signals = session.scalars(select(ManagementSignal).where(ManagementSignal.status.in_(("OPEN", "IN_PROGRESS"))).order_by(ManagementSignal.last_detected_at.desc()).limit(50))
        for signal in signals:
            items.append(OperationalWorkItem(
                signal.patient_id, "management_signal", signal.id, 5, "建议健康管理", signal.summary,
                "近期生活方式数据出现需要关注的变化，不等同于医学风险。", "查看趋势并决定跟进", signal.last_detected_at,
                owner="健康管理师", route_target="member_health", created_at=signal.last_detected_at, event_at=signal.last_detected_at,
            ))

        requests = session.scalars(select(ServiceRequest).where(ServiceRequest.status.in_(("REQUESTED", "REVIEWING", "APPROVED", "SCHEDULED", "IN_PROGRESS"))).order_by(ServiceRequest.requested_at.desc()).limit(50))
        for request in requests:
            catalog = session.get(ServiceCatalogItem, request.service_item_id)
            if request.status == "REQUESTED":
                status, next_action = "待处理", "审核服务申请"
            elif request.status == "APPROVED":
                status, next_action = "已通过", "安排服务时间"
            elif request.status == "SCHEDULED":
                status, next_action = "已安排", "确认服务开始"
            else:
                status, next_action = "服务中", "记录服务结果"
            items.append(OperationalWorkItem(
                request.patient_id, "service_request", request.id, 3, status, f"{catalog.name if catalog else '会员服务'}",
                request.reason or "成员服务申请", next_action, request.scheduled_at or request.requested_at,
                owner=request.assigned_manager or "待分配", route_target="member_service",
                created_at=request.requested_at, event_at=request.scheduled_at or request.requested_at,
            ))

        return sorted(items, key=lambda item: (item.priority, item.due_at or now, item.event_at or now, item.title))
