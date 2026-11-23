"""OpenAI-compatible chat client (Groq by default).

- The only network call the app makes. The host must match the configured endpoint and be on
  the allowlist; anything else is refused before a socket opens.
- Timeout per attempt, one retry on timeout / connection error / 429 / 5xx.
- Logs carry a prompt hash, status and latency. Never the prompt, the reply or the key.
"""

from __future__ import annotations

import logging
import time
from dataclasses import dataclass
from typing import Protocol
from urllib.parse import urlsplit

import httpx

from app.agents.schemas import FailureKind
from app.core.config import Settings
from app.core.logging_setup import short_hash

log = logging.getLogger(__name__)

ALLOWED_HOSTS = frozenset({"api.groq.com"})
RETRYABLE_STATUS = frozenset({429, 500, 502, 503, 504})


class LLMError(Exception):
    def __init__(self, kind: FailureKind, detail: str) -> None:
        super().__init__(detail)
        self.kind: FailureKind = kind
        self.detail = detail


class LLMClient(Protocol):
    @property
    def model(self) -> str: ...

    def complete(self, system: str, user: str, *, json_mode: bool, ref: str) -> str:
        """Return the assistant message text. Raise LLMError on any failure.

        `ref` is a record id used for logs only.
        """
        ...


def check_endpoint(base_url: str) -> str:
    """Validate the endpoint against the allowlist. Returns the chat completions URL."""
    parts = urlsplit(base_url)
    if parts.scheme != "https" or (parts.hostname or "") not in ALLOWED_HOSTS:
        raise LLMError("unreachable", "LLM endpoint is not on the allowlist")
    return base_url.rstrip("/") + "/chat/completions"


@dataclass
class GroqClient:
    api_key: str
    base_url: str
    model: str
    timeout_s: float = 20.0
    max_attempts: int = 2
    transport: httpx.BaseTransport | None = None  # tests inject a MockTransport

    @classmethod
    def from_settings(cls, settings: Settings) -> GroqClient:
        if not settings.llm_api_key:
            raise LLMError("unreachable", "no API key configured")
        return cls(
            api_key=settings.llm_api_key,
            base_url=settings.llm_base_url,
            model=settings.llm_model,
            timeout_s=settings.llm_timeout_s,
        )

    def complete(self, system: str, user: str, *, json_mode: bool, ref: str) -> str:
        url = check_endpoint(self.base_url)
        payload: dict[str, object] = {
            "model": self.model,
            "temperature": 0,
            "messages": [
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
        }
        if json_mode:
            payload["response_format"] = {"type": "json_object"}
        headers = {"Authorization": f"Bearer {self.api_key}"}
        prompt_hash = short_hash(system + user)
        last = LLMError("model_error", "no attempt made")
        with httpx.Client(timeout=self.timeout_s, transport=self.transport) as http:
            for attempt in range(1, self.max_attempts + 1):
                started = time.monotonic()
                try:
                    response = http.post(url, json=payload, headers=headers)
                except httpx.TimeoutException:
                    last = LLMError("timeout", f"timed out after {self.timeout_s:g}s")
                except httpx.HTTPError as exc:
                    last = LLMError("unreachable", f"connection error ({type(exc).__name__})")
                else:
                    elapsed = int((time.monotonic() - started) * 1000)
                    log.info(
                        "llm call ref=%s prompt=%s attempt=%d status=%d ms=%d",
                        ref, prompt_hash, attempt, response.status_code, elapsed,
                    )  # fmt: skip
                    if response.status_code == 200:
                        return _message_text(response)
                    last = LLMError("model_error", f"HTTP {response.status_code}")
                    if response.status_code not in RETRYABLE_STATUS:
                        break
                log.warning(
                    "llm attempt failed ref=%s prompt=%s attempt=%d kind=%s",
                    ref, prompt_hash, attempt, last.kind,
                )  # fmt: skip
        raise last


def _message_text(response: httpx.Response) -> str:
    try:
        content = response.json()["choices"][0]["message"]["content"]
    except (ValueError, KeyError, IndexError, TypeError) as exc:
        raise LLMError("model_error", "unexpected response shape") from exc
    if not isinstance(content, str) or not content.strip():
        raise LLMError("model_error", "empty completion")
    return content
