# DA-7 Fresh Regression Retest (0641adb)

- **Tester:** Developer 4 (QA and integration)
- **Date:** 2026-10-10
- **Commit under test:** `0641adb` "fix: preserve validated expense amounts" (main HEAD; also contains `47520ec` UI1 frontend fix)
- **Mode:** NON-DESTRUCTIVE. No approval, no undo, no file movement.
- **Backend:** real FastAPI on 127.0.0.1:8000, restarted on `0641adb` for this test (previous process held only finished LS1 sessions). Live model `qwen3:4b-instruct`, `external_requests: 0`. Backend log shows only this test's traffic: 2 scans, 6 PATCHes, no approve/undo.

## Verdict

**DA-7: FIXED** (API and plan-builder level). `PATCH {"accept": true}` on Bayside is rejected with 422 and changes nothing; the plan builder no longer re-parses `amount_text`; Bayside stays out of accepted rows and totals; Pixelforge and Sunbeam still work.

**New regression (X1, separate from DA-7):** `0641adb` breaks the UI1 fix `47520ec`. The full backend suite has 1 failure: accepting a `missing_amount` transaction with the amount omitted (`{accept: true}`) is now 422, where `47520ec` expects 200 (filed, not counted).

## Stage 1: inspection and unit tests

- `routes/session.py`: on `accept` for a `transaction` profile, the proposed transaction is rebuilt (amount = body amount, else stored `amount_text`, else `amount`) and re-run through `validate_classification` against the source excerpt. Any flag, invalid result or unparsed amount → 422 "Cannot accept transaction while source validation findings remain unresolved", before any mutation.
- `orchestrator.py`: `_parse_amount` removed; `amount = c.get("amount")` only. Accepted rows now require `not doc.review_flags` (any flag, not just the amount/currency subset).
- New test `test_bayside_ambiguous_amount_survives_acceptance_and_stays_out_of_plan` (validation integration).

| Command (from `backend/`) | Result |
|---|---|
| `.venv\Scripts\python.exe -B -m pytest -q -p no:cacheprovider tests/test_validation_integration.py tests/test_session.py` | 1 failed, 54 passed, 2 skipped |
| `.venv\Scripts\python.exe -B -m pytest -q -p no:cacheprovider` | 1 failed, 185 passed, 2 skipped |

Failing test: `tests/test_session.py::test_accept_without_amount_field_files_uncounted_and_null_is_rejected` (line 397), `assert 422 == 200`, detail "Cannot accept transaction while source validation findings remain unresolved".

## Stage 2: setup

Two independent runs, each with a fresh base, unique prefix (D1 workaround) and outside-root canary:

| Run | Base | Prefix | Live scan | Evidence |
|---|---|---|---|---|
| 1 | `%LOCALAPPDATA%\Temp\ghostos-da7` | `d7/` | `scan_a3287543f63b` | `setup/`, `live/`, `inprocess_mock_http_log.json` |
| 2 | `%LOCALAPPDATA%\Temp\ghostos-da7-run2` | `d7b/` | `scan_5a100bbf9e24` | `run2/` (complete, incl. `results.json`) |

Run 1 executed every check (all results identical to run 2) but the script crashed afterwards while writing `results.json` (a `CurrencyTotal` object was not JSON-serialisable in the M3 record — a QA script bug). Run 1's per-step evidence files were written; its `results.json` was not. The script was fixed (`default=str`) and run 2 produced the full record.

| File (in each root) | Size | SHA-256 |
|---|---|---|
| receipts/bayside-office-mart.pdf | 1124 | 3b11f36a…1d810f |
| invoices/INV-1043_Pixelforge_Studio.pdf | 1331 | a4a03b73…638cff7 |
| receipts/sunbeam-cafe-receipt.pdf | 1217 | aab1c6fe…edd4c9 |

Each run has a live root `D7-L` and an in-process root `D7-M`. The committed fixture folder was only read from.

## Results (run 2; run 1 identical)

### Stage 3: Bayside

| ID | Check | Actual | Result |
|---|---|---|---|
| B1 | Scan: Bayside untrusted | needs_review; flags `[amount_conflict]`; `amount` null; `amount_text` "PHP 1,520.00"; evidence "AMOUNT DUE: PHP 1,520.00" (verified) | PASS |
| B2 | Initial eligibility | one row, needs_review, amount null; totals PHP 19,331.20 (2 rows, Bayside excluded) | PASS |
| B3 | `PATCH {"accept": true}` | **HTTP 422** "Cannot accept transaction while source validation findings remain unresolved" | PASS |
| B4 | Record after rejection | classification, flags, status, user_corrected, disposition identical | PASS |
| B5 | Fresh plan after rejection | identical to the plan before; Bayside needs_review, amount null | PASS |
| M0 | In-process (mocked classifier): Bayside with parseable rejected `amount_text` | needs_review, amount_conflict, amount null | PASS |
| M1 | In-process `{accept: true}` (the old revival case) | 422; plan_revision 0→0; plan snapshot unchanged; record unchanged | PASS |
| M2 | In-process fresh plan | Bayside needs_review, amount null; no 1520.00 anywhere | PASS |
| M3 | Code-level probe of `_build_plan` on a **deep copy** of the session, with Bayside forced to ok/unflagged/amount null/amount_text "PHP 1,520.00" | row amount null, not accepted; totals PHP 19,331.20 | PASS |

M3 does not go through the API and does not modify the stored session; it only confirms the fallback is gone from the builder.

### Stage 4: valid controls

| ID | Check | Actual | Result |
|---|---|---|---|
| C1 | Pixelforge `{"amount":"18648.00","accept":true}` (evidence "Total Amount Due: PHP 18,648.00") | 200; amount 18648.00; ok; no flags | PASS |
| C2 | Sunbeam `{"amount":"683.20","accept":true}` (evidence "FINAL TOTAL: PHP 683.20") | 200; amount 683.20; ok; no flags | PASS |
| C3 | Pixelforge row | exactly one, accepted, 18648.00 PHP | PASS |
| C4 | Sunbeam row | exactly one, accepted, 683.20 PHP | PASS |
| M4 | Valid correction still bumps plan_revision | 0→1 | PASS |

### Report and filesystem

| ID | Check | Actual | Result |
|---|---|---|---|
| R1 | Prepared CSV (production `render_report`, not committed) | Pixelforge + Sunbeam only | PASS |
| R2 | Totals: independent 18,648.00 + 683.20 = 19,331.20 = CSV = plan | PHP 19,331.20 in all three | PASS |
| R3 | Bayside raw amount absent from rows and totals | Bayside needs_review, amount null | PASS |
| G1 / G2 | Roots and canary after live and in-process parts | unchanged | PASS |

### Other

| ID | Check | Result |
|---|---|---|
| X1 | Full backend suite | **FAIL** (1 failed; see below) |
| X2 | Offline and symlink tests | NOT TESTED |

**Totals (run 2):** 19 PASS, 1 FAIL, 1 NOT TESTED.

## Finding X1 (Dev 1 + Dev 3, Medium): DA-7 fix reverts the UI1 fix

`47520ec` made the Check screen omit an untouched empty amount, so `{accept: true}` on a transaction with no amount (flag `missing_amount`) files it uncounted (200). `0641adb` now revalidates every transaction accept and rejects it because `parsed_amount` is None, so that path returns 422 again. The repo's own test for it fails on `main`.

Product decision needed: should a transaction with no amount be acceptable as "file it, don't count it"? If yes, the accept gate should allow `missing_amount` while still rejecting `amount_conflict`; if no, the test and UI1 fix need updating. Not changed by QA.

## Separately tracked

UI1 (frontend `review_disposition` handling, from the leave-for-review state retest) and D1 remain open and are not part of the DA-7 verdict. F1 stays closed. DA-5b, DA-2 and DA-4 unchanged. No approve, undo or file move was performed.
