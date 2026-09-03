"""Seed the owned synthetic HealthOps SOP and safety knowledge foundation."""

from executive_health_ai.database import SessionLocal
from executive_health_ai.services.healthops_internal_knowledge import seed_healthops_internal_knowledge


if __name__ == "__main__":
    with SessionLocal() as session:
        counts = seed_healthops_internal_knowledge(session)
        session.commit()
    print(counts)
