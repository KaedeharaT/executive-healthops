"""Human-operated member service catalogue, requests and entitlement usage."""
from __future__ import annotations
from datetime import datetime, timedelta, timezone
from uuid import UUID
from sqlalchemy import select
from sqlalchemy.orm import Session
from executive_health_ai.models import AuditLog, HealthProgram, MemberEntitlement, MemberPlanChoice, ServiceCatalogItem, ServicePlan, ServicePlanItem, ServiceRequest, Task

DEMO_CATALOG = (
    ("health_archive", "健管服务", "健康档案数字化管理", "长期整理已确认健康资料", False, None),
    ("health_check_design", "健管服务", "高端体检个性化定制", "由健康管理团队协助整理体检安排", False, 1),
    ("monitoring", "健管服务", "数据监测", "持续查看已连接健康数据", False, None),
    ("medication_reminder", "健管服务", "用药提醒", "根据已确认用药记录安排提醒", False, None),
    ("regular_followup", "健管服务", "定期随访", "由健康管理团队安排后续跟进", False, None),
    ("lifestyle_survey", "健管服务", "生活调研", "协助了解生活方式和健康管理需求", False, 1),
    ("disease_analysis", "健管服务", "疾病动态分析", "汇总已确认健康资料供人工查看", False, None),
    ("outcome_analysis", "健管服务", "管理成效分析", "整理阶段性变化和执行情况", False, None),
    ("lifestyle_intervention", "健管服务", "生活方式干预", "由健康管理团队提供执行支持", False, None),
    ("stress_assessment", "健管服务", "精神压力评估", "由专业人员安排评估与支持", False, 1),
    ("mdt", "精准诊疗", "MDT多学科会诊", "需要多学科进一步评估时，由人工审核后安排", True, 1),
    ("home_consultation", "精准诊疗", "上门咨询", "由健康管理团队安排的到访咨询", True, 2),
    ("home_manager", "精准诊疗", "上门回访服务（健康管理师）", "由健康管理师安排的到访服务", True, 4),
    ("green_channel", "就医协助", "绿通资源", "由人工审核需求和权益后协助安排", True, 1),
    ("appointment", "就医协助", "预约挂号", "由健康管理团队协助预约", True, 2),
    ("expert_coordination", "就医协助", "名医协调", "由健康管理团队协助沟通与安排", True, 1),
    ("exam_booking", "就医协助", "检查预约", "由人工审核后协助安排检查", True, 2),
    ("exam_coordination", "就医协助", "检查协调", "协助处理检查前后的服务安排", True, 2),
    ("medical_accompaniment", "就医协助", "就医陪诊", "由人工确认服务安排", True, 2),
    ("prescription_delivery", "就医协助", "药物代配", "仅协助已确认处方的履约安排", True, 2),
    ("hospital_coordination", "就医协助", "住院协调", "人工审核权益与必要性后安排", True, 1),
    ("surgery_coordination", "就医协助", "手术协调", "人工审核权益与必要性后安排", True, 1),
    ("consultation", "远程问诊", "健康咨询", "健康管理团队协助安排", False, None),
    ("remote_consultation", "远程问诊", "远程问诊", "由人工确认后协助安排医生服务", True, 2),
    ("membership_support", "会员权益", "会员健康权益咨询", "帮助了解当前服务计划与可申请权益", False, None),
)


def bp_service_category(item: ServiceCatalogItem) -> str:
    """Present the existing catalogue through the four BP delivery families."""
    if item.code in {"health_archive", "health_check_design", "lifestyle_survey", "stress_assessment"}:
        return "评估与建档"
    if item.category == "就医协助":
        return "就医协调"
    if item.category in {"精准诊疗", "远程问诊"}:
        return "专业协作"
    return "连续管理"


class MemberServiceOperations:
    def ensure_demo_plan(self, session: Session, member_id: UUID) -> ServicePlan:
        plan = session.scalar(select(ServicePlan).where(ServicePlan.name == "金卡会员（演示）"))
        if plan is None:
            plan = ServicePlan(name="金卡会员（演示）", description="Synthetic / Demo 服务计划；不含真实价格或合同权益。", status="DEMO", version="demo-v1")
            session.add(plan); session.flush()
        # Reconcile the prototype catalogue for an already-created local demo
        # plan as well.  This is additive: existing entitlements, requests and
        # quota consumption remain untouched.
        existing_items = {item.code: item for item in session.scalars(select(ServiceCatalogItem)).all()}
        existing_plan_items = {
            item.service_item_id for item in session.scalars(select(ServicePlanItem).where(ServicePlanItem.service_plan_id == plan.id)).all()
        }
        for code, category, name, description, major, quota in DEMO_CATALOG:
            item = existing_items.get(code)
            if item is None:
                item = ServiceCatalogItem(code=code, category=category, name=name, description=description, is_major_timeline_service=major, status="DEMO")
                session.add(item); session.flush()
            if item.id not in existing_plan_items:
                session.add(ServicePlanItem(service_plan_id=plan.id, service_item_id=item.id, included=True, quota_type="COUNT" if quota else "UNLIMITED", included_quantity=quota, notes="DEMO"))
        items = list(session.scalars(select(ServicePlanItem).where(ServicePlanItem.service_plan_id == plan.id)))
        for plan_item in items:
            existing = session.scalar(select(MemberEntitlement).where(MemberEntitlement.patient_id == member_id, MemberEntitlement.service_item_id == plan_item.service_item_id))
            if existing is None:
                session.add(MemberEntitlement(patient_id=member_id, service_plan_id=plan.id, service_item_id=plan_item.service_item_id, total_quota=plan_item.included_quantity, status="ACTIVE"))
        session.flush(); return plan

    def member_services(self, session: Session, member_id: UUID) -> list[tuple[ServiceCatalogItem, MemberEntitlement]]:
        return list(session.execute(select(ServiceCatalogItem, MemberEntitlement).join(MemberEntitlement, MemberEntitlement.service_item_id == ServiceCatalogItem.id).where(MemberEntitlement.patient_id == member_id, MemberEntitlement.status == "ACTIVE").order_by(ServiceCatalogItem.category, ServiceCatalogItem.name)))

    def request(self, session: Session, member_id: UUID, item_id: UUID, reason: str, requested_by: str = "member") -> ServiceRequest:
        existing = session.scalar(select(ServiceRequest).where(ServiceRequest.patient_id == member_id, ServiceRequest.service_item_id == item_id, ServiceRequest.status.in_(("REQUESTED", "REVIEWING", "APPROVED", "SCHEDULED", "IN_PROGRESS", "IN_SERVICE"))))
        if existing: return existing
        request = ServiceRequest(
            patient_id=member_id, service_item_id=item_id, requested_by=requested_by,
            reason=reason.strip() or "成员申请服务", status="REQUESTED",
            sla_due_at=datetime.now(timezone.utc) + timedelta(days=3),
            next_action="健康管理师审核服务需求与权益",
        )
        session.add(request); session.flush(); return request

    def approve(self, session: Session, request_id: UUID, manager: str) -> ServiceRequest:
        request = session.get(ServiceRequest, request_id)
        if request is None: raise ValueError("服务申请不存在")
        if request.status not in {"REQUESTED", "REVIEWING"}: return request
        request.status = "APPROVED"
        request.assigned_manager = manager
        request.next_action = "确认服务执行方与预约时间"
        session.flush(); return request

    def schedule(self, session: Session, request_id: UUID, at: datetime, manager: str, provider: str | None = None) -> ServiceRequest:
        request = self.approve(session, request_id, manager)
        request.status, request.scheduled_at = "SCHEDULED", at
        request.service_provider = provider.strip() if provider and provider.strip() else request.service_provider
        request.next_action = "按预约安排开始服务"
        session.flush(); return request

    def start(self, session: Session, request_id: UUID, manager: str) -> ServiceRequest:
        request = session.get(ServiceRequest, request_id)
        if request is None:
            raise ValueError("服务申请不存在")
        if request.status not in {"SCHEDULED", "IN_PROGRESS", "IN_SERVICE"}:
            raise ValueError("请先安排服务后再记录执行")
        request.status, request.assigned_manager = "IN_SERVICE", manager
        request.next_action = "完成服务并回写结果与依据"
        session.flush(); return request

    def cancel(self, session: Session, request_id: UUID, reason: str = "成员取消申请") -> ServiceRequest:
        request = session.get(ServiceRequest, request_id)
        if request is None:
            raise ValueError("服务申请不存在")
        if request.status in {"COMPLETED", "CANCELLED"}:
            raise ValueError("当前服务申请不能取消")
        request.status = "CANCELLED"
        request.result_summary = reason.strip() or "服务申请已取消。"
        request.next_action = "如仍有需要，可重新申请或由健康管理师协调改期"
        session.flush(); return request

    def complete(
        self, session: Session, request_id: UUID, result_summary: str, manager: str,
        *, completion_evidence: str | None = None, next_action: str | None = None,
    ) -> ServiceRequest:
        request = session.get(ServiceRequest, request_id)
        if request is None: raise ValueError("服务申请不存在")
        if request.status == "COMPLETED": return request
        if request.status not in {"IN_PROGRESS", "IN_SERVICE"}:
            raise ValueError("请先审核服务申请后再记录完成")
        request.status = "COMPLETED"
        request.completed_at = datetime.now(timezone.utc)
        request.result_summary = result_summary.strip() or "服务已完成，后续由健康管理团队跟进。"
        request.completion_evidence = (completion_evidence or "人工确认的服务完成记录").strip()
        request.next_action = (next_action or "健康管理师复核服务结果并确认后续安排").strip()
        request.assigned_manager = manager
        entitlement = session.scalar(select(MemberEntitlement).where(MemberEntitlement.patient_id == request.patient_id, MemberEntitlement.service_item_id == request.service_item_id))
        if entitlement and entitlement.total_quota is not None: entitlement.used_quota = min(entitlement.total_quota, entitlement.used_quota + 1)
        existing_followup = session.scalar(select(Task).where(
            Task.patient_id == request.patient_id,
            Task.source == f"service_result:{request.id}",
            Task.status.not_in(("COMPLETED", "CANCELLED")),
        ))
        if existing_followup is None:
            session.add(Task(
                patient_id=request.patient_id, health_problem_id=request.related_problem_id,
                risk_event_id=request.related_risk_event_id,
                title="复核服务结果与下一步", instruction=request.next_action,
                status="PENDING", priority="MEDIUM", assignee=manager,
                responsible_role="health_manager",
                due_at=datetime.now(timezone.utc) + timedelta(days=7),
                source=f"service_result:{request.id}",
            ))
        session.add(AuditLog(
            patient_id=request.patient_id, actor=manager, actor_role="health_manager",
            action="completed_service_with_result", entity_type="ServiceRequest",
            entity_id=str(request.id), detail_json={"next_action": request.next_action, "evidence_recorded": True},
        ))
        session.flush(); return request

    def record_choice(self, session: Session, member_id: UUID, choice: str, comment: str = "") -> MemberPlanChoice:
        """Record a member decision and create the human next action it requires.

        A choice is never just a button acknowledgement: it either changes the
        current programme state or creates a visible HealthOps task.  It does
        not make a medical decision or alter a treatment plan.
        """
        if choice not in {"接受方案", "希望调整", "暂缓", "和健康管理师讨论"}:
            raise ValueError("不支持的方案选择")
        row = MemberPlanChoice(patient_id=member_id, proposal="持续监测 + 健康管理跟进（演示建议）", recommended_by="health_manager", reason="基于已确认健康资料与服务安排，不构成医学诊断。", member_choice=choice, member_comment=comment)
        session.add(row); session.flush()
        program = session.scalar(select(HealthProgram).where(
            HealthProgram.patient_id == member_id,
            HealthProgram.status.in_(("ACTIVE", "PLANNED", "PAUSED")),
        ).order_by(HealthProgram.created_at.desc()))
        existing = session.scalar(select(Task).where(
            Task.patient_id == member_id,
            Task.source == "member_plan_choice",
            Task.status.not_in(("COMPLETED", "CANCELLED")),
        ).order_by(Task.created_at.desc()))

        if choice == "接受方案":
            if program is not None:
                program.status, program.next_decision = "ACTIVE", "下一阶段复盘"
            title, instruction, assignee, role, due_at = (
                "开始执行已接受的健康计划",
                "按当前健康计划完成本周第一项行动；如遇困难，请在计划页记录并联系健康管理师。",
                "成员本人", "member", datetime.now(timezone.utc) + timedelta(days=7),
            )
            followup = "已接受，等待成员开始执行"
        elif choice == "暂缓":
            if program is not None:
                program.status, program.next_decision = "PAUSED", "下次复核"
            title, instruction, assignee, role, due_at = (
                "复核成员暂缓的健康计划",
                "成员已暂缓当前方案；在下次复核前不重复催办，请由健康管理师确认恢复条件。",
                "健康管理师", "health_manager", datetime.now(timezone.utc) + timedelta(days=30),
            )
            followup = "已暂缓，等待约定复核"
        else:
            title, instruction, assignee, role, due_at = (
                "与成员确认健康计划调整",
                "成员希望调整或讨论当前方案；请先确认实际困难与可执行的非医疗管理安排。",
                "健康管理师", "health_manager", datetime.now(timezone.utc),
            )
            followup = "等待健康管理师联系成员"

        if existing is None:
            session.add(Task(
                patient_id=member_id, program_id=program.id if program else None,
                title=title, instruction=instruction, status="PENDING", priority="MEDIUM",
                assignee=assignee, responsible_role=role, due_at=due_at, source="member_plan_choice",
            ))
        else:
            existing.title, existing.instruction = title, instruction
            existing.assignee, existing.responsible_role, existing.due_at = assignee, role, due_at
        row.manager_followup = followup
        session.add(AuditLog(
            patient_id=member_id, actor="成员本人", actor_role="member", action="recorded_member_plan_choice",
            entity_type="MemberPlanChoice", entity_id=str(row.id), detail_json={"choice": choice, "next_action": followup},
        ))
        session.flush(); return row
