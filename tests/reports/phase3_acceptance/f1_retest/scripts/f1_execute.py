"""F1 retest, part 2: pre-checks -> approve plan_scan_28419f4558ec once -> verify -> undo -> verify.

Stops (no undo, no repair) if approval, destination verification or report validation fails.
"""
import csv
import hashlib
import io
import json
import os
import sys
from datetime import datetime, timezone
from decimal import Decimal
from pathlib import Path
from urllib.error import HTTPError
from urllib.request import Request, urlopen

REPO = Path(r"C:\Users\My PC\Documents\Hackathon\GhostOS\GhostOS")
BASE = Path(r"C:\Users\My PC\AppData\Local\Temp\ghostos-phase3")
ROOT = BASE / "B-f1-retest"
CANARY = BASE / "outside-canary" / "canary.txt"
OLD = REPO / "tests" / "reports" / "phase3_acceptance"
OUT = OLD / "f1_retest"
SNAP = OUT / "snapshots"
BASE_URL = "http://127.0.0.1:8000"
SCAN_ID, PLAN_ID = "scan_28419f4558ec", "plan_scan_28419f4558ec"

old_setup = json.loads((OLD / "00_setup_manifest.json").read_text(encoding="utf-8"))
CANARY_SHA = old_setup["canary"]["sha256"]
A_FILES = {e["relative_path"]: e["sha256"] for e in old_setup["roots"]["A-blocker"]["files"]}
B_OLD_FILES = json.loads((OLD / "B_05c_tree_after_undo.json").read_text(encoding="utf-8"))["files"]
manifest = json.loads((OUT / "F1_00_setup_manifest.json").read_text(encoding="utf-8"))
ORIG = {f["relative_path"]: f["sha256"] for f in manifest["files"]}
TRUTH = {f["relative_path"]: f["expected"] for f in manifest["files"]}
REVIEWED = json.loads((OUT / "F1_02_plan_for_approval.json").read_text(encoding="utf-8"))
SOURCE_DIRS = ["archive", "archive/2026", "downloads", "inbox", "receipts"]

log, results = [], []


def sha(p: Path) -> str:
    return hashlib.sha256(p.read_bytes()).hexdigest()


def redact(obj):
    text = json.dumps(obj)
    for root, tag in ((ROOT, "<ROOT_F1>"), (BASE, "<TEST_BASE>")):
        for form in (str(root), str(root).replace("\\", "/")):
            text = text.replace(json.dumps(form)[1:-1], tag)
    return json.loads(text)


def http(method, path, body=None):
    req = Request(BASE_URL + path, data=json.dumps(body).encode() if body is not None else None, method=method,
                  headers={"Content-Type": "application/json"})
    try:
        with urlopen(req, timeout=300) as r:
            status, payload = r.status, json.loads(r.read() or b"null")
    except HTTPError as e:
        raw = e.read()
        status = e.code
        try:
            payload = json.loads(raw)
        except Exception:
            payload = raw.decode("utf-8", "replace")
    log.append(redact({"at": datetime.now(timezone.utc).isoformat(), "request": {"method": method, "path": path, "body": body},
                       "response": {"status": status, "body": payload}}))
    return status, payload


def tree(root: Path) -> dict:
    # rglob returns names exactly as stored on disk, so comparisons below are case-exact.
    return {
        "files": {p.relative_to(root).as_posix(): sha(p) for p in sorted(root.rglob("*")) if p.is_file()},
        "dirs": sorted(p.relative_to(root).as_posix() for p in root.rglob("*") if p.is_dir()),
        "empty_dirs": sorted(p.relative_to(root).as_posix() for p in root.rglob("*") if p.is_dir() and not any(p.iterdir())),
    }


def check(cid, name, ok, expected, actual):
    status = "PASS" if ok else "FAIL"
    results.append({"id": cid, "check": name, "status": status, "expected": expected, "actual": actual})
    print(f"[{status}] {cid} {name}\n        expected: {expected}\n        actual:   {actual}")
    return ok


def save():
    (OUT / "F1_05_http_log_execute.json").write_text(json.dumps(log, indent=2), encoding="utf-8")
    (OUT / "F1_09_results.json").write_text(json.dumps(results, indent=2), encoding="utf-8")


def snap(name, obj):
    (SNAP / name).write_text(json.dumps(obj, indent=2), encoding="utf-8")


def stop(msg):
    save()
    print(f"\nSTOP: {msg}")
    sys.exit(2)


for name in ("04_before_approve.json", "05_after_approve.json", "06_after_undo.json"):
    if (SNAP / name).exists():
        sys.exit(f"STOP: {name} already exists; this retest was already executed")

# ============================ PRE-CHECKS ======================================
print("=== PRE-APPROVAL CHECKS ===")
st, plan = http("GET", f"/api/scans/{SCAN_ID}/plan")
before = tree(ROOT)
snap("04_before_approve.json", before)
ok = True
ok &= check("P1", "Scan ID and plan ID match the reviewed plan", st == 200 and plan.get("plan_id") == PLAN_ID and plan.get("scan_id") == SCAN_ID,
            f"{SCAN_ID} / {PLAN_ID}", f"HTTP {st} {plan.get('scan_id')} / {plan.get('plan_id')}")
ok &= check("P2", "Plan byte-identical to the reviewed snapshot (operations, case, rows, totals)", plan == REVIEWED,
            "identical to F1_02_plan_for_approval.json", "identical" if plan == REVIEWED else "DIFFERS")
ok &= check("P3", "Five operations", len(plan.get("operations", [])) == 5, 5, len(plan.get("operations", [])))
ok &= check("P4", "Zero blocking reviews", plan.get("blocking_review_count") == 0, 0, plan.get("blocking_review_count"))
ok &= check("P5", "Original five files present with recorded SHA-256 (and nothing else)", before["files"] == ORIG,
            "matches F1_00_setup_manifest.json", "matches" if before["files"] == ORIG else before["files"])
busy = [op["destination_relative_path"] for op in plan.get("operations", []) if os.path.lexists(ROOT / op["destination_relative_path"])]
ok &= check("P6", "All destinations still free", not busy, "none exist", busy or "none exist")
ok &= check("P7", "Outside canary unchanged", sha(CANARY) == CANARY_SHA, CANARY_SHA[:16], sha(CANARY)[:16])
if not ok:
    stop("a pre-approval check differs from the reviewed plan; approval NOT requested")

# ============================ APPROVE (once) ===================================
print(f"\n=== APPROVING {PLAN_ID} on {ROOT} ===")
st, batch = http("POST", f"/api/plans/{PLAN_ID}/approve", {})
(OUT / "F1_06_approve_response.json").write_text(json.dumps(redact({"status": st, "body": batch}), indent=2), encoding="utf-8")
print(f"HTTP {st}: {json.dumps(batch)}")
after = tree(ROOT)
snap("05_after_approve.json", after)
if not check("S1", "Approval succeeds: 5 moved, 0 failed", st == 200 and batch.get("moved") == 5 and batch.get("failed") == [],
             "HTTP 200, moved=5, failed=[]", f"HTTP {st} {batch}"):
    stop("approval did not succeed as expected; undo NOT attempted")
batch_id, report_rel = batch["batch_id"], batch["report_relative_path"]

# ============================ DESTINATIONS =====================================
ops = {op["original_relative_path"]: op["destination_relative_path"] for op in plan["operations"]}
expected_files = {dst: ORIG[src] for src, dst in ops.items()}
actual_non_report = {k: v for k, v in after["files"].items() if k != report_rel}
v_ok = True
v_ok &= check("D1", "Every file is at its approved destination with EXACT case and original SHA-256",
              actual_non_report == expected_files, sorted(expected_files), sorted(actual_non_report))
case_dirs = [d for d in after["dirs"] if d.split("/")[0] in ("GhostOS Organized", "Invoices", "GhostOS Reports")]
v_ok &= check("D2", "Organized folder names on disk have the planned case",
              {"GhostOS Organized", "GhostOS Organized/Receipts", "GhostOS Organized/Receipts/2026-09", "Invoices", "Invoices/2026-09", "GhostOS Reports"} <= set(after["dirs"]),
              "GhostOS Organized/Receipts/2026-09, Invoices/2026-09, GhostOS Reports present exactly", case_dirs)
under_receipts = [k for k in after["files"] if k.lower().startswith("receipts/")] + [d for d in after["dirs"] if d.lower().startswith("receipts/")]
v_ok &= check("D3", "Nothing organized under the lowercase source 'receipts/' directory", not under_receipts,
              "receipts/ contains no files or subfolders", under_receipts or "receipts/ is empty")
in_sources = [k for k in after["files"] if any(k.lower().startswith(s + "/") for s in SOURCE_DIRS)]
v_ok &= check("D4", "No file left in or written to any source directory", not in_sources, "none", in_sources or "none")
v_ok &= check("D5", "No file overwritten (5 distinct destinations, each with its own source bytes; collision suffixed)",
              after["files"].get("Invoices/2026-09/invoice.pdf") == ORIG["archive/2026/invoice.pdf"]
              and after["files"].get("Invoices/2026-09/invoice (2).pdf") == ORIG["inbox/invoice.pdf"] and len(actual_non_report) == 5,
              "invoice.pdf=archive bytes, invoice (2).pdf=inbox bytes, 5 files", f"{len(actual_non_report)} files")
base_children = sorted(p.name for p in BASE.iterdir())
outside_ok = (base_children == ["A-blocker", "B-acceptance", "B-f1-retest", "outside-canary"]
              and tree(BASE / "A-blocker")["files"] == A_FILES
              and tree(BASE / "B-acceptance")["files"] == B_OLD_FILES and sha(CANARY) == CANARY_SHA)
v_ok &= check("D6", "Nothing written outside the selected root", outside_ok,
              "base children unchanged; A, old B and canary unchanged", f"base children {base_children}; ok={outside_ok}")
tmp = [k for k in after["files"] if k.endswith(".tmp")]
v_ok &= check("D7", "No temporary report file left", not tmp, "none", tmp or "none")
if not v_ok:
    stop("destination verification failed; undo NOT attempted (no unplanned repair)")

# ============================ CSV ==============================================
raw = (ROOT / report_rel).read_bytes()
(OUT / "F1_07_report_copy.csv").write_bytes(raw)
rows = list(csv.reader(io.StringIO(raw.decode("utf-8").lstrip("\ufeff"), newline="")))
header, data = rows[0], [r for r in rows[1:] if r]
c_ok = True
c_ok &= check("C1", "Report inside root at the returned path; BOM, CRLF and header",
              (ROOT / report_rel).is_file() and raw.startswith(b"\xef\xbb\xbf") and b"\n" not in raw.replace(b"\r\n", b"")
              and header == ["source_file", "merchant", "date", "category", "amount", "currency"],
              "GhostOS Reports/expenses-<stamp>.csv, BOM, CRLF, 6-column header", f"{report_rel}; header={header}")
expected_sources = {"archive/2026/invoice.pdf", "downloads/greenleaf-grocer-2026-09-14 (1).txt", "inbox/invoice.pdf", "receipts/sunbeam-cafe-receipt.pdf"}
c_ok &= check("C2", "Four data rows from the expected sources", len(data) == 4 and {r[0] for r in data} == expected_sources,
              sorted(expected_sources), sorted(r[0] for r in data))
errs = [r[0] for r in data if (r[2], r[3], Decimal(r[4]), r[5]) != (TRUTH[r[0]]["expected_date"], TRUTH[r[0]]["expected_category"],
                                                                     Decimal(TRUTH[r[0]]["expected_amount"]), TRUTH[r[0]]["expected_currency"])]
c_ok &= check("C3", "Row values match ground truth", not errs, "all match", errs or "all match")
totals = {}
for r in data:
    totals[r[5]] = totals.get(r[5], Decimal(0)) + Decimal(r[4])
gt = {"PHP": Decimal("3470.00") + Decimal("1286.50") + Decimal("683.20"), "USD": Decimal("59.88")}
c_ok &= check("C4", "CSV totals = independent ground truth = plan totals",
              totals == gt == {t["currency"]: Decimal(t["amount"]) for t in plan["totals"]},
              {k: str(v) for k, v in gt.items()}, {k: str(v) for k, v in totals.items()})
c_ok &= check("C5", "Duplicate copy excluded (one Greenleaf row; receipts/ copy is duplicate_of the downloads copy)",
              sum("greenleaf" in r[0] for r in data) == 1 and "receipts/greenleaf-grocer-2026-09-14.txt" not in {r[0] for r in data},
              "only downloads/greenleaf-grocer-2026-09-14 (1).txt", [r[0] for r in data if "greenleaf" in r[0]])
if not c_ok:
    stop("report validation failed; undo NOT attempted (no unplanned repair)")

# ============================ UNDO =============================================
print(f"\n=== UNDO {batch_id} ===")
st, undo = http("POST", f"/api/batches/{batch_id}/undo", {})
(OUT / "F1_08_undo_response.json").write_text(json.dumps(redact({"status": st, "body": undo}), indent=2), encoding="utf-8")
print(f"HTTP {st}: {json.dumps(undo)}")
restored = tree(ROOT)
snap("06_after_undo.json", restored)
check("U1", "Undo succeeds with no conflicts", st == 200 and undo.get("restored") == 5 and undo.get("conflicts") == [],
      "HTTP 200, restored=5, conflicts=[]", f"HTTP {st}, restored={undo.get('restored')}, conflicts={undo.get('conflicts')}")
back = {k: restored["files"].get(k) for k in ORIG}
check("U2", "All five original paths (exact case) restored with original SHA-256", back == ORIG,
      "5/5 identical", "5/5 identical" if back == ORIG else back)
organized_left = [k for k in restored["files"] if k != report_rel and k not in ORIG]
check("U3", "No organized files remain anywhere (incl. inside source folders)", not organized_left, "none", organized_left or "none")
check("U4", "Source folders contain only their original files",
      all(k in ORIG for k in restored["files"] if any(k.startswith(s + "/") for s in SOURCE_DIRS)),
      "only originals", sorted(k for k in restored["files"] if any(k.startswith(s + "/") for s in SOURCE_DIRS)))
check("U5", "(observed) Report CSV remaining after undo", True, "record actual", [k for k in restored["files"] if k.startswith("GhostOS Reports/")])
check("U6", "(observed) Empty generated folders remaining after undo", True, "record actual", restored["empty_dirs"])
check("U7", "Outside root still unchanged after undo",
      sorted(p.name for p in BASE.iterdir()) == ["A-blocker", "B-acceptance", "B-f1-retest", "outside-canary"]
      and tree(BASE / "A-blocker")["files"] == A_FILES and tree(BASE / "B-acceptance")["files"] == B_OLD_FILES and sha(CANARY) == CANARY_SHA,
      "unchanged", "unchanged")
save()
print(f"\nbatch_id: {batch_id}\nsaved to: {OUT}")
