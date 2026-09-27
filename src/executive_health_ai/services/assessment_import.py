"""Multi-document drafts over the existing intake, candidates and Agent goals."""
from copy import deepcopy
from datetime import date
import hashlib
import json
from uuid import UUID
from sqlalchemy import select
from executive_health_ai.models import (AgentGoal, Document, Patient, ReportExtractionRun,
    ReportExtractionCandidate, AgentPlanStep, AgentApprovalRequest)
from executive_health_ai.models.management_workflow import IntakeAssessment
from executive_health_ai.models.base import utc_now
from executive_health_ai.services.management_workflow import STEPS, TABLE_FIELDS, owned, audit

DATA_STEPS=tuple(s for s in STEPS[:-1] if s!='最近用药')
IDENTITY={'家族健康史':'具体疾病','个人病史':'疾病或问题','手术 / 住院史':'名称','过敏史':'名称',
    '当前用药 / 营养补充':'名称','最近用药':'名称','专项症状评估':'症状'}
NEGATIVE={'无','无已知','否','无药物过敏','无过敏史','无既往病史'}


def digest(value):return hashlib.sha256(json.dumps(value,ensure_ascii=False,sort_keys=True,default=str).encode()).hexdigest()
def step_for(section):return '当前用药 / 营养补充' if section=='最近用药' else section
def canonical(section,field,value):
    value=str(value or '').strip()
    if field=='sex':return {'男':'male','女':'female'}.get(value,value)
    if field=='birth_date':
        normalized=value.replace('年','-').replace('月','-').replace('日','').replace('/','-')
        try:return date.fromisoformat(normalized).isoformat()
        except ValueError:return value
    return ' '.join(value.split())


def metadata(row):return deepcopy((row.review or {}).get('document_intake',{}))
def set_metadata(row,value):row.review={**(row.review or {}),'document_intake':value}


class AssessmentImportService:
    def goals(self,session,row):
        return list(session.scalars(select(AgentGoal).where(AgentGoal.member_id==row.patient_id,
            AgentGoal.goal_type=='PROFILE_INTAKE',AgentGoal.context_json['intake_id'].as_string()==str(row.id))
            .order_by(AgentGoal.started_at,AgentGoal.id)))

    def upload_batch(self,session,member_id,intake_id,files,*,actor,role='HEALTH_MANAGER',document_type='auto'):
        from executive_health_ai.services.profile_ingestion import ProfileIngestionService, manager
        manager(role,actor);row=owned(session,IntakeAssessment,intake_id,member_id)
        if row.status!='DRAFT':raise ValueError('初评已提交，请先退回补充。')
        if not files or len(files)>20:raise ValueError('每批请选择 1–20 份资料。')
        if sum(len(content) for _,content in files)>100*1024*1024:raise ValueError('本批资料总大小不能超过 100 MB。')
        result=[]
        for name,content in files:
            try:
                with session.begin_nested():
                    goal,duplicate=ProfileIngestionService().upload(session,member_id,name,content,document_type,
                        actor=actor,role=role,intake_id=row.id)
                result.append({'filename':name,'goal_id':str(goal.id),'duplicate':duplicate,'error':None})
            except (ValueError,PermissionError,UnicodeError) as exc:
                result.append({'filename':name,'goal_id':None,'duplicate':False,'error':str(exc)})
        if any(r['goal_id'] for r in result):
            session.refresh(row)
            state=metadata(row);state.setdefault('reviews',{});state.setdefault('file_checks',{})
            set_metadata(row,state)
            audit(session,member_id,actor,'intake_documents_received',row)
        return result

    def project(self,session,member_id,intake_id):
        row=owned(session,IntakeAssessment,intake_id,member_id);member=session.get(Patient,member_id)
        goals=self.goals(session,row);files=[];facts=[];other=[];state=metadata(row)
        for goal in goals:
            doc=session.get(Document,UUID(goal.source_id));run=session.get(ReportExtractionRun,UUID(goal.context_json['run_id']))
            rows=list(session.scalars(select(ReportExtractionCandidate).where(ReportExtractionCandidate.extraction_run_id==run.id))) if run.status=='COMPLETED' else []
            warnings=run.metadata_json.get('coverage_warnings',[])
            signature=digest([str(goal.id),run.status,run.completed_at,warnings])
            needs_check=goal.status in {'ESCALATED','CANCELLED'} or bool(warnings) or any(r.candidate_type!='PROFILE_FACT' for r in rows)
            files.append({'goal':goal,'document':doc,'run':run,'warnings':warnings,'needs_check':needs_check,
                'checked':state.get('file_checks',{}).get(str(goal.id),{}).get('signature')==signature,
                'signature':signature,'count':len(rows)})
            for candidate in rows:
                if candidate.candidate_type=='PROFILE_FACT':facts.append(candidate)
                else:other.append(candidate)
        grouped={}
        for candidate in facts:
            data=candidate.structured_data_json;section,field=data['section'],data['field']
            record=data.get('record',{});id_field=IDENTITY.get(section)
            identity=canonical(section,id_field,record.get(id_field) or (data['value'] if field==id_field else '')) if id_field else ''
            if section=='家族健康史' and record.get('患病家属'):identity+=' / '+record['患病家属']
            ambiguous=bool(id_field and not identity)
            key=(section,identity or (str(candidate.document_id)+':'+data.get('source_locator','') if ambiguous else ''),field)
            group=grouped.setdefault(key,{'section':section,'field':field,'identity':identity,'ambiguous':ambiguous,'rows':[]})
            group['rows'].append(candidate)
        prefill={};groups=[]
        for group in grouped.values():
            section,field,identity=group['section'],group['field'],group['identity']
            values=list(dict.fromkeys(canonical(section,field,r.structured_data_json['value']) for r in group['rows']))
            current=(row.responses or {}).get(section)
            if section=='基础资料':old=canonical(section,field,getattr(member,field) or '')
            elif section in TABLE_FIELDS:
                id_field=IDENTITY[section]
                matching=[r for r in (current or []) if canonical(section,id_field,r.get(id_field))==identity.split(' / ')[0]
                    and (section!='家族健康史' or ' / ' not in identity or r.get('患病家属')==identity.split(' / ',1)[1])]
                old='；'.join(dict.fromkeys(str(r.get(field) or '') for r in matching)).strip('；')
            else:old=str((current or {}).get(field) or '')
            family=[g for g in grouped.values() if g['section']==section]
            negative_mix=bool(section in TABLE_FIELDS and any(g['identity'] in NEGATIVE for g in family)
                and any(g['identity'] and g['identity'] not in NEGATIVE for g in family))
            if section in TABLE_FIELDS and current:
                existing_ids={str(r.get(IDENTITY[section]) or '') for r in current}
                negative_mix |= bool(identity in NEGATIVE and existing_ids-NEGATIVE-{''} or identity not in NEGATIVE and existing_ids & NEGATIVE)
            conflict=len(values)>1 or bool(old and any(v!=canonical(section,field,old) for v in values)) or negative_mix
            value=values[0] if len(values)==1 else ''
            safe=not conflict and not group['ambiguous'] and bool(value)
            if section=='基础资料' and field=='sex' and value not in {'male','female'}:safe=False
            if section=='基础资料' and field=='birth_date':
                try:safe &= date(1900,1,1)<=date.fromisoformat(value)<=date.today()
                except ValueError:safe=False
            group.update(values=values,current=old,conflict=bool(conflict),safe=safe,
                key=digest([section,identity,field]),duplicate_count=len(group['rows'])-len(values))
            groups.append(group)
            if not safe or old:continue
            if section in TABLE_FIELDS:
                rows=prefill.setdefault(section,[]);id_field=IDENTITY[section]
                target=next((r for r in rows if r.get(id_field)==identity.split(' / ')[0] and
                    (section!='家族健康史' or ' / ' not in identity or r.get('患病家属')==identity.split(' / ',1)[1])),None)
                if target is None:
                    target={id_field:identity.split(' / ')[0]}
                    if section=='家族健康史' and ' / ' in identity:target['患病家属']=identity.split(' / ',1)[1]
                    rows.append(target)
                target[field]=value
            else:prefill.setdefault(section,{})[field]=value
        steps=[]
        for step in DATA_STEPS:
            relevant=[g for g in groups if step_for(g['section'])==step]
            fingerprint=digest([sorted(str(g.id) for g in goals),[(g['key'],[(str(r.id),r.structured_data_json['value']) for r in g['rows']]) for g in relevant]])
            response=self.saved_answers(row,member,step)
            reviewed=state.get('reviews',{}).get(step,{})
            checked=bool(reviewed and reviewed.get('signature')==fingerprint and reviewed.get('answer_hash')==digest(response))
            present=step in row.responses and (step!='当前用药 / 营养补充' or '最近用药' in row.responses)
            status='已填写' if present and (checked or not goals) else '存在冲突' if any(g['conflict'] for g in relevant) else '待确认' if relevant or present else '资料缺失'
            steps.append({'step':step,'status':status,'signature':fingerprint,'groups':relevant,'checked':checked,'present':present})
        return {'intake':row,'goals':goals,'files':files,'groups':groups,'other':other,'prefill':prefill,'steps':steps,
            'processing':any(g.status in {'RUNNING','PROCESSING','WRITING'} for g in goals)}

    @staticmethod
    def saved_answers(row,member,step):
        if step=='基础资料':return {field:str(getattr(member,field) or '') for field in ('display_name','birth_date','sex')}
        return [row.responses.get(step),row.responses.get('最近用药')] if step=='当前用药 / 营养补充' else row.responses.get(step)

    def form_data(self,view,section):
        """Merge only empty fields; retained answers always win."""
        row=view['intake'];current=deepcopy(row.responses.get(section));suggested=deepcopy(view['prefill'].get(section))
        if section in TABLE_FIELDS:
            result=current or []
            for proposal in suggested or []:
                identity=IDENTITY[section]
                existing=next((r for r in result if r.get(identity)==proposal.get(identity) and
                    (section!='家族健康史' or r.get('患病家属')==proposal.get('患病家属'))),None)
                if existing is None:result.append(proposal)
                else:
                    for k,v in proposal.items():
                        if not existing.get(k):existing[k]=v
            return result
        return {**(suggested or {}),**{k:v for k,v in (current or {}).items() if v}}

    def record_review(self,session,row,step,actor,note='',role='HEALTH_MANAGER'):
        from executive_health_ai.services.profile_ingestion import manager
        manager(role,actor)
        if row.status!='DRAFT':raise ValueError('初评已提交，不能修改来源核对记录。')
        view=self.project(session,row.patient_id,row.id)
        if view['processing']:raise ValueError('资料仍在逐份整理，请等待后再确认来源。')
        item=next(s for s in view['steps'] if s['step']==step)
        if any(g['conflict'] for g in item['groups']) and not note.strip():raise ValueError('请填写冲突处理或暂不采用的原因。')
        state=metadata(row);reviews=state.setdefault('reviews',{})
        reviews[step]={'signature':item['signature'],'answer_hash':digest(self.saved_answers(row,session.get(Patient,row.patient_id),step)),
            'actor':actor,'note':note,'at':utc_now().isoformat()}
        set_metadata(row,state)

    def acknowledge_file(self,session,member_id,intake_id,goal_id,actor,note):
        from executive_health_ai.services.profile_ingestion import manager
        manager('HEALTH_MANAGER',actor)
        view=self.project(session,member_id,intake_id)
        if view['intake'].status!='DRAFT' or not note.strip():raise ValueError('请在草稿阶段说明未识别内容的人工处理情况。')
        file=next((f for f in view['files'] if str(f['goal'].id)==str(goal_id)),None)
        if not file or not file['needs_check']:raise ValueError('本份资料不需要人工接手确认。')
        state=metadata(view['intake']);state.setdefault('file_checks',{})[str(goal_id)]={'signature':file['signature'],'actor':actor,'note':note,'at':utc_now().isoformat()}
        set_metadata(view['intake'],state);audit(session,member_id,actor,'intake_file_manually_checked',view['intake'])

    def validate_submit(self,session,row):
        view=self.project(session,row.patient_id,row.id)
        if not view['goals']:return view
        if view['processing']:raise ValueError('仍有资料正在整理，暂不能提交初评。')
        if any(g.status=='WAITING_DOCTOR' for g in view['goals']):raise ValueError('仍有资料等待医生判断，请先完成现有医生流程。')
        if any(f['needs_check'] and not f['checked'] for f in view['files']):raise ValueError('请核对未识别内容及未映射到初评的资料，并记录人工处理情况。')
        missing=[s['step'] for s in view['steps'] if s['status']!='已填写']
        if missing:raise ValueError('以下步骤尚未完成来源核对：'+'、'.join(missing))
        return view

    def finish(self,session,row,actor):
        from executive_health_ai.agent.profile_intake import trace
        from executive_health_ai.services.profile_ingestion import candidates
        for goal in self.goals(session,row):
            if goal.status in {'COMPLETED','CANCELLED'}:continue
            failed=goal.status=='ESCALATED'
            for approval in session.scalars(select(AgentApprovalRequest).where(AgentApprovalRequest.goal_id==goal.id,AgentApprovalRequest.status=='PENDING')):
                approval.status='CANCELLED' if failed else 'APPROVED';approval.decision=approval.status
                approval.decided_by=actor;approval.decided_at=utc_now()
            for step in session.scalars(select(AgentPlanStep).where(AgentPlanStep.plan_id==goal.current_plan_id)):
                if step.step_type in {'REVIEW','WRITING'} and not failed:
                    step.status='COMPLETED';step.completed_at=utc_now();step.result_summary='初评草稿来源已核对并提交；不写入医学结论'
            for candidate in candidates(session,goal):
                if candidate.candidate_type=='PROFILE_FACT':
                    candidate.status='INTAKE_REVIEWED';candidate.reviewed_by=actor;candidate.reviewed_at=utc_now()
                    candidate.structured_data_json={**candidate.structured_data_json,'confirmation_status':'初评来源已核对','target_type':'IntakeAssessment','target_id':str(row.id)}
            goal.status='CANCELLED' if failed else 'COMPLETED';goal.automation_paused=failed;goal.next_check_at=None
            if not failed:goal.completed_at=utc_now()
            goal.next_action='人工接手后已提交初评；本文件解析未成功' if failed else '初始评估已提交，等待健管初评；未生成新的诊断、处方或风险'
            goal.success_criteria={'intake_submitted':True,'sources_reviewed':True,'parsed':not failed}
            goal.context_json={**goal.context_json,'intake_submitted':True,'manager_confirmed':True}
            trace(session,goal,goal.next_action)
