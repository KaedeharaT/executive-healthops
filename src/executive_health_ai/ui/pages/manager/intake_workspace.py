"""The foreground view of existing intake Agents, shared by archive and wizard."""
from html import escape
from datetime import timezone
import streamlit as st
from executive_health_ai.database import SessionLocal
from executive_health_ai.services import intake_workspace as projection
from executive_health_ai.ui import components as c
from executive_health_ai.ui.experience import business_text


def continue_intake(patient,view,step=None):
    from executive_health_ai.ui.pages.manager import intake_entry
    with SessionLocal() as session:
        step=step or projection.first_incomplete(session,patient.id,view.intake)
    intake_entry.open_intake(patient,view,step=step,read_only=bool(view.intake and view.intake.status=='CONFIRMED'))


def support(data, event=None):
    st.markdown('**资料整理依据**')
    activities=[a for f in data['files'] for a in f['support']]
    cols=st.columns(3)
    for col,key,title in zip(cols,('mapping','semantic','knowledge'),('文件读取','内容整理','术语核对')):
        rows=[a for a in activities if a.key==key]
        with col:
            st.markdown('**'+title+'**')
            if key=='semantic':
                from executive_health_ai.ui.agent_progress import ai_timing
                for f in data['files']:ai_timing(f.get('progress'))
            if key=='semantic' and (event=='AI_REQUEST_STARTED' or any(f.get('progress') and f['progress'].ai_running for f in data['files'])):
                st.write('● 正在进行')
                st.caption('正在整理资料中的健康信息，并保留原文依据。')
            elif any(a.used for a in rows):
                if key=='semantic' and any(a.used and a.status=='SUCCESS' for a in rows):st.caption('✓ 资料整理完成')
                for result in dict.fromkeys(a.mark+' '+a.label+' · '+a.result for a in rows if a.used):
                    st.caption(business_text(result.replace('仍需健管确认。','已纳入本次初评确认。') if data['finished'] else result))
            elif key=='mapping' and rows and any(a.status=='SUCCESS' for a in rows):
                st.caption('✓ 已读取文件并归入对应资料栏')
            else:
                st.caption('本流程未使用' if key=='knowledge' else '本次未使用' if key!='mapping' else '尚未执行')
            if key=='semantic' and event!='AI_REQUEST_STARTED':st.caption('用途：从自由文本资料中提取可核对的健康信息')
            if key=='knowledge':st.caption('会员事实只来自上传资料、已有档案与会员回答。')


def execution_mark(data,event=None):
    """Only a running goal or the actual request callback can animate."""
    if data.get('progress') and not data['progress'].running:
        return '✓ ' if data['finished'] else '! ' if data['progress'].status in {'FAILED','ESCALATED','CANCELLED'} else '● '
    if event in {'AI_UNAVAILABLE','AI_REQUEST_TIMEOUT','AI_REQUEST_FAILED'}:return '! '
    if event=='AI_RESULT_CHECKED':return '✓ '
    if event=='AI_REQUEST_STARTED' or (data['current'] and data['current']['goal'].status in {'RUNNING','PROCESSING'}):
        return '<span class="intake-spinner" aria-label="正在执行"></span>'
    if any(f['goal'].status in {'ESCALATED','CANCELLED'} for f in data['files']):return '! '
    return '✓ ' if data['finished'] else '● '


def draw(data,event=None,*,assessment_summary=True):
    from executive_health_ai.ui.agent_progress import AgentProgressPanel
    failed=any(f['goal'].status in {'FAILED','ESCALATED','CANCELLED'} for f in data['files'])
    title='系统助手正在整理资料' if data['processing'] else '资料整理进度'
    st.subheader(title)
    if not data['files']:
        c.summary_strip([('资料完成度',str(data['stats'].get('percent',0))+'%'),
                         ('需要确认',data['stats'].get('pending',0)),('存在冲突',data['stats'].get('conflicts',0))])
        st.write('当前：暂无正在处理的健康资料')
        st.caption('上传资料后，自动整理有依据的信息，再处理少量例外。')
        return
    p=data.get('progress')
    exceptions=data.get('exceptions') or {}
    counts=exceptions.get('counts',{})
    if data.get('finished') and data.get('imported'):
        from executive_health_ai.services.intake_exceptions import state
        counts=state(data['imported']['intake']).get('completion',counts)
    next_text=(projection.PHASES[min(p.current_step,6)] if p and p.running else
        '处理剩余事项，再确认初评' if not data['finished'] else '确认管理重点，准备年度健康基线')
    c.summary_strip([('已自动整理',counts.get('auto_sources',counts.get('auto_filled',data['stats']['prefilled']))),
                     ('需要确认',counts.get('pending',data['stats'].get('pending',0))),
                     ('存在冲突',counts.get('conflicts',data['stats'].get('conflicts',0))),
                     ('资料完成度',str(data['stats'].get('percent',0))+'%')])
    AgentProgressPanel.render(p,flow_name='健康资料整理',next_action=next_text)
    if not data['processing'] and not p:
        st.write(f'✓ 已接收 {len(data["files"])} 份资料 · 已读取 {sum(f["run"].status=="COMPLETED" for f in data["files"])} 份')
        if failed:st.warning('部分资料未能完整整理，请核对原文件或重试。')
        st.write('✓ 已整理有来源依据的健康信息' if data['count'] else '尚无可用的整理结果')
        st.write(f'✓ 已自动整理 {counts.get("auto_sources",counts.get("auto_filled",data["stats"]["prefilled"]))} 项')
        remaining=counts.get('exceptions',0)
        st.write(f'● 等待处理 {remaining} 项必要例外' if remaining else '✓ 必要资料已准备完成' if not data['finished'] else '✓ 本次资料整理完成')
        st.caption('下一步：'+next_text)
    with st.expander('处理记录与来源',expanded=False):
        support(data,event)
        st.caption('健康档案更新：'+str(data['updates'])+' 项；正式医疗事实继续遵守现有确认规则。')
        for at,name,text in data['events']:
            at=(at.replace(tzinfo=timezone.utc) if at.tzinfo is None else at).astimezone()
            st.caption(at.strftime('%H:%M')+' · 《'+name+'》'+business_text(text))


def workspace(app,patient,view, *, uploader=True, show_actions=True):
    selected=st.session_state.get(f'intake-workspace-goal-{patient.id}')
    with SessionLocal() as session:data=projection.project(session,patient.id,view.intake,selected)
    from executive_health_ai.services.intake_exceptions import state as exception_state
    exception_mode=bool(view.intake and exception_state(view.intake).get('enabled'))
    assessment_summary=not (show_actions and exception_mode)
    @st.fragment(run_every=2 if data['processing'] else None)
    def live():
        with SessionLocal() as session:current=projection.project(session,patient.id,view.intake,selected)
        with st.container(key='intake-agent-board'):
            board=st.empty()
        with board.container():draw(current,assessment_summary=assessment_summary)
        if current['current'] and current['current']['goal'].status in {'RUNNING','PROCESSING'}:
            from executive_health_ai.ui.intake_execution import submit
            submit(current['current']['goal'].id)
        if data['processing'] and not current['processing']:st.rerun()
    queue_open=bool(view.intake and st.session_state.get(f'exception-open-{view.intake.id}')) and not data['processing']
    if exception_mode and show_actions:
        if queue_open:
            exception_column,board_column=st.columns([2.6,1],gap='large')
            with board_column,st.container(key='v7-context-intake-progress'):
                draw(data,assessment_summary=False)
        else:
            board_column,exception_column=st.columns([2.6,1],gap='large')
            with board_column:live()
    else:live()
    if not show_actions:return data
    failed=[f for f in data['files'] if f['goal'].status=='ESCALATED' and f['goal'].context_json.get('intake_id')]
    for f in failed:
        with st.container(border=True):
            st.warning(f['document'].title+'：'+f['goal'].next_action)
            from pathlib import Path
            path=Path(f['document'].storage_reference)
            if path.is_file():st.download_button('查看原文件',path.read_bytes(),file_name=f['document'].title,key='progress-original-'+str(f['goal'].id))
            if st.button('重新尝试',key='progress-retry-'+str(f['goal'].id)):
                from executive_health_ai.agent.profile_intake import retry
                from executive_health_ai.models import AgentGoal
                try:
                    with SessionLocal() as session:
                        retry(session,session.get(AgentGoal,f['goal'].id),actor=view.owner,role='HEALTH_MANAGER');session.commit()
                    st.rerun()
                except ValueError as error:st.error(str(error))
            st.button('转人工处理',key='progress-manual-'+str(f['goal'].id),on_click=continue_intake,args=(patient,view))
    if exception_mode:
        from executive_health_ai.ui.pages.manager.intake_exceptions import panel
        if not queue_open:
            with exception_column,st.container(key='v7-context-intake'):panel(patient,view)
        else:
            with exception_column:panel(patient,view)
    # Preserve the established confirmation workflow for uploads after submission.
    from executive_health_ai.ui.pages.manager.profile_intake import review_updates
    review_files=[item for item in data['files'] if not item['goal'].context_json.get('intake_id') and item['goal'].status not in {'RUNNING','PROCESSING'}]
    if review_files:
        with st.expander('核对健康档案更新',expanded=any(item['goal'].status=='WAITING_MANAGER' for item in review_files)):
            index=st.selectbox('待核对资料',range(len(review_files)),format_func=lambda i:review_files[i]['document'].title) if len(review_files)>1 else 0
            with SessionLocal() as session:
                from executive_health_ai.models import AgentGoal
                review_updates(app,session,session.get(AgentGoal,review_files[index]['goal'].id))
    if uploader:
        if data["files"]:
            with st.expander("上传健康资料",expanded=data["processing"]):upload_area(patient,view)
        else:upload_area(patient,view)
    return data


def upload_area(patient,view):
    key=f'workspace-upload-{patient.id}'
    with st.container(border=True,key='intake-upload-area'):
        st.subheader('上传健康资料',anchor='intake-upload')
        st.caption('体检、问卷、病历和用药记录都可在这里上传。助手会整理到对应档案，您只需处理缺失或有疑问的内容。')
        epoch=st.session_state.get(key+'-epoch',0)
        files=st.file_uploader('选择文件',type=['pdf','docx','xlsx','csv','txt','json','png','jpg','jpeg'],accept_multiple_files=True,key=key+'-'+str(epoch))
        st.caption('PDF / DOCX / XLSX / CSV / TXT / JSON / PNG / JPG · 每批最多 20 份、100 MB')
        if st.button('上传并整理资料',key=key+'-submit',disabled=not files):
            try:
                with SessionLocal() as session:
                    results=projection.upload(session,patient,view,[(f.name,f.getvalue()) for f in files]);session.commit()
                st.session_state[key+'-results']=results
                st.session_state.pop(f'intake-workspace-goal-{patient.id}',None)
                if any(not result['error'] for result in results):st.session_state[key+'-epoch']=epoch+1
                st.rerun()
            except (ValueError,PermissionError) as error:st.error(str(error))
        for result in st.session_state.pop(key+'-results',[]):
            if result['error']:st.error(result['filename']+'：'+result['error'])
            else:st.caption(result['filename']+('：已接收，无需重复上传' if result['duplicate'] else '：已接收'))


def cards(patient,view,data):
    st.subheader('初始健康评估')
    s=data['stats']
    st.caption(f'资料完成度：{s["percent"]}% · 点击分类查看或修正；不是健康评分。')
    with st.container(key='intake-section-cards'):
        for start in range(0,10,4):
            for col,item in zip(st.columns(4),data['sections'][start:start+4]):
                description=f'{item["prefilled"]} 项已预填 · {item["pending"]} 项待确认' if item['prefilled'] or item['pending'] else '点击查看与补充'
                if 'exceptions' in item:
                    description=f'{item["exceptions"]} 项例外 · 点击查看与修正' if item['exceptions'] else '已整理 · 可随初评一次确认' if item['status']!='已完成' else '已确认 · 点击查看'
                col.button(item['label']+'\n'+item['status']+'\n'+description,key=f'intake-category-{patient.id}-{start+data["sections"][start:start+4].index(item)}',
                    width='stretch',on_click=continue_intake,args=(patient,view,item['step']))
    from executive_health_ai.ui.pages.manager import intake_entry
    state=intake_entry.state(view.intake)
    label='确认并提交初始健康评估' if s['percent']==100 and view.intake and view.intake.status=='DRAFT' else '继续完成初始评估' if state in {'未开始','填写中'} else '开始健管确认' if state=='待健管确认' else '查看评估'
    from executive_health_ai.services.intake_exceptions import state as exception_state
    exception_mode=bool(view.intake and exception_state(view.intake).get('enabled'))
    formal_review=any(not f['goal'].context_json.get('intake_id') and f['goal'].status=='WAITING_MANAGER' for f in data.get('files',[]))
    st.button('完整查看 / 手工修正（11步）' if exception_mode else label,key=f'workspace-primary-{patient.id}',type='secondary' if exception_mode or formal_review else 'primary',on_click=continue_intake,args=(patient,view))
    if view.intake:
        if state!='已完成':
            st.button('查看已填写内容',key=f'workspace-preview-{patient.id}',on_click=intake_entry.open_intake,args=(patient,view),kwargs={'read_only':True})
        if state=='已完成':st.button('补充/修正',key=f'workspace-amend-{patient.id}',on_click=intake_entry.amend,args=(patient,view))
