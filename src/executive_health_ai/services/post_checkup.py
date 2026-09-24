"""Business adapters for report-to-care preparation. No autonomous medical writes.

The caller owns the transaction. Drafts live on the existing AgentGoal; official
care records are created only through this and the existing management services.
"""
from datetime import date, datetime, time, timedelta, timezone
from decimal import Decimal, InvalidOperation
from uuid import UUID

from sqlalchemy import select, update, func

from executive_health_ai.models import (Document, ReportExtractionRun, ReportExtractionCandidate,
    Patient, HealthProgram, HealthProblem, MedicationPlan, DoctorReview, Task, FollowUp,
    RiskEvent, ServiceCatalogItem, ServiceRequest, HealthEvent)
from executive_health_ai.models.management_workflow import IntakeAssessment, RecheckPlan, ManagementLog
from executive_health_ai.models.base import utc_now
from executive_health_ai.services.product_projection import ProductProjectionService, observations
from executive_health_ai.services.management_workflow import ManagementWorkflowService, owned, required, task, audit
from executive_health_ai.services.baseline_visualization import BaselineVisualizationService
from executive_health_ai.services.health_visualization import metric_label
from executive_health_ai.integrations.codes import canonical_metric_key
from executive_health_ai.services.knowledge_retrieval import KnowledgeRetrievalService


def require_role(role, expected, actor):
    if role != expected:
        raise PermissionError('当前身份不能执行此操作。')
    required(actor, '操作人')


def numeric(value):
    try:
        result = Decimal(str(value))
        return float(result) if result.is_finite() else None
    except (InvalidOperation, ValueError, TypeError):
        return None


class PostCheckupCareService:
    def confirm_report(self, session, goal, *, actor, role):
        """Explicit manager confirmation uses the existing candidate/risk service."""
        require_role(role, 'HEALTH_MANAGER', actor)
        from executive_health_ai.services.report_parsing import ReportParsingService
        parser = ReportParsingService()
        context = goal.context_json
        run = session.scalar(select(ReportExtractionRun).where(ReportExtractionRun.document_id == UUID(goal.source_id))
                             .order_by(ReportExtractionRun.created_at.desc()))
        if run and str(run.id) != context['report']['run_id']:
            raise ValueError('报告资料已更新，请重新读取后确认。')
        candidates = list(session.scalars(select(ReportExtractionCandidate).where(
            ReportExtractionCandidate.document_id == UUID(goal.source_id),
            ReportExtractionCandidate.extraction_run_id == UUID(context['report']['run_id']))))
        for candidate in candidates:
            if candidate.patient_id != goal.member_id:
                raise ValueError('报告资料不属于此会员。')
            if candidate.status in {'PENDING_REVIEW', 'CORRECTED'}:
                if candidate.candidate_type == 'OBSERVATION' and parser.possible_duplicate_observation(session, candidate):
                    raise ValueError('报告包含可能已入档的指标，请在原报告中核对并处理重复项。')
                parser.confirm_candidate(session, candidate, actor)
        risks = list(session.scalars(select(RiskEvent).where(RiskEvent.patient_id == goal.member_id,
                         RiskEvent.status.not_in(('CLOSED', 'DISMISSED_DATA_ISSUE')))))
        return {'confirmed_candidates': len(candidates),
                'requires_medical_review': any(r.requires_doctor_review or r.risk_level == 'RED' for r in risks)}

    def context(self, session, goal):
        report = owned(session, Document, goal.source_id, goal.member_id)
        if report.document_type != 'health_check_report':
            raise ValueError('此资料不是体检报告。')
        member = session.get(Patient, goal.member_id)
        view = ProductProjectionService().member(session, goal.member_id)
        program = view.program
        run = session.scalar(select(ReportExtractionRun).where(ReportExtractionRun.document_id == report.id)
                             .order_by(ReportExtractionRun.created_at.desc()))
        query = select(ReportExtractionCandidate).where(ReportExtractionCandidate.document_id == report.id,
                                                        ReportExtractionCandidate.status != 'REJECTED')
        if run:
            query = query.where(ReportExtractionCandidate.extraction_run_id == run.id)
        candidates = list(session.scalars(query))
        at = datetime.combine(run.detected_report_date, time(9), timezone.utc) if run and run.detected_report_date else report.created_at
        year = program.cycle_year or program.start_date.year if program else at.year
        try:
            baseline = BaselineVisualizationService().build(session, member.id, cycle_year=year)
        except ValueError:
            baseline = None
        metrics = [{ 'code': m.code, 'label': m.label, 'value': numeric(m.value), 'unit': m.unit,
                     'at': m.observed_at.isoformat() if m.observed_at else None} for m in baseline.metrics] if baseline else []
        history = observations(session, member.id)
        findings = []
        for row in candidates:
            value = numeric(row.normalized_value)
            if value is None or not row.canonical_code:
                continue
            code = canonical_metric_key(row.canonical_code)
            reference = next((m for m in metrics if m['code'] == code and m['unit'] == (row.unit or '')), None)
            base = reference['value'] if reference else None
            points = [{'at': o.observed_at.isoformat(), 'value': float(o.value_numeric), 'source': '已确认健康记录'}
                      for o in history if canonical_metric_key(o.metric_code) == code and o.unit == row.unit and o.observed_at < at]
            points.append({'at': at.isoformat(), 'value': value, 'source': '本次报告 · 待健管核对'})
            findings.append({'candidate_id': str(row.id), 'code': code, 'label': metric_label(code),
                'value': value, 'unit': row.unit or '', 'baseline': base,
                'delta': round(value-base, 4) if base is not None else None,
                'status': '报告标记异常，待核对' if row.abnormal_flag else '待核对',
                'evidence': row.evidence_text or '', 'page': row.source_page, 'points': points})
        intake = session.scalar(select(IntakeAssessment).where(IntakeAssessment.patient_id == member.id,
                                                               IntakeAssessment.cycle_year == year))
        snapshot = baseline.assessment.baseline_json if baseline else {}
        intake_fields = intake.responses if intake else snapshot.get('member_reported', {}).get('fields', {})
        recorded_problems = list(session.scalars(select(HealthProblem).where(HealthProblem.patient_id == member.id,
            HealthProblem.source != 'post_checkup_care').order_by(HealthProblem.opened_at.desc()).limit(30)))
        procedures = list(session.scalars(select(HealthEvent).where(HealthEvent.patient_id == member.id,
            HealthEvent.event_type.in_(('surgery', 'hospitalization', 'procedure'))).order_by(HealthEvent.start_at.desc()).limit(20)))
        medicines = list(session.scalars(select(MedicationPlan).where(MedicationPlan.patient_id == member.id,
                                                                      func.lower(MedicationPlan.status) == 'active')))
        risks = list(session.scalars(select(RiskEvent).where(RiskEvent.patient_id == member.id,
                          RiskEvent.status.not_in(('CLOSED', 'DISMISSED_DATA_ISSUE')))))
        prior_reports = list(session.scalars(select(Document).where(Document.patient_id == member.id,
                                      Document.document_type == 'health_check_report', Document.id != report.id)
                                      .order_by(Document.created_at.desc()).limit(10)))
        return {'program_id': str(program.id) if program else None, 'owner': program.owner if program else None,
            'member': {'name': member.display_name, 'birth_date': str(member.birth_date or ''),
                       'sex': member.sex, 'timezone': member.timezone,
                       'history': [{'title': p.title, 'description': p.description, 'status': p.status} for p in recorded_problems] or snapshot.get('health_problems', []),
                       'intake': intake_fields,
                       'allergies': intake_fields.get('过敏史') or snapshot.get('allergies', []),
                       'procedures': [{'description': p.description, 'occurred_at': p.start_at.isoformat()} for p in procedures],
                       'medications': [{'name': m.drug_name, 'dose': m.dose, 'unit': m.dose_unit, 'frequency': m.frequency} for m in medicines]},
            'report': {'id': str(report.id), 'title': report.title, 'at': at.isoformat(), 'status': report.status,
                       'run_id': str(run.id) if run else None,
                       'narrative': [{'text': r.summary or r.evidence_text or '', 'page': r.source_page,
                                      'candidate_id': str(r.id)} for r in candidates if r.candidate_type != 'OBSERVATION']},
            'structured': bool(candidates) and report.status != 'OCR_REQUIRED', 'findings': findings,
            'baseline': {'id': str(baseline.assessment.id), 'year': year, 'metrics': metrics} if baseline else None,
            'history_reports': [{'title': d.title, 'at': d.created_at.isoformat(), 'id': str(d.id)} for d in prior_reports],
            'recent_health_data': [{'label': metric_label(canonical_metric_key(o.metric_code)), 'value': float(o.value_numeric),
                                    'unit': o.unit, 'at': o.observed_at.isoformat()} for o in history[-50:]],
            'management': {'focus': program.main_goal if program else '',
                           'open_items': [{'title': t.title, 'owner': t.assignee, 'due': str(t.due_at or '')} for t in view.active_tasks],
                           'risks': [{'id': str(r.id), 'level': r.risk_level} for r in risks]},
            'requires_medical_review': any(r.requires_doctor_review or r.risk_level == 'RED' for r in risks)}

    def knowledge(self, session, context):
        queries = list(dict.fromkeys(f['label'] for f in context.get('findings', [])))[:8]
        hits = {}
        for query in queries:
            for hit in KnowledgeRetrievalService().search(session, query, categories=('CLINICAL_GUIDELINE', 'PATIENT_EDUCATION'), limit=3):
                hits[str(hit.chunk.id)] = {**hit.citation(), 'scope': hit.document.category}
        return list(hits.values())[:8]

    def request_review(self, session, goal, *, actor, role, doctor, question):
        require_role(role, 'HEALTH_MANAGER', actor)
        doctor = required(doctor, '责任医生')
        if doctor in {'待分配医生', '待分配', '内部医生'}:
            raise ValueError('请明确责任医生后提交。')
        context = goal.context_json
        if context.get('review_id'):
            return owned(session, DoctorReview, context['review_id'], goal.member_id)
        program = owned(session, HealthProgram, context['program_id'], goal.member_id)
        # A management question is not a medical diagnosis or a RiskEvent.
        problem = HealthProblem(patient_id=goal.member_id, program_id=program.id, title='体检后医学问题待判断',
            description=required(question, '需要医生判断的问题'), source='post_checkup_care', owner=actor)
        session.add(problem); session.flush()
        brief = '\n'.join(f"{f['label']}：{f['value']} {f['unit']}；年度基线 {f['baseline'] if f['baseline'] is not None else '未建立'}" for f in context['findings'])
        review = DoctorReview(patient_id=goal.member_id, program_id=program.id, health_problem_id=problem.id,
            doctor_name=doctor, department='全科 / 健康管理', doctor_brief=brief,
            question_for_doctor=question, opinion='', status='PENDING')
        session.add(review); audit(session, goal.member_id, actor, 'post_checkup_review_requested', review)
        return review

    def submit_review(self, session, goal, *, actor, role, judgement, recommendation, recheck,
                      suggested_date, recheck_title='', followup_date=None, notes=''):
        require_role(role, 'DOCTOR', actor)
        review = owned(session, DoctorReview, goal.context_json.get('review_id'), goal.member_id)
        if review.doctor_name != actor:
            raise PermissionError('请由本次责任医生提交判断。')
        if review.status == 'CONFIRMED':
            return review
        if goal.current_stage != 'WAITING_DOCTOR_REVIEW':
            raise ValueError('此报告当前不在医生复核阶段。')
        judgement, recommendation = required(judgement, '医学判断'), required(recommendation, '建议')
        due = date.fromisoformat(str(suggested_date))
        follow = date.fromisoformat(str(followup_date or suggested_date))
        if due < date.today() or follow < date.today():
            raise ValueError('建议日期不能早于今天。')
        if recheck:
            required(recheck_title, '复查项目')
        claim = session.execute(update(DoctorReview).where(DoctorReview.id == review.id, DoctorReview.status == 'PENDING').values(status='CONFIRMED'))
        if claim.rowcount != 1:
            session.refresh(review)
            return review
        review.opinion = judgement + '\n建议：' + recommendation + ('\n其他说明：' + notes if notes else '')
        review.status, review.reviewed_at = 'CONFIRMED', utc_now()
        problem = owned(session, HealthProblem, review.health_problem_id, goal.member_id)
        if problem.source == 'post_checkup_care':
            problem.status, problem.closed_at = 'CLOSED', review.reviewed_at
        goal.context_json = {**goal.context_json, 'doctor_result': {'judgement': judgement,
            'recommendation': recommendation, 'recheck': bool(recheck), 'recheck_title': recheck_title,
            'suggested_date': due.isoformat(), 'followup_date': follow.isoformat(), 'notes': notes}}
        audit(session, goal.member_id, actor, 'post_checkup_doctor_judgement', review, 'doctor')
        from executive_health_ai.services.event_service import EventService
        from executive_health_ai.agent.supervisor import HealthOpsAgentSupervisor
        event, _ = EventService().publish(session, event_type='DOCTOR_REVIEW_COMPLETED', member_id=goal.member_id,
            source_type='doctor_review', source_id=str(review.id), metadata={'goal_id': str(goal.id), 'actor': actor},
            payload_summary='体检后医学判断已提交')
        HealthOpsAgentSupervisor().receive_event(session, event)
        return review

    def validate_actions(self, session, goal, actions):
        if not actions or len(actions) > 20:
            raise ValueError('请保留 1 至 20 项后续安排。')
        clean = []
        for row in actions:
            kind = row.get('kind')
            if kind not in {'MANAGEMENT', 'FOLLOWUP', 'RECHECK', 'SERVICE'}:
                raise ValueError('不支持此行动类型。')
            due = date.fromisoformat(str(row.get('due', '')))
            if due < date.today():
                raise ValueError('安排日期不能早于今天。')
            if kind == 'RECHECK' and not goal.context_json.get('doctor_result', {}).get('recheck'):
                raise ValueError('复查项目需要本次医生的明确建议。')
            item = {'title': required(row.get('title'), '行动'), 'kind': kind, 'due': due.isoformat(),
                    'owner': required(row.get('owner'), '负责人'), 'evidence': required(row.get('evidence'), '依据')}
            if kind == 'SERVICE':
                catalog = session.scalar(select(ServiceCatalogItem).where(ServiceCatalogItem.code == row.get('service_code')))
                if not catalog:
                    raise ValueError('请填写有效的服务目录编号。')
                item['service_id'] = str(catalog.id)
            clean.append(item)
        return clean

    def create_actions(self, session, goal, *, actions, actor, role):
        require_role(role, 'HEALTH_MANAGER', actor)
        context = goal.context_json
        if goal.current_stage != 'CREATING_ACTIONS' or not context.get('manager_confirmed'):
            raise ValueError('请先完成报告确认和最终行动确认。')
        program = owned(session, HealthProgram, context['program_id'], goal.member_id)
        clean = self.validate_actions(session, goal, actions)
        service = ManagementWorkflowService()
        refs = {'tasks': [], 'rechecks': [], 'followups': [], 'services': [], 'logs': []}
        review = owned(session, DoctorReview, context['review_id'], goal.member_id) if context.get('review_id') else None
        for index, item in enumerate(clean):
            due = datetime.combine(date.fromisoformat(item['due']), time(9), timezone.utc)
            source = f'post_checkup:{goal.id}:{index}'
            action = task(session, goal.member_id, program.id, item['title'], item['evidence'], item['owner'], due, source)
            refs['tasks'].append(str(action.id))
            if item['kind'] == 'RECHECK':
                check = service.create_recheck(session, goal.member_id, program.id, title=item['title'], reason=item['evidence'],
                    planned_at=due, owner=item['owner'], doctor_review_id=review.id if review else None)
                session.flush(); refs['rechecks'].append(str(check.id))
            elif item['kind'] == 'FOLLOWUP':
                problem_id = review.health_problem_id if review else None
                if problem_id is None:
                    problem = HealthProblem(patient_id=goal.member_id, program_id=program.id, title='体检后健康管理跟进',
                        description='已由健管确认的报告准备记录，非医学诊断', owner=item['owner'], source='post_checkup_care',
                        status='CLOSED', closed_at=utc_now())
                    session.add(problem); session.flush(); problem_id = problem.id
                follow = FollowUp(patient_id=goal.member_id, health_problem_id=problem_id, task_id=action.id,
                                  status='PENDING', due_at=due, source=source)
                session.add(follow); session.flush(); refs['followups'].append(str(follow.id))
            elif item['kind'] == 'SERVICE':
                from executive_health_ai.services.member_services import MemberServiceOperations
                request = MemberServiceOperations().request(session, goal.member_id, UUID(item['service_id']), item['evidence'], actor)
                request.assigned_manager, request.sla_due_at = item['owner'], due
                request.program_id, request.management_task_id = program.id, action.id
                refs['services'].append(str(request.id))
        next_item = min(clean, key=lambda a: a['due'])
        log = service.record_log(session, goal.member_id, program.id, actor=actor, request_key=f'post_checkup:{goal.id}:complete',
            occurred_at=utc_now(), category='报告沟通', member_issue='新体检报告已完成整理与人工核对', manager_action='确认处理路径并建立后续安排',
            result=f"建立 {len(clean)} 项后续管理安排", owner=actor, next_action=next_item['title'],
            follow_up_at=datetime.combine(date.fromisoformat(next_item['due']), time(9), timezone.utc),
            related_document_id=UUID(goal.source_id), related_doctor_review_id=review.id if review else None)
        refs['logs'].append(str(log.id))
        audit(session, goal.member_id, actor, 'post_checkup_actions_created', log)
        return {'created': refs, 'actions': clean, 'next_node': next_item}

    def verify_completion(self, session, goal):
        context = goal.context_json
        refs = context.get('created', {})
        if not context.get('structured') or not context.get('manager_confirmed') or not context.get('actions_confirmed'):
            raise ValueError('整理和人工确认尚未全部完成。')
        if context.get('review_id'):
            review = owned(session, DoctorReview, context['review_id'], goal.member_id)
            if review.status != 'CONFIRMED':
                raise ValueError('医生尚未完成判断。')
        if not refs.get('tasks') or not refs.get('logs') or not context.get('next_node'):
            raise ValueError('正式安排或下一节点尚未建立。')
        for key, model in [('tasks', Task), ('rechecks', RecheckPlan), ('followups', FollowUp), ('services', ServiceRequest), ('logs', ManagementLog)]:
            for identity in refs.get(key, []):
                row = owned(session, model, identity, goal.member_id)
                if model is Task and (not row.assignee or not row.due_at):
                    raise ValueError('每项行动必须有负责人和日期。')
                if model is Task and not row.source.startswith(f'post_checkup:{goal.id}:'):
                    raise ValueError('行动记录不属于本次报告安排。')
        if len(refs['tasks']) != len(context['actions']):
            raise ValueError('存在尚未正式建立的行动。')
        return {'verified': True, 'next_node': context['next_node']}
