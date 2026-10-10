# Final DA-7 + UI1 Integration Retest (6b7785b)

- **Tester:** Developer 4 (QA and integration)
- **Date:** 2026-10-10
- **Commit under test:** `6b7785b674ca1546374b623df2f51f9c5f6185f3` (main). Includes `a1b082a` (filed-uncounted), `6b7785b` (UI empty-amount guard), `1ff4db9` (frontend test-runner fix).
- **Mode:** NON-DESTRUCTIVE. No approval, no undo, no file movement. No production code changed.
- **Untracked user file:** `GhostOS_24_Hour_Product_and_Build_Plan_Reformatted.docx` left untouched (45,401 bytes, SHA-256 `BC9E6C67…D75C7B6`, last write 2026-10-09 17:29).

## Verdict

| Area | Result |
|---|---|
| DA-7 (Bayside conflicting amount, live model) | **FIXED.** `{accept:true}` → 422, record and plan unchanged; PHP 1,520.00 never enters rows or totals. |
| UI1 (empty amount in the real UI) | **PASS.** "Looks right" is disabled with a hint for amount-flagged transactions; a forced click sends no request. |
| Filed-uncounted (API) | **PASS** for a genuinely amount-less receipt (live and mocked): 200, `filed_uncounted`, never counted. |
| Filed-uncounted vs conflict guard | **FAIL (FU-1, Dev 1, Medium).** A Bayside-type conflict whose model output has *no* amount_text is filed uncounted and its `amount_conflict` flag is cleared (still not counted). |
| UI ↔ API contract | **Finding (FU-2, Dev 3 + Dev 1, Low/Medium).** The filed-uncounted outcome is unreachable from the Check screen. |

**Counts:** Stage 1 commands all green; API/in-process 31 PASS, 1 FAIL; UI 5 PASS; NOT TESTED: offline, symlink, Electron desktop window.

## Stage 1: baseline and commands

`git rev-parse HEAD` = `6b7785b…`; `git status --short` = only the untracked `.docx`.

**Inspection:**

- `a1b082a` `routes/session.py`: on `accept` for a transaction, if the request has no `amount` key, the stored `amount` is null and the stored `amount_text` is empty, the revalidation gate is **skipped** and the record becomes `review_disposition="filed_uncounted"`, `status="ok"`, flags cleared. Otherwise the full source revalidation from `0641adb` applies (422 on any finding). `session_store.py` adds the literal.
- `6b7785b` `FilesPage.tsx`: `needsAmountEntry` disables "Looks right" when the amount box is empty, the doc is not corrected, and any flag is in `amount_conflict, amount_unparseable, missing_amount, missing_currency, invalid_currency, currency_mismatch, evidence_not_found`; shows "Type the amount you actually paid to confirm it — or leave this file for review."
- `1ff4db9` `test/mockHarness.ts`: marks expected rejections handled before advancing fake timers.

| Command | Result |
|---|---|
| `backend> .venv\Scripts\python.exe -B -m pytest -q -p no:cacheprovider` | 189 passed, 2 skipped |
| `backend> … pytest -q tests/test_schemas.py tests/test_classification_validation.py tests/test_validation_integration.py tests/test_session.py` | 152 passed, 2 skipped |
| `frontend> npm run typecheck` | exit 0 |
| `frontend> npm run lint` | exit 0; 2 warnings (`no-useless-escape`, `src/lib/report.test.ts:39`) |
| `frontend> npm test` | 10 files, 44 tests passed, exit 0 |
| `frontend> npm run build` | built, exit 0 |

## Stage 2: restart and setup

- The previous backend (on `0641adb`) held only my DA-7 scans; its recent traffic was `/api/status` polls from the open frontend. It was stopped and restarted on `6b7785b`.
- `/api/status`: model `qwen3:4b-instruct`, `model_loaded: true`, `external_requests: 0`.
- Base `%LOCALAPPDATA%\Temp\ghostos-final-da7ui1` (`<TEST_BASE>`), created fresh, with outside-root canary `outside-canary/canary.txt`.
- Four roots, each with a unique prefix (D1 workaround): `API-L` (`fa/`, live API), `UI-L` (`fu/`, real frontend), `M` and `M2` (`fm/`, `fn/`, in-process mocked).

| File (each root) | Size | SHA-256 | Source |
|---|---|---|---|
| receipts/bayside-office-mart.pdf | 1124 | 3b11f36a…1d810f | fixture |
| invoices/INV-1043_Pixelforge_Studio.pdf | 1331 | a4a03b73…638cff7 | fixture |
| receipts/sunbeam-cafe-receipt.pdf | 1217 | aab1c6fe…edd4c9 | fixture |
| receipts/kanto-stall-cash-note.txt | 155 | 83743934…51c4ab21 | synthetic, fictional, written by the script (no amount anywhere) |

Full hashes: `setup/manifest.json`. All roots and the canary were unchanged after every part (L-G1, M-G1).

## Stage 3: DA-7 (live, scan `scan_49c55469383d`)

Initial records (`live/state_initial.json`):

| Doc | Status | Flags | amount | amount_text | Evidence |
|---|---|---|---|---|---|
| Bayside | needs_review | amount_conflict | null | "PHP 1,520.00" | "AMOUNT DUE: PHP 1,520.00" (verified) |
| Pixelforge | ok | — | 18648.00 | "PHP 18,648.00" | "Total Amount Due: PHP 18,648.00" |
| Sunbeam | ok | — | 683.20 | "PHP 683.20" | "FINAL TOTAL: PHP 683.20" |
| Cash note | needs_review | missing_amount | null | null | "Amount not written on this note" |

| ID | Request | Actual | Result |
|---|---|---|---|
| L-B1 | scan | Bayside untrusted: amount null, amount_conflict | PASS |
| L-B2 | Bayside `{"accept":true}` | 422 "Cannot accept transaction while source validation findings remain unresolved"; record and plan identical | PASS |
| L-B3 | Bayside `{"amount":"1520.00","accept":true}` | 422 "amount correction is not supported by validated source evidence"; unchanged | PASS |
| L-C1 | Pixelforge `{"amount":"18648.00","accept":true}` | 200; 18648.00; ok; `filed`; no flags | PASS |
| L-C2 | Sunbeam `{"amount":"683.20","accept":true}` | 200; 683.20; ok; `filed`; no flags | PASS |
| L-R1 | prepared CSV (production `render_report`, not committed) | Pixelforge 18648.00 PHP; Sunbeam 683.20 PHP | PASS |
| L-R2 | totals | independent 18,648.00 + 683.20 = **PHP 19,331.20** = CSV = blocking plan = partial plan | PASS |
| L-R3 | 1,520.00 / 1,250.00 anywhere in rows | absent; Bayside row needs_review, amount null | PASS |
| L-R4 | blocking/destinations | Bayside still blocking → Uncategorized/; Pixelforge → Invoices/2026-10/; Sunbeam → Receipts/2026-09/ | PASS |

In-process (mocked classifier, store read directly; `inprocess/`):

| ID | Check | Actual | Result |
|---|---|---|---|
| M-B1 | Bayside with parseable rejected amount_text "PHP 1,520.00" | needs_review, amount_conflict, amount null | PASS |
| M-B2 | `{"accept":true}` | 422; revision 0→0; plan snapshot and record unchanged | PASS |
| M-B3 | `{"amount":"1520.00","accept":true}` | 422; unchanged | PASS |
| M-C1 | valid Pixelforge/Sunbeam | 200/200; accepted rows exactly those two; PHP 19,331.20 | PASS |

## Stage 4: UI1 in the real frontend

Driven with Microsoft Edge (headless) via `playwright-core` against the Vite dev server in live mode (`VITE_USE_FIXTURES=false`). The folder path was typed into the "folder path on this computer" box (`fu/` root); the network log captured every `/api/` request except status polls (`ui/network_log.json`). Screenshots in `ui/`.

| ID | Check | Actual | Result |
|---|---|---|---|
| U0 | UI scans the fresh root | `POST /api/scan {"root":"<TEST_BASE>\\UI-L"}` | PASS |
| U1 | Bayside panel (amount_conflict) | amount box empty; "Looks right · mark checked" **disabled**; hint shown; forced click → **0 PATCH**; record unchanged (`04_…panel.png`) | PASS |
| U2 | Cash note panel (missing_amount) | same: disabled, hint, 0 PATCH, unchanged (`05_…panel.png`) | PASS |
| U3 | UI session plan | both flagged docs needs_review, amount null; totals PHP 19,331.20 (blocking and partial); blocking count 2 | PASS |
| U4 | no approve/undo request from the UI run | none | PASS |

The UI run sent no PATCH, approve or undo request at all. The Electron desktop window was not driven (browser dev mode only): NOT TESTED.

## Stage 5: filed-uncounted API semantics

| ID | Check | Actual | Result |
|---|---|---|---|
| L-N1 | live cash note precondition | receipt/transaction; amount null; amount_text null; missing_amount | PASS |
| L-N2 | live `{"accept":true}` | 200; `filed_uncounted`; ok; amount null; flags cleared; row needs_review/null; totals unchanged (19,331.20) | PASS |
| L-N3 | live invented amount afterwards `{"amount":"500.00","accept":true}` | 422; unchanged | PASS |
| M-N1/M-N2 | mocked cash note | 200 `filed_uncounted`; revision 0→1; not accepted, not totaled; destination `Receipts/2026-09/` | PASS |
| M-N3 | invented amount after filed-uncounted | 422; revision, snapshot, record unchanged | PASS |
| L-V1…V5 / M-V1…V3 | invalid corrections: Sunbeam subtotal 610.00, Pixelforge 18500.00, currency XYZ, amount null, amount "" | 422 each; record and plan (and revision/snapshot in-process) unchanged | PASS |
| M-E1 | Bayside where the model returned **no** amount_text | needs_review; flags `missing_amount`, `amount_conflict` | PASS |
| M-E2 | its `{"accept":true}`: amount never counted | not accepted; amount null; totals unchanged | PASS |
| M-E3 | its `{"accept":true}`: conflict guard | **200**, `filed_uncounted`, status ok, flags `[missing_amount, amount_conflict]` → `[]` | **FAIL** |

### FU-1 (Dev 1, Medium): filed-uncounted bypasses the conflict guard when amount_text is empty

Eligibility for filed-uncounted checks only that the request has no `amount` and the stored `amount`/`amount_text` are empty. It does not look at the flags. When the model returns no amount for a receipt whose source has conflicting totals (as in M-E1), the validator raises `amount_conflict`, yet `{accept:true}` returns 200, marks it `filed_uncounted` and **clears `amount_conflict`**. No money is counted (DA-7's core risk stays closed), but the conflict signal is lost and the file stops blocking. This contradicts the commit message ("Conflicting/unsupported amounts keep the full guard"). Suggested: only allow filed-uncounted when the sole amount finding is `missing_amount` (no `amount_conflict` / `amount_unparseable`). Reproduced deterministically in-process; in this run the live model gave Bayside a non-empty amount_text, so the live path was not hit.

### FU-2 (Dev 3 + Dev 1, Low/Medium): filed-uncounted is unreachable from the Check screen

The UI guard includes `missing_amount`, so "Looks right" is disabled for exactly the amount-less receipts the backend now files uncounted. The hint says "or leave this file for review", but the transaction panel has no leave-for-review action; the only ways forward are typing an amount (422 for an amount-less paper, since nothing supports it) or the "Set all aside" review-choice dialog. A product decision is needed: either expose a "file without amount" action for `missing_amount`-only receipts, or drop the backend outcome. Note also that a filed-uncounted receipt is moved to `Receipts/YYYY-MM/` (not `Uncategorized/`), while the panel says "goes to Uncategorized/ once checked" before the decision.

Cosmetic: with a typed live root the header says "Demo files · 4 files" (`06_files_after.png`).

## QA process incident (no repository impact)

While installing `playwright-core` into the session scratchpad, a `Set-Location` to the scratchpad failed twice and the commands ran in `frontend/` instead: the first added `playwright-core` to `frontend/package.json`/`package-lock.json`; the second overwrote `frontend/package.json` and npm removed 152 packages from `frontend/node_modules`. Recovery: `git checkout -- package.json package-lock.json` (restoring only my own accidental edits to HEAD), Vite stopped, `npm ci` (152 packages from the lockfile), `npm test` 44/44 and `npm run build` OK, Vite restarted. `git status` afterwards showed only the `.docx`. All Stage 1 command results above were recorded **before** the incident; tests/build were re-run green after recovery. The driver was then installed with a guarded absolute path in the scratchpad.

## Separately tracked

UI1 (leave-for-review `review_disposition` handling), D1, DA-5b, DA-2 and DA-4 are not assessed here. F1 (phase 3) stays closed. Offline and symlink tests: NOT TESTED.

## Evidence

`setup/manifest.json`; `live/` (status, scan, states, every PATCH with before/after record and plan, final plans, `prepared_report.csv`, `http_log.json`); `inprocess/` (plans, mocked HTTP log); `ui/` (screenshots, `network_log.json`, `ui_scan_initial.json`, `ui_plan_after.json`, `results_ui.json`); `results_api.json`; `scripts/api_retest.py`, `scripts/ui_retest.mjs`.
