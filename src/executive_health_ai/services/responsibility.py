"""Shared responsibility policy, independent of any agent or medical thresholds.

This class routes work; it never grades risk or makes clinical decisions. Signals
must come from trusted business adapters, not arbitrary model-generated reasons.
The existing AgentRunTrace stores the immutable decision envelope for Agent V1.
"""
from dataclasses import asdict, dataclass
from datetime import datetime

from executive_health_ai.models.base import utc_now

ROUTES = ('AUTO', 'MANAGER', 'DOCTOR', 'ESCALATE')
LABELS = dict(zip(ROUTES, ('系统自动处理', '健管确认', '医生判断', '优先人工处理')))
REASONS = {
    'NON_MEDICAL_PREPARATION': ('AUTO', '整理资料、计算变化和准备草稿，不作医学决定'),
    'CONFIRMED_ARRANGEMENTS': ('AUTO', '仅建立已经人工确认的工作安排'),
    'PROFILE_CONFIRMATION': ('MANAGER', '需要核对资料来源、档案更新和冲突，确认后才正式入档'),
    'MANAGER_CONFIRMATION': ('MANAGER', '需要健管确认报告整理结果、管理重点和处理路径'),
    'ACTION_APPROVAL': ('MANAGER', '需要健管确认后续行动的负责人、日期与依据'),
    'MISSING_CONTEXT': ('MANAGER', '年度方案或责任健管尚未明确，需要补充资料'),
    'MANAGER_REQUEST': ('DOCTOR', '健管已申请医学判断'),
    'DIAGNOSIS': ('DOCTOR', '涉及诊断或医学异常意义判断'),
    'MEDICATION': ('DOCTOR', '涉及药物开始、停止或剂量调整'),
    'TREATMENT': ('DOCTOR', '涉及治疗方案的医学决定'),
    'EXAMINATION': ('DOCTOR', '涉及进一步医学检查决定'),
    'REFERRAL': ('DOCTOR', '涉及转诊决定'),
    'MEDICAL_RISK': ('DOCTOR', '涉及医学风险结论'),
    'DISEASE_CHANGE': ('DOCTOR', '涉及既有疾病变化的医学解释'),
    'RULE_DOCTOR': ('DOCTOR', '现有确定性风险规则要求医生复核'),
    'AI_MEDICAL_SUGGESTION': ('DOCTOR', '辅助整理提示可能涉及医学决定，需要医生核实'),
    'AI_MANAGER_SUGGESTION': ('MANAGER', '辅助整理存在待核实的管理信息，需要健管确认'),
    'AI_UNCERTAINTY': ('ESCALATE', '辅助整理无法确认能否安全继续，需要优先人工核实'),
    'EMERGENCY_RULE': ('ESCALATE', '现有安全规则要求优先人工介入'),
    'DATA_CONFLICT': ('ESCALATE', '同一报告的关键数据存在矛盾，暂不能可靠继续'),
    'UNREADABLE_REPORT': ('ESCALATE', '报告无法可靠整理，请人工查看重要资料'),
    'UNSAFE_CONTINUATION': ('ESCALATE', '流程无法安全继续，需要人工核对'),
    'HUMAN_TAKEOVER': ('ESCALATE', '工作人员已接手，自动流程暂停'),
}


@dataclass(frozen=True)
class ResponsibilityRoute:
    route_type: str
    reason_codes: tuple[str, ...]
    reason_summary: str
    rule_refs: tuple[str, ...]
    evidence_refs: tuple[str, ...]
    created_at: datetime
    confirmed_by: str | None = None

    def payload(self):
        value = asdict(self)
        value['created_at'] = self.created_at.isoformat()
        return value


class ResponsibilityRouter:
    def decide(self, *, reason_codes, rule_refs=(), evidence_refs=(),
               previous=None, doctor_cleared=False, escalation_cleared=False,
               ai_suggestion=None, confirmed_by=None):
        codes = tuple(dict.fromkeys(reason_codes))
        if not codes or any(code not in REASONS for code in codes):
            raise ValueError('责任分流缺少有效的业务规则。')
        refs, evidence = tuple(dict.fromkeys(rule_refs)), tuple(dict.fromkeys(evidence_refs))
        if ai_suggestion not in (None, *ROUTES):
            raise ValueError('无效的辅助责任建议。')
        # AI cannot invent an emergency or a risk grade. A medical suggestion
        # can only tighten the route, with an existing evidence reference.
        if ai_suggestion in {'MANAGER','DOCTOR','ESCALATE'}:
            if not evidence:
                raise ValueError('辅助责任建议必须关联已有依据。')
            codes += ({'MANAGER':'AI_MANAGER_SUGGESTION','DOCTOR':'AI_MEDICAL_SUGGESTION','ESCALATE':'AI_UNCERTAINTY'}[ai_suggestion],)
        route = max((REASONS[code][0] for code in codes), key=ROUTES.index)
        if previous and ((previous.route_type == 'ESCALATE' and not escalation_cleared)
                         or (previous.route_type == 'DOCTOR' and not doctor_cleared)):
            if ROUTES.index(previous.route_type) > ROUTES.index(route):
                route = previous.route_type
            codes = tuple(dict.fromkeys((*codes, *previous.reason_codes)))
            refs = tuple(dict.fromkeys((*refs, *previous.rule_refs)))
            evidence = tuple(dict.fromkeys((*evidence, *previous.evidence_refs)))
        # Only reasons that account for the selected responsibility are prominent.
        summary = '；'.join(dict.fromkeys(REASONS[c][1] for c in codes if REASONS[c][0] == route))
        return ResponsibilityRoute(route, codes, summary, refs, evidence, utc_now(), confirmed_by)
