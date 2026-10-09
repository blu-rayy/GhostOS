"""Tests for POST /api/classify route and the operations service."""

import json
from typing import Any
from urllib.error import URLError

import pytest
from fastapi.testclient import TestClient

import app.services.local_ai as local_ai
from app.main import app
from app.schemas import ClassificationRecord
from app.services.operations import build_proposed_operation

client = TestClient(app)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _ollama_payload(content: object) -> dict[str, object]:
    return {"message": {"role": "assistant", "content": content}}


def _valid_content(category: str = "receipt") -> str:
    return json.dumps({
        "category": category,
        "merchant": "Coffee Shop",
        "date": "2026-10-09",
        "amount_text": "PHP 185.00",
        "currency": "PHP",
        "evidence_quote": "Total: PHP 185.00",
        "explanation": "The document contains a merchant receipt total.",
    })


def _mock_urlopen(content: str):
    def fake_urlopen(request: Any, timeout: float):
        class FakeResp:
            status = 200
            def __enter__(self): return self
            def __exit__(self, *a): return None
            def read(self): return json.dumps(_ollama_payload(content)).encode()
        return FakeResp()
    return fake_urlopen


# ---------------------------------------------------------------------------
# Route tests
# ---------------------------------------------------------------------------

def test_classify_receipt_returns_200_with_operation(monkeypatch):
    monkeypatch.setattr(local_ai, "urlopen", _mock_urlopen(_valid_content("receipt")))
    response = client.post("/api/classify", json={
        "file_id": "file-001",
        "text_excerpt": "COFFEE SHOP RECEIPT\nTotal: PHP 185.00",
    })
    assert response.status_code == 200
    data = response.json()
    assert data["file_id"] == "file-001"
    assert data["classification"]["category"] == "receipt"
    assert data["field_profile"] == "transaction"
    assert data["classification"]["document_kind"] == "receipt"
    assert data["needs_review"] is False
    assert data["proposed_operation"] is not None
    assert "organized/receipts" in data["proposed_operation"]["destination_relative_path"]


def test_classify_invoice_routes_to_invoices_folder(monkeypatch):
    monkeypatch.setattr(local_ai, "urlopen", _mock_urlopen(_valid_content("invoice")))
    response = client.post("/api/classify", json={
        "file_id": "file-002",
        "text_excerpt": "INVOICE #1234\nTotal: PHP 5000.00",
    })
    assert response.status_code == 200
    data = response.json()
    assert "organized/invoices" in data["proposed_operation"]["destination_relative_path"]


def test_classify_uncertain_needs_review_no_operation(monkeypatch):
    monkeypatch.setattr(local_ai, "urlopen", _mock_urlopen(_valid_content("uncertain")))
    response = client.post("/api/classify", json={
        "file_id": "file-003",
        "text_excerpt": "Some ambiguous document text.",
    })
    assert response.status_code == 200
    data = response.json()
    assert data["needs_review"] is True
    assert data["proposed_operation"] is None


def test_classify_statement_exposes_reference_profile(monkeypatch):
    content = json.dumps({
        "category": "other",
        "document_kind": "statement",
        "merchant": None,
        "date": None,
        "amount_text": None,
        "currency": None,
        "evidence_quote": "Account statement",
        "explanation": "Multiple account transactions are present.",
    })
    monkeypatch.setattr(local_ai, "urlopen", _mock_urlopen(content))
    response = client.post("/api/classify", json={
        "file_id": "file-statement",
        "text_excerpt": "Account statement",
    })
    assert response.status_code == 200
    data = response.json()
    assert data["classification"]["document_kind"] == "statement"
    assert data["field_profile"] == "reference"
    assert data["proposed_operation"] is None
    assert data["needs_review"] is True


def test_classify_explicit_null_kind_cannot_propose_transaction_operation(monkeypatch):
    content = json.dumps({
        "category": "invoice",
        "document_kind": None,
        "merchant": "Unknown supplier",
        "date": "2026-10-09",
        "amount_text": "PHP 500.00",
        "currency": "PHP",
        "evidence_quote": "Total: PHP 500.00",
        "explanation": "The document kind is not identified.",
    })
    monkeypatch.setattr(local_ai, "urlopen", _mock_urlopen(content))
    response = client.post("/api/classify", json={
        "file_id": "file-null-kind",
        "text_excerpt": "Unknown invoice-like paperwork\nTotal: PHP 500.00",
    })
    assert response.status_code == 200
    data = response.json()
    assert data["classification"]["document_kind"] is None
    assert data["field_profile"] == "none"
    assert data["proposed_operation"] is None
    assert data["needs_review"] is True


def test_classify_ollama_unavailable_returns_503(monkeypatch):
    def unavailable(request, timeout):
        raise URLError("connection refused")
    monkeypatch.setattr(local_ai, "urlopen", unavailable)
    response = client.post("/api/classify", json={
        "file_id": "file-004",
        "text_excerpt": "Some document text.",
    })
    assert response.status_code == 503


def test_classify_schema_validation_failure_marks_review(monkeypatch):
    bad_content = json.dumps({"category": "invalid_category"})
    monkeypatch.setattr(local_ai, "urlopen", _mock_urlopen(bad_content))
    response = client.post("/api/classify", json={
        "file_id": "file-005",
        "text_excerpt": "Some document text.",
    })
    assert response.status_code == 200
    data = response.json()
    assert data["needs_review"] is True
    assert data["classification"]["category"] == "uncertain"


def test_classify_rejects_empty_excerpt():
    response = client.post("/api/classify", json={
        "file_id": "file-006",
        "text_excerpt": "",
    })
    # Empty excerpt is rejected by schema (min_length=1)
    assert response.status_code == 422


# ---------------------------------------------------------------------------
# Operations service unit tests
# ---------------------------------------------------------------------------

def _make_classification(category: str, merchant: str | None = None, amount: str | None = None):
    return ClassificationRecord(
        category=category,
        merchant=merchant,
        amount_text=amount,
    )


def test_receipt_gets_receipts_folder():
    op, needs_review, reason = build_proposed_operation(
        file_id="f1",
        original_relative_path="inbox/coffee.pdf",
        classification=_make_classification("receipt", merchant="Coffee Shop", amount="PHP 185.00"),
    )
    assert op is not None
    assert op.destination_relative_path == "organized/receipts/coffee.pdf"
    assert needs_review is False
    assert reason is None


def test_invoice_gets_invoices_folder():
    op, needs_review, reason = build_proposed_operation(
        file_id="f2",
        original_relative_path="inbox/inv001.pdf",
        classification=_make_classification("invoice"),
    )
    assert op is not None
    assert "organized/invoices" in op.destination_relative_path


def test_uncertain_triggers_review_and_no_operation():
    op, needs_review, reason = build_proposed_operation(
        file_id="f3",
        original_relative_path="inbox/unknown.pdf",
        classification=_make_classification("uncertain"),
    )
    assert op is None
    assert needs_review is True
    assert reason is not None


def test_reason_includes_merchant_and_amount():
    op, _, _ = build_proposed_operation(
        file_id="f4",
        original_relative_path="inbox/receipt.pdf",
        classification=_make_classification("receipt", merchant="Acme", amount="USD 50.00"),
    )
    assert op is not None
    assert "Acme" in op.reason
    assert "USD 50.00" in op.reason
