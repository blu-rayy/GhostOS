# GhostOS Phase 2 frontend QA

Date: 2026-10-09  
Owner: Codex (Developer 3)  
Branch: `qa/frontend-tests`

## Result

Pure-logic and fixture QA is green: 4 test files, 16 tests passed, 0 failed.
The suite is deterministic and offline. Mock API delays are driven with Vitest
fake timers; no network or real filesystem access is used.

Baseline confirmed from the fixture plan:

- PHP `26,007.45` across 6 accepted rows.
- USD `157.29` across 2 accepted rows.
- Five blocking review documents before corrections: `f07`, `f13`, `f15`,
  `f17`, and `f18`.

Coverage includes decimal-string money arithmetic and normalization; mock
destinations, review folders, date folders, duplicate collision suffixes,
accepted-row filtering, per-currency totals, undo conflict, correction with
`accept: false` and `accept: true`, failed-document manual entry, skipped-file
rows, all five skipped fixture entries, f07/f08/f10/f13/f14/f15/f16/f17/f18,
CSV filtering/quoting/formula guards, path traversal checks, and prompt text
being treated as data.

Commands run:

```text
cd frontend
npm.cmd install
npm.cmd test -- --reporter=verbose
npm.cmd exec -- vitest --version
npm.cmd run build
```

`npm.cmd install` completed with Vitest 4.1.11 and reported 0 vulnerabilities.
The first PowerShell `npm install` invocation was blocked by the local
execution policy; the equivalent `npm.cmd install` completed after registry
network permission was granted.
`npm.cmd run build` completed successfully (`tsc -b` and Vite production
build).

## Bugs and edge cases

No pure-logic implementation bugs remained after the suite passed. The first
run exposed three incorrect test assumptions, corrected in the tests:

- `f15` (`uncertain`) is intentionally omitted from report rows because the
  mock emits invoice/receipt rows only.
- Correcting failed `f10` does not decrement `blocking_review_count`; failed
  documents do not block approval by contract.
- CSV quoting doubles embedded quotes, so the injection assertion checks the
  escaped CSV representation.

Uncovered edge cases: the fixture has no `unreadable` or
`file_limit_reached` skipped entry, no three-way collision requiring `(3)`, no
empty filename/path input from a real folder picker, and no live backend
response to validate against the frontend types. These need backend/fixture
follow-up rather than fabricated frontend fixtures.

## Security and integration review

Observed good posture:

- `frontend/index.html:10` has a CSP with `script-src 'self'`; `connect-src`
  is limited to the app, loopback FastAPI, and loopback Ollama endpoints.
- `frontend/electron/main.cjs` sets `nodeIntegration: false`,
  `contextIsolation: true`, `sandbox: true`, and `webSecurity: true`.
- `frontend/electron/preload.cjs` exposes only `platform`, `version`,
  `capabilities`, and `selectFolder`; it does not expose `fs`, `require`, or
  `ipcRenderer`.
- `frontend/src/main.tsx:4-8` imports bundled `@fontsource` assets. No CDN font
  request or other outside network request was found in the renderer.
- Mock destinations are generated from fixed folders and filenames; the test
  rejects absolute paths, drive-letter paths, parent traversal, and the
  injection's requested `C:/Windows/System32` destination. Prompt-injection
  text remains fixture data and is not rendered through HTML or executed.

The CSP still allows `'unsafe-inline'` styles and `data:`/`blob:` images; these
are observed allowances, not failures, but should remain intentional.

## Contract comparison

The backend schemas currently present are Phase 1 schemas, while
`frontend/src/types/api.ts` and `docs/frontend-api-handoff.md` are explicitly
proposed Phase 2 schemas. The following are observed mismatches, not proposed
frontend changes:

1. Frontend sends `{ root }` to `POST /api/scan`; backend `ScanRequest` requires
   `{ root_path }`.
2. Frontend expects an immediate `ScanProgress` plus
   `GET /api/scans/{scan_id}/progress` and `GET /api/scans/{scan_id}`. Backend
   currently exposes synchronous `POST /api/scan` returning `ScanResponse`
   with `root_path`, `total_files`, and `files`.
3. The backend has no implemented `/api/status`, scan-progress, document PATCH,
   plan, approve, or undo routes.
4. Frontend `ScanResult` expects `documents[]` and `skipped[]`; backend returns
   `files[]` of `FileRecord`. Backend uses `filename`, `extension`,
   `extraction_status`, `text_excerpt`, and `reason`, while the frontend
   expects `file_type`, `status`, `excerpt`, `classification`, `review_flags`,
   `duplicate_of`, and `user_corrected`.
5. Frontend requires `sha256: string`, `max_files`, and `scanned_at`; backend's
   `sha256` is nullable and `ScanResponse` has no `max_files` or
   `scanned_at`.
6. Frontend `Classification` requires decimal-string `amount`, boolean
   `evidence_verified`, and non-null `explanation`; backend
   `ClassificationRecord` has no `amount` or `evidence_verified`, and its
   `explanation` is nullable.
7. Frontend `DocumentCorrection` requires `accept` and supports PATCH fields;
   no corresponding backend model or route exists.
8. Frontend `ProposedOperation` requires `collision_suffixed`; backend's
   `ProposedOperation` does not define it. Frontend's `PlanPreview`, report
   rows, currency totals, and blocking count have no backend equivalents yet.

Known contract gap: there is no `duplicate` or `excluded` report status. Exact
duplicates are informational in the current proposal and excluded from
accepted totals, but users cannot select an explicit excluded status.

Next task: Developer 1 should reconcile the Phase 1 FastAPI schemas/routes with
the proposed Phase 2 contract (or update `src/types/api.ts`), after which QA
should add a live-contract validation test without changing backend code here.
