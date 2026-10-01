"""Two-file intake acceptance in isolated actual Chromium, never the formal DB."""
import json,os,re,sys,importlib.util,subprocess
from pathlib import Path
from uuid import UUID
ROOT=Path(__file__).resolve().parents[1]
CASE=os.environ.get('HEALTHOPS_INTAKE_QA_CASE','final-browser')
assert re.fullmatch(r'[a-zA-Z0-9_-]+',CASE)
WORK=ROOT/'.runtime/intake-human-work'/CASE
OUT=ROOT/'docs/images/intake-human-work'
WORK.mkdir(parents=True,exist_ok=True);OUT.mkdir(parents=True,exist_ok=True)
NAME='合成初评减负验收'
os.environ['DATABASE_URL']='sqlite:///'+(WORK/'browser.db').as_posix()
from executive_health_ai.config import load_project_environment
load_project_environment()
sys.stdout.reconfigure(encoding='utf-8')
from sqlalchemy import select
from executive_health_ai.database import SessionLocal,engine
from executive_health_ai.models import Base,Patient,MemberAgent,HealthEvent,AgentGoal,AgentRunTrace,ReportExtractionRun
from executive_health_ai.models.management_workflow import IntakeAssessment
from executive_health_ai.services import intake_exceptions as service

def fixtures():
    from executive_health_ai.services.management_workflow import TABLE_FIELDS
    answers={
      '基础资料':{'display_name':NAME,'birth_date':'1980-01-01','sex':'male'},
      '家族健康史':[{'疾病类别':'代谢','具体疾病':'糖尿病','患病家属':'父亲','备注':'会员明确自述'}],
      '个人病史':[{'疾病或问题':'脂肪肝','是否存在':'既往报告记载','确诊来源':'体检报告','确诊时间':'2025-01-01','持续管理':'定期随访','备注':'原报告记录'}],
      '手术 / 住院史':[{'类型':'手术','名称':'阑尾切除术','日期':'2018-05-01','机构':'市医院','持续随访':'已结束随访','随访内容':'术后门诊复查'}],
      '过敏史':[{'类别':'药物','名称':'青霉素','过敏反应':'皮疹','来源':'会员本人回答'}],
      '当前用药 / 营养补充':[{'名称':'维生素D','剂量':'1','单位':'片','频次':'每日','途径':'口服','开始日期':'2025-01-01','处方来源':'会员自述'}],
      '最近用药':[{'名称':'维生素C','使用时间':'2025-01','原因':'会员自行补充','来源':'会员回答'}],
      '生活方式':{'饮食':'规律三餐','烟草':'偶尔吸烟','工作压力':'中等','休假':'每年两周','生活规律':'工作日规律作息'},
      '环境与暴露':{'空气污染':'居住市区','工业暴露':'办公环境','噪音':'临街','宠物':'养猫','香氛':'偶尔使用','油烟 / 二手烟':'家用油烟机','潮湿 / 霉菌':'房间通风','装修':'五年前装修','食品暴露':'家常饮食','个人用品暴露':'常规洗护'},
      '专项症状评估':[{'症状':'午后疲劳','原始回答':'偶尔','频率或严重度':'每周一次','原始分数':'1'}]}
    (WORK/'questionnaire.json').write_text(json.dumps({'source_date':'2025-09-28','responses':answers},ensure_ascii=False),encoding='utf-8')
    (WORK/'history.txt').write_text('报告日期：2026-09-28\n会员本人说：已戒烟，现在每周快走三次，饮酒情况为每周一杯葡萄酒。',encoding='utf-8')

def prepare():
    from datetime import date,timedelta
    from executive_health_ai.services.management_workflow import ManagementWorkflowService
    if (WORK/'member.json').exists():raise RuntimeError('Existing QA history retained. Use a new isolated directory for a new run.')
    Base.metadata.create_all(engine)
    with SessionLocal() as s:
        w=ManagementWorkflowService()
        program=w.enroll(s,name=NAME,start=date.today(),end=date.today()+timedelta(days=364),owner='验收健管',goal='合成资料整理验收')
        w.start_intake(s,program.patient_id,date.today().year,'验收健管');s.commit()
        agent=s.scalar(select(MemberAgent).where(MemberAgent.member_id==program.patient_id))
        (WORK/'member.json').write_text(json.dumps({'member':str(program.patient_id),'agent':str(agent.id)}),encoding='utf-8')
    fixtures()
    # A realistic partial questionnaire: optional exposures/old prescriptions
    # are not available, and the member explicitly reports no surgery history.
    path=WORK/'questionnaire.json';document=json.loads(path.read_text(encoding='utf-8'))
    answers=document['responses'];answers.pop('环境与暴露');answers.pop('最近用药')
    answers['手术 / 住院史']=[{'名称':'无手术史'}]
    answers['家族健康史'][0].pop('备注')
    for field in ('开始日期','处方来源','途径'):answers['当前用药 / 营养补充'][0].pop(field)
    for field in ('休假','工作压力','生活规律'):answers['生活方式'].pop(field)
    path.write_text(json.dumps(document,ensure_ascii=False),encoding='utf-8')
    (WORK/'manifest.json').write_text(json.dumps({'intake-human-work':{'source':str(ROOT),'database':str(WORK/'browser.db'),'port':18723}}),encoding='utf-8')
    old=subprocess.check_output(['git','show','backup/pre-intake-human-work-compression:src/executive_health_ai/services/intake_exceptions.py'],cwd=ROOT)
    (WORK/'legacy.py').write_bytes(old)
    print('Prepared synthetic member and two source documents; formal database untouched.')


def inspect():
    with SessionLocal() as s:
        member=s.scalar(select(Patient).where(Patient.display_name==NAME))
        row=s.scalar(select(IntakeAssessment).where(IntakeAssessment.patient_id==member.id))
        d=service.project(s,row);agent=s.scalar(select(MemberAgent).where(MemberAgent.member_id==member.id))
        spec=importlib.util.spec_from_file_location('intake_legacy_qa',WORK/'legacy.py')
        legacy=importlib.util.module_from_spec(spec);spec.loader.exec_module(legacy)
        old=legacy.project(s,row)
        events=list(s.scalars(select(HealthEvent).where(HealthEvent.member_id==member.id,HealthEvent.event_type=='INTAKE_ASSESSMENT_CONFIRMED')))
        goals=service.imports.goals(s,row)
        calls=list(s.scalars(select(ReportExtractionRun).where(ReportExtractionRun.patient_id==member.id)))
        return dict(status=row.status,counts=d['counts'],before=old['counts'],agent=str(agent.id),wakes=agent.wake_count,
            goals=[str(g.id) for g in goals],goal_states=[g.status for g in goals],ready=d['ready'],processing=d['processing'],
            queue=[{k:q.get(k) for k in ('key','kind','section','field','value','ambiguous')} for q in d['queue']],
            completion=service.state(row).get('completion'),
            resumed_events=[{'goal':str(e.goal_id),'action':e.route_action,'status':e.status} for e in events],
            resume_traces=len(list(s.scalars(select(AgentRunTrace.id).where(AgentRunTrace.goal_id.in_([g.id for g in goals]),AgentRunTrace.action=='intake_confirmation_resume')))),
            real_llm=[{'used':r.llm_used,'status':r.llm_status,'count':r.llm_call_count} for r in calls])


def browser_check():
    from playwright.sync_api import sync_playwright,expect
    with sync_playwright() as pw:
        browser=pw.chromium.launch(headless=True)
        page=browser.new_page(viewport={'width':1440,'height':900});page.set_default_timeout(45000)
        errors=[];page.on('pageerror',lambda e:errors.append(str(e)))
        def settle():
            page.wait_for_timeout(700) # Browser rendering settle only; never used by the business runtime.
            expect(page.locator('[data-testid="stApp"]')).to_have_attribute('data-test-script-state','notRunning',timeout=90000)
            assert not page.locator('[data-testid="stException"]').count(),page.locator('body').inner_text()
        def button(name):page.get_by_role('button',name=name,exact=True).click();settle()
        def radio(name):page.get_by_role('radio',name=name,exact=True).locator('xpath=ancestor::label').click();settle()
        def check(name):page.get_by_role('checkbox',name=name,exact=True).locator('xpath=ancestor::label').click();settle()
        def shot(name):
            page.locator('[data-testid="stMain"]').evaluate('(e)=>e.scrollTo(0,0)')
            page.screenshot(path=str(OUT/(name+'.png')),full_page=True)
            print(name,flush=True)
        try:
            page.goto('http://127.0.0.1:18723',wait_until='networkidle')
            entry=page.get_by_role('button',name='进入 HealthOps 运营后台',exact=True)
            menu=page.get_by_role('radio',name='会员',exact=True).locator('xpath=ancestor::label')
            entry.or_(menu).first.wait_for(state='visible',timeout=60000)
            if entry.count():button('进入 HealthOps 运营后台')
            radio('会员');search=page.get_by_label('搜索成员',exact=True);search.fill(NAME);search.press('Enter');settle()
            page.locator('[data-testid="stDataFrame"]').last.click(position={'x':150,'y':55});settle();radio('健康档案')
            if '--resume' not in sys.argv:
                shot('01-before-upload')
                page.locator('input[type=file]').set_input_files([str(WORK/f) for f in ('questionnaire.json','history.txt')]);settle()
                page.get_by_role('button',name='上传并整理资料',exact=True).click()
                page.locator('.agent-action-spinner').first.wait_for(state='visible',timeout=90000)
                shot('02-real-running')
            start=page.get_by_role('button',name=re.compile(r'^处理\d+项$'))
            start.wait_for(state='visible',timeout=600000);settle()
            initial=inspect();assert not initial['processing'];assert initial['counts']['optional_missing']>0
            assert not page.locator('.agent-action-spinner:visible').count()
            assert not page.get_by_text('AI与知识支持',exact=True).is_visible()
            assert not page.get_by_text('知识/术语辅助',exact=True).is_visible()
            assert page.get_by_role('button',name=re.compile(r'^处理\d+项$')).count()==1
            (OUT/'initial.json').write_text(json.dumps(initial,ensure_ascii=False,indent=2),encoding='utf-8')
            shot('03-compressed-workspace');start.click();settle();shot('04-exception-queue')
            typed=0;touched=0
            for _ in range(30):
                state=inspect()
                if state['ready']:break
                item=state['queue'][0]
                if item['kind']=='MISSING':
                    answer='七小时' if item['field']=='睡眠' else '改善午后精力' if item['field']=='concern' else '会员本人回答暂不清楚'
                    page.get_by_label('填写会员实际回答',exact=True).fill(answer)
                    button('保存答案并处理下一项');typed+=1
                elif item['kind']=='FILE':
                    page.get_by_label('未识别内容的处理说明',exact=True).fill('已核对合成原文，未识别内容保留原文件，不作额外医学解释。')
                    check('已核对原文件；未确认的档案候选保留待后续处理');button('完成本份资料核对')
                elif item['kind'] in {'CONFIRM','CONFLICT'}:
                    if item['ambiguous']:raise AssertionError('Unexpected ambiguous source; manual source review is required.')
                    if item['value']:button('确认并处理下一项' if item['kind']=='CONFIRM' else '采用并处理下一项')
                    else:
                        page.get_by_text('修改 / 忽略 / 暂不确认',exact=True).click();settle()
                        value='已戒烟' if item['field']=='烟草' else '每周快走三次' if item['field']=='运动' else '每周一杯葡萄酒' if item['field']=='饮酒' else None
                        if value is None:raise AssertionError('Needs explicit review: '+str(item))
                        page.get_by_label('修改为',exact=True).fill(value)
                        page.get_by_label('修改或忽略原因',exact=True).fill('合成会员本次已明确确认，与历史状态区分。')
                        button('保存修改并处理下一项');typed+=1
                else:raise AssertionError(str(item))
                touched+=1
                assert not page.get_by_role('combobox',name='填写步骤',exact=True).count()
            assert inspect()['ready'];shot('05-ready-single-confirmation')
            check('确认整理结果及已处理例外；可暂缺资料继续保持未知');button('确认完成初始健康评估')
            expect(page.get_by_text('初始健康评估已完成资料确认',exact=True)).to_be_visible()
            shot('06-submitted-next-step')
            final=inspect();original=json.loads((WORK/'member.json').read_text())
            assert final['agent']==original['agent']==initial['agent']
            assert final['goals']==initial['goals'] and all(s=='COMPLETED' for s in final['goal_states'])
            assert final['resumed_events'][0]['goal'] in initial['goals'] and final['resume_traces']==len(initial['goals'])
            assert final['status']=='SUBMITTED' and not errors
            assert any(c['used'] and c['status'] in {'SUCCESS','COMPLETED'} for c in final['real_llm']),final['real_llm']
            result={'actual_chromium':True,'browser':browser.version,'manual_fields_typed':typed,'manual_items_touched':touched,'full_wizard_traversal':False,'initial':initial,'final':final}
            (OUT/'verification.json').write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf-8')
            print(json.dumps({'before':initial['before'],'after':initial['counts'],'typed':typed,'touched':touched,'same_agent_and_goals':True},ensure_ascii=False),flush=True)
        except Exception:
            page.screenshot(path=str(WORK/'failure.png'),full_page=True)
            (WORK/'failure.txt').write_text(page.locator('body').inner_text(),encoding='utf-8');raise
        finally:browser.close()

if __name__=='__main__':
    prepare() if '--prepare' in sys.argv else browser_check()
