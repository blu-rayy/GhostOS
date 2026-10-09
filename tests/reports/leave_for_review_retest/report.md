# "Leave for review" routing retest (`b584d92`)

**Owner:** Developer 4 (QA) · **Run:** 2026-10-10 · **Commit:** `b584d92` ("fix: route leave-for-review documents safely") · **Backend:** real, `127.0.0.1:8000`, `qwen3:4b-instruct` (live local model) · **Status:** complete. **Routing fix verified through API, preview, commit and undo** (API path; UI click NOT TESTED). One FAIL against the stated expectation (L2, review flags cleared by design) and one frontend mock mismatch for Dev 3.

Earlier QA reports are unchanged. D1 is kept separate (avoided with a unique `lv/` prefix and a single fresh scan).

## Stage 1: inspection

| Item | Finding |
|---|---|
| UI "Leave for review" payload | `{category: "uncertain", accept: true}` (`frontend/src/lib/viewModel.ts:40` `NON_TRANSACTION_DECISIONS.leave`, sent from `FilesPage.tsx:94`); asserted by `documentAware.test.ts:61` |
| UI "File it" payload | `{category: "other", accept: true}` (`viewModel.ts:39`) |
| Backend correction route | Accepts `category` and `accept` on any profile; `accept:true` sets `user_corrected=true`, **clears `review_flags`** and sets `status="ok"` |
| Planner (`orchestrator._build_plan`) | New branch `elif doc.user_corrected and category == "uncertain"` → **`Uncategorized/`** ("Left for human review"), placed **before** the non-transactional → `Other/` branch |
| Backend test | `test_explicit_leave_for_review_routes_uncategorized_through_commit` (new) |
| **Frontend demo mock (Dev 3)** | **Out of sync with the backend.** `frontend/src/api/mock.ts` and `documentAware.test.ts:80` still expect "leave" → **`Other/`**. In demo mode the plan shows `Other/`, while the button text says "Leave for review → Uncategorized/" and the real backend routes it to `Uncategorized/`. The mock also still rejects `document_kind` corrections (`documentAware.test.ts:115`), which the real backend accepts since `9a909c7`. |

## Stage 2: disposable root

- **Root:** `<TEST_BASE>/L2`, where `<TEST_BASE>` = `%LOCALAPPDATA%\Temp\ghostos-leave-review` (new).
- **Canary:** `<TEST_BASE>/outside-canary-2/canary.txt`.
- **Earlier attempt:** a first attempt stopped on a wrong repository path in the QA script **before any scan or API call** (the backend log showed 0 calls). It left an **empty** `<TEST_BASE>/L1` folder and `<TEST_BASE>/outside-canary/canary.txt`. They were not deleted or reused.

| File | Size | SHA-256 | Role |
|---|---|---|---|
| `lv/legal/lease-agreement-summary.pdf` | 1020 | `4538c2e2306137414f574f3a216ea56da1c71756255c94fbc6c506e5b00516f9` | unresolved → "Leave for review" |
| `lv/identity/birth-certificate.pdf` | 1095 | `df083a5d7500220e94e943891489ab6dc100a88a783426a351e864ef6c4edd1b` | non-transactional → "File it" (`other`) |
| `lv/receipts/sunbeam-cafe-receipt.pdf` | 1217 | `aab1c6fe32a7f119fcf15db2b96eabdd930c66337776a4324824e1ae6a8ed4c9` | transaction control |

Backend state before the run: 1 process, 0 scans and 0 corrections. After the run: exactly 1 scan, 2 PATCH, 0 approve/undo.

## Stage 3: results (scan `scan_6bdcb43ff537`)

| ID | Check | Expected | Actual | Status | Owner |
|---|---|---|---|---|---|
| S0 | Live classification matches the scenario | lease and birth certificate unresolved and non-transactional; receipt ok, transaction | lease `needs_review`/`legal`/`none`; birth `needs_review`/`identity_or_civil`/`none`; receipt `ok`/`receipt`/`transaction` | PASS | — |
| S1 | Scan and first preview write nothing | unchanged | unchanged | PASS | — |
| **L1** | "Leave for review" via the exact UI payload | 200; category `uncertain`; kind/profile unchanged; no transaction values | 200; `uncertain`, `legal`, `none`; merchant/date/amount/currency null | **PASS** | — |
| **L2** | Review flags/status after "Leave for review" | review state preserved | **`status: ok`, `user_corrected: true`, `review_flags: []`**. `accept:true` clears the flags by design; the review intent survives only as category `uncertain` and the `Uncategorized/` route | **FAIL** (against the stated expectation; behaviour is by design) | Dev 1 + team (decision) |
| F1 | "File it" via the exact UI payload | 200; category `other`; no transaction values | 200; `other`, `identity_or_civil`, `none`, `ok` | PASS | — |
| D1g | Both decisions landed on this scan | yes | yes | PASS | — |
| **P1** | Lease destination | `Uncategorized/lease-agreement-summary.pdf` | `Uncategorized/lease-agreement-summary.pdf` ("Left for human review") | **PASS** | — |
| **P2** | Birth certificate destination (control) | `Other/birth-certificate.pdf` | `Other/birth-certificate.pdf` ("Non-transactional document") | **PASS** | — |
| P3 | Receipt destination (control) | `Receipts/2026-09/sunbeam-cafe-receipt.pdf` | as expected | PASS | — |
| P4 | Report rows | only the receipt, PHP 683.20 | `[(lv/receipts/sunbeam-cafe-receipt.pdf, accepted, 683.20, PHP)]` | PASS | — |
| P5 | Mode and blocking count | `blocking`, 0 | `blocking`, 0 | PASS | — |
| P6 | Corrections and preview write nothing | unchanged | unchanged | PASS | — |
| UI | Actual browser click on "Leave for review" | observed | not performed (no browser automation) | **NOT TESTED** | QA |

Evidence: `setup/manifest.json`, `scan_initial.json`, `plan_before_decisions.json`, `patch_leave.json`, `patch_file_it.json`, `plan_for_review.json`, `http_log.json`, `results.json`.

## Stage 4: approval and undo (human-confirmed)

Evidence: [`approve_undo/`](approve_undo/) (`approve_response.json`, `undo_response.json`, `report_copy.csv`, snapshots before, after approval and after undo, `http_log.json`, `results.json`). The backend log for the whole test shows exactly 1 scan, 2 PATCH, 1 approve (200) and 1 undo (200).

| ID | Check | Actual | Status |
|---|---|---|---|
| Q1–Q3 | Re-fetched plan | `scan_6bdcb43ff537` / `plan_scan_6bdcb43ff537`, mode `blocking`, **byte-identical** to the reviewed preview, 3 operations, 0 blocking | PASS |
| Q4–Q6 | Hashes, destinations free/contained/unique, canary and base folder | as recorded; unchanged | PASS |
| S1 | `POST approve {}` | `HTTP 200 {"batch_id":"batch_f11c33ea8d18","moved":3,"failed":[],"report_relative_path":"GhostOS Reports/expenses-202610092030.csv"}` | PASS |
| **M1** | Exact-case destinations with original SHA-256 | **`Uncategorized/lease-agreement-summary.pdf`** (`4538c2e2…`), `Other/birth-certificate.pdf` (`df083a5d…`), `Receipts/2026-09/sunbeam-cafe-receipt.pdf` (`aab1c6fe…`) | **PASS** |
| M2–M5 | No overwrite, nothing in source folders, no temporary file, no writes outside L2 | as expected | PASS |
| R1 | CSV rows | exactly `lv/receipts/sunbeam-cafe-receipt.pdf, 683.20, PHP` | PASS |
| R2 | Total recomputed from the CSV | PHP 683.20 | PASS |
| U1 | `POST undo` | `HTTP 200 {"restored":3,"conflicts":[]}` | PASS |
| U2 | Original paths and SHA-256 | 3/3 restored | PASS |
| U3 | No organized files remain | only the report | PASS |
| U4 | Report left after undo (observed) | `GhostOS Reports/expenses-202610092030.csv` | RECORDED |
| U5 | Empty folders left after undo (observed) | `Other`, `Receipts/2026-09`, `Uncategorized` | RECORDED |
| U6 | Outside L2 after undo | unchanged | PASS |

## Summary of statuses

- **PASS:** S0, S1, L1, F1, D1g, P1–P6, Q1–Q6, S1 (approve), M1–M5, R1–R2, U1–U3, U6.
- **FAIL:** L2 (review flags and status not preserved after "Leave for review"; by design of `accept:true`; needs a team decision).
- **NOT TESTED:** the real browser click (a separate, human-driven test on its own fresh folder).
- **For Dev 3:** the frontend demo mock routes "leave" to `Other/` (out of sync with the backend), and rejects `document_kind` corrections.
- **Separate and open:** D1; DA-5b, DA-6, DA-7 ([DA-5 retest](../document_aware_review/da5_retest_3c60bb3/report.md)).

## Reviewed and approved plan

| | |
|---|---|
| Root | `%LOCALAPPDATA%\Temp\ghostos-leave-review\L2` |
| Scan / plan | `scan_6bdcb43ff537` / `plan_scan_6bdcb43ff537` |
| Mode | `blocking` (default); approve body `{}`; `blocking_review_count = 0` |
| Operations | `lv/legal/lease-agreement-summary.pdf` → `Uncategorized/lease-agreement-summary.pdf` · `lv/identity/birth-certificate.pdf` → `Other/birth-certificate.pdf` · `lv/receipts/sunbeam-cafe-receipt.pdf` → `Receipts/2026-09/sunbeam-cafe-receipt.pdf` |
| Expected changes | Create `Uncategorized/`, `Other/`, `Receipts/2026-09/` and `GhostOS Reports/expenses-<stamp>.csv` (1 row, PHP 683.20); move 3 files; `lv/legal`, `lv/identity` and `lv/receipts` left empty |
