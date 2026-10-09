"""Phase 3 acceptance, Stage 4 (part 2): pre-checks -> approve plan_scan_bf77c62ddde8 -> verify -> undo -> verify.

Operates on root B only. Exits WITHOUT approving if any pre-check differs from the approved snapshot.
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

BASE_URL = "http://127.0.0.1:8000"
BASE = Path(r"C:\Users\My PC\AppData\Local\Temp\ghostos-phase3")
ROOT = BASE / "B-acceptance"
ROOT_A = BASE / "A-blocker"
CANARY = BASE / "outside-canary" / "canary.txt"
OUT = Path(r"C:\Users\My PC\Documents\Hackathon\GhostOS\GhostOS\tests\reports\phase3_acceptance")
PLAN_ID = "plan_scan_bf77c62ddde8"
SCAN_ID = "scan_bf77c62ddde8"

setup = json.loads((OUT / "00_setup_manifest.json").read_text(encoding="utf-8"))
MANIFEST = {e["relative_path"]: e for e in setup["roots"]["B-acceptance"]["files"]}
CANARY_SHA = setup["canary"]["sha256"]
APPROVED = json.loads((OUT / "B_03_plan_snapshot_for_approval.json").read_text(encoding="utf-8"))
A_FILES = {e["relative_path"]: e["sha256"] for e in setup["roots"]["A-blocker"]["files"]}

log, results = [], []


def redact(obj):
    text = json.dumps(obj)
    for root, tag in ((ROOT, "<ROOT_B>"), (BASE, "<TEST_BASE>")):
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


def sha(p: Path) -> str:
    return hashlib.sha256(p.read_bytes()).hexdigest()


def tree(root: Path) -> dict:
    return {
        "files": {p.relative_to(root).as_posix(): sha(p) for p in sorted(root.rglob("*")) if p.is_file()},
        "dirs": sorted(p.relative_to(root).as_posix() for p in root.rglob("*") if p.is_dir()),
        "empty_dirs": sorted(p.relative_to(root).as_posix() for p in root.rglob("*") if p.is_dir() and not any(p.iterdir())),
    }


def check(test, ok, expected, actual):
    status = "PASS" if ok else "FAIL"
    results.append({"test": test, "status": status, "expected": expected, "actual": actual})
    print(f"[{status}] {test}\n        expected: {expected}\n        actual:   {actual}")
    return ok


def save_all(extra=None):
    (OUT / "B_04_http_log_execute.json").write_text(json.dumps(log, indent=2), encoding="utf-8")
    (OUT / "B_09_results.json").write_text(json.dumps(results, indent=2), encoding="utf-8")
    if extra:
        for name, obj in extra.items():
            (OUT / name).write_text(json.dumps(redact(obj), indent=2), encoding="utf-8")


def stop(reason, snapshots):
    print(f"\nSTOP before approval: {reason}")
    save_all(snapshots)
    sys.exit(2)


# ============================ PRE-CHECKS ======================================
print("=== PRE-APPROVAL CHECKS ===")
st, plan = http("GET", f"/api/scans/{SCAN_ID}/plan")
before = tree(ROOT)
snaps = {"B_05_tree_before_approve.json": before}
pre_ok = True
pre_ok &= check("P1 Plan ID unchanged", st == 200 and plan.get("plan_id") == PLAN_ID, PLAN_ID, f"HTTP {st} {plan.get('plan_id') if isinstance(plan, dict) else plan}")
pre_ok &= check("P2 Plan identical to the approved snapshot (operations, rows, totals)", plan == APPROVED,
                "byte-identical JSON to B_03_plan_snapshot_for_approval.json", "identical" if plan == APPROVED else "DIFFERS")
pre_ok &= check("P3 Exactly five operations", len(plan.get("operations", [])) == 5, 5, len(plan.get("operations", [])))
pre_ok &= check("P4 Zero blocking reviews", plan.get("blocking_review_count") == 0, 0, plan.get("blocking_review_count"))
src_ok = before["files"] == {k: v["sha256"] for k, v in MANIFEST.items()}
pre_ok &= check("P5 Five originals present with recorded SHA-256", src_ok, "matches 00_setup_manifest.json",
                "matches" if src_ok else before["files"])
dest_problems = []
for op in plan.get("operations", []):
    rel = Path(op["destination_relative_path"])
    if rel.is_absolute() or ".." in rel.parts:
        dest_problems.append(f"{rel}: absolute or traversal")
        continue
    target = (ROOT / rel).resolve(strict=False)
    if ROOT.resolve() not in target.parents:
        dest_problems.append(f"{rel}: resolves outside root B")
    if os.path.lexists(ROOT / rel):
        dest_problems.append(f"{rel}: already exists")
pre_ok &= check("P6 Every destination is inside root B and still free", not dest_problems, "no problems", dest_problems or "none")
pre_ok &= check("P7 Outside canary unchanged", sha(CANARY) == CANARY_SHA, CANARY_SHA[:16], sha(CANARY)[:16])
if not pre_ok:
    stop("a pre-check differs from the approved snapshot", snaps)

# ============================ APPROVE ==========================================
print(f"\n=== APPROVING {PLAN_ID} on {ROOT} ===")
st, batch = http("POST", f"/api/plans/{PLAN_ID}/approve", {})
(OUT / "B_06_approve_response.json").write_text(json.dumps(redact({"status": st, "body": batch}), indent=2), encoding="utf-8")
print(f"HTTP {st}: {json.dumps(batch)}")
if st != 200:
    check("S1 Approval succeeds", False, "HTTP 200 with batch_id", f"HTTP {st} {batch}")
    save_all({**snaps, "B_05b_tree_after_approve.json": tree(ROOT)})
    sys.exit("STOP: approval did not return 200; undo NOT attempted automatically. Inspect B_06_approve_response.json.")
batch_id = batch["batch_id"]
after = tree(ROOT)
snaps["B_05b_tree_after_approve.json"] = after
check("S1 Approval succeeds", True, "HTTP 200 with batch_id", f"HTTP 200 batch_id={batch_id} moved={batch['moved']} failed={batch['failed']}")
check("S2 All five files committed, none failed", batch["moved"] == 5 and batch["failed"] == [], "moved=5, failed=[]",
      f"moved={batch['moved']}, failed={batch['failed']}")

# destinations: each destination holds exactly the original bytes, originals gone
mismatch = []
for op in plan["operations"]:
    src, dst = op["original_relative_path"], op["destination_relative_path"]
    if src in after["files"]:
        mismatch.append(f"{src} still present")
    if after["files"].get(dst) != MANIFEST[src]["sha256"]:
        mismatch.append(f"{dst} hash {after['files'].get(dst, 'MISSING')[:12]} != {MANIFEST[src]['sha256'][:12]}")
check("S3 Each file is at its planned destination with unchanged SHA-256", not mismatch, "5/5 match", mismatch or "5/5 match")
inv1 = after["files"].get("Invoices/2026-09/invoice.pdf")
inv2 = after["files"].get("Invoices/2026-09/invoice (2).pdf")
check("S4 Collision: both invoice.pdf files kept under distinct names, nothing overwritten",
      inv1 == MANIFEST["archive/2026/invoice.pdf"]["sha256"] and inv2 == MANIFEST["inbox/invoice.pdf"]["sha256"],
      "invoice.pdf = archive/2026 bytes; invoice (2).pdf = inbox bytes",
      f"invoice.pdf={str(inv1)[:12]}, invoice (2).pdf={str(inv2)[:12]}")
dup_ok = (after["files"].get("Receipts/2026-09/greenleaf-grocer-2026-09-14.txt") == MANIFEST["receipts/greenleaf-grocer-2026-09-14.txt"]["sha256"]
          and after["files"].get("Receipts/2026-09/greenleaf-grocer-2026-09-14 (1).txt") == MANIFEST["downloads/greenleaf-grocer-2026-09-14 (1).txt"]["sha256"])
check("S5 Duplicate pair: both copies moved, neither deleted", dup_ok, "both Greenleaf copies present in Receipts/2026-09/", "both present" if dup_ok else "MISSING")

report_rel = batch["report_relative_path"]
planned_dests = {op["destination_relative_path"] for op in plan["operations"]}
extra = sorted(set(after["files"]) - planned_dests - {report_rel})
check("S6 No unexpected files in root B (only planned moves + the report)", not extra, "none", extra or "none")
tmp_left = [f for f in after["files"] if f.endswith(".tmp")]
check("S7 No temporary report file left behind", not tmp_left, "none", tmp_left or "none")
base_children = sorted(p.name for p in BASE.iterdir())
check("S8 Nothing created outside root B; root A and canary unchanged",
      base_children == ["A-blocker", "B-acceptance", "outside-canary"] and tree(ROOT_A)["files"] == A_FILES and sha(CANARY) == CANARY_SHA,
      "base children [A-blocker, B-acceptance, outside-canary]; A and canary hashes unchanged",
      f"base children {base_children}; A {'unchanged' if tree(ROOT_A)['files'] == A_FILES else 'CHANGED'}; canary {'unchanged' if sha(CANARY) == CANARY_SHA else 'CHANGED'}")

# ============================ CSV ==============================================
report_path = ROOT / report_rel
raw = report_path.read_bytes()
(OUT / "B_07_report_copy.csv").write_bytes(raw)  # byte copy for the record (synthetic data)
text = raw.decode("utf-8")
rows = list(csv.reader(io.StringIO(text.lstrip("\ufeff"), newline="")))
header, data = rows[0], [r for r in rows[1:] if r]
check("S9 Report written inside root B at the returned path", report_path.is_file() and ROOT.resolve() in report_path.resolve().parents,
      "GhostOS Reports/expenses-<stamp>.csv inside root B", report_rel)
check("S10 CSV format: UTF-8 BOM, CRLF, expected header", raw.startswith(b"\xef\xbb\xbf") and b"\r\n" in raw and b"\n" not in raw.replace(b"\r\n", b"")
      and header == ["source_file", "merchant", "date", "category", "amount", "currency"],
      "BOM + CRLF + source_file,merchant,date,category,amount,currency", f"BOM={raw.startswith(b'\xef\xbb\xbf')} header={header}")

# independent expectation from the ground truth + the repository's report rule
truth = {k: v["expected"] for k, v in MANIFEST.items()}
expected_sources = {"archive/2026/invoice.pdf", "downloads/greenleaf-grocer-2026-09-14 (1).txt",
                    "inbox/invoice.pdf", "receipts/sunbeam-cafe-receipt.pdf"}
got_sources = {r[0] for r in data}
check("S11 CSV rows = committed, accepted rows only (4)", len(data) == 4 and got_sources == expected_sources,
      f"4 rows: {sorted(expected_sources)}", f"{len(data)} rows: {sorted(got_sources)}")
value_errors = []
for r in data:
    t = truth.get(r[0])
    if not t:
        value_errors.append(f"{r[0]}: not a selected file")
        continue
    if (r[2], r[3], Decimal(r[4]), r[5]) != (t["expected_date"], t["expected_category"], Decimal(t["expected_amount"]), t["expected_currency"]):
        value_errors.append(f"{r[0]}: got {r[2:]} expected {[t['expected_date'], t['expected_category'], t['expected_amount'], t['expected_currency']]}")
check("S12 Each CSV row's date, category, amount and currency match the ground truth", not value_errors, "all match", value_errors or "all match")
csv_totals = {}
for r in data:
    csv_totals[r[5]] = csv_totals.get(r[5], Decimal(0)) + Decimal(r[4])
gt_totals = {"PHP": Decimal("3470.00") + Decimal("1286.50") + Decimal("683.20"), "USD": Decimal("59.88")}
plan_totals = {t["currency"]: Decimal(t["amount"]) for t in plan["totals"]}
check("S13 CSV totals equal independent ground-truth totals and plan totals",
      csv_totals == gt_totals == plan_totals,
      {k: str(v) for k, v in gt_totals.items()},
      {"csv": {k: str(v) for k, v in csv_totals.items()}, "plan": {k: str(v) for k, v in plan_totals.items()}})
check("S14 Duplicate copy excluded from CSV (single Greenleaf row)",
      "receipts/greenleaf-grocer-2026-09-14.txt" not in got_sources and sum("greenleaf" in s for s in got_sources) == 1,
      "receipts/greenleaf-grocer-2026-09-14.txt absent (duplicate_of downloads copy); exactly one Greenleaf row",
      f"greenleaf rows: {[s for s in got_sources if 'greenleaf' in s]}")

# ============================ UNDO =============================================
print(f"\n=== UNDO {batch_id} ===")
st, undo = http("POST", f"/api/batches/{batch_id}/undo", {})
(OUT / "B_08_undo_response.json").write_text(json.dumps(redact({"status": st, "body": undo}), indent=2), encoding="utf-8")
print(f"HTTP {st}: {json.dumps(undo)}")
restored = tree(ROOT)
snaps["B_05c_tree_after_undo.json"] = restored
check("U1 Undo succeeds with no conflicts", st == 200 and undo.get("restored") == 5 and undo.get("conflicts") == [],
      "HTTP 200, restored=5, conflicts=[]", f"HTTP {st}, restored={undo.get('restored')}, conflicts={undo.get('conflicts')}")
orig = {k: v["sha256"] for k, v in MANIFEST.items()}
restored_originals = {k: restored["files"].get(k) for k in orig}
check("U2 All five original relative paths restored with original SHA-256", restored_originals == orig,
      "5/5 identical", "5/5 identical" if restored_originals == orig else {k: (v or "MISSING")[:12] for k, v in restored_originals.items()})
leftover_files = sorted(set(restored["files"]) - set(orig))
check("U3 (observed) Files remaining after undo", True, "record actual", leftover_files)
check("U4 (observed) Empty directories remaining after undo", True, "record actual", restored["empty_dirs"])
check("U5 Root A and outside canary unchanged after undo",
      tree(ROOT_A)["files"] == A_FILES and sha(CANARY) == CANARY_SHA, "unchanged",
      "unchanged" if tree(ROOT_A)["files"] == A_FILES and sha(CANARY) == CANARY_SHA else "CHANGED")

save_all(snaps)
print(f"\nbatch_id: {batch_id}\nsaved to: {OUT}")
