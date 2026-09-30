"""The single identity-bound archive action, with read-only historical access."""
from uuid import UUID
import streamlit as st
from executive_health_ai.database import SessionLocal
from executive_health_ai.models import Patient
from executive_health_ai.services.member_archive import MemberArchiveService, member_label


def _dismiss_archive():
    st.session_state.pop('member-archive-dialog',None)


def request_delete(member):
    # Consume selection even for an archived row; never fall through to navigation.
    st.session_state['member-directory-epoch']=st.session_state.get('member-directory-epoch',0)+1
    if member.archived_at:
        return
    identity=str(member.id)
    st.session_state['member-archive-dialog']=(identity,member_label(member))
    st.session_state.pop('member-delete-name-'+identity,None)


@st.dialog('删除会员',width='large',on_dismiss=_dismiss_archive)
def confirm_delete(member_id,expected_name):
    identity=UUID(str(member_id))
    with SessionLocal() as session:
        member=session.get(Patient,identity)
        if not member or member.archived_at:
            st.info('该成员已归档或不存在。')
            if st.button('返回会员列表'):
                _dismiss_archive()
                st.session_state.pop('focused_member_id',None);st.rerun()
            return
        service=MemberArchiveService()
        counts=service.preview(session,identity)
        running=service.is_running(session,identity)
    st.subheader('删除会员：'+expected_name)
    st.write('删除后，该会员将不再出现在在管会员列表中。历史健康档案和服务记录仍会保留。')
    if running:
        st.warning('该会员当前仍有自动化流程正在运行，请先完成或停止当前流程。')
        if st.button('取消',key='running-delete-cancel'):
            _dismiss_archive();st.rerun()
        return
    if any(counts.values()):
        st.warning('本次将安全停止关联的自动流程和运营事项。待医生判断、会诊和外部预约需负责人交接，不代表医学问题已解决或外部服务已撤销。')
        st.dataframe([{'关联事项':k,'未结束数量':v} for k,v in counts.items()],hide_index=True,width='stretch')
    name=st.text_input('请输入会员姓名“'+expected_name+'”确认',key='member-delete-name-'+str(identity))
    valid=name==expected_name
    if name and not valid:st.error('姓名不一致，请完整输入上方显示的成员姓名。')
    cancel,confirm=st.columns(2)
    if cancel.button('取消',width='stretch'):
        _dismiss_archive()
        st.rerun()
    with confirm,st.container(key='member-delete-confirm-danger'):
        if st.button('确认删除',disabled=not valid,width='stretch'):
            try:
                with SessionLocal() as session:
                    MemberArchiveService().archive(session,identity,expected_name=expected_name,confirmation_name=name,
                        actor='健康管理师',role='HEALTH_MANAGER',confirmed=True)
                    session.commit()
                _dismiss_archive()
                st.session_state.pop('focused_member_id',None)
                st.session_state['member-directory-epoch']=st.session_state.get('member-directory-epoch',0)+1
                st.session_state['workflow-flash']='会员已删除（安全归档），历史资料和审计记录已保留。'
                st.rerun()
            except (ValueError,PermissionError) as error:
                st.error(str(error))


def pending_confirmation():
    pending=st.session_state.get('member-archive-dialog')
    if pending:
        confirm_delete(*pending)


def archived_detail(app,member):
    """No editable renderer is reachable from an archived Member360."""
    from sqlalchemy import select
    from executive_health_ai.models import Observation, ServiceCatalogItem
    from executive_health_ai.services.member_management_projection import MemberManagementProjection
    from executive_health_ai.services.profile_ingestion import confirmed_profile
    from executive_health_ai.ui import components as c, experience as ux
    from executive_health_ai.ui.status_dictionary import status_label
    ux.inject_design('manager')
    if st.button('← 返回会员',key='back-to-dashboard'):
        st.session_state.pop('focused_member_id',None)
        st.session_state.pop('member-return-origin',None)
        app.request_navigation(surface='运营后台',ops_page='成员')
        st.rerun()
    with SessionLocal() as session:
        view=MemberManagementProjection().member(session,member.id)
        observations=list(session.scalars(select(Observation).where(Observation.patient_id==member.id).order_by(Observation.observed_at.desc())))
        facts=confirmed_profile(session,member.id)
        services={r.id:r.name for r in session.scalars(select(ServiceCatalogItem))}
    c.member_header(member_label(member)+' · 已归档',cycle='历史资料（只读）',owner=view.owner,
        phase='已归档',concern='',focus='',next_action='查阅历史记录',updated=ux.when(member.archived_at))
    st.info('已归档 · '+ux.local_time(member.archived_at).strftime('%Y-%m-%d %H:%M')+'。历史资料只读保留；归档不表示未决医学问题已解决。')
    with st.container(key='soft-member-navigation'):
        section=st.radio('成员页面',['概览','健康','管理','医疗','历程'],horizontal=True,label_visibility='collapsed',
            key=f'member-section-{member.id}',format_func=lambda x:'健康档案' if x=='健康' else x)
    def table(title,rows):
        st.subheader(title)
        if rows:st.dataframe(rows,hide_index=True,width='stretch')
        else:st.caption('没有此类历史记录。')
    if section=='概览':
        c.summary_strip([('健康资料',len(view.documents)),('测量记录',len(observations)),('管理记录',len(view.logs)),('服务记录',len(view.services))])
        st.write('健康档案、年度计划、服务、医生判断和长期历程均保留。自动流程已停止，后续不再进入日常工作。')
    elif section=='健康':
        table('已确认健康档案',facts)
        table('原始资料',[{'资料':d.title,'来源':d.source,'时间':ux.local_time(d.created_at)} for d in view.documents])
        table('测量记录',[{'指标':o.metric_code,'数值':float(o.value_numeric),'单位':o.unit,'来源':o.source,'时间':ux.local_time(o.observed_at)} for o in observations])
        if view.intake:
            st.subheader('初始评估（历史记录）')
            # Preserve section structure and source text without invoking edit controls.
            for label,values in (view.intake.responses or {}).items():
                st.markdown('**'+label+'**')
                entries=values if isinstance(values,list) else [values]
                for entry in entries:
                    if isinstance(entry,dict):
                        st.dataframe([{'项目':k,'记录':str(v)} for k,v in entry.items()],hide_index=True,width='stretch')
                    else:st.write(str(entry))
    elif section=='管理':
        table('年度计划',[{'年度':p.cycle_year or p.start_date.year,'目标':p.main_goal,'负责人':p.owner,'状态':status_label(p.status)} for p in view.programs])
        table('管理记录',[{'时间':ux.local_time(r.occurred_at),'会员反馈':r.member_issue,'处理':r.manager_action,'结果':r.result,'下一步':r.next_action,'来源':r.evidence} for r in view.logs])
        table('服务记录',[{'服务':services.get(r.service_item_id,'健康服务'),'时间':ux.local_time(r.requested_at),'状态':status_label(r.status,context='service_request'),'下一步':r.next_action} for r in view.services])
    elif section=='医疗':
        table('医生判断',[{'时间':ux.local_time(r.created_at),'状态':status_label(r.status),'意见':r.opinion or ''} for r in view.doctor_reviews])
        table('复查记录',[{'复查':r.title,'原因':r.reason,'时间':ux.local_time(r.planned_at),'结果':r.result,'依据':r.evidence,'状态':status_label(r.status)} for r in view.rechecks])
    else:
        from executive_health_ai.ui.pages.member.experience import timeline
        timeline(app,member,client_view=False)
