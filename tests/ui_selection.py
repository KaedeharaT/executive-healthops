"""Send native dataframe selection state in AppTest; keyboard input is browser-tested."""
import json
from streamlit.proto.WidgetStates_pb2 import WidgetStates


def select_table_row(app, index=0, *, prefix=None):
    # AppTest's Dataframe is an Element, not a Widget: it does not send table
    # selections with subsequent form submissions. Supply the same event state
    # that the real browser transports, without adding controls to the product.
    if not getattr(app, '_native_grid_transport', False):
        original_run = app._run

        def run_with_selections(widget_state=None, timeout=None):
            widget_state = widget_state if widget_state is not None else WidgetStates()
            for table in app.dataframe:
                if table.proto.id and table.key in app.session_state:
                    event = widget_state.widgets.add()
                    event.id = table.proto.id
                    event.string_value = json.dumps(app.session_state[table.key])
            return original_run(widget_state, timeout)

        app._run = run_with_selections
        app._native_grid_transport = True
    grid = next(item for item in app.dataframe if item.proto.id and
                (prefix is None or item.proto.id.split('-', 2)[2].startswith(prefix)))
    key = grid.proto.id.split('-', 2)[2]
    selection = {'cells': [[index, '会员']]} if key.startswith('member-directory-') else {'rows': [index]}
    app.session_state[key] = {'selection': selection}
    return app


def open_member(app):
    select_table_row(app, prefix='member-directory-').run(timeout=45)
    return app


def open_archive(app, title):
    # The summary was intentionally moved behind the full archive entry.
    entry=next((b for b in app.button if b.label=='查看完整健康档案'),None)
    if entry:entry.click().run(timeout=45)
    grid = next(t for t in app.dataframe if '资料' in t.value.columns)
    index = list(grid.value['资料']).index(title)
    return select_table_row(app, index, prefix='archive-content-')
