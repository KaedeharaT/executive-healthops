"""Compare UI calls and protected implementation against the pre-redesign commit."""
import ast
from collections import Counter
import hashlib
import json
import re
from pathlib import Path
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / 'docs/neumorphism-v1'
WIDGETS = {'button','download_button','link_button','form_submit_button','radio','tabs',
    'segmented_control','selectbox','multiselect','text_input','text_area','number_input',
    'date_input','time_input','slider','select_slider','checkbox','toggle','file_uploader',
    'dataframe','data_editor','table','altair_chart','vega_lite_chart','plotly_chart',
    'data_table','business_table','workflow','stage_stepper','stepper','timeline_event'}

def snapshot():
    calls = []
    paths = [ROOT/'streamlit_app.py', *sorted((ROOT/'src/executive_health_ai/ui').rglob('*.py'))]
    for path in paths:
        for node in ast.walk(ast.parse(path.read_text(encoding='utf-8-sig'))):
            if not isinstance(node, ast.Call): continue
            name = node.func.attr if isinstance(node.func, ast.Attribute) else node.func.id if isinstance(node.func, ast.Name) else ''
            if name in WIDGETS:
                calls.append({'file': path.relative_to(ROOT).as_posix(), 'kind': name,
                    'contract': ast.dump(node, include_attributes=False)})
    protected = {}
    for folder in ['services','agent','models','ui/charts']:
        for path in sorted((ROOT/'src/executive_health_ai'/folder).rglob('*.py')):
            protected[path.relative_to(ROOT).as_posix()] = hashlib.sha256(path.read_bytes()).hexdigest()
    for path in sorted((ROOT/'alembic').rglob('*.py')):
        protected[path.relative_to(ROOT).as_posix()] = hashlib.sha256(path.read_bytes()).hexdigest()
    return {'commit':subprocess.check_output(['git','rev-parse','HEAD'],cwd=ROOT,text=True).strip(),
        'ui_calls':calls,'protected_files':protected}


def content_literals(baseline=False):
    """Supplement call contracts with all original Chinese UI copy, excluding CSS."""
    names=subprocess.check_output(['git','ls-tree','-r','--name-only','backup/pre-neumorphism-redesign'],cwd=ROOT,text=True).splitlines()
    counts=Counter()
    for name in names:
        if name!='streamlit_app.py' and not (name.startswith('src/executive_health_ai/ui/') and name.endswith('.py')):continue
        if name.endswith('/styles.py'):continue
        source=subprocess.check_output(['git','show','backup/pre-neumorphism-redesign:'+name],cwd=ROOT).decode('utf-8-sig') if baseline else (ROOT/name).read_text(encoding='utf-8-sig')
        for node in ast.walk(ast.parse(source)):
            if isinstance(node,ast.Constant) and isinstance(node.value,str) and re.search('[\u4e00-\u9fff]',node.value) and '<style>' not in node.value:
                counts[(name,node.value)]+=1
    return counts

if __name__ == '__main__':
    OUT.mkdir(parents=True,exist_ok=True)
    mode = sys.argv[1]
    current = snapshot()
    target = OUT/f'ui-inventory-{mode}.json'
    target.write_text(json.dumps(current,ensure_ascii=False,indent=2),encoding='utf-8')
    if mode == 'after':
        before=json.loads((OUT/'ui-inventory-before.json').read_text(encoding='utf-8'))
        count=lambda data:Counter(json.dumps(v,sort_keys=True) for v in data['ui_calls'])
        missing=list((count(before)-count(current)).elements())
        changed=[p for p,h in before['protected_files'].items() if current['protected_files'].get(p)!=h]
        text_before,text_after=content_literals(True),content_literals()
        missing_copy=[{'file':p,'text':s} for p,s in (text_before-text_after).elements()]
        result={'before_calls':len(before['ui_calls']),'after_calls':len(current['ui_calls']),
            'deleted':len(missing),'missing':missing,'preserved_percent':100 if not missing else 100*(1-len(missing)/len(before['ui_calls'])),
            'protected_files':len(before['protected_files']),'protected_changes':changed,
            'original_ui_copy_literals':sum(text_before.values()),'missing_ui_copy':missing_copy}
        (OUT/'preservation-results.json').write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf-8')
        print(json.dumps(result,ensure_ascii=False))
        assert not missing and not changed and not missing_copy
    else: print(f"Inventoried {len(current['ui_calls'])} UI call sites and {len(current['protected_files'])} protected files")
