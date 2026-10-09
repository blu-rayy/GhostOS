# Uncategorized destination retest

**Owner:** Developer 4 (QA) · **Run:** 2026-10-10 (UTC 2026-10-09 19:4x) · **Commit:** `0dfdb65` ("standardize uncategorized destinations") · **Model:** `qwen3:4b-instruct` (local Ollama) · **Result: PASS (49/49 checks; no defects in the reported change)**

Contract and plan: [`test_plan.md`](test_plan.md). Scripts: [`scripts/`](scripts/). Earlier QA evidence is unchanged.

## Environment

| | |
|---|---|
| Backend | One uvicorn process for the whole retest. The server log shows exactly: 2 scans · 1 PATCH (the licence decision) · 3 approve calls (two refused on root A, one 200 on root B) · 1 undo. No other traffic |
| Test base `<TEST_BASE>` | `%LOCALAPPDATA%\Temp\ghostos-uncategorized` (new) |
| Roots | `A-normal` (`inbox-a/…`) and `B-partial` (`inbox-b/…`). The unique top-level folders keep every `file_id` distinct from other scans (D1 workaround) |
| Outside-root check | `<TEST_BASE>/outside-canary/canary.txt` plus the base folder's children list |
| Inputs | Byte-for-byte copies of `tests/fixtures/sample_folder` files, plus one **synthetic 0-byte** `inbox-a/scans/empty-scan.txt`. Hashes in [`setup/manifest.json`](setup/manifest.json) |
| Network | On (offline is out of scope) |

## Partial-mode contract (inspected, then confirmed by observation)

- **Preview:** `GET /api/scans/{id}/plan?mode=partial`.
- **Approve:** `POST /api/plans/{plan_id}/approve` with `{"mode":"partial"}`. The mode must match the previewed snapshot; otherwise 409.
- **Partial mode** skips the unresolved-review blocker and **moves every planned file, including unresolved ones into `Uncategorized/`**. Unresolved documents produce no report row.
- **The frontend has no partial-mode control** (API only).

## Results

### Stage 3: root A, blocking mode (`scan_8428a60ab5da` / `plan_scan_8428a60ab5da`)

| ID | Check | Expected | Actual | Status |
|---|---|---|---|---|
| N0 | Root and canary match the setup | identical | identical | PASS |
| N1.1 | `inbox-a/receipts/sunbeam-cafe-receipt.pdf` | `Receipts/2026-09/…` | `Receipts/2026-09/sunbeam-cafe-receipt.pdf` (ok) | PASS |
| N1.2 | Birth certificate (undecided, non-transactional) | `Uncategorized/` | `Uncategorized/birth-certificate.pdf`; flags `missing_evidence_quote`, `non_transactional_document` | PASS |
| N1.3 | Bayside (unresolved: conflicting totals) | `Uncategorized/` | `Uncategorized/bayside-office-mart.pdf`; `amount_conflict` | PASS |
| N1.4 | Aircon note (uncertain / missing date) | `Uncategorized/` | `Uncategorized/aircon-payment-note.txt`; `missing_amount`, `missing_merchant`, `missing_date` | PASS |
| N1.5 | Synthetic empty file (unreadable) | `Uncategorized/` | `Uncategorized/empty-scan.txt`; `model_error`; no classification | PASS |
| N1.6 | No `Unsorted/` | none | none | PASS |
| N1.7 | Non-transactional document not counted | no report row | none | PASS |
| N1.8 | Review warnings present | every unresolved document flagged | yes (4 documents) | PASS |
| N1.9 | Preview writes nothing | identical | identical | PASS |
| N2 | `POST approve {}` with `blocking_review_count = 4` | 409 | `409 {"detail":"Plan has 4 unresolved review items"}`; filesystem and canary unchanged | PASS |
| N3 | `POST approve {"mode":"partial"}` against the blocking preview | 409 mode mismatch | `409 {"detail":"Plan mode is 'blocking' but approval requested 'partial'; refresh the preview before approval"}`; unchanged | PASS |

Evidence: [`stage3/`](stage3/) (scan, blocking plan, snapshots), `stage3_stage4_http_log.json`, `stage3_stage4_results.json`.

### Stage 4: root B, partial mode (`scan_1cabbc9828aa` / `plan_scan_1cabbc9828aa`)

**Pre-approval** (evidence: [`stage4_preapproval/`](stage4_preapproval/)):

| ID | Check | Actual | Status |
|---|---|---|---|
| P0 | Root and canary match the setup | identical | PASS |
| P1 | Sunbeam and Tibay classified cleanly | ok, receipt/transaction, PHP 683.20 (2026-09-21) / PHP 2145.00 (2026-09-27) | PASS |
| P2a | Licence before the decision | `identity_or_civil`, profile `none`, all transaction fields null | PASS |
| P2b | "File it" `{"category":"other","accept":true}` | 200; category `other`; kind and profile unchanged; **no transaction values**; `user_corrected: true` | PASS |
| P2c | D1 guard: the decision landed on root B's own scan | `user_corrected` true on `scan_1cabbc9828aa` | PASS |
| P3 | Partial preview destinations (see the table below) | all 5 as expected; mode `partial`; no `Unsorted/` | PASS |
| P4 | Report rows and totals | 2 accepted rows; PHP 2828.20; `blocking_review_count = 2` (lease, Bayside); flags visible | PASS |
| P5 | Root B, root A and canary unchanged | identical | PASS |

**Approval** (human-confirmed; evidence: [`stage4_5_execute/`](stage4_5_execute/)):
- **Pre-checks Q1–Q9: all PASS.** IDs unchanged; plan byte-identical to the reviewed preview; mode `partial`; 5 operations; both unresolved documents → `Uncategorized/`; original hashes intact; destinations inside the root, free and unique; canary and root A unchanged.
- `POST /api/plans/plan_scan_1cabbc9828aa/approve {"mode":"partial"}` →
  ```json
  HTTP 200 {"batch_id":"batch_1ce449203861","moved":5,"failed":[],"report_relative_path":"GhostOS Reports/expenses-202610091949.csv","committed_at":"2026-10-09T19:49:13.500680+00:00"}
  ```

| Original | Approved destination | Actual on disk (exact case) | SHA-256 |
|---|---|---|---|
| `inbox-b/receipts/sunbeam-cafe-receipt.pdf` | `Receipts/2026-09/sunbeam-cafe-receipt.pdf` | identical | `aab1c6fe32a7f119…` ✓ |
| `inbox-b/receipts/tibay-hardware-receipt.csv` | `Receipts/2026-09/tibay-hardware-receipt.csv` | identical | `5cc008a23a59b8b2…` ✓ |
| `inbox-b/identity/drivers-license-record.txt` | `Other/drivers-license-record.txt` | identical | `a834865ede0b6a3b…` ✓ |
| `inbox-b/legal/lease-agreement-summary.pdf` | `Uncategorized/lease-agreement-summary.pdf` | identical | `4538c2e230613741…` ✓ |
| `inbox-b/receipts/bayside-office-mart.pdf` | `Uncategorized/bayside-office-mart.pdf` | identical | `3b11f36ab288c9fc…` ✓ |

| ID | Check | Status |
|---|---|---|
| S1 | Partial approval: 5 moved, 0 failed | PASS |
| M1 | Exact-case destinations with original SHA-256 | PASS |
| M2 | No overwrite (5 distinct files, each with its own bytes) | PASS |
| M3 | No `Unsorted/` folder | PASS |
| M4 | No organized file inside a source folder | PASS |
| M5 | No temporary report file left | PASS |
| M6 | Nothing written outside root B; root A and canary unchanged | PASS |

**CSV** (`GhostOS Reports/expenses-202610091949.csv`; copy [`stage4_5_execute/report_copy.csv`](stage4_5_execute/report_copy.csv)):

```
source_file,merchant,date,category,amount,currency
inbox-b/receipts/sunbeam-cafe-receipt.pdf,…,2026-09-21,receipt,683.20,PHP
inbox-b/receipts/tibay-hardware-receipt.csv,…,2026-09-27,receipt,2145.00,PHP
```

| ID | Check | Actual | Status |
|---|---|---|---|
| R1 | Inside root B; BOM, CRLF, 6-column header | yes | PASS |
| R2 | Exactly two accepted receipt rows | Sunbeam 683.20 PHP, Tibay 2145.00 PHP | PASS |
| R3 | Licence, lease and Bayside not in the CSV | absent | PASS |
| R4 | Totals **recomputed from the CSV rows** | PHP **2828.20** (683.20 + 2145.00) | PASS |

### Stage 5: undo

`POST /api/batches/batch_1ce449203861/undo` → `HTTP 200 {"batch_id":"batch_1ce449203861","restored":5,"conflicts":[]}`

| ID | Check | Actual | Status |
|---|---|---|---|
| U1 | Undo succeeds with 0 conflicts | restored 5 | PASS |
| U2 | All 5 original paths (exact case) with original SHA-256 | 5/5 identical to the setup manifest | PASS |
| U3 | No organized files remain | only the report remains | PASS |
| U4 | Source folders contain only their originals | yes | PASS |
| U5 | **Report files remaining (observed)** | `GhostOS Reports/expenses-202610091949.csv` | RECORDED |
| U6 | **Empty folders remaining (observed)** | `Other`, `Receipts/2026-09`, `Uncategorized` | RECORDED |
| U7 | Outside root B unchanged after undo | yes | PASS |

## Observations (no defect in the reported change)

| # | Severity | Owner | Observation |
|---|---|---|---|
| O1 | Decision / UX | Dev 1 + Dev 3 | **Partial mode moves unresolved documents too**, into `Uncategorized/`, without a review decision. It is safe and matches Developer 1's tests, but "partial" could be read as "move only the resolved files". It needs clear wording if it is ever exposed in the UI. It is currently API-only. |
| O2 | Low (carried F2) | Dev 1 | Undo leaves the report CSV and the generated empty folders (`Other`, `Receipts/2026-09`, `Uncategorized`). |
| O3 | Medium (carried DA-2) | Dev 2 | The aircon payment note is still classified as a `receipt` (transaction), but it is safely flagged and routed to `Uncategorized/`. |
| O4 | Cosmetic | Dev 1 | "unsorted" survives only in the test name `test_partial_mode_routes_unsorted_…` and a local variable; no production code uses `Unsorted/`. |

## Still open / not tested

- **D1** (cross-scan document IDs): still open and separate. It was avoided here by unique folder names and is not retested.
- **F1:** closed. Exact-case destinations held again in this run.
- **Document-aware findings DA-5 and the kind/reclassification decisions:** tracked in [`../document_aware_review/regression_9a909c7_report.md`](../document_aware_review/regression_9a909c7_report.md); not part of this retest.
- **Symlinks:** NOT TESTED (WinError 1314). **UI:** NOT TESTED (no partial mode in the UI). **Offline:** NOT TESTED.

## Reproduce

Run from the repo root with one fresh backend, and confirm each human step:

```powershell
backend\.venv\Scripts\python.exe -B tests\reports\uncategorized_retest\scripts\setup_roots.py
backend\.venv\Scripts\python.exe -B tests\reports\uncategorized_retest\scripts\stage3_and_stage4_preapproval.py
# review stage4_preapproval/plan_partial_for_review.json, then (IDs are hard-coded):
backend\.venv\Scripts\python.exe -B tests\reports\uncategorized_retest\scripts\stage4_5_partial_approve_undo.py
```

The scripts refuse to reuse existing roots or evidence folders.
