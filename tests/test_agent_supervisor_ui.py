"""Real navigation coverage for the four bounded-automation summaries."""

from pathlib import Path

from sqlalchemy import delete, select
from streamlit.testing.v1 import AppTest

from executive_health_ai.database import SessionLocal
from executive_health_ai.models import AgentGoal, Patient


APP = Path(__file__).resolve().parents[1] / "streamlit_app.py"


def _text(app: AppTest) -> str:
    values = []
    for collection in (app.title, app.subheader, app.caption, app.info, app.markdown):
        values.extend(str(item.value) for item in collection)
    return "\n".join(values)


def _radio(app: AppTest, label: str):
    return next(item for item in app.radio if item.label == label)


def test_member_manager_doctor_and_admin_see_business_agent_status_without_technical_ids() -> None:
    with SessionLocal() as session:
        member = session.scalar(select(Patient).order_by(Patient.created_at))
        assert member is not None
        session.execute(delete(AgentGoal).where(AgentGoal.source_type == "ui_agent_test"))
        goal = AgentGoal(member_id=member.id, goal_type="POST_CHECKUP_MANAGEMENT", title="完成年度体检后健康管理", status="WAITING", success_criteria={}, source_type="ui_agent_test", source_id="visible-status", owner="演示健康管理师", current_stage="等待医生完成医学复核", next_action="医生确认后由健康管理师安排随访", created_by="test")
        session.add(goal); session.commit()
    try:
        manager = AppTest.from_file(APP); manager.run(timeout=30)
        assert any("自动跟进状态" in item.label for item in manager.expander) and not manager.exception

        member_ui = AppTest.from_file(APP); member_ui.run(timeout=30)
        _radio(member_ui, "当前视图").set_value("成员健康中心"); member_ui.run(timeout=30)
        assert "持续管理状态" in _text(member_ui) and not member_ui.exception

        doctor = AppTest.from_file(APP); doctor.run(timeout=30)
        _radio(doctor, "工作区").set_value("医疗协同"); doctor.run(timeout=30)
        assert "完成年度体检后健康管理" in _text(doctor) and not doctor.exception

        admin = AppTest.from_file(APP); admin.run(timeout=30)
        _radio(admin, "工作区").set_value("更多"); admin.run(timeout=30)
        next(button for button in admin.button if button.key == "more-open-系统").click(); admin.run(timeout=30)
        visible = _text(admin)
        assert "自动化运营" in visible and "AgentGoal" not in visible
        assert not admin.exception
    finally:
        with SessionLocal() as session:
            session.execute(delete(AgentGoal).where(AgentGoal.source_type == "ui_agent_test")); session.commit()
