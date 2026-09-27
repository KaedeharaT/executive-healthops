"""Compare captured UI controls and collect the visual acceptance evidence."""
import json
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
IMAGES = ROOT / 'docs/images/neumorphism-v1'
OUT = ROOT / 'docs/neumorphism-v1/browser-preservation.json'


def read(phase):
    return json.loads((IMAGES / phase / 'browser-results.json').read_text(encoding='utf-8'))


before, after = read('before'), read('after')
old = {p['page']: p for p in before['pages'] if 'page' in p}
new = {p['page']: p for p in after['pages'] if 'page' in p}
comparisons = []
for name, page in old.items():
    updated = new[name]
    controls = lambda p: Counter(json.dumps(c, sort_keys=True) for c in p['controls'])
    comparisons.append({
        'page': name,
        'missing_controls': list((controls(page) - controls(updated)).elements()),
        'tables_before': page['tables'], 'tables_after': updated['tables'],
        'charts_before': page['charts'], 'charts_after': updated['charts'],
        'contrast': updated['contrast'],
    })
result = {
    'browser': after['browser'], 'compared_pages_or_sections': len(comparisons),
    'viewport_sizes': ['1440x900', '1366x768', '1920x1080', '390x844'],
    'screenshots': len(list(IMAGES.rglob('*.png'))),
    'before_after_pairs': len(set(p.name for p in (IMAGES/'before').glob('*.png')) & set(p.name for p in (IMAGES/'after').glob('*.png'))),
    'page_errors': before['errors'] + after['errors'],
    'pages': comparisons,
    'keyboard_and_motion': after['pages'][-1],
}
OUT.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding='utf-8')
print(json.dumps({k: v for k, v in result.items() if k != 'pages'}, ensure_ascii=False))
for p in comparisons:
    assert not p['missing_controls'], p
    assert p['tables_after'] >= p['tables_before'], p
    assert p['charts_after'] >= p['charts_before'], p
    assert not p['contrast']['findings'], p
assert not result['page_errors']
