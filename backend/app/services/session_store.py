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
    plan_revision: int = 0


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


@dataclass(frozen=True)
class PlanSnapshot:
    """The exact preview payload and source identities approved by the user."""

    plan: Plan
    session_revision: int
    source_identities: tuple[tuple[str, tuple[str, str]], ...]


# ---------------------------------------------------------------------------
# Batch (committed operations for undo)
# ---------------------------------------------------------------------------

@dataclass
class BatchEntry:
    file_id: str
    original_path: str   # absolute
    moved_to: str        # absolute
    # Relative paths and identity are retained so undo can revalidate the
    # original selected root instead of trusting stale absolute paths.
    original_relative_path: str = ""
    moved_relative_path: str = ""
    sha256: str = ""
    commit_state: str = "planned"
    undo_state: str = "pending"
    error: str | None = None


@dataclass
class Batch:
    batch_id: str
    plan_id: str
    entries: list[BatchEntry]
    report_relative_path: str
    committed_at: str
    root_path: str = ""
    moved: int = 0
    failed: list[dict] = field(default_factory=list)
    state: str = "preparing"  # preparing | committing | report_pending | committed | partial | failed | undone
    report_state: str = "pending"  # pending | prepared | published | failed
    report_temp_relative_path: str | None = None
    report_error: str | None = None


# ---------------------------------------------------------------------------
# Thread-safe store
# ---------------------------------------------------------------------------

class SessionStore:
    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._scans: dict[str, ScanSession] = {}
        self._batches: dict[str, Batch] = {}
        self._plan_snapshots: dict[str, PlanSnapshot] = {}

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

    def bump_revision_for_document(self, file_id: str) -> bool:
        """Invalidate existing previews after a document correction."""
        with self._lock:
            for session in self._scans.values():
                if any(doc.file_id == file_id for doc in session.documents):
                    session.plan_revision += 1
                    return True
        return False

    # plan snapshots
    def put_plan_snapshot(self, plan_id: str, snapshot: PlanSnapshot) -> None:
        with self._lock:
            self._plan_snapshots[plan_id] = snapshot

    def get_plan_snapshot(self, plan_id: str) -> Optional[PlanSnapshot]:
        with self._lock:
            return self._plan_snapshots.get(plan_id)

    # batches
    def put_batch(self, batch: Batch) -> None:
        with self._lock:
            self._batches[batch.batch_id] = batch

    def get_batch(self, batch_id: str) -> Optional[Batch]:
        with self._lock:
            return self._batches.get(batch_id)

    def get_batch_for_plan(self, plan_id: str) -> Optional[Batch]:
        with self._lock:
            return next((batch for batch in self._batches.values() if batch.plan_id == plan_id), None)


# Singleton store shared across the FastAPI process
store = SessionStore()
