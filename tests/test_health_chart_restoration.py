"""Chart data, rendered role surfaces and guards against disconnected renderers."""
from datetime import datetime, timedelta, timezone, date
from decimal import Decimal
import inspect
import json
from types import SimpleNamespace

import pytest
from sqlalchemy.orm import sessionmaker
from streamlit.testing.v1 import AppTest

from executive_health_ai.models import Observation, Patient, ReportExtractionRun, ReportExtractionCandidate, Document, SleepSession
from executive_health_ai.services.health_visualization import (
    HealthPoint, HealthSeries, HealthVisualizationService, PERIODS,
    default_period, filter_period, series_options,
)
from executive_health_ai.ui.charts.health import metric_trend_chart
from tests.test_baseline_visualization import _session

NOW = datetime.now(timezone.utc)


def series(code="weight", label="体重", unit="kg", values=(90, 88, 85.8)):
    return HealthSeries(code, label, unit, tuple(HealthPoint(NOW-timedelta(days=14-7*i), Decimal(str(v)), "人工记录") for i, v in enumerate(values)))


def test_axes_units_tooltip_and_readable_domain():
    spec = metric_trend_chart((series(),)).to_dict()
    x, y = (spec["encoding"][a] for a in ("x", "y"))
    assert x["title"] == "时间" and y["title"] == "kg"
    for axis in (x, y):
        assert all(axis["axis"][k] for k in ("labels", "ticks", "domain"))
    assert y["axis"]["grid"] and y["scale"]["zero"] is False
    assert 80 < y["scale"]["domain"][0] < 85.8 < 90 < y["scale"]["domain"][1] < 95
    assert {t["field"] for t in spec["encoding"]["tooltip"]} == {"时间", "数值", "指标", "单位", "来源"}


def test_blood_pressure_two_series_and_mixed_units_rejected():
    bp = (series("systolic_bp", "收缩压", "mmHg", (132, 128)), series("diastolic_bp", "舒张压", "mmHg", (86, 82)))
    assert list(series_options(bp)) == ["blood_pressure"]
    spec = metric_trend_chart(bp).to_dict()
    assert spec["encoding"]["y"]["title"] == "mmHg"
    assert {r["指标"] for rows in spec["datasets"].values() for r in rows} == {"收缩压", "舒张压"}
    with pytest.raises(ValueError, match="不同单位"):
        metric_trend_chart((series(), bp[0]))


@pytest.mark.parametrize("values", [(), (90,)])
def test_empty_and_single_point_have_no_fake_trend(values):
    assert metric_trend_chart((series(values=values),)) is None


def test_multi_point_draws_real_trend():
    assert metric_trend_chart((series(values=(90, 88)),)) is not None


@pytest.mark.parametrize("values,arrow", [((90, 91), "↑ 上升"), ((90, 85.8), "↓ 下降"), ((90, 90), "→ 基本持平")])
def test_direction_is_numeric_not_medical(values, arrow):
    text = series(values=values).comparison
    assert arrow in text and "kg" in text
    assert not any(w in text for w in ("改善", "恶化", "风险"))


def test_percentage_metric_change_is_percentage_points():
    assert "0.3 个百分点" in series("hba1c", "糖化血红蛋白", "%", (6.3, 6)).comparison


def test_time_ranges_are_real_windows_and_do_not_shift_old_data_to_today():
    group = (series(),)
    assert list(PERIODS) == ["7天", "30天", "3个月", "6个月", "1年", "全部"]
    assert len(filter_period(group, "7天", now=NOW)[0].points) == 2
    assert len(filter_period(group, "全部", now=NOW)[0].points) == 3
    assert not filter_period(group, "30天", now=NOW+timedelta(days=366))[0].points
    assert default_period(group, now=NOW+timedelta(days=366)) == "全部"
    assert len(filter_period(group, "全部", start=NOW-timedelta(days=8), end=NOW-timedelta(days=6))[0].points) == 1


@pytest.fixture
def chart_member(monkeypatch):
    import executive_health_ai.ui.pages.health_visualization as page
    with _session() as session:
        member = Patient(display_name="趋势测试成员", timezone="Asia/Tokyo")
        session.add(member); session.flush()
        for code, unit, values in [("weight", "kg", (90, 88, 85.8)), ("systolic_bp", "mmHg", (132, 128, 126)), ("diastolic_bp", "mmHg", (86, 82, 80)), ("sleep_duration", "minutes", (420, 450, 480)), ("steps", "count", (3000, 5000, 6000))]:
            for i, value in enumerate(values):
                session.add(Observation(patient_id=member.id, metric_code=code, unit=unit, value_numeric=value, observed_at=NOW-timedelta(days=14-i*7), quality_flag="valid", source="manual"))
        for kwargs in [dict(quality_flag="invalid"), dict(source_deleted=True), dict(excluded_from_analysis=True), dict(unit="stone")]:
            params = dict(patient_id=member.id, metric_code="weight", unit="kg", value_numeric=999, observed_at=NOW+timedelta(seconds=1), quality_flag="valid", source="manual")
            params.update(kwargs); session.add(Observation(**params))
        session.commit()
        factory = sessionmaker(bind=session.bind, expire_on_commit=False)
        monkeypatch.setattr(page, "SessionLocal", factory)
        yield session, member, factory


def test_shared_projection_excludes_unusable_data_and_converts_display_units(chart_member):
    session, member, _ = chart_member
    result = {s.code: s for s in HealthVisualizationService().build(session, member.id)}
    assert len(result["weight"].points) == 3
    assert result["weight"].points[-1].value == Decimal("85.8")
    assert result["sleep_duration"].unit == "小时" and result["sleep_duration"].points[-1].value == 8
    assert result["steps"].unit == "步"


def test_sleep_session_supplies_real_deep_duration_without_duplicate_total(chart_member):
    session, member, _ = chart_member
    for days in (0, 7):
        end = NOW-timedelta(days=days)
        session.add(SleepSession(patient_id=member.id, sleep_start=end-timedelta(hours=8), sleep_end=end, total_sleep_minutes=480, deep_sleep_minutes=90, source="test"))
    session.commit()
    result = {s.code: s for s in HealthVisualizationService().build(session, member.id)}
    assert len(result["sleep_duration"].points) == 3
    assert len(result["deep_sleep_duration"].points) == 2
    assert all(p.value == Decimal("1.5") for p in result["deep_sleep_duration"].points)
    assert result["deep_sleep_duration"].unit == "小时"


def _render_empty_chart(values):
    from executive_health_ai.ui.charts.health import render_metric_trend
    render_metric_trend(values, key="empty-chart")


@pytest.mark.parametrize("values", [(), (90,)])
def test_empty_or_single_point_ui_is_short_text_without_empty_plot(values):
    app = AppTest.from_function(_render_empty_chart, args=((series(values=values),),)).run()
    assert not app.exception and not app.get("vega_lite_chart")
    assert any("暂无足够数据形成趋势" in item.value for item in app.caption)


def test_doctor_context_uses_same_points_and_excludes_unrelated_metrics(chart_member):
    session, member, _ = chart_member
    service = HealthVisualizationService()
    review = SimpleNamespace(risk_event_id=None, question_for_doctor="近一个月血压是否持续异常？")
    contextual = service.for_review(session, member.id, review)
    assert {s.code for s in contextual} == {"systolic_bp", "diastolic_bp"}
    assert contextual == tuple(s for s in service.build(session, member.id) if s.code in {"systolic_bp", "diastolic_bp"})
    assert service.for_review(session, member.id, SimpleNamespace(risk_event_id=None, question_for_doctor="请核对病史")) == ()


def _render_role_data(member_id):
    from executive_health_ai.ui.pages.member.experience import health_data
    health_data(None, member_id)


def test_member_and_manager_shared_health_entry_actually_emits_chart(chart_member):
    _, member, _ = chart_member
    member_app = AppTest.from_function(_render_role_data, args=(member.id,)).run()
    manager_app = AppTest.from_function(_render_role_data, args=(member.id,)).run()
    assert not member_app.exception and not manager_app.exception
    assert len(member_app.get("vega_lite_chart")) == len(manager_app.get("vega_lite_chart")) == 1
    assert member_app.get("vega_lite_chart")[0].proto.spec == manager_app.get("vega_lite_chart")[0].proto.spec
    member_app.selectbox[0].set_value("sleep_duration"); member_app.run()
    assert not member_app.exception and json.loads(member_app.get("vega_lite_chart")[0].proto.spec)["layer"][0]["encoding"]["y"]["title"] == "小时"


def _render_review(member_id, factory):
    from types import SimpleNamespace
    from executive_health_ai.ui.pages.health_visualization import render_doctor_trend
    render_doctor_trend(member_id, SimpleNamespace(id="review-test", risk_event_id=None, question_for_doctor="近一个月血压是否持续异常？"), session_factory=factory)


def test_doctor_contextual_renderer_emits_one_chart(chart_member):
    _, member, factory = chart_member
    app = AppTest.from_function(_render_review, args=(member.id, factory)).run()
    assert not app.exception and len(app.get("vega_lite_chart")) == 1
    assert 'mmHg' in app.get("vega_lite_chart")[0].proto.spec


def test_report_comparison_uses_confirmed_exam_dates_not_upload_dates(chart_member):
    session, member, _ = chart_member
    for month, value in [(1, "4.15"), (9, "3.72")]:
        doc = Document(patient_id=member.id, document_type="health_check_report", title="检查", storage_reference="test://report", source="test", status="AVAILABLE")
        session.add(doc); session.flush()
        run = ReportExtractionRun(document_id=doc.id, patient_id=member.id, status="COMPLETED", parser_version="test", canonical_registry_version="test", file_hash=str(month), file_type="TXT", detected_report_date=date(2026, month, 1))
        session.add(run); session.flush()
        for status, amount in [("CONFIRMED", value), ("PENDING", "999")]:
            session.add(ReportExtractionCandidate(document_id=doc.id, extraction_run_id=run.id, patient_id=member.id, candidate_type="OBSERVATION", canonical_code="ldl_c", normalized_value=amount, unit="mmol/L", status=status, confidence="HIGH", extraction_method="RULE", raw_name="LDL-C", evidence_text="合成测试证据"))
    session.commit()
    result = HealthVisualizationService().report_series(session, member.id)
    assert len(result) == 1 and [p.at.month for p in result[0].points] == [1, 9]
    assert [p.value for p in result[0].points] == [Decimal("4.15"), Decimal("3.72")]


def test_chart_inventory_regression_new_role_routes_keep_shared_renderers():
    from executive_health_ai.ui.pages.member import experience as member
    from executive_health_ai.ui.pages.manager import experience as manager
    from executive_health_ai.ui.pages.doctor import experience as doctor
    assert "render_previews(" in inspect.getsource(member.home)
    from executive_health_ai.ui.pages.member.health_overview import render_member_health_overview
    assert "render_member_health_overview(" in inspect.getsource(member.overview)
    assert "render_baseline_progress(" in inspect.getsource(render_member_health_overview)
    assert "render_health_explorer(" in inspect.getsource(member.health_data)
    assert "render_previews(" in inspect.getsource(manager)
    assert "render_doctor_trend(" in inspect.getsource(doctor.detail)
    from tests.ui_source import source
    assert "member_pages.health_data(" in source("render_member_archive", "def render_simple_member_overview")
    assert "member_pages.health_data(" in source("render_client_health_hub", "def render_member_client_view")
    assert "render_report_trends(" in source("_render_client_checkup_page", "def _render_client_medical_archive")
