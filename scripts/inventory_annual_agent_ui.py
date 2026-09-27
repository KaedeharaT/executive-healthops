"""Inventory retained business controls against the immutable pre-task backup."""
import ast
from collections import Counter
import hashlib
import json
from pathlib import Path
import subprocess

ROOT=Path(__file__).resolve().parents[1]
OUT=ROOT/'docs/annual-agent-ai';OUT.mkdir(parents=True,exist_ok=True)
REF='backup/pre-annual-agent-ai-visibility'
QUIET={'creationflags':getattr(subprocess,'CREATE_NO_WINDOW',0)}
names=subprocess.check_output(['git','ls-tree','-r','--name-only',REF],cwd=ROOT,text=True,**QUIET).splitlines()
widgets={'button','download_button','link_button','form_submit_button','radio','selectbox','multiselect',
         'text_input','text_area','number_input','date_input','time_input','checkbox','file_uploader',
         'dataframe','data_editor','data_table','altair_chart','vega_lite_chart','stepper','timeline'}

def inventory(before):
    paths=[n for n in names if n=='streamlit_app.py' or n.startswith('src/executive_health_ai/ui/') and n.endswith('.py')]
    if not before:
        paths=sorted(set(paths)|{p.relative_to(ROOT).as_posix() for p in (ROOT/'src/executive_health_ai/ui').rglob('*.py')})
    records=[]
    for name in paths:
        content=subprocess.check_output(['git','show',REF+':'+name],cwd=ROOT,**QUIET).decode('utf-8-sig') if before else (ROOT/name).read_text(encoding='utf-8-sig')
        for node in ast.walk(ast.parse(content)):
            if not isinstance(node,ast.Call):continue
            kind=node.func.attr if isinstance(node.func,ast.Attribute) else node.func.id if isinstance(node.func,ast.Name) else ''
            if kind not in widgets:continue
            keyword={kw.arg:kw.value for kw in node.keywords}
            value=node.args[0] if node.args else keyword.get('label')
            label=value.value if isinstance(value,ast.Constant) and isinstance(value.value,str) else ''
            key=keyword.get('key')
            key=key.value if isinstance(key,ast.Constant) and isinstance(key.value,str) else ''
            records.append({'file':name,'line':node.lineno,'kind':kind,'label':label,'key':key})
    return records

before,after=inventory(True),inventory(False)
# Labels and stable keys preserve identity while containers and files may move.
identity=lambda r:json.dumps([r['kind'],r['label'],r['key']],ensure_ascii=False)
missing=list((Counter(map(identity,before))-Counter(map(identity,after))).elements())
protected=[n for n in names if n.startswith(('alembic/','src/executive_health_ai/models/')) or
    n in {'src/executive_health_ai/agent/care_routing.py','src/executive_health_ai/agent/tools.py','src/executive_health_ai/agent/supervisor.py',
          'src/executive_health_ai/services/responsibility.py','src/executive_health_ai/services/risk_triage.py','src/executive_health_ai/services/risk_operations.py'}]
changed=[]
for name in protected:
    old=subprocess.check_output(['git','show',REF+':'+name],cwd=ROOT,**QUIET).replace(b'\r\n',b'\n')
    new=(ROOT/name).read_bytes().replace(b'\r\n',b'\n')
    if hashlib.sha256(old).digest()!=hashlib.sha256(new).digest():changed.append(name)
result={'reference':REF,'before_controls':len(before),'after_controls':len(after),'missing_control_identities':missing,
        'protected_files':len(protected),'changed_safety_files':changed,
        'relocations':{'annual-members':'workflow.py annual() -> annual.py render(); columns retained or explicitly renamed'},
        'scope':'Static control identities plus browser journeys; presentation text and layout may change.'}
for name,data in [('inventory-before',before),('inventory-after',after),('preservation',result)]:
    (OUT/(name+'.json')).write_text(json.dumps(data,ensure_ascii=False,indent=2),encoding='utf-8')
print(json.dumps(result,ensure_ascii=True,indent=2))
assert not missing and not changed
