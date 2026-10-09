"""In-memory session store for GhostOS scan sessions, plans, and batches.

All state is process-scoped (lost on server restart). This is intentional
for the MVP — persistence is deferred to a later phase.
"""

from __future__ import annotations

import threading
import uuid
from dataclasses import dataclass, field
from typing import Optional

from app.schemas import ClassifyResponse


def new_id(prefix: str) -> str:
    return f"{prefix}_{uuid.uuid4().hex[:12]}"


# ---------------------------------------------------------------------------
# Scan session
# ---------------------------------------------------------------------------

@dataclass
class SkippedFile:
    relative_path: str
    reason: str
    detail: str


@dataclass
class DocumentRecord:
    file_id: str
    relative_path: str
    file_type: str
    size_bytes: int
    sha256: str
    excerpt: str
    status: str  # 'ok' | 'needs_review' | 'failed'
    classification: Optional[dict] = None
    review_flags: list = field(default_factory=list)
    duplicate_of: Optional[str] = None
    user_corrected: bool = False


@dataclass
class ScanSession:
    scan_id: str
    root: str
    scanned_at: str
    state: str = "running"   # 'running' | 'done' | 'error'
    files_total: int = 0
    files_processed: int = 0
    current_file: Optional[str] = None
    error: Optional[str] = None
    documents: list[DocumentRecord] = field(default_factory=list)
    skipped: list[SkippedFile] = field(default_factory=list)
    files_seen: int = 0
    max_files: int = 100


# ---------------------------------------------------------------------------
# Plan
# ---------------------------------------------------------------------------

@dataclass
class ProposedOp:
    file_id: str
    original_relative_path: str
    destination_relative_path: str
    reason: str
    collision_suffixed: bool = False


@dataclass
class ReportRow:
    file_id: str
    source_filename: str
    category: str
    date: Optional[str]
    merchant: Optional[str]
    amount: Optional[str]
    currency: Optional[str]
    status: str  # 'accepted' | 'needs_review'


@dataclass
class CurrencyTotal:
    currency: str
    amount: str
    row_count: int


@dataclass
class Plan:
    plan_id: str
    scan_id: str
    operations: list[ProposedOp]
    report_rows: list[ReportRow]
    totals: list[CurrencyTotal]
    blocking_review_count: int


# ---------------------------------------------------------------------------
# Batch (committed operations for undo)
# ---------------------------------------------------------------------------

@dataclass
class BatchEntry:
    file_id: str
    original_path: str   # absolute
    moved_to: str        # absolute


@dataclass
class Batch:
    batch_id: str
    plan_id: str
    entries: list[BatchEntry]
    report_relative_path: str
    committed_at: str


# ---------------------------------------------------------------------------
# Thread-safe store
# ---------------------------------------------------------------------------

class SessionStore:
    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._scans: dict[str, ScanSession] = {}
        self._batches: dict[str, Batch] = {}

    # scans
    def put_scan(self, session: ScanSession) -> None:
        with self._lock:
            self._scans[session.scan_id] = session

    def get_scan(self, scan_id: str) -> Optional[ScanSession]:
        with self._lock:
            return self._scans.get(scan_id)

    def find_document(self, file_id: str) -> Optional[DocumentRecord]:
        with self._lock:
            for session in self._scans.values():
                for doc in session.documents:
                    if doc.file_id == file_id:
                        return doc
        return None

    # batches
    def put_batch(self, batch: Batch) -> None:
        with self._lock:
            self._batches[batch.batch_id] = batch

    def get_batch(self, batch_id: str) -> Optional[Batch]:
        with self._lock:
            return self._batches.get(batch_id)


# Singleton store shared across the FastAPI process
store = SessionStore()
