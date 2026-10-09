"""Batch evaluation of the live classifier + validator against ground truth.

Runs the real scan pipeline (extract -> classify -> validate) on every file in
``tests/fixtures/sample_folder/`` and compares each result with the expected
values in ``tests/fixtures/expected_results/ground_truth.json``.

Launch from the backend directory with:

    python scripts/evaluate_dataset.py

Requires the local Ollama model (qwen3:4b-instruct) to be running at
127.0.0.1:11434. Prints a per-file table and an accuracy summary. Does not
write any files.
"""

from __future__ import annotations

import json
import sys
import time
from pathlib import Path

# Make direct execution from the backend directory import the app package.
BACKEND_DIR = Path(__file__).resolve().parents[1]
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from app.services.extractor import process_file_content  # noqa: E402
from app.services.local_ai import (  # noqa: E402
    LocalAIError,
    classify_excerpt,
)
from app.services.classification_validation import (  # noqa: E402
    validate_classification,
)

REPO_ROOT = Path(__file__).resolve().parents[2]
GROUND_TRUTH_PATH = REPO_ROOT / "tests" / "fixtures" / "expected_results" / "ground_truth.json"
SAMPLE_DIR = REPO_ROOT / "tests" / "fixtures" / "sample_folder"


def _fmt(value: object) -> str:
    if value is None:
        return "-"
    return str(value)


def main() -> None:
    gt = json.loads(GROUND_TRUTH_PATH.read_text(encoding="utf-8"))
    files = gt["files"]

    print(f"Evaluating {len(files)} files against {GROUND_TRUTH_PATH.name} (v{gt['version']})")
    print(f"Model: qwen3:4b-instruct @ 127.0.0.1:11434")
    print()

    rows: list[dict] = []
    total_latency = 0.0

    for entry in files:
        rel = entry["filename"]
        path = SAMPLE_DIR / rel
        ext = path.suffix.lower()

        sha256, extraction_status, excerpt, reason = process_file_content(path, ext)
        if extraction_status != "success" or not excerpt.strip():
            rows.append({
                "filename": rel,
                "error": f"extraction {extraction_status}: {reason}",
            })
            continue

        try:
            started = time.perf_counter()
            result = classify_excerpt(excerpt)
            latency = time.perf_counter() - started
            validation = validate_classification(excerpt, result.classification)
        except LocalAIError as exc:
            rows.append({"filename": rel, "error": f"{type(exc).__name__}: {exc}"})
            continue

        total_latency += latency
        c = result.classification

        # Category: expected, or any acceptable alternative.
        category_ok = c.category in entry["acceptable_categories"]
        # Evidence: expected quote is a substring of the extracted text.
        evidence_ok = entry["expected_evidence_quote"] in excerpt
        # Review: flagged iff ground truth says review is required.
        review_ok = (validation.needs_review or not validation.is_valid) == entry["expected_review_required"]
        # Amount: exact decimal-string match (null == unparseable/ambiguous).
        actual_amount = str(validation.parsed_amount) if validation.parsed_amount is not None else None
        amount_ok = actual_amount == entry["expected_amount"]

        rows.append({
            "filename": rel,
            "category": c.category,
            "expected_category": entry["expected_category"],
            "category_ok": category_ok,
            "merchant": c.merchant,
            "expected_merchant": entry["expected_merchant"],
            "date": c.date,
            "expected_date": entry["expected_date"],
            "amount": actual_amount,
            "expected_amount": entry["expected_amount"],
            "amount_ok": amount_ok,
            "currency": c.currency,
            "expected_currency": entry["expected_currency"],
            "evidence_ok": evidence_ok,
            "review_flagged": validation.needs_review or not validation.is_valid,
            "review_required": entry["expected_review_required"],
            "review_ok": review_ok,
            "flags": list(validation.flags),
            "latency": latency,
        })

    # Per-file table
    for r in rows:
        if "error" in r:
            print(f"  [ERR] {r['filename']}: ERROR {r['error']}")
            continue
        print(f"  [{'OK' if r['category_ok'] else 'XX'}] {r['filename']}")
        print(f"      category={r['category']} (exp {r['expected_category']})  "
              f"amount={r['amount']} (exp {r['expected_amount']})  cur={r['currency']} (exp {r['expected_currency']})")
        if r['flags']:
            print(f"      flags={r['flags']}")
        if not r['category_ok'] or not r['amount_ok'] or not r['review_ok'] or not r['evidence_ok']:
            print(f"      MISMATCH: cat={r['category_ok']} amount={r['amount_ok']} "
                  f"evidence={r['evidence_ok']} review={r['review_ok']} (flagged={r['review_flagged']} vs required={r['review_required']})")

    # Summary
    n = len([r for r in rows if "error" not in r])
    cat_ok = sum(1 for r in rows if r.get("category_ok"))
    amt_ok = sum(1 for r in rows if r.get("amount_ok"))
    ev_ok = sum(1 for r in rows if r.get("evidence_ok"))
    rev_ok = sum(1 for r in rows if r.get("review_ok"))
    errors = sum(1 for r in rows if "error" in r)

    print()
    print("=" * 60)
    print(f"Category accuracy:  {cat_ok}/{n} ({cat_ok / n * 100:.0f}%)" if n else "no files")
    print(f"Amount accuracy:    {amt_ok}/{n} ({amt_ok / n * 100:.0f}%)" if n else "")
    print(f"Evidence present:   {ev_ok}/{n} ({ev_ok / n * 100:.0f}%)" if n else "")
    print(f"Review correctness: {rev_ok}/{n} ({rev_ok / n * 100:.0f}%)" if n else "")
    print(f"Errors:             {errors}")
    if n:
        print(f"Avg latency/file:   {total_latency / n:.2f}s (total {total_latency:.1f}s)")


if __name__ == "__main__":
    main()
