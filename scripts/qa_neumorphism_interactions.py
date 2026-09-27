"""Keyboard, chart and synthetic import stories for the final presentation layer."""
import json
import sys
from pathlib import Path
from playwright.sync_api import sync_playwright, expect

sys.stdout.reconfigure(encoding='utf-8')
OUT=Path('docs/images/neumorphism-v1/interactions');OUT.mkdir(parents=True,exist_ok=True)
with sync_playwright() as p:
    browser=p.chromium.launch(headless=True)
    page=browser.new_page(viewport={'width':1440,'height':1000})
    errors=[];checks={}
    page.on('pageerror',lambda e:errors.append(str(e)))
    def settle():
        page.wait_for_timeout(500)
        page.locator('[data-testid="stStatusWidget"]').wait_for(state='hidden',timeout=90000)
        page.wait_for_timeout(400)
        assert not page.locator('[data-testid="stException"]').count(),page.locator('body').inner_text()
        assert not errors,errors
    def button(name):page.get_by_role('button',name=name,exact=True).last.click();settle()
    def radio(name):page.get_by_role('radio',name=name,exact=True).last.locator('xpath=ancestor::label').click();settle()
    def choose(label,value):
        field=page.get_by_label(label,exact=True);field.click();field.fill(value)
        page.get_by_role('option',name=value,exact=True).click();settle()
    def shot(name,selector):
        target=page.locator(selector)
        height=int(target.bounding_box()['height'])+180
        page.set_viewport_size({'width':1440,'height':max(1000,height)});settle()
        target.screenshot(path=str(OUT/f'{name}.png'))
        page.set_viewport_size({'width':1440,'height':1000});settle()
    try:
        page.goto('http://127.0.0.1:18530',wait_until='networkidle');settle()
        button('进入成员健康中心');radio('健康')
        chart=page.locator('[data-testid="stVegaLiteChart"]').first
        assert all(word in chart.inner_text() for word in ['时间','kg','年度基线','当前'])
        chart.locator('svg .mark-symbol.role-mark path').last.hover()
        expect(page.locator('#vg-tooltip-element')).to_be_visible()
        checks['baseline_current_axes_tooltip']=True
        radio('健康数据');choose('选择健康指标','血压（收缩压 / 舒张压）')
        page.locator('.st-key-health-trend-filters').get_by_text('全部',exact=True).click();settle()
        assert all(word in chart.inner_text() for word in ['时间','mmHg','收缩压','舒张压'])
        checks['blood_pressure_two_series_units']=True
        shot('blood-pressure-trend','.st-key-health-trend-panel')
        choose('选择健康指标','血糖')
        page.locator('.st-key-health-trend-filters').get_by_text('7天',exact=True).click();settle()
        assert '所选范围无记录' in page.locator('.st-key-health-trend-summary').inner_text()
        button('查看全部时间')
        assert chart.count()==1
        checks['empty_window_recovery']=True
        field=page.get_by_label('选择健康指标',exact=True)
        field.focus();page.keyboard.press('ArrowDown');page.keyboard.press('Escape')
        assert field.evaluate("e=>getComputedStyle(e).outlineWidth")=='3px'
        shot('keyboard-focus','.st-key-health-trend-filters')
        checks['keyboard_select_focus']=True

        # Imports run on a second isolated database, leaving paired screenshots reproducible.
        page.goto('http://127.0.0.1:18532',wait_until='networkidle');settle()
        button('进入 HealthOps 运营后台');radio('会员')
        query=page.get_by_label('搜索成员',exact=True);query.fill('Demo Executive A');query.press('Enter');settle()
        page.locator('[data-testid="stDataFrame"]').last.click(position={'x':100,'y':55});settle()
        radio('健康档案');button('＋ 导入健康资料');radio('健康问卷')
        questionnaire={'source_date':'2026-09-27','responses':{'生活方式':{'烟草':'偶尔吸烟','睡眠':'每天七小时'},
            '过敏史':[{'名称':'花粉','来源':'会员自述'}],'会员重点关注':{'concern':'改善睡眠'}}}
        page.locator('input[type=file]').set_input_files({'name':'新拟态视觉验收问卷（合成）.json','mimeType':'application/json',
            'buffer':json.dumps(questionnaire,ensure_ascii=False).encode('utf-8')})
        settle();button('上传并整理资料')
        expect(page.get_by_role('button',name='确认并更新健康档案',exact=True)).to_be_visible(timeout=90000)
        settle()
        assert page.locator('.neu-profile-legend').count()==1
        assert page.locator('[data-testid="stDataFrame"]').count()>=1
        checks['profile_preview_editor_confirmation_preserved']=True
        checks['profile_contrast']=page.evaluate(Path('scripts/neumorphism_contrast.js').read_text(encoding='utf-8'))
        shot('profile-confirmation','[data-testid="stMainBlockContainer"]')
        # Deliberately leave the synthetic candidate in preview, without confirming a medical fact.
        (OUT/'results.json').write_text(json.dumps({'checks':checks,'errors':errors},ensure_ascii=False,indent=2),encoding='utf-8')
        print(json.dumps(checks,ensure_ascii=False),flush=True)
    except Exception:
        page.screenshot(path=str(OUT/'failure.png'))
        (OUT/'failure.txt').write_text(page.locator('body').inner_text(),encoding='utf-8')
        raise
    finally:browser.close()
