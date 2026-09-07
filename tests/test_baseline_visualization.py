"""Read-only health-baseline visualization projections and chart safety."""
from __future__ import annotations

from copy import deepcopy
from datetime import date, datetime, timezone
from decimal import Decimal

from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from executive_health_ai.models import Base, Document, HealthAssessment, Observation, Patient, ReportExtractionCandidate, ReportExtractionRun
from executive_health_ai.services.baseline_visualization import BaselineVisualizationService, parse_reference_interval
from executive_health_ai.services.longitudinal import HealthAssessmentService
from executive_health_ai.ui.charts.baseline import baseline_trend_chart, coverage_chart, reference_range_chart


def _session() -> Session:
    engine = create_engine(
        "sqlite+pysqlite:///:memory:", connect_args={"check_same_thread": False}, poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    return sessionmaker(bind=engine, class_=Session)()


def _baseline(session: Session, *, metrics: list[dict] | None = None, year: int = 2026) -> tuple[Patient, HealthAssessment, dict[str, ReportExtractionCandidate]]:
    member = Patient(external_id=f"baseline-viz-{year}", display_name="可视化测试成员", timezone="Asia/Tokyo")
    session.add(member); session.flush()
    document = Document(patient_id=member.id, document_type="health_check_report", title=f"{year}年度体检报告", storage_reference="test://report", source="test", status="AVAILABLE")
    session.add(document); session.flush()
    run = ReportExtractionRun(document_id=document.id, patient_id=member.id, status="COMPLETED", parser_version="test", canonical_registry_version="test", file_hash=f"hash-{year}", file_type="TXT")
    session.add(run); session.flush()
    definitions = metrics or [
        {"code": "ldl", "value": "4.15", "unit": "mmol/L", "reference": "0.0-3.4", "flag": "H"},
        {"code": "weight", "value": "90", "unit": "kg", "reference": None, "flag": None},
        {"code": "systolic_bp", "value": "135", "unit": "mmHg", "reference": "90-139", "flag": None},
        {"code": "diastolic_bp", "value": "85", "unit": "mmHg", "reference": "60-89", "flag": None},
    ]
    candidates: dict[str, ReportExtractionCandidate] = {}
    rows = []
    for item in definitions:
        candidate = ReportExtractionCandidate(
            extraction_run_id=run.id, document_id=document.id, patient_id=member.id,
            candidate_type="OBSERVATION", canonical_code=item["code"], raw_name=item["code"],
            normalized_value=item["value"], unit=item["unit"], reference_range=item["reference"],
            abnormal_flag=item["flag"], confidence="HIGH", extraction_method="RULE",
            source_page=6, source_section="检验", evidence_text="测试报告原文", status="CONFIRMED",
        )
        session.add(candidate); session.flush(); candidates[item["code"]] = candidate
        rows.append({
            "metric": item["code"], "value": item["value"], "unit": item["unit"],
            "observed_at": f"{year}-01-10T09:00:00+00:00", "source_candidate_id": str(candidate.id),
        })
    snapshot = {
        "source_reports": [{"document_id": str(document.id), "title": document.title}],
        "key_metrics": rows,
        "health_problems": [], "current_medications": {"status": "PENDING_SUPPLEMENT", "label": "待补充"},
        "procedures_or_hospitalizations": {"status": "PENDING_SUPPLEMENT", "label": "待补充"},
        "data_coverage": {"血压": "已覆盖", "睡眠": "暂无数据", "运动": "数据不足"},
        "member_reported": {"source": "MEMBER_REPORTED", "status": "PENDING_SUPPLEMENT"},
        "completeness": {"organized": ["最近体检", "主要指标"], "pending": ["当前用药", "手术 / 住院史", "生活方式资料"]},
    }
    baseline = HealthAssessmentService().create_assessment(
        session, member.id, title=f"{year}年度健康基线", summary="测试基线", baseline=snapshot,
        created_by="健康管理师", confirmed=True, cycle_year=year,
        source_references={"source_report_ids": [str(document.id)], "source_candidate_ids": [str(row.id) for row in candidates.values()]},
    )
    session.commit()
    return member, baseline, candidates


def test_reference_interval_is_report_derived_and_missing_range_is_not_fabricated() -> None:
    assert parse_reference_interval("0.0-3.4").upper == Decimal("3.4")
    assert parse_reference_interval("< 5.6").kind == "UPPER"
    assert parse_reference_interval("≥ 1.0").kind == "LOWER"
    assert parse_reference_interval(None) is None
    assert parse_reference_interval("请咨询医生") is None
    session = _session(); member, _, _ = _baseline(session)
    view = BaselineVisualizationService().build(session, member.id, cycle_year=2026)
    by_code = {metric.code: metric for metric in view.metrics}
    assert by_code["ldl"].reference.text == "0.0-3.4"
    assert by_code["ldl"].explicit_status == "报告标记偏高"
    assert by_code["weight"].reference is None
    assert reference_range_chart(by_code["ldl"]) is not None
    assert reference_range_chart(by_code["weight"]) is None


def test_new_observation_updates_trend_but_never_mutates_baseline() -> None:
    session = _session(); member, baseline, _ = _baseline(session)
    frozen = deepcopy(baseline.baseline_json); frozen_hash = baseline.snapshot_hash
    session.add(Observation(patient_id=member.id, metric_code="weight", value_numeric=Decimal("85.2"), unit="kg", observed_at=datetime(2026, 6, 10, tzinfo=timezone.utc), source="device", quality_flag="valid"))
    session.commit(); session.refresh(baseline)
    view = BaselineVisualizationService().build(session, member.id, cycle_year=2026)
    weight = next(trend for trend in view.trends if trend.code == "weight")
    assert weight.has_follow_up
    assert weight.baseline_value == Decimal("90")
    assert view.assessment.baseline_json == frozen and view.assessment.snapshot_hash == frozen_hash
    assert next(row for row in view.comparisons if row.code == "weight").current == "85.200"
    assert baseline_trend_chart((weight,)) is not None


def test_single_point_has_no_trend_chart_and_bp_uses_two_same_unit_series() -> None:
    session = _session(); member, _, _ = _baseline(session)
    initial = BaselineVisualizationService().build(session, member.id, cycle_year=2026)
    weight = next(trend for trend in initial.trends if trend.code == "weight")
    assert not weight.has_follow_up and baseline_trend_chart((weight,)) is None
    session.add_all([
        Observation(patient_id=member.id, metric_code="systolic_bp", value_numeric=Decimal("128"), unit="mmHg", observed_at=datetime(2026, 5, 1, tzinfo=timezone.utc), source="device", quality_flag="valid"),
        Observation(patient_id=member.id, metric_code="diastolic_bp", value_numeric=Decimal("80"), unit="mmHg", observed_at=datetime(2026, 5, 1, tzinfo=timezone.utc), source="device", quality_flag="valid"),
    ]); session.commit()
    current = BaselineVisualizationService().build(session, member.id, cycle_year=2026)
    blood_pressure = tuple(trend for trend in current.trends if trend.code in {"systolic_bp", "diastolic_bp"})
    assert len(blood_pressure) == 2 and {trend.unit for trend in blood_pressure} == {"mmHg"}
    assert baseline_trend_chart(blood_pressure) is not None


def test_coverage_is_completeness_not_health_score() -> None:
    session = _session(); member, _, _ = _baseline(session)
    view = BaselineVisualizationService().build(session, member.id, cycle_year=2026)
    coverage = {item.label: item.status for item in view.coverage}
    assert coverage["年度体检"] == "已覆盖"
    assert coverage["睡眠"] == "暂无数据"
    assert coverage["生活方式"] == "待补充"
    assert "健康评分" not in str(view)
    assert coverage_chart(view.coverage).to_dict()


def test_amendment_uses_active_reference_and_preserves_update_history() -> None:
    session = _session(); member, baseline, candidates = _baseline(session)
    changed = deepcopy(baseline.baseline_json)
    changed["key_metrics"][0]["value"] = "3.90"
    amended = HealthAssessmentService().amend_baseline(
        session, baseline.id, changes={"key_metrics": changed["key_metrics"], "confirmed_correction": {"content": "LDL-C由4.15纠正为3.90", "evidence": "报告第6页"}},
        reason="纠正报告识别值", amended_by="健康管理师", evidence_references={"source_candidate_ids": [str(candidates["ldl"].id)]},
    ); session.commit()
    view = BaselineVisualizationService().build(session, member.id, cycle_year=2026)
    assert view.assessment.id == amended.id
    assert next(metric for metric in view.metrics if metric.code == "ldl").value == Decimal("3.90")
    assert view.amendments and view.amendments[0].reason == "纠正报告识别值"
    assert "4.15纠正为3.90" in view.amendments[0].changes[0]


def test_year_selector_projection_keeps_annual_baselines_separate() -> None:
    session = _session(); member, baseline_2026, _ = _baseline(session, year=2026)
    baseline_2026.status = "SUPERSEDED"
    baseline_2026.status = "CONFIRMED"
    # A second annual baseline belongs to the same member, not a replacement row.
    snapshot = deepcopy(baseline_2026.baseline_json)
    baseline_2027 = HealthAssessmentService().create_assessment(
        session, member.id, title="2027年度健康基线", summary="下一年度基线", baseline=snapshot,
        created_by="健康管理师", confirmed=True, cycle_year=2027,
        source_references=deepcopy(baseline_2026.source_references_json),
    ); session.commit()
    service = BaselineVisualizationService()
    assert service.available_years(session, member.id) == (2027, 2026)
    assert service.build(session, member.id, cycle_year=2026).assessment.id == baseline_2026.id
    assert service.build(session, member.id, cycle_year=2027).assessment.id == baseline_2027.id
