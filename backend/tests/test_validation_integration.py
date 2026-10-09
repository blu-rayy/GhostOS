"""Integration tests: scan orchestrator + source-aware validator.

These run the real scan pipeline (extract -> classify -> validate -> plan)
with a mocked classifier, covering the cases Developer 1 requested:
missing amounts, conflicting totals, and unsupported evidence quotes.
"""

import time

import pytest
from fastapi.testclient import TestClient

import app.services.local_ai as local_ai
from app.main import app
from app.services.orchestrator import _map_validation_flags

client = TestClient(app)


def _mock_classifier(monkeypatch, **fields):
    """Make classify_excerpt return a fixed ClassificationRecord."""
    from app.schemas import ClassificationRecord

    defaults = {
        "category": "receipt",
        "merchant": "Test Shop",
        "date": "2026-10-09",
        "amount_text": "PHP 100.00",
        "currency": "PHP",
        "evidence_quote": "Total: PHP 100.00",
        "explanation": "Mocked classification.",
    }
    defaults.update(fields)
    record = ClassificationRecord(**defaults)
    result = local_ai.ClassificationResult(classification=record, elapsed_seconds=0.01)
    monkeypatch.setattr(local_ai, "classify_excerpt", lambda excerpt, **kw: result)


def _scan_until_done(root: str, attempts: int = 50) -> tuple[str, dict]:
    resp = client.post("/api/scan", json={"root": root})
    assert resp.status_code == 200, resp.text
    scan_id = resp.json()["scan_id"]
    prog: dict = {}
    for _ in range(attempts):
        prog = client.get(f"/api/scans/{scan_id}/progress").json()
        if prog["state"] in ("done", "error"):
            break
        time.sleep(0.1)
    assert prog["state"] == "done", f"Scan did not complete: {prog}"
    return scan_id, client.get(f"/api/scans/{scan_id}").json()


def _flag_codes(doc: dict) -> list[str]:
    return [f["code"] for f in doc["review_flags"]]


def test_quotation_flag_uses_explicit_plain_language_message() -> None:
    flags = _map_validation_flags(("quotation_document",))

    assert flags == [{
        "code": "quotation_document",
        "message": "This document appears to be a quotation rather than a completed transaction.",
    }]
    assert "Validation check reported" not in flags[0]["message"]


def test_missing_amount_flags_needs_review(tmp_path, monkeypatch):
    """A receipt with no amount_text gets missing_amount and blocks approval."""
    _mock_classifier(
        monkeypatch,
        amount_text=None,
        evidence_quote="ACME STORE",
    )
    (tmp_path / "receipt.txt").write_text("ACME STORE\nDate: 2026-10-09\nThank you")

    scan_id, result = _scan_until_done(str(tmp_path))
    doc = result["documents"][0]

    assert doc["status"] == "needs_review"
    assert "missing_amount" in _flag_codes(doc)
    # Original fields preserved; unparseable amount serializes as null.
    assert doc["classification"]["amount_text"] is None
    assert doc["classification"]["amount"] is None
    assert doc["classification"]["merchant"] == "Test Shop"

    plan = client.get(f"/api/scans/{scan_id}/plan").json()
    assert plan["blocking_review_count"] == 1


def test_conflicting_totals_yield_amount_conflict(tmp_path, monkeypatch):
    """Two competing totals -> ambiguous_amount maps to amount_conflict, amount null."""
    _mock_classifier(
        monkeypatch,
        amount_text="PHP 100.00",
        evidence_quote="Total: PHP 100.00",
    )
    (tmp_path / "receipt.txt").write_text("SHOP\nTotal: PHP 100.00\nTotal: PHP 200.00")

    _, result = _scan_until_done(str(tmp_path))
    doc = result["documents"][0]

    assert doc["status"] == "needs_review"
    assert "amount_conflict" in _flag_codes(doc)
    # Conflicting amount is never guessed: serialized as null.
    assert doc["classification"]["amount"] is None
    assert doc["classification"]["amount_text"] == "PHP 100.00"


def test_unsupported_evidence_quote_not_verified(tmp_path, monkeypatch):
    """An evidence quote absent from the source text fails verification."""
    _mock_classifier(
        monkeypatch,
        amount_text="PHP 50.00",
        evidence_quote="GRAND TOTAL PHP 50.00",
    )
    (tmp_path / "receipt.txt").write_text("SHOP RECEIPT\nTotal: PHP 50.00")

    _, result = _scan_until_done(str(tmp_path))
    doc = result["documents"][0]

    assert doc["status"] == "needs_review"
    assert "evidence_not_found" in _flag_codes(doc)
    assert doc["classification"]["evidence_verified"] is False
    # Amount itself still parses and is preserved.
    assert doc["classification"]["amount"] == "50.00"
