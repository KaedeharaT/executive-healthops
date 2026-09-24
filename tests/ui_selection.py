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
    return select_table_row(app, prefix='member-directory-')
