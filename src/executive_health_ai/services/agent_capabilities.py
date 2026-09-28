"""Business projection of actual traces. Context flags alone never prove an AI call."""
from dataclasses import dataclass
from uuid import UUID
from sqlalchemy import select
from executive_health_ai.models import AgentRunTrace, ReportExtractionRun


@dataclass(frozen=True)
class SupportActivity:
    key: str
    title: str
    purpose: str
    status: str
    result: str
    at: object = None
    used: bool = False
    citations: tuple = ()

    @property
    def mark(self):
        return '✓' if self.status == 'SUCCESS' else '△' if self.status in {'UNAVAILABLE','UNUSABLE'} else '●' if self.status == 'RUNNING' else '○'

    @property
    def label(self):
        return {'SUCCESS':'已完成','UNAVAILABLE':'暂不可用','UNUSABLE':'结果未采用','NOT_USED':'未使用',
                'PENDING':'尚未执行','UNKNOWN':'无可核实调用记录','RUNNING':'正在执行'}[self.status]


def trace_data(trace):
    return (getattr(trace, 'metadata_json', None) or {}).get('capability', {})


def project(goal, traces=(), run=None):
    ctx = goal.context_json or {}
    ordered = sorted(traces, key=lambda t: t.started_at)
    actual = [t for t in ordered if t.action == 'capability_activity']
    latest = {trace_data(t).get('task'): t for t in actual}
    profile = getattr(goal, 'goal_type', None) == 'PROFILE_INTAKE'
    knowledge = latest.get('retrieve_knowledge')
    legacy = next((t for t in reversed(ordered) if t.tool_name == 'retrieve_knowledge' and t.action == 'tool_completed' and t.status == 'COMPLETED'), None)
    unavailable = next((t for t in reversed(ordered) if t.action == 'knowledge_unavailable'), None)
    purpose = '查找本次体检变化相关的已审核健康管理依据'
    if profile and not (knowledge or legacy or unavailable):
        support = [SupportActivity('knowledge','知识依据检索','本次资料解析与档案匹配', 'NOT_USED','本步骤未调用知识库；不需要医学知识检索。')]
    elif knowledge:
        data = trace_data(knowledge)
        ok = data.get('status') == 'SUCCESS'
        citations = tuple(data.get('citations', ())) if ok else ()
        count = data.get('knowledge_hit_count', len(citations))
        support = [SupportActivity('knowledge','知识依据检索',purpose,'SUCCESS' if ok else 'UNAVAILABLE',
            f'找到 {count} 条已审核依据' if ok and count else '检索完成，暂无匹配的已审核知识依据。' if ok else '知识检索暂不可用；继续人工核对，不生成替代来源。',
            knowledge.completed_at, True, citations)]
    elif unavailable and (not legacy or unavailable.started_at >= legacy.started_at):
        support = [SupportActivity('knowledge','知识依据检索',purpose,'UNAVAILABLE','知识检索暂不可用；未生成替代依据。',unavailable.completed_at,True)]
    elif legacy:
        citations = tuple(ctx.get('knowledge', ()))
        support = [SupportActivity('knowledge','知识依据检索',purpose,'SUCCESS',f'找到 {len(citations)} 条已审核依据' if citations else '检索完成，暂无匹配的已审核知识依据。',legacy.completed_at,True,citations)]
    else:
        support = [SupportActivity('knowledge','知识依据检索',purpose,'PENDING','尚无本次知识检索执行记录。')]

    def llm(task, key, title, purpose, pending, success):
        record = latest.get(task)
        if record:
            data = trace_data(record)
            status = data.get('status')
            accepted = data.get('accepted') is True and status == 'SUCCESS'
            result = success if accepted else '结果未通过原文 / 格式核对，继续使用规则结果。' if status == 'UNUSABLE' else '已使用规则整理结果继续流程。' if not profile else '保留规则结果与原文件；无法可靠整理的部分转人工核对。'
            if not data.get('request_sent') and status == 'UNAVAILABLE':
                result += ' 模型服务未就绪，本次未发起模型请求。'
            return SupportActivity(key,title,purpose,'SUCCESS' if accepted else 'UNUSABLE' if status == 'SUCCESS' else status,
                                   result,record.completed_at,bool(data.get('request_sent')))
        return SupportActivity(key,title,purpose,'PENDING',pending)

    if profile:
        parsed = any(t.tool_name == 'parse_profile_document' and t.status == 'COMPLETED' for t in ordered) or bool(run and run.status == 'COMPLETED')
        support.insert(0, SupportActivity('mapping','文件读取 / 规则映射','读取文件、识别结构化字段并核对来源',
            'SUCCESS' if parsed else 'PENDING',f'已完成资料读取与字段核对，共 {run.candidate_count if run else 0} 项候选。' if parsed else '文件读取或解析尚未完成。',used=parsed))
        calls = [t for t in actual if trace_data(t).get('kind') == 'LLM']
        if calls:
            operation = trace_data(calls[-1]).get('operation_id')
            calls = [t for t in calls if trace_data(t).get('operation_id') == operation] if operation else [latest[trace_data(calls[-1])['task']]]
            accepted = [t for t in calls if trace_data(t).get('accepted') and trace_data(t).get('status') == 'SUCCESS']
            # The persisted candidate count is deduplicated across the whole file.
            # Per-request counts stay in technical records, never multiplied here.
            count = sum(trace_data(t).get('result_count',0) for t in accepted)
            if run and (run.metadata_json or {}).get('semantic_candidate_count') is not None:
                count = run.metadata_json['semantic_candidate_count']
            status = 'SUCCESS' if accepted else 'UNAVAILABLE' if any(trace_data(t).get('status') == 'UNAVAILABLE' for t in calls) else 'UNUSABLE'
            failed = len(calls) - len(accepted)
            result = f'已整理 {count} 项有原文依据的候选资料，仍需健管确认。' if accepted else '未获得可采用的语义整理结果；保留规则结果与原文件，需人工核对。'
            if accepted and failed: result += f' 另有 {failed} 次请求无可采用结果，相关原文需人工核对。'
            if not any(trace_data(t).get('request_sent') for t in calls): result += ' 本次未发起模型请求。'
            support.insert(-1, SupportActivity('semantic','AI语义整理','仅提取原文可逐字核实的资料；等待健管确认',
                status,result,calls[-1].completed_at,any(trace_data(t).get('request_sent') for t in calls)))
        elif run and run.llm_status == 'UNAVAILABLE':
            support.insert(-1, SupportActivity('semantic','AI语义整理','整理自由文本原文','UNAVAILABLE','语义服务暂不可用；没有成功调用记录，保留规则结果并转人工核对。'))
        elif run and not (run.metadata_json or {}).get('capability_audited') and (run.llm_used or run.llm_call_count):
            support.insert(-1, SupportActivity('semantic','AI语义整理','整理自由文本原文','UNKNOWN','历史解析记录表明曾使用语义辅助；缺少逐次调用审计，不补写成功记录。'))
        else:
            support.insert(-1, SupportActivity('semantic','AI语义整理','仅在资料需要语义解析时使用',
                'NOT_USED' if parsed else 'PENDING','结构化资料已通过规则映射，本步骤未调用 AI。' if parsed else '尚无实际语义调用记录。'))
    else:
        summary = llm('post_checkup_manager_draft','summary','AI摘要整理','辅助生成待健管确认的非临床摘要',
                      '尚无摘要生成调用记录。','已生成待健管确认摘要。')
        if summary.status == 'PENDING':
            old = next((t for t in reversed(ordered) if t.action == 'summary_drafted' and t.status in {'AVAILABLE','UNAVAILABLE'}), None)
            if old:
                ok = old.status == 'AVAILABLE'
                summary = SupportActivity('summary','AI摘要整理',summary.purpose,'SUCCESS' if ok else 'UNAVAILABLE',
                    '已生成待健管确认摘要（历史调用记录）。' if ok else '已使用规则整理结果继续流程；历史记录未提供请求详情。',old.completed_at,ok)
        support.append(summary)
        support.append(llm('post_checkup_action_draft','doctor','医生意见整理','仅从医生原文提取随访主题；不改变行动类型、日期或医学决定',
            '当前尚未收到医生意见。' if not ctx.get('doctor_result') else '已收到医生意见，但尚无可核实的整理调用记录。',
            '已从医生原文提取随访主题；保留原行动类型、日期与医学决定。'))
    return tuple(support)


def load(session, goal):
    traces = list(session.scalars(select(AgentRunTrace).where(AgentRunTrace.goal_id == goal.id).order_by(AgentRunTrace.started_at)))
    run = session.get(ReportExtractionRun, UUID(goal.context_json['run_id'])) if getattr(goal,'goal_type',None) == 'PROFILE_INTAKE' and goal.context_json.get('run_id') else None
    if run and (run.patient_id != goal.member_id or str(run.document_id) != goal.source_id):
        raise ValueError('解析记录不属于本次流程。')
    return project(goal, traces, run), traces


def capabilities(goal, activities, traces):
    recorded = {t.tool_name for t in traces if t.status == 'COMPLETED'}
    has = lambda key: any(a.key == key and a.used for a in activities)
    flags = [('规则', any(t.action == 'responsibility_routed' for t in traces) or has('mapping')),
             ('健康档案', bool(recorded & {'get_member_context','get_health_history','match_profile_document'})),
             ('知识库', has('knowledge')), ('AI', any(a.used for a in activities if a.key in {'summary','doctor','semantic'})),
             ('健管', bool(goal.context_json.get('manager_confirmed') or goal.context_json.get('output'))),
             ('医生', bool(goal.context_json.get('doctor_result') or any(t.action == 'resumed_after_doctor' or
                t.action == 'profile_activity' and t.result_summary == '已收到医生判断，继续等待健管确认档案更新' for t in traces)))]
    current = '健管' if goal.status == 'WAITING_MANAGER' else '医生' if goal.status == 'WAITING_DOCTOR' else None
    return [(label, 'current' if label == current else 'used' if used else 'unused') for label,used in flags]


def technical_rows(traces):
    result = []
    for trace in traces:
        data = trace_data(trace)
        if not data:
            continue
        result.append({'时间':trace.started_at, '类型':data.get('kind'), '任务':data.get('task'),
            '状态':data.get('status'), 'Provider':data.get('provider','—'), '请求已发出':data.get('request_sent'),
            '耗时 ms':data.get('latency_ms'), '输入来源':' + '.join(data.get('input_sources',[])),
            '结果摘要':f"{data['knowledge_hit_count']} hits" if 'knowledge_hit_count' in data else f"{data['result_count']} 项候选 / 规则结果" if data.get('result_count') and (data.get('accepted') or data.get('kind') == 'RULE') else '结果通过核对' if data.get('accepted') else '未采用 / 无可用结果',
            '检索范围':data.get('retrieval_policy','—')})
    return result
