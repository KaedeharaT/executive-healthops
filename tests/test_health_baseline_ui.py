"""Streamlit interaction path for manager, doctor and member baseline views."""

from pathlib import Path

from sqlalchemy import delete, select
from streamlit.testing.v1 import AppTest

from executive_health_ai.database import SessionLocal
from executive_health_ai.models import HealthAssessment, Patient
from executive_health_ai.services.longitudinal import HealthAssessmentService


APP = Path(__file__).resolve().parents[1] / "streamlit_app.py"


def _radio(app: AppTest, label: str):
    return next(item for item in app.radio if item.label == label)


def _visible_text(app: AppTest) -> str:
    values: list[str] = []
    for collection in (app.title, app.subheader, app.caption, app.info, app.warning, app.success, app.markdown):
        values.extend(str(item.value) for item in collection)
    values.extend(item.label for item in app.expander)
    return "\n".join(values)


def test_baseline_review_confirmation_and_member_reference_point_are_interaction_verified() -> None:
    with SessionLocal() as session:
        member = session.scalar(select(Patient).order_by(Patient.created_at))
        assert member is not None
        session.execute(delete(HealthAssessment).where(HealthAssessment.patient_id == member.id, HealthAssessment.cycle_year == 2099))
        draft = HealthAssessmentService().create_manual_draft(
            session, member.id, created_by="健康管理师", summary="年度健康基线UI核验",
            cycle_year=2099, medical_review_required=True,
        )
        HealthAssessmentService().request_medical_review(session, draft.id, requested_by="健康管理师")
        draft_id = draft.id
        session.commit()
    try:
        doctor = AppTest.from_file(APP); doctor.run(timeout=30)
        _radio(doctor, "工作区").set_value("医疗协同"); doctor.run(timeout=30)
        assert "年度健康基线医学资料复核" in _visible_text(doctor)
        next(item for item in doctor.text_area if item.label == "医学资料复核说明").set_value("医学相关资料已人工核对")
        next(item for item in doctor.button if item.label == "完成医学资料复核").click(); doctor.run(timeout=30)
        assert not doctor.exception

        manager = AppTest.from_file(APP); manager.run(timeout=30)
        _radio(manager, "工作区").set_value("成员"); manager.run(timeout=30)
        next(item for item in manager.button if item.label == "查看成员").click(); manager.run(timeout=30)
        member_section = next(item for item in manager.radio if item.key and item.key.startswith("member-section-"))
        member_section.set_value("健康"); manager.run(timeout=30)
        _radio(manager, "成员健康内容").set_value("基线"); manager.run(timeout=30)
        assert "2099年度健康基线" in _visible_text(manager)
        next(item for item in manager.button if item.label == "确认健康基线").click(); manager.run(timeout=30)
        assert "确认后已冻结" in _visible_text(manager)
        assert any(item.label == "查看依据" for item in manager.button)
        assert any(item.label == "查看年度起点与当前状态比较" for item in manager.expander)
        assert not manager.exception

        member_ui = AppTest.from_file(APP); member_ui.run(timeout=30)
        _radio(member_ui, "当前视图").set_value("成员健康中心"); member_ui.run(timeout=30)
        _radio(member_ui, "成员健康中心导航").set_value("健康"); member_ui.run(timeout=30)
        assert "我的健康起点" in _visible_text(member_ui)
        assert "AgentGoal" not in _visible_text(member_ui) and not member_ui.exception
    finally:
        with SessionLocal() as session:
            session.execute(delete(HealthAssessment).where(HealthAssessment.id == draft_id)); session.commit()
