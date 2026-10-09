# Frontend → Backend handoff (H4)

**From:** Developer 3 (frontend) · **To:** Developer 1 (API schemas), Developer 4 (fixtures/QA)

The UI runs end to end on fixtures today: choose folder → scan with progress → review cards → preview moves and report → approve → undo.
The source of truth for the shapes below is [`frontend/src/types/api.ts`](../frontend/src/types/api.ts). Field names are snake_case so the Pydantic models can match them exactly.
**Developer 1:** please treat that file as a proposal. Change names freely, and tell me so I can update the file.

## Endpoints the UI calls

All calls go to `http://127.0.0.1:8000` (override with `VITE_API_BASE`). The UI must be able to call these from `http://localhost:5173`, so please allow that origin in CORS.

| Method | Path | Body | Returns |
|---|---|---|---|
| GET | `/api/status` | — | `SystemStatus` |
| POST | `/api/scan` | `{ root }` | `ScanProgress` (returns immediately; the scan runs in the background) |
| GET | `/api/scans/{scan_id}/progress` | — | `ScanProgress` (UI polls every 500 ms) |
| GET | `/api/scans/{scan_id}` | — | `ScanResult` (called once `state == "done"`) |
| PATCH | `/api/documents/{file_id}` | `DocumentCorrection` | updated `DocumentRecord` |
| GET | `/api/scans/{scan_id}/plan` | — | `PlanPreview` (read-only, no writes) |
| POST | `/api/plans/{plan_id}/approve` | `{}` | `BatchResult` |
| POST | `/api/batches/{batch_id}/undo` | `{}` | `UndoResult` |

For errors, send a non-2xx status with `{ "detail": "human readable message" }` (FastAPI's default). The UI shows `detail` as is.

## Fields the UI depends on

**SystemStatus** (the status bar shows this on every screen; it supports the offline claim in the demo)
`model_name`, `model_endpoint`, `model_loaded`, `external_requests` (count of non-loopback requests; shown in red if > 0), `last_inference_ms` (nullable), `backend_endpoint`, `last_inference_at`.

**ScanProgress**
`scan_id`, `state` (`running` | `done` | `error`), `files_total`, `files_processed`, `current_file` (nullable, relative path), `error` (nullable).

**ScanResult**
`scan_id`, `root`, `scanned_at`, `files_seen`, `max_files`, `documents[]`, `skipped[]` (`relative_path`, `reason`, `detail`).
`reason` is one of: `unsupported_type`, `too_large`, `unreadable`, `symlink`, `no_extractable_text`, `file_limit_reached`.

**DocumentRecord**

| Field | Notes |
|---|---|
| `file_id` | Stable for the whole scan. The UI uses it as the key everywhere. |
| `relative_path` | Relative to the root, with forward slashes. **Absolute paths never reach the UI.** |
| `file_type`, `size_bytes`, `sha256` | Metadata line on the card. |
| `excerpt` | The exact bounded text sent to the model. The UI highlights `evidence_quote` inside it. |
| `status` | `ok` \| `needs_review` \| `failed`. Only `needs_review` blocks approval. |
| `classification` | `null` when the extraction or model call failed. |
| `review_flags[]` | `{ code, message }`. The UI shows `message` verbatim, so write it for the end user. |
| `duplicate_of` | `file_id` of the exact-hash original, or `null`. Informational only. |
| `user_corrected` | `true` after any PATCH with `accept: true`. |

**Classification**
`category` (`invoice` | `receipt` | `other` | `uncertain`), `merchant`, `date` (ISO `yyyy-mm-dd`), `amount_text` (raw text), `amount` (**decimal string**, e.g. `"1520.00"`, never a float), `currency` (ISO 4217), `evidence_quote`, `evidence_verified` (backend substring check), `explanation`.
Any of the extracted fields may be `null`.

`review_flags[].code` values the UI styles: `evidence_not_found`, `amount_unparseable`, `amount_conflict`, `missing_date`, `missing_amount`, `low_confidence`, `model_error`, `possible_injection`.

**DocumentCorrection** (PATCH body)
Optional `category`, `merchant`, `date`, `amount` (decimal string), `currency`, plus a required `accept: boolean`.
When `accept` is true, set `user_corrected = true` and clear `review_flags`.

**PlanPreview**
`plan_id`, `scan_id`, `operations[]`, `report_rows[]`, `totals[]`, `blocking_review_count`.
- `operations[]`: `file_id`, `original_relative_path`, `destination_relative_path`, `reason` (shown as a tooltip), `collision_suffixed`.
- `report_rows[]`: `file_id`, `source_filename`, `category`, `date`, `merchant`, `amount`, `currency`, `status` (`accepted` | `needs_review`).
- `totals[]`: one entry per currency (`currency`, `amount`, `row_count`). **Accepted rows only.**
- `blocking_review_count`: the UI disables Approve while this is greater than 0.

**BatchResult**
`batch_id`, `moved`, `failed[]` (`file_id`, `error`), `report_relative_path`, `committed_at`.

**UndoResult**
`batch_id`, `restored`, `conflicts[]` (`file_id`, `relative_path`, `reason`).

## Plan rules the fixture mock assumes

The mock in [`frontend/src/api/mock.ts`](../frontend/src/api/mock.ts) follows these rules so the UI behaves realistically. Please confirm them or tell me what differs:

1. Destinations:
   - Invoices go to `Invoices/YYYY-MM/`, receipts to `Receipts/YYYY-MM/` (by document date), and other files to `Other/`.
   - Files go to `Needs Review/` when they failed, are uncertain, are an unreviewed `needs_review` document, or are an invoice or receipt without a date.
2. Name collisions get a ` (2)` suffix before the extension, and `collision_suffixed` is set to `true`.
3. A report row is `accepted` only if it has an amount, a currency and a date, is not awaiting review, and is not an exact duplicate.
4. `blocking_review_count` counts documents with `status == "needs_review"` that the user has not reviewed. Failed documents do not block approval; they are filed in `Needs Review/`.

## Open questions

- **Developer 1:** Is the scan synchronous or a background job? The UI assumes a job plus polling, because about 20 files at about 2 s each would leave a long blank wait.
- **Developer 1:** The browser cannot read absolute paths from a folder picker, so the user types or pastes the path. Do we want a `GET /api/browse?path=` endpoint for a folder picker later (stretch)?
- **Developer 1 and 2:** Should invoices the user *issued* (income, e.g. fixture `f18`) be excluded from the expense report? Today they are counted.
- **Developer 2:** Can `evidence_quote` be guaranteed to come back verbatim (same whitespace), so it can be highlighted in `excerpt`?

## For Developer 4: what the fixtures cover

[`frontend/src/fixtures/scan.json`](../frontend/src/fixtures/scan.json) has 18 documents and 5 skipped files.

| Fixture | Case |
|---|---|
| `f07` | Conflicting amounts (`amount_conflict`) |
| `f08` | Exact duplicate with the same filename as `f01`, so its move needs a collision suffix |
| `f10` | Model timeout (`failed`) |
| `f13` | Prompt injection |
| `f14`, `f16` | USD amounts alongside PHP |
| `f15` | Uncertain category (bank statement) |
| `f17` | Missing date |
| `f18` | Evidence quote not found in the text |
| Skipped files | Image, DOCX, scanned PDF, oversize CSV, symlink |

If your real sample set has cases these fixtures don't cover, send me the backend JSON for them and I'll add them.

## Requests from the paper redesign (Kristian, 2026-10-09)

The new screens are in `docs/design/step*.md`. Most of them work with the contract above. These would complete them, roughly in priority order. **Developer 1:** please accept, change or reject each one.

| # | Request | Used by | Without it |
|---|---|---|---|
| R1 | **Move as a background job**: `POST /api/plans/{plan_id}/approve` returns `{ batch_id }` immediately, and `GET /api/batches/{batch_id}/progress` returns `{ state: running\|done\|error, files_total, files_moved, current_file, failed[] }` (same pattern as scans). Then `GET /api/batches/{batch_id}` returns `BatchResult`. | Totals 3c (moving progress) | Indeterminate "moving…" bar, no counts |
| R2 | **Confirm**: a file in `BatchResult.failed[]` is left untouched at its original path (no partial copy). `error` should be written for the end user. | Totals 3d | Weaker wording: "didn't reach their new folder" |
| R3 | **Retry failed moves**: `POST /api/batches/{batch_id}/retry` (moves only the `failed[]` files, same destinations). | Totals 3d "Try the 2 again" | Button hidden |
| R4 | **Cancel after current file**: `POST /api/batches/{batch_id}/cancel`. Files already moved stay moved, and the remaining ones are reported as not moved. | Totals 3c "stop after this file" | Link hidden |
| R5 | **Undo and folders**: does undo remove destination folders it created that end up empty? Please document it either way. `UndoResult.conflicts[].reason` should be written for the end user. | Done 4b/4c/4d | UI says nothing about folders |
| R6 | **Income vs. expense** (extends the open question above): an optional `direction: "expense" \| "income" \| null` on `Classification`/`report_rows`, and `totals[]` per currency *and* direction. | Totals 3a | Step is named "Totals" and counts everything together, as today |
| R7 | **Candidate amounts** for `amount_conflict`: `review_flags[].candidates?: { label, amount, amount_text }[]` (e.g. subtotal vs amount due). | Check 2a choice buttons | Editable amount field + highlighted excerpt |
| R8 | **Re-read one file**: `POST /api/documents/{file_id}/rescan`. | Check 2c "Try reading it again" | Option hidden |

Frontend-only (no backend needed): "Open folder" on Done needs a new Electron preload method (`openFolder(root)` → `shell.openPath`, restricted to the scanned root). It needs Kristian's approval because it changes the preload API.
