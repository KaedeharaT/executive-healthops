"""Original synthetic SOP foundation for the Portfolio Training Copilot.

These documents describe existing Executive HealthOps workflow behavior.  They
are not hospital policy, clinical guidelines, or medical decision rules.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, timezone

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from executive_health_ai.models import KnowledgeChunk, KnowledgeDocument
from executive_health_ai.services.knowledge import KnowledgeService


@dataclass(frozen=True)
class TrainingKnowledgeSpec:
    code: str
    title: str
    category: str
    sections: tuple[tuple[str, str], ...]

    @property
    def content(self) -> str:
        return "\n\n".join(f"## {heading}\n{text}" for heading, text in self.sections)


TRAINING_KNOWLEDGE_V1: tuple[TrainingKnowledgeSpec, ...] = (
    TrainingKnowledgeSpec("report-review", "体检报告审核SOP", "INTERNAL_SOP", (
        ("适用范围", "用于成员上传体检报告后的运营审核。系统解析与 AI 语义提取只产生 Candidate；它们不是已确认事实，也不构成医学判断。"),
        ("接收与状态", "确认报告所属成员、体检日期、机构、文件完整性和当前状态。成员应看到已收到、整理中、等待审核、审核完成或需要补充资料，而不是内部技术状态。"),
        ("Evidence核对", "逐项对照原文件页码、表格、行和保留片段。无法回到原文的 Candidate 不得直接确认；内容不清时标记需要人工核对或补充资料。"),
        ("人工确认与入档", "健管师确认 Candidate 后，才形成正式 Finding 或 Observation 并保留 provenance。需要医学解释、重大新发现或用药判断时提交内部医生。"),
        ("Baseline与Comparison", "首份已确认报告用于形成 Baseline Draft 并由健管确认；已有 Baseline 时，新报告进入 Comparison，区分新增、持续、改善、恢复和未复查。"),
        ("下一步分类", "比较或审核后必须选择仅记录、健管关注、医生复核或复查任务。任务应包含负责人、期限和下一动作，不能在确认报告后形成死胡同。"),
    )),
    TrainingKnowledgeSpec("finding-confirmation", "异常结果确认与入档规范", "TRAINING_MATERIAL", (
        ("先确认事实", "异常标记首先回答原报告写了什么。核对项目名称、结果、单位、参考范围、异常标志、发生日期和原文依据，不依据常识改写原始结果。"),
        ("数据质量", "区分 VALID、SUSPECT、INVALID 和 MISSING。数据需确认时先处理来源、设备或录入质量，不能把可疑数据直接升级成医学结论。"),
        ("避免重复", "同一报告、同一项目和同一发生时间的重复 Candidate 只确认一次。后续比较引用已确认 Observation，不另外复制一份当前健康状态。"),
        ("岗位边界", "健管师负责事实确认、任务与协同，不负责诊断、处方、停药、调药或替代医生解释异常结果。"),
    )),
    TrainingKnowledgeSpec("yellow-risk", "Yellow Risk健管处理SOP", "INTERNAL_SOP", (
        ("适用范围", "Yellow Risk 是确定性规则生成的运营分流事项，表示需要健管师核实和跟进，不等于医学诊断，也不代表系统已给出治疗建议。"),
        ("接手与Active Worklist", "Yellow Risk 出现后为待处理。健管师接手后进入处理中，事项仍保留在 Active Worklist；只有明确关闭后才离开活动队列。"),
        ("首次确认", "先核对触发 Observation、数据时间与质量、RiskRule 说明、报告或设备 Evidence，并了解成员当前情况。记录负责人、当前状态、下一动作和期限。"),
        ("可选处理动作", "根据事实选择继续观察、联系成员、处理数据问题、调整管理或提交内部医生。每次动作都应推进状态，而不是重复生成多条独立工作项。"),
        ("提交内部医生", "当事项涉及医学解释、重大 Finding、用药问题、风险升级、转诊判断或规则覆盖不足时，进入 Doctor Review；健管师保留等待医生与后续执行责任。"),
        ("随访", "联系成员后可进入等待成员；提交医生后进入等待医生；需要复查时进入待随访。所有活动状态继续显示 Owner、Due 和 Next Action。"),
        ("关闭条件", "只有处理目标完成且结果明确时关闭。记录 closed_by、closed_at、关闭原因和最终动作，并把有意义的结果投影到长期健康时间线。"),
    )),
    TrainingKnowledgeSpec("red-risk", "Red Risk人工运营处置SOP", "INTERNAL_SOP", (
        ("适用范围", "Red Risk 是高优先级人工运营事项，不是自动诊断或自动急救指令。系统不得仅凭颜色自动报警、处方或替代人工医学判断。"),
        ("优先接手", "Red Risk 排在活动工作列表前部，并明确负责人。接手后记录已接手时间、触发依据、当前处理状态和立即的下一动作。"),
        ("人工协同", "健管师核对事实并按现有服务流程联系成员；需要医学判断时优先提交内部医生。若成员已有线下医疗安排，记录协同状态和等待结果。"),
        ("持续跟踪与关闭", "等待医生、处理中和待随访都属于活动状态。只有记录处置结果、关闭原因、责任人和后续安排后才能关闭，并保留 Timeline 结果。"),
    )),
    TrainingKnowledgeSpec("doctor-escalation", "健管到内部医生升级规范", "INTERNAL_SOP", (
        ("升级条件", "医学解释、新重大 Finding、风险升级、Medication 问题、外部专科转诊判断、正式规则覆盖不足，或健管无法在岗位边界内完成判断时，应提交内部医生。"),
        ("提交上下文", "Doctor Review 应包含为什么提交、提交人、成员事实、风险等级（如相关）、关键 Observation、报告 Finding、Medication、Evidence、健管已做动作和希望医生回答的问题。"),
        ("岗位边界", "健管师不得诊断、处方、停药、调药或替代医生形成医学结论。AI 也不得决定 Risk 或覆盖医生判断。"),
        ("完成后的交接", "医生完成 Review 后，健管工作项从等待医生转为待执行医生建议或待随访，不重复创建同义任务。健管师负责成员沟通和后续闭环。"),
        ("外部医疗", "内部医生建议外部专科时，由健管师按服务流程协调预约和反馈；外部结果回来后按内容交给医生或健管继续处理，并记录最终状态。"),
    )),
    TrainingKnowledgeSpec("health-plan", "健康计划建立与成员确认规范", "INTERNAL_SOP", (
        ("计划结构", "健康计划应从问题与目标出发，说明方案、成员选择、任务、负责人、期限、复盘时间与阶段结果。计划不是只展示一组建议。"),
        ("成员接受", "成员接受后，计划进入 ACCEPTED 或 ACTIVE，生成必要任务；健管工作台显示方案已接受和待启动事项。"),
        ("希望调整", "成员希望调整时创建健管待处理事项，下一动作是与成员确认调整。修改后的任务、负责人、期限和复盘时间应重新明确。"),
        ("成员暂缓", "成员暂缓时记录 PAUSED、原因和 next_review_at，在约定时间前不重复催促；暂缓本身不自动升级为医学风险。"),
        ("复盘", "任务执行后进行阶段复盘。未完成先了解障碍并调整管理；需要医学判断时再提交医生。"),
    )),
    TrainingKnowledgeSpec("member-task", "成员任务未完成处理规范", "TRAINING_MATERIAL", (
        ("先了解障碍", "成员任务未完成时先确认是遗忘、出差、工作压力、设备问题、任务难度还是其他原因，并把反馈记录到跟进事项。"),
        ("平台内提醒", "第一版使用平台内 Reminder 或 Task 提醒，不假装已接入短信、微信或推送渠道。提醒内容说明任务和下一步，不使用惩罚式措辞。"),
        ("调整任务", "必要时调整任务难度、安排或期限，并保留负责人和下次复核时间。不能只改按钮状态而不改变计划的下一动作。"),
        ("风险边界", "低风险成员未完成运动、睡眠记录或测量任务，优先作为依从性与运营事项处理，不直接进入医学中风险工作队列。"),
    )),
    TrainingKnowledgeSpec("service-operation", "服务申请、安排与结果回流SOP", "INTERNAL_SOP", (
        ("统一生命周期", "成员主动申请、健管推荐或医生建议的服务都进入 ServiceRequest，按已申请、已审核、已安排、执行中、已完成或已取消推进。"),
        ("审核", "审核服务内容、成员需求和可用权益。未批准时记录原因；批准后明确负责人、下一动作和安排时间。"),
        ("安排与改期", "安排后显示预约时间和负责人。改期通过更新 scheduled_at 和说明完成，不需要制造另一条重复服务请求；取消时记录取消方与原因。"),
        ("执行与结果", "执行中保留当前状态。完成时必须记录结果摘要，不能只有 COMPLETED；必要的后续动作回到健管或医生。"),
        ("权益与Timeline", "按已有权益规则记录服务使用。将有意义的服务结果投影到成员档案和长期健康时间线，但不把每次按钮点击都写成节点。"),
    )),
    TrainingKnowledgeSpec("outcome-review", "Outcome阶段复盘与下一步规范", "TRAINING_MATERIAL", (
        ("观察性表达", "Outcome 记录 before window、after window、指标与观察到的变化。除非有充分证据，不得写成某方案必然导致改善、治愈或确定因果。"),
        ("继续当前方案", "结果支持继续时，记录继续决定并创建下一次复盘时间；原计划与任务保持可追踪。"),
        ("调整方案", "未达到阶段目标或出现执行障碍时，创建健管调整任务，重新明确任务、负责人、期限和复盘窗口。"),
        ("进入稳定管理", "阶段目标稳定时，Program 进入 maintenance 或 stable 状态，并保留周期性复核，而不是把长期管理直接结束。"),
        ("提交医生", "结果涉及医学解释、异常恶化、用药或其他超出健管边界的事项时，复用 DoctorReview 进行升级。Outcome 和后续决定均进入 Timeline。"),
    )),
    TrainingKnowledgeSpec("data-freshness", "健康数据缺失与陈旧数据处理规范", "TRAINING_MATERIAL", (
        ("语义边界", "无数据不等于正常；没有 RiskEvent 不等于 Green；没有 Clinical Rule 覆盖也不等于已评估为低风险。界面应显示暂无足够数据、需要更新或未评估。"),
        ("陈旧数据", "展示最近记录值时同时显示最后记录时间和数据新鲜度。较久未更新或数据较旧时，不能继续把历史值表述为当前稳定状态。"),
        ("设备与同步", "先检查数据来源、最近同步时间和设备状态。设备异常时安排设备核查；没有设备时说明可用的手工记录或报告路径，不伪造连续数据。"),
        ("数据质量", "SUSPECT 表示数据需确认，INVALID 表示不可用，MISSING 表示暂无数据。先处理质量和补测，再决定是否需要管理或医生介入。"),
        ("下一动作", "可创建平台内提醒补测、联系成员或安排设备检查，并记录负责人和复核时间。新鲜度阈值仅用于展示和运营，不能冒充临床阈值。"),
    )),
    TrainingKnowledgeSpec("communication", "健管客户沟通基本规范", "TRAINING_MATERIAL", (
        ("说明角色", "向成员说明健管师负责资料整理、任务跟进与服务协调；医学解释和医疗决定由医生负责。AI 输出仅作受控信息辅助。"),
        ("说明状态", "使用成员可理解的语言说明已收到、整理中、等待审核、等待医生、待随访或已完成，并明确下一步和预计由谁处理。"),
        ("尊重选择", "讨论计划时提供接受、希望调整和暂缓选择，了解现实障碍，不使用恐吓或把未完成任务直接描述为疾病恶化。"),
        ("证据与不确定性", "区分成员事实、知识解释和医生判断。资料不足时明确说明未评估或依据不足，不用 AI 常识补全正式回答。"),
    )),
    TrainingKnowledgeSpec("common-errors", "新人健管常见错误案例", "TRAINING_MATERIAL", (
        ("把运营风险当诊断", "错误：看到 Yellow 或 Red 就向成员宣布疾病。正确：说明这是人工运营分流，先核对 Evidence，并在需要医学判断时提交医生。"),
        ("接手后让事项消失", "错误：点击接手后从 Worklist 删除。正确：进入处理中、等待成员、等待医生或待随访，直到有关闭原因与最终动作。"),
        ("没有Owner和Due", "错误：只记录需要关注。正确：每个活动事项明确负责人、下一动作；有实际期限时记录 Due，没有期限时不伪造。"),
        ("把Outcome当终点", "错误：只展示改善或未改善。正确：选择继续、调整、稳定管理或提交医生，并设置下一复盘。"),
        ("用模型补知识", "错误：知识库未命中时让模型自由回答并补一个来源。正确：显示依据不足，等待资料补充和审核。"),
    )),
)


def seed_training_knowledge(session: Session) -> dict[str, int]:
    """Add missing owned demo materials as APPROVED, without replacing user knowledge."""
    service = KnowledgeService()
    created_documents = 0
    created_chunks = 0
    for spec in TRAINING_KNOWLEDGE_V1:
        external_id = f"portfolio-training-v1-{spec.code}"
        existing = session.scalar(select(KnowledgeDocument).where(
            KnowledgeDocument.source_provider == "PORTFOLIO_TRAINING",
            KnowledgeDocument.source_external_id == external_id,
        ))
        if existing is not None:
            existing.metadata_json = {
                **(existing.metadata_json or {}),
                "jurisdiction": ["GLOBAL"],
                "audience": ["HEALTH_MANAGER", "TRAINING", "AI_INTERNAL"],
                "intended_use": ["TRAINING", "WORKFLOW_GUIDANCE"],
                "prohibited_use": ["NOT_FOR_DIAGNOSIS", "NOT_FOR_PRESCRIPTION", "NOT_FOR_AUTOMATIC_RISK", "NOT_FOR_EMERGENCY_AUTOMATION"],
            }
            continue
        document = service.create_document(
            session,
            title=spec.title,
            category=spec.category,
            source_type=spec.category,
            source_name="Executive HealthOps Portfolio Training SOP",
            source_provider="PORTFOLIO_TRAINING",
            source_external_id=external_id,
            summary=spec.sections[0][1],
            content_text=spec.content,
            version="v1.0",
            retrieved_at=datetime(2026, 9, 1, tzinfo=timezone.utc),
            license_note="本项目原创 Internal Demo Training Material；不代表医院制度或临床指南。",
            attribution="Executive HealthOps Portfolio Training SOP · Synthetic / Demo",
            review_status="PENDING_REVIEW",
            review_due_at=date(2027, 9, 1),
            tags=("Portfolio Training SOP", "Internal Demo Training Material", "Synthetic"),
            metadata_json={
                "portfolio_demo": True,
                "synthetic_demo": True,
                "portfolio_training_sop": True,
                "language": "zh-CN",
                "audience": ["HEALTH_MANAGER", "TRAINING", "AI_INTERNAL"],
                "jurisdiction": ["GLOBAL"],
                "intended_use": ["TRAINING", "WORKFLOW_GUIDANCE"],
                "prohibited_use": ["NOT_FOR_DIAGNOSIS", "NOT_FOR_PRESCRIPTION", "NOT_FOR_AUTOMATIC_RISK", "NOT_FOR_EMERGENCY_AUTOMATION"],
            },
        )
        service.approve_document(session, document, "Portfolio Demo Governance", "原创演示资料已按当前产品工作流核对；仅用于培训演示。")
        created_documents += 1
        created_chunks += len(spec.sections)
    session.flush()
    total_documents = int(session.scalar(select(func.count()).select_from(KnowledgeDocument).where(
        KnowledgeDocument.source_provider == "PORTFOLIO_TRAINING"
    )) or 0)
    total_chunks = int(session.scalar(select(func.count()).select_from(KnowledgeChunk).join(KnowledgeDocument).where(
        KnowledgeDocument.source_provider == "PORTFOLIO_TRAINING"
    )) or 0)
    return {"created_documents": created_documents, "created_chunks": created_chunks, "documents": total_documents, "chunks": total_chunks}
