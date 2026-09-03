"""Build the isolated, reproducible Executive HealthOps portfolio demo.

This script intentionally never opens, resets, or changes the normal development
database.  It creates ``data/portfolio_demo.db`` from migrations and synthetic,
anonymised fixture data only.  It does not copy a member report or any PHI.
"""

from __future__ import annotations

import argparse
import os
import runpy
import subprocess
import sys
from datetime import date, datetime, timezone
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_DATABASE = ROOT / "data" / "portfolio_demo.db"
DEMO_EXTERNAL_ID = "portfolio-demo-executive-a"


def _configure_console_encoding() -> None:
    """Keep synthetic-demo status output usable in legacy Windows consoles."""
    for stream in (sys.stdout, sys.stderr):
        try:
            stream.reconfigure(encoding="utf-8")
        except (AttributeError, OSError):
            # Embedded or redirected streams may not expose ``reconfigure``.
            pass


def _safe_target(path: Path) -> Path:
    """Allow only the dedicated portfolio SQLite file to be rebuilt."""
    target = path.resolve()
    expected_parent = (ROOT / "data").resolve()
    if target.parent != expected_parent or target.name != "portfolio_demo.db":
        raise ValueError("仅允许创建 data/portfolio_demo.db，绝不会修改开发数据库。")
    return target


def _database_url(target: Path) -> str:
    return f"sqlite:///{target.as_posix()}"


def _run_migrations(target: Path) -> None:
    env = os.environ.copy()
    env["DATABASE_URL"] = _database_url(target)
    subprocess.run(
        [sys.executable, "-m", "alembic", "upgrade", "head"],
        cwd=ROOT,
        env=env,
        check=True,
    )


def _seed_existing_demo() -> None:
    """Reuse the tested synthetic foundation, then replace portfolio-facing data."""
    seeded = runpy.run_path(str(ROOT / "scripts" / "seed_full_demo.py"), run_name="portfolio_seed")
    # Portfolio/current workflow deliberately excludes the legacy V0.1 Alert
    # fixture.  The following RiskEvent seed is the only new risk write path.
    seeded["seed_full_demo"](include_legacy_alert_workflow=False)
    # This script creates TEST-scope workflow fixtures only.  It never creates
    # a Clinical RiskRule and its UI is marked as an 演示风险 by the app.
    runpy.run_path(str(ROOT / "scripts" / "seed_risk_demo.py"), run_name="portfolio_risk_seed")


def _replace_report_fixture(session, patient_id) -> None:
    """Create a compact, anonymous report story with honest fixture evidence."""
    from sqlalchemy import delete, select

    from executive_health_ai.models import Document, ReportExtractionCandidate, ReportExtractionRun

    document_ids = list(session.scalars(select(Document.id).where(Document.patient_id == patient_id)))
    if document_ids:
        session.execute(delete(ReportExtractionCandidate).where(ReportExtractionCandidate.document_id.in_(document_ids)))
        session.execute(delete(ReportExtractionRun).where(ReportExtractionRun.document_id.in_(document_ids)))
        session.execute(delete(Document).where(Document.id.in_(document_ids)))

    report = Document(
        patient_id=patient_id,
        document_type="health_check_report",
        title="2024年度综合体检报告（演示）",
        storage_reference="portfolio-demo://anonymous-report-2024",
        source="portfolio_demo_fixture",
        status="AVAILABLE",
    )
    session.add(report)
    session.flush()
    run = ReportExtractionRun(
        document_id=report.id,
        patient_id=patient_id,
        status="COMPLETED",
        parser_version="portfolio-fixture-v1",
        canonical_registry_version="v1",
        file_hash="portfolio-demo-report-2024-v1",
        file_type="PDF",
        detected_hospital="演示医疗机构",
        detected_report_type="年度综合体检",
        detected_report_date=date(2024, 8, 20),
        page_count=17,
        has_text_layer=True,
        llm_used=True,
        llm_provider="local_llm",
        llm_status="COMPLETED",
        candidate_count=8,
        high_confidence_count=6,
        medium_confidence_count=2,
        completed_at=datetime(2024, 8, 20, 10, tzinfo=timezone.utc),
        metadata_json={"portfolio_fixture": True, "anonymised": True},
    )
    session.add(run)
    session.flush()

    rows = [
        ("OBSERVATION", "ldl", "低密度脂蛋白胆固醇", "4.20", "mmol/L", "< 3.40", "HIGH", "血脂检查", 6, "低密度脂蛋白胆固醇（LDL-C）4.20 mmol/L，参考范围 < 3.40 mmol/L。"),
        ("OBSERVATION", "triglyceride", "甘油三酯", "2.10", "mmol/L", "< 1.70", "HIGH", "血脂检查", 6, "甘油三酯（TG）2.10 mmol/L，参考范围 < 1.70 mmol/L。"),
        ("OBSERVATION", "hba1c", "糖化血红蛋白", "6.10", "%", "4.0–6.0", "HIGH", "糖代谢检查", 7, "糖化血红蛋白（HbA1c）6.10%，参考范围 4.0–6.0%。"),
        ("OBSERVATION", "bmi", "体重指数", "26.90", "kg/m²", "18.5–23.9", "HIGH", "人体成分", 2, "体重指数（BMI）26.90 kg/m²，参考范围 18.5–23.9 kg/m²。"),
        ("FINDING", None, "胸部CT", None, None, None, "ABNORMAL", "胸部CT", 12, "胸部CT：左肺下叶见小结节影，建议结合临床情况随访复查。"),
        ("FINDING", None, "甲状腺超声", None, None, None, "ABNORMAL", "甲状腺超声", 11, "甲状腺超声：甲状腺结节，建议按报告建议随访。"),
        ("FINDING", None, "腹部超声", None, None, None, "ABNORMAL", "腹部超声", 10, "腹部超声：脂肪肝表现，建议结合生活方式管理与人工随访。"),
        ("HISTORY", None, "既往手术史", None, None, None, None, "既往史", 1, "既往手术史：已记录一项既往手术信息，具体信息由人工核对后纳入健康档案。"),
    ]
    for candidate_type, code, name, value, unit, reference, flag, section, page, evidence in rows:
        summary = f"{name}需要人工结合完整报告跟进。" if candidate_type == "FINDING" else None
        if candidate_type == "HISTORY":
            summary = "既往手术记录已提取，等待人工核对。"
        session.add(ReportExtractionCandidate(
            extraction_run_id=run.id,
            document_id=report.id,
            patient_id=patient_id,
            candidate_type=candidate_type,
            canonical_code=code,
            raw_name=name,
            raw_value=value,
            normalized_value=value,
            unit=unit,
            reference_range=reference,
            abnormal_flag=flag,
            summary=summary,
            confidence="HIGH" if candidate_type != "FINDING" else "MEDIUM",
            extraction_method="HYBRID",
            source_page=page,
            source_section=section,
            evidence_text=evidence,
            status="CONFIRMED",
            reviewed_by="演示健康管理师",
            reviewed_at=datetime(2024, 8, 20, 11, tzinfo=timezone.utc),
        ))


def _add_knowledge_demo(session) -> None:
    """Add small, original demo metadata—never copied full external content."""
    from datetime import date as date_type

    from executive_health_ai.services.knowledge import KnowledgeService

    service = KnowledgeService()
    service.ensure_source_registry(session)
    documents = [
        {
            "title": "High Blood Pressure（演示引用）",
            "category": "PATIENT_EDUCATION",
            "source_type": "PATIENT_EDUCATION",
            "source_name": "MedlinePlus · NLM / NIH",
            "source_provider": "MEDLINEPLUS",
            "source_external_id": "portfolio-high-blood-pressure",
            "source_url": "https://medlineplus.gov/highbloodpressure.html",
            "summary": "用于演示健康教育资料的来源、审核和引用追溯；不构成诊断或治疗建议。",
            "license_note": "按需查询并保留来源链接；不镜像完整页面。",
            "attribution": "MedlinePlus, U.S. National Library of Medicine.",
        },
        {
            "title": "Metformin（演示标准词条）",
            "category": "TERMINOLOGY",
            "source_type": "TERMINOLOGY",
            "source_name": "RxNorm · NLM",
            "source_provider": "RXNORM",
            "source_external_id": "6809",
            "source_url": "https://rxnav.nlm.nih.gov/REST/rxcui/6809/properties.json",
            "summary": "RXCUI 6809 的药物标准化演示资料；用于术语映射，不提供处方或治疗建议。",
            "license_note": "按 NLM/RxNorm 使用条款保留来源与归属。",
            "attribution": "RxNorm, U.S. National Library of Medicine.",
        },
        {
            "title": "Metformin FDA 药品标签（待审核演示）",
            "category": "REGULATORY",
            "source_type": "REGULATORY",
            "source_name": "openFDA · FDA",
            "source_provider": "OPENFDA",
            "source_external_id": "portfolio-metformin-label",
            "source_url": "https://open.fda.gov/apis/drug/label/",
            "summary": "用于展示监管资料保存与人工审核；监管资料不替代医生判断。",
            "license_note": "保留 FDA/openFDA 来源说明；不将监管资料自动转为医疗决策。",
            "attribution": "openFDA, U.S. Food and Drug Administration.",
        },
    ]
    for index, item in enumerate(documents):
        document = service.create_document(
            session,
            **item,
            content_text=item["summary"],
            source_reference=item["source_url"],
            retrieved_at=datetime(2026, 8, 30, tzinfo=timezone.utc),
            review_status="PENDING_REVIEW",
            review_due_at=date_type(2027, 8, 30),
            tags=("作品集演示", item["source_provider"]),
            metadata_json={"portfolio_demo": True, "no_full_text_mirror": True},
        )
        if index < 2:
            service.approve_document(session, document, "演示审核人", "已核对来源、用途与许可说明。")

    from executive_health_ai.services.healthops_internal_knowledge import seed_healthops_internal_knowledge
    from executive_health_ai.services.knowledge_foundation import sync_source_registry
    from executive_health_ai.services.public_knowledge_seed import seed_public_knowledge

    seed_healthops_internal_knowledge(session)
    sync_source_registry(session)
    # Only original summaries with verified official provenance are approved
    # by the synthetic Portfolio governance path. No external page is mirrored.
    seed_public_knowledge(session, approve_for_portfolio=True)


def _add_ai_feedback_demo(session, patient_id) -> None:
    """Seed governance-only synthetic feedback; never train or deploy a model."""
    from executive_health_ai.services.ai_feedback import (
        AI_CONTENT_FEEDBACK, FeedbackDatasetBuilder, FeedbackService, ModelRegistryService,
    )

    service = FeedbackService()
    rows = [
        service.capture(
            session, feedback_type=AI_CONTENT_FEEDBACK, feature="report_semantic_mapping",
            source_entity_type="ReportExtractionCandidate", source_entity_id="synthetic-report-correction",
            member_id=patient_id, feedback_label="HUMAN_CORRECTION", created_by="演示审核人",
            input_material="synthetic:HbA1c:fasting_glucose", prediction_summary="HbA1c",
            human_correction="空腹血糖", feedback_reason="演示语义字段纠正",
            evidence_refs=[{"type": "REPORT_EVIDENCE", "page": 1}],
            model_provider="demo", model_name="synthetic-parser", model_version="demo-v1",
            prompt_version="report-v1", eligible_for_training=True, deidentified=True,
        ),
        service.capture(
            session, feedback_type=AI_CONTENT_FEEDBACK, feature="report_summary",
            source_entity_type="ReportExtractionRun", source_entity_id="synthetic-summary-correction",
            member_id=patient_id, feedback_label="HUMAN_CORRECTION", created_by="演示审核人",
            input_material="synthetic:summary", prediction_summary="需要关注",
            human_correction="需要结合原报告依据人工复核", feedback_reason="演示摘要边界纠正",
            evidence_refs=[{"type": "REPORT_EVIDENCE", "page": 1}],
            model_provider="demo", model_name="synthetic-parser", model_version="demo-v1",
            prompt_version="summary-v1", eligible_for_training=True, deidentified=True,
        ),
        service.capture_citation_feedback(
            session, answer_id="synthetic-grounded-answer", label="IRRELEVANT",
            reason="演示引用相关性反馈", actor="演示知识审核人",
        ),
    ]
    for row in rows:
        service.review(session, row.id, reviewer="演示 AI 治理审核人", accepted=True)
        service.accept_for_dataset(session, row.id, reviewer="演示 AI 治理审核人")
    dataset = FeedbackDatasetBuilder().build(
        session, dataset_id="portfolio-feedback", actor="演示 AI 治理审核人",
    )
    registry = ModelRegistryService()
    candidate = registry.create_candidate(
        session, provider="demo", base_model="configurable-llm",
        model_version="portfolio-candidate-v1", prompt_version="candidate-prompt-v1",
        training_dataset_version=f"{dataset.dataset_id}-v{dataset.dataset_version:03d}",
    )
    registry.record_evaluation(session, candidate.id, actor="演示评测流程", report={
        "citation_validity": 1.0, "hallucination_rate": 0.0,
        "critical_task_success": 1.0, "unsafe_answer_rate": 0.0,
        "no_source_refusal": True, "safety_regression": False,
        "demo_only": True,
    })


def _customize_portfolio_data() -> dict[str, int]:
    from sqlalchemy import func, select

    from executive_health_ai.database import SessionLocal
    from executive_health_ai.models import (
        Document, DoctorReview, HealthAssessment, HealthProgram, KnowledgeDocument, MedicationPlan,
        Patient, RiskEvent, ServiceCatalogItem, ServiceRequest, Task,
    )
    from executive_health_ai.services.member_services import MemberServiceOperations
    from executive_health_ai.services.risk_operations import RiskOperationsService

    with SessionLocal() as session:
        patient = session.scalar(select(Patient).where(Patient.external_id == "demo-executive-001"))
        if patient is None:
            raise RuntimeError("未能建立作品集演示成员。")
        patient.external_id = DEMO_EXTERNAL_ID
        patient.display_name = "Demo Executive A"
        patient.sex = "未说明"

        for task in session.scalars(select(Task).where(Task.patient_id == patient.id)):
            if task.assignee:
                task.assignee = "Demo Executive A"
        for program in session.scalars(select(HealthProgram).where(HealthProgram.patient_id == patient.id)):
            if "90-Day" in program.title or "90天" in program.title:
                program.title = "90天代谢健康计划（演示）"
                program.status = "ACTIVE"
                program.next_decision = "等待医生复核"
        for assessment in session.scalars(select(HealthAssessment).where(HealthAssessment.patient_id == patient.id)):
            assessment.title = "健康基线（演示）"
            assessment.summary = "基于匿名化体检结构、连续健康数据和人工管理记录整理的演示健康基线；不构成医学诊断。"
        medication_names = ["代谢健康用药记录（演示）", "血脂管理用药记录（演示）", "睡眠支持用药记录（演示）"]
        for index, plan in enumerate(session.scalars(select(MedicationPlan).where(MedicationPlan.patient_id == patient.id))):
            plan.drug_name = medication_names[index % len(medication_names)]
            plan.generic_name = None
            plan.dose = "按医嘱记录"
            plan.dose_unit = ""
            plan.prescriber_name = "待人工确认"

        _replace_report_fixture(session, patient.id)
        # Keep one human-owned Yellow path ready for the five-minute demo.  It
        # uses the existing TEST/demo rule only and never creates a clinical rule.
        yellow = session.scalar(select(RiskEvent).where(
            RiskEvent.patient_id == patient.id, RiskEvent.risk_level == "YELLOW",
        ).order_by(RiskEvent.created_at.desc()))
        if yellow is not None:
            yellow.status = "NEW"
            yellow.acknowledged_by = None
            yellow.acknowledged_at = None
            yellow.resolved_at = None
            if session.scalar(select(DoctorReview).where(DoctorReview.risk_event_id == yellow.id, DoctorReview.status == "PENDING")) is None:
                RiskOperationsService().escalate_to_doctor(
                    session, yellow.id, "演示健康管理师", "请医生人工确认下一步随访与管理安排。", "全科/健康管理",
                )
        # A completed Red fixture remains available for longitudinal history;
        # it does not obscure the active Yellow manager/doctor story.
        for red in session.scalars(select(RiskEvent).where(RiskEvent.patient_id == patient.id, RiskEvent.risk_level == "RED")):
            red.status = "CLOSED"
            red.resolved_at = red.resolved_at or datetime(2026, 8, 15, 10, tzinfo=timezone.utc)
        if session.scalar(select(Task).where(Task.patient_id == patient.id, Task.source == "portfolio_member_plan_task", Task.status.not_in(("COMPLETED", "CANCELLED")))) is None:
            active_program = session.scalar(select(HealthProgram).where(HealthProgram.patient_id == patient.id, HealthProgram.status == "ACTIVE").order_by(HealthProgram.created_at.desc()))
            session.add(Task(
                patient_id=patient.id, program_id=active_program.id if active_program else None,
                title="完成本周睡眠与活动记录", instruction="本周完成三次睡眠与活动记录；这是一项成员健康管理任务，不是医学风险。",
                status="PENDING", priority="MEDIUM", assignee="Demo Executive A", responsible_role="member",
                due_at=datetime(2026, 8, 31, 18, tzinfo=timezone.utc), source="portfolio_member_plan_task",
            ))
        service_plan = MemberServiceOperations().ensure_demo_plan(session, patient.id)
        first_service = session.scalar(select(ServiceCatalogItem).order_by(ServiceCatalogItem.name))
        if first_service is not None and session.scalar(select(ServiceRequest).where(ServiceRequest.patient_id == patient.id)) is None:
            session.add(ServiceRequest(
                patient_id=patient.id,
                service_item_id=first_service.id,
                requested_by="Demo Executive A",
                reason="作品集演示：展示人工服务申请与安排流程。",
                status="SCHEDULED",
                assigned_manager="演示健康管理师",
            ))
        _add_knowledge_demo(session)
        _add_ai_feedback_demo(session, patient.id)
        session.commit()

        return {
            "members": int(session.scalar(select(func.count()).select_from(Patient)) or 0),
            "reports": int(session.scalar(select(func.count()).select_from(Document)) or 0),
            "knowledge_documents": int(session.scalar(select(func.count()).select_from(KnowledgeDocument)) or 0),
            "service_plan": 1 if service_plan else 0,
        }


def build_portfolio_demo(target: Path = DEFAULT_DATABASE, *, rebuild: bool = True) -> dict[str, int]:
    """Create the dedicated portfolio DB and return a small non-PHI manifest."""
    target = _safe_target(target)
    target.parent.mkdir(parents=True, exist_ok=True)
    if target.exists() and rebuild:
        target.unlink()
    if target.exists():
        raise FileExistsError("作品集数据库已存在；使用 --rebuild 重新创建。")
    os.environ["DATABASE_URL"] = _database_url(target)
    _run_migrations(target)
    _seed_existing_demo()
    return _customize_portfolio_data()


def main() -> None:
    _configure_console_encoding()
    parser = argparse.ArgumentParser(description="创建隔离的 Executive HealthOps 作品集演示数据库。")
    parser.add_argument("--rebuild", action="store_true", help="安全地重建 data/portfolio_demo.db")
    args = parser.parse_args()
    counts = build_portfolio_demo(rebuild=args.rebuild)
    print("Portfolio demo database ready:")
    for key, value in counts.items():
        print(f"  {key}: {value}")
    print(f"  database: {DEFAULT_DATABASE.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
