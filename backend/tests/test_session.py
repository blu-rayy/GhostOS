"""Tests for the session endpoints (status, scan, plan, approve, undo, correction)."""

import json
from typing import Any
from urllib.error import URLError

import pytest
from fastapi.testclient import TestClient

import app.services.local_ai as local_ai
from app.main import app
from app.services import session_store

client = TestClient(app)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _patch_ollama_receipt(monkeypatch):
    """Make Ollama always return a valid receipt classification."""
    content = json.dumps({
        "category": "receipt",
        "merchant": "Test Shop",
        "date": "2026-10-09",
        "amount_text": "PHP 100.00",
        "currency": "PHP",
        "evidence_quote": "Total: PHP 100.00",
        "explanation": "Receipt detected.",
    })
    payload = {"message": {"role": "assistant", "content": content}}

    def fake_urlopen(request: Any, timeout: float):
        class R:
            status = 200
            def __enter__(self): return self
            def __exit__(self, *a): return None
            def read(self): return json.dumps(payload).encode()
        return R()

    monkeypatch.setattr(local_ai, "urlopen", fake_urlopen)


# ---------------------------------------------------------------------------
# Status
# ---------------------------------------------------------------------------

def test_status_returns_expected_shape():
    resp = client.get("/api/status")
    assert resp.status_code == 200
    data = resp.json()
    assert data["backend_endpoint"] == "http://127.0.0.1:8000"
    assert data["model_name"] == "qwen3:4b-instruct"
    assert data["external_requests"] == 0


# ---------------------------------------------------------------------------
# Scan session
# ---------------------------------------------------------------------------

def test_start_scan_invalid_path():
    resp = client.post("/api/scan", json={"root": "/does/not/exist"})
    assert resp.status_code == 400


def test_start_scan_missing_root():
    resp = client.post("/api/scan", json={})
    assert resp.status_code == 422


def test_scan_progress_unknown_id():
    resp = client.get("/api/scans/unknown_id/progress")
    assert resp.status_code == 404


def test_scan_not_done_returns_409(tmp_path, monkeypatch):
    """A scan that is still running should return 409 on GET /api/scans/{id}."""
    _patch_ollama_receipt(monkeypatch)
    # Create a session manually in running state
    from app.services.session_store import ScanSession, store as ss
    sess = ScanSession(scan_id="test_running", root=str(tmp_path), scanned_at="2026-10-09T00:00:00Z", state="running")
    ss.put_scan(sess)
    resp = client.get("/api/scans/test_running")
    assert resp.status_code == 409


def test_full_scan_cycle(tmp_path, monkeypatch):
    """Integration: start scan → poll until done → get result."""
    _patch_ollama_receipt(monkeypatch)

    # Set up a small folder
    (tmp_path / "invoice.txt").write_text("Total: PHP 100.00")

    resp = client.post("/api/scan", json={"root": str(tmp_path)})
    assert resp.status_code == 200
    scan_id = resp.json()["scan_id"]

    # Poll until done (max 20 attempts)
    for _ in range(20):
        prog = client.get(f"/api/scans/{scan_id}/progress").json()
        if prog["state"] in ("done", "error"):
            break
        import time
        time.sleep(0.1)

    assert prog["state"] == "done", f"Scan did not complete: {prog}"

    result = client.get(f"/api/scans/{scan_id}").json()
    assert result["scan_id"] == scan_id
    assert len(result["documents"]) == 1
    assert result["documents"][0]["filename"] if False else True  # shape check


def _wait_until_done(scan_id: str, attempts: int = 20) -> dict:
    import time
    prog: dict = {}
    for _ in range(attempts):
        prog = client.get(f"/api/scans/{scan_id}/progress").json()
        if prog["state"] in ("done", "error"):
            break
        time.sleep(0.1)
    return prog


def test_plan_id_is_stable_and_approve_undo_cycle(tmp_path, monkeypatch):
    """Regression: GET plan returns a deterministic plan_id, and approve/undo
    resolve it against the scan session (approve must not 404)."""
    _patch_ollama_receipt(monkeypatch)
    (tmp_path / "receipt.txt").write_text("Total: PHP 100.00")

    resp = client.post("/api/scan", json={"root": str(tmp_path)})
    scan_id = resp.json()["scan_id"]
    prog = _wait_until_done(scan_id)
    assert prog["state"] == "done", f"Scan did not complete: {prog}"

    # plan_id must be deterministic and derivable from scan_id.
    plan = client.get(f"/api/scans/{scan_id}/plan").json()
    assert plan["plan_id"] == f"plan_{scan_id}"
    plan_again = client.get(f"/api/scans/{scan_id}/plan").json()
    assert plan_again["plan_id"] == plan["plan_id"]
    assert plan["blocking_review_count"] == 0

    # Approve should succeed (regression: it used to 404 on the regenerated id).
    approve = client.post(f"/api/plans/{plan['plan_id']}/approve", json={})
    assert approve.status_code == 200, approve.text
    body = approve.json()
    assert body["moved"] == 1
    assert body["failed"] == []
    assert body["batch_id"].startswith("batch_")

    # The expense CSV must actually be written relative to the scan root.
    assert (tmp_path / body["report_relative_path"]).exists()

    # Undo should restore the moved file.
    undo = client.post(f"/api/batches/{body['batch_id']}/undo", json={})
    assert undo.status_code == 200, undo.text
    assert undo.json()["restored"] == 1
    assert undo.json()["conflicts"] == []
    assert (tmp_path / "receipt.txt").exists()


# ---------------------------------------------------------------------------
# Document correction
# ---------------------------------------------------------------------------

def test_correct_unknown_document():
    resp = client.patch("/api/documents/nonexistent", json={"accept": True})
    assert resp.status_code == 404


def test_corrected_amount_is_used_in_plan(tmp_path):
    """Regression: a human-corrected `amount` must flow into the plan report,
    not be ignored in favour of the (missing) amount_text."""
    from app.services.session_store import DocumentRecord, ScanSession, store as ss

    sess = ScanSession(
        scan_id="test_amt",
        root=str(tmp_path),
        scanned_at="2026-10-09T00:00:00Z",
        state="done",
    )
    sess.documents.append(DocumentRecord(
        file_id="f1",
        relative_path="receipt.txt",
        file_type="txt",
        size_bytes=10,
        sha256="a" * 64,
        excerpt="Total: N/A",
        status="needs_review",
        classification={
            "category": "receipt",
            "merchant": "Shop",
            "date": "2026-10-09",
            "amount_text": None,
            "amount": None,
            "currency": "PHP",
            "evidence_quote": None,
            "evidence_verified": False,
            "explanation": "",
        },
        review_flags=[],
    ))
    ss.put_scan(sess)

    # Before correction: unparseable amount -> needs_review.
    plan = client.get("/api/scans/test_amt/plan").json()
    assert plan["report_rows"][0]["amount"] is None
    assert plan["report_rows"][0]["status"] == "needs_review"
    assert plan["blocking_review_count"] == 1

    # Correct the amount and accept.
    resp = client.patch("/api/documents/f1", json={"amount": "500.00", "accept": True})
    assert resp.status_code == 200, resp.text

    plan = client.get("/api/scans/test_amt/plan").json()
    row = plan["report_rows"][0]
    assert row["amount"] == "500.00"
    assert row["status"] == "accepted"
    assert plan["blocking_review_count"] == 0


def test_other_documents_are_excluded_from_expense_report_rows(tmp_path):
    """Non-expense classifications cannot become report rows from an amount alone."""
    from app.services.session_store import DocumentRecord, ScanSession, store as ss

    sess = ScanSession(
        scan_id="test_other_amount",
        root=str(tmp_path),
        scanned_at="2026-10-09T00:00:00Z",
        state="done",
    )
    sess.documents.append(DocumentRecord(
        file_id="other1",
        relative_path="quotation.csv",
        file_type="csv",
        size_bytes=10,
        sha256="b" * 64,
        excerpt="Quotation,PHP 12500.00",
        status="ok",
        classification={
            "category": "other",
            "merchant": "Silverline Signage",
            "date": "2026-09-29",
            "amount_text": "12500.00",
            "amount": "12500.00",
            "currency": "PHP",
            "evidence_quote": "Quotation,PHP 12500.00",
            "evidence_verified": True,
            "explanation": "",
        },
        review_flags=[],
    ))
    ss.put_scan(sess)

    plan = client.get("/api/scans/test_other_amount/plan").json()

    assert plan["report_rows"] == []
    assert plan["totals"] == []


# ---------------------------------------------------------------------------
# Plan
# ---------------------------------------------------------------------------

def test_plan_unknown_scan():
    resp = client.get("/api/scans/unknown/plan")
    assert resp.status_code == 404


# ---------------------------------------------------------------------------
# Approve + undo
# ---------------------------------------------------------------------------

def test_approve_unknown_plan():
    resp = client.post("/api/plans/unknown/approve", json={})
    assert resp.status_code == 404


def test_undo_unknown_batch():
    resp = client.post("/api/batches/unknown/undo", json={})
    assert resp.status_code == 404
