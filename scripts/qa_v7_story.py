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
  page.locator('[data-testid="stDataFrame"]').first.click(position={'x':140,'y':55});settle()
  assert page.get_by_role('radio',name='管理',exact=True).is_checked()
  shot('01-today-direct-stage-review')
  page.get_by_role('checkbox',name='我已核对阶段结果，确认本次复盘',exact=True).locator('xpath=ancestor::label').click()
  button('确认并进入下一阶段')
  expect(page.get_by_role('textbox',name='处理结果',exact=True)).to_be_visible()
  page.get_by_role('textbox',name='处理结果',exact=True).fill('合成验收：已核对下一阶段安排与负责人。')
  button('完成本次处理');shot('02-next-phase-task-completed')
  page.get_by_text('新增安排',exact=True).click();settle()
  page.get_by_role('combobox',name='安排类型',exact=True).click();page.get_by_role('option',name='申请服务',exact=True).click();settle()
  button('继续')
  page.get_by_role('textbox',name='申请原因',exact=True).fill('V7合成验收：验证服务执行结果回写当前阶段。')
  button('提交服务申请');button('审核申请');button('确认服务安排');button('确认开始服务')
  page.get_by_role('textbox',name='服务结果',exact=True).fill('合成验收：已完成服务沟通，会员确认收到执行安排。')
  page.get_by_role('textbox',name='完成依据',exact=True).fill('合成服务人员与会员确认记录')
  button('记录服务完成');shot('03-service-result')
  button('继续处理下一项')
  result=page.get_by_role('textbox',name='随访情况 / 处理结果',exact=True)
  if not result.count():result=page.get_by_role('textbox',name='处理结果',exact=True)
  result.fill('合成验收：已确认服务结果，当前事项可关闭。');button('完成本次处理');shot('04-service-result-writeback')
  radio('年度管理');page.locator('[data-testid="stDataFrame"]').last.click(position={'x':140,'y':55});settle()
  assert page.get_by_role('radio',name='管理',exact=True).is_checked();shot('05-annual-member-management')
  radio('服务管理');page.get_by_label('搜索服务',exact=True).fill('V7合成验收');page.get_by_label('搜索服务',exact=True).press('Enter');settle()
  page.locator('[data-testid="stDataFrame"]').last.click(position={'x':140,'y':55});settle()
  assert page.get_by_role('button',name='← 返回服务管理',exact=True).is_visible();shot('06-service-formal-detail')
  b.close()
 except Exception:
  shot('failure');raise
