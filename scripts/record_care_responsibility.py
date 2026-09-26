"""Evaluate existing V1 instances once at upgrade time; never backdate history.

Uses the configured database and the same router as live business commands.
No workflow, risk, baseline, report, or clinical facts are invented or changed.
"""
from sqlalchemy import select
from executive_health_ai.database import SessionLocal
from executive_health_ai.models import AgentGoal
from executive_health_ai.agent.post_checkup import is_care_goal
from executive_health_ai.agent.care_routing import latest, route


def record_existing(session):
    count=0
    for goal in session.scalars(select(AgentGoal)):
        if is_care_goal(goal) and latest(session,goal) is None:
            route(session,goal)
            count+=1
    return count


if __name__=='__main__':
    with SessionLocal() as session:
        count=record_existing(session)
        session.commit()
    print(f'Recorded current responsibility for {count} existing care workflows.')
