"""Real Chromium uploads against an isolated synthetic demo database."""
import json
import os
from pathlib import Path
from playwright.sync_api import sync_playwright, expect

OUT=Path('docs/images/profile-intake-agent');OUT.mkdir(parents=True,exist_ok=True)

with sync_playwright() as p:
    browser=p.chromium.launch(headless=True)
    page=browser.new_page(viewport={'width':1440,'height':1100})
    def settle():
        page.wait_for_timeout(450)
        page.locator('[data-testid="stStatusWidget"]').wait_for(state='hidden',timeout=90000)
        page.wait_for_timeout(700)
        assert not page.locator('[data-testid="stException"]').count(),page.locator('body').inner_text()
    def button(name):
        page.get_by_role('button',name=name,exact=True).click();settle()
    def radio(name):
        page.get_by_role('radio',name=name,exact=True).locator('xpath=ancestor::label').click();settle()
    def shot(name):
        page.locator('[data-testid="stMain"]').evaluate('e=>e.scrollTop=0')
        page.screenshot(path=str(OUT/name),full_page=True)
    def member():
        radio('会员')
        field=page.get_by_role('textbox',name='搜索成员',exact=True)
        if field.count():
            field.fill('Demo Executive A');field.press('Enter');settle()
            page.locator('[data-testid="stDataFrame"]').first.click(position={'x':65,'y':55});settle()
        radio('健康档案')
    def upload(dtype,name,content,first=False):
        button('＋ 导入健康资料');radio(dtype)
        page.locator('input[type=file]').set_input_files({'name':name,'mimeType':'text/plain','buffer':content})
        settle()
        if first:shot('02-upload-document.png')
        button('上传并整理资料')
        if first:shot('03-agent-parsing.png')
        expect(page.get_by_role('button',name='确认并更新健康档案',exact=True)).to_be_visible(timeout=90000)
        settle()
    try:
        page.goto(os.getenv('QA_URL','http://127.0.0.1:8502'),wait_until='networkidle');settle()
        button('进入 HealthOps 运营后台');member();shot('01-health-record-upload-entry.png')
        upload('体检报告','合成验收体检.txt','体检日期：2026-09-27\n体重：85.7 kg\nLDL-C：3.65 mmol/L\nALT：38 U/L\n'.encode(),True)
        shot('04-extraction-preview.png');shot('06-manager-confirm.png')
        button('确认并更新健康档案')
        expect(page.get_by_text('本次健康资料已整理完成',exact=True)).to_be_visible(timeout=30000)
        shot('11-report-completed.png');button('← 返回健康档案');settle()
        questionnaire={'source_date':'2026-09-27','responses':{'生活方式':{'烟草':'偶尔吸烟','睡眠':'每天七小时'},'过敏史':[{'名称':'花粉','来源':'会员自述'}],'会员重点关注':{'concern':'改善睡眠'}}}
        upload('健康问卷','合成验收问卷.json',json.dumps(questionnaire,ensure_ascii=False).encode())
        shot('12-questionnaire-preview.png')
        button('确认并更新健康档案');expect(page.get_by_text('本次健康资料已整理完成',exact=True)).to_be_visible(timeout=30000)
        button('← 返回健康档案');settle()
        history={'source_date':'2026-09-27','responses':{'生活方式':{'烟草':'无'},'个人病史':[{'疾病或问题':'既往脂肪肝','确诊时间':'2024-01-02','确诊来源':'历史医疗记录'}],
            '当前用药 / 营养补充':[{'名称':'既往药物记录（合成验收）','剂量':'5','单位':'mg','频次':'每日一次'}],
            '手术 / 住院史':[{'名称':'既往手术记录（合成验收）','日期':'2020-01-02','类型':'手术'}]}}
        upload('历史健康档案','合成验收历史档案.json',json.dumps(history,ensure_ascii=False).encode())
        assert '存在冲突' in page.locator('body').inner_text();shot('05-conflict-review.png')
        button('确认并更新健康档案')
        expect(page.get_by_text('本次健康资料已整理完成',exact=True)).to_be_visible(timeout=30000)
        shot('13-history-completed.png');button('← 返回健康档案');settle()
        shot('07-health-record-updated.png')
        page.get_by_role('heading',name='资料导入记录',exact=True).scroll_into_view_if_needed()
        shot('10-import-history.png')
        # Open health measurements through the existing archive summary table.
        # Further member/health navigation is recorded separately after inspection.
        print('REPORT + QUESTIONNAIRE + HISTORY browser uploads and approvals PASS',flush=True)
        print(page.locator('body').inner_text()[-2500:],flush=True)
    except Exception:
        page.screenshot(path='.runtime/profile-browser-failure.png',full_page=True)
        print(page.locator('body').inner_text(),flush=True)
        raise
    finally:browser.close()
