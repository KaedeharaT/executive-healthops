"""Read-only archived records within the existing administrator audit area."""
import streamlit as st
from sqlalchemy import select
from executive_health_ai.models import Base


def render(app, member):
    st.info('该成员已归档。以下为只读历史资料；归档不表示未决医学问题已解决。')
    tables = {table.name: table for table in Base.metadata.sorted_tables
              if 'patient_id' in table.c or 'member_id' in table.c}
    selected = st.selectbox('历史记录表（只读）', sorted(tables), key='archived-history-table')
    table = tables[selected]
    owner = table.c.patient_id if 'patient_id' in table.c else table.c.member_id
    with app.SessionLocal() as session:
        rows = session.execute(select(table).where(owner == member.id)).mappings().all()
    st.caption(f'记录数：{len(rows)}；完整 Agent Trace 仍可在管理员「自动化运行」中查看。')
    st.dataframe([{k: str(v) if v is not None else '' for k, v in row.items()} for row in rows],
                 hide_index=True, width='stretch')
