"""Validate the GhostOS synthetic QA fixture dataset.

Checks tests/fixtures/sample_folder/ against
tests/fixtures/expected_results/ground_truth.json:

  1. ground-truth schema (types, enums, decimal-string amounts, ISO dates)
  2. exactly 20 files in the sample folder
  3. only supported extensions (.pdf, .txt, .csv)
  4. manifest and folder list the same files
  5. category counts are 7 invoice / 7 receipt / 3 other / 3 uncertain
  6. every file extracts successfully; PDFs have a real, image-free text layer
  7. every expected_evidence_quote is an exact substring of the extracted text
  8. every non-null expected_amount is traceable in the extracted text
  9. duplicate groups are byte-identical (SHA-256) and there are no unlisted duplicates
 10. collision groups share a destination filename but are different files
 11. files on disk match the generator (reproducibility)

Text is extracted with the backend's own extractor (backend/app/services/extractor.py),
imported read-only with bytecode writing disabled, so evidence quotes are checked against
exactly what the backend will send to the model. It never calls Ollama, never writes files,
and never modifies the fixtures or production code.

Exit codes: 0 = all checks passed, 1 = at least one check failed,
2 = blocked (a required dependency such as PyMuPDF is missing).

Usage (from the repository root, PowerShell):
    py tests\\fixtures\\validate_fixtures.py
"""

from __future__ import annotations

import hashlib
import importlib.util
import json
import re
import sys
from collections import Counter, defaultdict
from datetime import date
from pathlib import Path

sys.dont_write_bytecode = True  # never leave __pycache__ in backend/ or tests/

FIXTURES_DIR = Path(__file__).resolve().parent
REPO_ROOT = FIXTURES_DIR.parent.parent
SAMPLE_DIR = FIXTURES_DIR / "sample_folder"
GROUND_TRUTH_PATH = FIXTURES_DIR / "expected_results" / "ground_truth.json"
BACKEND_DIR = REPO_ROOT / "backend"

EXPECTED_FILE_COUNT = 20
EXPECTED_COUNTS = {"invoice": 7, "receipt": 7, "other": 3, "uncertain": 3}
SUPPORTED_EXTENSIONS = {".pdf", ".txt", ".csv"}
CATEGORIES = set(EXPECTED_COUNTS)
REQUIRED_FIELDS = {
    "filename": str,
    "expected_category": str,
    "expected_merchant": (str, type(None)),
    "expected_date": (str, type(None)),
    "expected_amount": (str, type(None)),
    "expected_currency": (str, type(None)),
    "expected_review_required": bool,
    "expected_evidence_quote": str,
    "duplicate_group": (str, type(None)),
    "collision_group": (str, type(None)),
    "special_notes": str,
}
DECIMAL_RE = re.compile(r"^\d+(\.\d{2})?$")
CURRENCY_RE = re.compile(r"^[A-Z]{3}$")


class Report:
    def __init__(self) -> None:
        self.results: list[tuple[str, str, list[str]]] = []

    def add(self, name: str, problems: list[str], blocked: list[str] | None = None) -> None:
        if blocked:
            self.results.append(("BLOCKED", name, blocked + problems))
        elif problems:
            self.results.append(("FAIL", name, problems))
        else:
            self.results.append(("PASS", name, []))

    def print_and_exit_code(self) -> int:
        for status, name, details in self.results:
            print(f"[{status:7}] {name}")
            for d in details:
                print(f"            - {d}")
        statuses = Counter(s for s, _, _ in self.results)
        print(
            f"\nSummary: {statuses['PASS']} passed, {statuses['FAIL']} failed, "
            f"{statuses['BLOCKED']} blocked (of {len(self.results)} checks)"
        )
        if statuses["FAIL"]:
            print("RESULT: FAIL")
            return 1
        if statuses["BLOCKED"]:
            print("RESULT: BLOCKED - install the missing dependency and re-run; PDF checks were NOT skipped silently.")
            return 2
        print("RESULT: PASS")
        return 0


def sha256_of(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def load_extractor():
    """Return (process_file_content, fitz) or (None, None, reason)."""
    try:
        import fitz  # noqa: F401  (PyMuPDF)
    except ImportError:
        return None, None, (
            "PyMuPDF (module 'fitz') is not installed for this Python. It is a declared backend "
            "dependency (backend/requirements.txt). Run this script with the backend virtual "
            "environment, e.g. backend\\.venv\\Scripts\\python.exe tests\\fixtures\\validate_fixtures.py"
        )
    sys.path.insert(0, str(BACKEND_DIR))
    try:
        from app.services.extractor import process_file_content  # type: ignore[import-not-found]
    except Exception as exc:  # pragma: no cover - reported, not hidden
        return None, None, f"Could not import backend extractor: {exc!r}"
    import fitz

    return process_file_content, fitz, None


def plain_excerpt(path: Path) -> str:
    """Mirror of the backend's TXT/CSV extraction, used only when PyMuPDF is unavailable."""
    with open(path, "r", encoding="utf-8", errors="replace") as f:
        return f.read(1600).strip()[:1500]


def main() -> int:
    report = Report()

    # 1. ground truth schema ------------------------------------------------
    try:
        # utf-8-sig: tolerate a BOM added by Windows editors; the generator check still flags the drift.
        manifest = json.loads(GROUND_TRUTH_PATH.read_text(encoding="utf-8-sig"))
        entries = manifest["files"]
    except Exception as exc:
        print(f"Cannot read ground truth {GROUND_TRUTH_PATH}: {exc}")
        return 1

    problems = []
    names = [e.get("filename") for e in entries]
    for dup, n in Counter(names).items():
        if n > 1:
            problems.append(f"filename listed {n} times: {dup}")
    for e in entries:
        fn = e.get("filename", "<missing filename>")
        for field, typ in REQUIRED_FIELDS.items():
            if field not in e:
                problems.append(f"{fn}: missing field '{field}'")
            elif not isinstance(e[field], typ):
                problems.append(f"{fn}: field '{field}' has type {type(e[field]).__name__}")
        if e.get("expected_category") not in CATEGORIES:
            problems.append(f"{fn}: invalid expected_category {e.get('expected_category')!r}")
        for cat in e.get("acceptable_categories", []):
            if cat not in CATEGORIES:
                problems.append(f"{fn}: invalid acceptable category {cat!r}")
        amount = e.get("expected_amount")
        if isinstance(amount, str) and not DECIMAL_RE.match(amount):
            problems.append(f"{fn}: expected_amount {amount!r} is not a plain decimal string")
        if isinstance(amount, (int, float)) and not isinstance(amount, bool):
            problems.append(f"{fn}: expected_amount is a JSON number; use a decimal string")
        currency = e.get("expected_currency")
        if isinstance(currency, str) and not CURRENCY_RE.match(currency):
            problems.append(f"{fn}: expected_currency {currency!r} is not an ISO 4217 code")
        d = e.get("expected_date")
        if isinstance(d, str):
            try:
                if date.fromisoformat(d).isoformat() != d:
                    raise ValueError
            except ValueError:
                problems.append(f"{fn}: expected_date {d!r} is not ISO yyyy-mm-dd")
        if isinstance(e.get("expected_evidence_quote"), str) and not e["expected_evidence_quote"].strip():
            problems.append(f"{fn}: expected_evidence_quote is empty")
    report.add(f"Ground truth schema ({len(entries)} entries)", problems)

    # 2-4. folder contents ---------------------------------------------------
    disk_files = sorted(p for p in SAMPLE_DIR.rglob("*") if p.is_file()) if SAMPLE_DIR.is_dir() else []
    rel_disk = {p.relative_to(SAMPLE_DIR).as_posix() for p in disk_files}

    report.add(
        f"Sample folder has exactly {EXPECTED_FILE_COUNT} files",
        [] if len(disk_files) == EXPECTED_FILE_COUNT else [f"found {len(disk_files)} files"],
    )
    report.add(
        "All files use supported extensions (.pdf, .txt, .csv)",
        [f"unsupported: {r}" for r in sorted(rel_disk) if Path(r).suffix.lower() not in SUPPORTED_EXTENSIONS],
    )
    problems = [f"listed in manifest but missing on disk: {n}" for n in names if n not in rel_disk]
    problems += [f"on disk but not in manifest: {r}" for r in sorted(rel_disk - set(names))]
    report.add("Manifest filenames exist and cover every file", problems)

    # 5. category counts -----------------------------------------------------
    counts = Counter(e.get("expected_category") for e in entries)
    problems = [
        f"{cat}: expected {want}, found {counts.get(cat, 0)}"
        for cat, want in EXPECTED_COUNTS.items()
        if counts.get(cat, 0) != want
    ]
    if manifest.get("category_counts") and manifest["category_counts"] != dict(sorted(counts.items())):
        problems.append(f"category_counts summary {manifest['category_counts']} disagrees with entries")
    report.add("Category counts are 7 invoice / 7 receipt / 3 other / 3 uncertain", problems)

    # 6. extraction ----------------------------------------------------------
    process_file_content, fitz, blocker = load_extractor()
    present = [e for e in entries if e["filename"] in rel_disk]
    excerpts: dict[str, str] = {}
    problems = []
    pdf_blocked = []
    for e in present:
        fn = e["filename"]
        path = SAMPLE_DIR / fn
        suffix = path.suffix.lower()
        if process_file_content is None:
            if suffix == ".pdf":
                pdf_blocked.append(fn)
                continue
            excerpts[fn] = plain_excerpt(path)
            if not excerpts[fn]:
                problems.append(f"{fn}: no text extracted")
            continue
        _sha, status, excerpt, reason = process_file_content(path, suffix)
        excerpts[fn] = excerpt
        if status != "success":
            problems.append(f"{fn}: backend extraction_status={status!r} reason={reason!r}")
        if suffix == ".pdf":
            with fitz.open(path) as doc:
                if doc.page_count < 1:
                    problems.append(f"{fn}: PDF has no pages")
                for page in doc:
                    if page.get_images():
                        problems.append(f"{fn}: page {page.number + 1} contains images (possible rasterized text)")
                    if not page.get_text().strip():
                        problems.append(f"{fn}: page {page.number + 1} has no extractable text")
    blocked = [blocker, f"PDF files not checked: {len(pdf_blocked)}"] if pdf_blocked else None
    report.add("All files extract successfully; PDFs have an image-free text layer", problems, blocked)

    # 7. evidence quotes -----------------------------------------------------
    problems = []
    for e in present:
        fn = e["filename"]
        if fn not in excerpts:
            continue
        if e["expected_evidence_quote"] not in excerpts[fn]:
            problems.append(f"{fn}: evidence quote not found verbatim: {e['expected_evidence_quote']!r}")
    report.add(
        "Evidence quotes are exact substrings of the backend-extracted text",
        problems,
        [blocker, f"evidence not checked for {len(pdf_blocked)} PDF files"] if pdf_blocked else None,
    )

    # 8. amounts traceable ---------------------------------------------------
    problems = []
    for e in present:
        fn, amount = e["filename"], e["expected_amount"]
        if amount is None or fn not in excerpts:
            continue
        if amount not in excerpts[fn].replace(",", ""):
            problems.append(f"{fn}: expected_amount {amount} does not appear in the extracted text")
    report.add(
        "Non-null expected amounts appear in the extracted text",
        problems,
        [blocker, f"amounts not checked for {len(pdf_blocked)} PDF files"] if pdf_blocked else None,
    )

    # 9. duplicates ----------------------------------------------------------
    hashes = {e["filename"]: sha256_of(SAMPLE_DIR / e["filename"]) for e in present}
    groups: dict[str, list[str]] = defaultdict(list)
    for e in present:
        if e.get("duplicate_group"):
            groups[e["duplicate_group"]].append(e["filename"])
    problems = []
    if not groups:
        problems.append("no duplicate_group defined; at least one byte-identical pair is required")
    for g, members in groups.items():
        if len(members) < 2:
            problems.append(f"{g}: needs at least 2 members, has {members}")
        if len({hashes[m] for m in members}) != 1:
            problems.append(f"{g}: members are not byte-identical: {members}")
        if len({(entry["expected_category"]) for entry in present if entry["filename"] in members}) != 1:
            problems.append(f"{g}: members have different expected categories")
    by_hash: dict[str, list[str]] = defaultdict(list)
    for fn, h in hashes.items():
        by_hash[h].append(fn)
    group_of = {e["filename"]: e.get("duplicate_group") for e in present}
    for h, members in by_hash.items():
        member_groups = {group_of[m] for m in members}
        if len(members) > 1 and (None in member_groups or len(member_groups) != 1):
            problems.append(f"unlisted identical files (sha256 {h[:12]}...): {members}")
    detail = ", ".join(f"{g}={hashes[m[0]][:12]}..." for g, m in groups.items() if m)
    report.add(f"Exact duplicate groups verified by SHA-256 ({detail})", problems)

    # 10. collisions ---------------------------------------------------------
    cgroups: dict[str, list[dict]] = defaultdict(list)
    for e in present:
        if e.get("collision_group"):
            cgroups[e["collision_group"]].append(e)
    problems = []
    if not cgroups:
        problems.append("no collision_group defined; at least one destination-name collision is required")
    for g, members in cgroups.items():
        fns = [m["filename"] for m in members]
        if len(members) < 2:
            problems.append(f"{g}: needs at least 2 members, has {fns}")
        if len({Path(f).name.lower() for f in fns}) != 1:
            problems.append(f"{g}: members do not share a basename: {fns}")
        if len({m["expected_category"] for m in members}) != 1:
            problems.append(f"{g}: members have different categories, so destinations would differ")
        months = {(m["expected_date"] or "")[:7] for m in members}
        if len(months) != 1 or "" in months:
            problems.append(f"{g}: members are not dated in the same month: {sorted(months)}")
        if len({hashes[f] for f in fns}) != len(fns):
            problems.append(f"{g}: members are byte-identical; a collision case must use different content")
    report.add("Collision groups share a destination filename but differ in content", problems)

    # 11. reproducibility ----------------------------------------------------
    problems = []
    gen_path = FIXTURES_DIR / "generate_sample_folder.py"
    if not gen_path.is_file():
        problems.append("generator script missing")
    else:
        spec = importlib.util.spec_from_file_location("ghostos_fixture_generator", gen_path)
        gen = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(gen)  # type: ignore[union-attr]
        for path, data in gen.planned_outputs().items():
            rel = path.relative_to(FIXTURES_DIR).as_posix()
            if not path.is_file():
                problems.append(f"{rel}: missing")
            elif path.read_bytes() != data:
                problems.append(f"{rel}: differs from generator output (edited by hand or line endings changed)")
    report.add("Files on disk match generate_sample_folder.py byte-for-byte", problems)

    return report.print_and_exit_code()


if __name__ == "__main__":
    sys.exit(main())
