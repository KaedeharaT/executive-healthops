"""Secondary, identity-bound archive action for the member directory."""
from uuid import UUID
import streamlit as st
from executive_health_ai.database import SessionLocal
from executive_health_ai.models import Patient
from executive_health_ai.services.member_archive import MemberArchiveService, member_label


@st.dialog('删除成员',width='large')
def confirm_delete(member_id,expected_name):
    identity=UUID(str(member_id))
    with SessionLocal() as session:
        member=session.get(Patient,identity)
        if not member or member.archived_at:
            st.info('该成员已归档或不存在。')
            if st.button('返回会员列表'):
                st.session_state.pop('focused_member_id',None);st.rerun()
            return
        counts=MemberArchiveService().preview(session,identity)
    st.write('您正在删除：**'+expected_name+'**')
    st.caption('会员标识：'+str(identity)[:8])
    st.markdown('删除后：\n- 该成员不再出现在正常会员列表与业务工作流中\n- 当前工作和后续自动流程停止，不标记为已完成\n- 已有健康档案、医生记录、Agent Trace 和审计记录保留')
    if any(counts.values()):
        st.warning('本次将安全停止关联的自动流程和运营事项。待医生判断、会诊和外部预约需负责人交接，不代表医学问题已解决或外部服务已撤销。')
        st.dataframe([{'关联事项':k,'未结束数量':v} for k,v in counts.items()],hide_index=True,width='stretch')
    name=st.text_input('请输入成员姓名进行确认',key='member-delete-name-'+str(identity))
    valid=name.strip()==expected_name
    if name and not valid:st.error('姓名不一致，请完整输入上方显示的成员姓名。')
    cancel,confirm=st.columns(2)
    if cancel.button('取消',width='stretch'):
        st.rerun()
    with confirm,st.container(key='member-delete-confirm-danger'):
        if st.button('确认删除',disabled=not valid,width='stretch'):
            try:
                with SessionLocal() as session:
                    MemberArchiveService().archive(session,identity,expected_name=expected_name,confirmation_name=name,
                        actor='健康管理师',role='HEALTH_MANAGER',confirmed=True)
                    session.commit()
                st.session_state.pop('focused_member_id',None)
                st.session_state['member-directory-epoch']=st.session_state.get('member-directory-epoch',0)+1
                st.session_state['workflow-flash']='成员已删除/归档，历史资料和审计记录已保留。'
                st.rerun()
            except (ValueError,PermissionError) as error:
                st.error(str(error))


def actions(app,member):
    st.markdown('**选中会员：'+member_label(member)+'**')
    st.caption('会员标识：'+str(member.id)[:8])
    with st.container(key='member-delete-danger'):
        if st.button('删除成员',key='directory-delete-'+str(member.id),help='危险操作：需输入姓名确认；实际安全归档，保留历史记录。'):
            st.session_state.pop('member-delete-name-'+str(member.id),None)
            confirm_delete(str(member.id),member_label(member))
