"""All session-based routes: status, scan sessions, documents, plans, batches."""

from __future__ import annotations

import shutil
from datetime import datetime, timezone
from pathlib import Path

from fastapi import APIRouter, HTTPException

from app.services.session_store import Batch, BatchEntry, new_id, store
from app.services.orchestrator import get_plan, start_scan_async
from app.services.report import write_report

router = APIRouter(prefix="/api", tags=["session"])

BASE_OLLAMA = "http://127.0.0.1:11434"
BASE_BACKEND = "http://127.0.0.1:8000"
MODEL_NAME = "qwen3:4b-instruct"

_external_request_count = 0  # stays 0 for the MVP (loopback only)
_last_inference_ms: float | None = None
_last_inference_at: str | None = None


# ---------------------------------------------------------------------------
# Status
# ---------------------------------------------------------------------------

@router.get("/status")
def get_status() -> dict:
    """System health endpoint. Returns model and endpoint info."""
    return {
        "backend_endpoint": BASE_BACKEND,
        "model_name": MODEL_NAME,
        "model_endpoint": BASE_OLLAMA,
        "model_loaded": True,  # If Ollama is up and responding, treat as loaded
        "external_requests": _external_request_count,
        "last_inference_ms": _last_inference_ms,
        "last_inference_at": _last_inference_at,
    }


# ---------------------------------------------------------------------------
# Scan
# ---------------------------------------------------------------------------

@router.post("/scan")
def start_scan(body: dict) -> dict:
    """Start a background scan. Returns ScanProgress immediately."""
    root = body.get("root", "")
    if not root:
        raise HTTPException(status_code=422, detail="'root' field is required")

    root_path = Path(root)
    if root_path.is_symlink():
        raise HTTPException(status_code=400, detail="Symlinked roots are not allowed")
    try:
        resolved = root_path.resolve(strict=True)
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid or inaccessible root folder")
    if not resolved.is_dir():
        raise HTTPException(status_code=400, detail="Root path must be a directory")

    scan_id = new_id("scan")
    session = start_scan_async(scan_id, root)

    return {
        "scan_id": session.scan_id,
        "state": session.state,
        "files_total": session.files_total,
        "files_processed": session.files_processed,
        "current_file": session.current_file,
        "error": session.error,
    }


@router.get("/scans/{scan_id}/progress")
def get_scan_progress(scan_id: str) -> dict:
    session = store.get_scan(scan_id)
    if session is None:
        raise HTTPException(status_code=404, detail=f"Scan {scan_id!r} not found")
    return {
        "scan_id": session.scan_id,
        "state": session.state,
        "files_total": session.files_total,
        "files_processed": session.files_processed,
        "current_file": session.current_file,
        "error": session.error,
    }


@router.get("/scans/{scan_id}")
def get_scan(scan_id: str) -> dict:
    session = store.get_scan(scan_id)
    if session is None:
        raise HTTPException(status_code=404, detail=f"Scan {scan_id!r} not found")
    if session.state != "done":
        raise HTTPException(status_code=409, detail="Scan is not yet complete")
    return {
        "scan_id": session.scan_id,
        "root": session.root,
        "scanned_at": session.scanned_at,
        "files_seen": session.files_seen,
        "max_files": session.max_files,
        "documents": [
            {
                "file_id": d.file_id,
                "relative_path": d.relative_path,
                "file_type": d.file_type,
                "size_bytes": d.size_bytes,
                "sha256": d.sha256,
                "excerpt": d.excerpt,
                "status": d.status,
                "classification": d.classification,
                "review_flags": d.review_flags,
                "duplicate_of": d.duplicate_of,
                "user_corrected": d.user_corrected,
            }
            for d in session.documents
        ],
        "skipped": [
            {
                "relative_path": s.relative_path,
                "reason": s.reason,
                "detail": s.detail,
            }
            for s in session.skipped
        ],
    }


# ---------------------------------------------------------------------------
# Document correction
# ---------------------------------------------------------------------------

@router.patch("/documents/{file_id}")
def correct_document(file_id: str, body: dict) -> dict:
    """Apply a human correction to a document record."""
    doc = store.find_document(file_id)
    if doc is None:
        raise HTTPException(status_code=404, detail=f"Document {file_id!r} not found")

    # Apply the correction fields
    if doc.classification is None:
        doc.classification = {
            "category": "uncertain",
            "merchant": None,
            "date": None,
            "amount_text": None,
            "amount": None,
            "currency": None,
            "evidence_quote": None,
            "evidence_verified": False,
            "explanation": "Entered manually",
        }

    for field in ("category", "merchant", "date", "amount", "currency"):
        if field in body:
            doc.classification[field] = body[field]

    if body.get("accept"):
        doc.user_corrected = True
        doc.review_flags = []
        doc.status = "ok"

    return {
        "file_id": doc.file_id,
        "relative_path": doc.relative_path,
        "file_type": doc.file_type,
        "size_bytes": doc.size_bytes,
        "sha256": doc.sha256,
        "excerpt": doc.excerpt,
        "status": doc.status,
        "classification": doc.classification,
        "review_flags": doc.review_flags,
        "duplicate_of": doc.duplicate_of,
        "user_corrected": doc.user_corrected,
    }


# ---------------------------------------------------------------------------
# Plan
# ---------------------------------------------------------------------------

@router.get("/scans/{scan_id}/plan")
def get_scan_plan(scan_id: str) -> dict:
    try:
        plan = get_plan(scan_id)
    except KeyError as e:
        raise HTTPException(status_code=404, detail=str(e))

    return {
        "plan_id": plan.plan_id,
        "scan_id": plan.scan_id,
        "operations": [
            {
                "file_id": op.file_id,
                "original_relative_path": op.original_relative_path,
                "destination_relative_path": op.destination_relative_path,
                "reason": op.reason,
                "collision_suffixed": op.collision_suffixed,
            }
            for op in plan.operations
        ],
        "report_rows": [
            {
                "file_id": r.file_id,
                "source_filename": r.source_filename,
                "category": r.category,
                "date": r.date,
                "merchant": r.merchant,
                "amount": r.amount,
                "currency": r.currency,
                "status": r.status,
            }
            for r in plan.report_rows
        ],
        "totals": [
            {"currency": t.currency, "amount": t.amount, "row_count": t.row_count}
            for t in plan.totals
        ],
        "blocking_review_count": plan.blocking_review_count,
    }


# ---------------------------------------------------------------------------
# Approve plan (physically move files)
# ---------------------------------------------------------------------------

@router.post("/plans/{plan_id}/approve")
def approve_plan(plan_id: str) -> dict:
    # plan_id is deterministic: "plan_<scan_id>" (see orchestrator._build_plan).
    prefix = "plan_"
    if not plan_id.startswith(prefix):
        raise HTTPException(status_code=404, detail=f"Plan {plan_id!r} not found")

    scan_id = plan_id[len(prefix):]
    session = store.get_scan(scan_id)
    if session is None or session.state != "done":
        raise HTTPException(status_code=404, detail=f"Plan {plan_id!r} not found")

    plan = get_plan(scan_id)

    if plan.blocking_review_count > 0:
        raise HTTPException(
            status_code=409,
            detail=f"Plan has {plan.blocking_review_count} unresolved review items",
        )

    root = Path(session.root)
    batch_id = new_id("batch")
    entries: list[BatchEntry] = []
    failed: list[dict] = []
    moved = 0

    for op in plan.operations:
        src = root / op.original_relative_path
        dst = root / op.destination_relative_path
        try:
            dst.parent.mkdir(parents=True, exist_ok=True)
            shutil.move(str(src), str(dst))
            entries.append(BatchEntry(
                file_id=op.file_id,
                original_path=str(src),
                moved_to=str(dst),
            ))
            moved += 1
        except Exception as e:
            failed.append({"file_id": op.file_id, "error": str(e)})

    committed_at = datetime.now(timezone.utc).isoformat()
    stamp = committed_at[:16].replace("-", "").replace(":", "").replace("T", "")
    report_path = f"GhostOS Reports/expenses-{stamp}.csv"

    # Write the expense CSV (accepted rows only) relative to the scan root.
    write_report(root, report_path, plan.report_rows)

    batch = Batch(
        batch_id=batch_id,
        plan_id=plan_id,
        entries=entries,
        report_relative_path=report_path,
        committed_at=committed_at,
    )
    store.put_batch(batch)

    return {
        "batch_id": batch_id,
        "moved": moved,
        "failed": failed,
        "report_relative_path": report_path,
        "committed_at": committed_at,
    }


# ---------------------------------------------------------------------------
# Undo batch
# ---------------------------------------------------------------------------

@router.post("/batches/{batch_id}/undo")
def undo_batch(batch_id: str) -> dict:
    batch = store.get_batch(batch_id)
    if batch is None:
        raise HTTPException(status_code=404, detail=f"Batch {batch_id!r} not found")

    restored = 0
    conflicts: list[dict] = []

    for entry in reversed(batch.entries):
        src = Path(entry.moved_to)
        dst = Path(entry.original_path)
        try:
            if not src.exists():
                conflicts.append({
                    "file_id": entry.file_id,
                    "relative_path": entry.original_path,
                    "reason": "File is no longer at its organized location",
                })
                continue
            if dst.exists():
                conflicts.append({
                    "file_id": entry.file_id,
                    "relative_path": entry.original_path,
                    "reason": "A different file now exists at the original path",
                })
                continue
            dst.parent.mkdir(parents=True, exist_ok=True)
            shutil.move(str(src), str(dst))
            restored += 1
        except Exception as e:
            conflicts.append({
                "file_id": entry.file_id,
                "relative_path": entry.original_path,
                "reason": str(e),
            })

    return {
        "batch_id": batch_id,
        "restored": restored,
        "conflicts": conflicts,
    }
