"""Compact goal/data loop inside the existing Member360 workspace."""
from uuid import UUID, uuid4
import streamlit as st
from sqlalchemy import select, or_
from executive_health_ai.database import SessionLocal
from executive_health_ai.models import HealthProgram, Observation
from executive_health_ai.models.goal_data import ManagementGoal, DailyHealthSummary, CommunicationRecord
from executive_health_ai.services import management_goals as goals, goal_metrics


def gate(app,patient,view):
    with SessionLocal() as session:
        program=session.get(HealthProgram,view.program.id) if view.program else None
        state=goals.prerequisites(session,program)
        if state['intake'] and not state['goal']:
            state['goal']=goals.prepare(session,program);session.commit()
        goal=state['goal']
        if state['formal']:return False
        identity=goal.id if goal else None
        confirmed=bool(goal and goal.confirmed_at)
        title=goal.title if goal else ''
        kind=goal.goal_type if goal else 'CUSTOM'
        end=goal.target_date if goal else None
        target=str(goal.target_value) if goal and goal.target_value is not None else ''
        plan=dict(goal.plan_draft) if goal else {}
    main,rail=st.columns([2.6,1],gap='large')
    with main,st.container(key='v7-main-management'):
        if not state['intake']:
            st.subheader('尚未进入正式年度健康管理')
            st.write('当前：资料收集中')
            st.caption('✓ 建立会员　● 完成初始评估　○ 确认健康管理目标　○ 建立年度健康基线　○ 制定管理计划')
            st.write('下一步：完成剩余初评资料')
            if st.button('继续处理初评',type='primary',key='goal-intake-next'):
                from executive_health_ai.ui.pages.manager.intake_entry import open_intake
                open_intake(patient,view)
                app.request_navigation(surface='运营后台',ops_page='成员',member_id=patient.id,member_section='健康')
        elif not confirmed:
            st.subheader('确认健康管理目标')
            st.caption('依据会员表达与现有资料准备；请确认本年度希望改善什么。')
            selected=st.selectbox('管理重点',list(goal_metrics.GOAL_LABELS),index=list(goal_metrics.GOAL_LABELS).index(kind),format_func=goal_metrics.GOAL_LABELS.get)
            edited=st.text_input('目标草稿',value=title)
            target_date=st.date_input('目标日期',value=end)
            with st.expander('数值目标（可选）'):
                numeric=st.text_input('目标值',value=target if selected==kind else '',help='使用当前指标标准单位；没有明确数值目标时留空。')
            readiness(patient.id,selected)
            if st.button('确认目标与指标',type='primary',key='goal-confirm'):
                try:
                    with SessionLocal() as session:
                        row=session.get(ManagementGoal,identity)
                        goals.confirm_goal(session,row,actor=view.owner,role='HEALTH_MANAGER',title=edited,goal_type=selected,target=numeric,target_date=target_date)
                        session.commit()
                    st.rerun()
                except (ValueError,PermissionError) as exc:st.error(str(exc))
        else:
            st.subheader('当前健康管理目标')
            st.write(title);readiness(patient.id,kind)
            if not state['baseline']:
                st.info('目标已确认。下一步：建立并确认年度健康基线。')
                if st.button('确认年度基线',type='primary',key='goal-baseline-next'):
                    st.session_state[f'archive-content-{patient.id}']='基线'
                    app.request_navigation(surface='运营后台',ops_page='成员',member_id=patient.id,member_section='健康')
            else:
                st.subheader('确认管理计划')
                for i,phase in enumerate(plan.get('phases',[]),1):st.write(f"阶段 {i}：{phase['title']} · {phase['start']}—{phase['end']}")
                st.caption('核心监测：'+' / '.join(goal_metrics.METRIC_LABELS.get(code,code) for code in plan.get('monitoring',[])))
                st.caption(plan.get('frequency',''))
                if st.button('确认这项管理计划',type='primary',key='goal-plan-confirm'):
                    try:
                        with SessionLocal() as session:
                            goals.confirm_plan(session,session.get(ManagementGoal,identity),actor=view.owner,role='HEALTH_MANAGER')
                            session.commit()
                        st.rerun()
                    except (ValueError,PermissionError) as exc:st.error(str(exc))
    with rail,st.container(key='v7-context-management'):
        st.subheader('下一步')
        st.write('完成初评资料' if not state['intake'] else '确认当前管理目标' if not confirmed else '确认年度基线' if not state['baseline'] else '确认计划后开始阶段管理')
        st.caption('责任健管：'+view.owner)
    return True


def readiness(member_id,kind):
    with SessionLocal() as session:data=goal_metrics.completeness(session,member_id,kind)
    st.markdown('**目标数据准备情况**')
    st.caption(f"核心指标：{data['CORE']['available']} / {data['CORE']['total']}　辅助指标：{data['SUPPORTING']['available']} / {data['SUPPORTING']['total']}")
    if data['CORE']['missing']:st.write('当前需补充：'+'、'.join(goal_metrics.METRIC_LABELS.get(c,c) for c in data['CORE']['missing']))
    if data['SUPPORTING']['missing']:st.caption('建议下次随访补充：'+'、'.join(goal_metrics.METRIC_LABELS.get(c,c) for c in data['SUPPORTING']['missing']))
    return data


def goal_status(member_id,program_id,*,compact=False):
    with SessionLocal() as session:
        goal=goals.current(session,program_id)
        if not goal or not goal.confirmed_at:return
        data=goal_metrics.completeness(session,member_id,goal.goal_type,configured=goal.requirements_json)
        value=data['latest'].get(goal.metric_code,{}).get('value')
        status=goal_metrics.progress(goal,value)
        st.subheader('当前健康管理目标')
        st.write(goal.title)
        st.caption(f'{goal.start_date}—{goal.target_date} · 责任健管：{goal.owner_id}')
        if status['percent'] is not None:
            st.caption(f"基线 {goal.baseline_value} → 当前 {status['current']} {goal.target_unit} · 进度 {status['percent']}% · 剩余 {status['remaining']} {goal.target_unit}")
        else:st.caption(status['status'])
        if not compact:
            readiness(member_id,goal.goal_type)
            if data['suggestions']:
                with st.expander('补充数据建议'):
                    suggestion=data['suggestions'][0];st.write(suggestion['text'])
                    if st.button('加入下次随访',key='goal-data-followup'):
                        from executive_health_ai.services.management_workflow import task
                        from executive_health_ai.models.base import utc_now
                        from datetime import timedelta
                        task(session,member_id,goal.program_id,suggestion['text'],suggestion['text'],goal.owner_id,
                            utc_now()+timedelta(days=7),'goal-data:'+str(goal.id)+':'+suggestion['metric'])
                        session.commit();st.success('已确认并加入随访。')


def summary(member_id):
    with SessionLocal() as session:
        row=session.scalar(select(DailyHealthSummary).where(DailyHealthSummary.patient_id==member_id)
            .order_by(DailyHealthSummary.summary_date.desc()).limit(1))
        if not row:return
        st.markdown('**最近健康摘要 · '+str(row.summary_date)+'**')
        if row.change_status=='INSUFFICIENT_DATA':
            st.caption('来源或质量修正后暂无可用数据，等待新的有效记录。')
            return
        parts=[]
        for code in ('weight','steps','sleep_duration','resting_heart_rate','systolic_bp','diastolic_bp'):
            if code in row.metrics:
                item=row.metrics[code];parts.append(goal_metrics.METRIC_LABELS[code]+' '+item['value']+' '+item['unit'])
        st.caption(' · '.join(parts))
        if row.changes:
            for change in row.changes[:2]:st.write(change['reason'])
        else:st.caption('未检测到达到已配置规则的有意义变化。')
        if row.completeness.get('percent') is not None:st.caption('目标核心数据完整度：'+str(row.completeness['percent'])+'%')


def provenance(member_id):
    with st.expander('来源详情'):
        with SessionLocal() as session:
            rows=list(session.scalars(goal_metrics.usable(select(Observation).where(Observation.patient_id==member_id))
                .order_by(Observation.observed_at.desc()).limit(12)))
            # Keep governed report/correction evidence reachable even after months
            # of device readings; reuse this source picker, with bounded reads.
            governed=list(session.scalars(goal_metrics.usable(select(Observation).where(
                Observation.patient_id==member_id,
                or_(Observation.source_type=='REPORT',Observation.supersedes_id.is_not(None))))
                .order_by(Observation.observed_at.desc()).limit(12)))
            seen={r.id for r in rows}
            rows.extend(r for r in governed if r.id not in seen)
            if not rows:st.caption('暂无可追溯的正式指标。');return
            row=st.selectbox('健康记录',rows,format_func=lambda r:f'{goal_metrics.METRIC_LABELS.get(r.metric_code,r.metric_code)} {r.value_numeric} {r.unit} · {r.observed_at:%Y-%m-%d}',key='provenance-observation')
            from executive_health_ai.services.data_provenance import detail
            info=detail(session,row)
            st.caption('已确认' if row.confirmation_status=='CONFIRMED' else '已通过数据规则')
            st.write('来源：'+('体检报告' if row.source_type=='REPORT' else '手机 / 设备' if row.source_type in {'MOBILE','DEVICE'} else row.source))
            if info['corrected']:st.caption('已修正')
            if st.checkbox('查看原始记录',key='provenance-original'):
                raw=info['raw'] or {}
                st.write(raw.get('original_text') or str(raw.get('original_value',raw.get('value','历史记录未保存原文'))))
                for candidate in info['candidates']:st.caption('曾整理为：'+str(candidate.get('normalized_value'))+' '+str(candidate.get('unit') or ''))


def communication(patient,view):
    from executive_health_ai.services import communications
    key=f'communication-draft-{patient.id}'
    st.subheader('记录本次沟通')
    if identity:=st.session_state.get(key):
        with SessionLocal() as session:
            row=session.get(CommunicationRecord,UUID(identity))
            st.write(row.raw_note);st.caption(row.structured_summary['medical_statement_status'])
            if row.structured_summary.get('monitoring'):st.write('后续：'+row.structured_summary['monitoring'])
            if row.structured_summary.get('followup_at'):
                from datetime import datetime
                from executive_health_ai.ui import experience as ux
                st.caption('跟进时间：'+ux.when(datetime.fromisoformat(row.structured_summary['followup_at'])))
            if st.button('确认记录与后续安排',type='primary'):
                communications.confirm(session,row,actor=view.owner,role='HEALTH_MANAGER');session.commit()
                st.session_state.pop(key,None);st.success('沟通原文与后续安排已保存。');st.rerun()
        return
    with st.form('communication-natural-note'):
        note=st.text_area('本次发生了什么，下一步怎么做',placeholder='电话、微信、现场沟通或医生讨论均可直接记录原话。')
        with st.expander('来源（有正式医生意见时关联）'):
            review=st.selectbox('已确认医生意见',[None]+[r for r in view.doctor_reviews if r.status=='CONFIRMED'],format_func=lambda r:r.doctor_name+' · '+r.opinion[:40] if r else '健管沟通记录')
        submitted=st.form_submit_button('整理本次记录',type='primary')
    if submitted:
        try:
            with SessionLocal() as session:
                row=communications.record(session,member_id=patient.id,program_id=view.program.id,raw_note=note,
                    actor=view.owner,role='HEALTH_MANAGER',source='DOCTOR' if review else 'MANAGER',
                    doctor_review_id=review.id if review else None,request_key=str(uuid4()))
                session.commit();st.session_state[key]=str(row.id)
            st.rerun()
        except (ValueError,PermissionError) as exc:st.error(str(exc))
