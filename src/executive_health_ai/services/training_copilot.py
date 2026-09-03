"""Deprecated training-product compatibility service.

The Training Copilot is not a current Executive HealthOps product surface.
Grounded answers, retrieval and citations live in the generic services and do
not depend on this module.  This module remains temporarily for historical
data and migration compatibility only.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable

from sqlalchemy.orm import Session

from executive_health_ai.models import TrainingSession
from executive_health_ai.models.base import utc_now
from executive_health_ai.services.grounded_ai import AIAnswer, GroundedAnswerService


TRAINING_KNOWLEDGE_CATEGORIES = (
    "INTERNAL_SOP", "TRAINING_MATERIAL", "CLINICAL_GUIDELINE", "PATIENT_EDUCATION",
)
TRAINING_KNOWLEDGE_SOURCE_TYPES = (
    "INTERNAL_SOP", "TRAINING_MATERIAL", "GUIDELINE", "PATIENT_EDUCATION",
)


@dataclass(frozen=True)
class TrainingCriterion:
    dimension: str
    label: str
    keywords: tuple[str, ...]
    points: int = 2


@dataclass(frozen=True)
class TrainingRubric:
    rubric_id: str
    title: str
    required_actions: tuple[TrainingCriterion, ...]
    forbidden_actions: tuple[TrainingCriterion, ...]
    escalation_conditions: tuple[str, ...]
    evidence_requirements: tuple[str, ...]
    workflow_sequence: tuple[str, ...]
    communication_points: tuple[str, ...]
    knowledge_query: str

    def score(self, response: str) -> dict[str, object]:
        normalized = "".join(response.lower().split())
        met, missing, forbidden = [], [], []
        dimensions: dict[str, int] = {}
        total = 0
        for item in self.required_actions:
            matched = any("".join(keyword.lower().split()) in normalized for keyword in item.keywords)
            if matched:
                total += item.points
                met.append(item.label)
                dimensions[item.dimension] = dimensions.get(item.dimension, 0) + item.points
            else:
                missing.append(item.label)
                dimensions.setdefault(item.dimension, 0)
        for item in self.forbidden_actions:
            if any("".join(keyword.lower().split()) in normalized for keyword in item.keywords):
                total = max(0, total - item.points)
                forbidden.append(item.label)
        return {
            "score": min(10, total), "max_score": 10,
            "met": met, "missing": missing, "forbidden": forbidden,
            "dimensions": dimensions,
        }


@dataclass(frozen=True)
class TrainingCase:
    case_id: str
    category: str
    category_label: str
    title: str
    scenario: str
    question: str
    rubric_id: str
    objectives: tuple[str, ...]


@dataclass(frozen=True)
class TrainingEvaluation:
    case: TrainingCase
    score: dict[str, object]
    answer: AIAnswer


def _criterion(dimension: str, label: str, *keywords: str) -> TrainingCriterion:
    return TrainingCriterion(dimension, label, tuple(keywords))


RUBRICS: dict[str, TrainingRubric] = {
    "report_review": TrainingRubric(
        "report_review", "体检报告审核",
        (
            _criterion("流程完整性", "确认报告事实与成员归属", "确认报告", "核对报告", "成员归属"),
            _criterion("依据使用", "检查原文、页码或表格依据", "查看依据", "原文", "页码", "表格"),
            _criterion("任务闭环", "建立负责人和截止时间", "负责人", "owner", "截止", "due"),
            _criterion("流程完整性", "首份报告进入基线、后续报告进入比较", "基线", "比较", "对比"),
            _criterion("升级判断", "医学解释交给医生", "提交医生", "医生复核", "医学判断"),
        ),
        (_criterion("岗位边界", "健管直接诊断或给出治疗结论", "诊断为", "确诊", "直接开药"),),
        ("重大新发现、医学解释或用药问题升级内部医生",),
        ("报告原文、页码、表格或保留片段",),
        ("接收", "整理", "人工确认", "基线/比较", "任务/升级"),
        ("向成员说明正在整理与人工审核",),
        "体检报告审核操作指南 报告确认 查看依据 基线 医生升级",
    ),
    "yellow_risk": TrainingRubric(
        "yellow_risk", "Yellow Risk 健管处理",
        (
            _criterion("流程完整性", "先接手并核实触发依据", "接手", "核实", "触发依据"),
            _criterion("依据使用", "查看 Observation 与规则依据", "observation", "数据依据", "规则依据", "查看依据"),
            _criterion("任务闭环", "明确负责人", "负责人", "owner", "我负责"),
            _criterion("任务闭环", "明确下一动作与期限", "下一步", "截止", "due", "复核时间"),
            _criterion("升级判断", "需要医学判断时提交医生", "提交医生", "医生复核", "医学判断"),
        ),
        (_criterion("岗位边界", "将 Yellow 直接解释为诊断", "确诊", "就是疾病", "自行诊断"),),
        ("重大 Finding、医学解释、用药或规则覆盖不足",),
        ("RiskEvent 触发数据与 RiskRule 引用",),
        ("接手", "核实", "行动", "等待/随访", "明确关闭"),
        ("向成员解释这是待人工核实事项，不是系统诊断",),
        "Yellow Risk健管处理SOP 接手 负责人 下一动作 截止 医生升级",
    ),
    "doctor_escalation": TrainingRubric(
        "doctor_escalation", "健管到内部医生升级",
        (
            _criterion("升级判断", "说明为什么需要医生", "医学判断", "重大finding", "用药问题", "规则覆盖不足"),
            _criterion("依据使用", "附上关键事实与依据", "关键数据", "报告依据", "查看依据", "observation"),
            _criterion("流程完整性", "提出明确的医生问题", "请医生确认", "需要医生回答", "复核问题"),
            _criterion("任务闭环", "保留健管跟踪责任", "等待医生", "健管跟踪", "后续跟进"),
            _criterion("岗位边界", "不代替医生形成医学结论", "不诊断", "医生判断", "不自行判断"),
        ),
        (_criterion("岗位边界", "健管直接决定诊断、处方或药物调整", "直接诊断", "直接开药", "停药", "调药"),),
        ("医学解释、重大 Finding、用药问题、转诊决定、规则不足",),
        ("成员事实、报告/数据依据、既往行动",),
        ("说明原因", "结构化上下文", "提出问题", "等待医生", "执行建议"),
        ("区分健管协调职责与医生医学判断",),
        "健管内部医生升级规范 医学判断 结构化上下文 复核问题",
    ),
    "plan_communication": TrainingRubric(
        "plan_communication", "健康计划沟通",
        (
            _criterion("沟通规范", "说明计划目标与可选动作", "计划目标", "接受", "调整", "暂缓"),
            _criterion("沟通规范", "确认成员选择与障碍", "成员选择", "确认意愿", "障碍"),
            _criterion("任务闭环", "将选择写入计划状态", "计划状态", "激活", "暂停"),
            _criterion("任务闭环", "建立具体任务、负责人和期限", "任务", "负责人", "截止"),
            _criterion("流程完整性", "约定下一次复盘", "复盘", "下次评估", "next review"),
        ),
        (_criterion("岗位边界", "把成员选择强制解释为医疗风险", "不接受就高风险", "直接升级风险"),),
        (), ("计划、成员选择、任务与复盘记录",),
        ("说明", "选择", "任务", "执行", "复盘"),
        ("尊重接受、调整和暂缓选择",),
        "健康计划跟进规范 接受 调整 暂缓 任务 负责人 复盘",
    ),
    "member_task": TrainingRubric(
        "member_task", "成员任务未完成",
        (
            _criterion("沟通规范", "先了解未完成原因", "原因", "障碍", "沟通"),
            _criterion("任务闭环", "发送平台内提醒", "提醒", "平台内"),
            _criterion("任务闭环", "调整任务或期限", "调整任务", "调整期限", "重新安排"),
            _criterion("流程完整性", "记录跟进结果", "记录", "跟进结果"),
            _criterion("岗位边界", "不自动升级医学风险", "不升级风险", "管理事项", "不是医学风险"),
        ),
        (_criterion("岗位边界", "一次未完成即自动生成医学风险", "直接中风险", "自动高风险", "医学风险"),),
        (), ("任务状态、成员反馈和调整记录",),
        ("提醒", "了解障碍", "调整", "复核"),
        ("避免惩罚式沟通",),
        "健康计划跟进规范 成员任务未完成 提醒 障碍 调整期限",
    ),
    "service_operation": TrainingRubric(
        "service_operation", "服务申请与安排",
        (
            _criterion("流程完整性", "审核申请与权益", "审核申请", "权益"),
            _criterion("任务闭环", "明确服务负责人", "负责人", "assigned manager"),
            _criterion("任务闭环", "安排时间并确认状态", "预约", "安排时间", "已安排"),
            _criterion("流程完整性", "记录服务结果", "结果摘要", "服务结果"),
            _criterion("流程完整性", "将结果回流档案与时间线", "时间线", "健康档案", "回流"),
        ),
        (_criterion("流程完整性", "仅把状态改成完成而不记录结果", "只改完成", "无需结果"),),
        (), ("ServiceRequest、安排记录与结果摘要",),
        ("申请", "审核", "安排", "执行", "结果", "回流"),
        ("向成员说明当前服务状态与下一步",),
        "服务安排与结果回流SOP 申请 审核 安排 服务结果 时间线",
    ),
    "outcome_next": TrainingRubric(
        "outcome_next", "Outcome 后续决定",
        (
            _criterion("依据使用", "描述观察到的变化而非因果", "观察到", "不能证明因果", "前后对比"),
            _criterion("流程完整性", "选择继续、调整、稳定期或医生", "继续", "调整", "稳定期", "提交医生"),
            _criterion("任务闭环", "记录管理决定", "记录决定", "后续决定"),
            _criterion("任务闭环", "设置下一复盘或任务", "下一次复盘", "任务", "截止"),
            _criterion("岗位边界", "医学解释交给医生", "医生判断", "提交医生", "不诊断"),
        ),
        (_criterion("岗位边界", "把相关变化写成确定疗效因果", "证明是方案导致", "治愈", "一定有效"),),
        ("结果涉及医学解释或异常恶化时提交医生",),
        ("before/after window、指标与结果记录",),
        ("观察", "决定", "任务/复盘", "时间线"),
        ("向成员使用观察性、非因果表述",),
        "健康计划跟进规范 Outcome 继续 调整 稳定期 医生 下一次复盘",
    ),
    "stale_data": TrainingRubric(
        "stale_data", "数据缺失与陈旧处理",
        (
            _criterion("依据使用", "识别最后记录时间与新鲜度", "最后记录", "数据较旧", "新鲜度"),
            _criterion("岗位边界", "明确无数据不等于正常", "不等于正常", "未评估", "数据不足"),
            _criterion("任务闭环", "提醒补测或检查设备", "补测", "检查设备", "提醒"),
            _criterion("流程完整性", "区分可疑、无效与缺失", "suspect", "invalid", "missing", "需确认"),
            _criterion("任务闭环", "记录负责人和复核时间", "负责人", "复核时间", "截止"),
        ),
        (_criterion("岗位边界", "使用陈旧记录宣布当前正常", "当前正常", "稳定无需处理"),),
        (), ("Observation 时间、质量状态与设备同步信息",),
        ("识别", "补测/设备核查", "记录", "复核"),
        ("向成员说明是数据不足，不是风险结论",),
        "数据缺失陈旧处理规范 无数据不等于正常 补测 设备 数据质量",
    ),
}


def _case(case_id: str, category: str, title: str, scenario: str, question: str, *objectives: str) -> TrainingCase:
    rubric = RUBRICS[category]
    return TrainingCase(case_id, category, rubric.title, title, scenario, question, category, tuple(objectives))


CASES: tuple[TrainingCase, ...] = (
    _case("report-01", "report_review", "首份年度体检报告", "Demo Executive A 上传首份17页年度体检报告，系统已完成结构化候选，部分 Finding 需要人工确认。", "你首先准备怎么处理？", "报告事实确认", "Evidence", "基线"),
    _case("report-02", "report_review", "第二份报告进入比较", "成员已有确认基线，又上传一份新报告，系统显示新增与未复查项目。", "你如何完成审核并安排下一步？", "报告比较", "Owner", "医生升级"),
    _case("yellow-01", "yellow_risk", "Yellow Risk 待接手", "演示规则基于已确认 Observation 生成一条 Yellow Risk，当前状态为待处理。", "你接手后如何推进？", "触发依据", "Owner / Due", "闭环"),
    _case("yellow-02", "yellow_risk", "Yellow Risk 等待成员", "你已联系成员但对方暂未回复，风险事项仍需持续跟进。", "你会如何记录状态和下一动作？", "等待成员", "跟进任务", "明确关闭"),
    _case("doctor-01", "doctor_escalation", "胸部CT复查建议", "报告出现胸部CT复查建议，成员询问是否代表严重疾病。", "作为健管师，你如何提交医生复核？", "岗位边界", "关键事实", "医生问题"),
    _case("doctor-02", "doctor_escalation", "规则覆盖不足", "新 Finding 没有匹配的正式 Clinical Rule，健管无法判断医学含义。", "你如何处理并完成交接？", "规则不足", "结构化上下文", "健管跟踪"),
    _case("plan-01", "plan_communication", "成员接受健康计划", "成员选择接受90天健康计划，但尚未建立具体任务。", "你如何把选择转成可执行计划？", "成员选择", "任务", "复盘"),
    _case("plan-02", "plan_communication", "成员希望暂缓", "成员因出差希望暂缓计划两周。", "你如何回应并处理系统状态？", "尊重选择", "暂停", "复核时间"),
    _case("task-01", "member_task", "运动任务未完成", "成员本周未完成运动记录，但没有新的医学风险事件。", "你会怎么跟进？", "平台提醒", "了解障碍", "不升级风险"),
    _case("task-02", "member_task", "血压测量遗漏", "成员连续两天未完成计划中的测量任务，设备连接正常。", "你如何处理任务而不混淆风险语义？", "任务调整", "跟进记录", "岗位边界"),
    _case("service-01", "service_operation", "营养咨询申请", "成员提交营养咨询服务申请，权益可用但尚未安排时间。", "你如何推进到可追溯结果？", "权益审核", "安排", "结果回流"),
    _case("service-02", "service_operation", "服务已执行待回流", "服务已执行，但当前记录只有 COMPLETED，没有结果摘要。", "你还需要完成哪些动作？", "结果摘要", "成员可见状态", "Timeline"),
    _case("outcome-01", "outcome_next", "睡眠指标观察到改善", "阶段前后对比显示睡眠时长增加，但不能证明由单一方案导致。", "Outcome 后你如何决定下一步？", "观察性表达", "管理决定", "下一复盘"),
    _case("outcome-02", "outcome_next", "体重未见改善", "阶段结果显示体重指标未见改善，成员执行中存在出差障碍。", "你如何记录并推进？", "调整方案", "任务", "必要时医生"),
    _case("stale-01", "stale_data", "血压最后记录32天前", "页面显示最近一次血压128/84，但记录时间为32天前。", "你应该如何向成员和团队表达？", "数据新鲜度", "补测", "未评估"),
    _case("stale-02", "stale_data", "设备数据质量可疑", "连续血糖数据被标记为 SUSPECT，另有一段 MISSING。", "你如何区分并安排处理？", "数据质量", "设备核查", "负责人"),
)

# Public immutable catalogs used by the UI and portfolio checks.
TRAINING_RUBRICS = RUBRICS
TRAINING_CASES = CASES


class TrainingCopilotService:
    """Application service for Q&A, cases, and process-skill assessment."""

    def __init__(self, grounded_answers: GroundedAnswerService | None = None) -> None:
        self.grounded_answers = grounded_answers or GroundedAnswerService()

    @staticmethod
    def list_cases(category: str | None = None) -> list[TrainingCase]:
        return [case for case in CASES if category is None or case.category == category]

    @staticmethod
    def get_case(case_id: str) -> TrainingCase:
        case = next((item for item in CASES if item.case_id == case_id), None)
        if case is None:
            raise ValueError("Training case not found.")
        return case

    @staticmethod
    def start_session(session: Session, *, mode: str, case_id: str | None = None) -> TrainingSession:
        if mode not in {"Q&A", "CASE", "ASSESSMENT"}:
            raise ValueError("Unsupported training mode.")
        record = TrainingSession(mode=mode, case_id=case_id)
        session.add(record)
        session.flush()
        return record

    @staticmethod
    def _answer_snapshot(answer: AIAnswer) -> dict[str, object]:
        return {
            "answer_id": answer.answer_id, "content": answer.content,
            "grounded": answer.grounded, "limitations": list(answer.limitations),
            "fact_citations": [item.public_payload() for item in answer.fact_citations],
            "knowledge_citations": [item.public_payload() for item in answer.knowledge_citations],
        }

    def answer_question(self, session: Session, question: str, *, training_session: TrainingSession | None = None) -> AIAnswer:
        if not question.strip():
            raise ValueError("请输入培训问题。")
        record = training_session or self.start_session(session, mode="Q&A")
        answer = self.grounded_answers.answer(
            session, question=question, feature="training_qa",
            categories=TRAINING_KNOWLEDGE_CATEGORIES,
            source_types=TRAINING_KNOWLEDGE_SOURCE_TYPES,
            audience="health_manager", session_id=str(record.id), conversation_id=str(record.id),
        )
        record.trainee_messages = [*record.trainee_messages, {"role": "trainee", "content": question}]
        snapshot = self._answer_snapshot(answer)
        record.coach_answers = [*record.coach_answers, snapshot]
        record.citations = [*record.citations, *snapshot["knowledge_citations"]]
        record.step += 1
        session.flush()
        return answer

    def evaluate_case(
        self, session: Session, case_id: str, response: str, *,
        mode: str = "CASE", training_session: TrainingSession | None = None,
    ) -> TrainingEvaluation:
        if not response.strip():
            raise ValueError("请输入你的处理思路。")
        case, rubric = self.get_case(case_id), RUBRICS[self.get_case(case_id).rubric_id]
        record = training_session or self.start_session(session, mode=mode, case_id=case_id)
        score = rubric.score(response)
        right = "；".join(score["met"]) or "已开始梳理处理思路"
        missing = "；".join(score["missing"]) or "当前流程要点已覆盖"
        forbidden = "；".join(score["forbidden"])
        draft = (
            f"你做对的：{right}。\n\n"
            f"还需要补充：{missing}。"
            + (f"\n\n需要纠正：{forbidden}。" if forbidden else "")
            + f"\n\n建议下一步：按“{' → '.join(rubric.workflow_sequence)}”完成记录，并确保医学判断由医生承担。"
        )
        answer = self.grounded_answers.answer(
            session, question=f"培训案例：{case.scenario}\n学员回答：{response}\n请按既定 rubric 提供流程反馈。",
            knowledge_query=rubric.knowledge_query, fallback_content=draft,
            feature="training_assessment" if mode == "ASSESSMENT" else "training_case_feedback",
            categories=TRAINING_KNOWLEDGE_CATEGORIES,
            source_types=TRAINING_KNOWLEDGE_SOURCE_TYPES,
            audience="health_manager", session_id=str(record.id), conversation_id=str(record.id),
        )
        record.trainee_messages = [*record.trainee_messages, {"role": "trainee", "content": response, "case_id": case_id}]
        snapshot = self._answer_snapshot(answer)
        record.coach_answers = [*record.coach_answers, snapshot]
        record.citations = [*record.citations, *snapshot["knowledge_citations"]]
        attempts = [*(record.score_result or {}).get("attempts", []), {"case_id": case_id, **score}]
        aggregate = {
            "score": round(sum(item["score"] for item in attempts) / len(attempts)),
            "max_score": 10,
            "dimensions": {
                dimension: sum(item["dimensions"].get(dimension, 0) for item in attempts)
                for dimension in {key for item in attempts for key in item["dimensions"]}
            },
            "attempts": attempts,
            "rubric_id": rubric.rubric_id,
            "portfolio_training_only": True,
        }
        record.step += 1
        category_cases = [item for item in CASES if item.category == case.category]
        position = category_cases.index(case)
        if position + 1 < len(category_cases):
            record.case_id = category_cases[position + 1].case_id
            record.status = "IN_PROGRESS"
            record.completed_at = None
            aggregate["next_case_id"] = record.case_id
        else:
            record.status = "COMPLETED"
            record.completed_at = utc_now()
            aggregate["next_case_id"] = None
        record.score_result = aggregate
        session.flush()
        return TrainingEvaluation(case, aggregate, answer)
