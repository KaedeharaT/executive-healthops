"""Business navigation uses native table events, without component-mode controls."""
from pathlib import Path
from streamlit.testing.v1 import AppTest
from tests.ui_selection import open_member
from executive_health_ai.ui.presentation import selected_record


def test_cell_selection_keeps_original_source_identity():
    rows = [object(), object()]
    assert selected_record(rows, {'selection': {'cells': [[1, '会员']]}}) is rows[1]


def test_directory_requires_explicit_selection_and_return_stays_in_list():
    app = AppTest.from_file(Path(__file__).resolve().parents[1] / 'streamlit_app.py').run(timeout=45)
    next(r for r in app.radio if r.label == '工作区').set_value('成员').run(timeout=45)
    assert not app.exception
    assert not any(b.label == '查看成员' for b in app.button)
    assert not any(r.label == '成员页面' for r in app.radio)
    assert not any(e.label == '键盘选择 / 完整标题' for e in app.expander)
    assert not any(c.label == '使用下拉选择' for c in app.checkbox)
    assert not any(s.label == '选择会员' for s in app.selectbox)
    open_member(app).run(timeout=45)
    assert not app.exception and any(r.label == '成员页面' for r in app.radio)
    next(b for b in app.button if b.label == '← 返回成员列表').click().run(timeout=45)
    assert not app.exception and not any(r.label == '成员页面' for r in app.radio)
    assert any(t.label == '搜索成员' for t in app.text_input)
