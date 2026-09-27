"""Prepare immutable source snapshots and identical synthetic QA database copies."""
from pathlib import Path
import hashlib
import io
import json
import sqlite3
import subprocess
import tarfile

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / '.runtime/neumorphism-v2'
OUT.mkdir(parents=True, exist_ok=True)
source = ROOT / '.runtime/neumorphism_qa.db'
manifest = {}
for name, ref, port in [('original', 'backup/pre-neumorphism-redesign', 18501), ('previous', '3b78204', 18502), ('revised', None, 18503)]:
    target = OUT / name
    target.mkdir(exist_ok=True)
    if ref:
        archive = subprocess.check_output(['git', 'archive', ref], cwd=ROOT)
        with tarfile.open(fileobj=io.BytesIO(archive)) as files:
            for item in files.getmembers():
                assert (target / item.name).resolve().is_relative_to(target.resolve())
                assert not item.issym() and not item.islnk()
            files.extractall(target)
    db = target / 'qa.db'
    if not db.exists():
        with sqlite3.connect(source) as src, sqlite3.connect(db) as dst:
            src.backup(dst)
    manifest[name] = {'ref': ref or 'working tree', 'port': port, 'source': str(target if ref else ROOT),
                      'database': str(db), 'sha256': hashlib.sha256(db.read_bytes()).hexdigest()}
(OUT / 'manifest.json').write_text(json.dumps(manifest, indent=2), encoding='utf-8')
print(json.dumps(manifest, indent=2))
