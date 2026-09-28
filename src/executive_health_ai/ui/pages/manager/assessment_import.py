"""Source review alongside the existing eleven-step assessment."""
from pathlib import Path
import re
import pandas as pd
import streamlit as st
from executive_health_ai.database import SessionLocal
from executive_health_ai.services.assessment_import import AssessmentImportService
from executive_health_ai.services.profile_ingestion import business_evidence

service=AssessmentImportService()


def panel(patient,row,actor):
    # The single foreground workspace owns upload and execution. This panel only
    # retains existing source review / manual handling before submission.
    with st.expander('资料来源与待核对内容', expanded=False):
        with SessionLocal() as session:view=service.project(session,patient.id,row.id)
        if not view['goals']:return view
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


def evidence(view,step):
    item=next(s for s in view['steps'] if s['step']==step)
    st.markdown('**本步骤资料核对 · '+item['status']+'**')
    records=[]
    for group in item['groups']:
        for candidate in group['rows']:
            data=candidate.structured_data_json
            location=data['source_locator']
            native=re.fullmatch(r'responses\.(.+)\[(\d+)\]',location)
            if native:location=native[1]+' · 第 '+native[2]+' 条'
            records.append({'字段':group['field'],'资料内容':data['value'],'现有填写':group['current'],
                '状态':'存在冲突' if group['conflict'] else '待核对' if not group['safe'] else '可预填',
                '文件':data['source_filename'],'位置':location,'原文':business_evidence(candidate)})
    if records:st.dataframe(pd.DataFrame(records),hide_index=True,width='stretch')
    else:st.caption('资料未提供本步骤可用字段，请人工填写；未知内容保持未知。')
    return item
