"""Optional local-only LLM capabilities.

Importing this package never contacts or loads a model.
"""
"""Optional, local-only language model helpers."""

from executive_health_ai.llm.qwen_client import LocalQwenClient, LocalQwenHealth, LocalQwenSettings, LocalQwenUnavailable

__all__ = ["LocalQwenClient", "LocalQwenHealth", "LocalQwenSettings", "LocalQwenUnavailable"]
