"""The Member360 history tab. Business projection is independent of Streamlit."""
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
    text=ux.business_text(str(value or ''))
    text=re.sub(r'\b[0-9a-f]{8}-[0-9a-f-]{27,}\b', '相关记录', text, flags=re.I)
    for term in ('correlation_id','Snapshot ID','Trace ID','ToolCall','HealthEvent','LLM Provider','Planner','JSON'):
        text=text.replace(term,'内部记录')
    return text


def display_value(value, unit):
    if unit in {'min','minutes'}:
        try:return number((Decimal(str(value))/60).quantize(Decimal('.1')))+' 小时'
        except InvalidOperation:pass
    return f'{number(value)} {unit or ""}'


def render(app, patient):
    c.section_header('健康历程','查看会员健康状态的重要变化，以及对应的管理行动和后续结果。')
    now=utc_now()
    selected_filter=st.radio('历程筛选',FILTERS,horizontal=True,key=f'longitudinal-filter-{patient.id}',label_visibility='collapsed')
    years=st.session_state.get(f'longitudinal-years-{patient.id}',1)
    window=(now-timedelta(days=365*years),now)
    projection=LongitudinalTimelineProjection()
    with SessionLocal() as session:
        view=projection.build(session,patient.id,time_range=window,filters=selected_filter,now=now)
        if view.empty:
            ux.empty_state('当前还没有足够的纵向健康记录','随着资料、设备、随访、医生结果和阶段管理进入系统后，这里会自动形成健康历程。')
            return
        st.write(public_text(view.story))
        st.caption(f'{window[0]:%Y-%m-%d} — {now:%Y-%m-%d} · 较早 → 最近 · 点击节点查看详情；连线表示同一管理过程')
        if not view.entries:st.info('本时段没有符合筛选的重要节点。')
        # Bound visual density independently of the service's bounded business reads.
        visible=view.entries[-60:]
        if len(view.entries)>60:st.caption('当前展示最近 60 个重要节点；可按健康变化、管理行动、医疗或阶段筛选。')
        selected=_track(entries=[{'key':e.entry_id,'date':e.occurred_at.strftime('%Y-%m-%d'),
            'track':e.track,'title':public_text(e.title),'summary':public_text(e.summary)[:55],
            'risk':RISK_LABELS.get(e.risk_level,''),'episode':e.care_episode_id or ''} for e in visible],
            key=f'longitudinal-tracks-{patient.id}-{selected_filter}-{years}',default=None)
        if view.has_earlier and st.button('查看更早记录',key=f'longitudinal-older-button-{patient.id}'):
            st.session_state[f'longitudinal-years-{patient.id}']=years+4;st.rerun()
        if view.truncated:st.caption('较长历史已按每类最近 500 条读取；此视图不代表全部归档。')
        entry=next((e for e in visible if e.entry_id==selected),None)
        if entry is None:return
        detail=projection.details(session,view,entry.entry_id)
    with st.expander(entry.title+' · '+entry.occurred_at.strftime('%Y-%m-%d'),expanded=True):
        left,right=st.columns([1.7,1],gap='large')
        with left:
            st.markdown('**当时的健康状态**')
            st.write(public_text(entry.details.get('state') or entry.summary))
            snap=entry.snapshot
            if snap:
                if snap.metric_summary:
                    rows=[]
                    for code, value in snap.metric_summary.items():
                        rows.append({'指标':METRIC_LABELS.get(code,'相关指标'),'记录值':display_value(value.get('value'),value.get('unit')),
                            '较年度基线':display_value(value['delta'],value.get('unit')) if 'delta' in value else '未记录可比基线',
                            '记录日期':str(value.get('at',entry.occurred_at.date()))[:10]})
                    st.dataframe(rows,hide_index=True,width='stretch')
                st.caption('当前阶段：'+public_text(snap.phase_summary)+' · '+snap.risk_summary)
                if snap.medication_summary:st.write('正式用药：'+'；'.join(snap.medication_summary))
                if snap.data_completeness.get('percent') is not None:st.caption('最近健康摘要的核心数据准备度：'+str(snap.data_completeness['percent'])+'%')
            if entry.details.get('sleep_week'):st.write('近7日睡眠：'+entry.details['sleep_week'])
            if entry.details.get('change'):
                change=entry.details['change'];unit=change.get('unit') or (snap.metric_summary.get(entry.metric,{}).get('unit') if snap else '')
                st.markdown('**与之前相比发生的变化**')
                values=[('当前值','today'),('近7日均值','mean_7d'),('近30日均值','mean_30d'),('记录基线','baseline')]
                st.write(' · '.join(label+'：'+display_value(change[k],unit) for label,k in values if change.get(k) is not None))
                previous=change.get('mean_7d',change.get('baseline'))
                if previous is not None and change.get('today') is not None:
                    try:st.write('变化量：'+display_value(Decimal(str(change['today']))-Decimal(str(previous)),unit))
                    except InvalidOperation:pass
                st.caption('比较时间窗：'+str(change.get('window_days','记录中的前后两个时间点'))+(' 天' if change.get('window_days') else ''))
                if change.get('reason'):st.write('触发依据：'+public_text(change['reason']))
                if entry.details.get('baseline_label'):
                    st.caption('个人基线：'+public_text(entry.details['baseline_label']))
                    bm=entry.details.get('baseline_metric')
                    if bm:st.write('年度基线值：'+display_value(bm['value'],bm['unit']))
            if entry.details.get('question'):st.write('提交给医生的问题：'+public_text(entry.details['question']))
            if entry.details.get('reason'):st.write('关联原因：'+public_text(entry.details['reason']))
            if entry.metric and st.button('查看该指标趋势',key=f'longitudinal-trend-{patient.id}'):
                st.session_state[f'health-metric-pending-{patient.id}']=entry.metric
                app.request_navigation(surface='运营后台',ops_page='成员',member_id=patient.id,member_section='健康',archive_view='健康数据')
            st.markdown('**系统自动做了什么**')
            st.write('；'.join(detail['automatic']) or '没有已记录的自动处理结果。')
            st.markdown('**人工 / 医生做了什么**')
            care=[e for e in detail['related'] if e.track=='CARE_ACTION']
            if care:
                for item in care:st.write(f'{item.occurred_at:%m-%d} · {public_text(item.title)}：'+public_text(item.details.get('human') or item.summary))
            else:st.write(public_text(entry.details.get('human') or entry.details.get('result') or '暂无关联的人工处理记录。'))
            if entry.details.get('phase'):
                for label,value in entry.details['phase'].items():
                    if isinstance(value,(str,int,float)) and not re.search('[a-zA-Z_]',label):st.write(public_text(label)+'：'+public_text(value))
        with right:
            if entry.risk_level:st.write('管理状态：'+RISK_LABELS[entry.risk_level])
            trigger=next((e for e in detail['related'] if e.entry_type in {'MEANINGFUL_CHANGE','RISK_CHANGE'}),None)
            if trigger and trigger.entry_id!=entry.entry_id:st.write(f'关联变化：{trigger.occurred_at:%m-%d} · '+public_text(trigger.title))
            if entry.details.get('goal'):st.write('关联目标：'+public_text(entry.details['goal']))
            pct=entry.details.get('progress',{}).get('percent')
            if pct is not None:st.progress(pct/100,text=f'目标进度 {pct:g}%')
            st.markdown('**后续结果**')
            st.write(public_text(detail['outcome']))
            for item in detail['outcomes']:
                st.write(f'{item.occurred_at:%m-%d} · '+public_text(item.summary));st.caption(public_text(item.details.get('result')))
            st.caption('观察到的前后变化不直接证明某项干预的因果效果。')
            if entry.details.get('next'):st.write('下一步：'+public_text(entry.details['next']))
            st.markdown('**数据来源**')
            for source in detail['sources']:
                st.caption(source['label']+(' · 已修正' if source['corrected'] else ''))
                st.write(public_text(source['text']))
                if source['original']:st.text(source['original'])
