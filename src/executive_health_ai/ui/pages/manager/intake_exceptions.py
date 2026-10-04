"""A short review queue, using the established draft and submission services."""
import streamlit as st
from executive_health_ai.database import SessionLocal
from executive_health_ai.models.management_workflow import IntakeAssessment
from executive_health_ai.services import intake_exceptions as service
from executive_health_ai.services.profile_ingestion import business_evidence
from executive_health_ai.ui import components as c


def panel(patient, view):
    with SessionLocal() as session:
        row=session.get(IntakeAssessment,view.intake.id)
        data=service.project(session,row)
        saved=service.state(row)
    with st.container(key='intake-exception-workspace',border=True):
        opened=st.session_state.get(f'exception-open-{row.id}',False)
        counts=saved.get('completion',data['counts']) if data['submitted'] else data['counts']
        if not opened or data['submitted']:
            st.subheader('还需要您做什么')
            st.write(f'需要确认 {counts["pending"]} 项 · 冲突 {counts["conflicts"]} 项 · 必须补充 {counts["required_missing"]} 项')
            st.caption(f'可暂缺 {counts.get("optional_missing",counts["missing"])} 项 · 不阻塞提交；未提供不等于“无”。')
        if data['submitted']:
            st.success('初始健康评估已完成资料确认')
            if row.status=='SUBMITTED':
                from executive_health_ai.ui.pages.manager import intake_entry
                st.button('继续健管确认',type='primary',key=f'intake-professional-{row.id}',
                    on_click=intake_entry.open_intake,args=(patient,view))
            st.write(f'资料来源：{counts["sources"]} 份 · 自动整理：{counts.get("auto_sources",counts["auto_filled"])} 项 · 人工补充：{counts["manual_fields"]} 项')
            st.caption('资料已确认。下一步：确认管理重点，准备年度健康基线。')
            return
        if data['processing']:
            st.write('正在整理，暂时无需操作。有疑问或必须补充的内容会集中显示在这里。')
            return
        if data['medical']:st.info('存在需要医生判断的事项，请完成原有医生确认流程后提交。')
        queue=data['queue']
        if queue:
            labels={'CONFIRM':'待确认','CONFLICT':'存在冲突','MISSING':'必须补充','FILE':'原文件 / 测量核对','DOCTOR':'需要医生判断'}
            st.subheader(f'需要你处理 {len(queue)} 项')
            key=f'exception-open-{row.id}'
            if not st.session_state.get(key):
                for missing in [q for q in queue if q['kind']=='MISSING'][:3]:
                    if st.button('待补充：'+missing['label'],key=key+'-missing-'+missing['key'],width='stretch'):
                        st.session_state[key]=True
                        st.session_state[key+'-selected']=missing['key'];st.rerun()
                if st.button(f'处理剩余事项（{len(queue)}项）',type='primary',key=key+'-start'):
                    st.session_state[key]=True;st.rerun()
                return
            item=next((q for q in queue if q['key']==st.session_state.get(key+'-selected')),queue[0])
            done=counts['processed'];total=done+len(queue)
            st.progress(done/total,text=f'已完成 {done} / {total} 项')
            st.caption(f'当前 {done+1} / {total} · 保存后自动进入下一项')
            st.markdown('**'+item['section']+' · '+item['label']+'**')
            st.write(labels[item['kind']])
            prefix='exception-'+item['key']
            if item['kind']=='DOCTOR':
                st.info('此项需要医生判断，现有医生协同流程返回后自动继续。')
                return
            if item['kind']=='FILE':
                file=item['file']
                for warning in file['warnings']:st.warning(warning)
                with SessionLocal() as session:
                    from executive_health_ai.models import AgentGoal
                    from executive_health_ai.services.profile_ingestion import candidates,ProfileIngestionService
                    goal=session.get(AgentGoal,file['goal'].id)
                    other=[r for r in candidates(session,goal) if r.candidate_type!='PROFILE_FACT']
                    safe=[]
                    for candidate in other:
                        status,old,reason=ProfileIngestionService().classify(session,goal,candidate)
                        st.write(candidate.raw_name+'：'+str(candidate.raw_value or candidate.summary or '')+' '+str(candidate.unit or ''))
                        st.caption('依据：'+candidate.evidence_text+' · '+reason)
                        if candidate.candidate_type=='OBSERVATION' and status in {'新增','更新'} and candidate.status in {'PENDING_REVIEW','CORRECTED'}:safe.append(candidate.id)
                    if safe and st.button('确认以上测量并同步健康档案',key=prefix+'-measure',disabled=data['medical']):
                        try:
                            service.confirm_measurements(session,session.get(IntakeAssessment,row.id),goal.id,view.owner,file['signature'])
                            session.commit();st.rerun()
                        except ValueError as error:st.error(str(error))
                note=st.text_input('未识别内容的处理说明',key=prefix+'-note',placeholder='如仍有未识别原文，请说明核对或保留待处理的情况')
                ack=st.checkbox('已核对原文件；未确认的档案候选保留待后续处理',key=prefix+'-ack')
                if st.button('完成本份资料核对',key=prefix+'-done',disabled=not ack or bool(file['warnings'] and not note.strip())):
                    apply(row.id,item,'ACKNOWLEDGE',view.owner,note=note or '已核对原始资料，未确认的档案候选保留待后续处理。')
            elif item['kind']=='MISSING':
                st.write(item['question'])
                with st.form(prefix):
                    answer=st.text_input('填写会员实际回答',placeholder='不知道时可明确填写“暂不清楚”')
                    if st.form_submit_button('保存答案并处理下一项',type='primary'):apply(row.id,item,'ANSWER',view.owner,value=answer)
            else:
                identity=''
                if item.get('ambiguous'):
                    st.info('原文未明确关联到哪项记录，请核对归属后确认。')
                    identity=st.text_input('所属记录名称',key=prefix+'-identity')
                for source in item['sources']:
                    meta=source.structured_data_json
                    st.write('《'+meta.get('source_filename','上传资料')+'》：'+meta['value'])
                    st.caption('依据：'+business_evidence(source))
                    st.caption(meta.get('source_date','')+' · '+location(meta.get('source_locator','')))
                if item['current']:st.write('已有回答：'+item['current'])
                if item['dated']:st.info('按资料日期建议当前采用：'+item['value']+'。请核对是否反映会员当前情况。')
                elif item['value']:st.write('拟采用：'+item['value'])
                if st.button('采用并处理下一项' if item['kind']=='CONFLICT' else '确认并处理下一项',key=prefix+'-confirm',type='primary',disabled=not item['value'] or not item['evidence_ok'] or bool(item.get('ambiguous') and not identity.strip())):
                    apply(row.id,item,'CONFIRM',view.owner,identity=identity)
                with st.expander('修改 / 忽略 / 暂不确认'):
                    with st.form(prefix+'-edit'):
                        answer=st.text_input('修改为',value=item['value'])
                        note=st.text_input('修改或忽略原因')
                        if st.form_submit_button('保存修改并处理下一项'):apply(row.id,item,'MODIFY',view.owner,value=answer,note=note,identity=identity)
                        if st.form_submit_button('忽略本条候选'):apply(row.id,item,'IGNORE',view.owner,note=note)
                    st.caption('暂不确认可直接离开，当前事项会继续保留。')
            waiting=[f for f in data['view']['files'] if f['goal'].status=='WAITING_MANAGER' and not f['goal'].context_json.get('review_id')]
            if waiting:
                with st.expander('需要医生判断'):
                    index=st.selectbox('相关资料',range(len(waiting)),format_func=lambda i:waiting[i]['document'].title,key=prefix+'-doctor-source')
                    question=st.text_input('请医生确认的问题',key=prefix+'-doctor-question')
                    if st.button('提交现有医生确认流程',key=prefix+'-doctor',disabled=not question.strip()):
                        from executive_health_ai.agent.profile_intake import request_doctor
                        from executive_health_ai.models import AgentGoal
                        try:
                            with SessionLocal() as session:
                                request_doctor(session,session.get(AgentGoal,waiting[index]['goal'].id),question=question,actor=view.owner,role='HEALTH_MANAGER')
                                session.commit()
                            st.rerun()
                        except (ValueError,PermissionError) as error:st.error(str(error))
        else:
            st.success('所有必要资料已处理')
            st.write(f'人工确认 {counts.get("human_confirmed",0)} 项 · 冲突处理 {counts.get("conflicts_resolved",0)} 项 · 人工补充 {counts["manual_fields"]} 项')
            st.write(f'资料来源：{counts["sources"]} 份 · 自动整理：{counts.get("auto_sources",counts["auto_filled"])} 项 · 人工补充：{counts["manual_fields"]} 项')
            unknown=True
            if data['missing']:
                with st.expander(f'仍未知的可选资料 {len(data["missing"])} 项'):
                    st.write('、'.join(m['section']+' / '+m['label'] for m in data['missing']))
                    st.caption('可在下方原有资料卡片中补充；未知不等于否认或没有。')
                st.caption('总确认时，这些可选资料继续保留未知。')
            checked=st.checkbox('确认整理结果及已处理例外；可暂缺资料继续保持未知',key=f'confirm-exceptions-{row.id}')
            if st.button('确认完成初始健康评估',type='primary',disabled=not checked or not unknown or data['medical']):
                try:
                    with SessionLocal() as session:
                        service.complete(session,session.get(IntakeAssessment,row.id),view.owner,retain_unknown=unknown)
                        session.commit()
                    st.session_state.pop(f'exception-open-{row.id}',None)
                    st.rerun()
                except (ValueError,PermissionError) as error:st.error(str(error))
        with st.expander('查看自动整理结果与来源'):
            for group in data['view']['groups']:
                st.write(group['section']+' · '+group['field']+'：'+' / '.join(group['values']))
                for candidate in group['rows']:st.caption(candidate.structured_data_json.get('source_filename','')+' · '+business_evidence(candidate))


def location(value):
    import re
    native=re.fullmatch(r'responses\.(.+)\[(\d+)\]',value)
    return native[1]+' · 第 '+native[2]+' 条' if native else value


def apply(row_id,item,action,actor,**kwargs):
    try:
        with SessionLocal() as session:
            service.decide(session,session.get(IntakeAssessment,row_id),item['key'],action,actor,
                expected_signature=item.get('signature'),**kwargs)
            session.commit()
        st.rerun()
    except (ValueError,PermissionError) as error:st.error(str(error))
