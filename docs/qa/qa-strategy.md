# GhostOS QA Strategy

**Goal:** show, with recorded evidence, that GhostOS meets the build plan's acceptance gate on the demo laptop with Wi-Fi off, using a fresh, unseen folder of about 20 supported files. The gate:

- ≥ 80% of clearly identifiable invoices and receipts land in the correct preview category.
- **No moves happen without approval.**
- **No writes happen outside the chosen root.**
- Report totals equal the sum of the accepted extracted rows.
- Every moved file can be restored with undo.

These are team test targets, not claims of measured performance. Results are recorded only as observed on our test sets.

## Test levels

| Level | Where | Who | Runs |
|---|---|---|---|
| Unit | `backend/tests/` | Developers 1 and 2 | `python -m pytest` in `backend/` |
| Model integration | `backend/tests/` with `@pytest.mark.integration` | Developer 2 | `python -m pytest -m integration` with Ollama running |
| Cross-component integration | `tests/integration/` | Developer 4 | API + real fixtures copied into `tmp_path` |
| End-to-end / manual | UI + backend + Ollama | Developer 4 | Scripted checklist; results in `tests/reports/` |

**Severity:**
- **S1:** a safety violation (data loss, write outside the root, move without approval, invented amount accepted). It blocks the demo.
- **S2:** a wrong result the user can see and fix.
- **S3:** cosmetic.

---

## 1. Scanning TXT, CSV and text-based PDF

**Checks**
- Recursive discovery finds every `.pdf`, `.txt` and `.csv`. Extensions match case-insensitively (`.PDF`).
- Each included file has a `file_id`, a `relative_path` (forward slashes), `filename`, `extension`, `size_bytes` and `sha256`.
- `extraction_status` is correct: `success` for files with text, `empty` for empty files and image-only PDFs, `error` for corrupt files (with a `reason`).
- The excerpt is bounded (the extractor caps it at 1,500 characters). Non-UTF-8 text does not crash the scan.
- Limits:
  - The scan stops at 100 files.
  - Files over 10 MB are skipped.
  - A symlinked root is rejected with HTTP 400.
  - Symlinked files are not followed.
- Unsupported types are not extracted.
- **Scanning never modifies the source folder.** Hash the whole tree before and after the scan, and compare file mtimes.

**Method:** integration tests against `POST /api/scan` on a copy of `edge_cases/`. Oversized files and symlinks are generated at test time.

**Pass:** every file in `tests/fixtures/expected_results/ground_truth.json` is returned with `extraction_status: "success"` and its `expected_evidence_quote` inside `text_excerpt`. Edge-case expectations are still to be written. The before/after tree hashes are identical.

## 2. Classification: invoice, receipt, other, uncertain

**Checks**
- The category is always one of the four values. Pydantic `extra="forbid"` rejects any extra keys from the model.
- Clear invoices and clear receipts are classified correctly. Notes and plans are classified as `other`. A bank statement or ambiguous text is classified as `other` or `uncertain`, **never** forced into invoice or receipt with full confidence.
- A failed model call (timeout, invalid JSON, schema failure) leads to Needs Review. It is never a guessed category.
- **Prompt injection:** a document telling the model to change rules or run commands is treated as data. The output contains no paths, commands or file operations.

**Method:** model-integration tests with Ollama running, on fixture excerpts. Record accuracy per category against the expected results.

**Pass:** ≥ 80% correct on the clearly identifiable invoices and receipts. There must be 0 cases where an injection fixture changes behaviour.

## 3. Evidence and financial field verification

**Checks**
- `evidence_quote` appears **verbatim** in the extracted text. A quote that does not appear must produce a review flag, not be accepted silently.
- `amount_text` is parsed with `Decimal` into a canonical amount. Ambiguous or conflicting values (subtotal ≠ total, several totals) are flagged for review, not picked arbitrarily.
- `date` is normalized to ISO format. A missing date leads to review, never a made-up date.
- `currency` is an ISO code, or is flagged for review when absent.
- Failed extraction never produces an amount.

**Method:** unit tests on the validation layer (once it exists) plus integration tests using fixtures with known amounts.

**Pass:** 0 accepted rows whose amount is not supported by the document text.

## 4. Exact duplicate detection

**Checks**
- Byte-identical files share a `sha256` and are flagged as duplicates.
- Files with the same name but different content are **not** duplicates.
- Duplicate detection is informational only: **neither copy is deleted**, and the user sees both.
- A duplicate is not counted twice in the report total.

**Pass:** duplicate pairs are identified as in the expected results, and the file count after approval equals the file count before it.

## 5. Name collisions and path safety

**Checks**
- Two files that map to the same destination both survive. The second gets a collision suffix, and nothing is overwritten.
- Every destination is built by code from the fixed category map. **No model output is used as a path.**
- Every destination resolves inside the chosen root. Test traversal attempts such as `..`, absolute paths, drive letters and UNC paths in any user-editable field.
- Symlinks inside the root are not followed during the move.
- Paths are checked again immediately before each move. A file changed or replaced between preview and approval is handled safely.
- Windows specifics:
  - Case-insensitive collisions (`Receipt.pdf` vs `receipt.pdf`).
  - Long paths.
  - Reserved names (`CON`, `NUL`).
  - Trailing dots and spaces.

**Pass:** 0 writes outside the root and 0 overwritten files across all collision and traversal fixtures.

## 6. Preview before approval

**Checks**
- Scan and plan endpoints are **read-only**. Hash the whole tree before and after preview; the hashes must be identical.
- The preview lists every proposed operation with its original path, destination and reason.
- Approval is impossible while blocking review items remain, in both the UI and the API. Test the API directly, not just the disabled button.
- An approved plan executes exactly the previewed operations, no more and no fewer.

**Pass:** the tree is unchanged after preview, and the operations performed equal the operations previewed.

## 7. CSV expense report correctness

**Checks**
- One row per invoice or receipt, each with its source filename and status (`accepted` / `needs_review`).
- Totals are per currency and cover **accepted rows only**. Different currencies are never summed together.
- Sums are compared exactly as `Decimal`, with no float drift.
- The CSV is well formed: it opens in Excel and LibreOffice, quotes commas in merchant names, and handles UTF-8 (₱).
- The report is written atomically (temporary file, then replace) and includes a generation timestamp.
- Totals match `expected_results → report_totals` exactly.

**Pass:** the CSV totals equal the expected totals to the cent, and every row traces back to a source file.

## 8. Batch undo and offline execution

**Undo checks**
- Undo restores every moved file to its original path, and the tree hash matches the pre-approval hash.
- Conflicts are reported, not forced:
  - The original path is occupied again.
  - The moved file was edited or renamed after approval.
- Undo continues safely after an interrupted move: it uses the manifest and never guesses.
- Undo never deletes user files. The generated report may be kept or removed, as the team decides.

**Offline checks**
- With Wi-Fi off and the network adapter disabled: scan, classify, preview, approve, report and undo all complete.
- The status bar shows the model name and the local endpoint, and zero external requests.
- No network calls other than loopback. Verify with `netstat`/`Get-NetTCPConnection` or a firewall rule blocking outbound traffic during the run.
- There is no silent cloud fallback.

**Pass:** the full demo script finishes in under 4 minutes offline, and undo leaves the tree identical to before approval.

---

## Known gaps found during Phase 1 inspection

These come from reading the code on `main` at commit `c22e517`. They are reported to the owners, not fixed by QA.

| # | Observation | Where | Impact | Owner |
|---|---|---|---|---|
| G1 | Unsupported, oversized, symlinked, out-of-root and unreadable files are **dropped silently**, with no record or reason. The plan requires skipping them "with reasons". | `backend/app/services/scanner.py` (`continue` branches) | The user can't see why a file is missing (S2) | Dev 1 |
| G2 | `ClassificationRecord` has `amount_text` but no parsed `Decimal` amount, and no evidence-verified flag yet. | `backend/app/schemas.py` | Areas 3 and 7 can't be tested yet. Expected in Phase 2. | Dev 1 / Dev 2 |
| G3 | The frontend mock contract (`root`, `DocumentRecord`, `excerpt`) differs from the backend (`root_path`, `FileRecord`, `text_excerpt`). | `frontend/src/types/`, `frontend/src/api/` vs `backend/app/schemas.py` | Integration will break until aligned (S2) | Dev 1 / Dev 3 |
| G4 | `file_id` is `md5(relative_path)[:8]`, so it changes when a file moves. | `scanner.py` `generate_file_id` | Undo must key on the manifest and file identity (hash), not `file_id` | Dev 1 |
| G5 | The 100-file limit counts supported files only. Truncation isn't reported. | `scanner.py` | The user doesn't know a scan was truncated (S3) | Dev 1 |
| G6 | Excerpt limits differ: 1,500 characters in the extractor, 2,000 in the schema, 8,000 in the AI adapter. | `extractor.py`, `schemas.py`, `local_ai.py` | Consistent today (1,500 is smallest). Watch for drift. | Dev 1 / Dev 2 |

## Recording results

Each QA run produces a Markdown file in `tests/reports/` named `YYYY-MM-DD_HHMM_<scope>.md` containing:
- the commit hash, model name, dataset and version, and whether the network was on or off;
- pass/fail per area, with failing fixture names;
- timings for the scan, the per-file classification and the end-to-end run.

Generated artifacts such as CSVs and logs from a run may be committed when they serve as evidence. Do not commit any data copied from a real folder.
