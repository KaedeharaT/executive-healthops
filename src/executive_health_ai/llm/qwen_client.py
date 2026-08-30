"""Small local Ollama Qwen client, based on the validated research client flow."""

from __future__ import annotations

import json
import logging
import os
import re
import time
from dataclasses import dataclass
from typing import Any
from urllib.parse import urlparse

import requests

logger = logging.getLogger(__name__)
_LOCAL_HOSTS = {"localhost", "127.0.0.1", "::1"}


@dataclass(frozen=True)
class LocalQwenSettings:
    enabled: bool
    provider: str
    base_url: str
    model: str
    timeout_seconds: int
    max_input_chars: int

    @classmethod
    def from_environment(cls) -> "LocalQwenSettings":
        return cls(
            enabled=os.getenv("LOCAL_LLM_ENABLED", "false").lower() == "true",
            provider=os.getenv("LOCAL_LLM_PROVIDER", "qwen").strip().lower(),
            base_url=os.getenv("OLLAMA_BASE_URL", "http://127.0.0.1:11434").rstrip("/"),
            model=os.getenv("LOCAL_LLM_MODEL", "qwen2.5:7b").strip(),
            # Keep the validated research-client default.  A local model may need
            # longer than a minute for a first (cold) inference, while the feature
            # remains opt-in and failures still fall back to human review.
            timeout_seconds=max(1, int(os.getenv("LOCAL_LLM_TIMEOUT_SECONDS", "600"))),
            max_input_chars=max(200, int(os.getenv("LOCAL_LLM_MAX_INPUT_CHARS", "3000"))),
        )

    def is_local_ollama(self) -> bool:
        parsed = urlparse(self.base_url)
        return self.provider == "qwen" and parsed.scheme == "http" and parsed.hostname in _LOCAL_HOSTS


class LocalQwenUnavailable(RuntimeError):
    """The optional local service is disabled or unavailable."""


@dataclass(frozen=True)
class LocalQwenHealth:
    enabled: bool
    available: bool
    provider: str
    model: str
    base_url: str
    reason: str | None = None


def sanitize_for_llm(text: str) -> str:
    """Remove common direct identifiers while preserving minimal clinical evidence."""
    cleaned = text
    labels = ("姓名", "患者姓名", "档案号", "体检号", "身份证", "证件号", "手机号", "电话", "地址", "邮箱", "公司", "单位")
    for label in labels:
        cleaned = re.sub(rf"(?im)^\s*{label}\s*[:：]\s*[^\n]+$", f"{label}：[已移除]", cleaned)
    cleaned = re.sub(r"\b1[3-9]\d{9}\b", "[已移除手机号]", cleaned)
    cleaned = re.sub(r"\b\d{17}[0-9Xx]\b", "[已移除证件号]", cleaned)
    cleaned = re.sub(r"[\w.+-]+@[\w.-]+\.[A-Za-z]{2,}", "[已移除邮箱]", cleaned)
    return cleaned


def parse_json_object(text: str) -> dict[str, Any]:
    """Parse strict JSON with a limited code-fence recovery; never evaluate text."""
    candidate = text.strip()
    if candidate.startswith("```"):
        candidate = re.sub(r"^```(?:json)?\s*|\s*```$", "", candidate, flags=re.IGNORECASE)
    start, end = candidate.find("{"), candidate.rfind("}")
    if start < 0 or end < start:
        raise ValueError("本地模型没有返回 JSON 对象")
    parsed = json.loads(candidate[start:end + 1])
    if not isinstance(parsed, dict):
        raise ValueError("本地模型返回的 JSON 不是对象")
    return parsed


class LocalQwenClient:
    """Local-only Ollama chat client. It never includes an API key in requests."""

    def __init__(self, settings: LocalQwenSettings | None = None, http_post=requests.post, http_get=requests.get) -> None:
        self.settings = settings or LocalQwenSettings.from_environment()
        self._http_post = http_post
        self._http_get = http_get

    def available(self) -> bool:
        return self.health_check().available

    def health_check(self) -> LocalQwenHealth:
        """Check only local Ollama availability and model presence; no inference."""
        if not self.settings.enabled:
            return LocalQwenHealth(False, False, self.settings.provider, self.settings.model, self.settings.base_url, "本地语义模型未启用")
        if not self.settings.is_local_ollama():
            return LocalQwenHealth(True, False, self.settings.provider, self.settings.model, self.settings.base_url, "本地语义模型地址不是受允许的环回 Ollama 地址")
        try:
            response = self._http_get(f"{self.settings.base_url}/api/tags", timeout=min(3, self.settings.timeout_seconds))
            if not response.ok:
                return LocalQwenHealth(True, False, self.settings.provider, self.settings.model, self.settings.base_url, "无法连接本地 Ollama")
            models = response.json().get("models", [])
            model_names = {str(item.get("name", "")) for item in models if isinstance(item, dict)}
            if self.settings.model not in model_names:
                return LocalQwenHealth(True, False, self.settings.provider, self.settings.model, self.settings.base_url, "本地未安装指定 Qwen 模型")
            return LocalQwenHealth(True, True, self.settings.provider, self.settings.model, self.settings.base_url)
        except (requests.RequestException, ValueError, KeyError):
            return LocalQwenHealth(True, False, self.settings.provider, self.settings.model, self.settings.base_url, "无法连接本地 Ollama")

    def generate_structured(self, *, task: str, system_prompt: str, user_prompt: str, document_id: str, page: int) -> dict[str, Any]:
        if not self.settings.enabled:
            raise LocalQwenUnavailable("本地语义模型未启用")
        if not self.settings.is_local_ollama():
            raise LocalQwenUnavailable("本地语义模型地址不是受允许的环回 Ollama 地址")
        if len(user_prompt) > self.settings.max_input_chars:
            user_prompt = user_prompt[:self.settings.max_input_chars]
        payload = {
            "model": self.settings.model,
            "messages": [{"role": "system", "content": system_prompt}, {"role": "user", "content": user_prompt}],
            "stream": False,
            "format": "json",
            "options": {"temperature": 0.0, "seed": 0},
        }
        started = time.perf_counter()
        try:
            response = self._http_post(f"{self.settings.base_url}/api/chat", json=payload, timeout=self.settings.timeout_seconds)
            response.raise_for_status()
            content = str(response.json()["message"]["content"])
            parsed = parse_json_object(content)
            logger.info("local_llm_completed provider=qwen task=%s document_id=%s page=%s input_chars=%s latency_ms=%s success=true", task, document_id, page, len(user_prompt), round((time.perf_counter() - started) * 1000))
            return parsed
        except (requests.RequestException, KeyError, ValueError, json.JSONDecodeError) as error:
            logger.warning("local_llm_failed provider=qwen task=%s document_id=%s page=%s input_chars=%s error_type=%s", task, document_id, page, len(user_prompt), type(error).__name__)
            raise LocalQwenUnavailable("本地语义模型当前不可用或未返回有效 JSON") from error
