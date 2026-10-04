"""Care-episode presentation inside the existing Member360 history tab."""
from datetime import timedelta
from decimal import Decimal, InvalidOperation
from pathlib import Path
import re
import streamlit as st
import streamlit.components.v1 as components
from executive_health_ai.database import SessionLocal
from executive_health_ai.models.base import utc_now
from executive_health_ai.services.longitudinal_timeline import LongitudinalTimelineProjection, FILTERS, RISK_LABELS, number
from executive_health_ai.services.goal_metrics import METRIC_LABELS
from executive_health_ai.ui import components as c
from executive_health_ai.ui import experience as ux

_track = components.declare_component('health_history_tracks', path=str(Path(__file__).with_name('timeline_component')))


def public_text(value):
    if isinstance(value,dict):
        return '；'.join(public_text(v) for k,v in value.items() if not re.search('[a-zA-Z_]',str(k))) or '已保留原始业务记录'
    text=ux.business_text(str(value or ''))
    text=re.sub(r'\b[0-9a-f]{8}-[0-9a-f-]{27,}\b', '相关记录', text, flags=re.I)
    text=re.sub(r'\b[0-9a-f]{32}\b','相关记录',text,flags=re.I)
    for term in ('correlation_id','Snapshot ID','Trace ID','ToolCall','Tool call','HealthEvent','LLM Provider','LLM provider','Planner','JSON','Goal ID'):
        text=re.sub(re.escape(term),'内部记录',text,flags=re.I)
    # Source records from older modules sometimes serialized a dict as text.
    if text.lstrip().startswith(('{','[')):return '已保留原始业务记录；请通过健康档案核对。'
    return text


def display_value(value, unit):
    if unit in {'min','minutes'}:
        try:return number((Decimal(str(value))/60).quantize(Decimal('.1')))+' 小时'
        except InvalidOperation:pass
    return f'{number(value)} {unit or ""}'


def change_text(entry):
    change=entry.details.get('change') or {}
    unit=change.get('unit') or (entry.snapshot.metric_summary.get(entry.metric,{}).get('unit') if entry.snapshot else '')
    previous=change.get('mean_7d',change.get('baseline'))
    if previous is not None and change.get('today') is not None:
        return display_value(previous,unit)+' → '+display_value(change['today'],unit)
    if entry.entry_type=='CURRENT_STATE' and entry.snapshot:
        return ' · '.join(METRIC_LABELS.get(k,'相关指标')+' '+display_value(v['value'],v['unit'])
            for k,v in entry.snapshot.metric_summary.items() if k in {'weight','sleep_duration'})
    return public_text(entry.summary)


def selected_groups(groups, limit):
    """Retain meaningful episodes, baseline and current state before routine milestones."""
    latest_baseline=max((g['entry'].occurred_at for g in groups if g['entry'].entry_type=='ANNUAL_BASELINE'),default=None)
    def priority(g):
        e=g['entry']
        return (100 if g['current'] else 90 if e.entry_type in {'MEANINGFUL_CHANGE','RISK_CHANGE','DOCTOR_DECISION'}
            else (85 if e.occurred_at==latest_baseline else 30) if e.entry_type=='ANNUAL_BASELINE'
            else 80 if e.entry_type in {'OUTCOME','PHASE_STARTED'} else 75 if e.entry_type=='GOAL_CONFIRMED'
            else 70 if any(r.entry_type=='PHASE_REVIEW' for r in g['members']) else 60)
    chosen={g['key'] for g in sorted(groups,key=lambda g:(priority(g),g['entry'].occurred_at),reverse=True)[:limit]}
    return [g for g in groups if g['key'] in chosen]


def detail_payload(group, detail):
    e=group['entry'];snap=e.snapshot
    state=[public_text(e.details.get('state') or e.summary)]
    if e.details.get('goal'):state.append('管理目标：'+public_text(e.details['goal']))
    if snap:
        state.append('当前阶段：'+public_text(snap.phase_summary))
        if snap.medication_summary:state.append('正式用药：'+'；'.join(public_text(v) for v in snap.medication_summary))
    if e.entry_type=='CURRENT_STATE':
        state.extend(['开放事项：'+str(e.details.get('open_items',0)), '下一步：'+public_text(e.details.get('next'))])
        if e.details.get('sleep_week'):state.append('近7日睡眠：'+e.details['sleep_week'])
    metrics=[]
    for code,v in (snap.metric_summary if snap else {}).items():
        metrics.append({'label':METRIC_LABELS.get(code,'身高' if code=='height' else '相关指标'),
            'value':display_value(v.get('value'),v.get('unit')),
            'comparison':display_value(v['delta'],v.get('unit')) if 'delta' in v else '暂无可比基线',
            'date':str(v.get('at',e.occurred_at.date()))[:10]})
    change=e.details.get('change') or {};changes=[change_text(e)] if change else ['此节点记录状态或管理里程碑，不额外推断显著变化。']
    unit=change.get('unit') or (snap.metric_summary.get(e.metric,{}).get('unit') if snap else '')
    for key,label in [('mean_7d','近7日均值'),('mean_30d','近30日均值')]:
        if change.get(key) is not None:changes.append(label+'：'+display_value(change[key],unit))
    if change.get('window_days'):changes.append('比较时间窗：'+str(change['window_days'])+' 天')
    if change.get('reason'):changes.append('触发依据：'+public_text(change['reason']))
    if e.details.get('baseline_label'):changes.append('个人基线：'+public_text(e.details['baseline_label']))
    bm=e.details.get('baseline_metric')
    if bm:changes.append('年度基线值：'+display_value(bm['value'],bm['unit']))
    memory=detail['memory']
    def care_text(row):
        if row.details.get('phase'):
            return '；'.join(k+'：'+public_text(v)[:160] for k,v in row.details['phase'].items()
                if k in {'阶段目标','实际完成','会员反馈','未解决问题','下一阶段'} and v)
        return public_text(row.details.get('human') or row.details.get('result') or row.summary)
    return {'key':group['key'],'state':state,'metrics':metrics,'changes':changes,
        'automatic':[public_text(v) for v in detail['automatic']] or ['没有留存可核验的自动准备记录。'],
        'human_reason':public_text(detail['human_reason']),
        'care':[{'date':r.occurred_at.strftime('%Y-%m-%d'),'title':public_text(r.title),
            'text':care_text(r)} for r in detail['care']],
        'outcomes':[{'text':'后续观察到'+public_text(r.summary),'status':r.status,
            'evidence':public_text(r.details.get('result')),'date':r.occurred_at.strftime('%Y-%m-%d')} for r in detail['outcomes']],
        'memory':{'status':memory['status'],'text':public_text(memory['text']),
            'range':' 至 '.join(memory['time_range']) if memory['time_range'] else '',
            'source':'关联计划调整与后续结果；原始记录见下方数据来源。' if memory['sources'] else ''},
        'sources':[{'label':s['label']+(' · 已修正' if s['corrected'] else ''),
            'text':public_text(s['text']),'original':public_text(s['original'])} for s in detail['sources']],
        'metric':bool(e.metric),'progress':e.details.get('progress',{}).get('percent')}


def render(app, patient):
    c.section_header('健康历程','查看健康状态的重要变化，以及系统准备、人工行动和后续结果。')
    now=utc_now();prefix=f'longitudinal-v2-{patient.id}'
    years=st.session_state.get(prefix+'-years',1)
    window=(now-timedelta(days=365*years),now)
    projection=LongitudinalTimelineProjection()
    with SessionLocal() as session:
        view=projection.build(session,patient.id,time_range=window,now=now)
        if view.empty:
            ux.empty_state('当前还没有足够的纵向健康记录','随着资料、设备、随访、医生结果和阶段管理进入系统后，这里会自动形成健康历程。')
            return
        overview=projection.overview(view)
        st.subheader('过去一年概览' if years==1 else '所选时间范围概览')
        for col,title,lines in zip(st.columns([1.3,1,1.2]),['健康状态','管理动作','当前结论'],
            [overview['state'],overview['actions'],overview['conclusion']]):
            with col:
                st.markdown('**'+title+'**')
                for line in lines:st.write(public_text(line))
        st.caption(f"本时段 {overview['attention']} 次需关注 / 优先处理事件 · {window[0]:%Y-%m-%d} — {now:%Y-%m-%d} · 较早 ↓ 最近")
        scope=st.radio('历程筛选',FILTERS,horizontal=True,key=f'longitudinal-filter-{patient.id}',label_visibility='collapsed')
        groups=projection.groups(view)
        if scope!='全部':
            allowed={'健康变化':{'MEANINGFUL_CHANGE','RISK_CHANGE','OUTCOME','ANNUAL_BASELINE','CURRENT_STATE'},
                '管理行动':{'CARE_CONTACT','MANAGEMENT_ITEM','FOLLOWUP','PLAN_ADJUSTMENT','GOAL_CONFIRMED','PLAN_CONFIRMED'},
                '医疗':{'DOCTOR_DECISION','MEDICATION_CHANGE','MEDICATION_END','RECHECK'},
                '阶段':{'PHASE_REVIEW','PHASE_STARTED'}}[scope]
            groups=[g for g in groups if g['current'] or any(e.entry_type in allowed for e in g['members'])]
        visible=selected_groups(groups,st.session_state.get(prefix+'-limit',10))
        selected=st.session_state.get(prefix+'-selected')
        group=next((g for g in visible if g['key']==selected),None)
        payload=detail_payload(group,projection.group_details(session,view,group)) if group else None
        entries=[{'key':g['key'],'date':g['entry'].occurred_at.strftime('%Y-%m-%d'),'title':public_text(g['title']),
            'summary':change_text(g['entry']),'risk':RISK_LABELS.get(g['entry'].risk_level,''),
            'human':g['human'],'outcome':public_text(g['outcome']),'current':g['current']} for g in visible]
        if not entries:st.info('本时段没有符合筛选的重要事件。')
        else:
            selected_value=_track(entries=entries,detail=payload,selected=selected,
                key=prefix+'-axis-'+scope,default=None)
            if isinstance(selected_value,dict) and selected_value!=st.session_state.get(prefix+'-handled'):
                st.session_state[prefix+'-handled']=selected_value
                action=selected_value.get('action');choice=selected_value.get('key')
                if action=='trend' and group and choice==group['key'] and group['entry'].metric:
                    st.session_state[f'health-metric-pending-{patient.id}']=group['entry'].metric
                    st.session_state[f'health-data-window-{patient.id}']={
                        'start':(group['entry'].occurred_at-timedelta(days=14)).date().isoformat(),
                        'end':max(e.occurred_at for e in group['members']).date().isoformat()}
                    st.session_state[f"ux-period-{patient.id}-{group['entry'].metric}"]='时间轴范围'
                    app.request_navigation(surface='运营后台',ops_page='成员',member_id=patient.id,member_section='健康',archive_view='健康数据',
                        health_data_window=st.session_state[f'health-data-window-{patient.id}'])
                elif action=='select' and choice!=selected and any(g['key']==choice for g in visible):
                    st.session_state[prefix+'-selected']=choice;st.rerun()
                elif action=='close' and selected:
                    st.session_state[prefix+'-selected']=None;st.rerun()
            elif isinstance(selected_value,str) and selected_value!=selected and any(g['key']==selected_value for g in visible):
                st.session_state[prefix+'-selected']=selected_value;st.rerun()
        if len(groups)>len(visible) or view.has_earlier:
            if st.button('查看更早记录',key=prefix+'-older'):
                st.session_state[prefix+'-limit']=st.session_state.get(prefix+'-limit',10)+10
                if len(groups)<=len(visible):st.session_state[prefix+'-years']=years+1
                st.rerun()
        if view.truncated:st.caption('较长历史已按每类最近500条读取；此视图不代表全部归档。')
