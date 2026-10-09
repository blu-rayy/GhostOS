# Uncategorized destination retest: contract and test plan

**Owner:** Developer 4 (QA) · **Commit:** `0dfdb65` ("standardize uncategorized destinations") · **Status:** Stage 1 (inspection) and Stage 2 (setup) done. **No scan, approval or file move yet.**

## Inspected contract (from code and Developer 1's tests, not assumed)

| Item | Actual contract | Source |
|---|---|---|
| Modes | `SortMode = "blocking" \| "partial"`; anything else → 422 | `schemas.py:21`; `test_invalid_sort_mode_returns_422` |
| Preview | `GET /api/scans/{scan_id}/plan?mode=blocking\|partial` (default `blocking`); the response includes `"mode"` | `session.py:398-437` |
| Snapshot | One snapshot per `plan_id` (`plan_<scan_id>`). A preview in a different mode **replaces** it, and an approval for the old mode is rejected | `orchestrator.get_plan`; `test_new_mode_preview_supersedes_old_snapshot_and_rejects_old_approval` |
| Approve | `POST /api/plans/{plan_id}/approve`, body `{"mode": "..."}` (`ApprovalRequest`; omitted body or mode = `blocking`). **The mode must equal the previewed snapshot's mode, otherwise 409** | `session.py:444-470` |
| Blocking mode | 409 `Plan has N unresolved review items` while any document is `needs_review` and not user-corrected | `session.py:501` |
| **Partial mode** | **No blocking check.** The plan still contains an operation for **every** document, so **unresolved documents are moved too, into `Uncategorized/`**, not left in place. Unresolved documents get **no report row** | `orchestrator._build_plan:248-256`; test asserts `moved == 1` for an unresolved document |
| Destinations | `Uncategorized/`: failed or unclassified, unresolved review, invoice/receipt without a date, uncertain category. `Other/`: decided non-transactional or `other`. `Invoices|Receipts/YYYY-MM/` for dated transactions. A clash with a source folder → `GhostOS Organized/…` | `orchestrator._build_plan:194-221` |
| `Unsorted/` | Not used by any production code. It survives only in one test's name and local variable | `git grep` |
| Report | Rows only for `invoice`/`receipt` with profile `transaction`; accepted only when date, amount, currency, status ok and not a duplicate; the CSV holds committed, accepted rows only | `orchestrator`, `session._committed_report_rows` |
| UI | **No partial-mode control in the frontend.** Partial mode is API-only | `git grep partial frontend/src` |

## Disposable roots (created; see `setup/manifest.json`)

Base `<TEST_BASE>` = `%LOCALAPPDATA%\Temp\ghostos-uncategorized` (new). Each root uses a **unique top-level folder** (`inbox-a/`, `inbox-b/`) so no `file_id` can collide with another scan (D1 workaround). The outside-root canary is `<TEST_BASE>/outside-canary/canary.txt`.

### A-normal (blocking mode; no successful approval planned)

| File | Fixture | Purpose |
|---|---|---|
| `inbox-a/receipts/sunbeam-cafe-receipt.pdf` | receipt | clear transaction |
| `inbox-a/identity/birth-certificate.pdf` | identity_or_civil | non-transactional, undecided |
| `inbox-a/receipts/bayside-office-mart.pdf` | receipt with conflicting totals | unresolved review |
| `inbox-a/misc/aircon-payment-note.txt` | uncertain note | uncertain or missing-date case |
| `inbox-a/scans/empty-scan.txt` | **synthetic 0-byte file** | unreadable / no text |

### B-partial (partial mode; one approve + undo)

| File | Purpose |
|---|---|
| `inbox-b/receipts/sunbeam-cafe-receipt.pdf` | transaction 1 (PHP 683.20) |
| `inbox-b/receipts/tibay-hardware-receipt.csv` | transaction 2 (PHP 2,145.00) |
| `inbox-b/identity/drivers-license-record.txt` | non-transactional, **decided "File it"** (needs your confirmation) |
| `inbox-b/legal/lease-agreement-summary.pdf` | non-transactional, **left undecided** |
| `inbox-b/receipts/bayside-office-mart.pdf` | unresolved review |

## Planned steps

### Stage 3: A-normal (read-only plus rejected approvals)

| ID | Step | Expected |
|---|---|---|
| N1 | Scan, `GET /scans/{id}`, `GET plan` (blocking) | Receipt → `Receipts/2026-09/`; birth certificate, Bayside, aircon note, empty file → **`Uncategorized/`**; birth certificate has no report row; review flags visible |
| N2 | `GET plan?mode=partial` (read-only comparison), then `GET plan` (blocking) again | Same destinations; partial drops unresolved report rows; the final snapshot is blocking |
| N3 | `POST approve {}`, **only if** the snapshot is blocking with `blocking_review_count > 0` | **409 unresolved review items**; folder unchanged |
| N4 | `POST approve {"mode":"partial"}` against the blocking snapshot | **409 mode mismatch**; folder unchanged (*an approval request: needs your OK*) |
| N5 | Fingerprint and canary | identical to setup |

### Stage 4: B-partial (one approve + undo, after a second confirmation)

| ID | Step | Expected |
|---|---|---|
| P1 | Scan and check classifications | Transactions `ok`; if a transaction is flagged, **stop and report** |
| P2 | Driver's licence decision `PATCH {"category":"other","accept":true}` (the UI's "File it") | 200 (*a user decision: needs your OK*) |
| P3 | `GET plan?mode=partial` | Sunbeam and Tibay → `Receipts/2026-09/`; licence → **`Other/`**; lease and Bayside → **`Uncategorized/`**; report rows: 2 accepted; totals **PHP 2,828.20**; `blocking_review_count = 2` |
| P4 | Show the exact plan → **your confirmation** → `POST approve {"mode":"partial"}` | 200; 5 moved, 0 failed |
| P5 | Verify | Exact-case destinations and hashes; nothing overwritten; no `Unsorted/`; canary and root A unchanged; CSV has 2 rows; totals recomputed from the CSV = PHP 2,828.20 |
| P6 | Undo with the returned `batch_id` | 5 restored; original paths and hashes; leftover CSV and empty folders recorded separately; no organized files under `inbox-b/` |

Still NOT TESTED or kept separate: symlinks (WinError 1314), D1 (separate open defect; avoided by unique paths), offline. F1 stays closed.
