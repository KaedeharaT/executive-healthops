"""Presentation regressions: priority, wording and honest progress semantics."""
from types import SimpleNamespace
from pathlib import Path
import pytest
from streamlit.testing.v1 import AppTest
from executive_health_ai.ui.components import work_level
from executive_health_ai.ui.experience import business_text


def priority_page(level):
    from executive_health_ai.ui.components import priority_strip
    priority_strip(level,'<script>unsafe</script>',next_action='WAITING_DOCTOR')


@pytest.mark.parametrize('level,label',[('RED','需要优先处理'),('YELLOW','需要您确认'),('GREEN','正常跟进'),('UNKNOWN','资料待完善')])
def test_priority_is_accessible_and_escapes_source(level,label):
    app=AppTest.from_function(priority_page,args=(level,)).run()
    assert not app.exception
    html=app.markdown[0].value
    assert label in html and 'role="status"' in html
    assert '<script>' not in html and '&lt;script&gt;' in html
    assert '等待医生判断' in html


@pytest.mark.parametrize('priority,status,expected',[(0,'等待医生','RED'),(4,'等待医生','YELLOW'),(3,'待处理','YELLOW'),(9,'已完成','GREEN')])
def test_work_priority_does_not_turn_every_doctor_wait_red(priority,status,expected):
    assert work_level(SimpleNamespace(priority=priority,status=status))==expected


@pytest.mark.parametrize('text',['Agent WAITING_MANAGER','LLM planner runtime trace','AI candidate model output','GREEN YELLOW RED','规则命中 语义抽取 解析中'])
def test_plain_business_terms(text):
    actual=business_text(text)
    assert actual!=text
    assert not any(term in actual for term in ['Agent','LLM','WAITING_MANAGER','runtime','trace','语义抽取','规则命中'])


def board_page(status,running):
    from types import SimpleNamespace
    from executive_health_ai.ui.agent_progress import AgentProgressPanel
    p=SimpleNamespace(status=status,running=running,elapsed_seconds=30,progress_percent=50,
        current_step=2,total_steps=3,completed_steps=1,step_label='核对资料',current_activity='整理资料',
        labels=('读取资料','核对资料','确认完成'),done=(True,False,False),file_total=0,wait_message='',timeout=False)
    AgentProgressPanel.render(p)


@pytest.mark.parametrize('status,running,spinner',[('RUNNING',True,True),('WAITING_MANAGER',True,False),('WAITING_DOCTOR',True,False),('COMPLETED',False,False)])
def test_waiting_stops_animation_and_current_step_visible(status,running,spinner):
    app=AppTest.from_function(board_page,args=(status,running)).run()
    assert not app.exception
    html=''.join(m.value for m in app.markdown)
    assert ('agent-action-spinner' in html)==spinner
    assert 'class="current"' in html and 'role="progressbar"' in html


def test_double_tracks_and_straight_connectors():
    html=(Path(__file__).parents[1]/'src/executive_health_ai/ui/pages/manager/timeline_component/index.html').read_text(encoding='utf-8')
    assert '健康状态变化' in html and '管理动作 / 医疗动作' in html
    assert 'lane-health' in html and 'lane-care' in html
    assert 'border-left:3px solid' in html and 'border-top:2px solid' in html
    assert '<path' not in html and '<svg' not in html and 'dashed' not in html
