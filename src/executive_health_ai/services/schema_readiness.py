"""Read-only launcher check for the shared longitudinal fact schema.

Schema upgrades remain an explicit, backed-up maintenance operation. Missing
tables/columns are deployment errors, not members with an empty history.
"""
from pathlib import Path
from sqlalchemy import inspect
from sqlalchemy.engine import make_url
from executive_health_ai.database import create_database_engine, get_database_url
from executive_health_ai.models import Observation
from executive_health_ai.models.goal_data import (ManagementGoal, ReportCandidateRevision,
    DailyHealthSummary, DailySummaryRevision, SummaryWorkItem, CommunicationRecord)


def require_longitudinal_schema(database_url=None):
    url=database_url or get_database_url()
    parsed=make_url(url)
    if parsed.drivername.startswith('sqlite') and parsed.database not in {None, '', ':memory:'}:
        # Do not create an empty SQLite database as a side effect of validation.
        if not parsed.database.startswith('file:') and not Path(parsed.database).is_file():
            raise RuntimeError('HealthOps database does not exist; restore it before startup. No database was created.')
    engine=create_database_engine(url)
    try:
        inspector=inspect(engine);tables=set(inspector.get_table_names());missing=[]
        for model in (Observation, ManagementGoal, ReportCandidateRevision, DailyHealthSummary,
                      DailySummaryRevision, SummaryWorkItem, CommunicationRecord):
            table=model.__table__
            if table.name not in tables:
                missing.append(table.name);continue
            columns={c['name'] for c in inspector.get_columns(table.name)}
            missing.extend(f'{table.name}.{c.name}' for c in table.columns if c.name not in columns)
        if missing:
            raise RuntimeError('HealthOps database schema is out of date: '+', '.join(missing)+
                '. Back up the configured database, verify DATABASE_URL, then run '
                'python -m alembic upgrade head before restarting. Startup did not migrate or rebuild data.')
    finally:
        engine.dispose()
