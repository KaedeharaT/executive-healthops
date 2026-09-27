"""Member-centred working pages. All reads/writes delegate to shared services."""
from datetime import date, datetime, time, timedelta
from uuid import uuid4
import pandas as pd
import streamlit as st
from executive_health_ai.database import SessionLocal
from executive_health_ai.services.management_workflow import ManagementWorkflowService, STEPS, TABLE_FIELDS, PROFILE_FIELDS, LOG_CATEGORIES, RECHECK_STATES, CASE_STATES
from executive_health_ai.services.member_management_projection import MemberManagementProjection
from executive_health_ai.ui import components as c, experience as ux
from executive_health_ai.ui.presentation import data_table, preview, task_records
from executive_health_ai.ui.status_dictionary import status_label

service=ManagementWorkflowService()
projection=MemberManagementProjection()
# Preserve all persisted transition states; present seven operational milestones.
RECHECK_LABELS={**RECHECK_STATES,'COMPLETED':'待报告','WAITING_REVIEW':'待医生复核','CLOSED':'完成'}
RECHECK_STEPS=['待确认','待预约','已预约','待执行','待报告','待医生复核','完成']


def write(command):
    try:
        with SessionLocal() as session:
            row=command(session)
            session.commit()
        st.session_state['workflow-flash']='已保存，相关页面将使用同一份记录。'
        st.rerun()
    except (ValueError,TypeError) as error:
        st.error(str(error))


def view_for(member_id):
    with SessionLocal() as session: return projection.member(session,member_id)


def flash():
    if msg:=st.session_state.pop('workflow-flash',None): st.success(msg)


def open_log(app,patient):
    st.session_state[f'workflow-mode-{patient.id}']='管理日志'
    st.session_state[f'workflow-open-log-{patient.id}']=True
    app._open_member_management(patient.id)


def phases(view):
    if not view.phases:
        st.caption('尚未制定阶段；完成初评与基线后建立年度方案。')
        return
    labels=[p.title+(' · 已完成' if p.status in {'COMPLETED','REVIEWED'} else '' if p.status=='ACTIVE' else ' · 待开始') for p in view.phases]
    current=next((labels[i] for i,p in enumerate(view.phases) if p.status=='ACTIVE'),'')
    c.workflow(labels,current)


def onboarding(view):
    if view.intake and view.onboarding!='持续管理中':
        st.markdown('**入组进度 · '+view.onboarding+'**')
        labels=[label+(' · 已完成' if done else ' · 待完成') for label,done in view.milestones]
        current=next((labels[i] for i,(_,done) in enumerate(view.milestones) if not done),'')
        c.workflow(labels,current)


def enroll(app):
    with st.expander('会员入组 · 新建年度服务周期'):
        with st.form('workflow-enroll'):
            name=st.text_input('会员称呼')
            members=app._members()
            existing=st.selectbox('会员档案',['新会员']+[str(m.id) for m in members],format_func=lambda k:next((m.display_name for m in members if str(m.id)==k),k))
            owner=st.text_input('责任健康管理师',value='演示健康管理师')
            a,b=st.columns(2)
            start=a.date_input('服务开始日期');end=b.date_input('服务结束日期',value=date.today()+timedelta(days=364))
            goal=st.text_input('年度目标');advisor=st.text_input('客户顾问（选填）')
            submit=st.form_submit_button('确认入组')
        if submit:
            from uuid import UUID
            write(lambda s:service.enroll(s,name=name,start=start,end=end,owner=owner,goal=goal,advisor=advisor,member_id=None if existing=='新会员' else UUID(existing)))


def annual(app):
    c.page_shell('manager','年度管理','围绕服务周期、当前阶段和下一节点推进会员管理。')
    flash()
    with SessionLocal() as session: rows=projection.annual(session)
    rows=[(m,v) for m,v in rows if v.program]
    c.summary_strip([('年度周期',len(rows)),('持续管理',sum(v.program.status=='ACTIVE' for _,v in rows)),('待建基线',sum(v.onboarding=='待建立基线' for _,v in rows))])
    query,state,owner=c.filter_bar(key='annual-filter',statuses=sorted({status_label(v.program.status) for _,v in rows}),owners=sorted({v.owner for _,v in rows}))
    rows=[(m,v) for m,v in rows if (not query or query in (m.display_name+v.program.main_goal).casefold()) and (state=='全部' or state==status_label(v.program.status)) and (owner=='全部' or owner==v.owner)]
    chosen=data_table(rows,[{'会员': m.display_name,'服务周期': f'{v.program.start_date} — {v.program.end_date}', '当前阶段': v.current_phase.title if v.current_phase else v.onboarding if v.intake else app.display_program_phase(v.program.current_phase),
        '年度目标': v.program.main_goal,'负责人':v.owner,'阶段状态':status_label(v.current_phase.status) if v.current_phase else v.onboarding,'下一节点':next((p.title for p in v.phases if v.current_phase and p.sequence>v.current_phase.sequence),'阶段复盘') if v.current_phase else '核对年度安排','下一日期':v.current_phase.end_date if v.current_phase else None} for m,v in rows],key='annual-members',label='选择年度会员',auto_select=False)
    if chosen:
        member,view=chosen
        st.session_state['member-return-origin']='年度管理'
        st.session_state[f'workflow-mode-{member.id}']='年度方案与阶段'
        app._open_member_management(member.id)
        st.rerun()



def phase_table(view,*,key):
    return data_table(view.phases,[{'事项': p.title,'目标':p.goal,'负责人':p.owner or view.owner,'状态':status_label(p.status),
        '计划完成':p.end_date,'实际完成':ux.local_time(p.completed_at) if p.completed_at else None,'结果':p.result_feedback or '待复盘'} for p in view.phases],key=key,label='选择阶段')


def phase_detail(view,phase,*,key):
    tasks=[t for t in view.tasks if t.program_id==view.program.id and t.due_at and phase.start_date<=ux.local_time(t.due_at).date()<=phase.end_date]
    c.summary_strip([('阶段目标',preview(phase.goal,50)),('已完成',sum(t.status=='COMPLETED' for t in tasks)),
                     ('待完成',sum(t.status not in {'COMPLETED','CANCELLED'} for t in tasks)),('计划结束',str(phase.end_date))])
    st.markdown('**阶段事项**')
    st.caption('显示本年度方案内、计划日期落在所选阶段的事项。未排期事项保留在管理事项中。')
    selected=data_table(tasks,[{'事项':t.title,'目标':t.instruction,'负责人':t.assignee or phase.owner or view.owner,
        '状态':status_label(t.status),'计划日期':ux.local_time(t.due_at),'实际日期':ux.local_time(t.completed_at) if getattr(t,'completed_at',None) else None,
        '结果':getattr(t,'outcome','') or ('已完成' if t.status=='COMPLETED' else '待执行')} for t in tasks],key=key+'-tasks',auto_select=False)
    if selected:
        with st.expander('事项目标与结果',expanded=True):st.write(selected.instruction)
    with st.expander('阶段管理内容与结果'):
        st.write(phase.goal);st.write(phase.management_content or '按阶段目标执行')
        st.write('阶段结果：'+(phase.result_feedback or '待阶段复盘'))



def intake(app,patient,member=False,assessment_id=None):
    from executive_health_ai.ui.pages.manager import intake_entry
    flash();view=view_for(patient.id);row=view.intake
    if assessment_id:
        from dataclasses import replace
        from executive_health_ai.models.management_workflow import IntakeAssessment
        from executive_health_ai.services.management_workflow import owned
        from executive_health_ai.services.member_management_projection import intake_program
        with SessionLocal() as session:
            row=owned(session,IntakeAssessment,assessment_id,patient.id)
            program=intake_program(session,row)
            view=projection.member(session,patient.id,program.id) if program else view
            view=replace(view,intake=row,program=program)
    if not member:
        st.button('← 返回健康档案',key=f'intake-back-{patient.id}',on_click=intake_entry.return_to_archive,args=(app,patient))
    with st.container(key='soft-intake-header'):
        st.subheader('初始健康评估')
        c.summary_strip([('会员',patient.display_name),('当前年度',str(row.cycle_year if row else (view.program.cycle_year or view.program.start_date.year) if view.program else date.today().year)),
                         ('责任健管',view.owner),('评估状态',intake_entry.state(row))])
    if not row:
        st.button('开始评估',type='primary',on_click=intake_entry.open_intake,args=(patient,view));return
    st.caption('保存的是本人陈述，提交后由健管核对；症状评分不代表诊断。')
    if st.session_state.get(f'intake-readonly-{patient.id}') and not assessment_id:
        intake_entry.answers(row)
        if row.status=='DRAFT':
            st.button('继续填写',type='primary',on_click=intake_entry.open_intake,args=(patient,view))
        elif row.status=='CONFIRMED':
            st.write('会员自述关注：'+row.member_concern)
            st.write('专业管理重点：'+row.professional_focus)
            if not member:
                st.button('补充/修正',on_click=intake_entry.amend,args=(patient,view))
        return
    if row.status!='DRAFT':
        st.success('问卷已提交' if row.status=='SUBMITTED' else '初评已确认')
        st.write('会员自述关注：'+ux.business_text(row.member_concern))
        with st.expander('查看已提交资料'):
            intake_entry.answers(row)
        if not member:manager_assessment(patient,view)
        return
    wizard_steps=[label for label in STEPS if label!='最近用药']
    resume_index=next((i for i,label in enumerate(wizard_steps[:-1]) if label not in row.responses or label=='当前用药 / 营养补充' and '最近用药' not in row.responses),len(wizard_steps)-1)
    index=st.session_state.get(f'intake-step-{patient.id}',resume_index)
    index=min(index,len(wizard_steps)-1)
    with st.container(key='soft-intake-progress'):
        chosen=st.selectbox('填写步骤',range(len(wizard_steps)),index=index,format_func=lambda i:f'{i+1}. {wizard_steps[i]}',key=f'intake-select-{patient.id}-{index}')
        step=wizard_steps[chosen]
        from executive_health_ai.ui.neumorphism import intake_steps
        intake_steps(wizard_steps, chosen, row.responses)
        st.progress(chosen/(len(wizard_steps)-1),text=f'第{chosen+1}步 / {len(wizard_steps)}步 · 可保存草稿后继续填写')
    if step=='确认提交':
        missing=[x for x in STEPS[:-1] if x not in row.responses]
        st.write('尚未确认：'+'、'.join(missing) if missing else '各步骤已保存，请确认自述准确后提交。')
        consent=st.checkbox('我确认已逐项核对；未知项由健康管理团队继续确认')
        if st.button('提交初始评估',disabled=bool(missing) or not consent,type='primary'):
            write(lambda s:service.submit_intake(s,patient.id,row.id,'会员本人' if member else view.owner))
        return
    with st.form(f'intake-form-{patient.id}-{chosen}'):
        old=row.responses.get(step)
        if step=='基础资料':
            name=st.text_input('姓名 / 称呼',value=patient.display_name or '')
            birth=st.date_input('出生日期（未知可留空）',value=patient.birth_date,min_value=date(1900,1,1),max_value=date.today())
            sex=st.selectbox('性别',['未提供','male','female'],index=['未提供','male','female'].index(patient.sex) if patient.sex in {'male','female'} else 0,format_func=lambda x:{'male':'男','female':'女'}.get(x,x))
            st.caption('身高与体重使用已有健康观测，联系方式通过家庭联系人维护。')
            data={'display_name':name,'birth_date':birth.isoformat() if birth else None,'sex':None if sex=='未提供' else sex}
        elif step in TABLE_FIELDS:
            if step=='专项症状评估':st.caption('按问卷原始问题记录症状；需要由专业人员核对，不作为医学诊断。')
            frame=st.data_editor(pd.DataFrame(old or [],columns=TABLE_FIELDS[step]),num_rows='dynamic',hide_index=True,width='stretch',key=f'intake-data-{patient.id}-{chosen}')
            data=frame.fillna('').to_dict('records')
        elif step in PROFILE_FIELDS:
            data={k:st.text_input(k,value=(old or {}).get(k,'')) for k in PROFILE_FIELDS[step]}
        else:
            data={'concern':st.text_area('会员自己最想改善什么',value=row.member_concern)}
        recent=None
        if step=='当前用药 / 营养补充':
            st.markdown('**最近用药**')
            recent=st.data_editor(pd.DataFrame(row.responses.get('最近用药') or [],columns=TABLE_FIELDS['最近用药']),num_rows='dynamic',hide_index=True,key=f'intake-recent-{patient.id}').fillna('').to_dict('records')
        st.divider()
        with st.container(key='soft-intake-actions'):
            left,right=st.columns(2)
            save_only=left.form_submit_button('保存草稿')
            save=right.form_submit_button('保存草稿并继续',type='primary')
    if save or save_only:
        try:
            with SessionLocal() as session:
                service.save_intake(session,patient.id,row.cycle_year,step,data,'会员本人' if member else view.owner)
                if recent is not None:service.save_intake(session,patient.id,row.cycle_year,'最近用药',recent,'会员本人' if member else view.owner)
                session.commit()
            st.session_state[f'intake-step-{patient.id}']=min(chosen+1,len(wizard_steps)-1) if save else chosen
            st.session_state['workflow-flash']='草稿已保存，可继续填写。';st.rerun()
        except ValueError as error:st.error(str(error))


def manager_assessment(patient,view):
    row=view.intake
    with st.expander('健管专业初评',expanded=row.review_status!='CONFIRMED'):
        st.caption('专业管理重点与会员关注分开；医学结论、检查建议和用药改变须有医生或正式医疗依据。')
        st.write('当前状态：'+{'DRAFT':'草稿','READY_FOR_REVIEW':'待初评','WAITING_MEDICAL_REVIEW':'等待医生','CONFIRMED':'已确认'}.get(row.review_status,'待核对'))
        with st.form(f'intake-review-{row.id}'):
            focus=st.text_area('专业管理重点',value=row.professional_focus)
            missing=st.text_area('需要补充资料',value=row.review.get('missing','') if isinstance(row.review.get('missing'),str) else '')
            tests=st.text_area('拟补充检查（需医生确认）',value=row.review.get('supplementary_tests',''))
            medical=st.text_area('需医生确认内容',value=row.review.get('medical_question',''))
            annual=st.text_area('初步年度管理重点',value=row.review.get('annual_focus',''))
            actor=st.text_input('初评人',value=view.owner)
            decision=st.selectbox('初评决定',['DRAFT','CONFIRM','RETURN'],format_func=lambda x:{'DRAFT':'保存初评草稿','CONFIRM':'确认初评 / 交医生确认','RETURN':'退回问卷补充'}[x])
            submit=st.form_submit_button('保存健管初评',type='primary')
        if submit:write(lambda s:service.review_intake(s,patient.id,row.id,focus=focus,missing=missing,tests=tests,medical_question=medical,annual_focus=annual,actor=actor,decision=decision))


def family(patient,view):
    with st.expander('家庭关系与紧急联系人'):
        data_table(view.family,[{'关系':r.relationship,'联系人':r.contact_name,'身份':'紧急联系人' if r.emergency else '家庭联系人'} for r in view.family],key=f'family-grid-{patient.id}',selectable=False)
        with st.form(f'family-{patient.id}'):
            relation=st.text_input('关系');name=st.text_input('联系人');contact=st.text_input('联系方式')
            emergency=st.checkbox('紧急联系人');shared=st.checkbox('共享服务权益标记（不自动授予权限）')
            members=[]
            with SessionLocal() as session:members=[m for m,_ in projection.annual(session) if m.id!=patient.id]
            linked=st.selectbox('关联会员（可选）',[None]+[m.id for m in members],format_func=lambda k:next((m.display_name for m in members if m.id==k),'不关联'))
            submit=st.form_submit_button('保存家庭关系')
        if submit:write(lambda s:service.family(s,patient.id,relationship=relation,contact_name=name,contact=contact,emergency=emergency,shared_entitlement=shared,related_patient_id=linked,actor=view.owner))


def management(app,patient):
    flash();view=view_for(patient.id)
    if not view.program:
        st.info('先从年度管理建立服务周期。');return
    st.caption('年度目标：'+preview(view.program.main_goal,90))
    action_col,mode_col=st.columns([1,4])
    if action_col.button('新增管理记录',key=f'management-add-log-{patient.id}'):
        st.session_state[f'workflow-mode-{patient.id}']='管理日志'
        st.session_state[f'workflow-open-log-{patient.id}']=True
        st.rerun()
    mode=mode_col.selectbox('管理工作',['管理事项','管理日志','年度方案与阶段','检查复查','阶段评估','关联服务','计划调整与随访'],key=f'workflow-mode-{patient.id}',label_visibility='collapsed')
    if mode=='管理事项':
        app.render_tasks({'tasks':list(view.tasks)})
    elif mode=='管理日志':
        if not view.logs or st.session_state.get(f'workflow-open-log-{patient.id}',False):
            with st.container(): logs(patient,view)
    elif mode=='年度方案与阶段':plan(patient,view)
    elif mode=='检查复查':recheck(patient,view)
    elif mode=='阶段评估':stage_review(patient,view)
    elif mode=='关联服务':
        if view.services:
            service_row=data_table(view.services,[{'服务原因':r.reason,'状态':status_label(r.status,context='service_request')} for r in view.services],key=f'member-service-records-{patient.id}',auto_select=False)
            if service_row is None:return
            phase=st.selectbox('关联阶段',[None]+list(view.phases),format_func=lambda r:r.title if r else '年度周期')
            linked=st.selectbox('关联管理事项',[None]+list(view.tasks),format_func=lambda r:r.title if r else '不关联')
            if st.button('关联周期与阶段'):write(lambda s:service.link_service(s,patient.id,service_row.id,view.program.id,phase.id if phase else None,linked.id if linked else None))
        if view.services and service_row:
            from executive_health_ai.ui.pages.manager.services import service_detail
            service_detail(app,service_row,patient)
        else:app.render_member_service_management(patient)
    else:
        from executive_health_ai.ui.pages.manager.experience import management as legacy
        action=st.radio('计划操作',['建立 / 调整计划','安排随访','记录阶段结果'],horizontal=True)
        legacy(app,patient,action=action)
    if mode=='管理日志':
        st.subheader('管理日志')
        log_rows(view.logs,key=f'logs-{patient.id}',switch=True)
    elif mode!='管理事项':
        st.subheader('最近管理记录');log_rows(view.logs[:2],key=f'recent-logs-{patient.id}')


def log_rows(rows, *, key='log-preview', switch=False):
    rows=list(rows)
    if not rows:
        st.caption('暂无管理记录。完成沟通后记录结果与下一步。');return
    if switch:
        left,right=st.columns([1,2])
        mode=left.radio('管理记录视图',['时间轴','表格'],horizontal=True,key=key+'-view')
        query=right.text_input('搜索管理记录',key=key+'-search')
    else:mode,query='时间轴',''
    rows=[r for r in rows if not query or query in r.member_issue+r.manager_action+r.result+r.next_action+r.owner]
    if not rows:
        st.caption('暂无匹配管理记录。');return
    records=[{'日期':ux.local_time(r.occurred_at),'类型':r.category,'沟通方式':r.channel,'发生什么':r.member_issue,'结果':r.result,'下一步':r.next_action,'跟进时间':ux.local_time(r.follow_up_at) if r.follow_up_at else None,'负责人':r.owner} for r in rows]
    if mode=='表格':
        selected=data_table(rows,records,key=key+'-grid',export=True)
        if selected:log_detail(selected)
    else:
        page=st.number_input('记录页',min_value=1,max_value=max(1,(len(rows)+7)//8),value=1,step=1,key=key+'-page') if switch and len(rows)>8 else 1
        for row in rows[(page-1)*8:page*8]:
            c.timeline_event(preview(row.member_issue,40),preview(row.result,60)+' · 下一步：'+preview(row.next_action,45),ux.when(row.occurred_at),row.category+' · '+row.owner)
            if switch:
                with st.expander('记录详情 · '+ux.when(row.occurred_at)+' · '+preview(row.member_issue,20)):
                    log_detail(row)


def log_detail(row):
    st.write('发生了什么：'+ux.business_text(row.member_issue))
    st.write('已做：'+ux.business_text(row.manager_action))
    st.write('结果：'+ux.business_text(row.result or '待反馈'))
    st.write('下一步：'+ux.business_text(row.next_action or '暂未安排'))
    st.caption(ux.owner(row.owner)+' · '+ux.due_date(row.follow_up_at))
    if row.follow_up_task_id:st.caption('已生成关联待办，不重复创建。')
    with st.container():
        st.write(' · '.join(str(getattr(row,k,'') or '') for k in ['channel','service_type','provider','department','expert']))
        st.write(ux.business_text(row.evidence or '未补充依据'))


def logs(patient,view):
    st.markdown('**新增管理记录**')
    request_key=st.session_state.setdefault(f'log-key-{patient.id}',str(uuid4()))
    pending_key=f'log-pending-{patient.id}'
    if pending:=st.session_state.get(pending_key):
        st.info('已准备后续待办，请确认负责人和跟进时间。')
        c.summary_strip([('下一步',pending['next_action']),('负责人',pending['owner']),('跟进日期',ux.when(pending['follow_up_at']))])
        if st.button('确认保存并建立待办',type='primary'):
            save_log(patient,view,request_key,pending,True)
        if st.button('修改记录'):
            st.session_state.pop(pending_key,None);st.rerun()
        return
    with st.form(f'log-form-{patient.id}'):
        a,b=st.columns(2);category=a.selectbox('记录类型',LOG_CATEGORIES);occurred=b.date_input('发生日期')
        occurred_time=st.time_input('发生时间',value=datetime.now(ux.LOCAL).time().replace(second=0,microsecond=0))
        issue=st.text_input('发生了什么');action=st.text_area('我做了什么',height=70);result=st.text_input('本次结果');next_action=st.text_input('下一步')
        a,b=st.columns(2);follow=a.date_input('下次跟进日期',value=None);owner=b.text_input('执行负责人',value=view.owner)
        with st.expander('机构、服务与依据（选填）'):
            channel=st.selectbox('沟通渠道',['电话','微信','面谈','其他']);provider=st.text_input('机构 / 医院');department=st.text_input('科室');expert=st.text_input('专家');evidence=st.text_area('依据说明')
            service_type=st.text_input('服务类型')
            linked_task=st.selectbox('相关任务',[None]+list(view.tasks),format_func=lambda r:r.title if r else '无')
            linked_doc=st.selectbox('相关报告',[None]+list(view.documents),format_func=lambda r:r.title if r else '无')
            linked_review=st.selectbox('相关医生复核',[None]+list(view.doctor_reviews),format_func=lambda r:r.question_for_doctor[:40] if r else '无')
            linked_service=st.selectbox('相关服务',[None]+list(view.services),format_func=lambda r:r.reason[:40] if r else '无')
            linked_risk=st.selectbox('相关风险',[None]+list(view.risks),format_func=lambda r:ux.business_text(r.summary[:40]) if r else '无')
        submit=st.form_submit_button('保存',type='primary')
    if submit:
        payload=dict(occurred_at=datetime.combine(occurred,occurred_time,ux.LOCAL),category=category,channel=channel,
            member_issue=issue,manager_action=action,result=result,next_action=next_action,
            follow_up_at=datetime.combine(follow,time(17),ux.LOCAL) if follow else None,owner=owner,
            provider=provider,department=department,expert=expert,evidence=evidence,service_type=service_type,
            related_task_id=linked_task.id if linked_task else None,related_document_id=linked_doc.id if linked_doc else None,
            related_doctor_review_id=linked_review.id if linked_review else None,related_service_id=linked_service.id if linked_service else None,
            related_risk_id=linked_risk.id if linked_risk else None)
        if next_action.strip() and follow:
            st.session_state[pending_key]=payload;st.rerun()
        save_log(patient,view,request_key,payload,False)


def save_log(patient,view,request_key,payload,followup):
    try:
        with SessionLocal() as session:
            service.record_log(session,patient.id,view.program.id,actor=view.owner,request_key=request_key,create_followup=followup,**payload)
            session.commit()
        for key in ('workflow-open-log','log-key','log-pending'):st.session_state.pop(f'{key}-{patient.id}',None)
        st.session_state['workflow-flash']='记录已保存，后续待办已进入今日工作。' if followup else '管理记录已保存。'
        st.rerun()
    except ValueError as error:st.error(str(error))


def plan(patient,view):
    st.write('年度目标：'+view.program.main_goal)
    phase=c.stage_stepper(view.phases,key=f'phase-stepper-{patient.id}',current_id=view.current_phase.id if view.current_phase else None)
    if phase:
        phase_detail(view,phase,key=f'phase-detail-{phase.id}')
        for review in view.reviews:
            if review.phase_id==phase.id:
                with st.expander('本阶段复盘记录'):
                    for label,value in review.content.items():st.write(label+'：'+(value or '本次未记录'))
    with st.expander('增加阶段',expanded=not view.phases):
        with st.form(f'phase-{patient.id}'):
            title=st.text_input('阶段名称');goal=st.text_input('阶段目标');content=st.text_area('管理内容')
            a,b=st.columns(2);start=a.date_input('阶段开始',value=view.program.start_date);end=b.date_input('阶段结束',value=view.program.start_date+timedelta(days=29))
            owner=st.text_input('阶段负责人',value=view.owner);submit=st.form_submit_button('保存阶段')
        if submit:write(lambda s:service.add_phase(s,patient.id,view.program.id,title=title,goal=goal,content=content,start=start,end=end,owner=owner))
    if view.program.status=='PLANNED' and st.button('启动年度方案',type='primary'):
        write(lambda s:service.start_program(s,patient.id,view.program.id,view.owner))


def recheck(patient,view,selected_id=None):
    if not selected_id:
        recheck_create(patient,view)
    if selected_id:
        selected=next((r for r in view.rechecks if r.id==selected_id),None)
    else:
        selected=data_table(view.rechecks,[{'检查项目':r.title,'原因':r.reason,'计划日期':ux.local_time(r.planned_at),'状态':RECHECK_LABELS[r.status],'医院':r.provider,'负责人':r.owner,'报告状态':'已关联' if r.document_id else '待报告','下一步':RECHECK_STATES[list(RECHECK_STATES)[list(RECHECK_STATES).index(r.status)+1]] if r.status!='CLOSED' else '查看结果'} for r in view.rechecks],key=f'recheck-grid-{patient.id}',search=True,auto_select=False)
    if selected:
        recheck_detail(patient,view,selected)


def recheck_create(patient,view):
    with st.expander('建立检查复查计划',expanded=not view.rechecks):
        with st.form(f'recheck-{patient.id}'):
            title=st.text_input('检查项目');reason=st.text_input('检查原因');planned=st.date_input('计划检查日期',value=date.today()+timedelta(days=7))
            provider=st.text_input('检查机构');evidence=st.text_area('正式医疗建议依据');owner=st.text_input('复查负责人',value=view.owner)
            review=st.selectbox('已确认医生意见',[None]+[r for r in view.doctor_reviews if r.status=='CONFIRMED'],format_func=lambda r:r.question_for_doctor[:40] if r else '使用已核对医疗记录')
            submit=st.form_submit_button('建立复查事项',type='primary')
        if submit:write(lambda s:service.create_recheck(s,patient.id,view.program.id,title=title,reason=reason,planned_at=datetime.combine(planned,time(9),ux.LOCAL),owner=owner,provider=provider,evidence=evidence,doctor_review_id=review.id if review else None))


def recheck_detail(patient,view,row):
    c.workflow(RECHECK_STEPS,RECHECK_LABELS[row.status])
    with st.expander(row.title+' · '+RECHECK_LABELS[row.status],expanded=True):
        st.caption(f'{ux.when(row.planned_at)} · {ux.owner(row.owner)}');st.write(row.reason)
        if row.status=='CLOSED':st.write(row.result);return
        target=list(RECHECK_STATES)[list(RECHECK_STATES).index(row.status)+1]
        with st.form(f'recheck-update-{row.id}'):
            result=st.text_input('复核结果 / 执行记录',value=row.result)
            document=st.selectbox('关联报告',[None]+list(view.documents),format_func=lambda r:r.title if r else '尚未取得')
            next_date=st.date_input('下次复查日期（选填）',value=None)
            action_label='记录检查已执行' if target=='COMPLETED' else '开始跟进报告' if row.status=='COMPLETED' else '推进至'+RECHECK_LABELS[target]
            submit=st.form_submit_button(action_label,type='primary')
        if submit:write(lambda s:service.advance_recheck(s,patient.id,row.id,status=target,actor=view.owner,result=result,document_id=document.id if document else None,next_recheck_at=datetime.combine(next_date,time(9),ux.LOCAL) if next_date else None))

def stage_review(patient,view):
    phase=view.current_phase
    if phase:
        stage_metrics(patient,view,phase)
    if not phase:st.info('暂无执行中的阶段；先启动年度方案。');return
    previous=next((r for r in view.reviews if r.phase_id==phase.id),None)
    if previous:
        st.success('本阶段已完成复盘；当前阶段继续执行至负责人确认交接。')
        data_table(list(previous.content),[{'复盘项目':k,'结果摘要':v} for k,v in previous.content.items()],key=f'review-result-{previous.id}',selectable=False)
        with st.expander('完整结论与下一阶段建议'):
            for k,v in previous.content.items():st.write(k+'：'+v)
        if st.button('确认进入下一阶段',type='primary'):
            write(lambda s:service.advance_phase(s,patient.id,phase.id,view.owner))
        return
    st.write('本阶段目标：'+phase.goal)
    st.caption('记录实际执行与观察变化，不自动作因果归因。数值结果仍沿用原阶段结果入口。')
    with st.expander('记录阶段评估',expanded=False), st.form(f'stage-review-{phase.id}'):
        content={}
        fields=['实际完成','关键指标变化','用药执行','检查完成','生活方式执行','服务完成','未解决问题','下一阶段建议']
        for i in range(0,len(fields),2):
            left,right=st.columns(2)
            content[fields[i]]=left.text_area(fields[i],height=70)
            content[fields[i+1]]=right.text_area(fields[i+1],height=70)
        decision=st.selectbox('阶段决定',['CONTINUE','ADJUST','DOCTOR_REVIEW','STABILIZE','NEXT_PHASE'],format_func=lambda x:{'CONTINUE':'继续','ADJUST':'调整','DOCTOR_REVIEW':'转医生','STABILIZE':'进入稳定管理','NEXT_PHASE':'进入下一阶段'}[x])
        submit=st.form_submit_button('确认阶段结果',type='primary')
    if submit:write(lambda s:service.review_stage(s,patient.id,phase.id,content=content,decision=decision,actor=view.owner))


def consultations(app,patient=None,doctor=False,members=None,selected_id=None):
    flash()
    selected_case=None
    if patient is None:
        members=members if members is not None else app._members()
        if not members:st.info('暂无会员。');return
        if not doctor:
            with SessionLocal() as session:
                all_cases=[(m,r) for m,v in projection.annual(session) for r in v.consultations]
            selection=data_table(all_cases,[{'会员':m.display_name,'会诊时间':ux.local_time(r.scheduled_at),'状态':CASE_STATES[r.status],'方式':r.location,'负责人':r.owner,'下一步':'确认行动拆解' if r.status=='WAITING_ACTIONS' else '核对资料与会诊安排'} for m,r in all_cases],key='global-consultations',search=True,auto_select=False)
            if selection:patient,selected_case=selection
            else:
                with st.expander('为会员申请会诊'):
                    patient=st.selectbox('会诊会员',members,format_func=lambda m:ux.business_text(m.display_name),key='consultation-member-manager')
                    consultations(app,patient)
                return
        else:
            patient=st.selectbox('会诊会员',members,format_func=lambda m:ux.business_text(m.display_name),key='consultation-member-doctor')
    view=view_for(patient.id)
    if doctor and view.intake and view.intake.status!='DRAFT':
        with st.expander('初始评估用药候选 · 医生核对'):
            candidates=view.intake.responses.get('当前用药 / 营养补充',[])
            if candidates:
                index=st.selectbox('待确认用药',range(len(candidates)),format_func=lambda i:candidates[i].get('名称','待核对'))
                st.caption('确认只是录入已核对处方记录，不是新开药或调整处方。')
                with st.form(f'medication-confirm-{patient.id}'):
                    evidence=st.text_area('正式处方 / 医疗记录依据');actor=st.text_input('核对医生')
                    submit=st.form_submit_button('确认映射到现有用药档案')
                if submit:write(lambda s:service.confirm_medication(s,patient.id,view.intake.id,index,actor=actor,role='doctor',evidence=evidence))
            else:st.caption('暂无已提交用药候选。')
    st.subheader('正式会诊')
    if not doctor and not selected_id:
        with st.expander('申请正式会诊',expanded=not view.consultations):
            with st.form(f'case-new-{patient.id}'):
                reason=st.text_area('为什么会诊');scheduled=st.date_input('会诊日期');location=st.text_input('地点 / 方式');evidence=st.text_area('关键资料与依据')
                scheduled_time=st.time_input('会诊时间',value=time(10))
                primary_doctor=st.text_input('主要参加医生');primary_department=st.text_input('主要科室')
                extra_doctors=st.text_area('其他参加医生（每行：医生｜科室）',height=70)
                submit=st.form_submit_button('提交会诊申请')
            if submit:
                participants=[{'doctor':primary_doctor.strip(),'department':primary_department.strip()}]
                for line in extra_doctors.splitlines():
                    if line.strip():
                        parts=line.replace('|','｜').split('｜',1)
                        participants.append({'doctor':parts[0].strip(),'department':parts[1].strip() if len(parts)>1 else ''})
                write(lambda s:service.create_consultation(s,patient.id,reason=reason,scheduled_at=datetime.combine(scheduled,scheduled_time,ux.LOCAL),location=location,participants=participants,evidence=evidence,owner=view.owner,program_id=view.program.id if view.program else None))
    if not view.consultations: return
    selected=next((r for r in view.consultations if r.id==selected_id),None) if selected_id else selected_case or data_table(view.consultations,[{'会诊':ux.local_time(r.scheduled_at),'状态':CASE_STATES[r.status],'方式':r.location,'负责人':r.owner,'结论':r.conclusion or '待医生确认'} for r in view.consultations],key=f'consultations-{patient.id}-{doctor}',label='会诊记录',auto_select=False)
    if not selected:return
    with SessionLocal() as session:case,encounter,opinions=projection.consultation(session,selected.id)
    current={'PREPARING':'资料准备','SCHEDULED':'会诊','WAITING_RESULT':'整理结果','WAITING_ACTIONS':'行动拆解','COMPLETED':'完成'}[case.status]
    c.workflow(['资料准备','医生确认','会诊','整理结果','行动拆解','完成'],current)
    st.markdown('### '+preview(encounter.reason,65));st.caption(CASE_STATES[case.status]+' · '+ux.owner(case.owner)+' · '+case.location)
    with st.expander('会诊原因与关键依据'):
        st.write(encounter.reason);st.write(case.evidence)
    st.caption('参加：'+'、'.join(p['department']+' '+p['doctor'] for p in case.participants))
    opinion=data_table(opinions,[{'医生':o.clinician_name,'科室':o.department,'观点与建议摘要':o.content,'状态':'已提交'} for o in opinions],key=f'opinions-{case.id}-{doctor}')
    if opinion:
        with st.expander('完整医生意见 · '+opinion.clinician_name):st.write(opinion.content)
    if not doctor and case.status=='PREPARING':
        if st.button('确认会诊安排',type='primary'):
            write(lambda s:service.schedule_consultation(s,patient.id,case.id,view.owner))
    if doctor and case.status in {'SCHEDULED','WAITING_RESULT'}:
        participant=st.selectbox('本次参加医生',case.participants,format_func=lambda p:p['doctor']+' · '+p['department'])
        with st.form(f'case-opinion-{case.id}'):
            opinion=st.text_area('本人医学意见');submit=st.form_submit_button('提交本科意见',type='primary')
        if submit:write(lambda s:service.consultation_opinion(s,patient.id,case.id,actor=participant['doctor'],department=participant['department'],content=opinion,role='doctor'))
        with st.expander('收齐意见后确认综合结论'):
            with st.form(f'case-conclusion-{case.id}'):
                conclusion=st.text_area('综合结论与执行建议');submit=st.form_submit_button('确认综合结论并交健管')
            if submit:write(lambda s:service.conclude_consultation(s,patient.id,case.id,actor=participant['doctor'],role='doctor',conclusion=conclusion))
    if case.conclusion:st.write('综合结论：'+case.conclusion)
    if not doctor and case.status=='WAITING_ACTIONS':
        st.markdown('**方案拆解 · 保存草稿不会创建任务**')
        data_table(case.action_drafts,[{'事项':a['title'],'类型':a['category'],'负责人':a['owner'],'截止':a['due']} for a in case.action_drafts],key=f'case-actions-grid-{case.id}',selectable=False)
        if case.action_drafts:
            with st.expander('完整行动草稿'):
                for action in case.action_drafts:
                    st.write(ux.business_text(action['title']))
                    st.caption(' · '.join(str(action[k]) for k in ('category','owner','due')))
        with st.form(f'case-actions-{case.id}'):
            category=st.selectbox('事项类型',['复查事项','用药管理事项','生活方式事项','服务事项','医生复核'])
            title=st.text_input('具体执行事项');owner=st.text_input('事项负责人',value=view.owner);due=st.date_input('事项截止日期')
            submit=st.form_submit_button('保存行动草稿')
        if submit:
            actions=[*case.action_drafts,{'category':category,'title':title,'owner':owner,'due':due.isoformat()}]
            write(lambda s:service.confirm_actions(s,patient.id,case.id,actions=actions,actor=view.owner))
        if case.action_drafts and st.button('确认并创建全部事项',type='primary'):
            write(lambda s:service.confirm_actions(s,patient.id,case.id,actions=case.action_drafts,actor=view.owner,confirm=True))
    if case.status=='COMPLETED':st.success('已交由'+case.confirmed_by+'执行，事项进入今日工作。')


def stage_metrics(patient,view,phase):
    """Actual observations within phase dates; never label annual baseline as phase start."""
    from executive_health_ai.ui.pages.health_visualization import load_series
    from executive_health_ai.services.health_visualization import filter_period, series_options, option_label
    from executive_health_ai.ui.charts.health import render_metric_trend
    from executive_health_ai.services.baseline_visualization import number_text
    start=datetime.combine(phase.start_date,time.min,ux.LOCAL)
    end=datetime.combine(phase.end_date,time.max,ux.LOCAL)
    series=filter_period(load_series(patient.id),'全部',start=start,end=min(end,datetime.now(ux.LOCAL)))
    comparable=[s for s in series if s.has_trend]
    st.markdown('**阶段指标对比**')
    data_table(comparable,[{'指标':s.label,'阶段内首条':f'{number_text(s.points[0].value)} {s.unit}','阶段内最新':f'{number_text(s.points[-1].value)} {s.unit}', '变化':s.comparison} for s in comparable],key=f'stage-metrics-{phase.id}',selectable=False,empty='本阶段暂无足够的连续数值记录。可先记录执行结果。')
    if comparable:
        st.caption('比较阶段内首条与最后一条有效记录，不冒充阶段边界测量；不作因果归因。')
        options=series_options(comparable)
        code=st.selectbox('阶段观察指标',list(options),format_func=lambda c:option_label(c,options[c]),key=f'stage-metric-{phase.id}')
        render_metric_trend(options[code],key=f'stage-trend-{phase.id}')
