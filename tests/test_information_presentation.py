"""Selection integrity and structured presentation, not screenshot substitutes."""
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace as Row

import pytest
from streamlit.testing.v1 import AppTest

from executive_health_ai.ui.presentation import display_frame, preview, selected_record, work_filter, task_records


def test_grid_shortens_preview_without_changing_source_and_keeps_typed_dates():
    original = '人工核对完整依据' * 30
    now = datetime.now(timezone.utc)
    records = [{'事项': original, '截止时间': now, '数量': 4}]
    frame = display_frame(records)
    assert len(frame.iloc[0]['事项']) == 32 and frame.iloc[0]['事项'].endswith('…')
    assert records[0]['事项'] == original
    assert frame.iloc[0]['截止时间'] == now and frame.iloc[0]['数量'] == 4
    assert 'RiskEvent' not in preview('Yellow RiskEvent systolic_bp')


@pytest.mark.parametrize('indices,expected', [([1], 'b'), ([], 'a'), ([20], 'a'), ([-1], 'a')])
def test_row_selection_maps_original_source_index(indices, expected):
    rows = [Row(id='a'), Row(id='b')]
    assert selected_record(rows, {'selection': {'rows': indices}}).id == expected
    assert selected_record([], {}) is None


def test_filter_preserves_overdue_then_high_priority_order_and_no_deadline():
    now = datetime(2026, 9, 21, 9, tzinfo=timezone.utc)
    def row(name, due, priority=2, state='待处理', source='task'):
        return Row(title=name, due_at=due, priority=priority, status=state, source_type=source)
    overdue = row('逾期', now-timedelta(days=2), 3)
    high = row('高优先', now+timedelta(days=2), 0)
    today = row('今天', now+timedelta(hours=3))
    doctor = row('医生', None, state='等待医生')
    recheck = row('复查', now+timedelta(days=3), source='recheck')
    rows = [doctor, recheck, today, high, overdue]
    assert work_filter(rows, '全部', now)[:3] == [overdue, high, today]
    assert work_filter(rows, '逾期', now) == [overdue]
    assert work_filter(rows, '高优先级', now) == [high]
    assert work_filter(rows, '今天', now) == [today]
    assert work_filter(rows, '等待医生', now) == [doctor]
    assert work_filter(rows, '复查', now) == [recheck]
    assert work_filter(rows, '服务', now) == []


def table_page():
    import streamlit as st
    from types import SimpleNamespace
    from executive_health_ai.ui.presentation import data_table
    rows = [SimpleNamespace(id='a', text='甲的完整说明'), SimpleNamespace(id='b', text='乙的完整说明')]
    selected = data_table(rows, [{'事项': '甲'}, {'事项': '乙'}], key='test-grid', search=True)
    if selected:
        st.write('详情：'+selected.text)


def test_grid_keyboard_selection_and_search_reset_cannot_target_hidden_record():
    app = AppTest.from_function(table_page).run()
    assert not app.exception and len(app.dataframe[0].value) == 2
    app.checkbox[0].set_value(True).run()
    app.selectbox[0].set_value(1).run()
    assert any('乙的完整说明' in x.value for x in app.markdown)
    app.text_input[0].set_value('甲').run()
    assert len(app.dataframe[0].value) == 1
    assert any('甲的完整说明' in x.value for x in app.markdown)
    assert not any('乙的完整说明' in x.value for x in app.markdown)
    app.text_input[0].set_value('不存在').run()
    assert not app.dataframe and not app.selectbox
    assert any('暂无记录' in x.value for x in app.caption)


def test_stage_stepper_expresses_current_without_inventing_percent():
    def page():
        from executive_health_ai.ui.components import workflow
        workflow(['初评 · 已完成', '持续管理', '阶段复盘'], '持续管理')
    app = AppTest.from_function(page).run()
    html = app.markdown[0].value
    assert html.count("role='listitem'") == 3
    assert '当前 · 持续管理' in html and html.count('flow-step active') == 1
    assert '%' not in html


def test_log_timeline_and_grid_keep_details_and_followup():
    def page():
        from types import SimpleNamespace
        from datetime import datetime, timezone
        from executive_health_ai.ui.pages.manager.workflow import log_rows
        row = SimpleNamespace(id='synthetic', occurred_at=datetime(2026, 9, 20, tzinfo=timezone.utc),
            category='电话', channel='电话', member_issue='确认预约', manager_action='核对合成安排',
            result='已确认', next_action='到期回访', owner='Synthetic Manager', follow_up_at=datetime(2026, 9, 27,tzinfo=timezone.utc), follow_up_task_id='existing', evidence='合成依据')
        log_rows([row], key='log-test', switch=True)
    app = AppTest.from_function(page).run()
    assert not app.exception
    assert any('v2-timeline' in x.value for x in app.markdown)
    assert any('核对合成安排' in x.value for x in app.markdown)
    app.radio[0].set_value('表格').run()
    assert not app.exception and len(app.dataframe[0].value) == 1
    assert {'日期','结果','下一步','跟进时间','负责人'} <= set(app.dataframe[0].value.columns)
    assert any('已生成关联待办' in x.value for x in app.caption)
    assert len(app.get('download_button')) == 1


def test_stage_chart_uses_actual_phase_observations(monkeypatch):
    from decimal import Decimal
    from executive_health_ai.ui.pages import health_visualization
    from executive_health_ai.services.health_visualization import HealthSeries, HealthPoint
    now = datetime.now(timezone.utc)
    series = HealthSeries('weight', '体重', 'kg', tuple(HealthPoint(now+timedelta(days=d), Decimal(v), '合成观测') for d,v in [(-10,'100'),(-5,'90'),(-1,'89'),(1,'88')]))
    monkeypatch.setattr(health_visualization, 'load_series', lambda _: [series])
    def page():
        from datetime import date, timedelta
        from types import SimpleNamespace
        from executive_health_ai.ui.pages.manager.workflow import stage_metrics
        phase = SimpleNamespace(id='synthetic-phase', start_date=date.today()-timedelta(days=7), end_date=date.today()+timedelta(days=5))
        stage_metrics(SimpleNamespace(id='synthetic'), None, phase)
    app = AppTest.from_function(page).run()
    assert not app.exception
    frame = app.dataframe[0].value
    assert frame.iloc[0]['阶段内首条'] == '90 kg'
    assert frame.iloc[0]['阶段内最新'] == '89 kg'
    assert len(app.get('vega_lite_chart')) == 1


def test_task_table_preserves_closed_and_open_status_without_raw_sources():
    rows = [Row(title='合成事项', source='AgentGoal', priority='HIGH', status='COMPLETED', assignee='合成负责人', responsible_role='health_manager', due_at=None, instruction='完整说明')]
    record = task_records(rows)[0]
    assert record['状态'] == '已完成' and record['下一步'] == '查看结果'
    assert 'AgentGoal' not in str(record)


def test_configuration_grid_requires_explicit_selection():
    def page():
        import streamlit as st
        from executive_health_ai.ui.presentation import data_table
        selected = data_table(['import','device'], [{'集成':'数据导入'},{'集成':'设备'}], key='config', auto_select=False)
        st.caption(selected or '尚未选择')
    app = AppTest.from_function(page).run()
    assert not app.exception and app.caption[-1].value == '尚未选择'
    app.checkbox[0].check().run()
    app.selectbox[0].select_index(1).run()
    assert not app.exception and app.caption[-1].value == 'device'
