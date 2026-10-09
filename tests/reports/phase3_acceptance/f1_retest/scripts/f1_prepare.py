"""F1 retest, part 1 (READ-ONLY after setup): create fresh root, copy 5 files, scan, preview, pre-approval checks.

Contains NO approve or undo call. Refuses to run if the new root or evidence folder already exists.
"""
import hashlib
import json
import os
import shutil
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from urllib.error import HTTPError
from urllib.request import Request, urlopen

REPO = Path(r"C:\Users\My PC\Documents\Hackathon\GhostOS\GhostOS")
FIXTURES = REPO / "tests" / "fixtures" / "sample_folder"
BASE = Path(r"C:\Users\My PC\AppData\Local\Temp\ghostos-phase3")
ROOT = BASE / "B-f1-retest"
CANARY = BASE / "outside-canary" / "canary.txt"
OLD = REPO / "tests" / "reports" / "phase3_acceptance"
OUT = OLD / "f1_retest"
BASE_URL = "http://127.0.0.1:8000"

old_setup = json.loads((OLD / "00_setup_manifest.json").read_text(encoding="utf-8"))
OLD_B = old_setup["roots"]["B-acceptance"]["files"]           # same five files, same layout
CANARY_SHA = old_setup["canary"]["sha256"]

# Independently expected plan, derived from the fix's documented rule (not from the backend's output):
# Invoices/2026-09 does not collide with any source directory; Receipts/2026-09 collides with the
# lowercase source directory "receipts" on Windows, so it must move under "GhostOS Organized/".
EXPECTED_OPS = {
    "archive/2026/invoice.pdf": "Invoices/2026-09/invoice.pdf",
    "inbox/invoice.pdf": "Invoices/2026-09/invoice (2).pdf",
    "downloads/greenleaf-grocer-2026-09-14 (1).txt": "GhostOS Organized/Receipts/2026-09/greenleaf-grocer-2026-09-14 (1).txt",
    "receipts/greenleaf-grocer-2026-09-14.txt": "GhostOS Organized/Receipts/2026-09/greenleaf-grocer-2026-09-14.txt",
    "receipts/sunbeam-cafe-receipt.pdf": "GhostOS Organized/Receipts/2026-09/sunbeam-cafe-receipt.pdf",
}
SOURCE_DIRS = ["archive", "archive/2026", "downloads", "inbox", "receipts"]

log, checks = [], []


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
        status, payload = e.code, e.read().decode("utf-8", "replace")
    log.append(redact({"at": datetime.now(timezone.utc).isoformat(), "request": {"method": method, "path": path, "body": body},
                       "response": {"status": status, "body": payload}}))
    return status, payload


def tree(root: Path) -> dict:
    return {"files": {p.relative_to(root).as_posix(): sha(p) for p in sorted(root.rglob("*")) if p.is_file()},
            "dirs": sorted(p.relative_to(root).as_posix() for p in root.rglob("*") if p.is_dir())}


def check(cid, name, ok, expected, actual):
    checks.append({"id": cid, "check": name, "status": "PASS" if ok else "FAIL", "expected": expected, "actual": actual})
    print(f"[{'PASS' if ok else 'FAIL'}] {cid} {name}\n        expected: {expected}\n        actual:   {actual}")
    return ok


def write(name, obj):
    (OUT / name).write_text(json.dumps(redact(obj), indent=2), encoding="utf-8")


# ---------------- setup (refuses to reuse anything) ----------------
for p in (ROOT, OUT):
    if p.exists():
        sys.exit(f"STOP: {p} already exists; refusing to reuse or overwrite it")
if sha(CANARY) != CANARY_SHA:
    sys.exit("STOP: outside canary changed since the original acceptance run")
ROOT.mkdir()
(OUT / "snapshots").mkdir(parents=True)

manifest = {"created_at": datetime.now(timezone.utc).isoformat(), "root": "<ROOT_F1>", "files": []}
for e in OLD_B:
    rel = e["relative_path"]
    src, dst = FIXTURES / rel, ROOT / rel
    dst.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(src, dst)
    h = sha(dst)
    if h != e["sha256"] or h != sha(src):
        sys.exit(f"STOP: copied hash for {rel} differs from the original acceptance manifest")
    manifest["files"].append({"relative_path": rel, "size_bytes": dst.stat().st_size, "sha256": h, "expected": e["expected"]})
write("F1_00_setup_manifest.json", manifest)

print(f"new root: {ROOT}")
for f in manifest["files"]:
    print(f"  {f['relative_path']:46} {f['size_bytes']:>5} B  {f['sha256']}")
receipts_entries = [p.name for p in ROOT.iterdir() if p.is_dir() and p.name.lower() == "receipts"]
check("R0", "Root contains the lowercase source directory 'receipts/' that triggered F1",
      receipts_entries == ["receipts"], "['receipts']", receipts_entries)

before = tree(ROOT)
(OUT / "snapshots" / "01_before_scan.json").write_text(json.dumps(before, indent=2), encoding="utf-8")

# ---------------- scan + preview (read-only) ----------------
st, prog = http("POST", "/api/scan", {"root": str(ROOT)})
if st != 200:
    sys.exit(f"STOP: scan request failed HTTP {st} {prog}")
scan_id = prog["scan_id"]
while prog["state"] == "running":
    time.sleep(1)
    st, prog = http("GET", f"/api/scans/{scan_id}/progress")
st, scan = http("GET", f"/api/scans/{scan_id}")
after_scan = tree(ROOT)
st, plan = http("GET", f"/api/scans/{scan_id}/plan")
after_preview = tree(ROOT)
write("F1_01_scan_result.json", scan)
write("F1_02_plan_for_approval.json", plan)
(OUT / "snapshots" / "02_after_scan.json").write_text(json.dumps(after_scan, indent=2), encoding="utf-8")
(OUT / "snapshots" / "03_after_preview.json").write_text(json.dumps(after_preview, indent=2), encoding="utf-8")

print(f"\nscan_id: {scan_id}\nplan_id: {plan['plan_id']}\n")
truth = {f["relative_path"]: f["expected"] for f in manifest["files"]}
for d in scan["documents"]:
    c = d.get("classification") or {}
    print(f"  {d['relative_path']:46} {d['status']:12} {c.get('category')} {c.get('date')} {c.get('amount')} {c.get('currency')} "
          f"flags={[f['code'] for f in d['review_flags']]} dup_of={d.get('duplicate_of')}")
print()

# ---------------- pre-approval checks ----------------
check("R1", "Scan does not modify the root", after_scan == before, "identical tree", "identical" if after_scan == before else "CHANGED")
check("R2", "Preview does not modify the root", after_preview == before, "identical tree", "identical" if after_preview == before else "CHANGED")
check("R3", "Plan ID belongs to this scan", plan.get("plan_id") == f"plan_{scan_id}", f"plan_{scan_id}", plan.get("plan_id"))
check("R4", "Zero blocking reviews (no correction needed)", plan.get("blocking_review_count") == 0, 0, plan.get("blocking_review_count"))
all_ok = all(d["status"] == "ok" for d in scan["documents"])
check("R5", "All five classified without review flags", all_ok and len(scan["documents"]) == 5,
      "5 documents, all status ok", f"{len(scan['documents'])} documents; statuses {[d['status'] for d in scan['documents']]}")
cls_ok = all((d.get("classification") or {}).get("category") == truth[d["relative_path"]]["expected_category"]
             and (d.get("classification") or {}).get("date") == truth[d["relative_path"]]["expected_date"]
             for d in scan["documents"])
check("R6", "Categories and dates match ground truth", cls_ok, "5/5", "5/5" if cls_ok else "MISMATCH")
actual_ops = {op["original_relative_path"]: op["destination_relative_path"] for op in plan.get("operations", [])}
check("R7", "Exactly five operations", len(actual_ops) == 5, 5, len(actual_ops))
check("R8", "Planned destinations equal the independently expected destinations", actual_ops == EXPECTED_OPS,
      EXPECTED_OPS, actual_ops)
receipt_dests = [d for s, d in actual_ops.items() if "greenleaf" in s or "sunbeam" in s]
check("R9", "Receipts routed to the distinct 'GhostOS Organized/Receipts/YYYY-MM/' location",
      bool(receipt_dests) and all(d.startswith("GhostOS Organized/Receipts/2026-09/") for d in receipt_dests),
      "all 3 receipts under GhostOS Organized/Receipts/2026-09/", receipt_dests)
inside_source = [d for d in actual_ops.values()
                 if any(d.lower() == s.lower() or d.lower().startswith(s.lower() + "/") for s in SOURCE_DIRS)]
check("R10", "No destination inside any scanned source directory (case-insensitive)", not inside_source,
      f"none inside {SOURCE_DIRS}", inside_source or "none")
bad = []
for d in actual_ops.values():
    rel = Path(d)
    if rel.is_absolute() or ".." in rel.parts or ROOT.resolve() not in (ROOT / rel).resolve().parents:
        bad.append(f"{d}: outside root")
    if os.path.lexists(ROOT / rel):
        bad.append(f"{d}: already exists")
check("R11", "All destinations relative, inside the root, and currently free", not bad, "no problems", bad or "none")
check("R12", "Destinations unique (case-insensitive)", len({d.lower() for d in actual_ops.values()}) == len(actual_ops),
      "5 unique", len({d.lower() for d in actual_ops.values()}))
check("R13", "Outside canary unchanged", sha(CANARY) == CANARY_SHA, CANARY_SHA[:16], sha(CANARY)[:16])
totals = {t["currency"]: t["amount"] for t in plan.get("totals", [])}
check("R14", "Plan totals equal independent ground truth (PHP 5439.70, USD 59.88)",
      totals == {"PHP": "5439.70", "USD": "59.88"}, {"PHP": "5439.70", "USD": "59.88"}, totals)

(OUT / "F1_03_http_log_prepare.json").write_text(json.dumps(log, indent=2), encoding="utf-8")
(OUT / "F1_04_preapproval_checks.json").write_text(json.dumps(checks, indent=2), encoding="utf-8")
failed = [c for c in checks if c["status"] != "PASS"]
print(f"\nPRE-APPROVAL: {len(checks) - len(failed)}/{len(checks)} passed. NO approval was requested.")
sys.exit(1 if failed else 0)
