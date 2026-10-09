# Document-aware review: QA test plan

**Owner:** Developer 4 · **Spec:** [`docs/design/document-aware-review.md`](../design/document-aware-review.md) · **Latest results:** [`tests/reports/document_aware_review/report.md`](../../tests/reports/document_aware_review/report.md)

## Goal

Prove that non-transactional paperwork (statements, identity/civil records, legal and medical papers, unclear documents) is never forced into expense fields, never counted in totals, and is filed only after an explicit user decision. Receipts and invoices must keep the existing transaction flow.

**Blocking safety defects:**
- an invented amount on a non-transactional document;
- a statement counted as an expense;
- any file move without explicit user approval.

## Test layers

| Layer | Tool | Destructive? |
|---|---|---|
| Unit (backend) | `pytest` in `backend/` (owned by Dev 1/2) | No |
| Unit (frontend logic) | `npm test` (vitest, `documentAware.test.ts`, owned by Dev 3) | No |
| Fixtures | `tests/fixtures/validate_fixtures.py` | No |
| Model evaluation | `backend/scripts/evaluate_sample_folder.py --output-dir <report dir>` | No (writes results only) |
| Live API acceptance | `tests/integration/document_aware_acceptance.py` (Dev 4): scan, preview, PATCH; **never approves or undoes**; checks the disposable folder is unchanged | No |
| Live approve/undo | Phase 3 procedure: disposable root, human-confirmed plan | **Yes**: requires explicit confirmation |
| UI visual | Browser screenshots (manual or Playwright) | No |
| Offline | Full flow with Wi-Fi off, run by a team member | Yes (with confirmation) |

## Fixtures

Reuse the generated dataset `tests/fixtures/sample_folder/` (25 files). Contract expectations exist in `ground_truth.json` (`expected_document_kind`, `expected_field_profile`) for:
- `misc/bank-statement-oct2026.txt` → `statement` / `reference`
- `identity/birth-certificate.pdf`, `identity/drivers-license-record.txt` → `identity_or_civil` / `none`
- `legal/lease-agreement-summary.pdf` → `legal` / `none`
- `medical/prescription-note.txt` → `medical` / `none`

QA-derived expectations, used until the ground truth is extended:
- `receipts/sunbeam-cafe-receipt.pdf` → `receipt` / `transaction`
- `misc/card-statement-sep2026.pdf` → `statement` / `reference`
- `misc/aircon-payment-note.txt` → `uncertain` / `none`
- `invoices/meralite-power-bill-sep2026.txt` → **pending decision DA-4** (invoice versus utility statement)

The live test copies fixtures into `%LOCALAPPDATA%\Temp\ghostos-docaware\R1`. It refuses to reuse an existing folder and never touches the committed fixtures.

## Scenarios

| | Scenario | Key checks |
|---|---|---|
| A | Receipt | `transaction` profile; merchant/date/amount correction accepted; counted once |
| B | Birth certificate / ID | `identity_or_civil`, profile `none`, null transaction fields; needs a decision; "file" → `Other/`, "leave" → `Needs Review/`; never counted; transaction corrections rejected |
| C | Bank and card statements | `statement`, profile `reference`; not one expense; balance and transactions never counted, including after a decision |
| D | Legal, medical | Correct kind; profile `none`; no fabricated values |
| E | Uncertain | Can stay in `Needs Review/` with null metadata |
| F | Contradictions and trust boundary | 422 with the record unchanged for transaction fields on non-transaction profiles, backend-controlled fields (`field_profile`, `editable_fields`, `destination_relative_path`, `operations`), `document_kind`, and contradictory categories; model output with extra keys rejected by the schema |
| G | Destinations and report | Fixed backend map only; no report rows for non-transactional kinds; preview and corrections write nothing; no move without approve |
| H | Regression | Backend, frontend and fixture suites; a live approve/undo on a disposable root (human-confirmed) |
| Offline | Wi-Fi off | Scan, evidence, decisions, approve, undo; `external_requests = 0` |

## How to run

```powershell
# from the repository root; start ONE fresh backend first (corrections are matched across scans: D1)
cd backend; .\.venv\Scripts\python.exe -m pytest -q; cd ..
cd frontend; npm run typecheck; npm run lint; npm test; cd ..
backend\.venv\Scripts\python.exe tests\fixtures\validate_fixtures.py
backend\.venv\Scripts\python.exe tests\integration\document_aware_acceptance.py
```

Rename or move an earlier `tests/reports/document_aware_review/acceptance/` folder and the disposable folder before a re-run. The script refuses to overwrite them.

## Reporting

Every check records its ID, input, expected and actual output, status (PASS / FAIL / BLOCKED / NOT TESTED) and owner. Results go to `tests/reports/document_aware_review/`. Earlier reports are never overwritten.
