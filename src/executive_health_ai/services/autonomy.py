"""Versioned execution policy. Formal risk is read from RiskEvent, never model output.

Extraction confidence and intake exceptions are deliberately independent of risk.
Policy evaluation is read-only so detached file/LLM execution never holds a write
transaction merely to record a decision. The executor persists it after I/O.
"""
from dataclasses import asdict, dataclass
from sqlalchemy import select
from executive_health_ai.models import RiskEvent, AgentRunTrace
from executive_health_ai.models.base import utc_now
from executive_health_ai.services.operational_worklist import ACTIVE_RISK_STATUSES

POLICY_VERSION = 'autonomy-1'
MODES = {'GREEN': 'OUT_OF_LOOP', 'YELLOW': 'ON_THE_LOOP', 'RED': 'IN_THE_LOOP'}
SAFE_PREPARATION = frozenset({'evaluate_confirmed_observations', 'record_goal_progress',
    'parse_profile_document', 'match_profile_document', 'request_doctor_review'})


@dataclass(frozen=True)
class AutonomyDecision:
    risk_level: str | None
    autonomy_mode: str
    tool_name: str
    decision: str
    reason_code: str
    requires_human: bool
    required_role: str | None
    policy_version: str = POLICY_VERSION
    risk_reference: str | None = None
    risk_rule_version: str | None = None


class AutonomyGate(PermissionError):
    def __init__(self, decision):
        self.decision = decision
        super().__init__({'REQUIRE_MANAGER': '此操作需要健管确认。',
            'REQUIRE_DOCTOR': '此操作需要医生判断。', 'BLOCK': '此操作不在自动执行范围内。'}[decision.decision])


def current_risk(session, member_id):
    """Highest unresolved formal event wins; absence is NOT a GREEN diagnosis."""
    rows = list(session.scalars(select(RiskEvent).where(RiskEvent.patient_id == member_id,
        RiskEvent.status.in_(ACTIVE_RISK_STATUSES))))
    return max(rows, key=lambda r: ({'GREEN': 1, 'YELLOW': 2, 'RED': 3}.get(r.risk_level, 0),
        r.created_at), default=None)


class AutonomyPolicy:
    def decide(self, *, risk_level, goal_type, tool, responsibility=None,
               member_context=None, current_state=None, approved_role=None):
        # Caller supplies only trusted service context. Tool permissions are a
        # lower bound: risk and model text cannot weaken them.
        level = tool.autonomy_level
        role = None
        if risk_level is not None and risk_level not in MODES:
            outcome, reason = 'BLOCK', 'UNKNOWN_FORMAL_RISK'
        elif not tool.enabled or level == 'FORBIDDEN':
            outcome, reason = 'BLOCK', 'TOOL_UNAVAILABLE'
        elif tool.name == 'request_doctor_review' and responsibility != 'DOCTOR' and approved_role not in {'HEALTH_MANAGER', 'ADMIN'}:
            outcome, reason, role = 'REQUIRE_MANAGER', 'REFERRAL_REQUIRES_GOVERNED_ROUTE', 'MANAGER'
        elif tool.permission == 'DOCTOR_APPROVAL' or level == 'DOCTOR_REQUIRED':
            outcome, reason, role = 'REQUIRE_DOCTOR', 'CLINICAL_GATE', 'DOCTOR'
        elif tool.name == 'execute_approved_plan_check' and risk_level != 'GREEN':
            outcome, reason, role = 'REQUIRE_MANAGER', 'AUTOMATIC_CLOSE_REQUIRES_GREEN', 'MANAGER'
        elif risk_level == 'RED' and tool.name == 'start_next_phase':
            outcome, reason, role = 'REQUIRE_MANAGER', 'RESOLVE_RED_BEFORE_NEXT_PHASE', 'MANAGER'
        elif tool.permission == 'MANAGER_APPROVAL' or level == 'MANAGER_REQUIRED':
            if approved_role in {'HEALTH_MANAGER', 'ADMIN'}:
                outcome, reason = 'AUTO_WITH_OVERSIGHT', 'EXPLICIT_MANAGER_APPROVAL'
            else:
                outcome, reason, role = 'REQUIRE_MANAGER', 'TOOL_MANAGER_GATE', 'MANAGER'
        elif tool.mode == 'read' or level == 'AUTO_SAFE':
            outcome, reason = ('AUTO_WITH_OVERSIGHT' if risk_level in {'YELLOW', 'RED'} else 'AUTO_EXECUTE'), 'SAFE_PREPARATION'
        elif risk_level == 'RED':
            outcome, reason, role = 'REQUIRE_MANAGER', 'RED_RESTRICTED_WRITE', 'MANAGER'
        elif risk_level == 'YELLOW':
            # A log of existing facts / scheduling check is reversible preparation.
            if approved_role in {'HEALTH_MANAGER', 'ADMIN'}:
                outcome, reason = 'AUTO_WITH_OVERSIGHT', 'EXPLICIT_MANAGER_APPROVAL'
            elif tool.name in {'create_followup_task', 'create_member_reminder'} and (member_context or {}).get('confirmed_followup'):
                outcome, reason = 'AUTO_WITH_OVERSIGHT', 'CONFIRMED_FOLLOWUP_REMINDER'
            elif tool.name in {'write_management_log', 'schedule_followup', 'record_goal_progress'}:
                outcome, reason = 'AUTO_WITH_OVERSIGHT', 'REVERSIBLE_PREPARATION'
            else:
                outcome, reason, role = 'REQUIRE_MANAGER', 'YELLOW_ARRANGEMENT_CONFIRMATION', 'MANAGER'
        elif risk_level == 'GREEN' and tool.name in {'create_followup', 'create_followup_task', 'create_member_reminder'} and not (member_context or {}).get('approved_operational_plan'):
            if approved_role in {'HEALTH_MANAGER', 'ADMIN'}:
                outcome, reason = 'AUTO_WITH_OVERSIGHT', 'EXPLICIT_MANAGER_APPROVAL'
            else:
                outcome, reason, role = 'REQUIRE_MANAGER', 'PLAN_APPROVAL_REQUIRED', 'MANAGER'
        else:
            outcome, reason = 'AUTO_EXECUTE', 'EXISTING_APPROVED_SCOPE'
        return AutonomyDecision(risk_level, MODES.get(risk_level, 'EXISTING_GATES'), tool.name,
            outcome, reason, role is not None, role)


def evaluate(session, tool, goal, approved_role=None, context=None):
    from dataclasses import replace
    risk = current_risk(session, goal.member_id)
    # Intake has its own evidence/exception gates; do not colour every document.
    if goal.goal_type == 'PROFILE_INTAKE':
        risk = None
    responsibility = tool.responsibility
    approved_plan = False
    confirmed_followup = False
    if risk and risk.risk_level == 'YELLOW' and tool.name in {'create_followup_task', 'create_member_reminder'}:
        # Existing post-checkup approval survives a durable doctor wait. Verify
        # both stored approvals and the exact review returned by its plan step.
        import json
        from uuid import UUID
        from executive_health_ai.models import AgentApprovalRequest, AgentPlanStep, DoctorReview
        approval = session.scalar(select(AgentApprovalRequest).where(AgentApprovalRequest.goal_id == goal.id,
            AgentApprovalRequest.status == 'APPROVED', AgentApprovalRequest.required_role == 'HEALTH_MANAGER'))
        if approval:
            for step in session.scalars(select(AgentPlanStep).where(AgentPlanStep.plan_id == goal.current_plan_id,
                    AgentPlanStep.tool_name == 'request_doctor_review', AgentPlanStep.status == 'COMPLETED')):
                ref = json.loads(step.result_summary or '{}').get('doctor_review_id')
                review = session.get(DoctorReview, UUID(ref)) if ref else None
                confirmed_followup = bool(review and review.patient_id == goal.member_id and
                    review.risk_event_id == risk.id and review.status == 'CONFIRMED')
                if confirmed_followup: break
    identity = (context or {}).get('management_plan_id')
    if identity:
        from uuid import UUID
        from executive_health_ai.models import ManagementPlan, DoctorReview
        plan = session.get(ManagementPlan, UUID(str(identity)))
        review = session.get(DoctorReview, plan.doctor_review_id) if plan and plan.doctor_review_id else None
        approved_plan = bool(plan and plan.patient_id == goal.member_id and plan.status == 'ACTIVE'
            and (plan.program_id is None or str(plan.program_id) == str((context or {}).get('program_id') or goal.context_json.get('program_id')))
            and (plan.adjusted_by or (review and review.status == 'CONFIRMED')))
    if risk and tool.name == 'request_doctor_review':
        from executive_health_ai.services.risk_autonomy import responsibility_for
        target = risk
        if goal.context_json.get('risk_event_id'):
            from uuid import UUID
            bound = session.get(RiskEvent, UUID(goal.context_json['risk_event_id']))
            if bound and bound.patient_id == goal.member_id and bound.status in ACTIVE_RISK_STATUSES:
                target = bound
        responsibility = responsibility_for(session, target).route_type
    decision = AutonomyPolicy().decide(risk_level=risk.risk_level if risk else None,
        goal_type=goal.goal_type, tool=tool, responsibility=responsibility,
        current_state=goal.status, approved_role=approved_role,
        member_context={'approved_operational_plan': approved_plan, 'confirmed_followup': confirmed_followup})
    return replace(decision, risk_reference=str(risk.id) if risk else None,
        risk_rule_version=str((risk.evidence_json or {}).get('rule_version', 'unknown')) if risk else None)


def persist(session, goal, decision):
    session.add(AgentRunTrace(goal_id=goal.id, plan_id=goal.current_plan_id,
        tool_name=decision.tool_name, action='autonomy_decision', status=decision.decision,
        completed_at=utc_now(), result_summary=decision.reason_code,
        metadata_json={**asdict(decision), 'member_agent_id': goal.context_json.get('member_agent_id'),
            'input_reference': goal.source_id}))
    session.flush()
