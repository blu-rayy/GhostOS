"""Opt-in real local Ollama integration test."""

import json
from urllib.error import URLError
from urllib.request import Request, urlopen

import pytest

from app.services.local_ai import (
    DEFAULT_MODEL,
    DEFAULT_OLLAMA_ENDPOINT,
    LocalAIError,
    classify_excerpt,
)


pytestmark = pytest.mark.integration


def _local_model_is_available() -> tuple[bool, str]:
    tags_endpoint = DEFAULT_OLLAMA_ENDPOINT.replace("/api/chat", "/api/tags")
    try:
        request = Request(tags_endpoint, method="GET")
        with urlopen(request, timeout=3) as response:
            payload = json.loads(response.read().decode("utf-8"))
    except (OSError, URLError, TimeoutError, json.JSONDecodeError) as exc:
        return False, f"local Ollama endpoint unavailable: {exc}"

    models = payload.get("models", [])
    names = {model.get("name") for model in models if isinstance(model, dict)}
    if DEFAULT_MODEL not in names:
        return False, f"local model {DEFAULT_MODEL!r} is not downloaded"
    return True, ""


def test_real_local_ollama_classification() -> None:
    available, reason = _local_model_is_available()
    if not available:
        pytest.skip(reason)

    excerpt = "COFFEE SHOP RECEIPT\nDate: 2026-10-09\nTotal: PHP 185.00"
    try:
        result = classify_excerpt(excerpt)
    except LocalAIError as exc:
        pytest.fail(f"local Ollama integration failed after availability check: {exc}")

    assert result.classification.category in {"invoice", "receipt", "other", "uncertain"}
    assert result.elapsed_seconds >= 0
