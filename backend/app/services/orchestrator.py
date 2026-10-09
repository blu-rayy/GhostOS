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
import copy
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
    PlanSnapshot,
    ScanSession,
    SkippedFile,
    store,
)
from app.services.path_safety import (
    conflicts_with_source_directory,
    paths_equivalent,
    relative_path_key,
)
from app.services.extractor import process_file_content
from app.services import local_ai
from app.services.classification_validation import validate_classification
from app.services.operations import build_proposed_operation
from app.schemas import ClassificationRecord
from app.services.document_awareness import field_profile_for_classification

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
# Validator flag mapping (validator names -> frontend ReviewFlagCodes)
# ---------------------------------------------------------------------------

# Maps each flag emitted by classification_validation.validate_classification
# onto the shared API/frontend ReviewFlagCode. Three validator names differ
# from the frontend codes; the rest map 1:1. Flags unknown to this table pass
# through untouched (the frontend renders unrecognized codes under the
# document target) so validation information is never silently discarded.
_VALIDATOR_FLAG_MAP: dict[str, tuple[str, str]] = {
    "missing_evidence_quote": ("missing_evidence_quote", "No evidence quote was provided for verification"),
    "evidence_quote_not_found": ("evidence_not_found", "Evidence quote not found verbatim in the extracted text"),
    "missing_amount": ("missing_amount", "No amount found in the document"),
    "invalid_amount_format": ("amount_unparseable", "The amount could not be parsed as a decimal value"),
    "ambiguous_amount": ("amount_conflict", "Multiple conflicting amounts found; none was selected"),
    "invalid_currency": ("invalid_currency", "The currency code is not supported"),
    "missing_currency": ("missing_currency", "No currency found in the document"),
    "currency_mismatch": ("currency_mismatch", "The declared currency does not match the document"),
    "missing_merchant": ("missing_merchant", "No merchant found in the document"),
    "missing_date": ("missing_date", "No date found in the document"),
    "uncertain_classification": ("uncertain_classification", "The classification is uncertain and needs human review"),
    "quotation_document": ("quotation_document", "This document appears to be a quotation rather than a completed transaction."),
    "non_transactional_document": ("non_transactional_document", "This is not a transaction document and has no expense fields"),
    "transaction_fields_on_non_transactional": ("transaction_fields_on_non_transactional", "Transaction fields were reported for a non-transactional document"),
    "uncertain_document_kind": ("uncertain_document_kind", "The document kind could not be determined"),
}


def _map_validation_flags(validator_flags: tuple[str, ...]) -> list[dict]:
    """Map validator flag names onto API review-flag dicts without dropping any."""
    mapped: list[dict] = []
    for flag in validator_flags:
        if flag in _VALIDATOR_FLAG_MAP:
            code, message = _VALIDATOR_FLAG_MAP[flag]
            mapped.append({"code": code, "message": message})
        else:
            mapped.append({"code": flag, "message": f"Validation check reported: {flag}"})
    return mapped


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

def _source_directories(session: ScanSession) -> tuple[str, ...]:
    """Collect real source directories using the same root's path semantics."""
    directories: set[str] = set()
    root = Path(session.root).resolve(strict=False)

    if root.is_dir():
        for root_dir, child_dirs, _ in os.walk(root, followlinks=False):
            safe_child_dirs: list[str] = []
            for child in child_dirs:
                child_path = Path(root_dir) / child
                if child_path.is_symlink():
                    continue
                relative = child_path.relative_to(root).as_posix()
                directories.add(relative)
                safe_child_dirs.append(child)
            child_dirs[:] = safe_child_dirs

    # Keep the snapshot meaningful even for tests or callers that construct a
    # completed session without a real directory walk.
    for doc in session.documents:
        normalized = doc.relative_path.replace("\\", "/")
        parts = normalized.split("/")[:-1]
        if Path(normalized).is_absolute() or normalized.startswith(("/", "\\")) or ".." in parts:
            continue
        for index in range(1, len(parts) + 1):
            if parts[index - 1]:
                directories.add("/".join(parts[:index]))

    return tuple(sorted(directories))


def _safe_destination_folder(
    root: Path,
    folder: str,
    source_directories: tuple[str, ...],
) -> str:
    """Choose a deterministic organization folder outside scanned source dirs."""
    if not conflicts_with_source_directory(root, folder, source_directories):
        return folder

    # Keep the category/date layout, but move it beneath a distinct root. The
    # numeric suffix is deterministic if prior source folders use the first
    # alternative name too.
    for number in range(1, 1000):
        organization_root = "GhostOS Organized" if number == 1 else f"GhostOS Organized {number}"
        candidate = f"{organization_root}/{folder}"
        if not conflicts_with_source_directory(root, candidate, source_directories):
            return candidate
    raise ValueError(f"Could not choose a safe destination for {folder!r}")

def _build_plan(session: ScanSession) -> Plan:
    root = Path(session.root).resolve(strict=False)
    source_directories = _source_directories(session)
    taken: set[str] = set()
    operations: list[ProposedOp] = []
    report_rows: list[ReportRow] = []

    for doc in session.documents:
        c = doc.classification
        category = c.get("category") if c else None
        document_aware = bool(c and "document_kind" in c)
        field_profile = field_profile_for_classification(c) if c else "none"

        # Determine destination folder
        if not c or doc.status == "failed":
            folder = "Needs Review"
            reason = "Could not be classified"
        elif doc.status == "needs_review" and not doc.user_corrected:
            folder = "Needs Review"
            reason = "Waiting for human review"
        elif document_aware and field_profile != "transaction":
            folder = "Other"
            reason = "Non-transactional document"
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

        folder = _safe_destination_folder(root, folder, source_directories)

        filename = doc.relative_path.rsplit("/", maxsplit=1)[-1]
        dest = f"{folder}/{filename}"

        # Collision suffix
        n = 1
        while relative_path_key(root, dest) in taken or os.path.lexists(str(root / dest)):
            dot = filename.rfind(".")
            stem = filename[:dot] if dot > 0 else filename
            ext = filename[dot:] if dot > 0 else ""
            n += 1
            dest = f"{folder}/{stem} ({n}){ext}"
        taken.add(relative_path_key(root, dest))

        if not paths_equivalent(root, dest, doc.relative_path):
            operations.append(ProposedOp(
                file_id=doc.file_id,
                original_relative_path=doc.relative_path,
                destination_relative_path=dest,
                reason=reason,
                collision_suffixed=(n > 1),
            ))

        # Report rows require a transaction profile as well as an invoice or
        # receipt category. Statements and other non-transactional documents
        # must never become one expense merely because they contain amounts.
        if (
            c
            and category in ("invoice", "receipt")
            and field_profile == "transaction"
        ):
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

            # Classify, then run the source-aware validator on the result.
            classification: Optional[ClassificationRecord] = None
            classify_flags: list[dict] = []
            classify_status = "ok"
            parsed_amount: Optional[Decimal] = None

            if extraction_status == "success" and excerpt.strip():
                try:
                    result = local_ai.classify_excerpt(excerpt)
                    classification = result.classification
                    validation = validate_classification(excerpt, classification)
                    parsed_amount = validation.parsed_amount
                    classify_flags = _map_validation_flags(validation.flags)
                    # Prompt injection guard the validator does not cover:
                    # long evidence quotes are suspicious.
                    if classification.evidence_quote and len(classification.evidence_quote) > 200:
                        classify_flags.append({"code": "possible_injection", "message": "Evidence quote is unusually long; manual review recommended"})
                    if validation.needs_review or not validation.is_valid or classify_flags:
                        classify_status = "needs_review"
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

            # Serialize the validator's parsed Decimal as a string (or null).
            # The original amount_text is preserved verbatim in classification.
            amount = str(parsed_amount) if parsed_amount is not None else None

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
            if classification and classification.document_kind is not None:
                session.documents[-1].classification["document_kind"] = classification.document_kind
                session.documents[-1].classification["field_profile"] = classification.field_profile
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

    plan_id = f"plan_{scan_id}"
    existing = store.get_plan_snapshot(plan_id)
    if existing is not None and existing.session_revision == session.plan_revision:
        return copy.deepcopy(existing.plan)

    # A GET of the preview endpoint is the explicit request for a fresh
    # preview after a correction or other session revision.
    plan = _build_plan(session)
    source_directories = _source_directories(session)
    identities = tuple(
        sorted(
            (
                op.file_id,
                (
                    next((d.relative_path for d in session.documents if d.file_id == op.file_id), ""),
                    next((d.sha256 for d in session.documents if d.file_id == op.file_id), ""),
                ),
            )
            for op in plan.operations
        )
    )
    store.put_plan_snapshot(
        plan_id,
        PlanSnapshot(
            plan=copy.deepcopy(plan),
            session_revision=session.plan_revision,
            source_identities=identities,
            source_directories=source_directories,
        ),
    )
    return copy.deepcopy(plan)
