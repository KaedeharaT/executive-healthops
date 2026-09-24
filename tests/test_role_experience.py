"""Role navigation and state regressions: actual writes, not widget counts only."""
from datetime import datetime, timedelta, timezone
from pathlib import Path
from types import SimpleNamespace

from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session
from streamlit.testing.v1 import AppTest
from tests.ui_selection import open_member, select_table_row

from executive_health_ai.database import SessionLocal
from executive_health_ai.models import Base, DoctorReview, HealthProblem, HealthProgram, Observation, OutcomeEvaluation, Patient, Task
from executive_health_ai.services import care_commands
from executive_health_ai.ui import experience as ux

APP = Path(__file__).resolve().parents[1] / "streamlit_app.py"


def _radio(app, label):
    return next(item for item in app.radio if item.label == label)


def _button(app, label):
    return next(item for item in app.button if item.label == label)


def _field(app, label, value):
    next(item for collection in (app.text_input, app.text_area) for item in collection if item.label == label).set_value(value)


def test_overdue_priority_and_future_service_are_time_aware():
    now = datetime(2026, 9, 18, 12, tzinfo=timezone.utc)
    items = [SimpleNamespace(due_at=now+timedelta(days=1), priority=0, status="待处理"), SimpleNamespace(due_at=now-timedelta(days=1), priority=3, status="待处理")]
    assert ux.sorted_work(items, now)[0] is items[1]
    past = SimpleNamespace(status="SCHEDULED", scheduled_at=now-timedelta(seconds=1))
    future = SimpleNamespace(status="SCHEDULED", scheduled_at=now+timedelta(days=1))
    done = SimpleNamespace(status="COMPLETED", scheduled_at=now+timedelta(hours=1))
    assert ux.upcoming_service([past, done, future], now) is future
    assert ux.upcoming_service([past], now) is None
    assert "逾期" in ux.when(past.scheduled_at, due=True, now=now)


def test_business_names_sanitize_embedded_provenance_and_legacy_outcomes():
    text = ux.business_text("来源：Yellow RiskEvent 6df126cb-543b-417d-aae2-5d3bb79fd231；systolic_bp")
    assert "需要持续关注" in text and "收缩压" in text
    assert "RiskEvent" not in text and not ux.UUID_PATTERN.search(text)
    assert ux.metric_name(r"\u4f53\u91cd") == "体重"
    assert ux.business_text(r"阶段结果：\u4f53\u91cd") == "阶段结果：体重"
    assert ux.owner("health_manager") == "负责人：健康管理师"


def test_same_observations_projection_excludes_deleted_invalid_and_disabled_data():
    engine = create_engine("sqlite://")
    Base.metadata.create_all(engine)
    with Session(engine) as session:
        member = Patient(display_name="Projection member", timezone="Asia/Tokyo")
        session.add(member); session.flush()
        for flag, deleted, excluded in [("valid", False, False), ("invalid", False, False), ("valid", True, False), ("valid", False, True)]:
            session.add(Observation(patient_id=member.id, metric_code="steps", value_numeric=4000, unit="count", source="manual", quality_flag=flag, source_deleted=deleted, excluded_from_analysis=excluded, observed_at=datetime.now(timezone.utc)))
        session.flush()
        assert len(ux.observations(session, member.id)) == 1


def test_doctor_completion_leaves_pending_queue_and_returns_manager_task():
    engine = create_engine("sqlite://")
    Base.metadata.create_all(engine)
    with Session(engine) as session:
        member = Patient(display_name="Review member", timezone="Asia/Tokyo")
        session.add(member); session.flush()
        problem = HealthProblem(patient_id=member.id, title="需医学复核", description="观察变化", severity="MEDIUM", source="outcome_evaluation")
        session.add(problem); session.flush()
        review = DoctorReview(patient_id=member.id, health_problem_id=problem.id, doctor_name="待分配医生", department="全科", status="PENDING", question_for_doctor="核对变化", doctor_brief="仅有整理资料", opinion="")
        session.add(review); session.flush()
        assert len(ux.pending_doctor_work(session, member.id)) == 1
        _, task = care_commands.complete_review(session, review, "医生", "全科", "已人工核对", "安排复查", datetime.now(timezone.utc)+timedelta(days=7))
        session.flush()
        assert len(ux.pending_doctor_work(session, member.id)) == 0
        assert task.responsible_role == "health_manager" and task.patient_id == member.id
        assert review.status == "CONFIRMED"


def test_manager_can_create_adjust_schedule_and_record_outcome_through_normal_ui():
    app = AppTest.from_file(APP).run(timeout=30)
    _radio(app, "工作区").set_value("成员"); app.run(timeout=30)
    open_member(app); app.run(timeout=30)
    _radio(app, "成员页面").set_value("管理"); app.run(timeout=30)
    next(item for item in app.selectbox if item.label == '管理工作').set_value('计划调整与随访'); app.run(timeout=30)
    _radio(app, "计划操作").set_value("建立 / 调整计划"); app.run(timeout=30)
    next(item for item in app.checkbox if item.label == "建立新计划").set_value(True); app.run(timeout=30)
    _field(app, "计划名称", "UX操作路径验收计划")
    _field(app, "本阶段目标", "完成连续健康记录")
    _field(app, "建立依据 / 调整原因", "基于已确认资料制定")
    _button(app, "保存健康计划").click(); app.run(timeout=30)
    assert not app.exception
    with SessionLocal() as session:
        program = session.scalar(select(HealthProgram).where(HealthProgram.title == "UX操作路径验收计划"))
        assert program is not None
        program_id = program.id
    # Refresh and select the newly persisted plan, rather than assuming an optimistic UI state.
    _radio(app, "计划操作").set_value("建立 / 调整计划"); app.run(timeout=30)
    selector = next(i for i in app.selectbox if i.label == "当前管理计划")
    # AppTest selectbox accepts the stored ORM object and maps it through format_func.
    with SessionLocal() as session:
        selected = session.get(HealthProgram, program_id)
    selector.set_value(str(selected.id)); app.run(timeout=30)
    _radio(app, "计划操作").set_value("建立 / 调整计划"); app.run(timeout=30)
    next(item for item in app.checkbox if item.label == "建立新计划").set_value(False); app.run(timeout=30)
    _field(app, "本阶段目标", "按调整后的频率记录健康变化")
    _field(app, "建立依据 / 调整原因", "与成员确认可执行频率")
    _button(app, "保存健康计划").click(); app.run(timeout=30)
    _radio(app, "计划操作").set_value("安排随访"); app.run(timeout=30)
    _field(app, "需要完成什么", "核对本周记录并确认后续安排")
    _button(app, "安排随访").click(); app.run(timeout=30)
    _radio(app, "计划操作").set_value("记录阶段结果"); app.run(timeout=30)
    _field(app, "起点数值", "132"); _field(app, "本次数值", "128")
    _field(app, "单位", "mmHg"); _field(app, "结果依据", "人工核对两次记录；不作因果推断")
    _button(app, "记录阶段结果并安排下一步").click(); app.run(timeout=30)
    assert not app.exception
    assert any("已回写" in item.value for item in app.success)
    with SessionLocal() as session:
        saved = session.get(HealthProgram, program_id)
        assert saved.main_goal == "按调整后的频率记录健康变化"
        outcome = session.scalar(select(OutcomeEvaluation).where(OutcomeEvaluation.program_id == program_id))
        assert outcome is not None and outcome.current_value == "128"
        tasks = list(session.scalars(select(Task).where(Task.program_id == program_id)))
        assert len(tasks) >= 2 and any(t.source == "outcome_continue" for t in tasks)


def test_member_task_entry_is_within_two_actions_and_persists_completion():
    with SessionLocal() as session:
        member = session.scalar(select(Patient).order_by(Patient.created_at))
        task = Task(patient_id=member.id, title="UX成员行动验收", instruction="记录已完成的健康行动", status="PENDING", priority="MEDIUM", assignee="成员本人", responsible_role="member", due_at=datetime.now(timezone.utc)-timedelta(days=1000), source="ux_test")
        session.add(task); session.commit(); task_id = task.id
    app = AppTest.from_file(APP).run(timeout=30)
    _radio(app, "当前视图").set_value("成员健康中心"); app.run(timeout=30)
    next(i for i in app.button if i.key == f"client-home-complete-{task_id}").click(); app.run(timeout=30)
    next(i for i in app.button if i.key == f"ux-complete-{task_id}").click(); app.run(timeout=30)
    assert not app.exception
    with SessionLocal() as session:
        assert session.get(Task, task_id).status == "COMPLETED"
