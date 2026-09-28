"""Real Chromium story on a disposable synthetic database, public navigation only."""
import json, os, sys, re
from pathlib import Path
sys.stdout.reconfigure(encoding='utf-8')
ROOT=Path(__file__).resolve().parents[1]
WORK=ROOT/'.runtime/service-operations';OUT=ROOT/'docs/images/service-operations-alignment'
if '--smoke' in sys.argv:OUT=WORK/'live-smoke'
if '--smoke' not in sys.argv and os.getenv('HEALTHOPS_QA_URL','http://127.0.0.1:18587') not in {
        'http://127.0.0.1:18587','http://127.0.0.1:18588'}:
    raise SystemExit('Business writes are restricted to the disposable V6 QA instances')
WORK.mkdir(parents=True,exist_ok=True);OUT.mkdir(parents=True,exist_ok=True)
if '--prepare' in sys.argv:
    from sqlalchemy import create_engine
    from sqlalchemy.orm import Session
    from executive_health_ai.models import Base,ServiceCatalogItem
    db=WORK/'qa.db'
    if db.exists():raise SystemExit('QA database already exists; not overwritten')
    engine=create_engine('sqlite:///'+db.as_posix());Base.metadata.create_all(engine)
    with Session(engine) as s:
        s.add(ServiceCatalogItem(code='V6_SYNTHETIC',name='阶段健康沟通（合成）',category='连续管理',description='仅合成验收，无对外预约'));s.commit()
    (WORK/'manifest.json').write_text(json.dumps({'service-v6':{'source':str(ROOT),'database':str(db),'port':18587}}),encoding='utf-8')
    raise SystemExit(0)

from playwright.sync_api import sync_playwright,expect
with sync_playwright() as p:
    browser=p.chromium.launch(headless=True);page=browser.new_page(viewport={'width':1440,'height':1100})
    page.set_default_timeout(30000)
    def settle():
        page.wait_for_timeout(700)
        expect(page.locator('[data-testid="stApp"]')).to_have_attribute('data-test-script-state','notRunning',timeout=90000)
        page.wait_for_function('!document.querySelector(\'[data-stale="true"]\')')
        assert not page.locator('[data-testid="stException"]').count(),page.locator('body').inner_text()
    def button(label):page.get_by_role('button',name=label,exact=True).click();settle()
    def radio(label):page.get_by_role('radio',name=label,exact=True).locator('xpath=ancestor::label').click();settle()
    def fill(label,value):page.get_by_label(label,exact=True).fill(value)
    def select(label,value):
        box=page.get_by_label(label,exact=True);box.click();box.fill(value);box.press('ArrowDown')
        page.get_by_role('option',name=value,exact=True).click();settle()
    def check(label):page.get_by_role('checkbox',name=label,exact=True).locator('xpath=ancestor::label').click();settle()
    def shot(name):
        page.locator('[data-testid="stMain"]').evaluate('(e)=>e.scrollTo(0,0)')
        page.screenshot(path=str(OUT/(name+'.png')))
        (OUT/(name+'.txt')).write_text(page.locator('body').inner_text(),encoding='utf-8')
        print(name,flush=True)
    def member():
        radio('会员');fill('搜索成员','Demo Executive A');page.get_by_label('搜索成员',exact=True).press('Enter');settle()
        if '--smoke' in sys.argv and not page.locator('[data-testid="stDataFrame"]').count():
            fill('搜索成员','');page.get_by_label('搜索成员',exact=True).press('Enter');settle()
        page.locator('[data-testid="stDataFrame"]').last.click(position={'x':160,'y':55});settle()
    def role(label):
        page.get_by_text('切换演示角色',exact=True).click();radio(label)
        page.get_by_text('切换演示角色',exact=True).click();settle()
    try:
        page.goto(os.getenv('HEALTHOPS_QA_URL','http://127.0.0.1:18587'),wait_until='networkidle');settle()
        if page.get_by_role('button',name='进入 HealthOps 运营后台',exact=True).count():button('进入 HealthOps 运营后台')
        if '--smoke' in sys.argv:
            shot('21-live-today')
            fill('查找待办','新会员资料收集');page.get_by_label('查找待办',exact=True).press('Enter');settle()
            if page.locator('[data-testid="stDataFrame"]').count():
                page.locator('[data-testid="stDataFrame"]').last.click(position={'x':160,'y':55});settle()
                expect(page.get_by_role('radio',name='健康档案',exact=True)).to_be_checked()
                expect(page.locator('[data-testid="stFileUploader"]')).to_have_count(1)
                assert not page.get_by_role('combobox',name='填写步骤',exact=True).count()
                shot('live-today-to-intake-agent')
            for label in ['年度管理','服务管理','医疗协同','专项管理']:
                radio(label);shot('live-'+label)
            member()
            for label in ['概览','健康档案','管理','医疗','历程']:
                radio(label);shot('live-member360-'+label)
            role('医生')
            for label in ['待我判断','历史']:radio(label);shot('live-doctor-'+label)
            role('成员')
            for label in ['首页','健康','计划','服务','历程']:radio(label);shot('live-member-'+label)
            role('管理员')
            for label in ['系统状态','自动化运行','数据与集成','规则与知识']:radio(label);shot('live-admin-'+label)
            (OUT/'live-smoke.json').write_text(json.dumps({'browser':browser.version,'url':os.getenv('HEALTHOPS_QA_URL'),
                'manager':'PASS','doctor':'PASS','member':'PASS','admin':'PASS','exceptions':0},ensure_ascii=False,indent=2),encoding='utf-8')
        elif '--today-routing' in sys.argv:
            member();radio('概览');button('处理下一步')
            fill('处理结果','已核对下一阶段执行安排，等待阶段复盘（合成）');button('完成本次处理')
            radio('今日工作');fill('查找待办','阶段复盘');page.get_by_label('查找待办',exact=True).press('Enter');settle()
            page.locator('[data-testid="stDataFrame"]').last.click(position={'x':160,'y':55});settle()
            assert '下一阶段持续管理' in page.locator('body').inner_text()
            assert '阶段复盘' in page.locator('body').inner_text()
            shot('21-early-phase-review-in-today')
            radio('会员')
            back=page.get_by_role('button',name='← 返回会员',exact=True)
            if back.count():button('← 返回会员')
            page.get_by_text('会员入组 · 新建年度服务周期',exact=True).click();settle()
            fill('会员称呼','V6入口验证会员（合成）');fill('责任健康管理师','V6责任健管');fill('年度目标','仅验证新会员今日资料入口')
            button('确认入组');radio('今日工作');fill('查找待办','V6入口验证会员');page.get_by_label('查找待办',exact=True).press('Enter');settle()
            page.locator('[data-testid="stDataFrame"]').last.click(position={'x':160,'y':55});settle()
            expect(page.get_by_role('radio',name='健康档案',exact=True)).to_be_checked()
            expect(page.locator('[data-testid="stFileUploader"]')).to_have_count(1)
            assert not page.get_by_role('combobox',name='填写步骤',exact=True).count()
            shot('22-today-to-agent-not-wizard')
            (OUT/'today-routing.json').write_text(json.dumps({'early_phase_review':True,'new_member_to_agent':True,'browser':browser.version}),encoding='utf-8')
        elif '--enroll' in sys.argv:
            shot('01-manager-home');radio('会员')
            page.get_by_text('会员入组 · 新建年度服务周期',exact=True).click();settle()
            fill('会员称呼','Demo Executive A');fill('责任健康管理师','V6责任健管');fill('年度目标','睡眠与体重记录、服务执行和阶段复盘（合成）')
            button('确认入组');member();shot('02-enrolled-owner');radio('健康档案')
            responses={'基础资料':{'display_name':'Demo Executive A','birth_date':'1980-01-01','sex':'male'},
                '家族健康史':[{'疾病类别':'会员回答','具体疾病':'暂不清楚','患病家属':'父亲','备注':'合成问卷原话'}],
                '个人病史':[], '手术 / 住院史':[], '过敏史':[], '当前用药 / 营养补充':[], '最近用药':[],
                '生活方式':{'睡眠':'七小时','运动':'每周步行三次','饮食':'规律三餐','烟草':'本人回答不吸烟','饮酒':'本人回答不饮酒','工作压力':'一般','休假':'每年两周','生活规律':'固定作息'},
                '环境与暴露':{'空气污染':'市区','工业暴露':'办公室','噪音':'普通住宅','宠物':'未养宠物','香氛':'未使用','油烟 / 二手烟':'厨房有排烟','潮湿 / 霉菌':'通风','装修':'五年前','食品暴露':'家常饮食','个人用品暴露':'常规洗护'},
                '会员重点关注':{'concern':'希望建立规律睡眠与体重记录'},'专项症状评估':[]}
            payload=json.dumps({'source_date':'2026-09-28','responses':responses},ensure_ascii=False).encode()
            page.locator('input[type=file]').set_input_files({'name':'V6合成会员问卷.json','mimeType':'application/json','buffer':payload});settle();button('上传并整理资料')
            shot('03-agent-and-exceptions')
            start=page.get_by_role('button',name=re.compile('^处理剩余'))
            if start.count():start.click();settle()
            for _ in range(40):
                body=page.locator('body').inner_text()
                if page.get_by_role('button',name='确认并完成初始健康评估',exact=True).count():break
                if page.get_by_role('textbox',name='填写会员实际回答',exact=True).count():
                    fill('填写会员实际回答','会员本人明确回答暂不清楚（合成）；保持未知');button('保存答案并处理下一项')
                elif page.get_by_role('button',name='确认并处理下一项',exact=True).count():button('确认并处理下一项')
                elif page.get_by_role('button',name='完成本份资料核对',exact=True).count():
                    check('已核对原文件；未确认的档案候选保留待后续处理');button('完成本份资料核对')
                else:raise AssertionError(body)
            optional=page.get_by_role('checkbox',name='这些可选资料尚未提供，继续保留未知',exact=True)
            if optional.count():check('这些可选资料尚未提供，继续保留未知')
            check('我已核对来源及整理结果，确认提交初评资料');button('确认并完成初始健康评估');shot('04-intake-submitted')
        elif '--review' in sys.argv:
            member();radio('健康档案');button('查看 / 手工修正（11步）')
            fill('专业管理重点','核对睡眠与体重记录，按阶段落实服务（合成）')
            fill('初步年度管理重点','建立规律记录与人工回访')
            select('初评决定','确认初评 / 交医生确认');button('保存健管初评');shot('05-manager-assessment')
            button('← 返回健康档案');button('查看完整健康档案');shot('06-full-archive')
        elif '--baseline' in sys.argv:
            member();radio('健康档案');button('查看完整健康档案')
            grid=page.locator('.st-key-soft-archive-details [data-testid="stDataFrame"]')
            grid.locator('.dvn-scroller').evaluate('(e)=>e.scrollTop=e.scrollHeight')
            page.wait_for_timeout(300)
            grid.click(position={'x':170,'y':365});settle()
            shot('07-baseline-entry')
            page.get_by_text('建立年度健康基线初稿或阶段复评',exact=True).click();settle()
            fill('健康管理摘要','基于会员已确认问卷建立资料参考点；睡眠七小时，疾病与用药未知项保持未知（合成）。')
            button('保存初稿');button('确认健康基线');shot('08-confirmed-baseline')
            radio('管理');select('管理工作','年度方案与阶段')
            fill('阶段名称','睡眠记录与服务执行（合成）');fill('阶段目标','完成沟通服务并核对执行结果')
            fill('管理内容','安排健康沟通服务、回访和阶段复盘，不作医学判断')
            button('保存阶段');button('启动年度方案');shot('09-active-phase')
        elif '--execute' in sys.argv or '--handoff' in sys.argv or '--doctor' in sys.argv or '--finish' in sys.argv:
            if '--doctor' not in sys.argv and '--finish' not in sys.argv:
                if '--execute' in sys.argv:
                    member();radio('管理');button('创建随访')
                    fill('随访事项','核对本周睡眠记录（合成）');fill('需要跟进什么','电话核对本人记录与执行困难')
                    button('创建随访待办');fill('处理结果','已电话核对，本人表示可以持续记录（合成）');button('完成本次处理')
                    button('申请服务');fill('申请原因','按当前阶段方案安排健康沟通，完成后回访（合成）');button('提交服务申请')
                    shot('10-plan-service-owner');button('审核申请');fill('服务执行方（可选）','V6合成服务团队 / 线上')
                    button('确认服务安排');shot('11-appointment');button('确认开始服务')
                    fill('服务结果','已完成健康沟通，会员反馈已理解记录方法（合成）');fill('完成依据','合成会员与服务方完成确认')
                    button('记录服务完成');button('继续处理下一项')
                    fill('随访情况 / 处理结果','已回访并确认服务结果，继续当前记录安排（合成）');button('完成本次处理');shot('12-service-result-writeback')
                    button('← 返回本会员管理工作区');select('管理工作','计划调整与随访');radio('记录阶段结果')
                    select('观察指标','体重');fill('起点数值','90');fill('本次数值','85.8');fill('已确认目标值（选填）','83');fill('单位','kg')
                    fill('结果依据','合成验收称重记录：起点90kg、本次85.8kg；仅观察差异，不作服务因果归因')
                    fill('下一步说明','继续核对记录，按约定开展下一阶段沟通')
                    button('记录阶段结果并安排下一步');radio('概览');button('处理下一步')
                else:
                    member();radio('概览');button('处理下一步')
                for _ in range(8):
                    if page.get_by_role('button',name='完成本次处理',exact=True).count():
                        field=page.get_by_role('textbox',name=re.compile('处理结果$'))
                        field.fill('已核对阶段安排，后续按现有方案执行（合成）');button('完成本次处理')
                    elif page.get_by_role('button',name='继续处理下一项',exact=True).count():button('继续处理下一项')
                    else:break
                button('开始阶段复盘');fill('未解决问题','请医生核对现有记录是否需要医学进一步判断（合成，不请求自动诊断）')
                check('未解决问题需要医生判断');check('我已核对阶段结果，确认本次复盘');shot('13-stage-review');button('确认阶段总结')
            if '--finish' not in sys.argv:
                role('医生')
                for x in (160,100,15):
                    page.locator('[data-testid="stDataFrame"]').last.click(position={'x':x,'y':55});settle()
                    if page.get_by_role('textbox',name='医学判断',exact=True).count():break
                fill('医学判断','已人工核对合成记录；本次不作新增诊断。');fill('建议','继续记录，必要医学问题由责任医生另行评估。')
                shot('14-doctor-boundary');button('提交判断');shot('15-doctor-submitted')
            role('健康管理师');member();radio('概览');button('处理下一步')
            for _ in range(8):
                if page.get_by_role('button',name='完成本次处理',exact=True).count():
                    page.get_by_role('textbox',name=re.compile('处理结果$')).fill('已核对医生返回意见，执行已有非医学管理安排（合成）');button('完成本次处理')
                elif page.get_by_role('button',name='继续处理下一项',exact=True).count():button('继续处理下一项')
                else:break
            if page.get_by_role('button',name='进入下一阶段',exact=True).count():button('进入下一阶段')
            button('确认并进入下一阶段')
            assert '确认下一阶段执行安排' in page.locator('body').inner_text()
            assert '仍有本阶段开放事项' not in page.locator('body').inner_text()
            shot('16-next-phase')
            radio('服务管理');shot('17-service-operations');radio('专项管理');shot('18-special-progress')
            page.locator('[data-testid="stDataFrame"]').last.click(position={'x':160,'y':55});settle();button('进入该会员专项管理');shot('19-same-member360')
            role('管理员');page.get_by_text('组织与人员',exact=True).click();settle();shot('20-organization-boundary')
            (OUT/'story-result.json').write_text(json.dumps({'browser':browser.version,'public_navigation':True,'errors':0,'full_story':True},indent=2),encoding='utf-8')
        else:
            member();radio('健康档案');shot('inspect-health')
    except Exception:
        page.screenshot(path=str(OUT/'failure.png'))
        (OUT/'failure.txt').write_text(page.locator('body').inner_text(),encoding='utf-8');raise
    finally:browser.close()
