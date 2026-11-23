"""Groq client: allowlist, timeout, one retry, error mapping, PII-free logs (R14, R45, R46)."""

from __future__ import annotations

import logging

import httpx
import pytest

from app.agents.llm_client import GroqClient, LLMError, check_endpoint

SECRET_PROMPT = "Anouk says: 400 spot rate requests a week"
KEY = "gsk_test_key_should_never_be_logged"


def client(
    handler: httpx.MockTransport, base: str = "https://api.groq.com/openai/v1"
) -> GroqClient:
    return GroqClient(api_key=KEY, base_url=base, model="m", timeout_s=1, transport=handler)


def ok(content: str = '{"a": 1}') -> httpx.Response:
    return httpx.Response(200, json={"choices": [{"message": {"content": content}}]})


def test_success_sends_model_and_bearer_key() -> None:
    seen: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        seen.append(request)
        return ok()

    assert (
        client(httpx.MockTransport(handler)).complete("s", "u", json_mode=True, ref="IN-1")
        == '{"a": 1}'
    )
    assert seen[0].url.host == "api.groq.com"
    assert seen[0].headers["authorization"] == f"Bearer {KEY}"
    assert b'"response_format"' in seen[0].content


def test_one_retry_after_timeout_then_success() -> None:
    attempts: list[Exception | httpx.Response] = [httpx.ReadTimeout("slow"), ok()]

    def handler(request: httpx.Request) -> httpx.Response:
        item = attempts.pop(0)
        if isinstance(item, Exception):
            raise item
        return item

    assert client(httpx.MockTransport(handler)).complete("s", "u", json_mode=True, ref="r")


@pytest.mark.parametrize(
    ("raise_or_status", "kind", "calls"),
    [
        (httpx.ReadTimeout("slow"), "timeout", 2),
        (httpx.ConnectError("down"), "unreachable", 2),
        (500, "model_error", 2),
        (429, "model_error", 2),
        (400, "model_error", 1),  # not retryable
        (401, "model_error", 1),
    ],
)
def test_failures_map_to_kinds(raise_or_status: Exception | int, kind: str, calls: int) -> None:
    count = 0

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal count
        count += 1
        if isinstance(raise_or_status, Exception):
            raise raise_or_status
        return httpx.Response(raise_or_status, json={"error": "x"})

    with pytest.raises(LLMError) as info:
        client(httpx.MockTransport(handler)).complete("s", "u", json_mode=True, ref="r")
    assert info.value.kind == kind
    assert count == calls


@pytest.mark.parametrize(
    "body",
    [{"choices": []}, {"nope": 1}, {"choices": [{"message": {"content": "  "}}]}],
)
def test_bad_response_shape_is_model_error(body: dict[str, object]) -> None:
    transport = httpx.MockTransport(lambda r: httpx.Response(200, json=body))
    with pytest.raises(LLMError) as info:
        client(transport).complete("s", "u", json_mode=True, ref="r")
    assert info.value.kind == "model_error"


@pytest.mark.parametrize(
    "base",
    [
        "https://evil.example.com/v1",
        "http://api.groq.com/openai/v1",  # not https
        "https://api.groq.com.evil.com/v1",
        "https://user@evil.com/api.groq.com",
    ],
)
def test_endpoint_not_on_allowlist_is_refused_before_any_request(base: str) -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        raise AssertionError("no request may be made")

    with pytest.raises(LLMError):
        client(httpx.MockTransport(handler), base).complete("s", "u", json_mode=True, ref="r")
    with pytest.raises(LLMError):
        check_endpoint(base)


def test_logs_have_no_prompt_reply_or_key(caplog: pytest.LogCaptureFixture) -> None:
    attempts = iter([httpx.Response(503), ok(SECRET_PROMPT)])
    transport = httpx.MockTransport(lambda r: next(attempts))
    with caplog.at_level(logging.DEBUG):
        client(transport).complete(SECRET_PROMPT, SECRET_PROMPT, json_mode=True, ref="IN-001")
    text = caplog.text
    assert "IN-001" in text
    assert "Anouk" not in text and "spot rate" not in text and KEY not in text
