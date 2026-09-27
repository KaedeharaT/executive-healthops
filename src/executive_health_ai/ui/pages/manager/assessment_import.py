"""Source review alongside the existing eleven-step assessment."""
from pathlib import Path
import pandas as pd
import streamlit as st
from executive_health_ai.database import SessionLocal
from executive_health_ai.services.assessment_import import AssessmentImportService
from executive_health_ai.agent.supervisor import HealthOpsAgentSupervisor

service=AssessmentImportService()


def uploader(patient,row,actor,key):
    st.caption('支持多份 PDF、Word（DOCX）、Excel（XLSX）、CSV、文本、问卷 JSON 和图片。扫描件或无法可靠识别的内容需人工补充。每批最多 20 份、100 MB。')
    files=st.file_uploader('上传任意健康资料',type=['pdf','docx','xlsx','csv','txt','json','png','jpg','jpeg'],accept_multiple_files=True,key=key)
    if st.button('逐份解析并预填初评',type='primary',disabled=not files,key=key+'-submit'):
        try:
            with SessionLocal() as session:
                results=service.upload_batch(session,patient.id,row.id,[(f.name,f.getvalue()) for f in files],actor=actor)
                session.commit()
            st.session_state['intake-upload-results']=results
            st.rerun()
        except (ValueError,PermissionError) as exc:st.error(str(exc))
    for result in st.session_state.pop('intake-upload-results',[]):
        if result['error']:st.error(result['filename']+'：'+result['error'])
        else:st.success(result['filename']+('：已在本次评估中，无需重复上传' if result['duplicate'] else '：已接收'))


def panel(patient,row,actor):
    with st.container(border=True,key='soft-assessment-documents'):
        st.subheader('从健康资料开始初评')
        st.write('逐份读取 → 带来源的事实 → 去重与冲突核对 → 预填 11 步评估')
        uploader(patient,row,actor,'assessment-files-'+str(row.id))
        with SessionLocal() as session:view=service.project(session,patient.id,row.id)
        if not view['goals']:return view
        @st.fragment(run_every=2 if view['processing'] else None)
        def progress():
            with SessionLocal() as session:
                current=service.project(session,patient.id,row.id)
                st.dataframe(pd.DataFrame([{'文件':f['document'].title,'状态':{'RUNNING':'正在逐份整理','PROCESSING':'正在读取','WAITING_MANAGER':'待健管核对','ESCALATED':'需人工处理','COMPLETED':'初评已提交','CANCELLED':'人工接手'}.get(f['goal'].status,f['goal'].status),
                    '识别内容':' / '.join(f['run'].metadata_json.get('detected_contents',[])) or '待核对','候选数量':f['count']} for f in current['files']]),hide_index=True,width='stretch')
                pending=next((g for g in current['goals'] if g.status=='RUNNING'),None)
                if pending:
                    HealthOpsAgentSupervisor().execute_next_step(session,pending.id);session.commit()
            if view['processing'] and not service_processing(patient,row):st.rerun()
        progress()
        st.dataframe(pd.DataFrame([{'步骤':str(i+1)+'. '+s['step'],'状态':s['status']} for i,s in enumerate(view['steps'])]+[{'步骤':'11. 确认提交','状态':'待逐项核对'}]),hide_index=True,width='stretch')
        st.caption('已填写：已保存并核对来源；待确认：已有候选或草稿；资料缺失：尚无可用填写；存在冲突：原文之间或与现有资料不同。没有提到不等于没有病史。')
        for f in view['files']:
            goal=f['goal'];path=Path(f['document'].storage_reference)
            if path.is_file():st.download_button('查看原文件 · '+f['document'].title,path.read_bytes(),file_name=f['document'].title,key='intake-source-'+str(goal.id))
            if f['needs_check']:
                st.warning(f['document'].title+'：'+('；'.join(f['warnings']) or '有未映射的测量/报告内容，或本次读取未成功，请核对原文件。'))
                if f['checked']:st.success('已记录人工核对结果')
                else:
                    note=st.text_input('人工核对与补充处理记录',key='file-note-'+str(goal.id))
                    if st.button('记录人工处理',key='file-check-'+str(goal.id),disabled=not note.strip()):
                        with SessionLocal() as session:
                            service.acknowledge_file(session,patient.id,row.id,goal.id,actor,note);session.commit()
                        st.rerun()
        if view['other']:
            st.write('未直接映射到初评字段的报告内容（保留来源，不自动形成医学结论）')
            st.dataframe(pd.DataFrame([{'内容':r.summary or r.raw_value,'原文':r.evidence_text,'来源页':r.source_page} for r in view['other']]),hide_index=True,width='stretch')
        return view


def service_processing(patient,row):
    with SessionLocal() as session:return service.project(session,patient.id,row.id)['processing']


def evidence(view,step):
    item=next(s for s in view['steps'] if s['step']==step)
    st.markdown('**本步骤资料核对 · '+item['status']+'**')
    records=[]
    for group in item['groups']:
        for candidate in group['rows']:
            data=candidate.structured_data_json
            records.append({'字段':group['field'],'资料内容':data['value'],'现有填写':group['current'],
                '状态':'存在冲突' if group['conflict'] else '待核对' if not group['safe'] else '可预填',
                '文件':data['source_filename'],'位置':data['source_locator'],'原文':candidate.evidence_text})
    if records:st.dataframe(pd.DataFrame(records),hide_index=True,width='stretch')
    else:st.caption('资料未提供本步骤可用字段，请人工填写；未知内容保持未知。')
    return item
