"""Archive acceptance in actual Chromium using an isolated synthetic database.

Run --prepare, then start the QA manifest using service_processes.py, then run
without arguments. Never opens or modifies the formal Demo database.
"""
import json
import os
import re
import sys
from pathlib import Path
from uuid import UUID
ROOT=Path(__file__).resolve().parents[1]
case=os.environ.get('HEALTHOPS_ARCHIVE_QA_CASE','member-list-removal')
assert re.fullmatch(r'[a-zA-Z0-9_-]+',case)
DATA=ROOT/'.runtime'/case
OUT=ROOT/'docs/images/member-list-removal'
DATA.mkdir(parents=True,exist_ok=True)
OUT.mkdir(parents=True,exist_ok=True)
os.environ['DATABASE_URL']='sqlite:///'+(DATA/'browser.db').as_posix()
os.environ['LOCAL_LLM_ENABLED']='false'
sys.stdout.reconfigure(encoding='utf-8')
from sqlalchemy import select,func
from executive_health_ai.database import SessionLocal,engine
from executive_health_ai.models import Base,Patient,MemberAgent,AgentGoal,AgentRunTrace,Observation,HealthProgram,Document


def prepare():
    from datetime import date,timedelta
    from executive_health_ai.models.base import utc_now
    from executive_health_ai.services.management_workflow import ManagementWorkflowService
    from executive_health_ai.services.report_parsing import ReportParsingService
    from executive_health_ai.services.profile_ingestion import ProfileIngestionService
    from executive_health_ai.models.management_workflow import ManagementLog
    if (DATA/'members.json').exists():raise RuntimeError('QA data already exists; do not reset historical records.')
    Base.metadata.create_all(engine)
    records={}
    with SessionLocal() as s:
        for suffix in ('Waiting','Running'):
            name='Demo Archive '+suffix
            member=s.scalar(select(Patient).where(Patient.display_name==name))
            program=s.scalar(select(HealthProgram).where(HealthProgram.patient_id==member.id)) if member else ManagementWorkflowService().enroll(s,name=name,start=date.today(),end=date.today()+timedelta(days=364),owner='合成健管',goal='归档验收，保留健康资料')
            parser=ReportParsingService();parser.storage_root=DATA/'uploads'
            if not s.scalar(select(Document.id).where(Document.patient_id==program.patient_id)):parser.upload_and_parse(s,program.patient_id,'archive-checkup.txt',('体检日期：'+date.today().isoformat()+'\n体重  85.8 kg\n低密度脂蛋白胆固醇  4.15 mmol/L').encode(),'合成健管')
            if not s.scalar(select(ManagementLog.id).where(ManagementLog.patient_id==program.patient_id)):
                s.add(ManagementLog(patient_id=program.patient_id,program_id=program.id,occurred_at=__import__('executive_health_ai.models.base',fromlist=['utc_now']).utc_now(),category='随访',channel='电话',member_issue='合成会员反馈',manager_action='记录反馈',result='历史结果保留',next_action='后续随访',owner='合成健管',evidence='合成验收记录',request_key='archive-qa-'+suffix,created_by='合成健管'))
            if not s.scalar(select(Observation.id).where(Observation.patient_id==program.patient_id)):
                s.add(Observation(patient_id=program.patient_id,observed_at=utc_now(),metric_code='weight',value_numeric=85.8,unit='kg',source='synthetic_archive_qa',quality_flag='valid'))
            if suffix=='Running':
                importer=ProfileIngestionService();importer.storage_root=DATA/'uploads'
                g,_=importer.upload(s,program.patient_id,'archive-questionnaire.json',json.dumps({'responses':{'生活方式':{'睡眠':'每天七小时'}}},ensure_ascii=False).encode(),'questionnaire',actor='合成健管',role='HEALTH_MANAGER')
                assert g.status=='RUNNING'
            s.commit()
            identity=s.scalar(select(MemberAgent).where(MemberAgent.member_id==program.patient_id))
            records[suffix]={'id':str(program.patient_id),'name':name,'identity':str(identity.id),'wakes':identity.wake_count}
        records['counts']={t.name:s.scalar(select(func.count()).select_from(t)) for t in Base.metadata.sorted_tables}
        records['traces']=[str(i) for i in s.scalars(select(AgentRunTrace.id))]
        assert records['counts']['observations']>0 and records['traces']
    (DATA/'members.json').write_text(json.dumps(records,ensure_ascii=False,indent=2),encoding='utf-8')
    (DATA/'manifest.json').write_text(json.dumps({'archive':{'source':str(ROOT),'database':str(DATA/'browser.db'),'port':18721}},indent=2),encoding='utf-8')
    print('Prepared isolated synthetic archive fixtures.')


def verify_history():
    records=json.loads((DATA/'members.json').read_text(encoding='utf-8'))
    from executive_health_ai.models.base import utc_now
    from executive_health_ai.services.operational_worklist import OperationalWorklistService
    with SessionLocal() as s:
        for suffix in ('Waiting','Running'):
            record=records[suffix];member=s.get(Patient,UUID(record['id']))
            if suffix=='Running':
                assert not member.archived_at
                assert s.get(MemberAgent,UUID(record['identity'])).status=='RUNNING'
                continue
            assert member.archived_at
            identity=s.get(MemberAgent,UUID(record['identity']))
            assert identity.member_id==member.id and identity.status=='IDLE' and identity.wake_count==record['wakes']
            assert all(g.status in {'COMPLETED','CANCELLED'} for g in s.scalars(select(AgentGoal).where(AgentGoal.member_id==member.id)))
            assert not any(i.member_id==member.id for i in OperationalWorklistService().list_items(s,utc_now()))
        for t in Base.metadata.sorted_tables:assert s.scalar(select(func.count()).select_from(t))>=records['counts'][t.name],t.name
        assert set(records['traces'])<={str(i) for i in s.scalars(select(AgentRunTrace.id))}
    print('All historical rows, observations, identities and traces preserved; no normal human work.')


def browser_check():
    from playwright.sync_api import sync_playwright,expect
    with sync_playwright() as p:
        browser=p.chromium.launch(headless=True)
        page=browser.new_page(viewport={'width':1440,'height':900})
        page.set_default_timeout(30000)
        errors=[];page.on('pageerror',lambda e:errors.append(str(e)))
        def settle():
            page.wait_for_timeout(850)
            expect(page.locator('[data-testid="stApp"]')).to_have_attribute('data-test-script-state','notRunning',timeout=60000)
            assert not page.locator('[data-testid="stException"]').count(),page.locator('body').inner_text()
            assert not errors,errors
        def button(name):page.get_by_role('button',name=name,exact=True).click();settle()
        def radio(name):page.get_by_role('radio',name=name,exact=True).locator('xpath=ancestor::label').click();settle()
        def search(value):
            f=page.get_by_label('搜索成员',exact=True);f.fill(value);f.press('Enter');settle()
        def row():page.locator('[data-testid="stDataFrame"]').last.click(position={'x':150,'y':55});settle()
        def shot(name):page.screenshot(path=str(OUT/name))
        page.goto('http://127.0.0.1:18721',wait_until='networkidle');settle()
        entry=page.get_by_role('button',name='进入 HealthOps 运营后台',exact=True)
        entry.or_(page.get_by_role('radio',name='会员',exact=True).locator('xpath=ancestor::label')).first.wait_for(state='visible',timeout=60000)
        if entry.count():button('进入 HealthOps 运营后台')
        radio('会员')
        assert not page.get_by_role('button',name='归档会员',exact=True).count()
        for suffix in ('Running','Waiting'):
            name='Demo Archive '+suffix
            search(name)
            grid=page.locator('[data-testid="stDataFrame"]').last
            shot('00-member-list.png')
            if '--inspect' in sys.argv:
                print('Grid:',grid.bounding_box())
                browser.close();return
            grid.click(position={'x':grid.bounding_box()['width']-35,'y':55});settle()
            expect(page.get_by_role('dialog',name='删除会员',exact=True)).to_be_visible()
            expect(page.get_by_label('搜索成员',exact=True)).to_be_visible()
            expect(page.get_by_role('button',name='← 返回会员',exact=True)).to_have_count(0)
            if suffix=='Running':
                assert '该会员当前仍有自动化流程正在运行' in page.get_by_role('dialog',name='删除会员',exact=True).inner_text()
                expect(page.get_by_role('button',name='确认删除',exact=True)).to_have_count(0)
                expect(page.get_by_role('button',name='停止当前流程并归档',exact=True)).to_have_count(0)
                shot('01-running-blocked.png')
                button('取消');continue
            confirm='确认删除'
            expect(page.get_by_role('button',name=confirm,exact=True)).to_be_disabled()
            label='请输入会员姓名“'+name+'”确认'
            for wrong in ('wrong',name+' '):
                f=page.get_by_label(label,exact=True);f.fill(wrong);f.press('Enter');settle()
                expect(page.get_by_role('button',name=confirm,exact=True)).to_be_disabled()
            shot('02-name-confirmation.png')
            button('取消');expect(page.get_by_role('dialog',name='删除会员',exact=True)).to_have_count(0)
            grid.click(position={'x':grid.bounding_box()['width']-35,'y':55});settle()
            f=page.get_by_label(label,exact=True);f.fill(name);f.press('Enter');settle()
            button(confirm)
            expect(page.get_by_role('dialog',name='删除会员',exact=True)).to_have_count(0)
            expect(page.get_by_label('搜索成员',exact=True)).to_be_visible()
            assert '未找到匹配会员' in page.locator('body').inner_text()
            shot('03-active-list-hidden.png')
        selector=page.get_by_label('状态',exact=True);selector.click();page.get_by_role('option',name='已归档',exact=True).click();settle()
        search('Demo Archive Waiting');shot('04-archived-filter.png');row()
        assert '已归档' in page.locator('body').inner_text()
        assert not page.get_by_role('button',name='···',exact=True).count()
        for tab in ('概览','健康档案','管理','医疗','历程'):
            radio(tab)
            assert not any(x in page.locator('body').inner_text() for x in ('恢复会员','确认并提交初始健康评估','处理下一步'))
            if tab=='健康档案':
                expect(page.get_by_role('heading',name='原始资料',exact=True)).to_be_visible()
                assert page.locator('[data-testid="stDataFrame"]').count()>=2
                shot('05-archived-health-records.png')
        button('← 返回会员')
        selector=page.get_by_label('状态',exact=True);selector.click();page.get_by_role('option',name='全部',exact=True).click();settle()
        search('Demo Archive');shot('06-all-filter.png')
        selector.click();page.get_by_role('option',name='在管',exact=True).click();settle()
        search('Demo Archive Running');row()
        for tab in ('概览','健康档案','管理','医疗','历程'):
            radio(tab)
            assert not page.get_by_role('button',name='···',exact=True).count()
            assert not page.get_by_role('button',name='归档会员',exact=True).count()
        shot('07-no-member360-delete.png')
        verify_history()
        result={'browser':'Chromium '+browser.version,'viewport':'1440x900','entry_count':1,'entry_location':'MEMBER LIST','row_navigation_conflict':False,'exact_name':True,'running_protected':True,'history_preserved':True,'archived_tabs':'5 passed','errors':errors}
        (OUT/'verification.json').write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf-8')
        print(json.dumps(result,ensure_ascii=False))
        browser.close()


if __name__=='__main__':
    if '--prepare' in sys.argv:prepare()
    elif '--verify' in sys.argv:verify_history()
    else:browser_check()
