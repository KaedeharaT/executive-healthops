"""Installed-Streamlit interaction regressions for limited UAT hardening."""

from pathlib import Path

from streamlit.testing.v1 import AppTest
import streamlit_app


APP = Path(__file__).resolve().parents[1] / "streamlit_app.py"


def _radio(app: AppTest, label: str):
    return next(item for item in app.radio if item.label == label)


def _assert_clean(app: AppTest) -> None:
    assert not app.exception
    assert not any("StreamlitAPIException" in getattr(item, "value", "") for item in app.error)


def test_member_report_upload_navigation_uses_pending_route_without_widget_mutation() -> None:
    app = AppTest.from_file(APP)
    app.run(timeout=30)
    _radio(app, "当前视图").set_value("成员健康中心")
    app.run(timeout=30)
    _radio(app, "成员健康中心导航").set_value("健康")
    app.run(timeout=30)
    _radio(app, "健康内容").set_value("体检")
    app.run(timeout=30)
    _assert_clean(app)
    assert app.file_uploader


def test_member_health_routes_report_upload_through_the_report_destination() -> None:
    """A member reaches report intake without putting it on the home screen."""
    app = AppTest.from_file(APP)
    app.run(timeout=30)
    _radio(app, "当前视图").set_value("成员健康中心")
    app.run(timeout=30)
    _radio(app, "成员健康中心导航").set_value("健康")
    app.run(timeout=30)
    _radio(app, "健康内容").set_value("体检")
    app.run(timeout=30)
    _assert_clean(app)
    assert app.file_uploader
    _radio(app, "健康内容").set_value("健康概览"); app.run(timeout=30)
    _assert_clean(app)
    assert any(item.label == "健康内容" for item in app.radio)


def test_member_home_does_not_embed_report_upload_or_full_timeline() -> None:
    app = AppTest.from_file(APP)
    app.run(timeout=30)
    _radio(app, "当前视图").set_value("成员健康中心")
    app.run(timeout=30)
    assert not any(item.value == "最近体检" for item in app.subheader)
    assert not any("健康历程" in str(item.value) for item in app.subheader)
    _assert_clean(app)


def test_report_upload_copy_keeps_cta_for_no_report_pending_report_and_confirmed_baseline() -> None:
    no_report = streamlit_app._report_upload_state(0, None, False)
    pending = streamlit_app._report_upload_state(1, "2026年度体检", False)
    confirmed = streamlit_app._report_upload_state(3, "2026年度体检", True)
    assert no_report[2] == "上传体检报告"
    assert pending[0] == "已上传 1 份报告" and pending[2] == "上传体检报告"
    assert confirmed[0].startswith("最近体检：") and confirmed[2] == "上传新体检报告"


def test_ops_member_archive_exposes_the_same_report_upload_intake() -> None:
    app = AppTest.from_file(APP)
    app.run(timeout=30)
    _radio(app, "工作区").set_value("成员")
    app.run(timeout=30)
    next(button for button in app.button if button.label == "查看成员").click(); app.run(timeout=30)
    next(radio for radio in app.radio if radio.key and radio.key.startswith("member-section-")).set_value("健康")
    app.run(timeout=30)
    _radio(app, "成员健康内容").set_value("体检")
    app.run(timeout=30)
    _assert_clean(app)
    assert app.file_uploader


def test_surface_state_is_isolated_between_two_streamlit_sessions() -> None:
    first = AppTest.from_file(APP); second = AppTest.from_file(APP)
    first.run(timeout=30); second.run(timeout=30)
    _radio(first, "当前视图").set_value("成员健康中心")
    first.run(timeout=30)
    _assert_clean(first); _assert_clean(second)
    assert any(item.label == "成员健康中心导航" for item in first.radio)
    assert any(item.value == "今日" for item in second.title)


def test_member_overview_timeline_node_is_clickable_without_exception() -> None:
    app = AppTest.from_file(APP)
    app.run(timeout=30)
    _radio(app, "工作区").set_value("成员")
    app.run(timeout=30)
    next(button for button in app.button if button.label == "查看成员").click()
    app.run(timeout=30)
    assert not [button for button in app.button if button.label == "查看详情"]
    _assert_clean(app)


def test_navigation_widget_keys_are_only_written_by_the_start_of_rerun_router() -> None:
    source = APP.read_text(encoding="utf-8")
    router = source.split("def apply_pending_navigation", 1)[1].split("def _render_sidebar_navigation", 1)[0]
    assert 'st.session_state["member-center-navigation"]' in router
    assert 'st.session_state["ops-navigation"]' in router
    outside_router = source.replace(router, "").replace('st.session_state["ops-navigation"] = legacy[selected]', "")
    assert 'st.session_state["member-center-navigation"] =' not in outside_router
    assert 'st.session_state["ops-navigation"] =' not in outside_router
