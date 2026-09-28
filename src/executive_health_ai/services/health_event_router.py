"""Read-only routing decisions, without parsing, clinical rules or business writes."""
from dataclasses import dataclass
from uuid import UUID
from sqlalchemy import select
from sqlalchemy.orm import Session
from executive_health_ai.models import AgentGoal, AgentPlan, AgentPlanStep, DoctorReview, HealthEvent


@dataclass(frozen=True)
class RouteDecision:
    action: str
    goal_id: UUID | None=None


class EventRouter:
    def decide(self,session: Session,event: HealthEvent) -> RouteDecision:
        if event.event_type in {'DEVICE_RAW_MEASUREMENT','MOBILE_RAW_MEASUREMENT'}:return RouteDecision('STORE_ONLY')
        if event.event_type in {'HEALTH_DOCUMENT_UPLOADED','CHECKUP_REPORT_UPLOADED'}:
            kind='PROFILE_INTAKE' if event.event_type=='HEALTH_DOCUMENT_UPLOADED' else 'POST_CHECKUP_MANAGEMENT'
            goal=session.scalar(select(AgentGoal).where(AgentGoal.member_id==event.member_id,
                AgentGoal.goal_type==kind,AgentGoal.source_id==event.source_id))
            return RouteDecision('RESUME_CURRENT_GOAL',goal.id) if goal else RouteDecision('CREATE_GOAL')
        if event.event_type=='DOCTOR_REVIEW_COMPLETED':
            review=session.get(DoctorReview,UUID(event.source_id))
            if not review or review.patient_id!=event.member_id:
                return RouteDecision('IGNORE')
            if review.status!='CONFIRMED':
                raise ValueError('医生意见尚未正式确认。')
            goal=next((g for g in session.scalars(select(AgentGoal).where(AgentGoal.member_id==event.member_id))
                if (g.context_json or {}).get('review_id')==event.source_id),None)
            if not goal:
                # Legacy plans bind the doctor review in a completed tool result.
                # Never guess using the member's most recent goal.
                import json
                rows=session.execute(select(AgentGoal,AgentPlanStep.result_summary)
                    .join(AgentPlan,AgentPlan.goal_id==AgentGoal.id)
                    .join(AgentPlanStep,AgentPlanStep.plan_id==AgentPlan.id)
                    .where(AgentGoal.member_id==event.member_id,AgentPlanStep.tool_name=='request_doctor_review'))
                for candidate,result in rows:
                    try: association=json.loads(result or '{}')
                    except (ValueError,TypeError):continue
                    if isinstance(association,dict) and association.get('doctor_review_id')==event.source_id:
                        goal=candidate;break
            return RouteDecision('RESUME_CURRENT_GOAL',goal.id) if goal else RouteDecision('STORE_ONLY')
        if event.event_category in {'MEANINGFUL_CHANGE','TIME_DUE'}:
            return RouteDecision('WAKE_MEMBER_AGENT')
        if event.event_type in {'MANAGEMENT_ITEM_COMPLETED','FOLLOWUP_RESULT_RECORDED','STAGE_REVIEW_CONFIRMED'}:
            return RouteDecision('WAKE_MEMBER_AGENT')
        return RouteDecision('STORE_ONLY')
