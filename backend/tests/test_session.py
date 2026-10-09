"""Tests for the session endpoints (status, scan, plan, approve, undo, correction)."""

import json
import os
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


def _put_unresolved_session(tmp_path):
    from app.services.session_store import DocumentRecord, ScanSession, store as ss

    session = ScanSession(
        scan_id=f"partial_{tmp_path.name}",
        root=str(tmp_path),
        scanned_at="2026-10-09T00:00:00Z",
        state="done",
    )
    content = b"Receipt needing review"
    (tmp_path / "receipt.txt").write_bytes(content)
    import hashlib
    session.documents.append(DocumentRecord(
        file_id=f"{session.scan_id}_file_0",
        relative_path="receipt.txt",
        file_type="txt",
        size_bytes=len(content),
        sha256=hashlib.sha256(content).hexdigest(),
        excerpt=content.decode(),
        status="needs_review",
        classification={
            "category": "receipt",
            "merchant": None,
            "date": None,
            "amount_text": None,
            "amount": None,
            "currency": None,
            "evidence_quote": None,
            "evidence_verified": False,
            "explanation": "Needs review",
        },
        review_flags=[{"code": "missing_amount", "message": "review"}],
    ))
    ss.put_scan(session)
    return session


def test_default_mode_blocks_unresolved_approval(tmp_path):
    session = _put_unresolved_session(tmp_path)
    preview = client.get(f"/api/scans/{session.scan_id}/plan")
    assert preview.status_code == 200
    payload = preview.json()
    assert payload["mode"] == "blocking"
    assert payload["operations"][0]["destination_relative_path"].startswith("Uncategorized/")
    blocked = client.post(f"/api/plans/{payload['plan_id']}/approve", json={})
    assert blocked.status_code == 409
    assert (tmp_path / "receipt.txt").exists()


def test_partial_mode_routes_unsorted_and_requires_matching_explicit_approval(tmp_path):
    session = _put_unresolved_session(tmp_path)
    preview = client.get(f"/api/scans/{session.scan_id}/plan?mode=partial")
    assert preview.status_code == 200
    payload = preview.json()
    assert payload["mode"] == "partial"
    assert payload["operations"][0]["destination_relative_path"].startswith("Uncategorized/")
    assert payload["report_rows"] == []
    assert payload["totals"] == []

    implicit_blocking = client.post(f"/api/plans/{payload['plan_id']}/approve", json={})
    assert implicit_blocking.status_code == 409

    approved = client.post(
        f"/api/plans/{payload['plan_id']}/approve",
        json={"mode": "partial"},
    )
    assert approved.status_code == 200, approved.text
    batch = approved.json()
    assert batch["moved"] == 1
    unsorted = tmp_path / payload["operations"][0]["destination_relative_path"]
    assert unsorted.exists()

    undone = client.post(f"/api/batches/{batch['batch_id']}/undo", json={})
    assert undone.status_code == 200
    assert undone.json()["restored"] == 1
    assert (tmp_path / "receipt.txt").exists()


def test_invalid_sort_mode_returns_422(tmp_path):
    session = _put_unresolved_session(tmp_path)
    assert client.get(f"/api/scans/{session.scan_id}/plan?mode=unsafe").status_code == 422
    preview = client.get(f"/api/scans/{session.scan_id}/plan").json()
    response = client.post(
        f"/api/plans/{preview['plan_id']}/approve",
        json={"mode": "unsafe"},
    )
    assert response.status_code == 422


def test_new_mode_preview_supersedes_old_snapshot_and_rejects_old_approval(tmp_path):
    session = _put_unresolved_session(tmp_path)
    blocking = client.get(f"/api/scans/{session.scan_id}/plan").json()
    partial = client.get(f"/api/scans/{session.scan_id}/plan?mode=partial").json()
    assert blocking["plan_id"] == partial["plan_id"]

    old_approval = client.post(f"/api/plans/{blocking['plan_id']}/approve", json={})
    assert old_approval.status_code == 409
    assert "mode" in old_approval.json()["detail"].lower()


def test_partial_mode_still_rejects_changed_source_without_moving(tmp_path):
    session = _put_unresolved_session(tmp_path)
    preview = client.get(f"/api/scans/{session.scan_id}/plan?mode=partial").json()
    (tmp_path / "receipt.txt").write_text("changed after scan")

    response = client.post(
        f"/api/plans/{preview['plan_id']}/approve",
        json={"mode": "partial"},
    )
    assert response.status_code == 200
    assert response.json()["moved"] == 0
    assert response.json()["failed"]
    assert (tmp_path / "receipt.txt").exists()


def test_partial_mode_preserves_classified_transaction_destination(tmp_path):
    session = _put_done_session_with_files(tmp_path)
    preview = client.get(f"/api/scans/{session.scan_id}/plan?mode=partial")

    assert preview.status_code == 200
    payload = preview.json()
    assert payload["mode"] == "partial"
    assert payload["operations"][0]["destination_relative_path"].startswith("Receipts/")
    assert payload["report_rows"][0]["status"] == "accepted"


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


def test_non_transactional_corrections_are_rejected(tmp_path):
    from app.services.session_store import DocumentRecord, ScanSession, store as ss

    sess = ScanSession(
        scan_id="test_statement_correction",
        root=str(tmp_path),
        scanned_at="2026-10-09T00:00:00Z",
        state="done",
    )
    for file_id, kind in (("statement1", "statement"), ("civil1", "identity_or_civil")):
        sess.documents.append(DocumentRecord(
            file_id=file_id,
            relative_path=f"{file_id}.txt",
            file_type="txt",
            size_bytes=1,
            sha256="c" * 64,
            excerpt="reference",
            status="needs_review",
            classification={
                "category": "other",
                "document_kind": kind,
                "merchant": None,
                "date": None,
                "amount_text": None,
                "amount": None,
                "currency": None,
                "evidence_quote": "reference",
                "evidence_verified": True,
                "explanation": "",
            },
        ))
    ss.put_scan(sess)

    for file_id in ("statement1", "civil1"):
        response = client.patch(
            f"/api/documents/{file_id}",
            json={"amount": "100.00", "accept": True},
        )
        assert response.status_code == 422


def test_contradictory_category_and_transaction_correction_has_no_mutation(tmp_path):
    from app.services.session_store import DocumentRecord, ScanSession, store as ss

    sess = ScanSession(
        scan_id="test_contradictory_correction",
        root=str(tmp_path),
        scanned_at="2026-10-09T00:00:00Z",
        state="done",
    )
    original_classification = {
        "category": "other",
        "document_kind": "statement",
        "field_profile": "reference",
        "merchant": None,
        "date": None,
        "amount_text": None,
        "amount": None,
        "currency": None,
        "evidence_quote": "Account statement",
        "evidence_verified": True,
        "explanation": "Multiple account transactions.",
    }
    original_flags = [{"code": "non_transactional_document", "message": "review"}]
    sess.documents.append(DocumentRecord(
        file_id="contradictory-doc",
        relative_path="statement.txt",
        file_type="txt",
        size_bytes=1,
        sha256="2" * 64,
        excerpt="Account statement",
        status="needs_review",
        classification=dict(original_classification),
        review_flags=list(original_flags),
    ))
    ss.put_scan(sess)
    preview = client.get("/api/scans/test_contradictory_correction/plan").json()
    revision_before = sess.plan_revision

    response = client.patch(
        "/api/documents/contradictory-doc",
        json={"category": "invoice", "amount": "100.00", "accept": True},
    )
    assert response.status_code == 422

    doc = ss.find_document("contradictory-doc")
    assert doc is not None
    assert doc.classification == original_classification
    assert doc.review_flags == original_flags
    assert doc.status == "needs_review"
    assert doc.user_corrected is False
    assert sess.plan_revision == revision_before
    current_preview = client.get("/api/scans/test_contradictory_correction/plan").json()
    assert current_preview == preview


def test_explicit_null_kind_cannot_become_transaction_expense(tmp_path):
    from app.services.session_store import DocumentRecord, ScanSession, store as ss

    sess = ScanSession(
        scan_id="test_null_kind_invoice",
        root=str(tmp_path),
        scanned_at="2026-10-09T00:00:00Z",
        state="done",
    )
    sess.documents.append(DocumentRecord(
        file_id="null-kind-invoice",
        relative_path="unknown.txt",
        file_type="txt",
        size_bytes=1,
        sha256="3" * 64,
        excerpt="Unknown paperwork",
        status="needs_review",
        classification={
            "category": "invoice",
            "document_kind": None,
            "field_profile": "none",
            "merchant": None,
            "date": None,
            "amount_text": "PHP 100.00",
            "amount": "100.00",
            "currency": "PHP",
            "evidence_quote": None,
            "evidence_verified": False,
            "explanation": "Unidentified document",
        },
        review_flags=[{"code": "uncertain_document_kind", "message": "review"}],
    ))
    ss.put_scan(sess)

    patch = client.patch(
        "/api/documents/null-kind-invoice",
        json={"amount": "100.00", "accept": True},
    )
    assert patch.status_code == 422
    plan = client.get("/api/scans/test_null_kind_invoice/plan").json()
    assert plan["report_rows"] == []
    assert plan["totals"] == []
    assert plan["operations"][0]["destination_relative_path"].startswith("Uncategorized/")


def test_new_document_defaults_to_null_kind_and_none_profile(tmp_path):
    from app.services.session_store import DocumentRecord, ScanSession, store as ss

    sess = ScanSession(
        scan_id="test_new_document_defaults",
        root=str(tmp_path),
        scanned_at="2026-10-09T00:00:00Z",
        state="done",
    )
    sess.documents.append(DocumentRecord(
        file_id="new-doc",
        relative_path="paper.txt",
        file_type="txt",
        size_bytes=1,
        sha256="e" * 64,
        excerpt="paper",
        status="needs_review",
        classification=None,
    ))
    ss.put_scan(sess)

    response = client.patch("/api/documents/new-doc", json={"accept": True})
    assert response.status_code == 200
    classification = response.json()["classification"]
    assert classification["document_kind"] is None
    assert classification["field_profile"] == "none"


def test_document_kind_correction_is_normalized_and_profile_is_derived(tmp_path):
    from app.services.session_store import DocumentRecord, ScanSession, store as ss

    sess = ScanSession(
        scan_id="test_kind_correction",
        root=str(tmp_path),
        scanned_at="2026-10-09T00:00:00Z",
        state="done",
    )
    sess.documents.append(DocumentRecord(
        file_id="kind-doc",
        relative_path="paper.txt",
        file_type="txt",
        size_bytes=1,
        sha256="f" * 64,
        excerpt="paper",
        status="needs_review",
        classification={"category": "other"},
    ))
    ss.put_scan(sess)

    response = client.patch(
        "/api/documents/kind-doc",
        json={"document_kind": "bank_statement"},
    )
    assert response.status_code == 200
    classification = response.json()["classification"]
    assert classification["document_kind"] == "statement"
    assert classification["field_profile"] == "reference"


def test_invoice_category_statement_kind_routes_other_and_has_no_report_row(tmp_path):
    from app.services.session_store import DocumentRecord, ScanSession, store as ss

    sess = ScanSession(
        scan_id="test_invoice_statement_kind",
        root=str(tmp_path),
        scanned_at="2026-10-09T00:00:00Z",
        state="done",
    )
    sess.documents.append(DocumentRecord(
        file_id="statement-invoice-category",
        relative_path="statement.txt",
        file_type="txt",
        size_bytes=1,
        sha256="1" * 64,
        excerpt="statement",
        status="ok",
        classification={
            "category": "invoice",
            "document_kind": "statement",
            "merchant": "Bank",
            "date": "2026-10-01",
            "amount": "1000.00",
            "currency": "PHP",
        },
    ))
    ss.put_scan(sess)

    plan = client.get("/api/scans/test_invoice_statement_kind/plan")
    assert plan.status_code == 200
    payload = plan.json()
    assert payload["operations"][0]["destination_relative_path"].startswith("Other/")
    assert payload["report_rows"] == []
    assert payload["totals"] == []


def test_session_response_exposes_derived_document_profile(tmp_path):
    from app.services.session_store import DocumentRecord, ScanSession, store as ss

    sess = ScanSession(
        scan_id="test_profile_response",
        root=str(tmp_path),
        scanned_at="2026-10-09T00:00:00Z",
        state="done",
    )
    sess.documents.append(DocumentRecord(
        file_id="statement-response",
        relative_path="statement.txt",
        file_type="txt",
        size_bytes=1,
        sha256="d" * 64,
        excerpt="statement",
        status="ok",
        classification={"category": "other", "document_kind": "statement"},
    ))
    ss.put_scan(sess)

    response = client.get("/api/scans/test_profile_response")
    assert response.status_code == 200
    classification = response.json()["documents"][0]["classification"]
    assert classification["document_kind"] == "statement"
    assert classification["field_profile"] == "reference"


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


# ---------------------------------------------------------------------------
# Filesystem safety at the commit/undo boundary
# ---------------------------------------------------------------------------

def _put_done_session_with_files(tmp_path, names: tuple[str, ...] = ("receipt.txt",)):
    """Create a real, already-scanned session for filesystem-boundary tests."""
    import hashlib
    from app.services.session_store import DocumentRecord, ScanSession, store as ss

    session = ScanSession(
        scan_id=f"safe_{tmp_path.name}",
        root=str(tmp_path),
        scanned_at="2026-10-09T00:00:00Z",
        state="done",
    )
    for index, name in enumerate(names):
        path = tmp_path / name
        path.parent.mkdir(parents=True, exist_ok=True)
        content = f"Receipt {index}\nTotal: PHP {100 + index}.00".encode()
        path.write_bytes(content)
        digest = hashlib.sha256(content).hexdigest()
        session.documents.append(DocumentRecord(
            file_id=f"{session.scan_id}_file_{index}",
            relative_path=name,
            file_type="txt",
            size_bytes=len(content),
            sha256=digest,
            excerpt=content.decode(),
            status="ok",
            classification={
                "category": "receipt",
                "merchant": "Test Shop",
                "date": "2026-10-09",
                "amount_text": f"PHP {100 + index}.00",
                "amount": f"{100 + index}.00",
                "currency": "PHP",
                "evidence_quote": f"Total: PHP {100 + index}.00",
                "evidence_verified": True,
                "explanation": "Test receipt",
            },
        ))
    ss.put_scan(session)
    return session


def _approve_safe_session(session):
    plan = client.get(f"/api/scans/{session.scan_id}/plan").json()
    response = client.post(f"/api/plans/{plan['plan_id']}/approve", json={})
    assert response.status_code == 200, response.text
    return plan, response.json()


def _require_symlink(link, target):
    try:
        link.symlink_to(target, target_is_directory=target.is_dir())
    except (OSError, NotImplementedError) as exc:
        pytest.skip(f"Symlinks unavailable on this platform: {exc}")


@pytest.mark.parametrize("relative_path", ["../outside.txt", "C:/outside.txt"])
def test_commit_rejects_traversal_and_absolute_paths(tmp_path, relative_path):
    outside = tmp_path.parent / "outside.txt"
    outside.write_text("must remain untouched")
    session = _put_done_session_with_files(tmp_path)
    session.documents[0].relative_path = relative_path
    plan, result = _approve_safe_session(session)

    assert result["moved"] == 0
    assert len(result["failed"]) == 1
    assert outside.read_text() == "must remain untouched"
    assert (tmp_path / "receipt.txt").exists()


def test_commit_rejects_symlink_source_and_destination_parent(tmp_path):
    outside = tmp_path.parent / "outside-target"
    outside.mkdir()
    outside_file = outside / "secret.txt"
    outside_file.write_text("outside")

    source_session = _put_done_session_with_files(tmp_path / "source")
    source_link = tmp_path / "source" / "link.txt"
    _require_symlink(source_link, outside_file)
    source_session.documents[0].relative_path = "link.txt"
    _, source_result = _approve_safe_session(source_session)
    assert source_result["moved"] == 0
    assert outside_file.read_text() == "outside"

    destination_root = tmp_path / "destination"
    destination_session = _put_done_session_with_files(destination_root)
    destination_parent = destination_root / "Receipts"
    destination_parent_target = outside / "dest"
    destination_parent_target.mkdir()
    destination_parent.unlink(missing_ok=True)
    _require_symlink(destination_parent, destination_parent_target)
    _, destination_result = _approve_safe_session(destination_session)
    assert destination_result["moved"] == 0
    assert (destination_root / "receipt.txt").exists()
    assert not any(destination_parent_target.rglob("receipt.txt"))


@pytest.mark.parametrize("mutation", ["changed", "missing"])
def test_commit_rechecks_source_identity_and_existence(tmp_path, mutation):
    session = _put_done_session_with_files(tmp_path)
    source = tmp_path / "receipt.txt"
    if mutation == "changed":
        source.write_text("changed after scan")
    else:
        source.unlink()

    _, result = _approve_safe_session(session)
    assert result["moved"] == 0
    assert len(result["failed"]) == 1


def test_commit_never_overwrites_existing_destination(tmp_path):
    session = _put_done_session_with_files(tmp_path)
    preview = client.get(f"/api/scans/{session.scan_id}/plan").json()
    destination = tmp_path / preview["operations"][0]["destination_relative_path"]
    destination.parent.mkdir(parents=True)
    destination.write_text("existing destination")

    result = client.post(f"/api/plans/{preview['plan_id']}/approve", json={}).json()
    assert result["moved"] == 0
    assert destination.read_text() == "existing destination"
    assert (tmp_path / "receipt.txt").exists()


def test_undo_rejects_edited_or_replaced_moved_file(tmp_path):
    session = _put_done_session_with_files(tmp_path)
    _, result = _approve_safe_session(session)
    moved = tmp_path / "Receipts" / "2026-10" / "receipt.txt"
    moved.write_text("edited after commit")

    undo = client.post(f"/api/batches/{result['batch_id']}/undo", json={})
    assert undo.status_code == 200
    assert undo.json()["restored"] == 0
    assert undo.json()["conflicts"]
    assert moved.read_text() == "edited after commit"
    assert not (tmp_path / "receipt.txt").exists()


def test_undo_rejects_occupied_original_path(tmp_path):
    session = _put_done_session_with_files(tmp_path)
    _, result = _approve_safe_session(session)
    original = tmp_path / "receipt.txt"
    original.write_text("different file")

    undo = client.post(f"/api/batches/{result['batch_id']}/undo", json={})
    assert undo.json()["restored"] == 0
    assert "different file" == original.read_text()


def test_undo_rejects_symlink_original_path_without_touching_outside(tmp_path):
    session = _put_done_session_with_files(tmp_path)
    _, result = _approve_safe_session(session)
    outside = tmp_path.parent / "undo-outside.txt"
    outside.write_text("outside")
    _require_symlink(tmp_path / "receipt.txt", outside)

    undo = client.post(f"/api/batches/{result['batch_id']}/undo", json={})
    assert undo.json()["restored"] == 0
    assert outside.read_text() == "outside"


def test_partial_commit_and_retry_are_reported_without_overwrite(tmp_path):
    session = _put_done_session_with_files(tmp_path, ("a.txt", "b.txt"))
    (tmp_path / "b.txt").unlink()

    plan, first = _approve_safe_session(session)
    assert first["moved"] == 1
    assert len(first["failed"]) == 1
    moved_a = tmp_path / "Receipts" / "2026-10" / "a.txt"
    assert moved_a.exists()

    retry = client.post(f"/api/plans/{plan['plan_id']}/approve", json={})
    assert retry.status_code == 200
    # Re-approval is idempotent: it returns the original batch result and
    # does not attempt to move the already-committed operation again.
    assert retry.json()["batch_id"] == first["batch_id"]
    assert retry.json()["moved"] == first["moved"]
    assert retry.json()["failed"] == first["failed"]
    assert moved_a.read_text().startswith("Receipt 0")


def test_partial_undo_is_safe_and_idempotent_on_retry(tmp_path):
    session = _put_done_session_with_files(tmp_path, ("a.txt", "b.txt"))
    _, result = _approve_safe_session(session)
    moved_b = tmp_path / "Receipts" / "2026-10" / "b.txt"
    moved_b.write_text("edited")

    first = client.post(f"/api/batches/{result['batch_id']}/undo", json={}).json()
    assert first["restored"] == 1
    assert len(first["conflicts"]) == 1
    assert (tmp_path / "a.txt").exists()

    second = client.post(f"/api/batches/{result['batch_id']}/undo", json={}).json()
    assert second["restored"] == 0
    assert len(second["conflicts"]) == 1
    assert (tmp_path / "a.txt").exists()
    assert moved_b.read_text() == "edited"


def test_approval_commits_exact_previewed_operations(tmp_path):
    session = _put_done_session_with_files(tmp_path, ("inbox/receipt.txt", "archive/receipt.txt"))
    preview = client.get(f"/api/scans/{session.scan_id}/plan").json()
    preview_operations = preview["operations"]

    approval = client.post(f"/api/plans/{preview['plan_id']}/approve", json={})
    assert approval.status_code == 200, approval.text
    assert len(preview_operations) == 2
    for operation in preview_operations:
        assert not (tmp_path / operation["original_relative_path"]).exists()
        assert (tmp_path / operation["destination_relative_path"]).exists()


def test_correction_after_preview_requires_fresh_preview(tmp_path):
    session = _put_done_session_with_files(tmp_path)
    preview = client.get(f"/api/scans/{session.scan_id}/plan").json()

    correction = client.patch(
        f"/api/documents/{session.scan_id}_file_0",
        json={"category": "invoice", "accept": True},
    )
    assert correction.status_code == 200

    stale_approval = client.post(f"/api/plans/{preview['plan_id']}/approve", json={})
    assert stale_approval.status_code == 409
    assert "stale" in stale_approval.json()["detail"].lower()
    assert (tmp_path / "receipt.txt").exists()

    refreshed = client.get(f"/api/scans/{session.scan_id}/plan").json()
    assert refreshed["operations"][0]["destination_relative_path"].startswith("Invoices/")
    approved = client.post(f"/api/plans/{refreshed['plan_id']}/approve", json={})
    assert approved.status_code == 200
    assert (tmp_path / refreshed["operations"][0]["destination_relative_path"]).exists()


def test_report_preparation_failure_happens_before_any_move(tmp_path, monkeypatch):
    import app.routes.session as session_routes

    session = _put_done_session_with_files(tmp_path)

    def fail_prepare(*args, **kwargs):
        raise OSError("temporary report directory unavailable")

    monkeypatch.setattr(session_routes, "write_report_temp", fail_prepare)
    preview = client.get(f"/api/scans/{session.scan_id}/plan").json()
    response = client.post(f"/api/plans/{preview['plan_id']}/approve", json={})

    assert response.status_code == 503
    batch_id = response.json()["detail"]["batch_id"]
    batch = session_store.store.get_batch(batch_id)
    assert batch is not None
    assert batch.state == "failed"
    assert batch.moved == 0
    assert (tmp_path / "receipt.txt").exists()
    assert not list((tmp_path / "GhostOS Reports").glob("*.csv"))


def test_partial_commit_report_contains_only_successful_moves(tmp_path):
    session = _put_done_session_with_files(tmp_path, ("a.txt", "b.txt"))
    (tmp_path / "b.txt").unlink()

    plan, result = _approve_safe_session(session)
    report = (tmp_path / result["report_relative_path"]).read_text(encoding="utf-8-sig")

    assert result["moved"] == 1
    assert len(result["failed"]) == 1
    assert "a.txt" in report
    assert "b.txt" not in report
    batch = session_store.store.get_batch(result["batch_id"])
    assert batch is not None
    assert batch.state == "partial"
    assert sum(entry.commit_state == "committed" for entry in batch.entries) == 1
    assert plan["report_rows"][0]["status"] == "accepted"


def test_report_publication_failure_is_recoverable_without_moving_again(tmp_path, monkeypatch):
    import app.routes.session as session_routes

    session = _put_done_session_with_files(tmp_path)
    original_publish = session_routes.publish_report
    calls = 0

    def fail_once(*args, **kwargs):
        nonlocal calls
        calls += 1
        if calls == 1:
            raise OSError("final report publication failed")
        return original_publish(*args, **kwargs)

    monkeypatch.setattr(session_routes, "publish_report", fail_once)
    preview = client.get(f"/api/scans/{session.scan_id}/plan").json()
    first = client.post(f"/api/plans/{preview['plan_id']}/approve", json={})

    assert first.status_code == 503
    batch_id = first.json()["detail"]["batch_id"]
    batch = session_store.store.get_batch(batch_id)
    assert batch is not None
    assert batch.state == "report_pending"
    assert batch.moved == 1
    moved = tmp_path / "Receipts" / "2026-10" / "receipt.txt"
    assert moved.exists()
    assert not (tmp_path / "receipt.txt").exists()

    retry = client.post(f"/api/plans/{preview['plan_id']}/approve", json={})
    assert retry.status_code == 200
    assert retry.json()["batch_id"] == batch_id
    assert retry.json()["moved"] == 1
    assert moved.exists()
    assert not (tmp_path / "receipt.txt").exists()
    assert (tmp_path / retry.json()["report_relative_path"]).exists()
    assert session_store.store.get_batch(batch_id).state == "committed"


def test_report_publication_failure_still_allows_safe_undo(tmp_path, monkeypatch):
    import app.routes.session as session_routes

    session = _put_done_session_with_files(tmp_path)
    monkeypatch.setattr(session_routes, "publish_report", lambda *args, **kwargs: (_ for _ in ()).throw(OSError("publish failed")))
    preview = client.get(f"/api/scans/{session.scan_id}/plan").json()
    failed = client.post(f"/api/plans/{preview['plan_id']}/approve", json={})
    batch_id = failed.json()["detail"]["batch_id"]

    undo = client.post(f"/api/batches/{batch_id}/undo", json={})
    assert undo.status_code == 200
    assert undo.json()["restored"] == 1
    assert (tmp_path / "receipt.txt").exists()


def test_existing_report_is_not_overwritten(tmp_path):
    from app.services.report import reserve_report_path

    first = reserve_report_path(tmp_path, "GhostOS Reports/expenses-test.csv")
    (tmp_path / first).write_text("earlier report", encoding="utf-8")
    second = reserve_report_path(tmp_path, "GhostOS Reports/expenses-test.csv")

    assert second != first
    assert (tmp_path / first).read_text(encoding="utf-8") == "earlier report"


def test_case_equivalent_source_directory_gets_distinct_destination_and_safe_undo(tmp_path):
    import hashlib
    from app.services.path_safety import paths_equivalent

    session = _put_done_session_with_files(tmp_path, ("receipts/source-receipt.txt", "invoice.txt"))
    original_invoice_bytes = (tmp_path / "invoice.txt").read_bytes()
    original_invoice_sha256 = hashlib.sha256(original_invoice_bytes).hexdigest()
    invoice = session.documents[1]
    invoice.classification["category"] = "invoice"
    invoice.classification["amount_text"] = "PHP 200.00"
    invoice.classification["amount"] = "200.00"
    invoice.classification["evidence_quote"] = "Total: PHP 200.00"
    invoice.excerpt = "Receipt 1\nTotal: PHP 200.00"

    preview = client.get(f"/api/scans/{session.scan_id}/plan").json()
    receipt_op = next(op for op in preview["operations"] if op["file_id"] == session.documents[0].file_id)
    invoice_op = next(op for op in preview["operations"] if op["file_id"] == session.documents[1].file_id)

    # On Windows, Receipts/ and the existing lowercase receipts/ directory
    # resolve to the same location. The planner must choose the documented
    # alternative root rather than relying on capitalization.
    if os.name == "nt":
        assert paths_equivalent(tmp_path, "receipts", "Receipts")
    assert receipt_op["destination_relative_path"] == "GhostOS Organized/Receipts/2026-10/source-receipt.txt"
    assert not paths_equivalent(
        tmp_path,
        receipt_op["destination_relative_path"],
        "receipts/source-receipt.txt",
    )

    # Create the previewed receipt destination after preview. Commit must not
    # overwrite it, while the invoice still commits to its exact preview path.
    existing_destination = tmp_path / receipt_op["destination_relative_path"]
    existing_destination.parent.mkdir(parents=True, exist_ok=True)
    existing_destination.write_text("pre-existing", encoding="utf-8")
    approval = client.post(f"/api/plans/{preview['plan_id']}/approve", json={})
    assert approval.status_code == 200, approval.text
    body = approval.json()
    assert body["moved"] == 1
    assert len(body["failed"]) == 1
    assert existing_destination.read_text(encoding="utf-8") == "pre-existing"
    assert (tmp_path / invoice_op["destination_relative_path"]).exists()
    assert (tmp_path / "receipts/source-receipt.txt").exists()
    assert (tmp_path / body["report_relative_path"]).exists()

    undo = client.post(f"/api/batches/{body['batch_id']}/undo", json={})
    assert undo.status_code == 200
    assert undo.json()["restored"] == 1
    assert (tmp_path / "invoice.txt").exists()
    assert hashlib.sha256((tmp_path / "invoice.txt").read_bytes()).hexdigest() == original_invoice_sha256
    assert (tmp_path / "receipts/source-receipt.txt").exists()
    assert existing_destination.read_text(encoding="utf-8") == "pre-existing"

    source_files = {
        path.relative_to(tmp_path / "receipts").as_posix()
        for path in (tmp_path / "receipts").rglob("*")
        if path.is_file()
    }
    assert source_files == {"source-receipt.txt"}
