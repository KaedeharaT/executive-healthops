"""Small local Ollama open-source LLM client, based on the validated research client flow."""

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
class LocalLLMSettings:
    enabled: bool
    provider: str
    base_url: str
    model: str
    timeout_seconds: int
    max_input_chars: int
    api_key: str = ""
    allow_external_phi: bool = False

    @classmethod
    def from_environment(cls) -> "LocalLLMSettings":
        provider = os.getenv("LOCAL_LLM_PROVIDER", "local").strip().lower()
        base_url = (
            os.getenv("LLM_API_BASE", "").strip()
            if provider in {"openai_compatible", "compatible_api"}
            else os.getenv("OLLAMA_BASE_URL", "http://127.0.0.1:11434").strip()
        )
        return cls(
            enabled=os.getenv("LOCAL_LLM_ENABLED", "false").lower() == "true",
            provider=provider,
            base_url=base_url.rstrip("/"),
            model=os.getenv("LOCAL_LLM_MODEL", "").strip(),
            # Keep the validated research-client default.  A local model may need
            # longer than a minute for a first (cold) inference, while the feature
            # remains opt-in and failures still fall back to human review.
            timeout_seconds=max(1, int(os.getenv("LOCAL_LLM_TIMEOUT_SECONDS", "600"))),
            max_input_chars=max(200, int(os.getenv("LOCAL_LLM_MAX_INPUT_CHARS", "3000"))),
            api_key=os.getenv("LLM_API_KEY", "").strip(),
            allow_external_phi=os.getenv("ALLOW_EXTERNAL_PHI_LLM", "false").lower() == "true",
        )

    def is_local_ollama(self) -> bool:
        parsed = urlparse(self.base_url)
        return self.provider in {"local", "ollama", "local_llm"} and parsed.scheme == "http" and parsed.hostname in _LOCAL_HOSTS

    def is_openai_compatible(self) -> bool:
        return self.provider in {"openai_compatible", "compatible_api"}

    def endpoint_allowed(self) -> bool:
        parsed = urlparse(self.base_url)
        return parsed.scheme in {"http", "https"} and (
            parsed.hostname in _LOCAL_HOSTS or self.allow_external_phi
        )


class LocalLLMUnavailable(RuntimeError):
    """The optional local service is disabled or unavailable."""


@dataclass(frozen=True)
class LocalLLMHealth:
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


class LocalLLMClient:
    """Configurable semantic LLM client for local or OpenAI-compatible endpoints."""

    def __init__(self, settings: LocalLLMSettings | None = None, http_post=requests.post, http_get=requests.get) -> None:
        self.settings = settings or LocalLLMSettings.from_environment()
        self._http_post = http_post
        self._http_get = http_get

    def available(self) -> bool:
        return self.health_check().available

    def health_check(self) -> LocalLLMHealth:
        """Check only local Ollama availability and model presence; no inference."""
        if not self.settings.enabled:
            return LocalLLMHealth(False, False, self.settings.provider, self.settings.model, self.settings.base_url, "本地语义模型未启用")
        if not self.settings.model:
            return LocalLLMHealth(True, False, self.settings.provider, self.settings.model, self.settings.base_url, "尚未配置本地模型")
        if not self.settings.endpoint_allowed():
            return LocalLLMHealth(True, False, self.settings.provider, self.settings.model, self.settings.base_url, "LLM 地址不符合隐私安全策略")
        try:
            if self.settings.is_local_ollama():
                url = f"{self.settings.base_url}/api/tags"
                headers = None
            elif self.settings.is_openai_compatible():
                url = f"{self.settings.base_url}/v1/models"
                headers = {"Authorization": f"Bearer {self.settings.api_key}"} if self.settings.api_key else None
            else:
                return LocalLLMHealth(True, False, self.settings.provider, self.settings.model, self.settings.base_url, "不支持的 LLM Provider")
            response = self._http_get(url, headers=headers, timeout=min(3, self.settings.timeout_seconds))
            if not response.ok:
                return LocalLLMHealth(True, False, self.settings.provider, self.settings.model, self.settings.base_url, "无法连接 LLM Provider")
            payload = response.json()
            models = payload.get("models", []) if self.settings.is_local_ollama() else payload.get("data", [])
            key = "name" if self.settings.is_local_ollama() else "id"
            model_names = {str(item.get(key, "")) for item in models if isinstance(item, dict)}
            if self.settings.model not in model_names:
                return LocalLLMHealth(True, False, self.settings.provider, self.settings.model, self.settings.base_url, "本地未安装指定模型")
            return LocalLLMHealth(True, True, self.settings.provider, self.settings.model, self.settings.base_url)
        except (requests.RequestException, ValueError, KeyError):
            return LocalLLMHealth(True, False, self.settings.provider, self.settings.model, self.settings.base_url, "无法连接 LLM Provider")

    def generate_structured(self, *, task: str, system_prompt: str, user_prompt: str, document_id: str, page: int) -> dict[str, Any]:
        if not self.settings.enabled:
            raise LocalLLMUnavailable("本地语义模型未启用")
        if not self.settings.model:
            raise LocalLLMUnavailable("尚未配置本地模型")
        if not self.settings.endpoint_allowed():
            raise LocalLLMUnavailable("LLM 地址不符合隐私安全策略")
        if len(user_prompt) > self.settings.max_input_chars:
            user_prompt = user_prompt[:self.settings.max_input_chars]
        messages = [{"role": "system", "content": system_prompt}, {"role": "user", "content": user_prompt}]
        payload = {
            "model": self.settings.model,
            "messages": messages,
            "stream": False,
        }
        if self.settings.is_local_ollama():
            url = f"{self.settings.base_url}/api/chat"
            payload.update({"format": "json", "options": {"temperature": 0.0, "seed": 0}})
            headers = None
        elif self.settings.is_openai_compatible():
            url = f"{self.settings.base_url}/v1/chat/completions"
            payload.update({"temperature": 0.0, "response_format": {"type": "json_object"}})
            headers = {"Authorization": f"Bearer {self.settings.api_key}"} if self.settings.api_key else None
        else:
            raise LocalLLMUnavailable("不支持的 LLM Provider")
        started = time.perf_counter()
        try:
            response = self._http_post(url, json=payload, headers=headers, timeout=self.settings.timeout_seconds)
            response.raise_for_status()
            response_payload = response.json()
            content = str(response_payload["message"]["content"] if self.settings.is_local_ollama() else response_payload["choices"][0]["message"]["content"])
            parsed = parse_json_object(content)
            logger.info("local_llm_completed provider=local_llm task=%s document_id=%s page=%s input_chars=%s latency_ms=%s success=true", task, document_id, page, len(user_prompt), round((time.perf_counter() - started) * 1000))
            return parsed
        except (requests.RequestException, KeyError, ValueError, json.JSONDecodeError) as error:
            logger.warning("local_llm_failed provider=local_llm task=%s document_id=%s page=%s input_chars=%s error_type=%s", task, document_id, page, len(user_prompt), type(error).__name__)
            raise LocalLLMUnavailable("本地语义模型当前不可用或未返回有效 JSON") from error
