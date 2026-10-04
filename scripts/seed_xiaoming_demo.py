"""Explicit synthetic story replay. Never invoked by the platform launcher.

Use --database <existing.db>; the CLI backs up first and verifies every preexisting
row before committing. --reset is confined to this seeder's recorded manifest.
"""
from contextlib import contextmanager, ExitStack
from datetime import date, datetime, timedelta, timezone
from decimal import Decimal
from pathlib import Path
from uuid import UUID
from unittest.mock import patch
import argparse
import hashlib
import json
import sqlite3
import sys

from sqlalchemy import select, event, delete
from sqlalchemy.orm import Session
from executive_health_ai.database import create_database_engine
from executive_health_ai.models import (Base, Patient, Observation, HealthAssessment, HealthEvent,
    HealthProgram, HealthJourney, ProgramPhase, AgentGoal, MemberAgent, AuditLog, Task,
    Document, ReportExtractionRun, ReportExtractionCandidate, RiskRule, RiskEvent,
    DoctorReview, HealthProblem, ManagementPlan, MedicationPlan, RawData, AnnualHealthAccount, ManagementRule)
from executive_health_ai.models.goal_data import DailyHealthSummary, SummaryWorkItem, ManagementGoal
from executive_health_ai.models.management_workflow import IntakeAssessment, ManagementLog, RecheckPlan
from executive_health_ai.services.management_workflow import ManagementWorkflowService, STEPS, TABLE_FIELDS, PROFILE_FIELDS, RECHECK_STATES
from executive_health_ai.services import management_goals, daily_summary, communications, care_runtime, chronic_care
from executive_health_ai.services.health_events import ingest_health_event, dispatch_event
from executive_health_ai.services.longitudinal import HealthAssessmentService
from executive_health_ai.services.care_episodes import link_care_episode
from executive_health_ai.services.risk_operations import RiskOperationsService
from executive_health_ai.services.task_transitions import TaskTransitionService
from executive_health_ai.services.management_action_loop import ManagementActionLoop
from executive_health_ai.services import daily_care, care_commands
from executive_health_ai.services.report_parsing import ReportParsingService
from executive_health_ai.services.member_agents import ensure_member_agent, synchronize
from executive_health_ai.services.goal_metrics import REGISTRY
from executive_health_ai.agent.supervisor import HealthOpsAgentSupervisor

EXTERNAL_ID = 'synthetic-demo-xiaoming-v1'
MANIFEST = 'xiaoming_synthetic_seed_v1'
OWNER = '演示健康管理师'
DOCTOR = '演示王医生'
AS_OF = date(2026, 10, 4)


def at(month, day=1, year=2026):
    return datetime(year, month, day, 4, tzinfo=timezone.utc)


@contextmanager
def replay_time(session, when):
    """Historical fixture clock, only in the explicit, single-process seeder.

    Calls the real services at the scenario time; no status/wait or rule results
    are mocked. Never import this helper into the running server.
    """
    class Clock(datetime):
        @classmethod
        def now(cls, tz=None):
            return when.astimezone(tz) if tz else when.replace(tzinfo=None)
    class Calendar(date):
        @classmethod
        def today(cls):
            return when.date()
    def timestamp_new(s, *_):
        for obj in s.new:
            for key in ('created_at', 'updated_at', 'received_at', 'assessed_at', 'recorded_at', 'started_at'):
                if hasattr(type(obj), key) and getattr(obj, key, None) is None:
                    setattr(obj, key, when)
    with ExitStack() as stack:
        for name, module in list(sys.modules.items()):
            if not name.startswith('executive_health_ai.') or name == 'executive_health_ai.models.base' or module is None:
                continue
            if hasattr(module, 'utc_now'):
                stack.enter_context(patch.object(module, 'utc_now', lambda: when))
            if getattr(module, 'datetime', None) is datetime:
                stack.enter_context(patch.object(module, 'datetime', Clock))
            if getattr(module, 'date', None) is date:
                stack.enter_context(patch.object(module, 'date', Calendar))
        event.listen(session, 'before_flush', timestamp_new)
        try:
            yield
            session.flush()
        finally:
            event.remove(session, 'before_flush', timestamp_new)


def inventory(session):
    """Typed primary keys + row hashes, also protects shared configuration."""
    result = {}
    for table in Base.metadata.tables.values():
        keys = list(table.primary_key.columns)
        rows = session.execute(select(table)).mappings()
        result[table.name] = {tuple(row[c.name] for c in keys): hashlib.sha256(
            json.dumps(dict(row), default=str, sort_keys=True, ensure_ascii=False).encode()).hexdigest() for row in rows}
    return result


def assert_preserved(before, after, *, removed=None):
    removed = removed or {}
    for table, rows in before.items():
        for key, digest in rows.items():
            if key in removed.get(table, set()):
                continue
            if after.get(table, {}).get(key) != digest:
                raise RuntimeError(f'Existing data changed: {table} {key}. Transaction must roll back.')


def reset_seed(session, member):
    """Delete only manifest-owned synthetic fixtures, including FK cycles.

    A new reference from outside the manifest blocks reset, including subsequent
    user work on Xiaoming. No cascading delete and no guessing by display name.
    """
    if member.external_id != EXTERNAL_ID:
        raise ValueError('Only the explicitly marked Xiaoming synthetic member can be reset.')
    receipt = session.scalar(select(AuditLog).where(AuditLog.patient_id == member.id, AuditLog.action == MANIFEST))
    if not receipt:
        raise ValueError('Missing synthetic ownership manifest; reset refused.')
    data = dict(receipt.detail_json['rows'])
    data.setdefault('audit_logs', []).append([str(receipt.id)])
    owned = {}
    for name, rows in data.items():
        table = Base.metadata.tables[name]
        cols = list(table.primary_key.columns)
        owned[name] = {tuple(c.type.python_type(v) for c, v in zip(cols, key)) for key in rows}
    for table in Base.metadata.tables.values():
        for row in session.execute(select(table)).mappings():
            key = tuple(row[c.name] for c in table.primary_key)
            if key in owned.get(table.name, set()):
                continue
            for fk in table.foreign_keys:
                if (row[fk.parent.name],) in owned.get(fk.column.table.name, set()):
                    raise ValueError('New work references the demo: reset refused; preserve it or use a QA copy.')
    if session.bind.dialect.name != 'sqlite':
        raise ValueError('Explicit synthetic reset currently supports SQLite only.')
    session.connection().exec_driver_sql('PRAGMA defer_foreign_keys=ON')
    for name, keys in owned.items():
        table = Base.metadata.tables[name]
        for key in keys:
            session.execute(delete(table).where(*(c == v for c, v in zip(table.primary_key, key))))
    session.expunge_all()
    return owned


def seed_xiaoming(session, *, reset=False):
    before = inventory(session)
    existing = session.scalar(select(Patient).where(Patient.external_id == EXTERNAL_ID))
    removed = {}
    if existing and not reset:
        receipt = session.scalar(select(AuditLog).where(AuditLog.patient_id == existing.id, AuditLog.action == MANIFEST))
        if not receipt:
            raise ValueError('Existing Xiaoming has no completed seed receipt; refusing to overwrite.')
        return existing
    if existing:
        removed = reset_seed(session, existing)
    workflow = ManagementWorkflowService()
    supervisor = HealthOpsAgentSupervisor()
    risk_ops = RiskOperationsService()
    stages = []
    def save(row):
        session.add(row); session.flush(); return row
    def measurement(code, value, when, source='DEVICE', unit=None):
        receipt, _ = ingest_health_event(session, member_id=member.id,
            event_type=source+'_RAW_MEASUREMENT', event_category='NEW_INFORMATION',
            source_type=source, source_id=f'{EXTERNAL_ID}:{code}:{when.isoformat()}', occurred_at=when,
            payload_ref={'synthetic': True, 'measurement': {'metric': code, 'value': str(value),
                'unit': unit or REGISTRY[code].default_unit, 'observed_at': when.isoformat(),
                'source_name': '小明合成设备记录（DEMO）', 'synthetic': True}})
        assert receipt.route_action == 'STORE_ONLY'
        return session.scalar(select(Observation).where(Observation.patient_id == member.id, Observation.source_record_id == receipt.source_id))
    def document(title, when, kind='health_check_report'):
        return save(Document(patient_id=member.id, document_type=kind, title=title+'（合成演示）',
            storage_reference='synthetic://xiaoming/'+when.date().isoformat(), source='SYNTHETIC / DEMO', created_at=when))
    def rule(code, metric, level, value, operator, route):
        return save(RiskRule(name='合成演示：'+code, code=EXTERNAL_ID+'-'+code,
            applicable_device_class='ANY', canonical_code=metric, risk_level=level,
            condition_type='SYNTHETIC_TEST_THRESHOLD', threshold_config={'metric':metric,'value':value,'operator':operator,'unit':REGISTRY[metric].default_unit},
            window_config={}, action_type='SYNTHETIC_TEST_ONLY', scope='DEMO', review_status='APPROVED',
            reviewed_by=DOCTOR, source_reference='SYNTHETIC TEST fixture，仅用于小明历史回放；不是医学标准',
            recommended_route=route, is_active=False))
    def changes_for(day):
        with replay_time(session, at(day.month, day.day, day.year)):
            summary = daily_summary.calculate(session, member.id, day)
            rows = list(session.scalars(select(HealthEvent).where(HealthEvent.member_id == member.id,
                HealthEvent.event_type == 'MEANINGFUL_CHANGE', HealthEvent.status == 'PENDING')))
            for row in rows:
                dispatch_event(session, row, supervisor=supervisor)
            return summary, rows
    def resume_risk(risk):
        for goal in session.scalars(select(AgentGoal).where(AgentGoal.member_id == member.id, AgentGoal.status == 'WAITING_MANAGER')):
            if goal.context_json.get('risk_event_id') == str(risk.id):
                care_runtime.resume(session, goal, event_type='RISK_RESOLVED', source_id=risk.id)
                daily_care.advance(session, goal, supervisor)
                assert goal.status == 'COMPLETED'
    def link(trigger, *rows):
        return link_care_episode(session, member.id, trigger.id,
            links=[{'type':type(r).__name__,'id':str(r.id)} for r in rows], actor=OWNER, role='HEALTH_MANAGER')
    def complete_plain_tasks(text):
        for task in list(session.scalars(select(Task).where(Task.patient_id == member.id,
                Task.status.not_in(('COMPLETED','CANCELLED')), Task.risk_event_id.is_(None)))):
            TaskTransitionService().complete(session, task.id, actor=OWNER, outcome=text)

    with replay_time(session, at(10, 5, 2025)):
        member = save(Patient(display_name='小明', external_id=EXTERNAL_ID, sex='male', birth_date=date(1984,3,12), timezone='Asia/Shanghai'))
        ensure_member_agent(session, member.id)
        prior_doc = document('入组健康资料', at(10,5,2025))
        prior = HealthAssessmentService().create_assessment(session, member.id, title='入组健康参考', summary='演示会员：开始记录体重、睡眠和生活方式。',
            baseline={'weight':86.4,'sleep_duration':384}, created_by=OWNER, confirmed=True, cycle_year=2025,
            source_references={'document_ids':[str(prior_doc.id)],'manual_intake':{'recorded_by':OWNER}})
        prior.confirmed_at = prior.assessed_at = at(10,5,2025)
    with replay_time(session, at(1,5)):
        program = workflow.enroll(session, name='小明', member_id=member.id, start=date(2026,1,1), end=date(2026,12,31), owner=OWNER,
            goal='年度持续体重管理：从86kg向82kg推进，同时改善睡眠规律性')
        annual_doc = document('2026年度体检资料', at(1,5))
        bmi = (Decimal('86') / Decimal('1.75')**2).quantize(Decimal('.1'))
        for code, value in {'weight':86,'height':175,'bmi':bmi,'sleep_duration':384,'steps':5500,'systolic_bp':124,'diastolic_bp':78}.items():
            measurement(code, value, at(1,5))
        medication = save(MedicationPlan(patient_id=member.id, drug_name='演示既往用药A', dose='1', dose_unit='合成记录单位',
            frequency='按原资料记录', route='原资料未载明', start_date=date(2025,10,5), prescriber_name=DOCTOR,
            status='active'))
        baseline = HealthAssessmentService().create_assessment(session, member.id, title='2026年度健康基线',
            summary=f'合成演示：体重86kg，BMI {bmi}，睡眠6.4小时，日均5500步；不据此诊断。',
            baseline={'weight':86,'height':175,'bmi':float(bmi),'sleep_duration':384,'steps':5500,'systolic_bp':124,'diastolic_bp':78,
                'key_metrics':[{'metric':c,'value':v,'unit':REGISTRY[c].default_unit} for c,v in {'weight':86,'bmi':float(bmi),'sleep_duration':384}.items()],
                'source_reports':[{'document_id':str(annual_doc.id),'title':annual_doc.title}],
                'current_medications':[{'name':medication.drug_name,'source_entity_id':str(medication.id)}]},
            created_by=OWNER, cycle_year=2026,
            management_cycle_id=session.scalar(select(AnnualHealthAccount.id).where(AnnualHealthAccount.patient_id==member.id,AnnualHealthAccount.year==2026)),
            source_references={'source_document_ids':[str(annual_doc.id)],'manual_intake':{'recorded_by':OWNER}})
        HealthAssessmentService().confirm(session, baseline.id, OWNER)
        baseline.assessed_at = baseline.confirmed_at = at(1,5)
    with replay_time(session, at(2,1)):
        questionnaire = document('会员生活方式与健康问卷', at(2,1), 'questionnaire')
        answers = {
            '基础资料':{'display_name':'小明','birth_date':'1984-03-12','sex':'male'},
            '家族健康史':[{'疾病类别':'自述','具体疾病':'未报告明确家族疾病','患病家属':'未指明','备注':'合成问卷自述，不代表排除风险'}],
            '个人病史':[{'疾病或问题':'曾有睡眠不规律','是否存在':'自述存在','确诊来源':'会员合成问卷，无医学诊断','确诊时间':'2025-10','持续管理':'生活方式跟踪','备注':'不得据此诊断'}],
            '过敏史':[{'类别':'自述','名称':'未报告已知过敏','过敏反应':'未报告','来源':questionnaire.title}],
            '当前用药 / 营养补充':[{'名称':medication.drug_name,'剂量':'1','单位':'合成记录单位','频次':'按原资料记录','途径':'未载明','开始日期':'2025-10-05','处方来源':annual_doc.title}],
            '生活方式':{'睡眠':'约6.4小时，轮班时不规律','运动':'每周步行3次','饮食':'晚间偶有咖啡','烟草':'自述不吸烟','饮酒':'偶尔少量饮酒','工作压力':'轮班工作','休假':'有计划','生活规律':'希望改善'},
            '会员重点关注':{'concern':'年度持续体重管理：从86kg向82kg推进，同时改善睡眠规律性'},
            '专项症状评估':[{'症状':'睡眠不规律','原始回答':'偶有夜班','频率或严重度':'自述偶发','原始分数':''}],
        }
        for step in STEPS[:-1]:
            workflow.save_intake(session, member.id, 2026, step, answers.get(step, [] if step in TABLE_FIELDS else {}), OWNER)
        intake = session.scalar(select(IntakeAssessment).where(IntakeAssessment.patient_id==member.id))
        workflow.submit_intake(session, member.id, intake.id, '小明（合成会员）')
        for title, start, end in [('阶段1 · 建立生活方式基线',date(2026,2,1),date(2026,2,28)),
                ('阶段2 · 稳定执行减重计划',date(2026,3,1),date(2026,7,31)),
                ('阶段3 · 睡眠问题处理',date(2026,8,1),date(2026,9,30)),
                ('阶段4 · 年度阶段复盘',date(2026,10,1),date(2026,12,31))]:
            stages.append(workflow.add_phase(session,member.id,program.id,title=title,goal=program.main_goal,
                content='跟踪体重、活动与睡眠；依据会员反馈调整生活方式，医学问题交医生。',start=start,end=end,owner=OWNER))
        workflow.review_intake(session,member.id,intake.id,focus='体重管理与睡眠规律性',missing='',tests='',medical_question='',
            annual_focus=program.main_goal,actor=OWNER,decision='CONFIRM')
        goal = management_goals.current(session, program.id)
        goal.start_date=date(2026,2,1);goal.baseline_value=Decimal('86')
        management_goals.confirm_goal(session,goal,actor=OWNER,role='HEALTH_MANAGER',target='82',target_date=date(2026,12,31))
        management_goals.confirm_plan(session,goal,actor=OWNER,role='HEALTH_MANAGER')
        complete_plain_tasks('会员与健管已核对合成基线，分别确认目标与计划。')
        problem=save(HealthProblem(patient_id=member.id,program_id=program.id,title='生活方式管理',description='合成会员确认的体重与睡眠关注事项，非诊断',source='SYNTHETIC',owner=OWNER,severity='LOW'))
        plan=save(ManagementPlan(patient_id=member.id,program_id=program.id,health_problem_id=problem.id,title='体重与睡眠生活方式计划',
            content='按已确认计划跟踪体重与日常活动。',source='MANAGER',owner=OWNER,status='ACTIVE',start_date=date(2026,2,1),adjusted_by=OWNER,adjusted_at=at(2,1)))
        green_rule=rule('计划内正常进展','weight','GREEN',85.8,'<=','AUTO')
        sleep_rule=rule('睡眠下降需健管核实','sleep_duration','YELLOW',330,'<=','HEALTH_MANAGER')
        doctor_rule=rule('复查变化请医生确认监测安排','systolic_bp','YELLOW',135,'>=','DOCTOR')
        sleep_trend=save(ManagementRule(name='合成演示：睡眠较个人近7日水平下降',code=EXTERNAL_ID+'-sleep-trend',
            canonical_code='sleep_duration',condition_type='PERCENTAGE_DECLINE',
            threshold_config={'value':-15,'operator':'<=','unit':'minutes'},window_config={'summary_minimum_days':7},
            review_status='APPROVED',source_reference='SYNTHETIC DEMO fixture，仅在离线生成期间启用，不是医学标准',is_active=False))

    sleep_change=doctor_change=green_change=None
    sleep_agent=doctor_agent=sleep_risk=doctor_risk=None
    review=follow_task=recheck=waiter=candidate=confirmed=adjustment=None

    def sleep_contact():
        nonlocal adjustment
        with replay_time(session,at(8,11)):
            raw_note='小明最近连续夜班，平均睡眠只有5个多小时，饮食方面晚上咖啡喝得比较多，准备先调整夜间咖啡和休息时间。两周后随访睡眠记录。（合成演示）'
            communication=communications.record(session,member_id=member.id,program_id=program.id,raw_note=raw_note,
                actor=OWNER,role='HEALTH_MANAGER',channel='电话',request_key=EXTERNAL_ID+':sleep-contact',occurred_at=at(8,11))
            from executive_health_ai.services.care_result_extraction import rules
            communication.structured_summary={**communication.structured_summary,
                'lifestyle_candidates':rules(raw_note,date(2026,8,11))['facts'],
                'extraction_method':'existing deterministic care-result rules'}
            communications.confirm(session,communication,actor=OWNER,role='HEALTH_MANAGER')
            log=session.get(ManagementLog,communication.log_id)
            log.related_risk_id=sleep_risk.id
            risk_ops.record_contact(session,sleep_risk.id,OWNER,'电话','已联系',raw_note)
            adjustment=risk_ops.adjust_management(session,sleep_risk.id,OWNER,'减少晚间咖啡，按夜班安排休息时间；两周后核对睡眠记录。','会员反馈连续夜班',at(8,25))
            chronic_care.adjust_management_plan(session,plan,OWNER,'会员夜班导致执行受限','减少夜间咖啡，按轮班安排休息；继续跟踪体重与睡眠。')
            link(sleep_change,communication,log,adjustment,plan,goal)
    def sleep_outcome():
        with replay_time(session,at(9,5)):
            risk_ops.complete_management_task(session,sleep_risk.id,OWNER,'会员反馈已减少晚间咖啡；后续观察到睡眠数据恢复至6.2小时。',adjustment.id)
            outcome=chronic_care.record_outcome_evaluation(session,program,'睡眠时长','5.4','6.2','小时','UP',OWNER,
                '合成设备记录：2026-08-10与2026-09-05；关联随访原文和计划调整。','IMPROVED',
                notes='后续观察到数据较此前恢复；不证明干预因果，不代表医学治愈。',evaluation_date=date(2026,9,5),care_trigger_id=sleep_change.id)
            risk_ops.close(session,sleep_risk.id,OWNER,'已完成健管跟踪；后续观察到恢复趋势，持续管理。')
            resume_risk(sleep_risk)

    def doctor_decision():
        nonlocal review,follow_task,recheck,waiter
        with replay_time(session,at(9,11)):
            review=session.get(DoctorReview,UUID(doctor_agent.context_json['review_id']))
            review.question_for_doctor='合成家庭复查记录与近期水平有变化，是否继续既定观察与复查安排？'
            opinion='合成医生意见：继续观察当前指标变化，按既定计划两周后完成后续复查；本次不调整用药，不据单次设备记录作诊断。'
            review,follow_task=care_commands.complete_review(session,review,DOCTOR,'全科（演示）',opinion,'按既定计划核对后续复查结果。',at(9,25))
            returned,_=ingest_health_event(session,member_id=member.id,event_type='DOCTOR_REVIEW_COMPLETED',event_category='NEW_INFORMATION',
                source_type='SYSTEM',source_id=str(review.id),payload_ref={})
            assert returned.goal_id==doctor_agent.id and doctor_agent.status=='WAITING_MANAGER'
            doctor_note=communications.record(session,member_id=member.id,program_id=program.id,raw_note=opinion,actor=OWNER,
                role='HEALTH_MANAGER',source='DOCTOR',doctor_review_id=review.id,request_key=EXTERNAL_ID+':doctor-note',occurred_at=at(9,11))
            communications.confirm(session,doctor_note,actor=OWNER,role='HEALTH_MANAGER')
            recheck=session.get(RecheckPlan,UUID(next(a['id'] for a in doctor_note.related_actions if a['kind']=='recheck')))
            waiter=care_runtime.start(session,supervisor,member_id=member.id,kind='DAILY_CARE',source_id=recheck.id,
                title='等待既定复查日期',context={'program_id':str(program.id),'event_payload':{'work_kind':'recheck','work_id':str(recheck.id),'due_at':at(9,25).isoformat()}},owner=OWNER)
            care_runtime.wait(session,waiter,'WAITING_TIME',next_action='等待9月25日复查结果',due=at(9,25),expected_event='TIME_DUE',expected_source=recheck.id)
            link(doctor_change,review,recheck,follow_task,doctor_note,session.get(ManagementLog,doctor_note.log_id))
    def recheck_result():
        with replay_time(session,at(9,25)):
            due,_=ingest_health_event(session,member_id=member.id,event_type='TIME_DUE',event_category='TIME_DUE',source_type='SYSTEM',
                source_id=str(recheck.id),occurred_at=at(9,25),payload_ref={'resume_goal_id':str(waiter.id)})
            assert waiter.status=='WAITING_MANAGER'
            result_doc=document('9月家庭监测复查结果',at(9,25))
            for state in list(RECHECK_STATES)[1:]:
                workflow.advance_recheck(session,member.id,recheck.id,status=state,actor=OWNER,
                    result='后续观察到家庭测量124/78mmHg，按医生已确认安排继续观察；合成结果，不作为诊断。',document_id=result_doc.id)
            care_runtime.resume(session,waiter,event_type='MANAGEMENT_ITEM_COMPLETED',source_id=recheck.id)
            daily_care.advance(session,waiter,supervisor)
            followup=risk_ops.record_follow_up(session,doctor_risk.id,OWNER,'已核对复查来源并落实医生后续观察安排。',follow_task.id)
            doctor_outcome=chronic_care.record_outcome_evaluation(session,program,'家庭收缩压','138','124','mmHg','DOWN',OWNER,
                '合成9月10日设备测量与9月25日复查结果；仅描述前后观察。','IMPROVED',notes='后续观察到数值回落；不能据此判断治疗效果。',
                evaluation_date=date(2026,9,25),care_trigger_id=doctor_change.id)
            link(doctor_change,followup,doctor_outcome)
            risk_ops.close(session,doctor_risk.id,OWNER,'医生意见和后续复查已落实，继续原管理计划。')
            resume_risk(doctor_risk)

    def correction():
        nonlocal candidate,confirmed
        with replay_time(session,at(5,10)):
            error_doc=document('体重测量核对资料',at(5,10))
            run=save(ReportExtractionRun(document_id=error_doc.id,patient_id=member.id,parser_version='synthetic-error-fixture-v1',
                canonical_registry_version='1',file_hash='synthetic-xiaoming-weight',file_type='txt',detected_report_date=date(2026,5,10)))
            candidate=save(ReportExtractionCandidate(extraction_run_id=run.id,document_id=error_doc.id,patient_id=member.id,
                candidate_type='OBSERVATION',canonical_code='weight',raw_name='体重',raw_value='83.6',normalized_value='86.3',unit='kg',
                extraction_method='LLM',evidence_text='SYNTHETIC / DEMO 原始体重：83.6 kg'))
            parsing=ReportParsingService()
            parsing.correct_candidate(session,candidate,OWNER,canonical='weight',value='83.6',unit='kg',reason='合成错误演示：核对原文，保留86.3候选版本。')
            confirmed=parsing.confirm_candidate(session,candidate,OWNER)
            chronic_care.record_outcome_evaluation(session,program,'体重','86','83.6','kg','DOWN',OWNER,
                '年度基线与人工核对后的合成体重资料 '+str(error_doc.id),'IMPROVED',evaluation_date=date(2026,5,10))

    def green_check():
        with replay_time(session,at(3,5)):
            checked=chronic_care.create_program_task(session,program,'计划内自动数据检查','核对已批准计划内的指标和下一次检查时间。',at(3,5),'健康管理助手',OWNER)
            checked.responsible_role='system';checked.source='approved_plan_check';checked.management_plan_id=plan.id
            event_row,_=ingest_health_event(session,member_id=member.id,event_type='TIME_DUE',event_category='TIME_DUE',
                source_type='SYSTEM',source_id='xiaoming-green-plan-check',occurred_at=at(3,5),
                payload_ref={'work_kind':'task','work_id':str(checked.id),'due_at':at(3,5).isoformat()})
            automatic=session.get(AgentGoal,event_row.goal_id)
            assert checked.status=='COMPLETED' and automatic.status=='COMPLETED',automatic.context_json
            base={'program_id':str(program.id),'source_reference':str(plan.id),'management_plan_id':str(plan.id)}
            supervisor.registry.execute(session,'create_followup',automatic,{**base,'idempotency_key':EXTERNAL_ID+':green-next',
                'title':'下一次计划内数据核对','instruction':'继续已确认计划中的例行指标核对，不要求会员额外补资料。','due_at':at(4,5).isoformat()})
            supervisor.registry.execute(session,'write_management_log',automatic,{**base,'idempotency_key':EXTERNAL_ID+':green-log',
                'data':{'category':'数据跟进','channel':'系统记录','member_issue':'计划内数据检查到期',
                    'manager_action':'系统自动推进已批准计划','result':'已核对数据和目标进度，已安排下次低风险检查；本次无需人工。',
                    'next_action':'按已确认计划继续核对','owner':OWNER}})

    # Genuine stage summaries, human confirmation and existing phase transition services.
    def stage_transition(index,when):
        with replay_time(session,when):
            complete_plain_tasks('合成历史回放：已核对并完成本阶段既定运营事项。')
            stage_agent=daily_care.maybe_stage(session,member.id,program.id,stages[index].id,supervisor)
            assert stage_agent and stage_agent.status=='WAITING_MANAGER'
            loop=ManagementActionLoop();state=loop.project(session,member.id,program.id)
            content=loop.stage_summary(state)
            content['实际完成']='已完成本阶段数据核对、随访与既定计划。'+content.get('实际完成','')
            content['下一阶段建议']=stages[index+1].goal
            stage_review=loop.review_stage(session,member.id,program.id,phase_id=stages[index].id,content=content,actor=OWNER)
            stage_review.reviewed_at=when
            draft=loop.next_phase_draft(loop.project(session,member.id,program.id))
            loop.enter_next_phase(session,member.id,program.id,stages[index].id,actor=OWNER,
                title=draft['title'],goal=draft['goal'],content=draft['content'],start=draft['start'],end=draft['end'],action='核对下一阶段指标与生活方式记录')
            assert stage_agent.status=='COMPLETED'
            if index==2:link(sleep_change,stage_review)
    # Replay one day at a time: no future measurements, notes or decisions in Agent context.
    day=date(2026,2,1)
    while day<=AS_OF:
        elapsed=(day-date(2026,2,1)).days
        weight=round(86-3.6*elapsed/(AS_OF-date(2026,2,1)).days,2)
        sleep=390 if day<date(2026,8,10) else 324 if day<=date(2026,8,19) else min(372,324+3*(day-date(2026,8,19)).days)
        bp=138 if date(2026,9,10)<=day<date(2026,9,20) else 124
        values={'sleep_duration':sleep,'steps':5500+min(2200,elapsed*12),'resting_heart_rate':68,'exercise_minutes':25,
            'weight':weight,'bmi':round(weight/1.75**2,1),'systolic_bp':bp,'diastolic_bp':78}
        with replay_time(session,at(day.month,day.day)):
            for code,value in values.items():measurement(code,value,at(day.month,day.day),source='MOBILE' if code=='steps' else 'DEVICE')
        green_rule.is_active=day<=date(2026,5,31)
        sleep_rule.is_active=date(2026,8,1)<=day<=date(2026,8,31)
        sleep_trend.is_active=sleep_rule.is_active
        doctor_rule.is_active=date(2026,9,1)<=day<=date(2026,9,30)
        session.flush()
        summary,changes=changes_for(day)
        for change in changes:
            metric=change.payload_ref['change']['metric']
            if metric=='sleep_duration' and sleep_change is None:
                sleep_change=change;sleep_agent=session.get(AgentGoal,change.goal_id)
                assert sleep_agent.status=='WAITING_MANAGER',sleep_agent.context_json
                sleep_risk=session.get(RiskEvent,UUID(sleep_agent.context_json['risk_event_id']))
            if metric=='systolic_bp' and doctor_change is None:
                doctor_change=change;doctor_agent=session.get(AgentGoal,change.goal_id)
                assert doctor_agent.status=='WAITING_DOCTOR',doctor_agent.context_json
                doctor_risk=session.get(RiskEvent,UUID(doctor_agent.context_json['risk_event_id']))
            if metric=='weight' and green_change is None:green_change=change
        hooks={date(2026,3,5):green_check,date(2026,5,10):correction,date(2026,8,11):sleep_contact,date(2026,9,5):sleep_outcome,
            date(2026,9,11):doctor_decision,date(2026,9,25):recheck_result}
        if day in hooks:hooks[day]()
        for i,end in enumerate((date(2026,2,28),date(2026,7,31),date(2026,9,30))):
            if day==end:stage_transition(i,at(day.month,day.day))
        day+=timedelta(days=1)
    for r in (green_rule,sleep_rule,doctor_rule,sleep_trend):r.is_active=False
    assert sleep_change and doctor_change and green_change, 'Deterministic summary scenarios did not trigger.'
    with replay_time(session,at(10,4)):
        complete_plain_tasks('已完成阶段交接，按确认计划继续管理。')
        next_task=care_commands.schedule_followup(session,program,title='10月15日核对体重与睡眠随访',instruction='核对当前指标、执行反馈及下一次计划安排。',due_at=at(10,15),owner=OWNER)
        for job in session.scalars(select(SummaryWorkItem).where(SummaryWorkItem.patient_id==member.id)):
            daily_summary.calculate(session,member.id,job.summary_date,emit=False);job.dirty=False
        synchronize(session,member.id)
    session.flush()
    after=inventory(session)
    assert_preserved(before,after,removed=removed)
    created={name:[[str(v) for v in key] for key in rows if key not in before[name] or key in removed.get(name,set())]
        for name,rows in after.items()}
    save(AuditLog(patient_id=member.id,actor=OWNER,actor_role='ADMIN',action=MANIFEST,entity_type='Patient',entity_id=str(member.id),
        detail_json={'synthetic':True,'as_of':str(AS_OF),'rows':{k:v for k,v in created.items() if v},
            'sleep_change':str(sleep_change.id),'doctor_change':str(doctor_change.id),'green_change':str(green_change.id),
            'candidate':str(candidate.id),'confirmed_observation':str(confirmed.id),'doctor_goal':str(doctor_agent.id),
            'recheck_goal':str(waiter.id),'next_task':str(next_task.id)}))
    return member


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--database',required=True,help='Existing SQLite database; never creates or rebuilds it')
    parser.add_argument('--reset',action='store_true',help='Reset only untouched manifest-owned Xiaoming fixtures; backup first')
    args=parser.parse_args()
    path=Path(args.database).resolve()
    if not path.is_file() or path.suffix.lower()!='.db':raise SystemExit('Expected an existing .db file.')
    from executive_health_ai.services.schema_readiness import require_longitudinal_schema
    url='sqlite:///'+path.as_posix();require_longitudinal_schema(url)
    folder=Path(__file__).resolve().parents[1]/'.runtime'/'xiaoming-demo'
    folder.mkdir(parents=True,exist_ok=True)
    stamp=datetime.now().strftime('%Y%m%d-%H%M%S-%f')
    backup=folder/(path.stem+'-before-'+stamp+'.db')
    with sqlite3.connect(path.as_uri()+'?mode=ro',uri=True) as source,sqlite3.connect(backup) as target:source.backup(target)
    engine=create_database_engine(url)
    with Session(engine) as session:
        member=seed_xiaoming(session,reset=args.reset)
        session.flush()
        if session.connection().exec_driver_sql('PRAGMA foreign_key_check').fetchall():
            raise RuntimeError('Foreign key verification failed; seed transaction rolled back.')
        member_id=str(member.id);session.commit()
    with sqlite3.connect(path.as_uri()+'?mode=ro',uri=True) as db:
        assert db.execute('PRAGMA integrity_check').fetchone()==('ok',)
        assert not db.execute('PRAGMA foreign_key_check').fetchall()
    print(json.dumps({'member_id':member_id,'name':'小明','synthetic':True,'database':str(path),'backup':str(backup)},ensure_ascii=False))
    engine.dispose()


if __name__=='__main__':
    sys.stdout.reconfigure(encoding='utf-8')
    main()
