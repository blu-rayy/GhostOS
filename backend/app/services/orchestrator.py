"""Scan orchestrator: runs in a background thread per scan session.

Responsibilities:
  1. Walk the root folder (via scanner.scan_folder logic)
  2. For each file: extract text + hash (extractor)
  3. Classify each excerpt with Ollama (local_ai)
  4. Build and validate the DocumentRecord
  5. Update session state so the progress endpoint stays current
"""

from __future__ import annotations

import os
import threading
from datetime import datetime, timezone
from decimal import Decimal, InvalidOperation
from pathlib import Path
from typing import Optional

from app.services.session_store import (
    Batch,
    BatchEntry,
    CurrencyTotal,
    DocumentRecord,
    Plan,
    ProposedOp,
    ReportRow,
    ScanSession,
    SkippedFile,
    store,
)
from app.services.extractor import process_file_content
from app.services import local_ai
from app.services.operations import build_proposed_operation
from app.schemas import ClassificationRecord

SUPPORTED_EXTENSIONS = {".pdf", ".txt", ".csv"}
MAX_FILES = 100
MAX_FILE_SIZE = 10 * 1024 * 1024  # 10 MB

_CATEGORY_FOLDER = {
    "invoice": "Invoices",
    "receipt": "Receipts",
    "other": "Other",
}

# ---------------------------------------------------------------------------
# Evidence verification
# ---------------------------------------------------------------------------

def _verify_evidence(excerpt: str, evidence_quote: Optional[str]) -> bool:
    if not evidence_quote:
        return False
    return evidence_quote in excerpt


# ---------------------------------------------------------------------------
# Review flag logic
# ---------------------------------------------------------------------------

def _compute_review_flags(
    classification: ClassificationRecord,
    excerpt: str,
    extraction_status: str,
) -> list[dict]:
    flags = []

    if extraction_status in ("error", "empty"):
        flags.append({"code": "model_error", "message": "Text extraction failed or produced no content"})
        return flags

    if classification.category in ("invoice", "receipt"):
        if not classification.date:
            flags.append({"code": "missing_date", "message": "No date found in the document"})
        if not classification.amount_text:
            flags.append({"code": "missing_amount", "message": "No amount found in the document"})

    if classification.evidence_quote and not _verify_evidence(excerpt, classification.evidence_quote):
        flags.append({"code": "evidence_not_found", "message": "Evidence quote not found verbatim in the extracted text"})

    # Prompt injection guard: long evidence quotes are suspicious
    if classification.evidence_quote and len(classification.evidence_quote) > 200:
        flags.append({"code": "possible_injection", "message": "Evidence quote is unusually long; manual review recommended"})

    return flags


# ---------------------------------------------------------------------------
# Amount parsing
# ---------------------------------------------------------------------------

def _parse_amount(amount_text: Optional[str]) -> Optional[str]:
    """Extract a decimal amount string from raw amount_text. Returns None on failure."""
    if not amount_text:
        return None
    import re
    # Strip currency symbols and whitespace, keep digits/commas/periods
    cleaned = re.sub(r"[^\d.,]", "", amount_text.replace(",", "."))
    # If multiple periods, keep only the last segment
    parts = cleaned.split(".")
    if len(parts) > 2:
        cleaned = "".join(parts[:-1]) + "." + parts[-1]
    try:
        return str(Decimal(cleaned))
    except InvalidOperation:
        return None


# ---------------------------------------------------------------------------
# Plan builder (backend-owned destination rules)
# ---------------------------------------------------------------------------

def _build_plan(session: ScanSession) -> Plan:
    taken: set[str] = set()
    operations: list[ProposedOp] = []
    report_rows: list[ReportRow] = []

    for doc in session.documents:
        c = doc.classification
        category = c.get("category") if c else None

        # Determine destination folder
        if not c or doc.status == "failed":
            folder = "Needs Review"
            reason = "Could not be classified"
        elif doc.status == "needs_review" and not doc.user_corrected:
            folder = "Needs Review"
            reason = "Waiting for human review"
        elif category in ("invoice", "receipt"):
            date = c.get("date")
            if not date:
                folder = "Needs Review"
                reason = f"{category} without a date"
            else:
                top = _CATEGORY_FOLDER.get(category, "Other")
                month = date[:7]
                folder = f"{top}/{month}"
                reason = f"{category} dated {date}"
        elif category == "other":
            folder = "Other"
            reason = "Not an invoice or receipt"
        else:
            folder = "Needs Review"
            reason = "Category uncertain"

        filename = doc.relative_path.rsplit("/", maxsplit=1)[-1]
        dest = f"{folder}/{filename}"

        # Collision suffix
        n = 1
        base_dest = dest
        while dest.lower() in taken:
            dot = filename.rfind(".")
            stem = filename[:dot] if dot > 0 else filename
            ext = filename[dot:] if dot > 0 else ""
            n += 1
            dest = f"{folder}/{stem} ({n}){ext}"
        taken.add(dest.lower())

        if dest != doc.relative_path:
            operations.append(ProposedOp(
                file_id=doc.file_id,
                original_relative_path=doc.relative_path,
                destination_relative_path=dest,
                reason=reason,
                collision_suffixed=(n > 1),
            ))

        # Report rows for invoices and receipts only
        if c and category in ("invoice", "receipt"):
            # Prefer the canonical `amount` field (set by the scan worker and by
            # human corrections). Fall back to re-parsing `amount_text` only when
            # no canonical amount exists, so corrected amounts are never ignored.
            amount = c.get("amount") or _parse_amount(c.get("amount_text"))
            duplicate = doc.duplicate_of is not None
            accepted = (
                c.get("date") is not None
                and amount is not None
                and c.get("currency") is not None
                and doc.status == "ok"
                and not duplicate
            )
            report_rows.append(ReportRow(
                file_id=doc.file_id,
                source_filename=doc.relative_path,
                category=category,
                date=c.get("date"),
                merchant=c.get("merchant"),
                amount=amount,
                currency=c.get("currency"),
                status="accepted" if accepted else "needs_review",
            ))

    # Currency totals
    by_currency: dict[str, list[Decimal]] = {}
    for row in report_rows:
        if row.status == "accepted" and row.currency and row.amount:
            try:
                by_currency.setdefault(row.currency, []).append(Decimal(row.amount))
            except InvalidOperation:
                pass

    totals = [
        CurrencyTotal(
            currency=cur,
            amount=str(sum(amounts)),
            row_count=len(amounts),
        )
        for cur, amounts in by_currency.items()
    ]

    blocking = sum(
        1 for d in session.documents
        if d.status == "needs_review" and not d.user_corrected
    )

    return Plan(
        plan_id=f"plan_{session.scan_id}",
        scan_id=session.scan_id,
        operations=operations,
        report_rows=report_rows,
        totals=totals,
        blocking_review_count=blocking,
    )


# ---------------------------------------------------------------------------
# Scan worker (background thread)
# ---------------------------------------------------------------------------

def _run_scan(session: ScanSession) -> None:
    """Background worker: scan → extract → classify → update session."""
    root = Path(session.root)
    seen_hashes: dict[str, str] = {}  # sha256 → file_id (for duplicate detection)

    try:
        files_to_process: list[tuple[Path, str, str]] = []  # (path, rel_path, ext)

        for root_dir, dirs, files in os.walk(root, followlinks=False):
            for file in files:
                file_path = Path(root_dir) / file
                ext = file_path.suffix.lower()

                if file_path.is_symlink():
                    session.skipped.append(SkippedFile(
                        relative_path=str(file_path.relative_to(root).as_posix()),
                        reason="symlink",
                        detail="Symlinked files are skipped for safety",
                    ))
                    continue

                if ext not in SUPPORTED_EXTENSIONS:
                    session.skipped.append(SkippedFile(
                        relative_path=file_path.relative_to(root).as_posix(),
                        reason="unsupported_type",
                        detail=f"Extension '{ext}' is not supported",
                    ))
                    continue

                try:
                    stat = file_path.stat()
                except OSError:
                    session.skipped.append(SkippedFile(
                        relative_path=file_path.relative_to(root).as_posix(),
                        reason="unreadable",
                        detail="Could not read file metadata",
                    ))
                    continue

                if stat.st_size > MAX_FILE_SIZE:
                    session.skipped.append(SkippedFile(
                        relative_path=file_path.relative_to(root).as_posix(),
                        reason="too_large",
                        detail=f"File is {stat.st_size} bytes (limit is {MAX_FILE_SIZE})",
                    ))
                    continue

                if len(files_to_process) >= MAX_FILES:
                    session.skipped.append(SkippedFile(
                        relative_path=file_path.relative_to(root).as_posix(),
                        reason="file_limit_reached",
                        detail=f"Limit of {MAX_FILES} files reached",
                    ))
                    continue

                rel_path = file_path.relative_to(root).as_posix()
                files_to_process.append((file_path, rel_path, ext))

        session.files_total = len(files_to_process)
        session.files_seen = session.files_total + len(session.skipped)
        store.put_scan(session)

        for file_path, rel_path, ext in files_to_process:
            session.current_file = rel_path
            store.put_scan(session)

            # Generate stable file ID
            import hashlib as _hashlib
            file_id = _hashlib.md5(rel_path.encode()).hexdigest()[:8]
            file_type = ext.lstrip(".")

            # Extract text + hash
            sha256, extraction_status, excerpt, extract_reason = process_file_content(file_path, ext)

            if sha256 is None:
                session.documents.append(DocumentRecord(
                    file_id=file_id,
                    relative_path=rel_path,
                    file_type=file_type,
                    size_bytes=file_path.stat().st_size,
                    sha256="",
                    excerpt="",
                    status="failed",
                    review_flags=[{"code": "model_error", "message": extract_reason or "Hashing failed"}],
                ))
                session.files_processed += 1
                store.put_scan(session)
                continue

            # Duplicate detection
            duplicate_of = seen_hashes.get(sha256)
            if duplicate_of:
                pass  # informational only, still classify
            else:
                seen_hashes[sha256] = file_id

            # Classify
            classification: Optional[ClassificationRecord] = None
            classify_flags: list[dict] = []
            classify_status = "ok"

            if extraction_status == "success" and excerpt.strip():
                try:
                    result = local_ai.classify_excerpt(excerpt)
                    classification = result.classification
                    flags = _compute_review_flags(classification, excerpt, extraction_status)
                    classify_flags = flags
                    classify_status = "needs_review" if flags else "ok"
                except local_ai.LocalAIValidationError as e:
                    classify_status = "needs_review"
                    classify_flags = [{"code": "model_error", "message": str(e)}]
                    classification = ClassificationRecord(category="uncertain", explanation=str(e))
                except (local_ai.LocalAIUnavailableError, local_ai.LocalAITimeoutError) as e:
                    classify_status = "failed"
                    classify_flags = [{"code": "model_error", "message": f"Ollama unavailable: {e}"}]
                except local_ai.LocalAIError as e:
                    classify_status = "needs_review"
                    classify_flags = [{"code": "model_error", "message": str(e)}]
            elif extraction_status in ("empty", "skipped"):
                classify_status = "needs_review"
                classify_flags = [{"code": "model_error", "message": extract_reason or "No extractable text"}]
            else:
                classify_status = "failed"
                classify_flags = [{"code": "model_error", "message": extract_reason or "Extraction failed"}]

            amount = _parse_amount(classification.amount_text) if classification else None

            session.documents.append(DocumentRecord(
                file_id=file_id,
                relative_path=rel_path,
                file_type=file_type,
                size_bytes=file_path.stat().st_size,
                sha256=sha256,
                excerpt=excerpt,
                status=classify_status,
                classification={
                    "category": classification.category,
                    "merchant": classification.merchant,
                    "date": classification.date,
                    "amount_text": classification.amount_text,
                    "amount": amount,
                    "currency": classification.currency,
                    "evidence_quote": classification.evidence_quote,
                    "evidence_verified": _verify_evidence(excerpt, classification.evidence_quote),
                    "explanation": classification.explanation or "",
                } if classification else None,
                review_flags=classify_flags,
                duplicate_of=duplicate_of,
            ))
            session.files_processed += 1
            store.put_scan(session)

        session.state = "done"
        session.current_file = None

    except Exception as e:
        session.state = "error"
        session.error = str(e)
        session.current_file = None

    finally:
        store.put_scan(session)


def start_scan_async(scan_id: str, root: str) -> ScanSession:
    """Create a session, persist it, launch the background worker, return immediately."""
    session = ScanSession(
        scan_id=scan_id,
        root=root,
        scanned_at=datetime.now(timezone.utc).isoformat(),
    )
    store.put_scan(session)
    t = threading.Thread(target=_run_scan, args=(session,), daemon=True)
    t.start()
    return session


def get_plan(scan_id: str) -> Plan:
    session = store.get_scan(scan_id)
    if session is None:
        raise KeyError(f"Scan {scan_id!r} not found")
    return _build_plan(session)
