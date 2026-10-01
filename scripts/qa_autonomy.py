"""Isolated deterministic autonomy story + actual Chromium navigation acceptance."""
import json, os, sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
WORK=ROOT/'.runtime/autonomy-browser-v2'
OUT=ROOT/'docs/images/autonomy-policy'
WORK.mkdir(exist_ok=True); OUT.mkdir(parents=True,exist_ok=True)
os.environ['DATABASE_URL']='sqlite:///'+(WORK/'browser.db').as_posix()
os.environ['LOCAL_LLM_ENABLED']='false'
sys.stdout.reconfigure(encoding='utf-8')
from sqlalchemy import select
from executive_health_ai.database import SessionLocal, engine
from executive_health_ai.models import Base, Observation, RiskRule, AgentGoal, MemberAgent
from executive_health_ai.models.base import utc_now
NAMES={'GREEN':'Demo 自主正常会员','YELLOW':'Demo 需关注会员','RED':'Demo 优先处理会员'}


def prepare():
    from datetime import date,timedelta
    from executive_health_ai.services.management_workflow import ManagementWorkflowService
    from executive_health_ai.models.management_workflow import IntakeAssessment
    from executive_health_ai.models import HealthAssessment
    from executive_health_ai.services.health_events import ingest_health_event
    from executive_health_ai.services.operational_worklist import OperationalWorklistService
    if (WORK/'story.json').exists():raise RuntimeError('保留已有合成验收数据；不要覆盖。')
    Base.metadata.create_all(engine)
    story={}
    with SessionLocal() as s:
        for number,(level,name) in enumerate(NAMES.items()):
            p=ManagementWorkflowService().enroll(s,name=name,start=date.today(),end=date.today()+timedelta(days=364),
                owner='验收责任健管',goal='仅用于非临床自主权限验收')
            for row in s.scalars(select(IntakeAssessment).where(IntakeAssessment.patient_id==p.patient_id)):
                row.status='CONFIRMED'
                row.review_status='CONFIRMED'
            s.add(HealthAssessment(patient_id=p.patient_id,assessment_type='BASELINE',cycle_year=p.cycle_year,
                version=1,title='合成年管理基线',summary='已确认的合成验收背景',baseline_json={},created_by=p.owner,
                status='CONFIRMED',reviewed_by=p.owner,confirmed_at=utc_now(),source_references_json={'source':'synthetic acceptance'}))
            workflow=ManagementWorkflowService()
            workflow.add_phase(s,p.patient_id,p.id,title='持续管理',goal='按已确认计划核对健康资料',
                content='到期检查已有安排，需要人工时才交接',start=date.today(),end=date.today()+timedelta(days=90),owner=p.owner)
            workflow.start_program(s,p.patient_id,p.id,p.owner)
            value=9000+number
            rule=RiskRule(name='合成自主权限规则：'+{'GREEN':'正常','YELLOW':'需关注','RED':'优先处理'}[level],code='AUTONOMY_SYNTHETIC_'+level,
                applicable_device_class='ANY',canonical_code='steps',risk_level=level,condition_type='SYNTHETIC_TEST_THRESHOLD',
                threshold_config={'metric':'steps','operator':'==','value':str(value),'unit':'count'},window_config={},
                action_type='SYNTHETIC_TEST_ONLY',recommended_route='DOCTOR' if level=='RED' else 'HEALTH_MANAGER',
                source_reference='合成验收规则，不是临床阈值',scope='TEST',review_status='APPROVED',reviewed_by='合成规则审核人',version='acceptance-1')
            obs=Observation(patient_id=p.patient_id,metric_code='steps',value_numeric=value,unit='count',
                source='DEVICE',quality_flag='valid',observed_at=utc_now())
            s.add_all([rule,obs]);s.flush()
            event,_=ingest_health_event(s,member_id=p.patient_id,event_type='MEANINGFUL_CHANGE',
                event_category='MEANINGFUL_CHANGE',source_type='SYSTEM',source_id='acceptance-'+level,
                payload_ref={'observation_ids':[str(obs.id)]})
            g=s.get(AgentGoal,event.goal_id)
            human=[i for i in OperationalWorklistService().list_items(s,utc_now()) if i.member_id==p.patient_id]
            agent=s.scalar(select(MemberAgent).where(MemberAgent.member_id==p.patient_id))
            story[level]={'member':str(p.patient_id),'goal':str(g.id),'status':g.status,'human_work':len(human),'agent':str(agent.id)}
        s.commit()
    assert [story[l]['human_work'] for l in NAMES]==[0,1,1],story
    (WORK/'story.json').write_text(json.dumps(story,ensure_ascii=False,indent=2),encoding='utf-8')
    (WORK/'manifest.json').write_text(json.dumps({'autonomy':{'source':str(ROOT),'database':str(WORK/'browser.db'),'port':18725}}),encoding='utf-8')
    print(json.dumps(story,ensure_ascii=False))


def browser():
    from playwright.sync_api import sync_playwright,expect
    with sync_playwright() as pw:
        b=pw.chromium.launch(headless=True)
        page=b.new_page(viewport={'width':1440,'height':900});page.set_default_timeout(45000)
        errors=[];page.on('pageerror',lambda e:errors.append(str(e)))
        def settle():
            page.wait_for_timeout(700) # Browser render stabilization only, never business progress.
            expect(page.locator('[data-testid="stApp"]')).to_have_attribute('data-test-script-state','notRunning',timeout=90000)
            assert not page.locator('[data-testid="stException"]').count(),page.locator('body').inner_text()
        def radio(name):page.get_by_role('radio',name=name,exact=True).locator('xpath=ancestor::label').click();settle()
        def button(name):page.get_by_role('button',name=name,exact=True).click();settle()
        def shot(name):
            page.locator('[data-testid="stMain"]').evaluate('(e)=>e.scrollTo(0,0)')
            page.screenshot(path=str(OUT/(name+'.png')))
            assert page.evaluate('document.documentElement.scrollWidth<=innerWidth')
            print(name,flush=True)
        try:
            page.goto('http://127.0.0.1:18725',wait_until='networkidle')
            entry=page.get_by_role('button',name='进入 HealthOps 运营后台',exact=True)
            menu=page.get_by_role('radio',name='会员',exact=True)
            entry.or_(menu).first.wait_for(state='attached',timeout=60000)
            if entry.count():button('进入 HealthOps 运营后台')
            settle();shot('01-today')
            page.get_by_label('工作筛选',exact=True).click()
            page.get_by_role('option',name='需关注',exact=True).click();settle();shot('01-today-attention-filter')
            page.get_by_label('工作筛选',exact=True).click()
            page.get_by_role('option',name='全部',exact=True).click();settle()
            for n,(level,name) in enumerate(NAMES.items(),2):
                radio('会员')
                back=page.get_by_role('button',name='← 返回会员',exact=True)
                if back.count():button('← 返回会员')
                search=page.get_by_label('搜索成员',exact=True);search.fill(name);search.press('Enter');settle()
                page.locator('[data-testid="stDataFrame"]').last.click(position={'x':150,'y':55});settle()
                radio('概览')
                expect(page.get_by_text('管理状态：'+{'GREEN':'正常自动管理','YELLOW':'需关注','RED':'优先处理'}[level],exact=True)).to_be_visible()
                shot(f'{n:02d}-{level.lower()}-overview')
                radio('管理');shot(f'{n:02d}-{level.lower()}-management')
                if level=='RED':
                    expect(page.get_by_text('当前责任：医生',exact=True)).to_be_visible()
                    button('处理');expect(page.get_by_text('等待医生判断 · 当前责任：内部医生',exact=True)).to_be_visible()
                    shot('04-red-current-action')
                    radio('会员')
                radio('医疗');shot(f'{n:02d}-{level.lower()}-medical')
            page.get_by_text('切换演示角色',exact=True).click();radio('医生')
            page.get_by_text('切换演示角色',exact=True).click();settle();shot('05-doctor')
            page.get_by_text('切换演示角色',exact=True).click();radio('管理员')
            page.get_by_text('切换演示角色',exact=True).click();settle()
            radio('自动化运行');shot('06-admin-automation');radio('管理工具');shot('07-admin-autonomy-decisions')
            assert not errors,errors
            (OUT/'verification.json').write_text(json.dumps({'browser':b.version,'viewport':[1440,900],
                'actual_click_navigation':True,'page_errors':errors,'story':json.loads((WORK/'story.json').read_text(encoding='utf-8'))},ensure_ascii=False,indent=2),encoding='utf-8')
        except Exception:
            page.screenshot(path=str(OUT/'failure.png'),full_page=True)
            (WORK/'failure.txt').write_text(page.locator('body').inner_text(),encoding='utf-8')
            raise
        finally:b.close()


def doctor_return():
    """Complete only the isolated synthetic review through the real doctor UI."""
    from playwright.sync_api import sync_playwright,expect
    from uuid import UUID
    from sqlalchemy import func
    from executive_health_ai.models import RiskEvent, DoctorReview, AgentRunTrace
    original=json.loads((WORK/'story.json').read_text(encoding='utf-8'))['RED']
    with sync_playwright() as pw:
        b=pw.chromium.launch(headless=True);page=b.new_page(viewport={'width':1440,'height':900})
        page.set_default_timeout(45000)
        def settle():
            page.wait_for_timeout(700)
            expect(page.locator('[data-testid="stApp"]')).to_have_attribute('data-test-script-state','notRunning',timeout=90000)
            assert not page.locator('[data-testid="stException"]').count()
        def radio(n):page.get_by_role('radio',name=n,exact=True).locator('xpath=ancestor::label').click();settle()
        try:
            page.goto('http://127.0.0.1:18725',wait_until='networkidle');settle()
            entry=page.get_by_role('button',name='进入 HealthOps 运营后台',exact=True)
            entry.wait_for(state='visible',timeout=60000)
            entry.click();settle()
            page.get_by_text('切换演示角色',exact=True).click();radio('医生')
            page.get_by_text('切换演示角色',exact=True).click();settle()
            for x in (150,100,15):
                page.locator('[data-testid="stDataFrame"]').last.click(position={'x':x,'y':55});settle()
                if page.get_by_label('医学判断',exact=True).count():break
            page.get_by_label('医学判断',exact=True).fill('合成验收：已核对原始资料，请健管联系会员核实近期情况。本记录不是临床建议。')
            page.get_by_label('建议',exact=True).fill('联系合成会员并记录反馈，保留原正式规则结果。')
            page.get_by_role('button',name='提交判断',exact=True).click();settle()
            page.screenshot(path=str(OUT/'08-doctor-result-submitted.png'))
            with SessionLocal() as s:
                goal=s.get(AgentGoal,UUID(original['goal']))
                risk=s.get(RiskEvent,UUID(goal.context_json['risk_event_id']))
                result={'same_goal':str(goal.id)==original['goal'],'status':goal.status,'risk':risk.risk_level,
                    'goal_count':s.scalar(select(func.count(AgentGoal.id)).where(AgentGoal.member_id==goal.member_id)),
                    'resume_trace':s.scalar(select(func.count(AgentRunTrace.id)).where(AgentRunTrace.goal_id==goal.id,AgentRunTrace.action=='resume'))}
                assert result['same_goal'] and result['status']=='WAITING_MANAGER' and result['risk']=='RED' and result['goal_count']==1
            (OUT/'doctor-return.json').write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf-8')
            print(json.dumps(result),flush=True)
        except Exception:
            page.screenshot(path=str(OUT/'doctor-return-failure.png'),full_page=True)
            (WORK/'doctor-failure.txt').write_text(page.locator('body').inner_text(),encoding='utf-8')
            raise
        finally:b.close()

if __name__=='__main__':
    prepare() if '--prepare' in sys.argv else doctor_return() if '--doctor-return' in sys.argv else browser()
