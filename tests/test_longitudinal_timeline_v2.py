from pathlib import Path
import pytest
from sqlalchemy import event
from tests.test_longitudinal_timeline import data, view
from executive_health_ai.services.longitudinal_timeline import LongitudinalTimelineProjection as Projection
from executive_health_ai.ui.pages.manager.longitudinal_timeline import detail_payload, public_text, selected_groups

COMPONENT=Path('src/executive_health_ai/ui/pages/manager/timeline_component/index.html').read_text(encoding='utf-8')


def sleep_group(v):return next(g for g in Projection().groups(v) if g['entry'].metric=='sleep_duration')


def test_timeline_groups_care_episode(data):
    v=view(data);g=sleep_group(v)
    assert {'MEANINGFUL_CHANGE','CARE_CONTACT','PLAN_ADJUSTMENT','DOCTOR_DECISION','OUTCOME'} <= {e.entry_type for e in g['members']}
    ids=[e.entry_id for group in Projection().groups(v) for e in group['members']]
    assert len(ids)==len(set(ids))


@pytest.mark.parametrize('check',['main_timeline_vertical','no_curved_connector','no_bezier_svg_path','elbow_connector_90deg'])
def test_connectors(check):
    if check=='main_timeline_vertical':assert 'grid-template-columns:95px 28px minmax(0,1fr)' in COMPONENT and 'border-left:2px solid' in COMPONENT
    elif check=='no_curved_connector':assert 'stroke-dasharray' not in COMPONENT and 'createElementNS' not in COMPONENT
    elif check=='no_bezier_svg_path':assert '<svg' not in COMPONENT and "setAttribute('d'" not in COMPONENT
    else:assert '.section:before' in COMPONENT and 'border-top:1px solid' in COMPONENT and 'border-left:1px solid' in COMPONENT


@pytest.mark.parametrize('check',['episode_trigger_linked','agent_preparation_visible','human_role_visible','action_visible','outcome_visible','doctor_episode_grouped'])
def test_episode_story(data,check):
    db,r=data;v=view(data);g=sleep_group(v);d=Projection().group_details(db,v,g);p=detail_payload(g,d)
    if check=='episode_trigger_linked':assert str(r['change'].id) in g['entry'].entry_id
    elif check=='agent_preparation_visible':assert any('回溯' in x for x in p['automatic'])
    elif check=='human_role_visible':assert g['human']=='需要医生' and '家庭监测' in p['human_reason']
    elif check=='action_visible':assert any('减少晚间咖啡' in x['text'] for x in p['care'])
    elif check=='outcome_visible':assert p['outcomes'][0]['status']=='改善' and '后续观察到' in p['outcomes'][0]['text']
    else:assert sum(any(e.entry_type=='DOCTOR_DECISION' for e in x['members']) for x in Projection().groups(v))==1


def test_care_memory_visible_when_supported(data):
    db,_=data;v=view(data);d=Projection().group_details(db,v,sleep_group(v));m=d['memory']
    assert m['status']=='候选，待后续验证' and '夜班' in m['text'] and m['sources'] and m['time_range']
    assert '因果' in m['text']


def test_care_memory_not_invented(data):
    db,_=data;v=view(data);g=next(g for g in Projection().groups(v) if g['current'])
    assert Projection().group_details(db,v,g)['memory']=={'status':'尚未形成','text':'尚无可追溯的长期管理经验记录。','sources':[],'time_range':None}


def test_daily_stable_summary_hidden_from_main_timeline(data):
    assert not any(e.entry_type in {'RAW','OBSERVATION','DAILY_SUMMARY'} for g in Projection().groups(view(data)) for e in g['members'])


def test_meaningful_change_visible(data):assert sleep_group(view(data))['entry'].entry_type=='MEANINGFUL_CHANGE'


def test_current_state_last_and_page_bounded(data):
    groups=Projection().groups(view(data));visible=selected_groups(groups,5)
    assert len(visible)==5 and visible[-1]['current']
    assert [g['entry'].occurred_at for g in visible]==sorted(g['entry'].occurred_at for g in visible)


def test_trace_hidden():
    assert public_text('Tool call Planner Goal ID Trace ID LLM provider JSON')=='内部记录 内部记录 内部记录 内部记录 内部记录 内部记录'
    assert '86.3' not in public_text({'tool':'86.3'})


def test_detail_seven_sections_and_raw_entry(data):
    db,_=data;v=view(data);p=detail_payload(sleep_group(v),Projection().group_details(db,v,sleep_group(v)))
    assert any('324 min' in s['original'] for s in p['sources'])
    for i,title in enumerate(['当时的健康状态','发生了什么变化','系统自动完成','为什么需要人工','人工 / 医生做了什么','后续结果','长期管理经验'],1):
        assert f'{i}. {title}' in COMPONENT
    assert '查看相关趋势' in COMPONENT and '查看数据来源' in COMPONENT


def test_group_and_memory_are_readonly(data):
    db,_=data;statements=[]
    def capture(c,cu,s,*args):statements.append(s)
    event.listen(db.bind,'before_cursor_execute',capture)
    try:
        v=view(data)
        for g in Projection().groups(v):Projection().group_details(db,v,g)
    finally:event.remove(db.bind,'before_cursor_execute',capture)
    assert not any(s.lstrip().upper().startswith(('INSERT','UPDATE','DELETE')) for s in statements)


def test_overview_uses_real_projection_counts(data):
    v=view(data);o=Projection().overview(v)
    assert o['attention']==1 and '1 次医生协同' in o['actions']
    assert any('86 → 81.2 kg' in t for t in o['state'])


def test_empty_member_has_no_axis(data):
    db,r=data;v=Projection().build(db,r['empty'].id,now=r['now'])
    assert v.empty and Projection().groups(v)==[]

def test_overview_uses_latest_annual_baseline(data):
    from datetime import timedelta
    db,r=data
    v=Projection().build(db,r['member'].id,time_range=(r['now']-timedelta(days=730),r['now']),now=r['now'])
    assert any('86 → 81.2 kg' in text for text in Projection().overview(v)['state'])


def test_episode_trend_navigation_preserves_metric_and_event_dates(data,monkeypatch,tmp_path):
    from sqlalchemy.orm import sessionmaker
    from streamlit.testing.v1 import AppTest
    from executive_health_ai.ui.pages.manager import longitudinal_timeline as ui
    db,r=data
    import sqlite3
    from sqlalchemy import create_engine
    path=tmp_path/'ui.db'
    with sqlite3.connect(path) as target:db.connection().connection.driver_connection.backup(target)
    engine=create_engine('sqlite:///'+path.as_posix())
    monkeypatch.setattr(ui,'SessionLocal',sessionmaker(engine))
    monkeypatch.setattr(ui,'utc_now',lambda:r['now'])
    choice=sleep_group(view(data))['key'];action={'key':choice,'action':'select','nonce':1}
    monkeypatch.setattr(ui,'_track',lambda **kwargs:action)
    app=AppTest.from_string(f'''
from types import SimpleNamespace
from uuid import UUID
import streamlit as st
from executive_health_ai.ui.pages.manager.longitudinal_timeline import render
def navigate(**kw):st.session_state['navigation']=kw
render(SimpleNamespace(request_navigation=navigate),SimpleNamespace(id=UUID('{r['member'].id}')))
''').run(timeout=30)
    action={'key':choice,'action':'trend','nonce':2};app.run(timeout=30)
    assert not app.exception
    assert app.session_state['navigation']['archive_view']=='健康数据'
    assert app.session_state[f"health-metric-pending-{r['member'].id}"]=='sleep_duration'
    window=app.session_state[f"health-data-window-{r['member'].id}"]
    assert window=={'start':'2026-07-30','end':'2026-09-30'}
    assert app.session_state['navigation']['health_data_window']==window
    engine.dispose()
