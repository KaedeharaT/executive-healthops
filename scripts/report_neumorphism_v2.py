"""Verify matched captures and original controls; this does not judge aesthetics."""
from collections import Counter
from pathlib import Path
import hashlib
import json

ROOT=Path(__file__).resolve().parents[1]
IMAGES=ROOT/'docs/images/neumorphism-v2'
records={v:json.loads((IMAGES/v/'results.json').read_text(encoding='utf-8')) for v in ['original','previous','revised']}
pages={v:{p['page']:p for p in data['pages']} for v,data in records.items()}
assert set(pages['original'])==set(pages['previous'])==set(pages['revised'])
checks=[]
for name, old in pages['previous'].items():
    new=pages['revised'][name]
    original=pages['original'][name]
    assert original['viewport']==old['viewport']==new['viewport']==[1440,900]
    assert original['scroll']==old['scroll']==new['scroll'],name
    calls=lambda p:Counter(json.dumps(c,sort_keys=True) for c in p['controls'])
    missing=list((calls(old)-calls(new)).elements())
    assert not missing,(name,missing)
    assert old['tables']==new['tables'],name
    assert old['charts']==new['charts'],name
    assert not new['contrast']['findings'],(name,new['contrast'])
    checks.append({'page':name,'viewport':new['viewport'],'scroll':new['scroll'],'missing_controls':missing,
                   'tables_before_after':[old['tables'],new['tables']],'charts_before_after':[old['charts'],new['charts']],
                   'contrast':new['contrast']})
assert all(not r['errors'] for r in records.values())
manifest=json.loads((ROOT/'.runtime/neumorphism-v2/manifest.json').read_text(encoding='utf-8'))
data_checks={v:{'initial_sha256':x['sha256'],'current_sha256':hashlib.sha256(Path(x['database']).read_bytes()).hexdigest()} for v,x in manifest.items()}
assert len({x['current_sha256'] for x in data_checks.values()})==1,data_checks
result={'browser':records['revised']['browser'],'matched_views':len(checks),'database_copies':data_checks,
        'pages':checks,'errors':[],'note':'Pixel differences and this check do not make a visual acceptance decision.'}
(ROOT/'docs/neumorphism-v2/browser-evidence.json').write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf-8')
print(json.dumps({'matched_views':len(checks),'missing_controls':0,'errors':0,'identical_database_copies':True}))
