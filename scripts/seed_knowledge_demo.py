"""Create a small, idempotent set of clearly synthetic knowledge-library examples."""

from executive_health_ai.database import SessionLocal
from executive_health_ai.models import KnowledgeDocument
from executive_health_ai.services.knowledge import KnowledgeService
from sqlalchemy import select


DEMO_DOCUMENTS = [
    {"title": "家庭血压异常处理流程（演示）", "category": "SERVICE_SOP", "summary": "演示连续家庭血压异常后的健康管理师核实、医生升级与随访流程。", "source_type": "企业内部SOP"},
    {"title": "90天代谢健康管理模板（演示）", "category": "MANAGEMENT_PROGRAM", "summary": "演示阶段目标、周任务与阶段复评的资料结构。", "source_type": "人工整理"},
    {"title": "苹果健康数据接入说明（演示）", "category": "DATA_DEVICE", "summary": "演示苹果健康数据的来源、质量和成员匹配说明。", "source_type": "设备厂商资料"},
    {"title": "AI医疗边界说明（演示）", "category": "SAFETY_COMPLIANCE", "summary": "演示 AI 辅助不得替代诊断、处方或紧急医学判断的治理边界。", "source_type": "企业内部SOP"},
]


def main() -> None:
    service = KnowledgeService()
    with SessionLocal() as session:
        existing = set(session.scalars(select(KnowledgeDocument.title)))
        for item in DEMO_DOCUMENTS:
            if item["title"] in existing:
                continue
            document = service.create_document(
                session, title=item["title"], category=item["category"], summary=item["summary"],
                content_text="合成演示资料，不作为真实医学指南或临床决策依据。",
                source_type=item["source_type"], source_name="合成演示资料", version="v1.0",
                tags=["演示资料"], review_status="APPROVED", metadata_json={"synthetic_demo": True},
            )
            service.approve_document(session, document, "演示审核人")
        session.commit()


if __name__ == "__main__":
    main()
