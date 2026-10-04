"""Drive the current component protocol from normal Member360 navigation."""
from pathlib import Path
from streamlit.testing.v1 import AppTest
from executive_health_ai.database import SessionLocal
from executive_health_ai.ui.pages.manager import longitudinal_timeline as timeline
from tests.test_longitudinal_timeline import seed
from tests.ui_selection import open_member


def open_sleep_episode(monkeypatch):
    # conftest binds SessionLocal to the disposable test database, never the demo.
    with SessionLocal() as session:
        story = seed.seed_story(session)
        member = story['member']
        member.display_name = '合成历程导航 ' + str(member.id)[:8]
        member_id, name = member.id, member.display_name
        session.commit()
    monkeypatch.setattr(timeline, 'utc_now', lambda: story['now'])
    transport = {'detail': None, 'action': 'select'}

    def component(**kwargs):
        transport['detail'] = kwargs['detail']
        entry = next(e for e in kwargs['entries'] if e['title'] == '睡眠管理事件')
        transport['key'] = entry['key']
        return {'key': entry['key'], 'action': transport['action']}

    monkeypatch.setattr(timeline, '_track', component)
    app = AppTest.from_file(Path(__file__).resolve().parents[1] / 'streamlit_app.py').run(timeout=45)
    next(r for r in app.radio if r.label == '工作区').set_value('成员').run(timeout=45)
    next(t for t in app.text_input if t.label == '搜索成员').set_value(name).run(timeout=45)
    open_member(app)
    next(r for r in app.radio if r.label == '成员页面').set_value('历程').run(timeout=45)
    assert not app.exception
    assert transport['detail'] and transport['detail']['key'] == transport['key']
    return app, transport, member_id
