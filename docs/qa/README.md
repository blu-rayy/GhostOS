# GhostOS QA — Developer 4

Developer 4 owns **integration and quality assurance**. The job is to show, with recorded evidence, that the GhostOS workflow is safe and correct on the demo laptop with Wi-Fi off. The workflow is scan → classify → preview → approve → report → undo.

## Responsibilities

| Area | What Developer 4 does |
|---|---|
| Test data | Builds and maintains the sample dataset, edge-case files and expected results in [`tests/fixtures/`](../../tests/fixtures/). |
| Integration | Owns the integration branch and merges small increments from Developers 1–3 about every two hours. Checks that backend responses match the API contract the frontend uses. |
| Integration tests | Writes cross-component tests in [`tests/integration/`](../../tests/integration/). Unit tests stay with each owner (e.g. [`backend/tests/`](../../backend/tests/)). |
| Safety checks | Verifies that no file moves before approval, no writes happen outside the chosen root, nothing is overwritten, and undo restores files. |
| Report correctness | Checks that the expense CSV rows and totals match the expected results exactly. |
| Offline gate | Runs the full workflow with networking disabled and records the result. |
| Results log | Records observed pass/fail results in [`tests/reports/`](../../tests/reports/). These are observations, not accuracy claims. |
| Demo | Prepares the offline demo run, the backup dataset and the pitch with the team. |

Developer 4 does **not** change production code owned by other developers. Defects go back to the owner with:
- a reproduction,
- the fixture that triggers it,
- the expected and observed results.

## Handoffs (from the build plan)

| When | Deliverable |
|---|---|
| H4 | Fixture set and QA workspace (this phase) |
| H12 | End-to-end smoke test on the integrated build |
| H14–18 | Tests on unseen data, offline operation, symlinks, duplicates, collisions and partial failures |
| H21–24 | Two timed demo rehearsals from a clean restart with networking disabled |

## Documents

- [QA strategy](qa-strategy.md): what is tested and how, per feature area.
- [Phase 1 checklist](phase1-checklist.md): H0–H4 tasks and acceptance criteria.
- [Fixture guide](../../tests/fixtures/README.md): how sample files and expected results are maintained.

## Where tests live

```
backend/tests/          Unit tests: owned by Developers 1 and 2 (pytest, run from backend/)
tests/integration/      Cross-component tests: owned by Developer 4
tests/fixtures/         Shared sample files and expected results: owned by Developer 4
tests/reports/          Recorded QA run results: owned by Developer 4
```
