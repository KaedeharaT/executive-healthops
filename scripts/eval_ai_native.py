"""Run the bounded, deterministic AI Native regression set without a live model."""
import os,subprocess,sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
env={**os.environ,'LOCAL_LLM_ENABLED':'false'}
raise SystemExit(subprocess.call([sys.executable,'-m','pytest',
    'tests/test_ai_native_completion.py','tests/test_health_event_runtime.py',
    'tests/test_agent_supervisor_post_checkup_e2e.py','tests/test_management_action_loop.py','-q'],cwd=ROOT,env=env))
