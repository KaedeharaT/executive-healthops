"""The foreground view of existing intake Agents, shared by archive and wizard."""
from html import escape
from datetime import timezone
import streamlit as st
from executive_health_ai.database import SessionLocal
from executive_health_ai.services import intake_workspace as projection
from executive_health_ai.ui import components as c


def styles():
    st.markdown('''<style>
    .st-key-intake-agent-board {border-top:3px solid var(--blue)!important;border-radius:16px;background:var(--surface);padding:20px;box-shadow:var(--neu-shadow);}
    ol.intake-agent-steps {display:grid!important;grid-template-columns:repeat(7,minmax(0,1fr))!important;list-style:none;padding:0!important;gap:8px;margin:18px 0!important;width:100%;}
    .intake-agent-steps li {padding:12px 6px;text-align:center;border:1px solid var(--line);border-radius:12px;background:var(--neu-well);font-size:14px;}
    .intake-agent-steps b {display:block;font-size:22px;margin-bottom:6px;}
    .intake-agent-steps .current {background:var(--blue);color:white;box-shadow:var(--neu-control);font-weight:700;}
    .intake-agent-steps .done {background:#e7f3ec;color:#226548;}
    .intake-agent-current {background:#e3edf8;border-left:4px solid var(--blue);border-radius:12px;padding:16px;margin:12px 0;}
    .intake-agent-current strong {font-size:22px;display:block;margin-bottom:6px;}
    .intake-spinner {display:inline-block;width:18px;height:18px;border:2px solid #c2d9ed;border-top-color:#2875b7;border-radius:50%;animation:intake-spin 1s linear infinite;margin-right:9px;vertical-align:-2px;}
    @keyframes intake-spin {to {transform:rotate(360deg)}}
    @media(prefers-reduced-motion:reduce){.intake-spinner{animation:none;}}
    .intake-agent-history {list-style:none;padding:0;margin:8px 0;line-height:1.7;font-size:14px;}
    .st-key-intake-section-cards button {width:100%;min-height:112px;text-align:left;justify-content:flex-start;white-space:pre-line;border-radius:14px!important;cursor:pointer;transition:transform .15s,box-shadow .15s;}
    .st-key-intake-section-cards button:hover {transform:translateY(-3px);box-shadow:var(--neu-emphasis)!important;}
    .st-key-intake-section-cards button:active {transform:translateY(1px);box-shadow:var(--neu-inset)!important;}
    .st-key-intake-section-cards button:focus-visible {outline:3px solid var(--blue);outline-offset:3px;}
    @media(max-width:900px){ol.intake-agent-steps{grid-template-columns:repeat(4,minmax(0,1fr))!important;}}
    @media(prefers-reduced-motion:reduce){.st-key-intake-section-cards button{transition:none;transform:none!important;}}
    </style>''',unsafe_allow_html=True)


def continue_intake(patient,view,step=None):
    from executive_health_ai.ui.pages.manager import intake_entry
    with SessionLocal() as session:
        step=step or projection.first_incomplete(session,patient.id,view.intake)
    intake_entry.open_intake(patient,view,step=step,read_only=bool(view.intake and view.intake.status=='CONFIRMED'))


def support(data, event=None):
    st.markdown('**AI与知识支持**')
    activities=[a for f in data['files'] for a in f['support']]
    cols=st.columns(3)
    for col,key,title in zip(cols,('mapping','semantic','knowledge'),('规则映射','AI语义整理','知识/术语辅助')):
        rows=[a for a in activities if a.key==key]
        with col:
            st.markdown('**'+title+'**')
            if key=='semantic':
                from executive_health_ai.ui.agent_progress import ai_timing
                for f in data['files']:ai_timing(f.get('progress'))
            if key=='semantic' and event=='AI_REQUEST_STARTED':
                st.write('● 正在进行')
                st.caption('本地AI正在整理资料 · 用途：从自由文本中提取有原文依据的健康信息')
            elif any(a.used for a in rows):
                if key=='semantic' and any(a.used and a.status=='SUCCESS' for a in rows):st.caption('✓ 本地AI整理完成')
                for result in dict.fromkeys(a.mark+' '+a.label+' · '+a.result for a in rows if a.used):
                    st.caption(result.replace('仍需健管确认。','已纳入本次初评确认。') if data['finished'] else result)
            elif key=='mapping' and rows and any(a.status=='SUCCESS' for a in rows):
                st.caption('✓ 已完成文件读取与规则映射')
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


def draw(data, event=None, *, assessment_summary=True):
    if event is None and data['current'] and data['current']['goal'].status=='PROCESSING':
        event=data['current']['goal'].context_json.get('execution',{}).get('event')
    with st.container():
        title='健康管理助手正在整理资料' if data['processing'] else '本次资料整理已完成' if data['ready'] and not any(f['goal'].status in {'FAILED','ESCALATED','CANCELLED'} for f in data['files']) else '健康管理助手'
        st.subheader(title)
        if not data['files']:
            st.write('当前：暂无正在处理的健康资料')
            st.caption('你可以上传会员现有资料，系统会自动整理并尽量完善初始健康评估。')
            st.markdown('[上传健康资料](#intake-upload)')
            support(data)
            return
        from executive_health_ai.ui.agent_progress import render as progress_bar
        progress_bar(data.get('progress'),show_activity=False)
        phase=2 if event in {'CONTENT_READ','AI_REQUEST_STARTED'} else 4 if event=='PREFILL_READY' else data['phase']
        if data.get('progress'):phase=data['progress'].current_step-1
        done=data['progress'].done if data.get('progress') else tuple(i<phase or data['finished'] for i in range(7))
        st.markdown('<ol class="intake-agent-steps" aria-label="健康资料整理进度">'+''.join(
            f'<li class="{"done" if done[i] else "current" if i==phase else ""}"><b>{"✓" if done[i] else "●" if i==phase else "○"}</b>{label}<br><small>{"已完成" if done[i] else "当前" if i==phase else "待开始"}</small></li>'
            for i,label in enumerate(projection.PHASES))+'</ol>',unsafe_allow_html=True)
        current=data['current']
        linked=any(f['goal'].context_json.get('intake_id') for f in data['files'])
        filename=current['document'].title if current else '本批资料已整理，等待逐项核对' if not data['finished'] else '本批资料来源已核对并提交'
        action=('正在从 '+str(len(data['files']))+' 份健康资料中'+('提取可核对的健康信息' if phase==2 else '读取内容' if phase==1 else '匹配现有档案并准备初评预填' if phase in {3,4} else '接收原始资料')) if current else '需要您核对来源、处理冲突并补充初评' if not data['finished'] else '初始评估已提交，后续医学事实仍按现有规则确认'
        if current and data.get('progress'):action=data['progress'].current_activity
        if current and phase==6:action='正在写入已经确认的健康档案更新'
        if not current and data.get('exceptions') and not data['finished']:
            remaining=data['exceptions']['counts']['exceptions']
            action=f'资料已整理，请在下方处理 {remaining} 项例外，然后一次确认提交初评' if remaining else '资料已准备完成，请在下方一次确认提交初评'
        if event=='AI_REQUEST_STARTED':action='本地AI正在整理资料：从自由文本中提取有原文依据的健康信息'
        elif event=='AI_RESULT_CHECKED':action='本地AI整理完成，已核对候选信息的原文依据'
        elif event=='AI_UNAVAILABLE':action='本地AI未能完成可靠提取，保留原文等待人工补充'
        if not current and not linked:
            action='本次健康档案更新已完成，可继续完善初始评估' if data['finished'] else '健康档案更新草稿已准备，请核对来源与冲突后确认'
        if not current and any(f['goal'].status=='WAITING_DOCTOR' for f in data['files']):
            action='等待医生判断；医生提交后再继续健管确认'
            filename='医学问题已交给医生，当前无需重复整理资料'
        elif not current and any(f['goal'].status in {'FAILED','ESCALATED','CANCELLED'} for f in data['files']):
            action='资料需要人工接手，请核对原文件并补充可读取资料'
            filename='部分资料未能可靠读取，尚未全部完成'
        heading='当前正在进行' if data['processing'] else '当前状态'
        st.markdown('<div class="intake-agent-current" role="status"><strong>'+execution_mark(data,event)+heading+'</strong>'+escape(action)+'<br>当前处理：'+escape(filename)+'</div>',unsafe_allow_html=True)
        c.summary_strip([('上传资料',str(len(data['files']))+' 份'),('已经完成',f'{data["processed"]} / {len(data["files"])} 文件'),('已发现',str(data['count'])+' 项健康信息')])
        if data['ready']:
            s=data['stats']
            if assessment_summary:
                c.summary_strip([('自动预填',s['prefilled']),('待健管确认',s['pending']),('仍需补充',s['missing']),('冲突',s['conflicts']),('健康档案更新',data['updates'])])
            else:
                st.caption(f'健康档案更新：{data["updates"]} 项；初评准备度与待处理项见下方。')
            st.caption('健康档案候选已保留原文、测量及冲突核对结果；未经确认不会写入正式医疗事实。')
        st.markdown('**活动时间轴**')
        lines=[f'✓ 收到 {len(data["files"])} 份健康资料']
        shown=sorted(dict.fromkeys(data['events'][-6:]+[e for e in data['events'] if e[2].startswith('本地AI')][-4:]),key=lambda e:e[0])
        lines += [(at.replace(tzinfo=timezone.utc) if at.tzinfo is None else at).astimezone().strftime('%H:%M')+
                  (' ! 《' if '本地AI未能' in text else ' ✓ 《')+name+'》'+text for at,name,text in shown]
        if current:lines+=['● '+action+' · 《'+filename+'》']
        next_text='资料整理完成后，请从下方卡片核对来源并补充；此时需要您确认。' if current else '继续完成初始健康评估；提交前需核对所有来源。' if not data['finished'] else '查看已提交初评，继续健管专业确认。'
        if data.get('exceptions'):
            next_text='资料整理完成后处理少量例外；目前暂未轮到你。' if current else '在下方“需要你处理”逐项处理例外，再一次确认提交。' if not data['finished'] else '资料已提交；继续原有健管专业确认。'
            if not current and not data['finished'] and not data['exceptions']['queue']:next_text='资料已准备完成，可在下方一次确认提交初评。'
        if not current and not linked:next_text='核对下方健康档案更新；已提交的初评保留原有确认状态。' if not data['finished'] else '继续查看或完善初始健康评估。'
        lines+=['○ 下一步：'+next_text]
        st.markdown('<ul class="intake-agent-history">'+''.join('<li>'+escape(line)+'</li>' for line in lines)+'</ul>',unsafe_allow_html=True)
        support(data,event)


def workspace(app,patient,view, *, uploader=True, show_actions=True):
    styles()
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
    live()
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
        panel(patient,view)
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
        upload_area(patient,view)
    return data


def upload_area(patient,view):
    key=f'workspace-upload-{patient.id}'
    with st.container(border=True,key='intake-upload-area'):
        st.subheader('上传健康资料',anchor='intake-upload')
        st.caption('上传该会员现有的体检、问卷、病历、用药记录或其他健康资料。健康管理助手会自动识别内容，优先用于完善初始健康评估，并同步准备健康档案更新。')
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
    st.button('查看 / 手工修正（11步）' if exception_mode else label,key=f'workspace-primary-{patient.id}',type='secondary' if exception_mode or formal_review else 'primary',on_click=continue_intake,args=(patient,view))
    if view.intake:
        if state!='已完成':
            st.button('查看已填写内容',key=f'workspace-preview-{patient.id}',on_click=intake_entry.open_intake,args=(patient,view),kwargs={'read_only':True})
        if state=='已完成':st.button('补充/修正',key=f'workspace-amend-{patient.id}',on_click=intake_entry.amend,args=(patient,view))
