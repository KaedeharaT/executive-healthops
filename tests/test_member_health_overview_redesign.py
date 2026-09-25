"""Member overview grouping, source-backed stages and retained detail routes."""
from contextlib import nullcontext
from dataclasses import replace
from datetime import datetime, timezone
from decimal import Decimal
from pathlib import Path
from types import SimpleNamespace

import pytest
from streamlit.testing.v1 import AppTest

from executive_health_ai.services.baseline_visualization import (
    BaselineComparisonView, BaselineVisualization, CoverageItem, HealthDomainView,
)
from executive_health_ai.ui.pages.member.health_overview import management_stages, split_domains
from executive_health_ai.ui.pages.baseline_visualization import selected_comparisons
from tests.test_baseline_timeline_fix import trend


def example_view(*, follow_up=True, domains=None, status="CONFIRMED", program_status="ACTIVE", phase="ONGOING"):
    baseline = SimpleNamespace(id="test-baseline", cycle_year=2026, assessed_at=datetime(2026, 1, 1), confirmed_at=datetime(2026, 1, 2), status=status)
    t = trend(after="85.8" if follow_up else None)
    comparison = BaselineComparisonView("weight", "体重", "90", "85.8", "kg", "已记录", Decimal("-4.2") if follow_up else None, None, "↓ 下降" if follow_up else "暂无后续数据")
    domains = domains if domains is not None else (
        HealthDomainView("肝脏", "资料不足", "当前基线中暂无该领域的可展示指标。"),
        HealthDomainView("肺部", "需要持续关注", "已有检查发现待跟进"),
        HealthDomainView("心血管", "资料不足", "当前基线中暂无该领域的可展示指标。"),
        HealthDomainView("体重与体成分", "已建立", "已有体重记录"),
    )
    coverage = (CoverageItem("年度体检", "已覆盖"), CoverageItem("既往史", "待补充"), CoverageItem("当前用药", "待补充"), CoverageItem("生命体征", "已覆盖"), CoverageItem("连续健康数据", "部分"), CoverageItem("生活方式", "待补充"))
    health = BaselineVisualization(baseline, (), (t,), coverage, domains, (comparison,), ())
    return SimpleNamespace(baseline=baseline, health=SimpleNamespace(baseline=health), program=SimpleNamespace(status=program_status,current_phase=phase), owner="测试健管", active_tasks=())


def render_example(view):
    from contextlib import nullcontext
    from types import SimpleNamespace
    import streamlit as st
    from executive_health_ai.ui.pages.member.health_overview import render_member_health_overview
    from executive_health_ai.ui.display import get_status_display
    def record(*args, **kwargs):
        st.session_state['destination'] = kwargs or args
    app = SimpleNamespace(_label=get_status_display, _baseline_evidence_payload=lambda *args: {}, render_evidence_panel=lambda *args, **kwargs: st.caption("原始依据入口"),
        _render_client_medical_archive=lambda p: st.caption("用药、既往史、手术住院完整入口"),
        _open_client_baseline=record, _open_member_report_upload=record, request_navigation=record)
    render_member_health_overview(app, SimpleNamespace(id="example"), {"problems": []}, view, session_factory=nullcontext)


def text(app):
    return '\n'.join(str(e.value) for col in (app.markdown, app.caption, app.subheader) for e in col)


def test_missing_domains_are_grouped_once_without_repeated_empty_paragraphs():
    app = AppTest.from_function(render_example, args=(example_view(),)).run()
    assert not app.exception
    content = text(app)
    assert "资料不足" not in content and "当前基线中暂无该领域" not in content
    assert "待补充领域指标：肝脏、心血管" in content
    available, missing, focus = split_domains(example_view().health.baseline.domains)
    assert len(available) + len(missing) == 4
    assert [d.label for d in focus] == ["肺部"]


def test_baseline_change_precedes_focus_and_all_details_follow_coverage():
    app = AppTest.from_function(render_example, args=(example_view(),)).run()
    headings = [e.value for e in app.subheader]
    assert headings == ["2026年度健康基线", "从年度基线到现在", "当前重点关注", "健康领域概览", "资料完整性"]
    assert len(app.get("vega_lite_chart")) == 1
    assert "**详细资料**" in text(app)
    assert "已有检查发现待跟进" in text(app)
    assert "90 kg" in text(app) and "85.8 kg" in text(app) and "↓ 下降 4.2 kg" in text(app)
    assert "当前健康状态 · 所选指标最近记录：2026/09/01" in text(app)
    assert next(e for e in app.expander if e.label == "所有指标与当前对比").proto.expanded is False
    for label in ["年度基线完整资料", "重要健康背景 · 用药与既往史", "体检报告与健康数据"]:
        assert any(e.label == label for e in app.expander)


@pytest.mark.parametrize("state,phase,label", [("ACTIVE","ONGOING","当前"), ("PAUSED","ONGOING","已暂停"), ("PLANNED","ONGOING","已规划"), ("ACTIVE",None,"阶段待确认")])
def test_management_stage_uses_actual_plan_state(state, phase, label):
    v = example_view(program_status=state, phase=phase)
    result = management_stages(v.baseline, v.program)
    assert result[0] == ("建立基线", "已完成", "done")
    assert result[1][1] == label
    assert (result[1][2] == "current") == (label == "当前")


def test_reassessment_absent_plan_and_draft_do_not_invent_active_progress():
    v = example_view(phase="REASSESSMENT")
    assert management_stages(v.baseline, v.program)[2] == ("阶段复盘", "当前", "current")
    assert not any(s[2] == "current" for s in management_stages(v.baseline, None))
    draft = example_view(status="DRAFT")
    steps = management_stages(draft.baseline, None)
    assert steps[0][1] == "当前 · 待确认"
    assert all('%' not in state for _, state, _ in steps)
    assert sum(tone == "current" for _, _, tone in management_stages(draft.baseline, draft.program)) == 1
    assert management_stages(draft.baseline, draft.program)[1] == ("持续管理", "当前", "current")


def test_coverage_counts_only_fully_covered_categories_and_disclaims_score():
    app = AppTest.from_function(render_example, args=(example_view(),)).run()
    content = text(app)
    assert "2 / 6 类资料已覆盖" in content
    assert "这是资料完整度，不代表健康评分。" in content
    assert "连续健康数据</span>" in content and "待补充 · 部分覆盖" in content
    assert "健康评分 2" not in content


def test_domain_table_preserves_missing_and_available_domains_with_source_statuses():
    view = example_view()
    original = view.health.baseline.domains
    app = AppTest.from_function(render_example, args=(view,)).run()
    assert not app.exception
    table = next(e.value for e in app.markdown if '<table class="overview-domain-list"' in e.value)
    assert table.count('<th scope="row">') == len(original)
    for item in original:
        assert f'<th scope="row">{item.label}</th>' in table
    assert table.count('待补充资料') == 2
    assert table.count('需要持续关注') == 1
    assert table.count('资料已建立') == 1
    assert view.health.baseline.domains == original


def test_single_baseline_point_preserves_value_without_empty_chart():
    app = AppTest.from_function(render_example, args=(example_view(follow_up=False),)).run()
    assert not app.exception and len(app.get("vega_lite_chart")) == 0
    assert "目前还没有足够的后续数据形成趋势。" in text(app)
    assert "90 kg" in text(app)


def test_selected_window_cannot_show_current_value_from_excluded_record():
    view = example_view().health.baseline
    filtered = replace(view.trends[0], points=(view.trends[0].points[0],))
    current = selected_comparisons(view, (filtered,))[0]
    assert current.delta is None and current.direction == "暂无后续数据"
    assert view.comparisons[0].delta == Decimal('-4.2')  # Read-only display filtering.


def test_new_domain_is_rendered_from_projection_without_ui_registration():
    view = example_view(domains=(HealthDomainView("其他检查", "需要持续关注", "测试记录的真实说明"),))
    app = AppTest.from_function(render_example, args=(view,)).run()
    assert "其他检查" in text(app) and "测试记录的真实说明" in text(app)


def test_no_baseline_has_recovery_action_without_invented_coverage_or_chart():
    v = example_view()
    v.baseline, v.health, v.program = None, None, None
    app = AppTest.from_function(render_example, args=(v,)).run()
    assert not app.exception and len(app.get("vega_lite_chart")) == 0
    assert "年度健康基线待建立" in text(app)
    assert "类资料已覆盖" not in text(app)
    assert any(b.label == "补充健康资料" for b in app.button)


def test_draft_does_not_present_confirmed_comparison_from_another_snapshot():
    app = AppTest.from_function(render_example, args=(example_view(status="DRAFT"),)).run()
    assert not app.exception and len(app.get("vega_lite_chart")) == 0
    assert "基线尚待人工确认" in text(app)
    assert "85.8 kg" not in text(app)


def test_real_member_navigation_keeps_details_evidence_and_supplement_routes():
    app = AppTest.from_file(Path(__file__).resolve().parents[1] / "streamlit_app.py").run(timeout=45)
    def radio(label, value):
        next(r for r in app.radio if r.label == label).set_value(value)
        app.run(timeout=45)
        assert not app.exception
    radio("当前视图", "成员健康中心")
    radio("成员健康中心导航", "健康")
    assert "重点关注" in text(app) and len(app.get("vega_lite_chart")) == 1
    assert any(e.proto.popover.label == "查看依据" for e in app.get('popover'))
    next(b for b in app.button if b.label == "查看年度健康基线").click(); app.run(timeout=45)
    assert "关键指标基线" in text(app) and not app.exception
    next(b for b in app.button if b.label == "返回健康概览").click(); app.run(timeout=45)
    next(b for b in app.button if b.label == "补充健康资料").click(); app.run(timeout=45)
    assert next(r for r in app.radio if r.label == "健康内容").value == "体检"
    assert app.get('file_uploader') and not app.exception
