"""Human exception decisions over the existing intake draft and source candidates.

No model, Agent, medical inference or knowledge retrieval lives here. Proposals stay
in the assessment workspace until the manager submits through the existing service.
"""
from copy import deepcopy
from datetime import date
from executive_health_ai.models import Patient
from executive_health_ai.models.base import utc_now
from executive_health_ai.services.assessment_import import AssessmentImportService, IDENTITY, digest, step_for
from executive_health_ai.services.management_workflow import (
    ManagementWorkflowService, TABLE_FIELDS, PROFILE_FIELDS, STEPS, audit)

imports = AssessmentImportService()
CATALOG = {'基础资料': ['display_name', 'birth_date', 'sex'], **TABLE_FIELDS,
           **PROFILE_FIELDS, '会员重点关注': ['concern']}
LABELS = {'display_name': '会员称呼', 'birth_date': '出生日期', 'sex': '性别',
          'concern': '会员希望改善的问题'}
REQUIRED = {**{s: {IDENTITY[s]} for s in TABLE_FIELDS if s != '最近用药'},
            '基础资料': {'display_name'}, '生活方式': {'睡眠', '烟草', '饮酒'},
            '环境与暴露': {'空气污染'}, '会员重点关注': {'concern'}}
QUESTIONS = {('过敏史', '名称'): '是否存在药物或其他过敏？请记录会员的实际回答。',
             ('生活方式', '睡眠'): '最近一个月平均睡眠时间是多少？',
             ('家族健康史', '具体疾病'): '家族成员有哪些疾病与健康背景？',
             ('会员重点关注', 'concern'): '会员目前最希望改善什么问题？'}


def state(row):
    saved=deepcopy((row.review or {}).get('exception_intake', {}))
    # Existing multi-file draft uploads also use the new queue, without a data
    # migration or re-upload. This is a projection, not an implicit database write.
    if 'document_intake' in (row.review or {}):saved.setdefault('enabled',True)
    return saved


def enable(row):
    row.review = {**(row.review or {}), 'exception_intake': {**state(row), 'enabled': True}}


def signature(group):
    return digest([group['key'], group['current'],
                   [(str(r.id), r.structured_data_json, r.evidence_text) for r in group['rows']]])


def put(answers, section, field, value, identity=''):
    if section in TABLE_FIELDS:
        rows = answers.setdefault(section, [])
        id_field = IDENTITY[section]
        name, _, relative = identity.partition(' / ')
        target = next((r for r in rows if r.get(id_field, '') == name and
                       (section != '家族健康史' or not relative or r.get('患病家属') == relative)), None)
        if target is None:
            target = {id_field: name} if name else {}
            if relative: target['患病家属'] = relative
            rows.append(target)
        target[field] = value
    else:
        answers.setdefault(section, {})[field] = value


def project(session, row):
    view = imports.project(session, row.patient_id, row.id)
    saved = state(row)
    decisions = saved.get('decisions', {})
    answers = deepcopy(row.responses or {})
    member = session.get(Patient, row.patient_id)
    answers['基础资料'] = {f: str(getattr(member, f) or '') for f in CATALOG['基础资料']}
    queue, accepted, auto, confirmed = [], [], 0, 0
    for group in view['groups']:
        key, sig = group['key'], signature(group)
        decision = decisions.get(key, {})
        valid = decision.get('signature') == sig
        semantic = any(r.extraction_method == 'LLM' for r in group['rows'])
        # Independent source validation also protects imported or legacy candidates.
        evidence_ok = all(r.evidence_text and str(r.structured_data_json['value']) in r.evidence_text
                          and r.structured_data_json.get('source_document_id') == str(r.document_id)
                          for r in group['rows'])
        value = group['values'][0] if len(group['values']) == 1 else ''
        reviewed=next(s for s in view['steps'] if s['step']==step_for(group['section']))['checked']
        if reviewed:
            # Advanced editing remains authoritative after its existing source check.
            if group['current']:confirmed += 1;accepted.append(key)
        elif valid:
            if decision['action'] != 'IGNORE':
                put(answers, group['section'], group['field'], decision['value'], group['identity'])
                confirmed += 1
                accepted.append(key)
        elif group['safe'] and evidence_ok and not semantic:
            put(answers, group['section'], group['field'], value, group['identity'])
            auto += 1
        else:
            dated = [(r.structured_data_json.get('source_date'), r.structured_data_json['value'])
                     for r in group['rows']]
            # A date orders source statements; it does not establish clinical truth.
            dates_valid = all(d and len(d) == 10 for d, _ in dated)
            latest = max((d for d, _ in dated), default='') if dates_valid else ''
            latest_values = {v for d, v in dated if d == latest} if latest else set()
            suggestion = next(iter(latest_values)) if len(latest_values) == 1 else value
            queue.append(dict(key=key, signature=sig, kind='CONFLICT' if group['conflict'] else 'CONFIRM',
                section=group['section'], field=group['field'], identity=group['identity'],
                label=LABELS.get(group['field'], group['field']), value=suggestion,
                current=group['current'], sources=group['rows'], evidence_ok=evidence_ok,
                dated=bool(latest and len(latest_values) == 1)))
    for answer in saved.get('answers', {}).values():
        if answer.get('base_hash',digest(row.responses.get(answer['section'])))==digest(row.responses.get(answer['section'])):
            put(answers, answer['section'], answer['field'], answer['value'], answer.get('identity', ''))
    # Count actual schema slots (including each additional table record), not sections.
    total, missing, filled = 0, [], 0
    blocked = {(q['section'], q['identity'], q['field']) for q in queue}
    for section, fields in CATALOG.items():
        records = (answers.get(section) or [{}]) if section in TABLE_FIELDS else [answers.get(section, {})]
        for record in records:
            identity = str(record.get(IDENTITY[section], '')) if section in TABLE_FIELDS else ''
            if section == '家族健康史' and record.get('患病家属'): identity += ' / ' + record['患病家属']
            for field in fields:
                total += 1
                if record.get(field): filled += 1; continue
                if (section, identity, field) in blocked or any(q['kind'] in {'CONFIRM','CONFLICT'} and
                    q['section'] == section and q['field'] == field and not identity for q in queue):
                    continue
                item = dict(key='missing:' + digest([section, identity, field]), kind='MISSING',
                    section=section, field=field, identity=identity, label=LABELS.get(field, field),
                    question=QUESTIONS.get((section, field), '请补充' + section + '的' + LABELS.get(field, field) + '。'),
                    value='', required=field in REQUIRED.get(section, set()))
                missing.append(item)
                if item['required']: queue.append(item)
    for file in view['files']:
        if file['needs_check'] and not file['checked']:
            queue.append(dict(key='file:' + str(file['goal'].id), signature=file['signature'], kind='FILE',
                section='资料核对', field='', label=file['document'].title, value='', file=file))
    medical = any(g.status == 'WAITING_DOCTOR' for g in view['goals'])
    counts = dict(total=total, auto_filled=auto + sum(q['kind'] in {'CONFIRM','CONFLICT'} for q in queue)
                  + len(accepted), confirmed=confirmed,
                  pending=sum(q['kind']=='CONFIRM' for q in queue),
                  conflicts=sum(q['kind']=='CONFLICT' for q in queue), missing=len(missing),
                  required_missing=sum(q['kind']=='MISSING' for q in queue), exceptions=len(queue),
                  manual_fields=len(saved.get('answers', {})), filled=filled,
                  sources=len(view['files']))
    return dict(view=view, answers=answers, queue=queue, missing=missing, counts=counts,
                processing=view['processing'], medical=medical,
                ready=not queue and not view['processing'] and not medical,
                submitted=row.status != 'DRAFT')


def decide(session, row, key, action, actor, value='', note='', expected_signature=None):
    from executive_health_ai.services.profile_ingestion import manager
    manager('HEALTH_MANAGER', actor)
    data = project(session, row)
    if row.status != 'DRAFT' or data['processing']: raise ValueError('请在资料整理完成后处理草稿。')
    item = next((q for q in data['queue'] + data['missing'] if q['key'] == key), None)
    if not item: raise ValueError('此事项已变更，请刷新后处理。')
    if expected_signature and item.get('signature') != expected_signature: raise ValueError('来源已变化，请重新核对。')
    saved = state(row)
    saved.setdefault('initial_counts', data['counts'])
    if action in {'ANSWER','MODIFY'}:
        value=value.strip()
        if len(value)>500:raise ValueError('回答请控制在 500 字以内。')
        if item['section']=='基础资料' and item['field']=='birth_date':
            try:valid=date(1900,1,1)<=date.fromisoformat(value)<=date.today()
            except ValueError:valid=False
            if not valid:raise ValueError('出生日期请使用有效的年-月-日；未知可继续留空。')
        if item['section']=='基础资料' and item['field']=='sex':
            value={'男':'male','女':'female'}.get(value,value)
            if value not in {'male','female'}:raise ValueError('性别请填写男或女；未知可继续留空。')
        if item['section']=='专项症状评估' and item['field']=='原始分数' and value not in {'0','1','2','3','4'}:
            raise ValueError('只能采用原资料提供的 0 至 4 分，不能推算。')
    if item['kind'] == 'FILE':
        if action != 'ACKNOWLEDGE': raise ValueError('请记录原文件及测量候选的处理情况。')
        imports.acknowledge_file(session, row.patient_id, row.id, item['file']['goal'].id, actor, note)
        return
    if item['kind'] == 'MISSING':
        if action != 'ANSWER' or not value.strip(): raise ValueError('请填写会员实际回答；不知道时可明确记录“暂不清楚”。')
        saved.setdefault('answers', {})[key] = {k:item[k] for k in ('section','field','identity')}
        saved['answers'][key].update(value=value.strip(), actor=actor, at=utc_now().isoformat(),
                                    base_hash=digest(row.responses.get(item['section'])))
    else:
        if action not in {'CONFIRM','MODIFY','IGNORE'}: raise ValueError('请选择确认、修改或忽略。')
        if action == 'CONFIRM' and not item['evidence_ok']: raise ValueError('来源无法核实，请人工修正或忽略。')
        value = item['value'] if action == 'CONFIRM' else value.strip()
        if action != 'IGNORE' and not value: raise ValueError('请填写采用的回答。')
        if action == 'IGNORE' and not note.strip(): raise ValueError('请说明忽略原因。')
        saved.setdefault('decisions', {})[key] = dict(signature=item['signature'], action=action,
            value=value, note=note, actor=actor, at=utc_now().isoformat(), kind=item['kind'])
    row.review = {**row.review, 'exception_intake':saved}
    audit(session, row.patient_id, actor, 'intake_exception_resolved', row)


def complete(session, row, actor, *, retain_unknown=False):
    from executive_health_ai.services.profile_ingestion import manager
    manager('HEALTH_MANAGER', actor)
    data = project(session, row)
    if row.status != 'DRAFT' or not data['ready']: raise ValueError('仍有待确认、冲突、必需回答或医学判断尚未处理。')
    if data['missing'] and not retain_unknown: raise ValueError('请确认未提供的可选资料继续保持未知，不代表“无”。')
    workflow = ManagementWorkflowService()
    for section in STEPS[:-1]:
        workflow.save_intake(session, row.patient_id, row.cycle_year, section,
            data['answers'].get(section, [] if section in TABLE_FIELDS else {}), actor)
    for step in data['view']['steps']:
        imports.record_review(session, row, step['step'], actor,
            '已逐项处理例外并总确认来源；未提供的可选资料保持未知。')
    saved = state(row)
    saved.update(completion=data['counts'], completed_at=utc_now().isoformat(),
                 optional_unknown=[{k:m[k] for k in ('section','field','identity')} for m in data['missing']],
                 confirmed_by=actor)
    row.review = {**row.review, 'exception_intake':saved}
    return workflow.submit_intake(session, row.patient_id, row.id, actor)


def editor_data(view, section, original):
    """The existing wizard sees the same decisions as the foreground queue."""
    row=view['intake'];saved=state(row)
    if not saved.get('enabled'):return original
    answer={section:deepcopy(original)}
    for group in view['groups']:
        if group['section']!=section:continue
        decision=saved.get('decisions',{}).get(group['key'],{})
        if decision.get('signature')==signature(group) and decision.get('action')!='IGNORE':
            put(answer,section,group['field'],decision['value'],group['identity'])
    for item in saved.get('answers',{}).values():
        if item['section']==section and item.get('base_hash',digest(row.responses.get(section)))==digest(row.responses.get(section)):
            put(answer,section,item['field'],item['value'],item.get('identity',''))
    return answer[section]


def confirm_measurements(session,row,goal_id,actor,expected_signature):
    """Reuse formal observation confirmation, including its existing risk rules."""
    from executive_health_ai.services.profile_ingestion import manager,ProfileIngestionService,candidates
    from executive_health_ai.services.report_parsing import ReportParsingService
    manager('HEALTH_MANAGER',actor)
    data=project(session,row)
    file=next((f for f in data['view']['files'] if f['goal'].id==goal_id),None)
    if row.status!='DRAFT' or data['processing'] or data['medical'] or not file or file['goal'].status!='WAITING_MANAGER':
        raise ValueError('请等待资料整理及医生判断完成后再确认测量。')
    if file['signature']!=expected_signature:raise ValueError('来源已变化，请刷新并重新核对。')
    rows=[r for r in candidates(session,file['goal']) if r.candidate_type=='OBSERVATION'
          and r.status in {'PENDING_REVIEW','CORRECTED'}
          and ProfileIngestionService().classify(session,file['goal'],r)[0] in {'新增','更新'}]
    if not rows:raise ValueError('暂无日期、单位及来源完整的新增测量可确认。')
    for candidate in rows:ReportParsingService().confirm_candidate(session,candidate,actor)
    return len(rows)
