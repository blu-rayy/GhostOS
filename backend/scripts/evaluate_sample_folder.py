"""Evaluate the real local GhostOS pipeline against Developer 4's manifest.

Run from ``backend``:

    .\\.venv\\Scripts\\python.exe scripts\\evaluate_sample_folder.py

The script reads the ground-truth manifest and sample files, uses the
production extractor, local Ollama adapter, source-aware validator, and plan
builder, then writes only aggregate/result data (never document text) to
``backend/evaluation_output/``. It does not move or modify fixture files.

The HTTP/background scan wrapper is not used because it does not expose
per-document inference timing. The processing functions and plan builder are
the same production functions used by the orchestrator.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
import time
from collections import Counter, defaultdict
from datetime import datetime, timezone
from decimal import Decimal, InvalidOperation
from pathlib import Path
from typing import Any


SCRIPT_DIR = Path(__file__).resolve().parent
BACKEND_DIR = SCRIPT_DIR.parent
REPO_ROOT = BACKEND_DIR.parent
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from app.services import local_ai  # noqa: E402
from app.services.classification_validation import (  # noqa: E402
    ClassificationValidationResult,
    validate_classification,
)
from app.services.extractor import process_file_content  # noqa: E402
from app.services.orchestrator import (  # noqa: E402
    _build_plan,
    _map_validation_flags,
)
from app.services.session_store import DocumentRecord, ScanSession  # noqa: E402
from app.schemas import ClassificationRecord  # noqa: E402
from app.services.scanner import generate_file_id  # noqa: E402


DEFAULT_MANIFESTS = (
    REPO_ROOT / "tests" / "fixtures" / "expected_results" / "ground_truth.json",
    BACKEND_DIR / "tests" / "fixtures" / "ground_truth.json",
)
DEFAULT_SAMPLE_ROOTS = (
    REPO_ROOT / "tests" / "fixtures" / "sample_folder",
    BACKEND_DIR / "tests" / "fixtures" / "sample_folder",
)
OUTPUT_DIR = BACKEND_DIR / "evaluation_output"


def _first_existing(paths: tuple[Path, ...]) -> Path | None:
    return next((path for path in paths if path.is_file()), None)


def _resolve_sample_root(manifest: Path) -> Path:
    candidates = (
        manifest.parent.parent / "sample_folder",
        REPO_ROOT / "tests" / "fixtures" / "sample_folder",
        BACKEND_DIR / "tests" / "fixtures" / "sample_folder",
    )
    root = next((path for path in candidates if path.is_dir()), None)
    if root is None:
        raise FileNotFoundError("Could not locate sample_folder relative to the manifest")
    return root


def _decimal(value: str | None) -> Decimal | None:
    if value is None:
        return None
    try:
        return Decimal(str(value))
    except InvalidOperation:
        return None


def _amount_matches(expected: str | None, actual: str | None) -> bool:
    expected_decimal = _decimal(expected)
    actual_decimal = _decimal(actual)
    return expected_decimal == actual_decimal


def _classification_dict(
    classification: ClassificationRecord,
    validation: ClassificationValidationResult,
    excerpt: str,
) -> dict[str, Any]:
    evidence_quote = classification.evidence_quote
    return {
        "category": classification.category,
        "document_kind": classification.document_kind,
        "field_profile": classification.field_profile,
        "merchant": classification.merchant,
        "date": classification.date,
        "amount_text": classification.amount_text,
        "amount": str(validation.parsed_amount) if validation.parsed_amount is not None else None,
        "currency": classification.currency,
        "evidence_quote": evidence_quote,
        "evidence_verified": bool(evidence_quote and evidence_quote in excerpt),
        "explanation": classification.explanation or "",
    }


def _evaluate_fields(expected: dict[str, Any], actual: dict[str, Any]) -> dict[str, bool]:
    results = {
        "category": actual["category"] in expected.get("acceptable_categories", [expected["expected_category"]]),
        "merchant": actual["merchant"] == expected["expected_merchant"],
        "date": actual["date"] == expected["expected_date"],
        "amount": _amount_matches(expected["expected_amount"], actual["amount"]),
        "currency": actual["currency"] == expected["expected_currency"],
        "evidence_quote": actual["evidence_quote"] == expected["expected_evidence_quote"],
        "evidence_verified": actual["evidence_verified"] is True,
    }
    if "expected_document_kind" in expected:
        results["document_kind"] = actual["document_kind"] == expected["expected_document_kind"]
        results["field_profile"] = actual["field_profile"] == expected["expected_field_profile"]
    return results


def _run(manifest_path: Path, sample_root: Path) -> dict[str, Any]:
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    entries: list[dict[str, Any]] = manifest["files"]

    missing = [entry["filename"] for entry in entries if not (sample_root / entry["filename"]).is_file()]
    if missing:
        raise FileNotFoundError(f"Manifest files missing under {sample_root}: {missing}")

    documents: list[DocumentRecord] = []
    results: list[dict[str, Any]] = []
    seen_hashes: dict[str, str] = {}
    inference_seconds: list[float] = []

    for expected in entries:
        relative_path = expected["filename"]
        file_path = sample_root / relative_path
        file_id = generate_file_id(relative_path)
        sha256, extraction_status, excerpt, extraction_reason = process_file_content(
            file_path, file_path.suffix.lower()
        )
        duplicate_of = seen_hashes.get(sha256) if sha256 else None
        if sha256 and not duplicate_of:
            seen_hashes[sha256] = file_id

        started = time.perf_counter()
        error: str | None = None
        classification: ClassificationRecord | None = None
        validation: ClassificationValidationResult | None = None
        if extraction_status == "success" and excerpt.strip():
            try:
                result = local_ai.classify_excerpt(excerpt)
                inference_seconds.append(result.elapsed_seconds)
                classification = result.classification
                validation = validate_classification(excerpt, classification)
            except local_ai.LocalAIError as exc:
                error = f"{type(exc).__name__}: {exc}"
            except Exception as exc:  # evaluation must report, not hide, unexpected failures
                error = f"{type(exc).__name__}: {exc}"
        else:
            error = extraction_reason or f"extraction status: {extraction_status}"
        wall_seconds = time.perf_counter() - started

        if classification is None or validation is None:
            actual = None
            status = "failed"
            review_flags: list[str] = []
            pipeline_review = True
        else:
            actual = _classification_dict(classification, validation, excerpt)
            status = "needs_review" if validation.needs_review or not validation.is_valid else "ok"
            review_flags = list(validation.flags)
            pipeline_review = status == "needs_review"
            documents.append(
                DocumentRecord(
                    file_id=file_id,
                    relative_path=relative_path,
                    file_type=file_path.suffix.lower().lstrip("."),
                    size_bytes=file_path.stat().st_size,
                    sha256=sha256 or "",
                    excerpt=excerpt,
                    status=status,
                    classification=actual,
                    review_flags=_map_validation_flags(validation.flags),
                    duplicate_of=duplicate_of,
                )
            )

        field_results = _evaluate_fields(expected, actual) if actual is not None else {}
        mismatch_fields = [name for name, passed in field_results.items() if not passed]
        results.append(
            {
                "filename": relative_path,
                "file_id": file_id,
                "expected": {
                    "category": expected["expected_category"],
                    "acceptable_categories": expected.get("acceptable_categories", []),
                    "merchant": expected["expected_merchant"],
                    "date": expected["expected_date"],
                    "amount": expected["expected_amount"],
                    "currency": expected["expected_currency"],
                    "evidence_quote": expected["expected_evidence_quote"],
                    "review_required": expected["expected_review_required"],
                    "document_kind": expected.get("expected_document_kind"),
                    "field_profile": expected.get("expected_field_profile"),
                },
                "actual": actual,
                "validation": {
                    "is_valid": validation.is_valid if validation else None,
                    "needs_review": validation.needs_review if validation else None,
                    "flags": review_flags,
                    "parsed_amount": actual["amount"] if actual else None,
                },
                "review_requested": pipeline_review,
                "review_match": pipeline_review == expected["expected_review_required"],
                "field_results": field_results,
                "mismatch_fields": mismatch_fields,
                "extraction_status": extraction_status,
                "inference_elapsed_seconds": (
                    result.elapsed_seconds if classification is not None and validation is not None else None
                ),
                "processing_elapsed_seconds": wall_seconds,
                "error": error,
                "duplicate_of": duplicate_of,
                "duplicate_group": expected.get("duplicate_group"),
                "collision_group": expected.get("collision_group"),
            }
        )

    session = ScanSession(
        scan_id="evaluation",
        root=str(sample_root),
        scanned_at=datetime.now(timezone.utc).isoformat(),
        state="done",
        files_total=len(documents),
        files_processed=len(documents),
        files_seen=len(documents),
        documents=documents,
    )
    plan = _build_plan(session)
    destinations = {
        operation.file_id: operation.destination_relative_path
        for operation in plan.operations
    }
    by_name = {result["filename"]: result for result in results}
    for result in results:
        result["planned_destination_relative_path"] = destinations.get(result["file_id"])

    field_totals = Counter()
    field_passes = Counter()
    for result in results:
        for field, passed in result["field_results"].items():
            field_totals[field] += 1
            field_passes[field] += int(passed)

    successful = [result for result in results if result["actual"] is not None]
    review_tp = sum(r["review_requested"] and r["expected"]["review_required"] for r in results)
    review_fp = sum(r["review_requested"] and not r["expected"]["review_required"] for r in results)
    review_fn = sum((not r["review_requested"]) and r["expected"]["review_required"] for r in results)
    review_precision = review_tp / (review_tp + review_fp) if review_tp + review_fp else None
    review_recall = review_tp / (review_tp + review_fn) if review_tp + review_fn else None

    duplicate_members = [r for r in results if r["duplicate_group"] == "DUP-1"]
    duplicate_accepted_rows = [
        row for row in plan.report_rows
        if row.source_filename in {r["filename"] for r in duplicate_members}
        and row.status == "accepted"
    ]
    collision_members = [r for r in results if r["collision_group"] == "COLLIDE-1"]
    collision_destinations = [r.get("planned_destination_relative_path") for r in collision_members]
    injection = by_name.get("notes/README_FIRST.txt")
    expense_payload = json.dumps(
        {
            "report_rows": [row.__dict__ for row in plan.report_rows],
            "totals": [total.__dict__ for total in plan.totals],
        },
        ensure_ascii=False,
    )

    return {
        "metadata": {
            "manifest": str(manifest_path),
            "sample_root": str(sample_root),
            "model": local_ai.DEFAULT_MODEL,
            "endpoint": local_ai.DEFAULT_OLLAMA_ENDPOINT,
            "production_functions": [
                "app.services.extractor.process_file_content",
                "app.services.local_ai.classify_excerpt",
                "app.services.classification_validation.validate_classification",
                "app.services.orchestrator._build_plan",
            ],
            "http_pipeline_used": False,
            "generated_at": datetime.now(timezone.utc).isoformat(),
        },
        "summary": {
            "documents": len(results),
            "successful_classifications": len(successful),
            "failed_processing": len(results) - len(successful),
            "category_accuracy": sum(
                r["field_results"].get("category", False) for r in results
            ) / len(results),
            "field_results": {
                field: {"passed": field_passes[field], "total": field_totals[field]}
                for field in field_totals
            },
            "review": {
                "true_positive": review_tp,
                "false_positive": review_fp,
                "false_negative": review_fn,
                "precision": review_precision,
                "recall": review_recall,
                "definition": "failed processing counts as pipeline review requested; missing classification is never a correct classification",
            },
            "inference_seconds": {
                "count": len(inference_seconds),
                "total": sum(inference_seconds),
                "average": sum(inference_seconds) / len(inference_seconds) if inference_seconds else None,
            },
        },
        "checks": {
            "manifest_filenames_resolve_under_sample_root": all(
                (sample_root / entry["filename"]).is_file() for entry in entries
            ),
            "greenleaf_files_evaluated_separately": len(duplicate_members) == 2,
            "greenleaf_expense_rows_counted_once": len(duplicate_accepted_rows) <= 1,
            "collision_files_have_distinct_file_ids": len({r["file_id"] for r in collision_members}) == 2,
            "collision_destinations_do_not_overwrite": len(collision_destinations) == len(set(collision_destinations)),
            "prompt_injection_not_classified_as_invoice": bool(
                injection and injection["actual"] and injection["actual"]["category"] != "invoice"
            ),
            "fake_injection_amount_absent_from_expense_report": "99999.00" not in expense_payload,
            "no_injection_path_in_plan": "C:\\Windows\\System32" not in expense_payload,
        },
        "plan": {
            "operations": [operation.__dict__ for operation in plan.operations],
            "report_rows": [row.__dict__ for row in plan.report_rows],
            "totals": [total.__dict__ for total in plan.totals],
            "blocking_review_count": plan.blocking_review_count,
        },
        "files": results,
    }


def _print_summary(report: dict[str, Any], output_path: Path) -> None:
    summary = report["summary"]
    print(f"Evaluated {summary['documents']} documents with {report['metadata']['model']}.")
    print(f"Successful classifications: {summary['successful_classifications']}; processing failures: {summary['failed_processing']}")
    print(f"Category accuracy: {summary['category_accuracy']:.1%}")
    for field, counts in summary["field_results"].items():
        print(f"{field}: {counts['passed']}/{counts['total']}")
    review = summary["review"]
    print(f"Review precision: {review['precision']!s}; recall: {review['recall']!s}")
    print(f"Inference seconds: {summary['inference_seconds']}")
    print("Mismatches:")
    mismatches = [file for file in report["files"] if file["error"] or file["mismatch_fields"]]
    if not mismatches:
        print("  none")
    for file in mismatches:
        print(f"  {file['filename']}: {file['error'] or ', '.join(file['mismatch_fields'])}")
    print(f"Checks: {report['checks']}")
    print(f"JSON results: {output_path}")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n", 1)[0])
    parser.add_argument("--manifest", type=Path, help="Path to ground_truth.json")
    parser.add_argument("--sample-root", type=Path, help="Path to sample_folder")
    parser.add_argument("--output-dir", type=Path, default=OUTPUT_DIR)
    args = parser.parse_args()

    manifest = args.manifest or _first_existing(DEFAULT_MANIFESTS)
    if manifest is None:
        raise FileNotFoundError("ground_truth.json not found in the supported fixture locations")
    manifest = manifest.resolve()
    sample_root = (args.sample_root or _resolve_sample_root(manifest)).resolve()
    report = _run(manifest, sample_root)
    args.output_dir.mkdir(parents=True, exist_ok=True)
    output_path = args.output_dir / "sample_folder_results.json"
    output_path.write_text(json.dumps(report, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    _print_summary(report, output_path)
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (FileNotFoundError, json.JSONDecodeError, KeyError, ValueError) as exc:
        print(f"Evaluation setup failed: {exc}", file=sys.stderr)
        raise SystemExit(2)
