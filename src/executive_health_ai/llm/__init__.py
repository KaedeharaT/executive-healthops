"""Optional local-only LLM capabilities.

Importing this package never contacts or loads a model.
"""
"""Optional, local-only language model helpers."""

from executive_health_ai.llm.local_llm_client import LocalLLMClient, LocalLLMHealth, LocalLLMSettings, LocalLLMUnavailable

__all__ = ["LocalLLMClient", "LocalLLMHealth", "LocalLLMSettings", "LocalLLMUnavailable"]
