"""Safely add the original Portfolio Training SOP foundation to the active DB."""

from executive_health_ai.database import SessionLocal
from executive_health_ai.services.training_knowledge import seed_training_knowledge


def main() -> None:
    with SessionLocal() as session:
        counts = seed_training_knowledge(session)
        session.commit()
    print("Training knowledge foundation ready:")
    for key, value in counts.items():
        print(f"  {key}: {value}")


if __name__ == "__main__":
    main()
