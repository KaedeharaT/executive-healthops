"""Provider-neutral health data ingestion boundary."""

from executive_health_ai.integrations.adapters import PROVIDERS, get_adapter

__all__ = ["PROVIDERS", "get_adapter"]
