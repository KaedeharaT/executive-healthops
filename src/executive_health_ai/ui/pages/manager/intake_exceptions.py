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
        st.subheader('初始健康评估准备度')
        counts=saved.get('completion',data['counts']) if data['submitted'] else data['counts']
        c.summary_strip([('已确认',counts['filled'] if data['submitted'] else counts['confirmed']),('自动预填',counts['auto_filled']),
            ('待确认',counts['pending']),('缺失',counts['missing']),('冲突',counts['conflicts'])])
        st.caption('仅表示资料填写情况，不是健康评分。未提供的资料保持未知，不自动填写“无”。')
        if data['submitted']:
            st.success('初始健康评估资料已提交')
            st.write(f'资料来源：{counts["sources"]} 份 · 自动整理：{counts["auto_filled"]} 项 · 人工补充：{counts["manual_fields"]} 项')
            st.caption('后续健管专业确认及医生核对继续按原流程办理。')
            return
        st.subheader('需要你处理')
        if data['processing']:
            st.write('暂未轮到你。资料整理完成后，待确认、冲突和必需补充项会集中显示在这里。')
            return
        if data['medical']:st.info('存在需要医生判断的事项，请完成原有医生确认流程后提交。')
        queue=data['queue']
        if queue:
            labels={'CONFIRM':'待确认','CONFLICT':'存在冲突','MISSING':'资料缺失','FILE':'原文件 / 测量核对'}
            st.write(f'待确认 {counts["pending"]} 项 · 冲突 {counts["conflicts"]} 项 · 必需补充 {counts["required_missing"]} 项')
            key=f'exception-open-{row.id}'
            if not st.session_state.get(key):
                if st.button(f'处理剩余 {len(queue)} 项',type='primary',key=key+'-start'):
                    st.session_state[key]=True;st.rerun()
                return
            item=queue[0]
            st.caption(f'当前第 1 项 / 剩余 {len(queue)} 项 · 处理后自动进入下一项')
            st.markdown('**'+item['section']+' · '+item['label']+'**')
            st.write(labels[item['kind']])
            prefix='exception-'+item['key']
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
                for source in item['sources']:
                    meta=source.structured_data_json
                    st.write('《'+meta.get('source_filename','上传资料')+'》：'+meta['value'])
                    st.caption('依据：'+business_evidence(source))
                    st.caption(meta.get('source_date','')+' · '+location(meta.get('source_locator','')))
                if item['current']:st.write('已有回答：'+item['current'])
                if item['dated']:st.info('按资料日期建议当前采用：'+item['value']+'。请核对是否反映会员当前情况。')
                elif item['value']:st.write('拟采用：'+item['value'])
                if st.button('采用并处理下一项' if item['kind']=='CONFLICT' else '确认并处理下一项',key=prefix+'-confirm',type='primary',disabled=not item['value'] or not item['evidence_ok']):
                    apply(row.id,item,'CONFIRM',view.owner)
                with st.expander('修改 / 忽略 / 暂不确认'):
                    with st.form(prefix+'-edit'):
                        answer=st.text_input('修改为',value=item['value'])
                        note=st.text_input('修改或忽略原因')
                        if st.form_submit_button('保存修改并处理下一项'):apply(row.id,item,'MODIFY',view.owner,value=answer,note=note)
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
            st.success('初始健康评估已准备完成')
            st.write(f'资料来源：{counts["sources"]} 份 · 自动整理：{counts["auto_filled"]} 项 · 人工补充：{counts["manual_fields"]} 项')
            unknown=True
            if data['missing']:
                with st.expander(f'仍未知的可选资料 {len(data["missing"])} 项'):
                    st.write('、'.join(m['section']+' / '+m['label'] for m in data['missing']))
                    st.caption('可在下方原有资料卡片中补充；未知不等于否认或没有。')
                unknown=st.checkbox('这些可选资料尚未提供，继续保留未知',key=f'unknown-{row.id}')
            checked=st.checkbox('我已核对来源及整理结果，确认提交初评资料',key=f'confirm-exceptions-{row.id}')
            if st.button('确认并完成初始健康评估',type='primary',disabled=not checked or not unknown or data['medical']):
                try:
                    with SessionLocal() as session:
                        service.complete(session,session.get(IntakeAssessment,row.id),view.owner,retain_unknown=unknown)
                        session.commit()
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
