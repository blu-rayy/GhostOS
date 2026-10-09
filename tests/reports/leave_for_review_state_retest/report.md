# Leave-for-Review State Acceptance Retest (bf99c68)

- **Tester:** Developer 4 (QA and integration)
- **Date:** 2026-10-10
- **Commit under test:** `bf99c68` "fix: preserve leave-for-review state"
- **Backend:** real FastAPI on 127.0.0.1:8000, restarted on `bf99c68` before this run, using the live model `qwen3:4b-instruct`. The backend log shows one scan, 3 PATCHes and 1 approve attempt (409), all from this run.
- **Unit tests:** `pytest` on `bf99c68` gave 184 passed and 2 skipped.
- **Status:** All stages are complete. Stages 1–3 ran first, and the run stopped at Stage 4. Stage 5 (approve, then undo) ran after separate human authorisation; see the Stage 5 results at the end.

## Setup

The disposable root is `<TEST_BASE>/LS1`, where `<TEST_BASE>` = `%LOCALAPPDATA%\Temp\ghostos-leave-state`. It is a new folder and not the committed fixture directory. The `ls/` prefix avoids the D1 file_id collision.

| File | Size | SHA-256 | Role |
|---|---|---|---|
| ls/receipts/bayside-office-mart.pdf | 1124 | 3b11f36a…1d810f | Leave for review (has the existing flag `amount_conflict`) |
| ls/legal/lease-agreement-summary.pdf | 1020 | 4538c2e2…0516f9 | Leave for review (a non-transaction document; this is the UI-realistic path) |
| ls/identity/birth-certificate.pdf | 1095 | df083a5d…edd1b | Control: "File it" → Other/ |
| ls/receipts/sunbeam-cafe-receipt.pdf | 1217 | aab1c6fe…edd4c9 | Control: valid receipt |

- **Canary:** `<TEST_BASE>/outside-canary/canary.txt`, outside the root. It was unchanged.
- **In-process copy:** `<TEST_BASE>/LS1-inprocess`. It is used only by the revision check that runs the production app with a mocked classifier.
- **Full hashes:** `setup/manifest.json`.

## Results

| ID | Check | Result |
|---|---|---|
| S0 | Live scan preconditions: Bayside is needs_review with amount_conflict; the lease is needs_review with 3 flags; the birth certificate is needs_review; Sunbeam is ok | PASS |
| S1 | `review_disposition` is "none" on every document before any correction | PASS |
| L1-P / L1-G | Bayside after `{category:"uncertain",accept:true}`. Both the PATCH and the GET return disposition `leave_for_review`, status `needs_review`, flags `[amount_conflict]`, category `uncertain`, and unchanged transaction fields | PASS / PASS |
| L2-P / L2-G | The same checks on the lease. Its flags `[missing_evidence_quote, missing_currency, non_transactional_document]` are preserved | PASS / PASS |
| F1 | Control: "File it" on the birth certificate gives disposition `filed`, status ok, flags cleared, category other | PASS |
| B1 | The blocking preview has blocking_review_count = 2 (the two left-for-review files) | PASS |
| B2 | Blocking preview destinations: both left-for-review files → Uncategorized/, the birth certificate → Other/, Sunbeam → Receipts/2026-09/ | PASS |
| B3 | The guarded default (blocking) approval returned **409** "Plan has 2 unresolved review items", and the filesystem was unchanged | PASS |
| P1 | Partial preview destinations are the same as in the blocking preview | PASS |
| P2 | The partial preview report rows contain only Sunbeam (accepted, PHP 683.20); neither left-for-review file has a row | PASS |
| P3 | The partial preview has mode `partial`, totals PHP 683.20 (1 row), and blocking count still 2 | PASS |
| P4 | After the previews, both left-for-review files are still needs_review / leave_for_review with their flags intact | PASS |
| G1 | The scans, corrections, previews and the refused approval wrote nothing; the root, the in-process copy and the canary are unchanged | PASS |
| RV1 | In-process (mocked classifier): Leave for review bumps plan_revision from 0 to 1, keeps the stored flags, and makes the earlier partial snapshot stale | PASS |
| UI1 | The frontend handles `review_disposition` (code inspection) | **FAIL** (Dev 3) |
| UI2 | An actual browser click on "Leave for review" | NOT TESTED |
| Stage 5 | Approve the partial plan, verify, undo, verify (20 checks, below) | PASS |

**Totals:** 16 PASS, 1 FAIL and 1 NOT TESTED before approval; Stage 5 added 20 PASS.

## Finding UI1 (Dev 3, Medium): the frontend treats a "left for review" file as resolved

The backend (`bf99c68`) now keeps a left-for-review file at `status=needs_review` with `user_corrected=true`, and counts it as blocking. The frontend has no `review_disposition` handling, and its checks ignore it:

- `frontend/src/lib/viewModel.ts`: `isBlocking(d) = d.status === 'needs_review' && !d.user_corrected`
- `frontend/src/pages/FilesPage.tsx`: `isNeeds(row) = … status === 'needs_review' && !row.doc.user_corrected`, and `isReady` accepts any `user_corrected` file

**Effect:** in blocking mode (sortMode `blocking`) a left-for-review file looks decided, so the UI lets the user continue to totals. The backend then refuses approval with 409 ("Plan has N unresolved review items"), which B3 reproduced through the API. Partial mode is unaffected, because the review-choice pop-up sets `sortMode: 'partial'`.

**Suggested fix (Dev 3):** treat `review_disposition === 'leave_for_review'` as still needing review, or as "set aside", and only allow it through partial mode.

## Separately tracked items (not changed by this run)

- **F1:** stays closed.
- **D1, DA-5b, DA-2, DA-4, DA-6 and DA-7:** tracked separately.
- **DA-7** is not exercised here: Bayside is left for review, not accepted as-is, so it has no report row.
- **Earlier L2 (flags cleared after leave-for-review):** addressed for the leave path by `bf99c68` (L1 and L2 above). "File it" still clears flags by design (F1 control).
- **Offline and symlink tests:** NOT TESTED.

## Stage 4: authorisation package (approved)

| Item | Value |
|---|---|
| Root | `<TEST_BASE>/LS1` |
| Scan | `scan_1d788bbc1289` |
| Plan | `plan_scan_1d788bbc1289` |
| Mode | `partial` |
| Blocking count | 2 (files set aside to Uncategorized/) |

### Proposed moves

| From | To |
|---|---|
| ls/receipts/bayside-office-mart.pdf | Uncategorized/bayside-office-mart.pdf |
| ls/legal/lease-agreement-summary.pdf | Uncategorized/lease-agreement-summary.pdf |
| ls/identity/birth-certificate.pdf | Other/birth-certificate.pdf |
| ls/receipts/sunbeam-cafe-receipt.pdf | Receipts/2026-09/sunbeam-cafe-receipt.pdf |

### Expected results

- **CSV:** `GhostOS Reports/expenses-<stamp>.csv` with one row: `ls/receipts/sunbeam-cafe-receipt.pdf, SUNBEAM CAFE, 2026-09-21, receipt, 683.20, PHP`.
- **Totals:** PHP 683.20.
- **After approve:**
  - each file sits at its destination with the same SHA-256;
  - the left-for-review files remain needs_review / leave_for_review (moved, but not accepted);
  - nothing is written outside the root.
- **After undo:**
  - all 4 files are restored with matching hashes;
  - the CSV and empty folders are left behind (known behaviour);
  - the canary is unchanged.

**Evidence:** `setup/manifest.json`, `scan_initial.json`, `state_before_corrections.json`, `leave_*.json`, `file_it_birth_certificate.json`, `plan_blocking.json`, `plan_partial_for_review.json`, `http_log.json`, `results.json`, `scripts/stage2_3_preapproval.py`.

## Stage 5: approve and undo (human-authorised)

- **Script:** `scripts/stage5_approve_undo.py`
- **Evidence:** `stage5/` (`plan_refetched.json`, `scan_before_approve.json`, `approve_response.json`, `snapshot_after_approve.json`, `report_csv_copy.csv`, `scan_after_approve.json`, `undo_response.json`, `snapshot_after_undo.json`, `http_log.json`, `results.json`)

### Preconditions (all PASS, checked before the single approval request)

| ID | Check | Result |
|---|---|---|
| A1 | Re-fetched plan is identical to the reviewed plan: scan, plan ID, `partial` mode, blocking 2, the 4 operations, report rows and totals | PASS |
| A2 | Bayside and the lease are still leave_for_review / needs_review with their original flags | PASS |
| A3 | Birth certificate is filed / ok / other → Other/; Sunbeam is ok, with the only accepted row | PASS |
| A4 | All 4 original SHA-256 hashes match the manifest, and the root holds no other files | PASS |
| A5 | All destinations are free and inside the root, and there is no `GhostOS Reports/` folder yet | PASS |
| A6 | The canary and the in-process copy are unchanged | PASS |

### Approval

`POST /api/plans/plan_scan_1d788bbc1289/approve {"mode":"partial"}` returned **200** with batch `batch_c0a405492f92`. It was sent once.

| ID | Check | Result |
|---|---|---|
| V0 | HTTP 200 with a batch_id | PASS |
| V1 | Destinations exist with exact case: `Uncategorized/bayside-office-mart.pdf`, `Uncategorized/lease-agreement-summary.pdf`, `Other/birth-certificate.pdf`, `Receipts/2026-09/sunbeam-cafe-receipt.pdf` | PASS |
| V2 | Destination hashes equal the manifest, so files are byte-identical and nothing was overwritten | PASS |
| V3 | Original paths are gone and no files remain under `ls/` | PASS |
| V4 | The root holds only the 4 destinations plus `GhostOS Reports/expenses-202610092104.csv` | PASS |
| V5 | The CSV is exactly the header plus `ls/receipts/sunbeam-cafe-receipt.pdf,SUNBEAM CAFE,2026-09-21,receipt,683.20,PHP` (PHP 683.20) | PASS |
| V6 | After the move, both left-for-review documents are still needs_review / leave_for_review with their flags, and neither is in the CSV (moved without being accepted) | PASS |
| V7 | No out-of-root writes: the canary and in-process copy are unchanged, and the test base holds only `LS1`, `LS1-inprocess` and `outside-canary` | PASS |

### Undo

`POST /api/batches/batch_c0a405492f92/undo` returned **200**.

| ID | Check | Result |
|---|---|---|
| U0 | HTTP 200 | PASS |
| U1 | All four original paths are restored with their original SHA-256 | PASS |
| U2 | All destinations are vacated | PASS |
| U3 | Leftover file after undo: `GhostOS Reports/expenses-202610092104.csv` remains (known behaviour, recorded separately) | PASS (recorded) |
| U4 | Empty folders after undo: `Other/`, `Receipts/2026-09/` and `Uncategorized/` remain (known behaviour, recorded separately) | PASS (recorded) |
| U5 | The canary and in-process copy are unchanged | PASS |

**Conclusion:** `bf99c68` meets the acceptance criteria at the API and filesystem level. A "Leave for review" document:

- keeps its flags and its `needs_review` status;
- blocks default approval (409);
- is moved to `Uncategorized/` in partial mode without being accepted;
- is excluded from the CSV and the totals;
- is fully restored by undo.

"File it" (→ Other/) and the accepted receipt keep their separate behaviour.

UI1 (Dev 3) and D1 remain open and are tracked separately from this filesystem result. Nothing was deleted, and the test folders were left in place.