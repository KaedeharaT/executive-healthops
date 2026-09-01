"""Small, original summaries of verified official sources for governed review.

No page is mirrored. Normal development imports are PENDING_REVIEW. Only an
explicit synthetic Portfolio build may mark these curated summaries approved.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, timezone
from hashlib import sha256

from sqlalchemy import select
from sqlalchemy.orm import Session

from executive_health_ai.models import KnowledgeChunk, KnowledgeDocument, KnowledgeReviewAudit


@dataclass(frozen=True)
class PublicSeed:
    source_id: str; external_id: str; title: str; category: str; url: str; jurisdiction: str
    intended_use: tuple[str, ...]; sections: tuple[tuple[str, str], ...]


PUBLIC_SEEDS: tuple[PublicSeed, ...] = (
    PublicSeed("MEDLINEPLUS", "medical-tests-a1c", "糖化血红蛋白（HbA1c）基础说明", "MEDICAL_TEST", "https://medlineplus.gov/lab-tests/hemoglobin-a1c-hba1c-test/", "US", ("EXPLANATION", "MEMBER_EDUCATION"), (("检查用途", "HbA1c用于反映一段时间内的平均血糖状况。单次结果应结合检测条件、既往趋势和医生判断理解。"),("边界", "知识说明不能代替诊断；成员个体目标和复查安排由医疗专业人员结合具体情况确定。"))),
    PublicSeed("MEDLINEPLUS", "ldl-cholesterol", "LDL 与血脂检查基础说明", "MEDICAL_TEST", "https://medlineplus.gov/cholesterol.html", "US", ("EXPLANATION", "MEMBER_EDUCATION"), (("概念", "LDL是血脂信息的一部分，通常需要与总胆固醇、HDL、甘油三酯和整体健康背景共同理解。"),("边界", "系统可解释指标名称和记录趋势，但不根据单项结果自动诊断或决定用药。"))),
    PublicSeed("NHLBI", "high-blood-pressure", "血压持续监测与测量质量", "PATIENT_EDUCATION", "https://www.nhlbi.nih.gov/health/high-blood-pressure", "US", ("EXPLANATION", "MEMBER_EDUCATION"), (("连续记录", "血压会随时间、活动和测量条件变化；连续、可追溯的记录比孤立数值更有助于医疗团队了解趋势。"),("测量边界", "设备、姿势、休息时间和重复测量会影响数据质量。异常或不一致数据应复测或提交专业人员复核。"))),
    PublicSeed("CDC", "physical-activity", "身体活动健康教育", "LIFESTYLE", "https://www.cdc.gov/physical-activity-basics/benefits/", "US", ("EXPLANATION", "MEMBER_EDUCATION"), (("健康作用", "规律身体活动与心血管、代谢、睡眠和情绪健康相关。建议应结合个人能力和健康状况。"),("安全边界", "存在慢性病、症状或运动风险时，应由医疗专业人员确认适合的活动类型和强度。"))),
    PublicSeed("CDC", "sleep-heart", "睡眠与健康基础教育", "LIFESTYLE", "https://www.cdc.gov/heart-disease/about/sleep-and-heart-health.html", "US", ("EXPLANATION", "MEMBER_EDUCATION"), (("睡眠记录", "睡眠时长与质量是长期健康背景的一部分，趋势比单晚数据更有意义。"),("边界", "设备睡眠数据可用于教育和趋势观察，不能由系统自动诊断失眠或睡眠呼吸障碍。"))),
    PublicSeed("CDC", "smoking", "吸烟健康教育与支持边界", "LIFESTYLE", "https://www.cdc.gov/tobacco/about/index.html", "US", ("EXPLANATION", "MEMBER_EDUCATION"), (("教育", "吸烟和烟草暴露是可干预的健康因素；沟通应使用支持性语言并记录成员意愿。"),("升级", "涉及戒烟药物、症状或复杂健康问题时，健管应转交医生或合适的专业服务。"))),
    PublicSeed("NIDDK", "weight-management", "体重与代谢健康教育", "PATIENT_EDUCATION", "https://www.niddk.nih.gov/health-information/weight-management", "US", ("EXPLANATION", "MEMBER_EDUCATION"), (("长期背景", "体重管理应结合长期趋势、生活方式、代谢信息和成员目标，不以单个BMI值替代全面评估。"),("行动边界", "系统支持记录、计划和随访；诊断和药物或手术选择属于医生判断。"))),
    PublicSeed("NIH_ODS", "supplement-safety", "膳食补充剂信息边界", "LIFESTYLE", "https://ods.od.nih.gov/factsheets/list-all/", "US", ("EXPLANATION", "MEMBER_EDUCATION"), (("分类", "膳食补充剂信息与药品标签、处方治疗必须分开管理。"),("安全", "知识库可以说明成分和安全注意事项，但不得据此自动推荐补充剂治疗疾病；相互作用疑问应提交医生或药师。"))),
    PublicSeed("RXNORM", "metformin", "Metformin / 二甲双胍术语规范化", "MEDICATION", "https://rxnav.nlm.nih.gov/REST/drugs.json?name=metformin", "US", ("NORMALIZATION",), (("标准化", "RxNorm用于将药物名称映射到标准概念和标识；二甲双胍与metformin可作为检索别名。"),("边界", "术语匹配不代表处方建议，不能触发自动停药、换药或剂量调整。"))),
    PublicSeed("DAILYMED", "official-label", "官方药品标签检索说明", "MEDICATION", "https://dailymed.nlm.nih.gov/dailymed/app-support-web-services.cfm", "US", ("DOCTOR_REFERENCE", "EXPLANATION"), (("来源", "DailyMed提供版本化的Structured Product Label资料，适合按需查找官方标签来源。"),("边界", "标签资料用于核对和参考，不由AI转化为个体处方决定；实际用药判断由医生承担。"))),
    PublicSeed("APPLE_HEALTHKIT", "healthkit-data", "Apple HealthKit 数据定义边界", "DEVICE_GUIDANCE", "https://developer.apple.com/documentation/healthkit", "GLOBAL", ("NORMALIZATION",), (("技术用途", "HealthKit定义健康和健身数据类型及访问权限，可作为数据接入与来源识别的技术参考。"),("医学边界", "Apple开发文档不是医学解释来源；HealthKit数据仍需保留单位、时间、来源和数据质量。"))),
    PublicSeed("NIST_AI_RMF", "ai-rmf-1", "NIST AI RMF 与 HealthOps AI 治理", "AI_SAFETY", "https://www.nist.gov/publications/artificial-intelligence-risk-management-framework-ai-rmf-10", "GLOBAL", ("TRAINING", "WORKFLOW_GUIDANCE"), (("治理", "AI风险治理应覆盖设计、使用、监测和评估，并强调可靠、安全、透明、可解释、隐私与责任。"),("HealthOps边界", "在HealthOps中，LLM用于语义辅助；确定性代码负责风险与状态，医生保留医学判断，引用和使用记录提供可审计性。"))),
)


def seed_public_knowledge(session: Session, *, approve_for_portfolio: bool = False) -> tuple[int, int]:
    docs = chunks = 0
    now = datetime.now(timezone.utc)
    for seed in PUBLIC_SEEDS:
        existing = session.scalar(select(KnowledgeDocument).where(KnowledgeDocument.source_external_id == f"foundation:{seed.external_id}"))
        if existing: continue
        status = "APPROVED" if approve_for_portfolio else "PENDING_REVIEW"
        content = "\n\n".join(f"## {heading}\n{text}" for heading, text in seed.sections)
        document = KnowledgeDocument(title=seed.title, category=seed.category, summary="基于官方来源整理的原创中文摘要；不是原文翻译。",
            content_text=content, source_type="OFFICIAL_PUBLIC_SUMMARY", source_name=seed.source_id,
            source_reference=seed.url, source_provider=seed.source_id, source_external_id=f"foundation:{seed.external_id}",
            source_url=seed.url, source_version="accessed-2026-09-02", retrieved_at=now,
            license_note="See governed source registry; no protected full text copied.", attribution=f"Source: {seed.source_id}",
            content_hash=sha256(content.encode()).hexdigest(), version="v1.0", tags=[seed.source_id, seed.category], language="zh-CN",
            review_status=status, reviewed_by="Portfolio demo governance" if approve_for_portfolio else None,
            reviewed_at=now if approve_for_portfolio else None, review_comment="Synthetic Portfolio approval of original summary only" if approve_for_portfolio else "Requires human knowledge review",
            review_due_at=date(2027, 3, 2), effective_date=date(2026, 9, 2), is_active=True,
            metadata_json={"jurisdiction":[seed.jurisdiction], "audience":["MEMBER","HEALTH_MANAGER","DOCTOR","AI_INTERNAL"],
                "intended_use":list(seed.intended_use), "prohibited_use":["NOT_FOR_DIAGNOSIS","NOT_FOR_PRESCRIPTION","NOT_FOR_AUTOMATIC_RISK","NOT_FOR_EMERGENCY_AUTOMATION"],
                "normalized_summary_zh":True, "translation_status":"ORIGINAL_SUMMARY_NOT_TRANSLATION", "source_strategy":"PUBLIC_SUMMARY"})
        session.add(document); session.flush(); docs += 1
        for index, (heading, text) in enumerate(seed.sections):
            session.add(KnowledgeChunk(knowledge_document_id=document.id, chunk_index=index, heading=heading, content=text,
                source_location=f"§ {heading}", content_length=len(text), token_estimate=max(1, len(text)//2))); chunks += 1
        if approve_for_portfolio:
            session.add(KnowledgeReviewAudit(knowledge_document_id=document.id, reviewer="Portfolio demo governance", previous_status="PENDING_REVIEW", new_status="APPROVED", review_comment="Original summary and official-source provenance reviewed for synthetic demo."))
    session.flush()
    return docs, chunks
