# GhostOS — Developer Context

Local-only document organizer (invoices/receipts). No cloud, no external
network calls. Backend and AI are loopback-only: FastAPI on
`http://127.0.0.1:8000`, Ollama on `http://127.0.0.1:11434`
(model `qwen3:4b-instruct`).

End-to-end flow: folder select → async scan (poll progress) → review/correct
documents → plan preview (read-only) → approve (moves files + writes CSV) →
undo (restore originals).

## Repo layout

- `backend/` — FastAPI app. Entry `backend/app/main.py`. Run/test from this dir.
- `frontend/` — React 19 + TypeScript + Vite + Tailwind v4, runs in browser
  and Electron. Entry `frontend/src/main.tsx` → `frontend/src/App.tsx`.
- `frontend/electron/` — Electron main + preload (`main.cjs`, `preload.cjs`).
- `docs/frontend-api-handoff.md` — endpoint/field contract from frontend side.
- `docs/qa/` — QA strategy + Phase 1 checklist.
- `tests/` (repo root) — fixtures/integration/reports workspace.
- `pyrightconfig.json` (repo root) — sets `backend/` as source root for the
  Python analyzer (`extraPaths: ["backend"]`, python 3.11).

## Backend

Stack: Python 3.11+, FastAPI, Uvicorn, Pydantic, PyMuPDF, pytest, httpx.
Venv: `backend/.venv`. Install: `python -m pip install -r requirements.txt`.

Run (from `backend/`, venv active):

```powershell
python -m uvicorn app.main:app --host 127.0.0.1 --port 8000 --reload
```

Tests (from `backend/`, venv active): `python -m pytest`
(58 passed, 1 skipped — the skip is the real-Ollama integration test, which
only runs when a local Ollama + model is present.)

Routers (all mounted in `backend/app/main.py`):

| Router file | Prefix | Endpoints |
|---|---|---|
| `app/routes/session.py` | `/api` | `GET /status`, `POST /scan`, `GET /scans/{id}/progress`, `GET /scans/{id}`, `PATCH /documents/{file_id}`, `GET /scans/{id}/plan`, `POST /plans/{id}/approve`, `POST /batches/{id}/undo` |
| `app/routes/scan.py` | `/api/scan-v1` | `POST ""` (legacy sync scan, body `{root_path}`) |
| `app/routes/classify.py` | `/api/classify` | `POST ""` (single-excerpt classify) |
| `app/routes/contracts.py` | `/api/contracts` | `GET /examples` (static contract samples) |

Services in `backend/app/services/`:

- `scanner.py` — legacy sync folder walk (PDF/TXT/CSV, 100-file cap, 10 MB
  skip, symlink rejection).
- `extractor.py` — SHA-256 + bounded text excerpt (1500 chars).
- `local_ai.py` — Ollama adapter, strict `ClassificationRecord` validation,
  controlled error types (unavailable/timeout/validation/response).
- `orchestrator.py` — async scan worker (scan → extract → classify),
  review-flag logic, plan builder.
- `operations.py` — backend-owned destination rules (model never picks paths).
- `session_store.py` — in-memory thread-safe store for scans + batches.
- `report.py` — expense CSV writer. Mirrors `frontend/src/lib/report.ts`
  (accepted rows only, CRLF, formula-injection neutralization, UTF-8 BOM).

Canonical schemas: `backend/app/schemas.py` (`ScanRequest`, `FileRecord`,
`ScanResponse`, `ClassificationRecord`, `ClassifyRequest/Response`,
`ProposedOperation`).

### Invariants / gotchas (do not break)

- Session `POST /api/scan` takes body `{root}` (not `root_path`; the legacy
  `scan-v1` route uses `root_path`).
- `plan_id` is deterministic: `plan_{scan_id}`
  (`orchestrator.py`). `approve` derives `scan_id` from it. Random plan IDs
  break approve with 404.
- Plan report rows prefer canonical `classification.amount` (set by worker and
  human corrections), falling back to parsing `amount_text`. Never drop the
  `amount` field or corrections stop counting as `accepted`.
- `approve` physically moves files AND writes the CSV under
  `GhostOS Reports/expenses-<stamp>.csv` relative to the scan root.
- `blocking_review_count` = docs with `status == "needs_review"` and not
  user-corrected. `failed` docs go to `Needs Review/` but do not block.
- `classify.py` passes `request.file_id` as `original_relative_path`
  placeholder — single-file classify destinations are not real paths.
- `GET /` still returns `{"phase": 1}` (stale label, harmless).
- No CORS middleware — browser dev server (`127.0.0.1:5173`) calling the API
  will be blocked; use Electron or same-origin for real-backend testing.
- All session state is process memory — server restart loses scans/batches.

## Frontend

Stack: React 19, Vite 8, Tailwind v4, `lucide-react`. Node 20.19+/22.12+,
npm 10+.

Scripts (from `frontend/`): `dev:browser` (Vite on `127.0.0.1:5173`),
`dev:electron` (needs Vite already running), `dev` (both),
`build` (`tsc -b && vite build`), `typecheck` (`tsc -b`), `lint` (oxlint),
`preview`, `electron:preview`.

API layer (`frontend/src/api/`):

- `client.ts` — `GhostApi` interface (everything the UI needs).
- `http.ts` — real client, `VITE_API_BASE` default `http://127.0.0.1:8000`.
- `mock.ts` — in-memory fixture mock (simulated scan timing, demo failure
  scenarios).
- `index.ts` — `USING_FIXTURES = VITE_USE_FIXTURES !== 'false'`; fixtures are
  the default. Real backend needs `frontend/.env.local` with
  `VITE_USE_FIXTURES=false` + `VITE_API_BASE=http://127.0.0.1:8000`.

Pages (`frontend/src/pages/`): `Dashboard`, `FolderSelect`, `Scanning`,
`Files`, `Plan`, `Report`, `Activity`, `Completion`, `Settings` (9 views,
see `App.tsx`). Key components: `shell/AppShell`, `documents/*`,
`plan/*`, `report/ExpenseReportTable`, `activity/ActivityTimeline`.

State: `frontend/src/state/AppState.tsx` + `reducer.ts` — all backend calls
go through `api`; nothing touches the filesystem directly. Status bar polls
`getStatus` every 10 s. Scan progress polls every 500 ms.

Platform (`frontend/src/platform/`): `browser.ts` vs `electron.ts` adapters.
Only Electron (`window.ghostos` bridge, `contextIsolation: true`,
`nodeIntegration: false`) has a native folder picker; browser mode requires
a typed/pasted path.

Pure libs: `lib/money.ts` (BigInt-cents decimal math, no floats),
`lib/report.ts` (CSV export, accepted rows only), `lib/viewModel.ts`
(contract → table rows), `lib/format.ts`, `lib/labels.ts`, `lib/review.ts`.
`lib/plan.ts` is obsolete (nothing imports it, safe to delete).

Fixtures: `frontend/src/fixtures/scan.json` (18 docs, 5 skipped, edge cases:
duplicates, timeout, injection, multi-currency, uncertain, missing date,
evidence mismatch), `status.json`.

## Git state (2026-10-09)

- `main` — clean, at `89edc44` (merge of QA fixtures PR #4).
- `origin/feature/phase2-step2-session-management` (`64b3ec2`) — the full
  session-management layer (session routes/services/report/tests) plus the
  plan_id, amount-correction, and CSV-write fixes. Open PR from this branch.
- Older remote branches: `feature/phase2-step1-classify`,
  `feature/step3-scanner`, `feature/step4-extraction`,
  `developer-1-jj/phase1-step2-contracts`, `feature/frontend-fixture-ui`.
- Untracked local-only: `pyrightconfig.json` (editor config, consider
  committing if the team uses Pyright/Pylance).

## Picking up work

1. Backend: `cd backend`, activate `.venv`, `python -m pytest`, then
   `python -m uvicorn app.main:app --host 127.0.0.1 --port 8000 --reload`.
2. Frontend fixture mode (no backend): `cd frontend`, `npm install`,
   `npm run dev:browser`.
3. Frontend real-backend mode: add `frontend/.env.local` (see above), start
   backend first, then `npm run dev:electron`.
4. Contract source of truth: `frontend/src/types/api.ts` proposes shapes,
   `backend/app/schemas.py` enforces them — keep field names snake_case on
   both sides and update both when changing a contract.
