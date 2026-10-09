# GhostOS — Project Context

> Working reference for the four developers, coding assistants, and project manager.
> Updated: 2026-10-09. Status is a plan, **not** a claim that features are complete.

## Mission

GhostOS is a **local-AI file organization and expense reporting workspace**. A user chooses one folder of mixed invoices, receipts, and notes. GhostOS scans supported files, extracts text locally, classifies documents using a local model, shows evidence and uncertain values, previews safe destination paths and a CSV expense report, requires explicit approval, and supports batch undo.

**Pitch:** Sensitive paperwork stays on-device; file operations are transparent, reviewable, and reversible, even without Wi-Fi.

### Source of truth and changes

- Product baseline: `GhostOS_24_Hour_Product_and_Build_Plan_Reformatted.docx` (GhostOS 24-Hour Product and Build Plan).
- Event requirements: `AppBuildersPH-Hackathon-2026-Participant-Briefing.pdf`.
- **Current team decision:** deliver a desktop application rather than just a browser-at-localhost experience. The original product plan recommends a locally served React/TypeScript UI and FastAPI backend and says an installer is out of scope. Desktop shell/packaging details are **not yet fixed**; use the existing repository implementation and team decision, and do not assume Electron or Tauri without confirmation.
- Hour-based phases are planning targets from the product brief. **The official submission deadline overrides the nominal H24 endpoint.**
- Consult the actual repository and current branches before claiming anything is implemented. Different developers may already be in Phase 2; this document is the target architecture and ownership map, not a live status report.

## Team and responsibilities

| Developer | Person | Primary ownership | Key handoffs |
|---|---|---|---|
| Dev 1 | John Janiel Obmerga | Backend foundation, API contracts, scanning, text extraction, safe path resolution, plan/commit/undo, audit | H4 scan contract; H10 commit/undo API |
| Dev 2 | Kurt Laurence Tendero | Ollama/local model, structured classification, typed adapter, extraction/validation coordination, latency and offline verification | H2 offline model call; H8 integrated classifier |
| Dev 3 | Kristian David Bautista | Frontend/desktop UI, evidence and editing experience, preview and approval, backend integration; **project manager, pitch deck, video, submission coordination** | H4 fixture-driven UI; H12 live backend flow |
| Dev 4 | Jhon Vincent Libatique | Test dataset, fixtures, QA, integration branch, edge cases, report checks, demo support | H4 fixtures; H12 end-to-end smoke test |

**Collaboration:** Dev 1 owns API schemas; Dev 2 returns typed classification records; Dev 3 consumes fixtures until live endpoints are ready; Dev 4 owns integration and records observed pass/fail results. Agree on request/response shapes early; merge small increments every ~2 hours. The names/roles above reflect team conversation and should be checked against the official participant roster before submission.

## MVP boundaries

**Required:**
- Scan one selected root folder; up to **100** supported files (text-based PDF, TXT, CSV); skip oversized, unsupported, unreadable files with reasons.
- Extract locally, classify `invoice | receipt | other | uncertain`, include evidence snippets and optional merchant/date/amount/currency.
- Detect exact duplicates by hash and filename collisions; **never auto-delete duplicates**.
- Show destination preview, draft expense CSV and low-confidence/ambiguous fields for user correction.
- Explicit approval before moving files; destinations **inside selected root only**; produce CSV with source filenames and an undo/audit manifest.
- Undo batch when original locations are safe; explain conflicts and partial failures.
- Offline functionality with visible model identifier, loopback endpoint, and no external inference requests.

**Out of scope:** arbitrary shell commands, unrestricted desktop control, automatic deletion, scanned-PDF OCR, cloud sync, tax calculation, payment advice. Stretch only after stable core: DOCX extraction, OCR for one image format, second language.

## Architecture and trust boundaries

Original recommended stack:
- React + TypeScript UI (now targeted as desktop UI by team decision).
- Python FastAPI at `127.0.0.1`.
- Ollama at `127.0.0.1:11434`; candidate `qwen3:4b-instruct` predownloaded, configurable; `qwen3:1.7b` only if quality and hardware testing justify switching.
- PyMuPDF for text-based PDF extraction; standard-library `csv`, `pathlib`, `hashlib`, `decimal`; SQLite for metadata/plans/audit.

Pipeline:
1. **Scan** — root folder -> safe inventory, hashes, bounded text excerpts (Dev 1).
2. **Interpret** — excerpts -> schema-constrained model JSON (Dev 2).
3. **Validate** — verify evidence/amounts, flag uncertainty (backend with Dev 2 coordination).
4. **Preview** — validated records -> proposed destinations + draft report, **no writes** (backend + UI).
5. **Approve** — explicit action -> collision-safe moves, CSV and audit manifest (backend).
6. **Undo** — manifest -> conditional reverse moves, report conflicts (backend + UI).

AI JSON contract (one call per file):
```json
{
  "category": "invoice",
  "merchant": "Example Store",
  "date": "2026-10-09",
  "amount_text": "PHP 123.45",
  "currency": "PHP",
  "evidence_quote": "TOTAL PHP 123.45",
  "explanation": "Total appears on the invoice."
}
```
These are illustrative values, not measured model output. The actual shared schema governs nullability and naming.

- Bind `source_id`/`file_id` in application code, not in model output.
- Model sees only bounded text, **not absolute paths or executable instructions**.
- Backend checks `evidence_quote` exists in source text; parses money with `Decimal`; conflicting/missing fields require review. Confidence is a review flag, not calibrated probability.
- Proposed operation: `file_id`, `original_relative_path`, `destination_relative_path`, `reason`.
- Backend generates paths using a fixed category map (e.g. `Invoices/YYYY-MM`, `Receipts/YYYY-MM`, `Needs Review`). Model must **never** supply executable paths.
- Resolve/recheck paths inside selected root before each move; reject symlinks; never overwrite; handle collisions; preserve file identity in manifest.
- Document contents are untrusted, including embedded prompt instructions.
- Ollama `/api/chat`, `stream=false`, structured `format` schema, short timeout and one retry; failures -> Needs Review. Disable cloud fallbacks/telemetry.
- Undo only when original path is free and destination matches recorded identity. Partial operations are logged and reported, never guessed away.
- Generate report through temporary CSV and atomic replace; include source filename, timestamp, and row status.

## Phases and work assignments

The phases below are the **product plan's relative build windows**. Since the official submission closes at **10:00 AM October 10, 2026 (Philippine time)** and code freezes then, complete all required submission artifacts and final commits before that absolute deadline.

### Phase 1 — Foundation (H0–H2)
**Goal:** prove setup, offline inference, and common contracts.

- **Dev 1:** initialize FastAPI/health route, define scan/classification contracts and example payloads, validate loopback binding.
- **Dev 2:** install/preload Ollama model, run structured inference offline, record model ID and observed latency.
- **Dev 3:** initialize React/TypeScript desktop UI skeleton, folder-select and workspace design, types/fixtures; coordinate H1 contract meeting; start pitch narrative.
- **Dev 4:** integration branch, initial safe sample files, expected-result sheet, QA checklist and fixture format.
- **Gate:** backend and UI start, schema agreed, at least one real offline structured model response, initial fixtures available. If model fails, decide smaller model or reduced scope immediately.

### Phase 2 — Independent components (H2–H6)
**Goal:** scanner/extractor, classifier/validator, fixture UI, ~20-file test set.

- **Dev 1:** safe inventory, PDF/TXT/CSV extraction, hashes, bounded excerpts, skip reasons.
- **Dev 2:** typed classifier adapter, category/evidence extraction, structured response and error handling; evaluate five unseen files.
- **Dev 3:** document table, evidence cards, scan status, review states and mock preview flow; create first pitch slide outline.
- **Dev 4:** ~20-file dataset including duplicates, collisions, unreadable/ambiguous cases; frontend fixtures and expected outcomes.
- **Gate:** five unseen files show defensible category and evidence; scan API and fixture UI can run independently.

### Phase 3 — Planning and reversible operations (H6–H10)
**Goal:** proposed plans, collisions, approval, safe commit and undo.

- **Dev 1:** fixed-map destination planner, root/symlink checks, collision-safe commit, manifest and undo API.
- **Dev 2:** integrate classifier into backend, evidence/Decimal validation, uncertainty/failure routing.
- **Dev 3:** destination plan, editable fields, approval confirmation and operation states; connect real classification responses when available.
- **Dev 4:** test duplicates, path collisions, symlinks, five-file preview -> approval -> undo; record bugs.
- **Gate:** safe five-file approval and undo demonstrated.

### Phase 4 — Full integration (H10–H14)
**Goal:** one complete real workflow and scope freeze.

- **Dev 1:** report CSV, commit/undo robustness, audit events and integration fixes.
- **Dev 2:** classification failures, timeouts, offline model stability, verified evidence.
- **Dev 3:** replace fixture mode in primary path with live API, editable uncertain rows, totals, audit timeline, clear partial failures.
- **Dev 4:** H12 end-to-end smoke test, verify CSV against accepted rows, record results.
- **Gate:** scan -> interpret -> review -> preview -> approve -> report -> undo works. **Freeze scope** when this passes.

### Phase 5 — QA and safety (H14–H18)
**Goal:** pass acceptance gates on unseen files with networking off.

- **Dev 1:** fix root escape, symlink, overwrite, partial move and undo defects.
- **Dev 2:** malformed outputs, hallucinations, missing evidence, ambiguous money, offline reliability.
- **Dev 3:** UI cancel/retry/errors, progress, conflicts, truthful success/partial status.
- **Dev 4:** lead full regression, unseen set, duplicates, collision, offline and partial-failure testing; record counts and results.
- **Gate:** no unapproved/out-of-root writes, accurate accepted-row totals, safe undo, classification target checked.

### Phase 6 — Polish and submission preparation (H18–H21)
**Goal:** demo clarity and submission assets, not feature expansion.

- **Dev 1:** stable startup, reproducible instructions, safety proof.
- **Dev 2:** verify offline model and latency on demo laptop; model/tool disclosures.
- **Dev 3:** UI polish, pitch deck, ~1-minute demo video direction/edit, public post and submission draft.
- **Dev 4:** clean backup dataset, QA evidence, screenshots/recording assistance, README and submission cross-check.
- **Gate:** clean offline restart; video, repository, social URL and disclosure list prepared.

### Phase 7 — Rehearsal and release (H21–H24, subject to hard deadline)
**Goal:** freeze working build and deliver submission **before 10 AM**.

- **Dev 1:** fix only release-blocking backend defects; verify commit/undo.
- **Dev 2:** confirm offline model loaded and no cloud dependency.
- **Dev 3:** finalize deck/video, social post, submission form, five-minute live pitch + three-minute Q&A prep.
- **Dev 4:** lead two timed rehearsals, audit checklist, demo laptop and fallback recording.
- **Gate:** submission accepted before deadline, public repo accessible, live offline demo rehearsed with undo. Do not commit code after the 10 AM freeze.

## Acceptance targets (not claimed achievements)

On demo laptop, Wi-Fi disabled, fresh unseen folder of roughly 20 supported files:
- >=80% of clearly identifiable invoices/receipts in correct preview category.
- Zero moves without approval; zero writes outside chosen root.
- CSV totals equal sum of accepted extracted rows.
- Every moved file restorable **when original target is safe**; conflicts explicitly reported.
- Complete offline workflow, including model name and endpoint shown.
- Core demonstration targeted to <=4 minutes, leaving room inside the event's **5-minute live pitch/demo**.

Do not invent benchmark numbers or call fixture behavior a successful live test.

## Official hackathon rules and deadlines

- Theme: **Local AI**. Meaningful AI inference must execute on device. Cloud can be secondary; disclose all tools.
- Build must be substantially done during the hackathon; disclose reused code/assets and AI coding tools. No external human assistance.
- **Submission:** October 10, **10:00 AM**, no extensions; **one submission only**; public GitHub repo; **code freeze at 10:00 AM**.
- Submit on: https://cerebralvalley.ai/e/appbuildersph-hackathon-2026
- Include: project name, short description, official team members, public GitHub, demo video, X/LinkedIn video URL, local vs internet functions, models, frameworks, APIs/cloud services, existing assets/code and AI development tools.
- Required explanation: **Why does this product benefit from running AI locally?**
- Video: ideally ~1 minute. Post to X or LinkedIn, tag Devin/Cognition and include `#AppBuildersPH`.
- Demo Day: **October 10**, Cyberzone SM Makati. Arrival noon; AV check 12:15 PM; finalists announced 1 PM; pitching begins 1:40 PM. A team member must pitch **in person**.
- Live format: **5 minutes pitch + demo, 3 minutes Q&A**.
- Judges: Problem/usefulness 25%; Local AI 25%; technical execution 20%; innovation 15%; product/demo 15%.
- A live deployment is not mandatory if the public repository includes recreation instructions.

**PM warning:** The product plan's H0–H24 schedule is relative and may extend beyond the official 10 AM submission cutoff if started at the event's 2:30 PM build kickoff. Prioritize the **absolute** deadline and plan backward; the submitted code must be ready before 10 AM.

## Kristian's parallel PM / pitch / video track

| Time | PM, pitch and submission work |
|---|---|
| H0–H2 | Lock roles, API fields, demo laptop and Git workflow; create pitch thesis and disclosure log. |
| H2–H6 | Draft slides: user problem, local AI benefit, workflow, safety, architecture, live demo. |
| H6–H10 | Create video storyboard, decide who records and who narrates; collect verified product clips. |
| H10–H14 | Capture real integrated workflow and draft ~60-second video; verify all product claims. |
| H14–H18 | Edit video, prepare X/LinkedIn copy, verify public repo/README and disclosures. |
| H18–H21 | Publish required post, assemble submission fields, review links and rehearse pitch. |
| H21–H24 | Submit before 10 AM; run timed live demo and Q&A rehearsals, respecting code freeze. |

Suggested pitch sequence: user problem -> why local AI -> short architecture/trust explanation -> **live offline workflow** -> safety/undo -> what is proven and limitations. Avoid slide-heavy presentation.

Suggested ~60-second video: messy folder/problem (0–10s), offline local model and scan (10–25s), evidence/correction and preview (25–40s), approve/report (40–50s), undo + value proposition (50–60s). Adjust to actual working features.

## Team working agreement

- Branch per owner/task; integrate small increments every two hours.
- API changes require notification to consumers and fixture/test updates.
- No direct filesystem writes from UI. Backend is sole authority for commit and undo.
- Do not move files during scanning, inference or preview.
- Never label a mock fixture as a real AI result in the demo.
- Test on a **fresh** folder and retain a safe backup.
- Report blocker with: failing step, observed error, expected behavior, owner, and next action.
- QA records actual test input, expected result, observed result, and pass/fail.
- Scope freeze after first working end-to-end run; safety defects outrank polish.

## Context for coding assistants

Before changing code:
1. Inspect repository tree, branch, existing tests and current contracts.
2. Identify which developer-owned component is affected and its upstream/downstream dependencies.
3. Preserve established schemas and desktop architecture; propose contract changes explicitly.
4. Write minimal scoped changes, tests and reproducible commands.
5. Do not invent completed work or performance measurements.
6. Return: changed files, tests run/results, integration needs, and remaining blockers.

**Definition of done:** A change runs locally, passes relevant tests, does not violate trust boundaries, and is usable by its downstream developer. A phase is complete only when its exit gate has been demonstrated, not just coded.

## Open decisions to confirm

- Desktop shell and distribution strategy (the initial product plan described browser-at-localhost; the team later chose desktop).
- Exact current endpoint/schema names versus this conceptual contract.
- Actual model availability, laptop performance and model identifier.
- Current phase completion and outstanding integration defects.
- Final official team names, repository URL and video/social URLs.

---

# GhostOS — Implementation State (observed, not planned)

Observed from the repository on 2026-10-10 (deadline day). The plan above is
the target; this section describes what is actually built. Verify against the
repo before claiming more.

End-to-end flow that works: folder select → async scan (poll progress) →
review/correct documents → plan preview (read-only) → approve (moves files +
writes CSV) → undo (restore originals).

**Phase 4 gate demonstrated 2026-10-10:** controlled 3-file live-model run
(scan → review → plan → approve → report → undo, 0 failures, 0 conflicts,
CSV total PHP 2650.50 exact) logged at `tests/reports/e2e-demo-2026-10-10.md`.
Code freeze proposed on the backend pipeline as of `8069727`.

## Repo layout

- `backend/` — FastAPI app. Entry `backend/app/main.py`. Run/test from this dir.
- `frontend/` — React 19 + TypeScript + Vite + Tailwind v4, runs in browser
  and Electron. Entry `frontend/src/main.tsx` → `frontend/src/App.tsx`.
- `frontend/electron/` — Electron main + preload (`main.cjs`, `preload.cjs`;
  current implementation — packaging/distribution decision still open per
  plan above).
- `docs/frontend-api-handoff.md` — endpoint/field contract from frontend side.
- `docs/qa/` — QA strategy + checklists (`phase1-checklist.md`,
  `phase2-frontend-qa.md`).
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
(124 passed, including the real-Ollama integration test when
`qwen3:4b-instruct` is installed locally.)

Accuracy harness (from `backend/`, model required):
`python scripts/evaluate_sample_folder.py` — runs the live pipeline on all 20
files in `tests/fixtures/sample_folder/` and grades against
`tests/fixtures/expected_results/ground_truth.json` (per-field accuracy,
review precision/recall, duplicate/collision integrity, injection-safety
checks, JSON report). Last measured: category 17/20, amount 20/20,
evidence 15/20, precision 0.57 / recall 1.0, ~2.1s/file, 0 errors.
Reports are written to `backend/evaluation_output/` (gitignored by design).

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
  Field-enumerating system prompt, `temperature: 0`, no Ollama `format:` schema
  (it suppressed optional fields on `qwen3:4b-instruct`); JSON fences tolerated.
- `classification_validation.py` — source-aware validator: exact evidence
  check, authoritative-final-total vs reconciliation-component resolution with
  arithmetic cross-check, `ambiguous_amount` / currency / missing-field /
  `quotation_document` flags, `uncertain` always reviewed. Knows PHP, USD, EUR,
  GBP, SGD (+S$), JPY (+¥).
- `orchestrator.py` — async scan worker (scan → extract → classify →
  **validate**), plan builder. `plan_id` deterministic (`plan_{scan_id}`).
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
- CORS middleware is present (`app/main.py`), scoped to
  `http://127.0.0.1:5173` + `http://localhost:5173` (GET/POST/PATCH/OPTIONS) —
  browser live-mode works.
- All session state is process memory — server restart loses scans/batches.
  (SQLite for metadata/plans/audit is planned, not implemented.)

## Frontend

Stack: React 19, Vite 8, Tailwind v4, `lucide-react`. Node 20.19+/22.12+,
npm 10+.

Scripts (from `frontend/`): `dev:browser` (Vite on `127.0.0.1:5173`),
`dev:electron` (needs Vite already running), `dev` (both),
`build` (`tsc -b && vite build`), `typecheck` (`tsc -b`), `lint` (oxlint),
`test` (`vitest run`, 23 tests green), `preview`, `electron:preview`.
Vitest is a declared devDependency (committed test files import it).

API layer (`frontend/src/api/`):

- `client.ts` — `GhostApi` interface (everything the UI needs).
- `http.ts` — real client, `VITE_API_BASE` default `http://127.0.0.1:8000`.
- `mock.ts` — in-memory fixture mock (simulated scan timing, demo failure
  scenarios).
- `index.ts` — `USING_FIXTURES = VITE_USE_FIXTURES !== 'false'`; fixtures are
  the default. Real backend needs `frontend/.env.local` with
  `VITE_USE_FIXTURES=false` + `VITE_API_BASE=http://127.0.0.1:8000`.

Pages (`frontend/src/pages/`): `Dashboard`, `FolderSelect`, `Scanning`,
`Files`, `Plan`, `Report`, `Activity`, `Completion`, `Settings`,
plus paper-redesign screens `start/*`, `totals/*`, `done/*` (Steps 1–4).
Key components: `shell/AppShell`, `documents/*`,
`plan/*`, `report/ExpenseReportTable`, `activity/ActivityTimeline`,
`pip/Pip`, `paper/*` (paper-sketch UI tokens).

**Backend requests R1–R8** from the paper redesign sit in
`docs/frontend-api-handoff.md` (background approve jobs, retry/cancel,
rescan-one-file, income/expense direction, candidate amounts, …) —
proposed, NOT agreed; treat as post-deadline unless the team explicitly
accepts one. R2/R5 are documentation-only answers Dev 1 can give.

State: `frontend/src/state/AppState.tsx` + `reducer.ts` — all backend calls
go through `api`; nothing touches the filesystem directly. Status bar polls
`getStatus` every 10 s. Scan progress polls every 500 ms.

Platform (`frontend/src/platform/`): `browser.ts` vs `electron.ts` adapters.
Only Electron (`window.ghostos` bridge, `contextIsolation: true`,
`nodeIntegration: false`) has a native folder picker; browser mode requires
a typed/pasted path.

Pure libs: `lib/money.ts` (BigInt-cents decimal math, no floats),
`lib/report.ts` (CSV export, accepted rows only), `lib/viewModel.ts`
(contract → table rows), `lib/format.ts`, `lib/labels.ts`, `lib/review.ts`,
`lib/steps.ts`, `lib/copy.ts`.
`lib/plan.ts` is obsolete (nothing imports it, safe to delete).

Fixtures: `frontend/src/fixtures/scan.json` (18 docs, 5 skipped, edge cases:
duplicates, timeout, injection, multi-currency, uncertain, missing date,
evidence mismatch), `status.json`.

## Git state (2026-10-10, pre-freeze)

- `main` @ `8069727` — includes: session-management layer, validation
  integration + prompt fix + SGD/JPY support, Dev 1's validator-safety rewrite
  (authoritative/component amounts, `quotation_document`, CORS) + tests,
  frontend QA/PiP/paper work (Steps 1–4 screens), vitest devDependency,
  `context.md`, `pyrightconfig.json`, and the e2e demo log
  (`tests/reports/e2e-demo-2026-10-10.md`).
- Flag-name mapping (validator → frontend): 8 codes identical; 3 renamed
  (`evidence_quote_not_found`→`evidence_not_found`,
  `invalid_amount_format`→`amount_unparseable`,
  `ambiguous_amount`→`amount_conflict`); unknown flags pass through.
- Older remote branches (may be merged or stale — check before reusing):
  `feature/phase2-step1-classify`, `feature/step3-scanner`,
  `feature/step4-extraction`, `developer-1-jj/phase1-step2-contracts`,
  `feature/frontend-fixture-ui`, `feature/phase2-step2-session-management`.

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
