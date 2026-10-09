"""All session-based routes: status, scan sessions, documents, plans, batches."""

from __future__ import annotations

import shutil
from datetime import datetime, timezone
from pathlib import Path
import hashlib
import os
import stat

from fastapi import APIRouter, HTTPException

from app.services.session_store import Batch, BatchEntry, new_id, store
from app.services.orchestrator import get_plan, start_scan_async
from app.services.report import (
    discard_report_reservation,
    publish_report,
    render_report,
    reserve_report_path,
    write_report_temp,
)
from app.services.path_safety import conflicts_with_source_directory


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _safe_root(root: Path) -> Path:
    """Resolve and validate the selected root for a filesystem operation."""
    if root.is_symlink():
        raise ValueError("Selected root is a symlink")
    resolved = root.resolve(strict=True)
    if not resolved.is_dir():
        raise ValueError("Selected root is not a directory")
    return resolved


def _safe_relative_path(root: Path, relative_path: str, *, require_exists: bool) -> Path:
    """Resolve a plan path without allowing traversal or symlink escapes."""
    if not relative_path:
        raise ValueError("Path is empty")

    candidate_input = Path(relative_path)
    if candidate_input.is_absolute() or ".." in candidate_input.parts:
        raise ValueError("Absolute or traversal path is not allowed")

    candidate = root / candidate_input
    resolved = candidate.resolve(strict=require_exists)
    try:
        resolved.relative_to(root)
    except ValueError as exc:
        raise ValueError("Path escapes the selected root") from exc

    # Check every existing component, including the leaf. This catches a
    # dangling symlink as well as a symlink whose target is inside the root.
    current = root
    for part in candidate_input.parts:
        current = current / part
        if os.path.lexists(str(current)) and current.is_symlink():
            raise ValueError("Symlink path components are not allowed")

    if require_exists:
        if not candidate.is_file() or not stat.S_ISREG(candidate.stat().st_mode):
            raise ValueError("Source is not a regular file")
    return candidate


def _safe_destination(
    root: Path,
    relative_path: str,
    source_directories: tuple[str, ...] = (),
) -> Path:
    """Validate a not-yet-existing destination and its existing parents."""
    if conflicts_with_source_directory(root, relative_path, source_directories):
        raise ValueError("Destination is inside a scanned source directory")
    destination = _safe_relative_path(root, relative_path, require_exists=False)
    if os.path.lexists(str(destination)):
        raise ValueError("Destination already exists")
    return destination


def _batch_response(batch: Batch) -> dict:
    return {
        "batch_id": batch.batch_id,
        "moved": batch.moved,
        "failed": batch.failed,
        "report_relative_path": batch.report_relative_path,
        "committed_at": batch.committed_at,
    }


def _committed_report_rows(batch: Batch, snapshot) -> list:
    committed_ids = {
        entry.file_id
        for entry in batch.entries
        if entry.commit_state == "committed"
    }
    return [
        row
        for row in snapshot.plan.report_rows
        if row.file_id in committed_ids and row.status == "accepted"
    ]


def _publish_batch_report(root: Path, batch: Batch, snapshot) -> None:
    """Publish only committed accepted rows; raise while retaining batch state."""
    if batch.report_state == "published":
        return
    if not batch.report_temp_relative_path:
        raise ValueError("Batch has no temporary report path")

    content = render_report(_committed_report_rows(batch, snapshot))
    write_report_temp(root, batch.report_temp_relative_path, content)
    publish_report(root, batch.report_temp_relative_path, batch.report_relative_path)
    batch.report_state = "published"
    batch.report_error = None
    batch.state = "partial" if batch.failed else "committed"
    store.put_batch(batch)

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

    # Any correction invalidates the previously displayed organization plan.
    store.bump_revision_for_document(file_id)

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

    snapshot = store.get_plan_snapshot(plan_id)
    if snapshot is None:
        raise HTTPException(status_code=409, detail="Plan preview is required before approval")
    if snapshot.session_revision != session.plan_revision:
        raise HTTPException(status_code=409, detail="Plan is stale; refresh the preview before approval")

    # Approval is idempotent for a published or partial batch. A pending report
    # is retried without moving any already-committed files.
    existing_batch = store.get_batch_for_plan(plan_id)
    if existing_batch is not None:
        if existing_batch.report_state == "published":
            return _batch_response(existing_batch)
        if existing_batch.state == "report_pending":
            try:
                root = _safe_root(Path(existing_batch.root_path))
                _publish_batch_report(root, existing_batch, snapshot)
                return _batch_response(existing_batch)
            except Exception as exc:
                existing_batch.report_error = str(exc)
                existing_batch.state = "report_pending"
                existing_batch.report_state = "pending"
                store.put_batch(existing_batch)
                raise HTTPException(
                    status_code=503,
                    detail={"batch_id": existing_batch.batch_id, "message": f"Report publication pending: {exc}"},
                ) from exc
        raise HTTPException(
            status_code=409,
            detail={"batch_id": existing_batch.batch_id, "message": "Approval is already recorded but the batch is not publishable"},
        )

    plan = snapshot.plan

    if plan.blocking_review_count > 0:
        raise HTTPException(
            status_code=409,
            detail=f"Plan has {plan.blocking_review_count} unresolved review items",
        )

    try:
        root = _safe_root(Path(session.root))
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    batch_id = new_id("batch")
    source_identities = dict(snapshot.source_identities)
    entries: list[BatchEntry] = []
    for op in plan.operations:
        expected_identity = source_identities.get(op.file_id)
        expected_sha256 = expected_identity[1] if expected_identity else ""
        entries.append(BatchEntry(
            file_id=op.file_id,
            original_path=str(root / op.original_relative_path),
            moved_to=str(root / op.destination_relative_path),
            original_relative_path=op.original_relative_path,
            moved_relative_path=op.destination_relative_path,
            sha256=expected_sha256,
        ))

    committed_at = datetime.now(timezone.utc).isoformat()
    stamp = committed_at[:16].replace("-", "").replace(":", "").replace("T", "")
    preferred_report_path = f"GhostOS Reports/expenses-{stamp}.csv"
    temp_report_path = f"GhostOS Reports/.{batch_id}.csv.tmp"
    batch = Batch(
        batch_id=batch_id,
        plan_id=plan_id,
        entries=entries,
        report_relative_path=preferred_report_path,
        committed_at=committed_at,
        root_path=str(root),
        report_temp_relative_path=temp_report_path,
        state="preparing",
    )
    # Persist the recovery manifest before any move or report publication.
    store.put_batch(batch)

    try:
        batch.report_relative_path = reserve_report_path(root, preferred_report_path)
        # Pre-render and fsync valid CSV content before touching source files.
        write_report_temp(root, temp_report_path, render_report(plan.report_rows))
        batch.report_state = "prepared"
        store.put_batch(batch)
    except Exception as exc:
        try:
            discard_report_reservation(root, temp_report_path, batch.report_relative_path)
        except Exception:
            pass
        batch.state = "failed"
        batch.report_state = "failed"
        batch.report_error = str(exc)
        store.put_batch(batch)
        raise HTTPException(
            status_code=503,
            detail={"batch_id": batch_id, "message": f"Report preparation failed: {exc}"},
        ) from exc

    batch.state = "committing"
    store.put_batch(batch)

    for op, entry in zip(plan.operations, entries):
        try:
            # Revalidate every operation at the filesystem boundary. The plan
            # is only a preview; files and directories may have changed since
            # it was generated.
            src = _safe_relative_path(root, op.original_relative_path, require_exists=True)
            dst = _safe_destination(root, op.destination_relative_path, snapshot.source_directories)

            expected_sha256 = entry.sha256
            if not expected_sha256:
                raise ValueError("No scanned file identity is available")
            actual_sha256 = _sha256(src)
            if actual_sha256 != expected_sha256:
                raise ValueError("Source file changed since scanning")

            dst.parent.mkdir(parents=True, exist_ok=True)
            # A parent could have been replaced between validation and mkdir.
            src = _safe_relative_path(root, op.original_relative_path, require_exists=True)
            dst = _safe_destination(root, op.destination_relative_path, snapshot.source_directories)
            shutil.move(str(src), str(dst))
            entry.original_path = str(src)
            entry.moved_to = str(dst)
            entry.commit_state = "committed"
            entry.error = None
            batch.moved += 1
            store.put_batch(batch)
        except Exception as e:
            entry.commit_state = "failed"
            entry.error = str(e)
            batch.failed.append({"file_id": op.file_id, "error": str(e)})
            store.put_batch(batch)

    try:
        _publish_batch_report(root, batch, snapshot)
    except Exception as exc:
        batch.state = "report_pending"
        batch.report_state = "pending"
        batch.report_error = str(exc)
        store.put_batch(batch)
        raise HTTPException(
            status_code=503,
            detail={"batch_id": batch_id, "message": f"Report publication pending: {exc}"},
        ) from exc

    return _batch_response(batch)


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

    try:
        root = _safe_root(Path(batch.root_path))
    except (ValueError, OSError) as exc:
        return {
            "batch_id": batch_id,
            "restored": 0,
            "conflicts": [
                {"file_id": entry.file_id, "relative_path": entry.original_relative_path or entry.original_path, "reason": str(exc)}
                for entry in batch.entries
                if entry.undo_state != "restored"
            ],
        }

    for entry in reversed(batch.entries):
        if entry.undo_state == "restored":
            continue
        try:
            moved_relative = entry.moved_relative_path
            original_relative = entry.original_relative_path
            if not moved_relative or not original_relative or not entry.sha256:
                raise ValueError("Batch entry lacks safe identity metadata")

            src = _safe_relative_path(root, moved_relative, require_exists=True)
            dst = _safe_relative_path(root, original_relative, require_exists=False)
            if os.path.lexists(str(dst)):
                raise ValueError("A different file now exists at the original path")
            if _sha256(src) != entry.sha256:
                raise ValueError("Moved file changed since commit")

            dst.parent.mkdir(parents=True, exist_ok=True)
            # Revalidate after creating parents and immediately before move.
            src = _safe_relative_path(root, moved_relative, require_exists=True)
            dst = _safe_relative_path(root, original_relative, require_exists=False)
            if os.path.lexists(str(dst)):
                raise ValueError("A different file now exists at the original path")
            if _sha256(src) != entry.sha256:
                raise ValueError("Moved file changed since commit")

            shutil.move(str(src), str(dst))
            entry.undo_state = "restored"
            restored += 1
        except FileNotFoundError:
            conflicts.append({
                "file_id": entry.file_id,
                "relative_path": entry.original_relative_path or entry.original_path,
                "reason": "File is no longer at its organized location",
            })
        except Exception as e:
            conflicts.append({
                "file_id": entry.file_id,
                "relative_path": entry.original_relative_path or entry.original_path,
                "reason": str(e),
            })

    return {
        "batch_id": batch_id,
        "restored": restored,
        "conflicts": conflicts,
    }
