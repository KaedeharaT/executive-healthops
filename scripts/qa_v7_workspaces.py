"""Visible Chromium inventory on isolated V7 synthetic databases."""
import json,sys,re
from pathlib import Path
from playwright.sync_api import sync_playwright,expect

sys.stdout.reconfigure(encoding='utf-8')
MODE='before' if '--before' in sys.argv else 'after'
ROOT=Path(__file__).resolve().parents[1];OUT=ROOT/'docs/images/v7-redesign'/MODE
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
  controls=page.evaluate('''() => [...document.querySelectorAll('button,input:not([type=hidden]),[role=combobox],a[href],summary,[data-testid=stDataFrame]')].filter(e=>e.checkVisibility({checkOpacity:true,checkVisibilityCSS:true}) && e.getBoundingClientRect().width>0 && e.getBoundingClientRect().height>0 && e.getAttribute('aria-label')!=='Link to heading').map(e=>({type:e.getAttribute('role')||e.type||e.tagName,label:e.getAttribute('aria-label')||e.innerText||e.getAttribute('placeholder')||'',primary:['primary','primaryFormSubmit'].includes(e.getAttribute('kind')),disabled:e.disabled||false}))''')
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
  page.goto('http://127.0.0.1:'+('18594' if MODE=='before' else '18591'),wait_until='networkidle');settle()
  if page.get_by_role('button',name='进入 HealthOps 运营后台',exact=True).count():button('进入 HealthOps 运营后台')
  shot('01-today');radio('会员');shot('02-members');member();shot('03-member360-overview')
  radio('健康档案');shot('05-health-record-agent-completed')
  radio('管理');shot('07-management')
  review=page.get_by_role('button',name=re.compile('^(开始阶段复盘|进行阶段复盘)$'))
  if review.count():review.click();settle();shot('08-stage-review')
  for n,label in [('09-annual','年度管理'),('10-service-management','服务管理'),('11-medical-collaboration','医疗协同'),('12-special-programs','专项管理')]:radio(label);shot(n)
  role('医生');shot('13-doctor');role('成员');shot('14-member');role('管理员');shot('15-admin')
  role('健康管理师');member('V6入口验证会员');radio('健康档案');shot('06-intake-exceptions')
  b.close()
 except Exception:
  shot('failure');raise
