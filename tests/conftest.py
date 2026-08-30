"""Keep automated tests independent from local models and local health data."""

import os
from pathlib import Path


# The application loader respects explicit process variables, so this prevents a
# local `.env` from causing network/model inference during ordinary unit tests.
os.environ["LOCAL_LLM_ENABLED"] = "false"

# A public checkout must never accidentally use a developer's SQLite file (or
# require a pre-existing database) merely to render a Streamlit smoke test.
# The test database is disposable, isolated under an ignored runtime folder,
# and its schema is built from the current model metadata before tests import
# application modules.
ROOT = Path(__file__).resolve().parents[1]
RUNTIME = ROOT / ".runtime"
RUNTIME.mkdir(exist_ok=True)
os.environ["DATABASE_URL"] = f"sqlite:///{(RUNTIME / 'pytest_app.db').as_posix()}"

from executive_health_ai.database import engine  # noqa: E402
from executive_health_ai.models import Base  # noqa: E402
from scripts.seed_full_demo import seed_full_demo  # noqa: E402

Base.metadata.create_all(engine)
# Streamlit interaction tests exercise the normal product entry point.  Give
# that isolated database one idempotent synthetic member story rather than
# silently relying on a developer's pre-seeded local database.
seed_full_demo()
