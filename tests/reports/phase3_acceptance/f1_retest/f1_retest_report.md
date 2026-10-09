# F1 retest: Windows case-insensitive destination mismatch

**Owner:** Developer 4 (QA) · **Run:** 2026-10-10 (UTC 2026-10-09 17:55) · **Commit:** `2dfc7dc` (`main`, contains `92ea278` "Fix Windows destination path collisions") · **Result: F1 FIXED (all checks PASS)**

This is an independent retest of finding **F1** from the [original Phase 3 acceptance report](../report.md). That report and its evidence are kept unchanged as the historical record of the failure: checks S3, S5 and S6 originally failed because the planned `Receipts/2026-09/` was organized into the user's existing lowercase `receipts/` folder.

## What changed in the backend

`backend/app/services/path_safety.py` (new) and `orchestrator._build_plan`:
- When planning, the backend collects every scanned source directory. If a category folder would fall inside one of them (compared as Windows compares paths, ignoring case), the folder is moved under **`GhostOS Organized/`**.
- Collision suffixes also account for files already on disk.
- At approval, `session._safe_destination` rejects any destination inside a source directory recorded in the plan snapshot.

## Environment

| | |
|---|---|
| OS | Windows 11 Pro 10.0.26200, NTFS (case-insensitive, case-preserving) |
| Backend | One uvicorn process for the whole retest, PID 11920. The server log shows exactly: `POST /api/scan` 200 → `POST /api/plans/plan_scan_28419f4558ec/approve` 200 → `POST /api/batches/batch_72e59374531a/undo` 200. No restart, no corrections, no other traffic |
| Model | `qwen3:4b-instruct` via Ollama on 127.0.0.1:11434 |
| Root | `<TEST_BASE>/B-f1-retest`: new and unique, confirmed absent beforehand. `<TEST_BASE>` = `%LOCALAPPDATA%\Temp\ghostos-phase3` |
| Other folders | `<TEST_BASE>/A-blocker`, `<TEST_BASE>/B-acceptance` (from the original run) and `<TEST_BASE>/outside-canary` were monitored as an outside-root write detector |
| Network | Not disconnected (offline is out of scope for this retest) |

## Inputs (same five files and layout as the original run, including the lowercase `receipts/` folder)

| Original path | Size | SHA-256 |
|---|---|---|
| `inbox/invoice.pdf` | 1298 | `d34d23a313745851815763807d69b5369f5a9ed3028b07c2b21401139afe3ae5` |
| `archive/2026/invoice.pdf` | 1211 | `0bec9fe8f96693999451669e264d62772ffe2de3ea48548fec5d6c4957ac8024` |
| `receipts/sunbeam-cafe-receipt.pdf` | 1217 | `aab1c6fe32a7f119fcf15db2b96eabdd930c66337776a4324824e1ae6a8ed4c9` |
| `receipts/greenleaf-grocer-2026-09-14.txt` | 431 | `165d4ac5289f2d4c5296221a1cb4cdca11de33c4cb1ada1bd309571fa3a7fdc4` |
| `downloads/greenleaf-grocer-2026-09-14 (1).txt` | 431 | `165d4ac5289f2d4c5296221a1cb4cdca11de33c4cb1ada1bd309571fa3a7fdc4` |

All five hashes equal both the fixture source and the original acceptance manifest.

## Plan (`scan_28419f4558ec` → `plan_scan_28419f4558ec`, 0 blocking reviews)

The expected destinations were written down independently, from the fix's rule, **before** scanning. They match the plan exactly.

| Original | Planned destination | Actual on disk after approve (exact case) |
|---|---|---|
| `archive/2026/invoice.pdf` | `Invoices/2026-09/invoice.pdf` | `Invoices/2026-09/invoice.pdf` ✓ |
| `inbox/invoice.pdf` | `Invoices/2026-09/invoice (2).pdf` (collision suffix) | `Invoices/2026-09/invoice (2).pdf` ✓ |
| `downloads/greenleaf-grocer-2026-09-14 (1).txt` | `GhostOS Organized/Receipts/2026-09/greenleaf-grocer-2026-09-14 (1).txt` | identical ✓ |
| `receipts/greenleaf-grocer-2026-09-14.txt` | `GhostOS Organized/Receipts/2026-09/greenleaf-grocer-2026-09-14.txt` | identical ✓ |
| `receipts/sunbeam-cafe-receipt.pdf` | `GhostOS Organized/Receipts/2026-09/sunbeam-cafe-receipt.pdf` | identical ✓ |

## Results

### Preparation and pre-approval (read-only)

| ID | Check | Result |
|---|---|---|
| R0 | Root contains the lowercase source folder `receipts/` that triggered F1 | **PASS** |
| R1–R2 | Scan and preview leave the root unchanged | **PASS** |
| R3–R6 | Plan ID belongs to the scan; 0 blocking reviews; 5/5 classified `ok`; categories and dates match the ground truth | **PASS** |
| R7–R8 | Exactly 5 operations, equal to the independently expected destinations | **PASS** |
| R9 | All 3 receipts routed to `GhostOS Organized/Receipts/2026-09/` | **PASS** |
| R10 | No destination inside any source folder (`archive`, `archive/2026`, `downloads`, `inbox`, `receipts`), ignoring case | **PASS** |
| R11–R12 | Destinations relative, inside the root, free and unique | **PASS** |
| R13–R14 | Canary unchanged; plan totals PHP 5,439.70 / USD 59.88 | **PASS** |
| P1–P7 | Re-fetched just before approval: same IDs, **plan byte-identical to the reviewed snapshot** (including case), 5 operations, 0 blocking, original hashes intact, destinations free, canary unchanged | **PASS** |

### Approval: `HTTP 200 {"batch_id":"batch_72e59374531a","moved":5,"failed":[],"report_relative_path":"GhostOS Reports/expenses-202610091755.csv"}`

| ID | Check | Result |
|---|---|---|
| S1 | Approval succeeds: 5 moved, 0 failed | **PASS** |
| **D1** | Every file at its approved destination with **exactly the same case** and the original SHA-256 (exact string comparison of on-disk names) | **PASS** (the original S3 had FAILED) |
| **D2** | Folder names on disk have the planned case: `GhostOS Organized/Receipts/2026-09`, `Invoices/2026-09`, `GhostOS Reports` | **PASS** |
| **D3** | **Nothing organized under the lowercase source folder `receipts/`** (it was empty after approval) | **PASS** (the original S5 and S6 had FAILED) |
| D4 | No file written into any source folder | **PASS** |
| D5 | Nothing overwritten: `invoice.pdf` holds the archive bytes, `invoice (2).pdf` the inbox bytes; 5 distinct files | **PASS** |
| D6 | Nothing written outside the root: base folder children unchanged; `A-blocker`, the original `B-acceptance` and the canary unchanged | **PASS** |
| D7 | No temporary report file left | **PASS** |

### Expense CSV (`GhostOS Reports/expenses-202610091755.csv`, copy in [`F1_07_report_copy.csv`](F1_07_report_copy.csv))

```
source_file,merchant,date,category,amount,currency
archive/2026/invoice.pdf,CARABAO PAPER SUPPLY CO.,2026-09-18,invoice,3470.00,PHP
downloads/greenleaf-grocer-2026-09-14 (1).txt,GREENLEAF GROCER - Sample Branch (fictional),2026-09-14,receipt,1286.50,PHP
inbox/invoice.pdf,BRIGHTLINE WEB HOSTING LLC,2026-09-03,invoice,59.88,USD
receipts/sunbeam-cafe-receipt.pdf,SUNBEAM CAFE,2026-09-21,receipt,683.20,PHP
```

| ID | Check | Result |
|---|---|---|
| C1 | Inside the root at the returned path; UTF-8 BOM, CRLF, 6-column header | **PASS** |
| C2 | 4 data rows from the expected sources | **PASS** |
| C3 | Date, category, amount and currency match the ground truth per row | **PASS** |
| C4 | Totals: CSV = independent ground truth = plan: **PHP 5,439.70** (3,470.00 + 1,286.50 + 683.20), **USD 59.88** | **PASS** |
| C5 | Duplicate excluded: one Greenleaf row (`downloads/…(1).txt`) | **PASS** |

**Why the duplicate is excluded:** this is unchanged from the original report. Folders are walked alphabetically, so `downloads/…(1).txt` is seen first, and `receipts/greenleaf-…txt` is marked `duplicate_of` it. `_build_plan` accepts a row only when `duplicate_of is None`, and the writer emits committed, accepted rows only. Both copies were moved, and neither was deleted.

### Undo: `HTTP 200 {"batch_id":"batch_72e59374531a","restored":5,"conflicts":[]}`

| ID | Check | Result |
|---|---|---|
| U1 | Undo succeeds with 0 conflicts | **PASS** |
| U2 | All 5 original paths (exact case) restored with the original SHA-256, matching the input table | **PASS** |
| U3 | No organized files remain anywhere | **PASS** |
| U4 | Source folders contain only their original files (no organized files inside `receipts/` or any other source) | **PASS** |
| U5 | Report CSV left after undo (observed) | `GhostOS Reports/expenses-202610091755.csv` **remains** |
| U6 | Empty generated folders left after undo (observed) | `GhostOS Organized/Receipts/2026-09`, `Invoices/2026-09` remain. **None are inside the user's source folders** (the original run left `receipts/2026-09` inside the user's folder) |
| U7 | Nothing outside the root changed after undo | **PASS** |

## Conclusion

**F1 is fixed for this scenario.** The planned and actual destinations agree exactly, including case. Organized files are never placed inside the lowercase `receipts/` source folder. Nothing was overwritten or written outside the root, the CSV matches the ground truth, and undo restores every original path and hash. Undo no longer leaves a generated folder inside a user's source folder.

## Observations (not F1 failures)

| # | Severity | Owner | Observation |
|---|---|---|---|
| O1 | Low (UX) | Dev 1 / Dev 3 | **Split layout:** in one batch, invoices go to `Invoices/…` at the root but receipts go to `GhostOS Organized/Receipts/…`, because only the receipts folder clashed with a source folder. It's safe and matches the preview, but users may look in two places. Consider always using one organized root when any clash exists, or highlighting it in the Totals preview. |
| O2 | Low (carried over, F2) | Dev 1 | Undo still leaves the report CSV and empty generated folders, and the batch state never becomes `undone`. |
| O3 | Decision (carried over, F3) | Team | The CSV still has no row-status or timestamp column. The kept duplicate copy depends on folder walk order. |

## Still open / not tested

- **D1 (High, separate from F1):** corrections are still matched by `file_id` across all scans (`session_store.find_document`). Not exercised here; no corrections were made.
- **Symlink escape: NOT TESTED.** Windows Developer Mode is still off (WinError 1314).
- **Other folder names:** only the `receipts` clash was exercised, plus `Invoices` with no clash. An `invoices/` source folder, `Needs Review/`, `Other/`, and a pre-existing `GhostOS Organized/` were not tested.
- **503 report-failure recovery, restart recovery, offline:** NOT TESTED in this retest.

## Evidence (this folder)

`F1_00_setup_manifest.json` · `F1_01_scan_result.json` · `F1_02_plan_for_approval.json` · `F1_03_http_log_prepare.json` · `F1_04_preapproval_checks.json` · `F1_05_http_log_execute.json` · `F1_06_approve_response.json` · `F1_07_report_copy.csv` · `F1_08_undo_response.json` · `F1_09_results.json` · `snapshots/01_before_scan … 06_after_undo.json` · `scripts/f1_prepare.py`, `scripts/f1_execute.py` (they contain local test paths; the evidence files redact them as `<ROOT_F1>` and `<TEST_BASE>`).

Reproduce: start one fresh backend process, then run `backend\.venv\Scripts\python.exe tests\reports\phase3_acceptance\f1_retest\scripts\f1_prepare.py`, have a human review the plan, and run `…\f1_execute.py`. The plan and scan IDs are hard-coded in the execute script, and both scripts refuse to reuse existing folders.
