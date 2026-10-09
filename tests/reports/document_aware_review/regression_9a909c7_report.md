# Document-aware regression on `9a909c7`: results and incident

**Owner:** Developer 4 (QA) · **Run:** 2026-10-10 (UTC 2026-10-09 19:10) · **Commit:** `9a909c76fc366c1c2fccfcec9f73564b891e5346` · **Model:** `qwen3:4b-instruct` (local Ollama) · **Scope:** non-destructive (no approve, undo or file move)

Evidence: [`regression_9a909c7/`](regression_9a909c7/) (`environment.json`, `live_http_log.json`, `mock_http_log.json`, `live_scan_initial.json`, `live_plan_initial.json`, `results.json`). Script: [`tests/integration/document_aware_regression_9a909c7.py`](../../integration/document_aware_regression_9a909c7.py). The original [document-aware report](report.md), the F1 records and the D1 records are unchanged.

## Summary

- **DA-5 still fails** in the path a real scan takes. When the model returns no `document_kind`, the scan stores **no kind key**, so the record falls back to the legacy rule. A statement labelled `invoice` then gets profile `transaction`. **One explicit "accept as-is" makes it count as an expense and plans it into `Invoices/2026-09/`.** This was reproduced with a controlled, mocked model response through the production API. It is a **blocking safety defect under the QA rules** (a statement counted as an expense), but only after a user accepts.
- **The live tests A, C and D are INVALID.** A second scan of the **committed fixture folder** (`tests/fixtures/sample_folder`, `scan_1d183cc90511`) started on the same backend about 30 seconds before this run, most likely from the UI. Because of **D1** (corrections matched by `file_id` across every scan), **all of this run's live corrections were applied to that session, not to the disposable `R2` scan.** No file was moved or changed (`generate_sample_folder.py --check`: 26/26 identical), and no approve or undo was called.
- The explicit-null unit check (B1) passes: the explicit-null fix itself works.

## Incident: D1 cross-scan contamination (live part)

| | |
|---|---|
| Other session | `scan_1d183cc90511`, root `…/GhostOS/tests/fixtures/sample_folder` (committed fixtures), 25 documents, started `2026-10-09T19:09:46Z`; **not started by this script** |
| This run's scan | `scan_424cfd725bc9`, root `<TEST_BASE>/R2` (5 copied files) |
| Mechanism | `PATCH /api/documents/{file_id}` → `session_store.find_document()` returns the **first** scan containing that `file_id`; `file_id = md5(relative_path)[:8]` is identical for the same relative paths |
| Effect on `scan_1d183cc90511` (in memory only) | `identity/drivers-license-record.txt` → category `receipt`, accepted · `misc/card-statement-sep2026.pdf` → category `invoice`, accepted · `misc/bank-statement-oct2026.txt` → kind `receipt` (profile `transaction`), merchant/date/amount `9120.50`/currency set, accepted · `identity/birth-certificate.pdf` → kind `receipt` (not accepted) |
| Effect on `R2` scan | none: every document still `needs_review`, `user_corrected: false`; its plan never changed |
| Filesystem | unchanged. `R2` byte-identical (A4, D4); committed fixtures identical (generator check); 0 approve/undo calls in the server log |
| Current risk | `scan_1d183cc90511` is still in backend memory, **pointing at the committed fixture folder**, with QA's test corrections mixed in. Its plan is blocked (`blocking_review_count=10`). **It must not be approved**: approving would move files inside the repository's fixture folder |

D1 is no longer theoretical. It caused real cross-session contamination as soon as two clients used the backend at once. **Proposed severity: High (blocking for any multi-session or demo use).**

## Results

| ID | Test | Method | Input | Expected | Actual | Status | Owner |
|---|---|---|---|---|---|---|---|
| A1/A2/A3 | DA-1 category switch (card statement → `invoice`; ID → `receipt`) | live | PATCH `{category, accept:true}` | record acceptance; route to `Other/`; no report row | **Applied to the wrong session (D1).** In that session the corrections were **accepted (HTTP 200)**, both documents planned to **`Other/`**, and no report row. The `R2` plan was unaffected | **BLOCKED** (invalid run) · observed behaviour consistent with DA-1 routing fixed; acceptance itself is a **CONTRACT DECISION REQUIRED** | Dev 1 |
| B1 | DA-5, stored record with explicit `document_kind: null` (category `invoice`, amount, date, status ok) | controlled unit (production `document_awareness` + `_build_plan`, constructed record) | — | profile `none`; no row; `Other/` | profile `none`; `Other/statement.txt`; no row; no totals | **PASS** | — |
| B2 | Legacy record (no `document_kind` key) | controlled unit | — | record behaviour | profile `transaction`; `Invoices/2026-09/`; row **accepted**; totals PHP 9120.50 | CONTRACT DECISION REQUIRED (legacy compatibility) | Dev 1 |
| **B3** | DA-5, **new scan, model returns `document_kind: null`** (bank and card statements, category `invoice`) | **MOCKED model response** through an in-process FastAPI `TestClient` (production routes, orchestrator, validator, plan builder; separate in-memory store; no real model) | mocked classification | profile `none`; not eligible; routed safely | Stored kind key **absent**; API reports kind `invoice`, profile **`transaction`**; `needs_review` (`amount_conflict`); row `needs_review` | **FAIL** | Dev 1 |
| **B4** | Same, then the user accepts as-is (`{accept:true}`, the Check screen's "Looks right · mark checked") | MOCKED, in-process | PATCH `{accept:true}` | statement never counted | Bank statement: **`Invoices/2026-09/`, row accepted, totals PHP 9120.50**. Card statement: **`Invoices/2026-09/`, row accepted, cumulative PHP 14511.56** | **FAIL (blocking safety rule: statement counted)** | Dev 1 |
| B5 | Mock folder unchanged | MOCKED | — | unchanged | unchanged | PASS | — |
| C1 | F6: `{document_kind:"receipt"}` on a birth certificate | live | PATCH | record behaviour | HTTP 200, kind `receipt`, profile `transaction`. **Applied to the other session (D1)** | CONTRACT DECISION REQUIRED (behaviour recorded; run otherwise invalid) | Dev 1 + team |
| C2 | `{document_kind: 5}` | live | PATCH | record behaviour | HTTP 422 `document_kind must be a supported string or null` | CONTRACT DECISION REQUIRED | Dev 1 + team |
| D1 | Amount on a statement before any kind change | live | PATCH `{amount, currency, accept}` | 422 | HTTP 422 `profile 'reference' does not allow transaction corrections` (validation runs before the lookup side effects, so the result is valid) | **PASS** | — |
| D2/D3 | Statement → kind `receipt`, then merchant/date/amount/currency + accept | live | PATCH ×2 | record eligibility | Both HTTP 200, applied to **the other session**: kind `receipt`, profile `transaction`, amount 9120.50 accepted; category still `other` → planned `Other/`, **no report row** | **BLOCKED** (invalid run) · CONTRACT DECISION REQUIRED | Dev 1 + team |
| A4, D4 | `R2` folder unchanged | live | — | unchanged | unchanged | PASS | — |

**Statement reclassification (D):** from the code and the observed responses, a statement becomes **countable** after three explicit API corrections:
1. `{document_kind:"receipt"}` (or `invoice`);
2. `{category:"receipt"}` (or `invoice`);
3. merchant, date, amount, currency and `accept:true`.

D3 omitted the category change, which is why it was not counted. The UI's non-transactional panel sends only `{category, accept}` decisions and has **no kind control**, so today this path exists through the API only. Whether a user may turn a statement into a receipt is a **contract decision**.

## Recommended next actions

1. **Now (everyone):** do **not** approve `scan_1d183cc90511`. It points at the committed `tests/fixtures/sample_folder` and contains QA's test corrections. Discard it by restarting the backend (in-memory state), coordinated with whoever is using the UI. Never scan or approve the committed fixture folder in the app; scan a copy instead.
2. **Dev 1, D1 (High):** scope document IDs to a scan, e.g. `PATCH /api/scans/{scan_id}/documents/{file_id}`, or make `file_id` unique per scan. Dev 3 updates the client.
3. **Dev 1, DA-5 (blocking):** when the model returns no kind, store `document_kind: null` explicitly (the key must be present) so the conservative `none` profile applies. Keep the category-based fallback only for records created before this field existed.
4. **Team:** decide whether users may change `document_kind` (C) and reclassify statements as receipts (D), and whether a contradictory category correction should be rejected or only neutralised (A).
5. **QA:** after a coordinated backend restart with no other clients, re-run the live part (A, C, D) on a fresh folder.

---

## Re-run after a coordinated backend restart (valid live results)

The backend was restarted with permission, which discarded `scan_1d183cc90511` (now HTTP 404). The script was re-run with `--suffix _rerun1` (new folders `<TEST_BASE>/R2_rerun1` and `R2-mock_rerun1`; evidence in [`regression_9a909c7_rerun1/`](regression_9a909c7_rerun1/)). The server log shows **exactly 1 scan (this run) and 0 approve/undo calls**. A new guard (**A0**) confirmed that the corrections landed on this run's own scan (`scan_4c743136da13`).

**Totals: 9 PASS, 4 FAIL, 7 CONTRACT DECISION REQUIRED**, plus one follow-up step for D.

| ID | Test | Actual (live unless noted) | Status |
|---|---|---|---|
| A0 | D1 guard | corrections on this scan: card statement ✓, driver's licence ✓ | PASS |
| A1 | Category switch `{category:"invoice"/"receipt", accept:true}` on a statement and an ID | **Accepted (HTTP 200)**; stored category changes, kind and profile unchanged (`statement`/`reference`, `identity_or_civil`/`none`) | CONTRACT DECISION REQUIRED |
| A2 | Routing after the switch | **`Other/card-statement-sep2026.pdf`**, **`Other/drivers-license-record.txt`**; no report rows | **PASS** (DA-1 misfiling fixed) |
| A3 | Totals | `{PHP: 683.20}` (receipt only) | PASS |
| A4, D4 | Folder unchanged | unchanged | PASS |
| C1 | `{document_kind:"receipt"}` on a birth certificate | HTTP 200 → kind `receipt`, profile **`transaction`**, still `needs_review`; plan `Needs Review/`; no row | CONTRACT DECISION REQUIRED |
| C2 | `{document_kind: 5}` | HTTP 422 `document_kind must be a supported string or null` | CONTRACT DECISION REQUIRED (behaviour recorded) |
| D1 | Amount on a statement before any kind change | HTTP 422 (`reference` profile) | PASS |
| D2 | Statement → `{document_kind:"receipt"}` | HTTP 200 → profile `transaction`, still `needs_review` | CONTRACT DECISION REQUIRED |
| D3 | + `{merchant, date, amount 9120.50, currency, accept}` | HTTP 200, status ok; category still `other` → `Other/`, **no report row** | CONTRACT DECISION REQUIRED |
| D3b | + `{category:"receipt", accept:true}` ([`d_step3_category.json`](regression_9a909c7_rerun1/d_step3_category.json)) | HTTP 200 → **report row accepted PHP 9120.50; totals PHP 9803.70; planned to `GhostOS Organized/Receipts/2026-09/`**; folder unchanged | CONTRACT DECISION REQUIRED |
| B1 | Explicit `document_kind: null` stored record (unit) | profile `none`, `Other/`, no row | PASS |
| B2 | Legacy record without a kind key (unit) | `transaction`, `Invoices/2026-09/`, accepted | CONTRACT DECISION REQUIRED |
| **B3** | New scan, model returns `null` kind (**MOCKED**, in-process) | stored kind key absent → profile **`transaction`** | **FAIL** |
| **B4** | …then `{accept:true}` (**MOCKED**) | bank statement **`Invoices/2026-09/`, accepted PHP 9120.50**; card statement accepted (cumulative PHP 14511.56) | **FAIL (blocking safety rule)** |
| B5 | Mock folder unchanged | unchanged | PASS |

**Exact user actions for a statement to count (D), all through the API:**
1. `PATCH {document_kind:"receipt"}`;
2. `PATCH {merchant, date, amount, currency, accept:true}`;
3. `PATCH {category:"receipt", accept:true}`.

The Check UI exposes none of these for a non-transactional document: it only sends `{category:"other"|"uncertain", accept:true}`. So today this needs direct API use. Whether it should be allowed is a contract decision.

**Conclusions on `9a909c7`:**
- **DA-1 misfiling: fixed.** Non-transactional documents are routed to `Other/` regardless of category. The correction is still accepted rather than rejected (a decision).
- **DA-5: the explicit-null case is fixed (B1), but the live scan path is still open (B3/B4).** When the model omits the kind, the record is treated as an expense after a single "accept as-is". This remains the top-priority backend fix.
- **D1:** confirmed in practice by the incident above. High priority.
- **C/D:** kind corrections enable full reclassification of a statement into a countable receipt via the API. **Team decision required.**
