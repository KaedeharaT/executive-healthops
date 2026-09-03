from __future__ import annotations

import io
import json
from pathlib import Path
from uuid import UUID
from zipfile import ZIP_DEFLATED, ZipFile

import pandas as pd
import pytest
from sqlalchemy import create_engine, func, select
from sqlalchemy.orm import Session
from streamlit.testing.v1 import AppTest

from executive_health_ai.models import Base, IngestionJob, KnowledgeDocument, Observation, Patient, RiskEvent
from executive_health_ai.services.data_packages import (
    DataPackageAdapter,
    DataPackageError,
    HealthDataImportService,
    KnowledgePackageAdapter,
    build_healthops_template,
    build_synthetic_package,
)


def _session() -> Session:
    engine = create_engine("sqlite+pysqlite:///:memory:")
    Base.metadata.create_all(engine)
    return Session(engine)


def _csv(member: str = "PARTNER-001", *, metric: str = "收缩压", value: str = "120", unit: str = "mmHg", at: str = "2026-09-03T08:00:00+09:00") -> bytes:
    return pd.DataFrame([{
        "外部成员编号": member, "指标名称": metric, "数值": value,
        "单位": unit, "采集时间": at, "数据来源": "synthetic partner",
    }]).to_csv(index=False).encode("utf-8-sig")


def test_csv_json_xlsx_and_manifest_zip_share_one_inspection_contract() -> None:
    adapter = DataPackageAdapter()
    csv_result = adapter.inspect("observations.csv", _csv())
    json_result = adapter.inspect("observations.json", json.dumps({"records": [{
        "external_member_id": "PARTNER-001", "metric": "steps", "value": 8000,
        "unit": "count", "observed_at": "2026-09-03T20:00:00+09:00", "source": "synthetic",
    }]}).encode())
    xlsx_result = adapter.inspect("HealthOps数据模板.xlsx", build_healthops_template())
    zip_result = adapter.inspect("synthetic_health_package.zip", build_synthetic_package())
    assert csv_result.counts["observations"] == 1
    assert json_result.counts["observations"] == 1
    assert xlsx_result.counts["observations"] == 1
    assert zip_result.package_name == "HealthOps 匿名演示数据包"
    assert zip_result.schema_version == "1.0"
    assert all(adapter.preview(item) for item in (csv_result, json_result, xlsx_result, zip_result))


def test_single_files_identify_business_record_type_without_table_selection() -> None:
    adapter = DataPackageAdapter()
    members = adapter.inspect("partner-export.csv", pd.DataFrame([{
        "外部成员编号": "DEMO-01", "姓名或显示名": "匿名成员",
    }]).to_csv(index=False).encode("utf-8-sig"))
    services = adapter.inspect("delivery.json", json.dumps({"services": [{
        "外部成员编号": "DEMO-01", "服务名称": "健康复盘", "完成时间": "2026-09-03",
    }]}).encode())
    assert members.counts == {"members": 1}
    assert services.counts == {"services": 1}


def test_validation_reports_bad_unit_bad_date_and_missing_business_fields() -> None:
    bad_unit = DataPackageAdapter().inspect("bad-unit.csv", _csv(unit="unknown-unit"))
    bad_date = DataPackageAdapter().inspect("bad-date.csv", _csv(at="yesterday"))
    missing = DataPackageAdapter().inspect("missing.csv", pd.DataFrame([{"指标名称": "血糖"}]).to_csv(index=False).encode())
    assert any("数值或单位需要确认" in issue.message for issue in bad_unit.issues)
    assert any("采集时间格式" in issue.message for issue in bad_date.issues)
    assert any("外部成员编号" in issue.message for issue in missing.issues)


def test_member_matching_and_confirmed_import_are_traceable_and_duplicate_safe() -> None:
    inspection = DataPackageAdapter().inspect("observations.csv", _csv())
    with _session() as session:
        member = Patient(external_id="PARTNER-001", display_name="Synthetic Member", timezone="Asia/Tokyo")
        session.add(member); session.commit()
        service = HealthDataImportService()
        assert service.unmatched_member_codes(session, inspection) == []
        result = service.import_package(session, inspection, imported_by="synthetic admin")
        session.commit()
        assert result.status == "SUCCESS" and result.created == 1 and result.members == 1
        job = session.get(IngestionJob, UUID(result.job_id))
        assert job and job.external_sync_id == inspection.package_hash and job.created_by == "synthetic admin"
        assert job.installation_id == inspection.source
        assert session.scalar(select(func.count()).select_from(Observation)) == 1
        duplicate = service.import_package(session, inspection, imported_by="synthetic admin")
        assert duplicate.status == "DUPLICATE_PACKAGE" and duplicate.previous_job_id == result.job_id
        assert session.scalar(select(func.count()).select_from(Observation)) == 1


def test_missing_member_can_be_linked_created_as_draft_or_left_pending() -> None:
    inspection = DataPackageAdapter().inspect("observations.csv", _csv("UNMATCHED-01"))
    with _session() as session:
        existing = Patient(external_id="EXISTING", display_name="Synthetic Existing", timezone="Asia/Tokyo")
        session.add(existing); session.commit()
        service = HealthDataImportService()
        assert service.unmatched_member_codes(session, inspection) == ["UNMATCHED-01"]
        result = service.import_package(session, inspection, member_overrides={"UNMATCHED-01": str(existing.id)})
        session.commit()
        assert result.created == 1 and result.pending_review == 0

    second = DataPackageAdapter().inspect("second.csv", _csv("DRAFT-01", metric="steps", value="5000", unit="count"))
    with _session() as session:
        result = HealthDataImportService().import_package(session, second, member_overrides={"DRAFT-01": "CREATE_DRAFT"})
        session.commit()
        assert result.created == 1
        assert session.scalar(select(Patient).where(Patient.external_id == "DRAFT-01")).display_name.startswith("待完善成员")


def test_external_risk_label_is_ignored_and_does_not_bypass_rules() -> None:
    payload = json.dumps({"records": [{
        "external_member_id": "SAFE-01", "metric": "steps", "value": 7000, "unit": "count",
        "observed_at": "2026-09-03T20:00:00+09:00", "risk": "RED", "diagnosis": "external claim",
    }]}).encode()
    inspection = DataPackageAdapter().inspect("external.json", payload)
    with _session() as session:
        session.add(Patient(external_id="SAFE-01", timezone="Asia/Tokyo")); session.commit()
        result = HealthDataImportService().import_package(session, inspection)
        session.commit()
        assert result.created == 1
        assert session.scalar(select(func.count()).select_from(RiskEvent)) == 0


def test_import_rolls_back_as_one_transaction(monkeypatch) -> None:
    inspection = DataPackageAdapter().inspect("observations.csv", _csv())
    with _session() as session:
        session.add(Patient(external_id="PARTNER-001", timezone="Asia/Tokyo")); session.commit()
        monkeypatch.setattr("executive_health_ai.services.data_packages.ingest", lambda *args, **kwargs: (_ for _ in ()).throw(RuntimeError("synthetic failure")))
        with pytest.raises(RuntimeError):
            HealthDataImportService().import_package(session, inspection)
        assert session.scalar(select(func.count()).select_from(IngestionJob)) == 0
        assert session.scalar(select(func.count()).select_from(Observation)) == 0


def test_zip_traversal_bomb_executable_and_formula_are_blocked() -> None:
    adapter = DataPackageAdapter()
    unsafe = io.BytesIO()
    with ZipFile(unsafe, "w", ZIP_DEFLATED) as archive:
        archive.writestr("../observations.csv", _csv())
    with pytest.raises(DataPackageError, match="不安全"):
        adapter.inspect("unsafe.zip", unsafe.getvalue())
    executable = io.BytesIO()
    with ZipFile(executable, "w", ZIP_DEFLATED) as archive:
        archive.writestr("run.exe", b"not executable")
    with pytest.raises(DataPackageError, match="只能包含"):
        adapter.inspect("executable.zip", executable.getvalue())
    bomb = io.BytesIO()
    with ZipFile(bomb, "w", ZIP_DEFLATED) as archive:
        archive.writestr("observations.csv", b"0" * 50_000)
    with pytest.raises(DataPackageError, match="压缩比例异常"):
        adapter.inspect("bomb.zip", bomb.getvalue())
    formula = pd.DataFrame([{"外部成员编号": "=CMD()", "指标名称": "steps", "数值": 1, "单位": "count", "采集时间": "2026-09-03T00:00:00+09:00"}]).to_csv(index=False).encode()
    with pytest.raises(DataPackageError, match="公式"):
        adapter.inspect("formula.csv", formula)


def _knowledge_package(*, include_source: bool = True) -> bytes:
    document = {"document_key": "demo-1", "title": "Synthetic health education", "source": "Synthetic Partner", "organization": "Demo Org", "version": "v1", "category": "PATIENT_EDUCATION", "source_url": "https://example.invalid/demo", "license_note": "Synthetic test only"}
    if not include_source:
        document.pop("source")
    output = io.BytesIO()
    with ZipFile(output, "w", ZIP_DEFLATED) as archive:
        archive.writestr("documents.jsonl", json.dumps(document) + "\n")
        archive.writestr("chunks.jsonl", json.dumps({"document_key": "demo-1", "heading": "Overview", "section": "1", "content": "Synthetic reviewed content candidate."}) + "\n")
        archive.writestr("source_registry.json", json.dumps({"sources": [{"name": "Synthetic Partner"}]}))
    return output.getvalue()


def test_knowledge_package_requires_source_and_enters_pending_review_only() -> None:
    adapter = KnowledgePackageAdapter()
    with pytest.raises(DataPackageError, match="来源"):
        adapter.inspect(_knowledge_package(include_source=False))
    inspection = adapter.inspect(_knowledge_package())
    with _session() as session:
        assert adapter.import_for_review(session, inspection) == 1
        session.commit()
        document = session.scalar(select(KnowledgeDocument))
        assert document and document.review_status == "PENDING_REVIEW" and document.source_name == "Synthetic Partner"


def test_integration_center_uses_business_copy_and_hides_connection_secrets() -> None:
    source = Path("streamlit_app.py").read_text(encoding="utf-8")
    shell = Path("src/executive_health_ai/ui/pages/shell.py").read_text(encoding="utf-8")
    center = source.split("def render_integration_center", 1)[1].split("def render_more_workspace", 1)[0]
    for label in ("集成与数据", "数据导入", "AI服务", "专业知识", "设备接入", "上传数据包"):
        assert label in source
    assert 'type="password"' in source and "DATABASE_URL" not in center
    assert 'options = ["风险规则", "操作记录", "系统"]' in shell
    assert "成员端与医生工作视图不提供配置入口" in center
    assert "raw JSON" not in center and "UUID" not in center and "provider code" not in center


def test_all_four_integration_modes_render_in_the_same_system_page() -> None:
    app = AppTest.from_file(Path(__file__).resolve().parents[1] / "streamlit_app.py")
    app.run(timeout=30)
    next(item for item in app.radio if item.label == "工作区").set_value("更多")
    app.run(timeout=30)
    next(item for item in app.button if item.key == "more-open-系统").click()
    app.run(timeout=30)
    assert not app.exception
    for key in ("integration-open-data", "integration-open-ai", "integration-open-knowledge", "integration-open-device"):
        next(item for item in app.button if item.key == key).click()
        app.run(timeout=30)
        assert not app.exception
