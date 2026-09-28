"""Real Chromium, isolated synthetic data, existing local model; no internal URLs."""
import json
import sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
WORK=ROOT/'.runtime/intake-exception-workflow'
OUT=ROOT/'docs/images/intake-exception-workflow'
WORK.mkdir(parents=True,exist_ok=True);OUT.mkdir(parents=True,exist_ok=True)
NAME='Demo Intake Exceptions V3'


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
    (WORK/'checkup-report.txt').write_text('体检日期：2026-09-28\n体重 78 kg\n',encoding='utf-8')


if '--prepare' in sys.argv:
    import sqlite3
    from sqlalchemy import create_engine
    from sqlalchemy.orm import Session
    from executive_health_ai.models import Patient
    from executive_health_ai.services.management_workflow import ManagementWorkflowService
    with sqlite3.connect(ROOT/'executive_health_ai.db') as source,sqlite3.connect(WORK/'qa.db') as destination:source.backup(destination)
    with Session(create_engine('sqlite:///'+(WORK/'qa.db').as_posix())) as session:
        patient=Patient(display_name=NAME,timezone='Asia/Tokyo');session.add(patient);session.flush()
        ManagementWorkflowService().start_intake(session,patient.id,2026,'验收健管');session.commit()
    fixtures()
    (WORK/'manifest.json').write_text(json.dumps({'intake-v3':{'source':str(ROOT),'database':str(WORK/'qa.db'),'port':18584}}),encoding='utf-8')
    sys.exit(0)


def persisted():
    from sqlalchemy import create_engine,select,func
    from sqlalchemy.orm import Session
    from executive_health_ai.models import Patient,AgentGoal,AgentRunTrace,ReportExtractionRun,ReportExtractionCandidate,Observation,MedicationPlan
    from executive_health_ai.models.management_workflow import IntakeAssessment
    from executive_health_ai.services.intake_exceptions import state,project
    with Session(create_engine('sqlite:///'+(WORK/'qa.db').as_posix())) as session:
        patient=session.scalar(select(Patient).where(Patient.display_name==NAME))
        row=session.scalar(select(IntakeAssessment).where(IntakeAssessment.patient_id==patient.id))
        goals=list(session.scalars(select(AgentGoal).where(AgentGoal.member_id==patient.id)))
        runs=list(session.scalars(select(ReportExtractionRun).where(ReportExtractionRun.patient_id==patient.id)))
        llm=list(session.scalars(select(ReportExtractionCandidate).where(ReportExtractionCandidate.patient_id==patient.id,ReportExtractionCandidate.extraction_method=='LLM')))
        traces=list(session.scalars(select(AgentRunTrace).where(AgentRunTrace.goal_id.in_([g.id for g in goals]),AgentRunTrace.action=='capability_activity')))
        calls=[t.metadata_json['capability'] for t in traces]
        return dict(status=row.status,completion=state(row).get('completion'),initial_counts=state(row).get('initial_counts'),
            progress=project(session,row)['counts'],responses=row.responses,
            calls=[{'llm_used':r.llm_used,'llm_status':r.llm_status,'llm_count':r.llm_call_count,
                    'actual_request_count':r.metadata_json.get('semantic_request_count',0)} for r in runs],
            llm_activity=[{k:call.get(k) for k in ('task','status','request_sent','latency_ms','result_count','accepted')} for call in calls if call.get('kind')=='LLM'],
            unmapped_warnings=[warning for r in runs for warning in r.metadata_json.get('coverage_warnings',[])],
            knowledge_calls=sum(call.get('task')=='retrieve_knowledge' for call in calls),
            real_llm_candidates=len(llm),all_agents_completed=all(g.status=='COMPLETED' for g in goals),
            observations=session.scalar(select(func.count(Observation.id)).where(Observation.patient_id==patient.id)),
            medications=session.scalar(select(func.count(MedicationPlan.id)).where(MedicationPlan.patient_id==patient.id)))


from playwright.sync_api import sync_playwright,expect
with sync_playwright() as p:
    browser=p.chromium.launch(headless=True)
    page=browser.new_page(viewport={'width':1440,'height':1150})
    page.set_default_timeout(30000);errors=[];page.on('pageerror',lambda e:errors.append(str(e)))
    def settle():
        page.wait_for_timeout(500)
        expect(page.locator('[data-testid="stApp"]')).to_have_attribute('data-test-script-state','notRunning',timeout=660000)
        page.locator('[data-testid="stStatusWidget"]').wait_for(state='hidden',timeout=660000)
        page.wait_for_function('!document.querySelector(\'[data-stale="true"]\')',timeout=30000)
        assert not page.locator('[data-testid="stException"]').count(),page.locator('body').inner_text()
    def button(name):page.get_by_role('button',name=name,exact=True).click();settle()
    def radio(name):page.get_by_role('radio',name=name,exact=True).locator('xpath=ancestor::label').click();settle()
    def check(name):page.get_by_role('checkbox',name=name,exact=True).locator('xpath=ancestor::label').click();settle()
    def shot(name):
        if name in {'04-exceptions-ready.png','05-conflict-source-review.png','06-ready-for-single-confirmation.png','07-submitted-workspace.png'}:
            page.locator('.st-key-intake-exception-workspace').screenshot(path=str(OUT/name))
        else:page.screenshot(path=str(OUT/name),full_page=True)
    try:
        page.goto('http://127.0.0.1:18584',wait_until='networkidle');settle()
        if page.get_by_role('button',name='进入 HealthOps 运营后台',exact=True).count():button('进入 HealthOps 运营后台')
        radio('会员');search=page.get_by_label('搜索成员',exact=True);search.fill(NAME);search.press('Enter');settle()
        page.locator('[data-testid="stDataFrame"]').last.click(position={'x':100,'y':55});settle()
        button('查看会员 / 进入Member360');radio('健康档案')
        if '--inspect' in sys.argv:
            expect(page.get_by_text('初始健康评估资料已提交',exact=True)).to_be_visible()
            assert not page.locator('.intake-spinner').count()
            assert '本地AI开始整理自由文本' in page.locator('body').inner_text()
            assert '已纳入本次初评确认' in page.locator('body').inner_text()
            page.set_viewport_size({'width':1440,'height':2900})
            page.locator('[data-testid="stMain"]').evaluate('(e)=>e.scrollTo(0,0)')
            shot('08-complete-workspace.png')
            print('Completed workspace and retained real AI timeline verified',flush=True)
            sys.exit(0)
        if '--resume' not in sys.argv:shot('01-empty-workspace.png')
        if '--resume' not in sys.argv:
            page.locator('input[type=file]').set_input_files([str(WORK/n) for n in ('questionnaire.json','history.txt','checkup-report.txt')]);settle()
            page.get_by_role('button',name='上传并整理资料',exact=True).click()
            expect(page.locator('.intake-spinner')).to_be_visible(timeout=60000)
            shot('02-real-running-spinner.png')
            expect(page.locator('.intake-agent-current')).to_contain_text('本地AI正在整理资料',timeout=120000)
            shot('03-real-local-ai.png')
            print('Real local AI request visible in Chromium',flush=True)
            expect(page.get_by_role('heading',name='本次资料整理已完成',exact=True)).to_be_visible(timeout=660000);settle()
        assert page.locator('.intake-spinner').count()==0
        assert '本流程未使用' in page.locator('body').inner_text()
        assert not persisted()['unmapped_warnings']
        if '--resume' not in sys.argv:shot('04-exceptions-ready.png')
        start=page.get_by_role('button',name='处理剩余')
        if start.count():start.click();settle()
        typed=persisted()['progress']['manual_fields'] if '--resume' in sys.argv else 0
        for index in range(20):
            panel=page.locator('.st-key-intake-exception-workspace')
            if not persisted()['progress']['exceptions']:
                expect(panel.get_by_text('初始健康评估已准备完成',exact=True)).to_be_visible()
                break
            body=panel.inner_text()
            if '初始健康评估已准备完成' in body:break
            if '填写会员实际回答' in body:
                answer='七小时' if '睡眠' in body else '改善午后精力'
                page.get_by_label('填写会员实际回答',exact=True).fill(answer)
                button('保存答案并处理下一项');typed+=1
            elif page.get_by_role('button',name='采用并处理下一项',exact=True).count():
                shot('05-conflict-source-review.png');button('采用并处理下一项')
            elif page.get_by_role('button',name='确认并处理下一项',exact=True).count():button('确认并处理下一项')
            elif page.get_by_role('button',name='完成本份资料核对',exact=True).count():
                if page.get_by_role('button',name='确认以上测量并同步健康档案',exact=True).count():button('确认以上测量并同步健康档案')
                # Unmapped source warnings are a real failure of this acceptance dataset.
                assert not persisted()['unmapped_warnings']
                if not persisted()['progress']['exceptions']:continue
                check('已核对原文件；未确认的档案候选保留待后续处理')
                action=page.get_by_role('button',name='完成本份资料核对',exact=True)
                # Streamlit may replace the queue while Playwright completes a
                # click. Verify the persisted outcome instead of clicking twice.
                try:action.click(timeout=5000);settle()
                except Exception:
                    if persisted()['progress']['exceptions']:raise
                    settle()
            else:raise AssertionError(body)
        assert '初始健康评估已准备完成' in panel.inner_text()
        assert not page.get_by_role('combobox',name='填写步骤').count()
        shot('06-ready-for-single-confirmation.png')
        if page.get_by_role('checkbox',name='这些可选资料尚未提供，继续保留未知',exact=True).count():check('这些可选资料尚未提供，继续保留未知')
        check('我已核对来源及整理结果，确认提交初评资料')
        button('确认并完成初始健康评估')
        expect(page.get_by_text('初始健康评估资料已提交',exact=True)).to_be_visible()
        assert page.locator('.intake-spinner').count()==0
        shot('07-submitted-workspace.png')
        result=persisted()
        assert result['real_llm_candidates']>=2 and result['status']=='SUBMITTED'
        assert result['observations']==1 and result['medications']==0
        assert result['completion']['manual_fields']==2 and typed==2
        assert result['knowledge_calls']==0
        assert sum(c['actual_request_count'] for c in result['calls'])==1
        assert all(c['status']=='SUCCESS' and c['request_sent'] and c['accepted'] for c in result['llm_activity'])
        assert result['responses']['生活方式']['烟草']=='已戒烟'
        assert not errors
        (OUT/'browser-results.json').write_text(json.dumps(dict(browser=browser.version,actual_browser=True,
            manager_typed_fields=typed,full_wizard_traversal=False,errors=errors,**result),ensure_ascii=False,indent=2),encoding='utf-8')
        print(json.dumps(result,ensure_ascii=False),flush=True)
    except Exception:
        shot('failure.png');(OUT/'failure.txt').write_text(page.locator('body').inner_text(),encoding='utf-8');raise
    finally:browser.close()
