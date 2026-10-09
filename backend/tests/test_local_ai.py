"""Unit tests for the local Ollama classification adapter."""

import json
import socket
from typing import Any
from urllib.error import URLError

import pytest

import app.services.local_ai as local_ai
from app.schemas import ClassificationRecord


class FakeResponse:
    def __init__(self, payload: object, status: int = 200) -> None:
        self.status = status
        self._raw = json.dumps(payload).encode("utf-8")

    def __enter__(self) -> "FakeResponse":
        return self

    def __exit__(self, *args: object) -> None:
        return None

    def read(self) -> bytes:
        return self._raw


def ollama_payload(content: object) -> dict[str, object]:
    return {"message": {"role": "assistant", "content": content}}


def valid_content(category: str = "receipt") -> str:
    return json.dumps(
        {
            "category": category,
            "merchant": "Coffee Shop",
            "date": "2026-10-09",
            "amount_text": "PHP 185.00",
            "currency": "PHP",
            "evidence_quote": "Total: PHP 185.00",
            "explanation": "The excerpt identifies a receipt total.",
        }
    )


def test_success_returns_valid_classification_and_elapsed_time(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    captured: dict[str, Any] = {}

    def fake_urlopen(request: Any, timeout: float) -> FakeResponse:
        captured["request"] = request
        captured["timeout"] = timeout
        return FakeResponse(ollama_payload(valid_content()))

    monkeypatch.setattr(local_ai, "urlopen", fake_urlopen)

    result = local_ai.classify_excerpt("COFFEE SHOP RECEIPT\nTotal: PHP 185.00")

    assert isinstance(result.classification, ClassificationRecord)
    assert result.classification.category == "receipt"
    assert result.elapsed_seconds >= 0
    request_body = json.loads(captured["request"].data.decode("utf-8"))
    assert request_body["stream"] is False
    # Structured output is enforced by prompt + post-validation, not Ollama's
    # "format" schema (which suppressed optional fields on qwen3:4b-instruct).
    assert "format" not in request_body
    assert request_body["options"]["temperature"] == 0
    assert "RECEIPT" in request_body["messages"][1]["content"]
    system = request_body["messages"][0]["content"]
    assert "merchant" in system and "amount_text" in system and "currency" in system


@pytest.mark.parametrize("category", ["invoice", "receipt", "other", "uncertain"])
def test_all_allowed_categories_are_supported(
    monkeypatch: pytest.MonkeyPatch, category: str
) -> None:
    monkeypatch.setattr(
        local_ai,
        "urlopen",
        lambda request, timeout: FakeResponse(ollama_payload(valid_content(category))),
    )

    result = local_ai.classify_excerpt("document excerpt")

    assert result.classification.category == category


def test_missing_optional_fields_are_handled_as_none(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    content = json.dumps({"category": "other"})
    monkeypatch.setattr(
        local_ai,
        "urlopen",
        lambda request, timeout: FakeResponse(ollama_payload(content)),
    )

    result = local_ai.classify_excerpt("unclassified document")

    assert result.classification.merchant is None
    assert result.classification.explanation is None


@pytest.mark.parametrize(
    "content",
    [
        json.dumps({"category": "invalid"}),
        json.dumps({"category": "receipt", "source_id": "secret"}),
    ],
)
def test_invalid_or_unexpected_model_fields_are_rejected(
    monkeypatch: pytest.MonkeyPatch, content: str
) -> None:
    monkeypatch.setattr(
        local_ai,
        "urlopen",
        lambda request, timeout: FakeResponse(ollama_payload(content)),
    )

    with pytest.raises(local_ai.LocalAIValidationError):
        local_ai.classify_excerpt("document excerpt")


@pytest.mark.parametrize(
    "payload",
    [
        {"message": {"content": "not-json"}},
        {"message": {"content": json.dumps(["not", "an", "object"])}},
        {"unexpected": "response"},
    ],
)
def test_malformed_or_unexpected_responses_fail_clearly(
    monkeypatch: pytest.MonkeyPatch, payload: dict[str, object]
) -> None:
    monkeypatch.setattr(
        local_ai,
        "urlopen",
        lambda request, timeout: FakeResponse(payload),
    )

    with pytest.raises(local_ai.LocalAIResponseError):
        local_ai.classify_excerpt("document excerpt")


def test_connection_error_is_wrapped_and_retried_once(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls = 0

    def unavailable(request: Any, timeout: float) -> FakeResponse:
        nonlocal calls
        calls += 1
        raise URLError("connection refused")

    monkeypatch.setattr(local_ai, "urlopen", unavailable)

    with pytest.raises(local_ai.LocalAIUnavailableError):
        local_ai.classify_excerpt("document excerpt")

    assert calls == 2


def test_timeout_is_wrapped_without_exceeding_one_retry(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls = 0

    def times_out(request: Any, timeout: float) -> FakeResponse:
        nonlocal calls
        calls += 1
        raise socket.timeout("timed out")

    monkeypatch.setattr(local_ai, "urlopen", times_out)

    with pytest.raises(local_ai.LocalAITimeoutError):
        local_ai.classify_excerpt("document excerpt", max_retries=1)

    assert calls == 2


def test_validation_error_is_not_retried(monkeypatch: pytest.MonkeyPatch) -> None:
    calls = 0

    def invalid_response(request: Any, timeout: float) -> FakeResponse:
        nonlocal calls
        calls += 1
        return FakeResponse(ollama_payload(json.dumps({"category": "invalid"})))

    monkeypatch.setattr(local_ai, "urlopen", invalid_response)

    with pytest.raises(local_ai.LocalAIValidationError):
        local_ai.classify_excerpt("document excerpt", max_retries=1)

    assert calls == 1


def test_excessively_long_input_is_rejected_before_http_request(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls = 0

    def should_not_be_called(request: Any, timeout: float) -> FakeResponse:
        nonlocal calls
        calls += 1
        return FakeResponse(ollama_payload(valid_content()))

    monkeypatch.setattr(local_ai, "urlopen", should_not_be_called)

    with pytest.raises(local_ai.LocalAIInputError, match="maximum length"):
        local_ai.classify_excerpt("x" * 11, max_excerpt_length=10)

    assert calls == 0
