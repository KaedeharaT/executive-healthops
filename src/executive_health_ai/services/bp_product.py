"""BP-aligned product projections without creating another source of truth."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, timedelta, timezone
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from executive_health_ai.models import AuditLog, Consent, HealthAssessment, HealthProgram


CONSENT_SCOPES = {
    "ANNUAL_SERVICE": ("年度健康管理服务", "用于执行已确认的年度健康管理计划与服务。"),
    "LONGITUDINAL_HEALTH_RECORD": ("长期健康档案", "用于持续保存已确认健康事实、行动与结果。"),
    "ALGORITHM_MODEL_USE": ("算法与模型辅助", "用于报告整理、摘要与有依据的辅助解释；不用于自动诊断或风险决策。"),
}

SEVEN_STEP_RESPONSIBILITY_LOOP = (
    "采集", "判断", "分级", "确认", "行动", "回写", "复盘", "下一轮",
)


@dataclass(frozen=True)
class CareCycle:
    code: str
    label: str
    objective: str
    next_review_date: date


def care_cycle_for(
    program: HealthProgram | None, *, baseline_confirmed: bool, today: date | None = None,
) -> CareCycle:
    """Describe the member's current cadence; persisted business entities remain authoritative."""
    current = today or date.today()
    if not baseline_confirmed:
        return CareCycle("FIRST_MONTH", "首月 · 建立基线", "整合体检、病史、用药、健康数据、生活方式与目标", current + timedelta(days=30))
    if program is None:
        return CareCycle("MONTHLY", "每月 · 持续执行", "跟进任务、复查、数据与管理结果", current + timedelta(days=30))
    elapsed = max((current - program.start_date).days, 0)
    if elapsed < 30:
        return CareCycle("FIRST_MONTH", "首月 · 开始执行", "确认基线、年度目标、负责人和第一批行动", program.start_date + timedelta(days=30))
    if elapsed >= 335 or (program.end_date and (program.end_date - current).days <= 30):
        return CareCycle("ANNUAL", "年度 · 年度复盘", "比较年度体检、重大事件、服务与结果，准备下一年度计划", program.end_date or program.start_date + timedelta(days=365))
    quarter_end = program.start_date + timedelta(days=((elapsed // 90) + 1) * 90)
    if elapsed % 90 >= 76:
        return CareCycle("QUARTERLY", "季度 · 阶段校准", "对比关键指标、复评风险、协调医生并校准计划", quarter_end)
    month_end = program.start_date + timedelta(days=((elapsed // 30) + 1) * 30)
    return CareCycle("MONTHLY", "每月 · 持续执行", "监测趋势、跟进任务、复查与服务结果", month_end)


class ConsentService:
    """Minimal, revocable consent workflow for the three BP-defined scopes."""

    def list_for_member(self, session: Session, member_id: UUID) -> dict[str, Consent | None]:
        rows = list(session.scalars(select(Consent).where(Consent.patient_id == member_id).order_by(Consent.created_at.desc())))
        return {scope: next((row for row in rows if row.consent_type == scope), None) for scope in CONSENT_SCOPES}

    def grant(self, session: Session, member_id: UUID, scope: str, *, actor: str, source: str) -> Consent:
        if scope not in CONSENT_SCOPES:
            raise ValueError("不支持的授权范围")
        current = self.list_for_member(session, member_id)[scope]
        now = datetime.now(timezone.utc)
        if current is None:
            current = Consent(
                patient_id=member_id, consent_type=scope, status="GRANTED",
                granted_at=now, withdrawn_at=None, source=source,
            )
            session.add(current)
            session.flush()
        else:
            current.status, current.granted_at, current.withdrawn_at, current.source = "GRANTED", now, None, source
        session.add(AuditLog(
            patient_id=member_id, actor=actor, actor_role="member", action="granted_consent",
            entity_type="Consent", entity_id=str(current.id), detail_json={"scope": scope, "source": source},
        ))
        session.flush()
        return current

    def revoke(self, session: Session, member_id: UUID, scope: str, *, actor: str, source: str) -> Consent:
        current = self.list_for_member(session, member_id).get(scope)
        if current is None or current.status != "GRANTED":
            raise ValueError("当前授权尚未生效")
        current.status, current.withdrawn_at, current.source = "REVOKED", datetime.now(timezone.utc), source
        session.add(AuditLog(
            patient_id=member_id, actor=actor, actor_role="member", action="revoked_consent",
            entity_type="Consent", entity_id=str(current.id), detail_json={"scope": scope, "source": source},
        ))
        session.flush()
        return current


def current_care_cycle(session: Session, member_id: UUID, *, today: date | None = None) -> CareCycle:
    baseline = session.scalar(select(HealthAssessment).where(
        HealthAssessment.patient_id == member_id,
        HealthAssessment.assessment_type == "BASELINE",
        HealthAssessment.status == "CONFIRMED",
    ).order_by(HealthAssessment.confirmed_at.desc()))
    program = session.scalar(select(HealthProgram).where(
        HealthProgram.patient_id == member_id,
        HealthProgram.status.in_(("ACTIVE", "PLANNED", "PAUSED")),
    ).order_by(HealthProgram.created_at.desc()))
    return care_cycle_for(program, baseline_confirmed=baseline is not None, today=today)
