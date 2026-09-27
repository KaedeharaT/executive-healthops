"""Run the unchanged suite in an isolated checkout so demo rebuild cannot hit live data."""
import os
from pathlib import Path
import shutil
import subprocess
import sys

ROOT=Path(__file__).resolve().parents[1]
target=ROOT/'.runtime/neumorphism-test-workspace'
target.mkdir(parents=True,exist_ok=True)
paths=subprocess.check_output(['git','ls-files'],cwd=ROOT,text=True).splitlines()
paths += ['src/executive_health_ai/ui/neumorphism.py']
for name in paths:
    src=ROOT/name
    if not src.is_file():continue
    dst=target/name
    dst.parent.mkdir(parents=True,exist_ok=True)
    shutil.copy2(src,dst)
env=os.environ.copy()
env.update(PYTHONUTF8='1',PYTHONIOENCODING='utf-8',PYTHONPATH=str(target/'src')+os.pathsep+str(target),LOCAL_LLM_ENABLED='false')
with (ROOT/'docs/neumorphism-v1/final-tests.txt').open('w',encoding='utf-8') as output:
    output.write('Isolated unchanged full test suite; prevents Windows locks on the running demo database.\n')
    output.flush()
    completed=subprocess.run([sys.executable,'-m','pytest','-q','--tb=short'],cwd=target,env=env,stdout=output,stderr=subprocess.STDOUT)
sys.exit(completed.returncode)
