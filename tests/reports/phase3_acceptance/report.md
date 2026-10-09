# Phase 3 acceptance test: safe commit, report and undo

**Owner:** Developer 4 (QA) · **Run:** 2026-10-10 (UTC 2026-10-09 17:1x) · **Commit:** `01e660c` (`main`) · **Status: PASS with findings**

This was a controlled run of the **real** backend: an unmodified FastAPI process with `qwen3:4b-instruct` on Ollama. It used disposable copies of synthetic fixtures. No production code was changed, no Git operation was run, and nothing was deleted. Each check below was observed directly; checks that could not be observed are marked **NOT TESTED**.

## Summary

| Area | Result |
|---|---|
| Approval refused while a review is unresolved (root A) | **PASS** (409, no file changed) |
| Stale preview refused after a correction (root A) | **PASS** (409 "Plan is stale", no file changed) |
| Scan and preview are read-only (A and B) | **PASS** |
| Approve: 5 files committed, 0 failed, nothing outside root B touched | **PASS** |
| Name collision gets a distinct, non-overwriting destination | **PASS** (`invoice (2).pdf`) |
| CSV contains only committed, accepted rows; rows and totals match the ground truth | **PASS** (4 rows; PHP 5,439.70, USD 59.88) |
| Undo restores all 5 originals byte for byte | **PASS** (restored 5, 0 conflicts) |
| Files land exactly at the paths shown in the preview | **FAIL** on folder-name case: see **F1** |
| UI screenshots | **NOT TESTED** (browser automation deferred; manual capture pending) |
| Report-publication failure (HTTP 503) and recovery | **NOT TESTED** |
| Symlink escape | **NOT TESTED** (WinError 1314: Developer Mode off) |
| Restart and recovery of in-memory batch state | **NOT TESTED** (state is in memory by design) |

## Environment

| | |
|---|---|
| OS | Windows 11 Pro 10.0.26200, NTFS (case-insensitive, case-preserving) |
| Backend | `uvicorn app.main:app` on 127.0.0.1:8000, **one process for the whole run** (PID 27416, a single start in the server log) |
| Model | `qwen3:4b-instruct` via Ollama 0.40.2 at 127.0.0.1:11434; `/api/status` reported `external_requests: 0` |
| Backend tests (re-run by QA before the test) | 140 passed, 2 skipped (both symlink tests, WinError 1314); `test_session.py` 29 passed, 2 skipped |
| Network | Not disconnected for this run (offline behaviour is not part of Phase 3) |
| Test base `<TEST_BASE>` | `%LOCALAPPDATA%\Temp\ghostos-phase3\`, created fresh (the setup refuses to run if it exists) and outside the repository |
| Roots | `<TEST_BASE>/A-blocker` (Stage 3) · `<TEST_BASE>/B-acceptance` (Stage 4) · `<TEST_BASE>/outside-canary/canary.txt` (outside-root write detector) |

Paths in the JSON evidence are redacted to `<ROOT_A>`, `<ROOT_B>` and `<TEST_BASE>`.

## Inputs (byte-for-byte copies of `tests/fixtures/sample_folder`)

| Root | File | SHA-256 (first 16) | Ground truth |
|---|---|---|---|
| A | `receipts/bayside-office-mart.pdf` | `3b11f36ab288c9fc` | receipt, PHP, **amount null, review required** (contradictory totals) |
| A | `receipts/tibay-hardware-receipt.csv` | `5cc008a23a59b8b2` | receipt, 2026-09-27, PHP 2,145.00 |
| B | `inbox/invoice.pdf` | `d34d23a313745851` | invoice, Brightline, 2026-09-03, **USD 59.88**, collision `COLLIDE-1` |
| B | `archive/2026/invoice.pdf` | `0bec9fe8f9669399` | invoice, Carabao, 2026-09-18, **PHP 3,470.00**, collision `COLLIDE-1` |
| B | `receipts/sunbeam-cafe-receipt.pdf` | `aab1c6fe32a7f119` | receipt, 2026-09-21, **PHP 683.20** (subtotal 610.00 must not be used) |
| B | `receipts/greenleaf-grocer-2026-09-14.txt` | `165d4ac5289f2d4c` | receipt, 2026-09-14, **PHP 1,286.50**, duplicate `DUP-1` |
| B | `downloads/greenleaf-grocer-2026-09-14 (1).txt` | `165d4ac5289f2d4c` | byte-identical copy of the line above |

Full hashes are in [`00_setup_manifest.json`](00_setup_manifest.json).

## Stage 3: unresolved-review blocker (root A, `scan_7dbfcd940270`)

Model result: Bayside `needs_review` with `amount_conflict` and amount null; Tibay `ok` at PHP 2,145.00. `blocking_review_count = 1`.

| # | Check | Expected | Actual | Result |
|---|---|---|---|---|
| A1 | Scan is read-only | tree and hashes unchanged | unchanged | **PASS** |
| A2 | Preview is read-only | unchanged | unchanged | **PASS** |
| A3 | Approve with an open review | 409, no change | `409 {"detail":"Plan has 1 unresolved review items"}`, unchanged | **PASS** |
| A4 | Correction that does not accept (`{"merchant":"BAYSIDE OFFICE MART","accept":false}`) | 200, stays `needs_review` | 200, `needs_review`, `user_corrected:false` | **PASS** |
| A5 | Approve the **pre-correction** snapshot | 409 stale, no change | `409 {"detail":"Plan is stale; refresh the preview before approval"}`, unchanged | **PASS** |
| A6 | Fresh preview after that correction | still blocked | `blocking_review_count = 1` (not approved) | **PASS** |
| A7 | Root A and canary at the end | unchanged | unchanged | **PASS** |
| A8 | Blocked state in the UI | screenshot | — | **NOT TESTED** |

**Requirement confirmed:** any `PATCH /api/documents/{id}` makes the stored preview stale. A fresh `GET /api/scans/{id}/plan` is required before approval. Nothing was accepted, approved or moved in root A.

Evidence: `A_01_http_log.json`, `A_02_scan_result.json`, `A_03_plan_snapshot1.json`, `A_03b_plan_snapshot2_after_correction.json`, `A_04_patch_response.json`, `A_05_fingerprints.json`, `A_06_results.json`.

## Stage 4: approve, report and undo (root B, `scan_bf77c62ddde8` → `plan_scan_bf77c62ddde8` → `batch_5744f571110c`)

All 5 classifications matched the ground truth (category, date, amount, currency), and **none was flagged**, so no correction was needed or made. The preview was shown to and approved by a human before the approve call.

### Pre-approval checks (all passed; the approve call is guarded by them)

P1 plan ID unchanged · P2 plan JSON identical to the human-approved snapshot · P3 exactly 5 operations · P4 `blocking_review_count = 0` · P5 the 5 originals still match the setup hashes · P6 every destination is relative, inside root B and does not exist · P7 canary unchanged.

### Approve

`POST /api/plans/plan_scan_bf77c62ddde8/approve` →
```json
HTTP 200
{"batch_id": "batch_5744f571110c", "moved": 5, "failed": [],
 "report_relative_path": "GhostOS Reports/expenses-202610091720.csv",
 "committed_at": "2026-10-09T17:20:49.734944+00:00"}
```

| # | Check | Result | Notes |
|---|---|---|---|
| S1 | Approval succeeds | **PASS** | HTTP 200, `batch_id` returned |
| S2 | 5 committed, 0 failed | **PASS** | |
| S3 | Each file at its planned destination with unchanged SHA-256 | **FAIL** as written; **PASS** under Windows path semantics | Hashes 5/5 correct, sources removed. The 3 receipt files are at `receipts/2026-09/…`, not the previewed `Receipts/2026-09/…` (see F1) |
| S4 | Collision handled without overwrite | **PASS** | `Invoices/2026-09/invoice.pdf` = archive bytes; `Invoices/2026-09/invoice (2).pdf` = inbox bytes |
| S5 | Duplicate pair: both moved, neither deleted | **FAIL** as written; **PASS** under Windows path semantics | Both copies present with original bytes, under `receipts/2026-09/` (F1) |
| S6 | No unexpected files | **FAIL** as written; **PASS** under Windows path semantics | Only the 5 moved files and the report |
| S7 | No temporary report file left | **PASS** | |
| S8 | Nothing outside root B touched | **PASS** | `<TEST_BASE>` still holds only `A-blocker`, `B-acceptance`, `outside-canary`; A and canary hashes unchanged |

The case-insensitive re-check reads only the tree snapshot taken immediately after approval ([`B_10_case_insensitive_reverification.json`](B_10_case_insensitive_reverification.json)):

| Planned (preview) | Actually on disk | SHA-256 |
|---|---|---|
| `Invoices/2026-09/invoice.pdf` | `Invoices/2026-09/invoice.pdf` | ✓ |
| `Invoices/2026-09/invoice (2).pdf` | `Invoices/2026-09/invoice (2).pdf` | ✓ |
| `Receipts/2026-09/greenleaf-grocer-2026-09-14 (1).txt` | `receipts/2026-09/greenleaf-grocer-2026-09-14 (1).txt` | ✓ |
| `Receipts/2026-09/greenleaf-grocer-2026-09-14.txt` | `receipts/2026-09/greenleaf-grocer-2026-09-14.txt` | ✓ |
| `Receipts/2026-09/sunbeam-cafe-receipt.pdf` | `receipts/2026-09/sunbeam-cafe-receipt.pdf` | ✓ |

### Expense report CSV

`GhostOS Reports/expenses-202610091720.csv` (byte copy: [`B_07_report_copy.csv`](B_07_report_copy.csv)). UTF-8 BOM, CRLF line endings:

```
source_file,merchant,date,category,amount,currency
archive/2026/invoice.pdf,CARABAO PAPER SUPPLY CO.,2026-09-18,invoice,3470.00,PHP
downloads/greenleaf-grocer-2026-09-14 (1).txt,GREENLEAF GROCER - Sample Branch (fictional),2026-09-14,receipt,1286.50,PHP
inbox/invoice.pdf,BRIGHTLINE WEB HOSTING LLC,2026-09-03,invoice,59.88,USD
receipts/sunbeam-cafe-receipt.pdf,SUNBEAM CAFE,2026-09-21,receipt,683.20,PHP
```

| # | Check | Expected | Actual | Result |
|---|---|---|---|---|
| S9 | Report inside root B at the returned path | yes | yes | **PASS** |
| S10 | Format | BOM, CRLF, 6-column header | as expected | **PASS** |
| S11 | Committed, accepted rows only | 4 rows (see the sources above) | 4, same sources | **PASS** |
| S12 | Row values match the ground truth | date, category, amount, currency | all match | **PASS** |
| S13 | Totals: CSV = independent ground truth = plan | PHP **5,439.70** (3,470.00 + 1,286.50 + 683.20), USD **59.88** | CSV PHP 5,439.70 / USD 59.88; plan the same | **PASS** |
| S14 | Duplicate copy excluded | one Greenleaf row | only `downloads/…(1).txt` | **PASS** (behaviour as implemented; see F3) |

**Why the duplicate is excluded (from the source code):**
1. The scanner walks folders in alphabetical order, so `downloads/…(1).txt` is seen first.
2. `receipts/greenleaf-…txt` is then marked `duplicate_of` it.
3. `orchestrator._build_plan` marks a report row `accepted` only when `duplicate_of is None`, so the copy's row becomes `needs_review`. It does not block approval.
4. The writer (`session.py: _committed_report_rows` plus `report.to_csv`) emits only rows that were both committed and accepted.

Both files were still moved and neither was deleted, consistent with "duplicate detection is informational".

### Undo

`POST /api/batches/batch_5744f571110c/undo` → `HTTP 200 {"batch_id":"batch_5744f571110c","restored":5,"conflicts":[]}`

| # | Check | Result | Observed |
|---|---|---|---|
| U1 | Undo succeeds with no conflicts | **PASS** | restored 5, conflicts `[]` |
| U2 | All 5 original paths restored with original SHA-256 | **PASS** | 5/5 identical to `00_setup_manifest.json` |
| U3 | Files left after undo (observed) | recorded | `GhostOS Reports/expenses-202610091720.csv` **remains** |
| U4 | Empty folders left after undo (observed) | recorded | `Invoices/2026-09` (inside the new `Invoices/`) and **`receipts/2026-09` inside the user's own `receipts/` folder** remain |
| U5 | Root A and canary after undo | **PASS** | unchanged |

**Hashes: original vs restored**

| Original path | Setup | After undo |
|---|---|---|
| `inbox/invoice.pdf` | `d34d23a313745851…` | identical |
| `archive/2026/invoice.pdf` | `0bec9fe8f9669399…` | identical |
| `receipts/sunbeam-cafe-receipt.pdf` | `aab1c6fe32a7f119…` | identical |
| `receipts/greenleaf-grocer-2026-09-14.txt` | `165d4ac5289f2d4c…` | identical |
| `downloads/greenleaf-grocer-2026-09-14 (1).txt` | `165d4ac5289f2d4c…` | identical |

Evidence: `B_00_fingerprint_before.json`, `B_01_http_log_preview.json`, `B_02_scan_result.json`, `B_03_plan_snapshot_for_approval.json`, `B_04_http_log_execute.json`, `B_05_tree_before_approve.json`, `B_05b_tree_after_approve.json`, `B_05c_tree_after_undo.json`, `B_06_approve_response.json`, `B_07_report_copy.csv`, `B_08_undo_response.json`, `B_09_results.json`, `B_10_case_insensitive_reverification.json`.

## Findings and defects

| # | Severity | Component | Finding | Evidence |
|---|---|---|---|---|
| **F1** | **Medium** | Backend plan builder and approve (`orchestrator._build_plan`, `session.approve_plan` → `dst.parent.mkdir`) | **The preview's category folder can silently merge into an existing folder that differs only in case.** On Windows (case-insensitive), the planned `Receipts/2026-09/` resolved to the user's existing `receipts/` folder. The 3 receipt files were organized **inside the source folder** as `receipts/2026-09/…`, so the result differs from what the user approved. Undo then leaves an empty `receipts/2026-09/` inside the user's folder. No data was lost or overwritten (destination-existence checks are case-insensitive on NTFS). Suggested fix: detect case-insensitive clashes with existing folders when planning, and show or resolve them in the preview. | S3/S5/S6, B_10 |
| **D1** | **High (open)** | `session_store.find_document`, `bump_revision_for_document` | Still searches **every scan** by `file_id = md5(relative_path)`, so a correction after a re-scan of the same layout in one backend process edits the old scan and bumps the wrong revision. **Not triggered in this run**: roots A and B had no shared paths and the backend was fresh. The code is unchanged, so it stays open. | code review |
| F2 | Low | Undo | Undo leaves the report CSV and the created empty folders (`Invoices/2026-09`, `receipts/2026-09`) behind. The batch state never becomes `undone`. These are observed behaviours to document for users or to decide on. | U3, U4 |
| F3 | Decision | Report contract | (a) The CSV has **no row status or generated-timestamp column**, and rows that are not accepted are omitted. The build plan asks for "a generated timestamp and a row status such as accepted or needs review". (b) Which duplicate copy is kept depends on folder walk order; here it was the `(1)` download, not the original `receipts/` file. (c) The excluded duplicate is labelled `needs_review` but never blocks approval and gets no CSV row, which is invisible to the user. | S11, S14 |
| F4 | Low (code observation) | Undo | Undo does not check `commit_state`, so an entry that **failed** to move would come back as an undo "conflict". Not exercised (0 failures). | code review |
| F5 | Low (code observation) | `/api/status` | `model_loaded` is hard-coded to `true` and doesn't check Ollama. Not exercised. | code review |

## Not tested and limitations

- **UI screenshots (A8 and the Stage 4 screens):** not captured. Browser automation was deferred by request. To capture manually, use the UI's "try the demo files" with a typed path to a **fresh** copy. Do not correct documents in the UI for a layout the API has already scanned in the same backend process (D1).
- **Report publication failure (HTTP 503 with `batch_id`) and retry:** not induced. Doing so safely would need fault injection (e.g. a read-only `GhostOS Reports` folder), which was out of scope for this run. Covered only by the developer's unit tests.
- **Symlink escape (commit and undo):** **NOT TESTED**. Symlink creation fails with WinError 1314 (Developer Mode off); the two backend symlink tests are skipped for the same reason.
- **In-memory recovery:** scans, snapshots and batches live in process memory. A restart between approve and undo would lose the batch. Not tested, and the backend was kept running throughout.
- **Not transactional:** moves are individual `shutil.move` calls with a pre-recorded manifest; a crash mid-batch was not simulated.
- **Model variability:** one run. All 5 root-B files classified correctly here; this is not an accuracy claim.
- **Network:** online during the run; offline operation is a separate test.

## Reproduce

From the repository root, with the backend running as **one fresh process** on 127.0.0.1:8000 and Ollama serving `qwen3:4b-instruct`. The scripts are in [`scripts/`](scripts/); edit the absolute paths at the top of each for your machine.

```powershell
backend\.venv\Scripts\python.exe tests\reports\phase3_acceptance\scripts\setup_phase3.py      # refuses if the base or report folder exists
backend\.venv\Scripts\python.exe tests\reports\phase3_acceptance\scripts\stage3_blocker.py    # root A: only ever requests approval when it must be refused
backend\.venv\Scripts\python.exe tests\reports\phase3_acceptance\scripts\stage4_preview.py    # root B: scan + preview only; human reviews the plan
backend\.venv\Scripts\python.exe tests\reports\phase3_acceptance\scripts\stage4_execute.py    # pre-checks -> approve -> verify -> undo -> verify (plan ID hard-coded)
backend\.venv\Scripts\python.exe tests\reports\phase3_acceptance\scripts\reverify_case.py     # case-insensitive re-check from saved evidence
```

Test folders were left in place for inspection (`<TEST_BASE>`). Nothing was deleted automatically.
