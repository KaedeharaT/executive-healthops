"""Task-oriented read model for the HealthOps home page.

The worklist is deliberately a transient UI aggregation.  It never changes
clinical records and keeps the existing RiskEvent, ManagementSignal, Task and
DoctorReview workflows as their respective sources of truth.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from executive_health_ai.models import ManagementSignal, RiskEvent, Task, ServiceCatalogItem, ServiceRequest


ACTIVE_RISK_STATUSES = (
    "NEW", "ACKNOWLEDGED", "IN_REVIEW", "MONITORING", "ESCALATED_TO_DOCTOR", "FOLLOW_UP", "ESCALATED",
)
OPEN_TASK_STATUSES = ("COMPLETED", "CANCELLED")


@dataclass(frozen=True)
class OperationalWorkItem:
    """A small, display-ready item with one source entity and one next action."""

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


class OperationalWorklistService:
    """Compose the daily queue without materialising another workflow table."""

    def list_items(self, session: Session, now: datetime) -> list[OperationalWorkItem]:
        items: list[OperationalWorkItem] = []
        risk_events = session.scalars(
            select(RiskEvent)
            .where(RiskEvent.status.in_(ACTIVE_RISK_STATUSES))
            .order_by(RiskEvent.created_at.desc())
            .limit(50)
        )
        for event in risk_events:
            if event.risk_level == "RED":
                items.append(OperationalWorkItem(event.patient_id, "risk_event", event.id, 0, "高风险", event.summary, "健康数据需要立即人工核实", "立即处理", event.created_at))
            elif event.risk_level == "YELLOW" and event.status == "NEW":
                items.append(OperationalWorkItem(event.patient_id, "risk_event", event.id, 1, "中风险", event.summary, "健康数据触发了已审核规则", "接手并核实", event.created_at))
            elif event.status == "ESCALATED_TO_DOCTOR":
                items.append(OperationalWorkItem(event.patient_id, "risk_event", event.id, 4, "等待医生", event.summary, "已提交内部医生复核", "等待医生意见", event.created_at))

        tasks = session.scalars(
            select(Task)
            .where(Task.status.not_in(OPEN_TASK_STATUSES))
            .order_by(Task.due_at, Task.created_at.desc())
            .limit(100)
        )
        for task in tasks:
            if task.due_at is not None and task.due_at.date() > now.date():
                continue
            status = "今日跟进" if task.due_at is None or task.due_at.date() == now.date() else "逾期"
            document_id = None
            if task.source.startswith("member_report_upload:"):
                try:
                    document_id = UUID(task.source.rsplit(":", 1)[1])
                except (ValueError, IndexError):
                    document_id = None
                status = "待处理"
                comparison_path = "长期比较" in task.instruction
                next_action = "审核报告并进入长期比较" if comparison_path else "审核报告并建立健康基线"
                items.append(OperationalWorkItem(task.patient_id, "report_review", task.id, 1, status, task.title, "成员上传的新体检报告已完成自动整理", next_action, task.due_at, document_id))
                continue
            items.append(OperationalWorkItem(task.patient_id, "task", task.id, 2 if status == "逾期" else 3, status, task.title, task.instruction, "完成跟进", task.due_at))

        signals = session.scalars(
            select(ManagementSignal)
            .where(ManagementSignal.status.in_(("OPEN", "IN_PROGRESS")))
            .order_by(ManagementSignal.last_detected_at.desc())
            .limit(50)
        )
        for signal in signals:
            items.append(OperationalWorkItem(signal.patient_id, "management_signal", signal.id, 5, "建议健康管理", signal.summary, "近期生活方式数据出现需要关注的变化", "查看趋势并决定跟进", signal.last_detected_at))

        requests = session.scalars(select(ServiceRequest).where(ServiceRequest.status.in_(("REQUESTED", "APPROVED", "SCHEDULED", "IN_PROGRESS"))).order_by(ServiceRequest.requested_at.desc()).limit(50))
        for request in requests:
            item = session.get(ServiceCatalogItem, request.service_item_id)
            title = f"{item.name if item else '会员服务'}待安排"
            items.append(OperationalWorkItem(request.patient_id, "service_request", request.id, 2, "待处理", title, request.reason, "确认并安排服务", request.scheduled_at or request.requested_at))

        return sorted(items, key=lambda item: (item.priority, item.due_at or now, item.title))
