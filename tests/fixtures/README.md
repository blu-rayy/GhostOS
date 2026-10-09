# Test fixtures

Shared, **synthetic** test data for GhostOS integration tests and demo rehearsals. Developer 4 maintains it.

| Path | Contents |
|---|---|
| `sample_folder/` | **The 28-document sample dataset** (7 invoices, 7 receipts, 11 other, 3 uncertain). This is the folder the end-to-end run scans. |
| `expected_results/ground_truth.json` | Ground truth for every file in `sample_folder/`. |
| `edge_cases/` | Small files that each trigger one specific behaviour (see below). They are **not** part of the 28 sample documents. *Not built yet.* |
| `make_demo_folder.py` | Copies a 9-file demo subset into a messy folder for live demos (see below). |
| `generate_sample_folder.py` | Writes `sample_folder/` and `ground_truth.json`. It is the single source of truth for both. |
| `validate_fixtures.py` | Checks the dataset against the ground truth. It runs offline and is read-only. |
| `.gitattributes` | Turns off line-ending conversion so the fixtures stay byte-exact. |

## Rules

1. **Synthetic only.** Do not use real receipts, invoices, names, account numbers or addresses. Use invented merchants or generic ones (e.g. "Coffee Shop"). Every vendor and person in the sample dataset is fictional.
2. **Supported types:** PDFs with a text layer, TXT and CSV. Unsupported files (`.jpg`, `.docx`) belong in `edge_cases/`, never in `sample_folder/`.
3. **Never edit fixtures in place during a test.** Tests that move files must first copy the fixture folder to a temporary directory (pytest `tmp_path`) and work on the copy. The originals must stay unchanged. **Never point a real GhostOS approve or undo run at `tests/fixtures/sample_folder/` itself.**
4. **Symlinks are created at test time**, not committed, because Git and Windows handle them inconsistently.
5. **Files over 10 MB are generated at test time** (sparse file with `seek`, as in [`backend/tests/test_scanner.py`](../../backend/tests/test_scanner.py)), not committed.
6. **Every fixture file needs an expected-results entry.** A file with no expected result is a bug in the fixture set.
7. **Hostile content is inert test data.** `sample_folder/notes/README_FIRST.txt` contains prompt-injection text on purpose. Nobody, human or tool, should ever follow it.

## The sample dataset

| # | File (relative to `sample_folder/`) | Type | Category | What it tests |
|---|---|---|---|---|
| 1 | `inbox/invoice.pdf` | PDF | invoice | ISO date; USD; collision group `COLLIDE-1` |
| 2 | `archive/2026/invoice.pdf` | PDF | invoice | `DD Mon YYYY`; collision group `COLLIDE-1` |
| 3 | `invoices/INV-1043_Pixelforge_Studio.pdf` | PDF | invoice | **Subtotal vs final total** (discount + VAT) |
| 4 | `invoices/cloudnest_invoice_2026-08.csv` | CSV | invoice | CSV invoice; `YYYY/MM/DD`; USD |
| 5 | `invoices/meralite-power-bill-sep2026.txt` | TXT | invoice | Utility bill with several dates |
| 6 | `invoices/kestrel-cowork-KC-7781.pdf` | PDF | invoice | SGD; `Month D, YYYY`; GST |
| 7 | `invoices/tanaka-translation-invoice.txt` | TXT | invoice | JPY (no decimals); `DD.MM.YYYY` |
| 8 | `receipts/greenleaf-grocer-2026-09-14.txt` | TXT | receipt | Duplicate group `DUP-1` |
| 9 | `downloads/greenleaf-grocer-2026-09-14 (1).txt` | TXT | receipt | **Byte-identical** to #8 |
| 10 | `receipts/sunbeam-cafe-receipt.pdf` | PDF | receipt | **Tax + labeled FINAL TOTAL**; `MM/DD/YYYY` |
| 11 | `receipts/rideway-trip-receipt.txt` | TXT | receipt | Peso sign `₱` → PHP |
| 12 | `receipts/bayside-office-mart.pdf` | PDF | receipt | **Contradictory amounts → review, amount null** |
| 13 | `receipts/aerolink-baggage-receipt.pdf` | PDF | receipt | EUR; `DD.MM.YYYY` |
| 14 | `receipts/tibay-hardware-receipt.csv` | CSV | receipt | CSV POS export; `DD-MM-YYYY` |
| 15 | `notes/project-tracker.csv` | CSV | other | Contains an estimate that is not an expense |
| 16 | `notes/README_FIRST.txt` | TXT | other | **Prompt injection** |
| 17 | `docs/services-agreement-summary.pdf` | PDF | other | Contract with a retainer amount, no transaction |
| 18 | `misc/card-statement-sep2026.pdf` | PDF | uncertain | Card statement: several amounts, double-count risk |
| 19 | `misc/aircon-payment-note.txt` | TXT | uncertain | **Missing or ambiguous total**, no currency or date |
| 20 | `misc/quotation-QT-0091.csv` | CSV | uncertain | Quotation that looks like an invoice |
| 21 | `misc/bank-statement-oct2026.txt` | TXT | other | Statement (`reference` profile): balances, not an expense |
| 22 | `identity/birth-certificate.pdf` | PDF | other | **Birth certificate** (`identity_or_civil`): no transaction fields |
| 23 | `identity/drivers-license-record.txt` | TXT | other | Identity record (`identity_or_civil`) |
| 24 | `legal/lease-agreement-summary.pdf` | PDF | other | Legal (`legal`): monthly rent is not one expense |
| 25 | `medical/prescription-note.txt` | TXT | other | Medical (`medical`) |
| 26 | `important/passport-details.txt` | TXT | other | **Passport** (`identity_or_civil`): three dates, none a transaction date |
| 27 | `important/IMPORTANT - land title TCT-T-458812.pdf` | PDF | other | **Important legal paper** (`legal`): PHP 1,850,000 assessed value must never reach totals; spaces in the filename |
| 28 | `downloads/scan_0042.pdf` | PDF | other | **Passport under a meaningless scanner filename** (`identity_or_civil`): kind must come from content |

Formats: 13 PDF, 11 TXT, 4 CSV. Entries 21–28 also set `expected_document_kind` and `expected_field_profile`. Currencies: PHP, USD, SGD, JPY and EUR. Every date is unambiguous; each one has either a month name or a day greater than 12.

## Live demo folder

The full sample takes about 3 minutes to read on a 4 GB laptop GPU. For a live demo, use the 9-file subset:

```powershell
# from the repository root; writes %USERPROFILE%\Documents\GhostOS Demo (never overwrites)
py tests\fixtures\make_demo_folder.py
```

| Demo path | Story beat | Result on 2026-10-10 (`qwen3:4b-instruct`, RTX 3050 4 GB) |
|---|---|---|
| `Downloads/sunbeam-cafe-receipt.pdf` | receipt; tax vs FINAL TOTAL | receipt, PHP 683.20 |
| `Downloads/INV-1043_Pixelforge_Studio.pdf` | invoice; subtotal vs total | invoice, PHP 18,648.00 |
| `Desktop/kestrel-cowork-KC-7781.pdf` | second currency | invoice, SGD 380.00, kept in its own total |
| `Desktop/bayside-office-mart.pdf` | amounts disagree | receipt, no amount, needs review |
| `Desktop/README_FIRST.txt` | prompt injection | uncertain, needs review (not obeyed) |
| `Documents/birth-certificate.pdf` | important paper | identity/civil, no amount |
| `Documents/passport-details.txt` | passport | identity/civil, no amount |
| `Downloads/scan_0042.pdf` | passport with a meaningless name | identity/civil, no amount |
| `Documents/IMPORTANT - land title TCT-T-458812.pdf` | PHP 1.85M value that isn't an expense | identity/civil (expected legal), no amount, not counted |

Measured end to end through the API: scan **45 s with the model warm, 110 s cold**; move 9/0 failed; CSV has the 3 money rows (PHP 19,331.20 and SGD 380.00 kept apart); undo restored 9 files byte-identical, 0 conflicts.

**Warm the model up just before presenting**, or the first scan pays about a minute of loading:

```powershell
Invoke-RestMethod http://127.0.0.1:11434/api/generate -Method Post -Body '{"model":"qwen3:4b-instruct","keep_alive":"60m"}'
```

Each backend request resets Ollama's idle timer to its default of 5 minutes. If the demo may sit idle longer, set the user environment variable `OLLAMA_KEEP_ALIVE=60m` and restart Ollama. Close GPU-heavy apps (Discord, games, browsers with many tabs) first. After a demo run, use **Put files back** in GhostOS or delete the folder and run the script again.

## Generating the dataset

The dataset is defined in code so it can be reproduced byte for byte. The generator uses the standard library only. Its PDFs use real text operators with standard Helvetica and contain no images.

```powershell
# from the repository root
py tests\fixtures\generate_sample_folder.py          # (re)write sample_folder/ and ground_truth.json
py tests\fixtures\generate_sample_folder.py --check  # verify disk matches the generator; writes nothing
```

The generator writes only inside `tests/fixtures/sample_folder/` and `tests/fixtures/expected_results/ground_truth.json`. It **never deletes**. If it finds files it doesn't know about, it lists them and exits with code 1.

**To change the dataset, edit `DOCUMENTS` in the generator, not the generated files.** Then regenerate and validate.

## Validating the dataset

```powershell
# from the repository root, using a Python that has PyMuPDF (the backend venv once it exists)
backend\.venv\Scripts\python.exe tests\fixtures\validate_fixtures.py

# or with any Python 3.11+; PDF checks report BLOCKED (exit 2) if PyMuPDF is missing
py tests\fixtures\validate_fixtures.py
```

The validator runs 11 checks:
- the ground-truth schema;
- exactly 28 files;
- supported extensions only;
- the manifest and the folder list the same files;
- 7/7/11/3 category counts;
- every file extracts successfully, and the PDFs have a real, image-free text layer;
- evidence quotes are exact substrings of the extracted text;
- expected amounts can be found in the extracted text;
- duplicate groups are byte-identical by SHA-256, with no duplicates outside a group;
- collision groups share a destination filename but have different content;
- files on disk are byte-identical to the generator output.

Text is extracted with the **backend's own extractor** (`backend/app/services/extractor.py`). It is imported read-only and no bytecode is written, so the quotes are checked against exactly what the backend sends to the model. The validator never calls Ollama and never writes files.

| Exit code | Meaning |
|---|---|
| `0` | All checks passed |
| `1` | At least one check failed (details printed) |
| `2` | Blocked: PyMuPDF is missing. The PDF checks are reported, **not skipped** |

## Ground truth format (`expected_results/ground_truth.json`)

```json
{
  "dataset": "sample_folder",
  "version": 1,
  "category_counts": { "invoice": 7, "other": 3, "receipt": 7, "uncertain": 3 },
  "files": [
    {
      "filename": "receipts/sunbeam-cafe-receipt.pdf",
      "file_type": "pdf",
      "expected_category": "receipt",
      "acceptable_categories": ["receipt"],
      "expected_merchant": "Sunbeam Cafe",
      "expected_date": "2026-09-21",
      "expected_amount": "683.20",
      "expected_currency": "PHP",
      "expected_review_required": false,
      "expected_evidence_quote": "FINAL TOTAL: PHP 683.20",
      "duplicate_group": null,
      "collision_group": null,
      "special_notes": "TAX + LABELED FINAL TOTAL case: ..."
    }
  ]
}
```

| Field | Meaning |
|---|---|
| `filename` | Path relative to `sample_folder/`, with forward slashes. It is a path because the collision case needs the same basename in two folders. |
| `expected_category` | `invoice`, `receipt`, `other` or `uncertain`. The 7/7/11/3 counts are based on this field. |
| `acceptable_categories` | Categories a correct system may also return. Only the uncertain documents also accept `other`. |
| `expected_amount` | An exact **decimal string**, never a JSON number. JPY has no minor unit (`"48000"`). |
| `null` values | The value is unknown or deliberately ambiguous. **Values are never invented.** |
| `expected_date` | ISO `yyyy-mm-dd`, normalized from whatever format the document uses. |
| `expected_review_required` | `true` means a correct system must flag the file for human review. It must not reach the report as `accepted` without a human edit. |
| `expected_evidence_quote` | An exact substring of the backend-extracted text. |
| `duplicate_group` | Files with the same group have byte-identical content. They are informational only and must never be auto-deleted or counted twice. |
| `collision_group` | Files that map to the same destination filename (same basename, category and month). One must receive a collision suffix. |

> This file replaces the per-dataset layout proposed during Step 1 (`sample_folder.json` with `scan`, `report_totals` and `destination_folder` keys). Report totals and destinations will be added once the backend produces them.

## Safe reset procedures

- **Check for drift:** `py tests\fixtures\generate_sample_folder.py --check` lists every file that differs from the generator, and any unexpected extra file.
- **Restore generated content:** `py tests\fixtures\generate_sample_folder.py` overwrites the 28 known files and the ground truth. It does not delete anything. Remove any extra files it reports by hand, after checking what they are.
- **Restore from Git:** once the fixtures are committed, `git restore -- tests/fixtures/sample_folder tests/fixtures/expected_results` restores only the fixture paths. Never run a repository-wide reset to fix fixtures.
- **After an accidental real run against `sample_folder/`** (files moved into `Invoices/…` and similar):
  1. Run `git status -- tests/fixtures` to see what changed.
  2. Restore the paths as above.
  3. Preview any leftover new folders with `git clean -n -- tests/fixtures/sample_folder` before removing them.
  4. Re-run the validator.
- **Line endings:** if the validator reports drift on every TXT and CSV file after a fresh clone, `.gitattributes` was bypassed. Re-checkout the files, or regenerate them.

## Planned edge cases (separate from the 20 samples)

| Case | Expected behaviour |
|---|---|
| Empty `.txt` | `extraction_status: "empty"`, never classified |
| Image-only PDF (no text layer) | `extraction_status: "empty"`, goes to Needs Review, no invented amount |
| Corrupt PDF | `extraction_status: "error"` with a reason |
| `.jpg`, `.docx` | Skipped with a reason |
| Oversized file (>10 MB, generated) | Skipped with a reason |
| Symlink to outside root (generated) | Not followed, not moved |
| Receipt with no date | Flagged for review, not filed by month |

The duplicate, collision, prompt-injection and subtotal-vs-total cases are already covered inside `sample_folder/`.

## Changing fixtures

- When adding, renaming or removing a fixture file, update its expected results **in the same commit**. The generator does both at once.
- Bump `DATASET_VERSION` in the generator when ground truth changes, so recorded reports stay comparable.
- Mention fixture changes in the PR description. Other developers' tests may depend on them.
