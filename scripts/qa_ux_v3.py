"""Read-only Chromium QA against an already-running synthetic Portfolio Demo.

Usage: python scripts/qa_product_logic.py --url http://localhost:18509
Requires Playwright + Chromium. Does not start servers, seed data or submit forms.
Screenshots are real viewport captures; human review is still required.
"""
import argparse,json
parser=argparse.ArgumentParser()
parser.add_argument('--url',default='http://localhost:18509')
args=parser.parse_args()
from pathlib import Path
from playwright.sync_api import sync_playwright
stage='after'
import sys
sys.stdout.reconfigure(encoding='utf-8')
root=Path('docs/images/ux-v3'); root.mkdir(parents=True,exist_ok=True)
results={}
with sync_playwright() as p:
 browser=p.chromium.launch(headless=True)
 page=browser.new_page(viewport={'width':1500,'height':1100},device_scale_factor=1)
 errors=[]
 page.on('pageerror',lambda error:errors.append(str(error)))
 def settle():
  page.wait_for_timeout(700)
  page.locator('[data-testid="stStatusWidget"]').wait_for(state='hidden',timeout=60000)
  page.wait_for_timeout(600)
  assert not page.locator('[data-testid="stException"]').count(),page.locator('body').inner_text()
  if stage=='after':
   assert not errors,errors
   assert not page.get_by_text('TypeError:',exact=False).count()
 def radio(name,first=False):
  role_change=name in {'健康管理师','医生','管理员','成员'} and first and stage=='after'
  if role_change:
   page.get_by_role('button',name='切换演示角色').click();page.wait_for_timeout(250)
   target=page.get_by_role('radio',name=name,exact=True).last
  else:
   r=page.get_by_role('radio',name=name,exact=True)
   target=r.first if first else r.last
  target.locator('xpath=ancestor::label').click();settle()
  if role_change:
   page.get_by_text('当前：'+name+' · 演示预览',exact=True).wait_for(timeout=30000)
   page.keyboard.press('Escape');page.wait_for_timeout(200)
 def capture(name):
  page.locator('[data-testid="stMain"]').evaluate('(el)=>el.scrollTop=0')
  page.evaluate('() => document.fonts.ready');page.wait_for_timeout(400)
  page.screenshot(path=str(root/f'{name}.png'),full_page=True)
  text=page.locator('body').inner_text()
  import re
  if not name.startswith('admin'):
   assert not re.search(r'RiskEvent|AgentGoal|PlanStep|canonical_code|provider_code|[0-9a-f]{8}-(?:[0-9a-f]{4}-){3}[0-9a-f]{12}',text),name
  Path(f'.runtime/ux-{stage}-{name}.txt').write_text(text,encoding='utf8')
  results[name]={'charts':len([x for x in page.locator('[data-testid="stVegaLiteChart"] svg').all() if x.is_visible()]),'exceptions':0}
  if stage=='after' and name in {'member-home','member-health','member-health-data','member-360-overview','member-360-health','doctor-detail'}:
   assert results[name]['charts']>0,name
  print(name,results[name],flush=True)
 page.goto(args.url,wait_until='networkidle');settle()
 page.get_by_role('button',name='进入成员健康中心',exact=True).click();settle();capture('member-home')
 radio('健康');capture('member-health')
 radio('健康数据');capture('member-health-data')
 radio('体检与检查');capture('member-checkups')
 radio('计划');capture('member-plan')
 radio('服务');capture('member-service')
 radio('历程');capture('member-timeline')
 radio('健康管理师',True);capture('manager-today')
 radio('成员')
 page.get_by_role('button',name='查看成员',exact=True).first.click();settle();capture('member-360-overview')
 page.get_by_role('button',name='查看趋势',exact=True).first.click();settle()
 assert page.get_by_text('选择健康指标',exact=True).count()
 capture('member-360-data')
 page.get_by_role('button',name='健康资料与其他视图',exact=True).click();page.wait_for_timeout(300)
 radio('健康概览');page.keyboard.press('Escape');capture('member-360-health')
 page.locator('[data-testid="stVegaLiteChart"]').first.scroll_into_view_if_needed();page.wait_for_timeout(300)
 page.screenshot(path=str(root/'member-360-health-chart.png'))
 radio('管理');capture('member-360-management')
 radio('医疗');capture('member-360-medical')
 radio('医疗协同');capture('manager-medical')
 radio('服务',True);capture('manager-service')
 radio('更多');capture('manager-more')
 page.get_by_role('button',name='打开',exact=True).nth(2).click();settle()
 assert page.get_by_role('radio',name='规则与知识',exact=True).is_checked()
 radio('医生',True);capture('doctor-queue')
 page.locator('[data-testid="stVegaLiteChart"]').first.scroll_into_view_if_needed();page.wait_for_timeout(300)
 page.screenshot(path=str(root/'doctor-detail.png'),full_page=True)
 page.get_by_role('button',name='提交判断并交回健管',exact=True).scroll_into_view_if_needed();page.screenshot(path=str(root/'doctor-decision.png'))
 results['doctor-detail']={'charts':page.locator('[data-testid="stVegaLiteChart"] svg').count(),'exceptions':0}
 radio('管理员',True);radio('系统状态');capture('admin-system')
 radio('集成与数据');capture('admin-integrations')
 page.get_by_role('button',name='检查',exact=True).nth(1).click();settle();capture('admin-ai-config')
 radio('自动化运营');capture('admin-automation')
 radio('规则与知识');capture('admin-rules')
 radio('专业知识');settle();capture('admin-knowledge')
 radio('系统状态');capture('admin-system')
 radio('成员',True);radio('首页');capture('member-home')
 page.get_by_role('button',name='去完成').first.click();settle()
 assert page.get_by_role('button',name='确认完成',exact=True).count()
 radio('健康')
 radio('健康概览')
 point=page.locator('[data-testid="stVegaLiteChart"] svg .mark-symbol.role-mark path').last
 point.hover();page.wait_for_timeout(600)
 tooltip=page.locator('#vg-tooltip-element')
 assert tooltip.is_visible() and 'kg' in tooltip.inner_text()
 results['tooltip']={'visible':True,'text':tooltip.inner_text()}
 page.mouse.move(5,5)
 page.get_by_text('所有指标 · 基线与当前对比',exact=True).click();settle()
 assert page.locator('[data-testid="stDataFrame"]').count()
 page.get_by_text('所有指标 · 基线与当前对比',exact=True).click()
 radio('历程');page.get_by_text('查看完整历程与依据',exact=True).click();settle()
 assert '健康历程暂时无法加载' not in page.locator('body').inner_text()
 radio('首页')
 # Keyboard reaches the same native actions; focus is visibly styled.
 action=page.get_by_role('button',name='去完成').first
 action.focus();page.keyboard.press('Tab')
 results['keyboard']={'activeTag':page.evaluate('document.activeElement.tagName'),'outline':page.evaluate('getComputedStyle(document.activeElement).outlineWidth')}
 page.set_viewport_size({'width':640,'height':1100});page.wait_for_timeout(700)
 collapse=page.locator('[data-testid="stSidebarCollapseButton"] button')
 if collapse.count() and collapse.is_visible(): collapse.click();page.wait_for_timeout(300)
 capture('member-home-narrow')
 # Reveal business navigation only long enough to choose the next page.
 def narrow_nav(name):
  sidebar=page.locator('[data-testid="stSidebar"]')
  if page.locator('[data-testid="stExpandSidebarButton"]').is_visible():
   page.locator('[data-testid="stExpandSidebarButton"]').click();page.wait_for_timeout(300)
  sidebar.get_by_role('radio',name=name,exact=True).locator('xpath=ancestor::label').click();settle()
  collapse=page.locator('[data-testid="stSidebarCollapseButton"] button')
  if collapse.count() and collapse.is_visible(): collapse.click();page.wait_for_timeout(300)
 narrow_nav('健康');capture('member-health-narrow')
 chart=page.locator('[data-testid="stVegaLiteChart"]')
 chart.scroll_into_view_if_needed();page.screenshot(path=str(root/'member-health-narrow-chart.png'))
 results['narrow'] = page.locator('[data-testid="stMain"]').evaluate('(e)=>({width:e.clientWidth,scrollWidth:e.scrollWidth})')
 assert results['narrow']['scrollWidth'] <= results['narrow']['width']+1
 radio('健康数据');capture('member-health-data-narrow')
 chart=page.locator('[data-testid="stVegaLiteChart"]');chart.scroll_into_view_if_needed()
 page.screenshot(path=str(root/'member-health-data-narrow-chart.png'))
 (root/'member-360.png').write_bytes((root/'member-360-overview.png').read_bytes())
 (root/'doctor-review.png').write_bytes((root/'doctor-detail.png').read_bytes())
 Path('.runtime/ux-v3-browser.json').write_text(json.dumps(results,ensure_ascii=False,indent=2),encoding='utf8')
 browser.close()
