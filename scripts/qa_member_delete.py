"""Chromium archive acceptance. Requires an isolated prepared synthetic QA database."""
import json
from pathlib import Path
from playwright.sync_api import sync_playwright, expect

OUT=Path('docs/images/member-delete-fix');OUT.mkdir(parents=True,exist_ok=True)
with sync_playwright() as p:
    browser=p.chromium.launch(headless=True)
    page=browser.new_page(viewport={'width':1440,'height':900})
    page.set_default_timeout(25000)
    errors=[];page.on('pageerror',lambda e:errors.append(str(e)))
    page.add_init_script('''window.filterSamples=[];new MutationObserver(()=>{
      const n=document.querySelectorAll('.st-key-soft-filter-member-list').length;
      if(n>0) window.filterSamples.push({count:n,phase:window.action,stale:document.querySelectorAll('[data-stale="true"] .st-key-soft-filter-member-list').length});
    }).observe(document,{subtree:true,childList:true});''')
    def settle():
        page.wait_for_timeout(900)
        page.locator('[data-testid="stStatusWidget"]').wait_for(state='hidden',timeout=60000)
        assert not page.locator('[data-testid="stException"]').count(),page.locator('body').inner_text()
        assert not errors,errors
    def button(name):
        page.evaluate('(name)=>window.action=name',name)
        page.get_by_role('button',name=name,exact=True).click();settle()
    def radio(name):page.get_by_role('radio',name=name,exact=True).locator('xpath=ancestor::label').click();settle()
    def search(value):
        field=page.get_by_label('搜索成员',exact=True);field.fill(value);field.press('Enter');settle()
    def shot(name):page.screenshot(path=str(OUT/name))
    try:
        page.goto('http://127.0.0.1:18550',wait_until='networkidle');settle()
        if page.get_by_role('button',name='进入 HealthOps 运营后台',exact=True).count():button('进入 HealthOps 运营后台')
        radio('会员')
        for label in ['搜索成员','状态','负责人']:expect(page.get_by_label(label,exact=True)).to_have_count(1)
        shot('01-member-filter-fixed.png')
        search('Demo Archive QA')
        page.locator('[data-testid="stDataFrame"]').last.click(position={'x':100,'y':55});settle()
        expect(page.get_by_role('button',name='删除成员',exact=True)).to_be_visible()
        shot('02-member-delete-action.png')
        button('删除成员')
        expect(page.get_by_role('dialog')).to_be_visible()
        expect(page.get_by_role('button',name='确认删除',exact=True)).to_be_disabled()
        field=page.get_by_label('请输入成员姓名进行确认',exact=True)
        field.fill('wrong');field.press('Enter');settle()
        expect(page.get_by_role('button',name='确认删除',exact=True)).to_be_disabled()
        button('取消');expect(page.get_by_role('dialog')).to_have_count(0)
        button('删除成员');field.fill('Demo Archive QA');field.press('Enter');settle()
        expect(page.get_by_role('button',name='确认删除',exact=True)).to_be_enabled()
        shot('03-member-delete-confirm.png')
        button('确认删除')
        expect(page.get_by_role('dialog')).to_have_count(0)
        expect(page.get_by_role('button',name='删除成员',exact=True)).to_have_count(0)
        assert '成员已删除/归档' in page.locator('body').inner_text()
        shot('04-member-after-delete.png')
        search('');radio('年度管理');radio('会员')
        for label in ['搜索成员','状态','负责人']:expect(page.get_by_label(label,exact=True)).to_have_count(1)
        page.get_by_text('切换演示角色',exact=True).click();radio('管理员');page.keyboard.press('Escape');settle()
        page.locator('[data-testid="stExpander"] summary').filter(has_text='操作记录').click();settle()
        page.get_by_label('显示已归档成员',exact=True).locator('xpath=ancestor::label').click();settle()
        selector=page.get_by_label('选择成员',exact=True)
        if selector.input_value()!='Demo Archive QA':
            selector.click();selector.press('ArrowDown')
            page.get_by_role('option',name='Demo Archive QA',exact=False).click();settle()
        assert '该成员已归档' in page.locator('body').inner_text()
        page.get_by_label('历史记录表（只读）',exact=True).scroll_into_view_if_needed()
        shot('05-admin-archived-history.png')
        samples=page.evaluate('window.filterSamples')
        assert max(x['count'] for x in samples)==1, 'Duplicate filter containers during rendering'
        (OUT/'filter-render-samples.json').write_text(json.dumps(samples,ensure_ascii=False,indent=2),encoding='utf-8')
        (OUT/'browser-results.json').write_text(json.dumps({'browser':browser.version,'viewport':'1440x900',
            'filter_count':1,'max_filter_containers_during_render':max(x['count'] for x in samples),
            'cancel':True,'wrong_name_blocked':True,'confirmed_archive':True,'admin_history':True,'errors':errors},indent=2),encoding='utf-8')
        print('Chromium acceptance passed',flush=True)
    except Exception:
        shot('failure.png');(OUT/'failure.txt').write_text(page.locator('body').inner_text(),encoding='utf-8');raise
    finally:browser.close()
