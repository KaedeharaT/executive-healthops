"""Window-consistent presentation over existing health series."""
from datetime import datetime, timezone
from decimal import Decimal
from types import SimpleNamespace

from executive_health_ai.services.health_visualization import HealthPoint, HealthSeries
from executive_health_ai.ui.pages.health_trend_panel import ordered_options, summary_values


def series(code, unit, values):
    return HealthSeries(code, code, unit, tuple(HealthPoint(datetime(2026, 9, day, tzinfo=timezone.utc), Decimal(value), '人工记录') for day, value in values))


def test_summary_follows_filtered_current_not_full_history():
    visible = (series('weight', 'kg', [(1, '90'), (10, '88')]),)
    baseline = [SimpleNamespace(code='weight', unit='kg', value=Decimal('92'))]
    values = dict(summary_values(visible, baseline))
    assert values['当前值 · 所选范围'] == '88 kg'
    assert values['年度基线'] == '92 kg'
    assert values['较年度基线变化'] == '↓4 kg'
    assert values['最近测量'] == '2026-09-10 00:00'


def test_no_points_or_no_comparable_baseline_never_invent_values():
    values = dict(summary_values((series('alt', 'U/L', []),), []))
    assert values['当前值 · 所选范围'] == '所选范围无记录'
    assert values['年度基线'] == '暂无年度基线'
    assert values['较年度基线变化'] == '暂无可比数据'
    mismatch = [SimpleNamespace(code='alt', unit='other', value=Decimal('30'))]
    assert dict(summary_values((series('alt', 'U/L', [(1, '52')]),), mismatch))['年度基线'] == '暂无年度基线'


def test_blood_pressure_pair_keeps_order_and_distinct_dates():
    group = (series('systolic_bp', 'mmHg', [(17, '126')]), series('diastolic_bp', 'mmHg', [(16, '80')]))
    refs = [SimpleNamespace(code=s.code, unit='mmHg', value=Decimal(v)) for s, v in zip(group, ('132', '86'))]
    values = dict(summary_values(group, refs))
    assert values['当前值 · 所选范围'] == '126 / 80 mmHg'
    assert values['年度基线'] == '132 / 86 mmHg'
    assert values['较年度基线变化'] == '↓6 / ↓6 mmHg'
    assert '2026-09-17' in values['最近测量'] and '2026-09-16' in values['最近测量']


def test_percentage_delta_is_percentage_points():
    refs = [SimpleNamespace(code='hba1c', unit='%', value=Decimal('6.3'))]
    assert dict(summary_values((series('hba1c', '%', [(1, '6')]),), refs))['较年度基线变化'] == '↓0.3 个百分点'


def test_display_order_preserves_all_options_including_unlisted_future_metrics():
    options = {code: object() for code in ('blood_pressure', 'sleep_duration', 'weight', 'bmi', 'new_metric')}
    ordered = ordered_options(options)
    assert list(ordered) == ['weight', 'bmi', 'blood_pressure', 'sleep_duration', 'new_metric']
    assert ordered == options
