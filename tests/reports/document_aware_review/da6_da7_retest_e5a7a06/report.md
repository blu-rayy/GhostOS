# DA-6 / DA-7 regression retest (commit `e5a7a06`)

**Owner:** Developer 4 (QA) · **Run:** 2026-10-10 · **Branch / commit:** `main` @ `e5a7a06` ("fix: validate corrected transaction amounts safely") · **Scope:** non-destructive (no approve, undo or file move)

**Result: DA-6 FIXED. DA-7 PARTLY FIXED; still OPEN via accept-as-is (High). New: the Check screen's empty-amount "mark checked" payload is now rejected (UI1).**

Earlier DA-6/DA-7 evidence ([`../da5_retest_3c60bb3/report.md`](../da5_retest_3c60bb3/report.md)) and all other reports are unchanged. DA-5b, DA-2, DA-4 and D1 are kept separate; F1 stays closed.

## Stage 1: baseline

| Command (in `backend/`) | Result |
|---|---|
| `.\.venv\Scripts\python.exe -m pytest -q -p no:cacheprovider -rs` | **183 passed, 2 skipped** (both `test_session.py:927`, symlinks unavailable: WinError 1314) |
| `… -m pytest -q -p no:cacheprovider tests/test_session.py tests/test_classification_validation.py tests/test_validation_integration.py` | **119 passed, 2 skipped** |

New tests in `e5a7a06`:
- `test_invalid_transaction_corrections_are_rejected_atomically`
- `test_ambiguous_amount_flag_cannot_be_accepted_by_plan`
- `test_ambiguous_source_rejects_amount_correction`

**Gap:** the second test builds a record that *still carries* `amount_conflict`. It does not exercise `PATCH {accept:true}`, which clears the flags (see DA-7 below).

**Implementation inspected:**
- `routes/session.py` `correct_document`: every validation runs **before** any mutation (atomic):
  - forbidden and unknown fields;
  - category enum and kind/category contradiction;
  - profile;
  - `accept` boolean, merchant type, ISO date, supported currency, parseable amount;
  - the amount must pass the scan's authoritative-total validator against the excerpt.
- After any successful PATCH, `accept:true` still sets `review_flags = []` and `status = "ok"`.
- `orchestrator._build_plan`: a row is accepted only when no amount-related flag is present. It still uses `amount = c.get("amount") or _parse_amount(c.get("amount_text"))`.

## Stage 2: setup

- **Roots** (new, under `%LOCALAPPDATA%\Temp\ghostos-docaware`): `DA67-L` (live) and `DA67-M` (in-process). Both have the same six files under the prefix `d67/`.
- **Canary:** `DA67-canary/canary.txt`.
- **Hashes and expected amounts:** [`setup/manifest.json`](setup/manifest.json).

| File | Expected accepted amount |
|---|---|
| `d67/receipts/tibay-hardware-receipt.csv` (valid receipt) | PHP 2145.00 |
| `d67/archive/2026/invoice.pdf` (valid invoice, Carabao) | PHP 3470.00 |
| `d67/receipts/bayside-office-mart.pdf` (conflicting totals) | none (must not be counted) |
| `d67/misc/card-statement-sep2026.pdf` (statement) | none |
| `d67/invoices/INV-1043_Pixelforge_Studio.pdf` | PHP 18648.00 |
| `d67/receipts/sunbeam-cafe-receipt.pdf` | PHP 683.20 |

**Methods:**
- **LIVE:** the real backend `127.0.0.1:8000` with the live `qwen3:4b-instruct` (scan `scan_01f5e1f4a0d0`). The server log shows 1 scan, 20 PATCH and 0 approve/undo.
- **INPROCESS:** the production app via FastAPI `TestClient` with a **mocked classifier** and its own in-memory store, so `plan_revision` and the plan snapshot can be read directly.
- **The CSV** was *prepared* with the production `render_report` from the final plan rows. **No approval was made**, so no committed CSV exists.

## Amount evidence (live scan)

| File | Status | Validated `amount` | Model `amount_text` | Flags |
|---|---|---|---|---|
| Pixelforge | ok | **18648.00** | `PHP 18,648.00` | — |
| Sunbeam | ok | **683.20** | `PHP 683.20` | — |
| Tibay | ok | 2145.00 | `2145.00` | — |
| Carabao invoice | ok | 3470.00 | `PHP 3,470.00` | — |
| Bayside | needs_review | **null** | `PHP 1,520.00` | `amount_conflict` |
| Card statement | needs_review | null | `PHP 5,391.06` | `amount_conflict`, `missing_merchant`, `non_transactional_document`, `transaction_fields_on_non_transactional` (kind `statement`, profile `reference`, category `invoice`) |

## Results

| ID | Area | Method | Request / check | Expected | Actual | Status | Owner |
|---|---|---|---|---|---|---|---|
| E1–E4 | Evidence | LIVE | Pixelforge, Sunbeam, Tibay, Carabao amounts | ok, expected amount | as expected | PASS | — |
| E5 | Evidence | LIVE | Bayside flagged | `amount_conflict`, amount null | as expected | PASS | — |
| E6 | Evidence | LIVE | Card statement not one expense | non-transaction profile, no accepted row | `statement`/`reference`, no row | PASS | — |
| **V1** | DA-6 | LIVE | `{amount:"abc"}` | 422; record and plan unchanged | 422 `amount must be a parseable monetary value`; unchanged | **PASS** | — |
| **V2** | DA-6 | LIVE | `{date:"2026-13-45"}` | 422; unchanged | 422 `date must be an ISO date (YYYY-MM-DD)`; unchanged | **PASS** | — |
| **V3** | DA-6 | LIVE | `{currency:"XYZ"}` | 422; unchanged | 422 `currency must be a supported currency code`; unchanged | **PASS** | — |
| **V4** | DA-6 | LIVE | `{amount:"9999.99"}` (contradicts the source) | 422; unchanged | 422 `amount correction is not supported by validated source evidence`; unchanged | **PASS** | — |
| V5–V9 | DA-6 | LIVE | `destination_relative_path` / `operations` / `field_profile` / `editable_fields` / `allowed_fields` | 422; unchanged | 422 `Unsupported backend-controlled fields: …`; unchanged | PASS | — |
| V10 | DA-6 | LIVE | `{accept:"yes"}` | 422 | 422 `accept must be a boolean`; unchanged | PASS | — |
| V11, G2, M2 | Filesystem | LIVE / INPROCESS | after all steps | roots and canary unchanged | unchanged | PASS | — |
| **RV1–RV4** | Stage 5 | INPROCESS (store read) | rejected `amount:"abc"`, `currency:"XYZ"`, Bayside `amount:"1520.00"`, `field_profile` | 422; `plan_revision`, snapshot, classification, flags, status, `user_corrected` unchanged | 422; revision 0→0; snapshot and record unchanged | **PASS** | — |
| RV5 | Stage 5 | INPROCESS | snapshot still current after rejections | `session_revision == plan_revision` | 0 == 0 | PASS | — |
| RV6 | Stage 5 | INPROCESS | valid correction `{amount:"683.20"}` | 200; revision bumped, snapshot stale (approve → 409) | 200; snapshot 0 vs revision 1 | PASS | — |
| **B1/B2** | DA-7 | LIVE | Bayside `{amount:"1250.00"}` / `{amount:"1520.00"}` | 422 (source ambiguous) | 422 `not supported by validated source evidence`; unchanged | **PASS** | — |
| S1 | DA-7 | LIVE | Sunbeam `{amount:"610.00"}` (subtotal) | 422 | 422; unchanged | PASS | — |
| P1 | DA-7 | LIVE | Pixelforge `{amount:"18500.00"}` (subtotal) | 422 | 422; unchanged | PASS | — |
| S2 | DA-7 | LIVE | Sunbeam `{amount:"683.20"}` (source-supported) | 200 | 200; amount 683.20 | PASS | — |
| C1/C2 | DA-7 | LIVE | Statement `{amount:"5391.06"}` / `{category:"invoice", accept:true}` | 422 | 422 `document_kind 'statement' cannot use transaction category 'invoice'` | PASS | — |
| C3 | DA-7 | LIVE | Statement `{accept:true}` | no accepted row | 422 (same contradiction check: model category `invoice` + kind `statement`); no row | PASS | — |
| **B3** | **DA-7** | **LIVE** | **Bayside `{accept:true}` (no amount)** | **no accepted row; nothing added to totals** | **200; flags cleared; plan row `accepted` with amount `1520.00`; totals PHP 26466.20** | **FAIL** | **Dev 1** |
| **M1** | **DA-7** | INPROCESS mocked | same, deterministic | no accepted row | **200; stored amount null; row `accepted` 1520.00** | **FAIL** | **Dev 1** |
| **R1** | Report | LIVE + `render_report` | prepared CSV rows | Tibay, Carabao, Pixelforge, Sunbeam only | **+ `d67/receipts/bayside-office-mart.pdf`** | **FAIL** (consequence of B3) | Dev 1 |
| **R2** | Report | LIVE + `render_report` | totals recomputed from the CSV | **PHP 24946.20** (2145.00 + 3470.00 + 18648.00 + 683.20) | CSV PHP **26466.20**; plan PHP 26466.20 (**+1520.00**) | **FAIL** (consequence of B3) | Dev 1 |
| **R3** | Report | LIVE | Bayside and statement absent from the CSV | absent | **Bayside present** | **FAIL** (consequence of B3) | Dev 1 |
| G1 | Plan | LIVE | destinations from the backend map, relative, in-root, unique | yes | `Invoices/2026-09/…`, `Invoices/2026-10/…`, `Receipts/2026-09/…`, `Uncategorized/card-statement-sep2026.pdf` | PASS | — |
| **UI1** | UI contract | LIVE | Check-screen "Looks right" payload with empty fields `{amount:null, date:null, merchant:null, accept:true}` on a valid invoice | record | **422 `amount must be a parseable monetary value`** | RECORDED (new finding) | Dev 1 + Dev 3 |

**Totals:** 35 PASS · 5 FAIL (one root cause, DA-7 accept-as-is, plus its 3 report consequences and the in-process confirmation) · 1 RECORDED.

## Failures

### DA-7 (still open): accept-as-is revives a rejected amount (High; Dev 1)

**Reproduce (live):**
1. Scan a copy containing `receipts/bayside-office-mart.pdf`. Result: `needs_review`, `amount_conflict`, `amount: null`, `amount_text: "PHP 1,520.00"`.
2. `PATCH /api/documents/{id}` with body `{"accept": true}`. Result: 200; `review_flags: []`; `status: ok`.
3. `GET /api/scans/{scan}/plan`. Result: Bayside row `accepted` with amount `1520.00`, and the totals include it.

**Cause:** `accept:true` clears `review_flags`, so the new flag gate in `_build_plan` no longer sees `amount_conflict`. The plan then falls back to `_parse_amount(amount_text)` even though the validator rejected that amount.

**Suggested fix:**
- never use the raw `amount_text` fallback for a record whose validated `amount` is null after a scan (require an explicit, source-validated `amount` correction); **or**
- preserve amount-related flags (or a persistent "amount_unverified" marker) through `accept`.

Also add a test that goes through `PATCH {accept:true}`.

### UI1 (new): the Check screen's empty-amount payload is rejected (Medium; Dev 1 + Dev 3)

`FilesPage.tsx` sends `{amount: amount || null, date: date || null, merchant: merchant || null, accept: true}`. The backend now returns 422 for `amount: null`, so "Looks right · mark checked" fails for any transaction document whose amount field is empty, such as a receipt with conflicting totals or the uncertain aircon note. Either the UI should omit `amount` when it is empty, or the backend should treat `null` as "no change". Whatever is chosen, accept-as-is must not then revive a raw amount (DA-7).

## Comparison with previous findings

| Finding | Before (`9a909c7` / `3c60bb3`) | Now (`e5a7a06`) |
|---|---|---|
| **DA-6** invalid transaction corrections | `amount:"abc"`, `date:"2026-13-45"`, `currency:"XYZ"` stored with 200; bogus `XYZ` totals entry | **FIXED**: each rejected 422; record, flags, status, revision and snapshot unchanged |
| **DA-7** rejected amount revived | accept-as-is turned an ambiguous statement into an accepted 5391.06 row | **PARTLY FIXED**: amount corrections must match the source (Bayside 1250/1520, subtotals rejected); a statement can't take a transaction category. **Still OPEN**: accept-as-is on an ambiguous transaction document (Bayside) yields an accepted row at the rejected amount (PHP 1520.00) |
| Statement as an expense | possible via category or kind switches | category switch to `invoice`/`receipt` on a statement is now 422 (C2) |
| DA-5b, DA-2, DA-4, D1 | open | unchanged and separate (not retested) |
| F1 | closed | closed |

**Not tested:** committed CSV (no approval in this run), offline, symlinks (WinError 1314), browser UI.

## Evidence

`setup/manifest.json` · `live/scan_initial.json` · `live/amount_evidence.json` · `live/plan_initial.json` · `live/plan_final.json` · `live/prepared_report.csv` · `live/da6/*.json` (before/after record and plan per request) · `live/http_log.json` · `inprocess_mock_http_log.json` · `results.json` · `scripts/da6_da7_retest.py`
