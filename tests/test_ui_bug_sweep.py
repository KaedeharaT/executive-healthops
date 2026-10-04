"""User-path regressions for ordinary Streamlit UI hygiene.

These tests deliberately start at the visible navigation controls.  They do
not call render helpers directly: the purpose is to catch the class of bugs
where a feature exists but a user cannot reach it, or a rerun mutates a live
widget key.
"""

from pathlib import Path
from html.parser import HTMLParser

from streamlit.testing.v1 import AppTest
from tests.ui_selection import open_member, select_table_row

import streamlit_app
from executive_health_ai.ui.localization.zh_cn import observation, status


APP = Path(__file__).resolve().parents[1] / "streamlit_app.py"
FORBIDDEN_BUSINESS_TOKENS = (
    "risk_event_id", "candidate_id", "document_id", "rule_code",
    "synthetic_", "demo_synthetic", "\nopen\n", "\ndoctor\n",
    "\nunknown\n", "\nnone\n", "\nnull\n",
)


def _radio(app: AppTest, label: str):
    return next(item for item in app.radio if item.label == label)


def _assert_clean(app: AppTest) -> None:
    assert not app.exception
    messages = [str(item.value) for item in app.error]
    assert not any("StreamlitAPIException" in message or "DuplicateWidgetID" in message for message in messages)


def _visible_text(app: AppTest) -> str:
    class VisibleHTML(HTMLParser):
        def __init__(self):
            super().__init__()
            self.parts = []
        def handle_data(self, data):
            self.parts.append(data)

    values: list[str] = []
    for collection in (app.title, app.subheader, app.caption, app.info, app.warning, app.success, app.error, app.metric):
        for item in collection:
            values.append(str(getattr(item, "value", "")))
            values.append(str(getattr(item, "label", "")))
    for item in app.markdown:
        value = str(item.value)
        if "<style>" not in value:
            parsed = VisibleHTML()
            parsed.feed(value)
            values.append(" ".join(parsed.parts))
    return "\n".join(values).lower()


def _assert_no_business_contract_leak(app: AppTest) -> None:
    visible = _visible_text(app)
    assert not any(token in visible for token in FORBIDDEN_BUSINESS_TOKENS)


def test_display_registry_never_returns_unknown_or_raw_service_statuses() -> None:
    """The reported ``unknown：建议关注`` path resolves at the display source."""
    assert streamlit_app._metric_display_name("unknown") == "健康数据"
    assert streamlit_app._metric_display_name("unmapped_metric") == "健康数据"
    assert observation("unknown") == "健康数据"
    assert status("REQUESTED") == "已申请"
    assert status("NEEDS_MANUAL_REVIEW") == "需要人工核对"
    assert status(None) == "未记录"


def test_member_center_checkup_upload_and_home_are_reachable_without_state_error() -> None:
    app = AppTest.from_file(APP)
    app.run(timeout=30)
    _radio(app, "当前视图").set_value("成员健康中心")
    app.run(timeout=30)
    _assert_clean(app)
    assert "unknown" not in _visible_text(app)
    _assert_no_business_contract_leak(app)

    _radio(app, "成员健康中心导航").set_value("健康")
    app.run(timeout=30)
    _radio(app, "健康内容").set_value("体检")
    app.run(timeout=30)
    _assert_clean(app)
    assert app.file_uploader
    _assert_no_business_contract_leak(app)

    _radio(app, "健康内容").set_value("健康概览")
    app.run(timeout=30)
    _assert_clean(app)
    assert any(item.label == "健康内容" for item in app.radio)


def test_ops_and_member_navigation_sweep_has_no_visible_placeholder_or_widget_failure() -> None:
    app = AppTest.from_file(APP)
    app.run(timeout=30)
    _radio(app, "工作区").set_value("成员")
    app.run(timeout=30)
    open_member(app)
    app.run(timeout=30)
    _assert_clean(app)

    section = next(item for item in app.radio if item.key and item.key.startswith("member-section-"))
    for name in ("概览", "管理", "健康", "医疗", "历程", "概览"):
        section.set_value(name)
        app.run(timeout=30)
        _assert_clean(app)
        assert "unknown" not in _visible_text(app)
        _assert_no_business_contract_leak(app)

    _radio(app, "当前视图").set_value("成员健康中心")
    app.run(timeout=30)
    member_navigation = _radio(app, "成员健康中心导航")
    for page in ("首页", "健康", "历程", "计划", "服务", "首页"):
        member_navigation.set_value(page)
        app.run(timeout=30)
        _assert_clean(app)
        visible = _visible_text(app)
        assert "unknown" not in visible and "null" not in visible
        _assert_no_business_contract_leak(app)


def test_timeline_health_data_action_routes_without_mutating_live_widgets(monkeypatch) -> None:
    """Exercise the real timeline → data handoff, including its route context."""
    from tests.timeline_navigation import open_sleep_episode
    app, transport, member_id = open_sleep_episode(monkeypatch)
    transport['action'] = 'trend'
    app.run(timeout=30)
    _assert_clean(app)
    assert any(item.value == "健康数据" for item in app.subheader)
    # The trend panel presents this same route context as quiet filter metadata.
    assert any("时间轴选择的时间段" in str(item.value) for item in [*app.info, *app.caption])
    assert app.session_state[f'health-data-window-{member_id}'] == {'start': '2026-07-30', 'end': '2026-09-30'}
