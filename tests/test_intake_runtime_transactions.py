"""File-backed SQLite regression: a real outstanding model call must not lock UI writes."""
from concurrent.futures import ThreadPoolExecutor
from datetime import timedelta
from threading import Event
from uuid import UUID
import pytest
from sqlalchemy import create_engine,select,func
from sqlalchemy.orm import Session
from executive_health_ai.models import Base,Patient,AgentGoal,ReportExtractionCandidate
from executive_health_ai.models.base import utc_now
from executive_health_ai.agent.supervisor import HealthOpsAgentSupervisor
from executive_health_ai.services.profile_ingestion import ProfileIngestionService
from executive_health_ai.services.management_workflow import ManagementWorkflowService
from executive_health_ai.services.assessment_import import AssessmentImportService
from executive_health_ai.llm.activity import notify_progress,observe_progress
from executive_health_ai.ui.pages.manager.intake_workspace import execution_mark


@pytest.fixture
def runtime(tmp_path,monkeypatch):
    engine=create_engine('sqlite:///'+str(tmp_path/'concurrency.db'),
        connect_args={'check_same_thread':False,'timeout':0.5})
    Base.metadata.create_all(engine)
    monkeypatch.setattr(ProfileIngestionService,'storage_root',tmp_path/'uploads')
    with Session(engine,expire_on_commit=False) as s:
        p=Patient(display_name='Synthetic lock regression',timezone='Asia/Tokyo');s.add(p);s.flush()
        intake=ManagementWorkflowService().start_intake(s,p.id,2026,'QA')
        result=AssessmentImportService().upload_batch(s,p.id,intake.id,
            [('history.txt','睡眠：七小时\n现在每周快走三次'.encode())],actor='QA')[0]
        goal_id=UUID(result['goal_id']);s.commit()
        HealthOpsAgentSupervisor().execute_next_step(s,goal_id,durable_profile=True)
    yield engine,goal_id
    engine.dispose()


def advance(engine,goal_id):
    with Session(engine,expire_on_commit=False) as s:
        return HealthOpsAgentSupervisor().execute_next_step(s,goal_id,durable_profile=True)


def test_model_request_releases_write_lock_and_publishes_claim(runtime,monkeypatch):
    engine,goal_id=runtime;entered=Event();release=Event();calls=[];events=[]
    class Client:
        def generate_structured(self,**kw):
            calls.append(kw['task']);notify_progress('AI_REQUEST_STARTED');entered.set()
            assert release.wait(15),'test did not release model request'
            return {'facts':[{'section':'生活方式','field':'运动','value':'每周快走三次','evidence':'现在每周快走三次'}]}
    monkeypatch.setattr('executive_health_ai.services.intake_extraction.LocalLLMClient',Client)
    def run():
        with observe_progress(events.append):return advance(engine,goal_id)
    with ThreadPoolExecutor(max_workers=1) as pool:
        future=pool.submit(run)
        try:
            assert entered.wait(15)
            with Session(engine) as other:
                g=other.get(AgentGoal,goal_id)
                assert g.status=='PROCESSING'
                assert g.context_json['execution']['event']=='AI_REQUEST_STARTED'
                assert 'intake-spinner' in execution_mark({'current':{'goal':g}})
                assert other.scalar(select(func.count(ReportExtractionCandidate.id)))==0
                # A competing UI/worker invocation returns without a duplicate request.
                result=HealthOpsAgentSupervisor().execute_next_step(other,goal_id,durable_profile=True)
                assert result.status=='PROCESSING'
                # Unrelated business writes must also succeed before the model returns.
                other.add(Patient(display_name='Concurrent business write',timezone='Asia/Tokyo'))
                other.commit()
            assert calls==['parse_health_intake']
        finally:release.set()
        assert future.result(timeout=15).current_stage=='NORMALIZING'
    assert 'AI_REQUEST_STARTED' in events  # The foreground UI observer remains connected.
    assert advance(engine,goal_id).current_stage=='MATCHING'
    assert advance(engine,goal_id).status=='WAITING_MANAGER'
    with Session(engine) as s:
        g=s.get(AgentGoal,goal_id)
        assert g.next_check_at is None and 'execution' not in g.context_json
        assert s.scalar(select(func.count(ReportExtractionCandidate.id)))==2
        assert 'intake-spinner' not in execution_mark({'current':None,'finished':False,'files':[{'goal':g}]})


def test_expired_claim_recovers_same_goal(runtime,monkeypatch):
    engine,goal_id=runtime
    with Session(engine) as s:
        g=s.get(AgentGoal,goal_id);g.status='PROCESSING';g.next_check_at=utc_now()-timedelta(seconds=1)
        g.context_json={**g.context_json,'execution':{'token':'dead-worker','event':'AI_REQUEST_STARTED'}};s.commit()
    assert advance(engine,goal_id).current_stage=='NORMALIZING' # Existing disabled-model fallback retained.
    with Session(engine) as s:assert s.scalar(select(func.count(AgentGoal.id)))==1


def test_runtime_failure_rolls_back_results_releases_claim_and_propagates(runtime,monkeypatch):
    engine,goal_id=runtime
    def fail(self,session,goal,client=None):
        session.add(Patient(display_name='must rollback',timezone='Asia/Tokyo'));session.flush()
        raise RuntimeError('deliberate storage failure')
    monkeypatch.setattr(ProfileIngestionService,'parse',fail)
    with pytest.raises(RuntimeError,match='deliberate storage failure'):advance(engine,goal_id)
    with Session(engine) as s:
        g=s.get(AgentGoal,goal_id)
        assert g.status=='RUNNING' and g.current_stage=='PARSING'
        assert s.scalar(select(func.count(Patient.id)))==1


def test_superseded_execution_cannot_write_candidates(runtime,monkeypatch):
    engine,goal_id=runtime
    class Client:
        def generate_structured(self,**kw):
            with Session(engine) as other:
                g=other.get(AgentGoal,goal_id)
                g.context_json={**g.context_json,'execution':{'token':'replacement','event':'RUNNING'}}
                other.commit()
            return {'facts':[]}
    monkeypatch.setattr('executive_health_ai.services.intake_extraction.LocalLLMClient',Client)
    assert advance(engine,goal_id).status=='PROCESSING'
    with Session(engine) as s:
        assert s.scalar(select(func.count(ReportExtractionCandidate.id)))==0
        assert s.get(AgentGoal,goal_id).context_json['execution']['token']=='replacement'
