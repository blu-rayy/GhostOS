# DA-5 retest: missing document kind (commit `3c60bb3`)

**Owner:** Developer 4 (QA) · **Run:** 2026-10-10 · **Branch / commit:** `main` @ `3c60bb3` ("fix: preserve document kind fallback safety") · **Status:** complete. Stages 1–4 were non-destructive. Stage 5 (approve/undo of the explicit-null batch) was human-confirmed: **18/18 PASS**. **DA-5b, DA-6, DA-7 and the reclassification decision remain OPEN.**

Earlier DA-5 evidence ([`report.md`](../report.md), [`regression_9a909c7_report.md`](../regression_9a909c7_report.md)) and the F1 and D1 records are unchanged.

## Method and labelling

| Layer | What it is | Used for |
|---|---|---|
| **Unit** | Production `ClassificationRecord`, `document_awareness`, `_build_plan` called directly on constructed records | B1 (legacy record with the field genuinely omitted) |
| **MOCKED classifier** | `scripts/mock_backend.py`: the **unmodified production app** on `127.0.0.1:8001`. Only `local_ai.classify_excerpt` is replaced with fixed, marker-selected JSON. No Ollama call. Routes, orchestrator, validator, plan builder, PATCH, approve/undo and report writer are production code | A (explicit `document_kind: null`), B2 (new scan whose model JSON omits the field), C, `/api/classify`, corrections, routing |
| Real backend `:8000` | Untouched in this retest | — |

**Live-model behaviour was not tested here.** Every A/B2/C/K result comes from the mocked classifier.

Roots (new, under `%LOCALAPPDATA%\Temp\ghostos-docaware`): `DA5-R1` (state tests, prefix `r1/`), `DA5-R2` (candidate approval batch, prefix `r2/`), `DA5-R3` (corrected B2, prefix `r3/`), canary `DA5-canary/canary.txt`. The unique prefixes avoid D1. Hashes are in `setup/manifest.json` and `b2_rerun/R3_snapshot_initial.json`.

## Stage 1: baseline

| Command (in `backend/`) | Result |
|---|---|
| `.\.venv\Scripts\python.exe -m pytest -q -p no:cacheprovider` | **179 passed, 2 skipped** (matches the reported full-suite result; skips = symlink WinError 1314) |
| `… -m pytest -q -p no:cacheprovider tests/test_schemas.py tests/test_classification_validation.py tests/test_classify.py tests/test_validation_integration.py tests/test_session.py tests/test_local_ai.py` | **170 passed, 2 skipped**. The reported "focused 154 passed, 2 skipped" could **not** be reproduced because its selection wasn't recorded; this is QA's focused set |
| `… -m pytest -q -p no:cacheprovider -k "null or omit or legacy or fallback or uncertain_document_kind or reference or profile"` | 22 passed |

**Code inspected:**
- the scan stores `document_kind` whenever the model JSON *contains* the key, including null (`orchestrator.py:477`, `model_fields_set`);
- `ClassificationRecord.field_profile` applies the category fallback only when the key is **absent**;
- the validator adds `uncertain_document_kind` for an explicit null (`3c60bb3`);
- `build_proposed_operation` returns no operation unless the profile is `transaction` (`3c60bb3`);
- the plan builder's report rows require profile `transaction`;
- partial mode excludes unresolved rows.

## Stage 3–4 results

| ID | Case | Method | Check | Expected | Actual | Status | Owner |
|---|---|---|---|---|---|---|---|
| B1a | Legacy (omitted) | unit | Derived kind and profile | `invoice` / `transaction` (category fallback) | `invoice` / `transaction` | PASS | — |
| B1b | Legacy | unit | `_build_plan` | `Invoices/2026-09/`, accepted row PHP 100.00 | as expected | PASS | — |
| B1c | Legacy vs null | unit | `ClassificationRecord.field_profile` | omitted → `transaction`; null → `none` | omitted → `transaction`; null → `none` | PASS | — |
| K1 | `/api/classify` statement | MOCKED | profile `reference` | no transaction operation | `reference`, `proposed_operation: null`, `needs_review: true`, "Document is not a single transaction" | PASS | — |
| K2 | `/api/classify` identity | MOCKED | profile `none` | no operation | `none`, no op, review | PASS | — |
| K3 | `/api/classify` explicit null | MOCKED | profile `none` | no operation | kind null, `none`, no op, review | PASS | — |
| K4 | `/api/classify` kind omitted | MOCKED | legacy compatibility | `transaction`, op proposed | `invoice` / `transaction`, `organized/invoices/k4` | PASS (compatibility as documented) | — |
| K5 | `/api/classify` receipt | MOCKED | valid kind | `transaction`, op proposed | `receipt` / `transaction`, `organized/receipts/k5` | PASS | — |
| **A1** | Explicit null | MOCKED scan | GET state | kind `null` (key present), profile `none`, `needs_review`, `uncertain_document_kind` | kind `null`, `none`, `needs_review`, flags `amount_conflict`, `uncertain_document_kind` | PASS | — |
| A2 | Explicit null | MOCKED | Expense amount | `amount: null` | `amount: null` (raw `amount_text` "PHP 9,120.50" retained) | PASS | — |
| **A3** | Explicit null | MOCKED | Blocking and partial routing | `Uncategorized/`, no report row in either | `Uncategorized/bank-statement-oct2026.txt` in both; no row | PASS | — |
| X1–X3 | Explicit null | MOCKED | PATCH amount; merchant/date/currency; `field_profile` | 422, unchanged | 422 (`profile 'none' does not allow transaction corrections` / `backend-controlled fields`); unchanged | PASS | — |
| X7 | Explicit null | MOCKED | PATCH `{document_kind: 5}` | 422, unchanged | 422 `document_kind must be a supported string or null`; unchanged | PASS | — |
| A4 | Explicit null | MOCKED | Accept as-is `{accept:true}` | never an expense row | 200; `Other/bank-statement-oct2026.txt`; no row | PASS | — |
| A5/A5b | Explicit null | MOCKED | `{category:"invoice", accept:true}` | no expense row | 200 (no-op: category was already `invoice`); no row | PASS | — |
| A6 | Explicit null | MOCKED | `PATCH {document_kind:"invoice"}`, then merchant/date/amount/currency + accept | record | 200, 200 → `Invoices/2026-09/…`, **accepted row PHP 9120.50** | CONTRACT DECISION REQUIRED (explicit user reclassification) | Dev 1 + team |
| **C1/C2** | Valid receipt | MOCKED | kind/profile/route/row | `receipt`/`transaction`, ok; `Receipts/2026-09/sunbeam-cafe-receipt.pdf`; one accepted row PHP 683.20 | as expected | PASS | — |
| **X4** | Valid receipt | MOCKED | PATCH `{amount:"abc", accept:true}` | 422, unchanged | **200; stored `amount: "abc"`** | **FAIL** | Dev 1 |
| **X5** | Valid receipt | MOCKED | PATCH `{date:"2026-13-45"}` | 422 | **200; stored** | **FAIL** | Dev 1 |
| **X6** | Valid receipt | MOCKED | PATCH `{currency:"XYZ"}` | 422 | **200; stored**. Plan totals then contain `{"currency":"XYZ","amount":"0","row_count":0}` | **FAIL** | Dev 1 |
| ~~B2a/B2b~~ (first run) | — | MOCKED | — | — | **INVALID: QA harness error.** The card statement's text also contains "SUNBEAM CAFE", which the mock matched first, so it received the receipt response. Fixed by checking statement markers first; re-run on a fresh root below | INVALID | QA |
| B2a′ | New-scan omission | MOCKED | Harness check | mocked JSON without `document_kind` | confirmed (`"MOCK: kind omitted"`) | PASS | — |
| **B2a** | New-scan omission | MOCKED | GET state | record | kind `invoice` (fallback), profile **`transaction`**, `needs_review` (`amount_conflict`), `amount: null`; row `needs_review` 5391.06 | RECORDED | — |
| **B2b** | New-scan omission | MOCKED | Accept as-is | not counted (QA safety rule) | **200 → `Invoices/2026-09/card-statement-sep2026.pdf`, accepted row PHP 5391.06, totals PHP 5391.06** | **FAIL** (QA blocking safety rule; matches the documented legacy compatibility) | Dev 1 + team |
| G1–G4 | All roots | MOCKED | Scan, previews, corrections | no writes; canary unchanged | unchanged throughout | PASS | — |

**Totals (valid checks): 26 PASS · 4 FAIL · 1 CONTRACT DECISION REQUIRED · 1 RECORDED · 2 INVALID (superseded).**

## Findings

| ID | Severity | Owner | Finding |
|---|---|---|---|
| **DA-5** | — | Dev 1 | **Explicit null: fixed** (A1–A5, K3). The record is conservative (`none`, review flag, `Uncategorized/` until decided, `Other/` after accept), and is never an expense row through ordinary paths. |
| **DA-5b** | **High (blocking safety rule)** | Dev 1 + team | **A new model response that omits `document_kind` is treated as a legacy record.** The category fallback gives profile `transaction`, and one "accept as-is" counts a statement (PHP 5391.06). The legacy fallback is intended for old stored records, but a new scan can't currently be told apart from one. Suggested fix: when the orchestrator stores a new classification, record `document_kind: null` if the model omitted it (so `none` and review apply). Keep the fallback only for pre-existing stored records or seven-field fixtures. |
| **DA-6** | **Medium–High** | Dev 1 | **Transaction corrections aren't validated.** `PATCH` stores `amount:"abc"`, `date:"2026-13-45"` and `currency:"XYZ"` with 200 on a transaction record. Effects: the plan report rows can carry invalid values; totals silently skip the bad amount; and a bogus `{"currency":"XYZ","amount":"0","row_count":0}` totals entry appears. Suggested fix: validate a decimal amount, an ISO date and a supported currency, and return 422 with the record unchanged. |
| **DA-7** | Medium | Dev 1 | **An accepted row can revive an amount the validator rejected.** In B2b the validator set `amount: null` (`amount_conflict`), but after accept-as-is `_build_plan` used `_parse_amount(amount_text)` and produced an accepted 5391.06 row. Suggested fix: when the validator rejected the amount, keep the row `needs_review` until the user enters an amount explicitly. |
| Decision | — | team | A6: whether a user may reclassify a null-kind document's kind and enter payment details (it then counts). Same open question as the earlier C/D findings. |

## Stage 5: approve and undo of the explicit-null batch (human-confirmed)

**Mock backend** (`127.0.0.1:8001`; production app, mocked classifier). The file moves were real, inside the disposable root only. Evidence: [`stage5_execute/`](stage5_execute/) (`approve_response.json`, `undo_response.json`, `report_copy.csv`, snapshots before, after approval and after undo, `http_log.json`, `results.json`).

| ID | Check | Actual | Status |
|---|---|---|---|
| Q1–Q2 | Re-fetched plan | same scan, plan and mode (`partial`); **byte-identical** to the reviewed preview | PASS |
| Q3 | Explicit-null statement before approval | `needs_review`, not corrected, kind `null` (key present), profile `none`, → `Uncategorized/bank-statement-oct2026.txt` | PASS |
| Q4 | Plan rows | Sunbeam 683.20 PHP, Tibay 2145.00 PHP accepted; no statement row | PASS |
| Q5–Q7 | Hashes, free/unique/contained destinations, canary and other roots | as recorded; unchanged | PASS |
| S1 | `POST approve {"mode":"partial"}` | `HTTP 200 {"batch_id":"batch_34249d9117e5","moved":3,"failed":[],"report_relative_path":"GhostOS Reports/expenses-202610092015.csv"}` | PASS |
| M1 | Exact-case destinations with original SHA-256 | `Receipts/2026-09/sunbeam-cafe-receipt.pdf` (`aab1c6fe…`), `Receipts/2026-09/tibay-hardware-receipt.csv` (`5cc008a2…`), `Uncategorized/bank-statement-oct2026.txt` | PASS |
| M2–M5 | No overwrite, nothing in source folders, no temporary file, no out-of-root change | as expected | PASS |
| R1 | CSV rows | exactly Sunbeam 683.20 PHP and Tibay 2145.00 PHP | PASS |
| R2 | Statement in the CSV | absent; contributes nothing | PASS |
| R3 | Total **recomputed from the CSV** | PHP **2828.20** (683.20 + 2145.00) | PASS |
| U1 | `POST undo` | `HTTP 200 {"restored":3,"conflicts":[]}` | PASS |
| U2 | Original paths and SHA-256 | 3/3 restored | PASS |
| U3 | No organized files remain | only the report | PASS |
| U4 | Report left after undo (observed) | `GhostOS Reports/expenses-202610092015.csv` | RECORDED |
| U5 | Empty folders left after undo (observed) | `Receipts/2026-09`, `Uncategorized` | RECORDED |
| U6 | Outside root after undo | unchanged | PASS |

**Scope:** this run verifies only the **explicit-null** case end to end. It does **not** resolve DA-5b (kind omitted in a new scan), DA-6 (unvalidated corrections), DA-7 (rejected amount revived on accept) or the kind-reclassification decision. All four remain **OPEN**.

### Plan that was reviewed and approved

| | |
|---|---|
| Root | `%LOCALAPPDATA%\Temp\ghostos-docaware\DA5-R2` |
| Scan / plan | `scan_8394fbe2c049` / `plan_scan_8394fbe2c049`, mode `partial` ([`r2_preview_v2/R2_plan_partial_for_review.json`](r2_preview_v2/R2_plan_partial_for_review.json)) |
| Blocking reviews | 1 (`r2/misc/bank-statement-oct2026.txt`: explicit-null kind, unresolved) |
| Operations | `r2/misc/bank-statement-oct2026.txt` → `Uncategorized/bank-statement-oct2026.txt` · `r2/receipts/sunbeam-cafe-receipt.pdf` → `Receipts/2026-09/sunbeam-cafe-receipt.pdf` · `r2/receipts/tibay-hardware-receipt.csv` → `Receipts/2026-09/tibay-hardware-receipt.csv` |
| Expected CSV | 2 accepted rows (Sunbeam 683.20 PHP, Tibay 2145.00 PHP) → **PHP 2828.20**; no row for the explicit-null statement |

The superseded first preview of R2 (scan `scan_64fcd9ae2475`, in `R2_plan_partial_for_review.json` at this folder's top level) was lost when the mock backend was restarted, and must not be approved.

## Not tested

Live-model omission or null behaviour · symlinks (WinError 1314) · UI · offline · D1 (avoided by prefixes; still open).
