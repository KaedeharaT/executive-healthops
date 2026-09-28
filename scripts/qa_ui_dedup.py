"""Visible Chromium audit on an isolated synthetic platform; no internal URLs/state injection."""
import argparse,json,re
from pathlib import Path
from playwright.sync_api import sync_playwright,expect
ROOT=Path(__file__).resolve().parents[1]
parser=argparse.ArgumentParser();parser.add_argument('--phase',default='after');args=parser.parse_args()
OUT=ROOT/('docs/images/ui-dedup-audit' if args.phase=='after' else '.runtime/ui-dedup/before')
OUT.mkdir(parents=True,exist_ok=True)
records=[]
with sync_playwright() as p:
 browser=p.chromium.launch(headless=True);page=browser.new_page(viewport={'width':1440,'height':1050});page.set_default_timeout(30000)
 def settle():
  page.wait_for_timeout(900)
  expect(page.locator('[data-testid="stApp"]')).to_have_attribute('data-test-script-state','notRunning',timeout=90000)
  page.wait_for_function('!document.querySelector(\'[data-stale="true"]\')',timeout=30000)
  assert not page.locator('[data-testid="stException"]').count(),page.locator('body').inner_text()
 def button(name):page.get_by_role('button',name=name,exact=True).click();settle()
 def radio(name):page.get_by_role('radio',name=name,exact=True).locator('xpath=ancestor::label').click();settle()
 def choose(label,value):
  field=page.get_by_label(label,exact=True);field.click();field.fill(value)
  field.press('ArrowDown')
  page.get_by_role('option',name=value,exact=True).click();settle()
 def search(label,value):
  field=page.get_by_label(label,exact=True);field.fill(value);field.press('Enter');settle()
 def row(index=-1):
  before=page.locator('body').inner_text()
  page.locator('[data-testid="stDataFrame"]').nth(index).click(position={'x':100,'y':55});settle()
  if before==page.locator('body').inner_text():
   page.locator('[data-testid="stDataFrame"]').nth(index).click(position={'x':160,'y':55});settle()
 def top():page.locator('[data-testid="stMain"]').evaluate('(e)=>e.scrollTo(0,0)')
 def role(name):
  top();page.get_by_text('切换演示角色',exact=True).click();radio(name)
  page.get_by_text('切换演示角色',exact=True).click();settle()
 def shot(name):
  settle();top()
  primaries=page.locator('button[kind="primary"],button[kind="primaryFormSubmit"]').evaluate_all('els=>els.filter(e=>e.getClientRects().length && !e.disabled).map(e=>e.innerText)')
  assert len(primaries)<=1,(name,primaries)
  controls=page.locator('button,a,input,[role="radio"],[role="combobox"],[role="tab"],summary,[data-testid="stDataFrame"]').evaluate_all('els=>els.filter(e=>e.getClientRects().length).map(e=>({tag:e.tagName,role:e.getAttribute("role"),label:e.innerText||e.getAttribute("aria-label")||e.getAttribute("placeholder")||e.getAttribute("type"),testid:e.getAttribute("data-testid")}))')
  text=page.locator('body').inner_text();(OUT/(name+'.txt')).write_text(text,encoding='utf-8')
  if name=='06-management':page.get_by_text('下一件要做',exact=True).scroll_into_view_if_needed()
  page.screenshot(path=str(OUT/(name+'.png')))
  records.append({'page':name,'controls':controls,'primary_actions':primaries,'exceptions':0});print(name,flush=True)
 def directory(name='Demo Executive A'):
  radio('会员')
  back=page.get_by_role('button',name=re.compile('^← 返回(会员|年度管理|今日工作)$'))
  if back.count():
   back.click();settle();radio('会员')
  search('搜索成员',name);row()
  if page.get_by_role('button',name='查看会员 / 进入Member360',exact=True).count():button('查看会员 / 进入Member360')
 try:
  page.goto('http://127.0.0.1:18585',wait_until='networkidle');settle()
  button('进入 HealthOps 运营后台');shot('01-manager-today')
  if page.locator('[data-testid="stDataFrame"]').count():
   row();shot('11-today-detail');button('← 返回今日工作')
  radio('会员');search('搜索成员','Demo Executive A');shot('02-members');row()
  assert not page.get_by_role('button',name='查看会员 / 进入Member360',exact=True).count()
  if page.get_by_role('button',name='查看会员 / 进入Member360',exact=True).count():button('查看会员 / 进入Member360')
  shot('03-member360')
  expect(page.get_by_role('radio',name='概览',exact=True)).to_be_checked()
  trends=page.get_by_role('button',name='查看趋势',exact=True)
  if trends.count():
   trends.first.click();settle();shot('34-manager-health-data');button('← 返回健康档案摘要')
  radio('健康档案');shot('04-health-record')
  button('查看完整健康档案');shot('12-full-archive');button('← 返回健康档案主页')
  radio('管理');shot('06-management')
  for value,name in [('阶段评估','13-stage-review'),('检查复查','14-recheck')]:
   choose('管理工作',value);shot(name)
  radio('医疗');shot('15-medical');radio('历程');shot('16-manager-history')
  radio('年度管理');shot('07-annual');row();shot('17-annual-member-destination')
  expect(page.get_by_role('radio',name='管理',exact=True)).to_be_checked()
  radio('医疗协同');shot('18-medical-collaboration')
  radio('服务');shot('19-services')
  if page.locator('[data-testid="stDataFrame"]').count():row();shot('20-service-detail')
  directory('UI Audit Intake');radio('健康档案');shot('05-intake')
  expect(page.locator('[data-testid="stFileUploader"]')).to_have_count(1)
  assert '资料用途' not in page.locator('body').inner_text()
  assert not page.get_by_role('button',name='继续完成初始评估',exact=True).count()
  assert not page.get_by_role('button',name='查看运行看板',exact=True).count()
  q=page.get_by_role('button',name=re.compile('^处理剩余'))
  if q.count():q.click();settle();shot('21-intake-exception')
  card=page.get_by_role('button',name=re.compile('^家族史'))
  if card.count():card.click();settle();shot('22-intake-editor')
  role('医生');shot('08-doctor')
  if page.locator('[data-testid="stDataFrame"]').count():
   search('搜索记录','肝功能');row();shot('23-doctor-detail');button('← 返回待我判断')
  radio('历史');shot('24-doctor-history')
  role('成员');radio('首页');shot('09-member-home')
  for label,name in [('健康','25-member-health'),('计划','26-member-plan'),('服务','27-member-service'),('历程','28-member-history')]:radio(label);shot(name)
  role('管理员');radio('系统状态');shot('10-admin')
  radio('自动化运行');shot('29-admin-automation')
  if page.locator('[data-testid="stDataFrame"]').count():row();shot('30-agent-board');button('← 返回自动化运行')
  radio('数据与集成');shot('31-integrations')
  radio('规则与知识');shot('32-rules');radio('专业知识');shot('33-knowledge')
  (OUT/'browser-controls.json').write_text(json.dumps({'browser':browser.version,'phase':args.phase,'pages':records},ensure_ascii=False,indent=2),encoding='utf-8')
 except Exception:
  page.screenshot(path=str(OUT/'failure.png'));(OUT/'failure.txt').write_text(page.locator('body').inner_text(),encoding='utf-8')
  (OUT/'browser-controls.json').write_text(json.dumps({'browser':browser.version,'pages':records},ensure_ascii=False,indent=2),encoding='utf-8');raise
 finally:browser.close()
