# QA Phase 1 Checklist (H0–H4)

Owner: Developer 4. Hand off the H4 items to the team when they are done.

## 1. Inspect the repository

- [x] Record the repo layout, branch and existing tests.
- [x] Identify the test conventions: pytest under `backend/tests/`, run from `backend/`, with the `integration` marker for tests that need a real Ollama.
- [x] Note contract and behaviour gaps that affect QA (see [QA strategy → Known gaps](qa-strategy.md#known-gaps-found-during-phase-1-inspection)).

**Acceptance:** `git status` shows only new files under `tests/` and `docs/qa/`. No other developer's files are modified.

## 2. Set up the QA workspace

- [x] Create `tests/fixtures/{sample_folder,expected_results,edge_cases}/`, `tests/integration/`, `tests/reports/` and `docs/qa/`.
- [x] Write the QA README, this checklist, the fixture guide and the QA strategy.

**Acceptance:** all directories exist and are tracked through `.gitkeep`. The docs link to each other and to real paths.

## 3. Agree on the API contract (with Developer 1)

- [ ] Confirm the scan request and response field names (`root_path`, `FileRecord`). The frontend mock currently uses `root` and a different document shape.
- [ ] Agree on how skipped files are reported. Today unsupported, oversized and symlinked files are dropped silently.
- [ ] Agree where amount parsing (Decimal) and evidence-quote checking will live.

**Acceptance:** one written contract is referenced by both `backend/app/schemas.py` and `frontend/src/types/`, and open mismatches are listed with owners.

## 4. Fixture set (H4 deliverable)

- [x] Write the expected-results format: `tests/fixtures/expected_results/ground_truth.json` (see the [fixture guide](../../tests/fixtures/README.md)).
- [x] **Step 2:** build the 20-file synthetic sample dataset in `tests/fixtures/sample_folder/` (7 invoices, 7 receipts, 3 other, 3 uncertain). It covers a duplicate pair, a name collision, subtotal vs total, tax with a final total, contradictory amounts, a missing total and prompt injection.
- [x] Add a reproducible generator (`generate_sample_folder.py`) and an offline validator (`validate_fixtures.py`).
- [ ] Build the separate edge-case set in `tests/fixtures/edge_cases/`: empty file, image-only PDF, corrupt PDF, `.jpg`/`.docx`, and a receipt with no date. Symlinks and oversized files are generated at test time.

**Acceptance:** `validate_fixtures.py` exits 0 with PyMuPDF installed. Every file has a ground-truth entry, and every file is synthetic, with no real personal or financial data.

## 5. Check the local AI is ready (with Developer 2)

- [ ] Ollama is running at `127.0.0.1:11434` with `qwen3:4b-instruct` pulled.
- [ ] `pytest -m integration` in `backend/` passes with Wi-Fi **off**.

**Acceptance:** a result entry in `tests/reports/` records the date, model, pass/fail and the time per call.

## Exit criteria for Phase 1

- QA workspace and docs are merged.
- The contract mismatches and known gaps are known to their owners.
- The edge-case fixtures and expected-results format are ready for Developer 1's scan tests and Developer 3's UI flow.
