"""Visible Chromium inventory on isolated V7 synthetic databases."""
import json,sys,re
from pathlib import Path
from playwright.sync_api import sync_playwright,expect

sys.stdout.reconfigure(encoding='utf-8')
MODE='before' if '--before' in sys.argv else 'after'
ROOT=Path(__file__).resolve().parents[1];OUT=ROOT/'docs/images/v7-redesign/story'
OUT.mkdir(parents=True,exist_ok=True)
inventory=[]
with sync_playwright() as p:
 b=p.chromium.launch(headless=True);page=b.new_page(viewport={'width':1440,'height':900})
 def settle():
  page.wait_for_timeout(700)
  expect(page.locator('[data-testid="stApp"]')).to_have_attribute('data-test-script-state','notRunning',timeout=90000)
  page.wait_for_function('!document.querySelector(\'[data-stale="true"]\')')
  assert not page.locator('[data-testid="stException"]').count(),page.locator('body').inner_text()
 def radio(n):page.get_by_role('radio',name=n,exact=True).locator('xpath=ancestor::label').click();settle()
 def button(n):page.get_by_role('button',name=n,exact=True).click();settle()
 def shot(n):
  page.locator('[data-testid="stMain"]').evaluate('(e)=>e.scrollTo(0,0)')
  page.screenshot(path=str(OUT/(n+'.png')))
  (OUT/(n+'.txt')).write_text(page.locator('body').inner_text(),encoding='utf-8')
  controls=page.evaluate('''() => [...document.querySelectorAll('button,input:not([type=hidden]),[role=combobox],a[href],summary,[data-testid=stDataFrame]')].filter(e=>e.getBoundingClientRect().width>0 && e.getBoundingClientRect().height>0 && getComputedStyle(e).visibility!=='hidden').map(e=>({type:e.getAttribute('role')||e.type||e.tagName,label:e.getAttribute('aria-label')||e.innerText||e.getAttribute('placeholder')||'',primary:e.getAttribute('kind')==='primary',disabled:e.disabled||false}))''')
  inventory.append({'page':n,'controls':controls,'count':len(controls),'primary':sum(c['primary'] for c in controls)})
  (OUT/'inventory.json').write_text(json.dumps(inventory,ensure_ascii=False,indent=2),encoding='utf-8');print(n,flush=True)
 def member(name='Demo Executive A'):
  radio('会员')
  back=page.get_by_role('button',name='← 返回会员',exact=True)
  if back.count():button('← 返回会员')
  page.get_by_label('搜索成员',exact=True).fill(name);page.get_by_label('搜索成员',exact=True).press('Enter');settle()
  for x in (160,100,15):
   page.locator('[data-testid="stDataFrame"]').last.click(position={'x':x,'y':55});settle()
   if page.get_by_role('radio',name='概览',exact=True).count():break
 def role(n):
  page.get_by_text('切换演示角色',exact=True).click();radio(n);page.get_by_text('切换演示角色',exact=True).click();settle()
 try:
  page.goto('http://127.0.0.1:18593',wait_until='networkidle');settle()
  if page.get_by_role('button',name='进入 HealthOps 运营后台',exact=True).count():button('进入 HealthOps 运营后台')
  page.get_by_label('查找待办',exact=True).fill('Demo Executive A');page.get_by_label('查找待办',exact=True).press('Enter');settle()
  for x in (140,80,15):
   page.locator('[data-testid="stDataFrame"]').first.click(position={'x':x,'y':55});settle()
   if page.get_by_role('radio',name='管理',exact=True).count():break
  assert page.get_by_role('radio',name='管理',exact=True).is_checked()
  button('← 返回今日工作')
  assert page.get_by_label('查找待办',exact=True).is_visible()
  assert not page.get_by_role('radio',name='概览',exact=True).count()
  shot('11-back-to-today-without-reopen')
  b.close()
 except Exception:
  shot('failure');raise
