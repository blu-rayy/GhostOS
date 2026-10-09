"""DA-5 retest - Stage 5: approve plan_scan_8394fbe2c049 (partial) on DA5-R2 via the MOCK backend, verify, undo, verify.

Stops without undo (no unplanned repair) if approval, move or report verification fails.

    backend\\.venv\\Scripts\\python.exe -B tests\\reports\\document_aware_review\\da5_retest_3c60bb3\\scripts\\da5_stage5_approve_undo.py
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

REPO = Path(__file__).resolve().parents[5]
OUT = REPO / "tests" / "reports" / "document_aware_review" / "da5_retest_3c60bb3"
EV = OUT / "stage5_execute"
BASE = Path.home() / "AppData" / "Local" / "Temp" / "ghostos-docaware"
ROOT = BASE / "DA5-R2"
CANARY = BASE / "DA5-canary" / "canary.txt"
MOCK = "http://127.0.0.1:8001"
SCAN_ID, PLAN_ID = "scan_8394fbe2c049", "plan_scan_8394fbe2c049"
STATEMENT = "r2/misc/bank-statement-oct2026.txt"
SOURCE_DIRS = ["r2", "r2/misc", "r2/receipts"]

MANIFEST = json.loads((OUT / "setup" / "manifest.json").read_text(encoding="utf-8"))
ORIG = {k: v["sha256"] for k, v in MANIFEST["roots"]["DA5-R2"]["snapshot"]["files"].items()}
REVIEWED = json.loads((OUT / "r2_preview_v2" / "R2_plan_partial_for_review.json").read_text(encoding="utf-8"))
OTHER_ROOTS = {name: MANIFEST["roots"][name]["snapshot"]["files"] for name in ("DA5-R1",)}
log, results = [], []


def sha(p): return hashlib.sha256(p.read_bytes()).hexdigest()


def snap(root):
    return {"files": {p.relative_to(root).as_posix(): {"sha256": sha(p), "size": p.stat().st_size} for p in sorted(root.rglob("*")) if p.is_file()},
            "dirs": sorted(p.relative_to(root).as_posix() for p in root.rglob("*") if p.is_dir()),
            "empty_dirs": sorted(p.relative_to(root).as_posix() for p in root.rglob("*") if p.is_dir() and not any(p.iterdir()))}


def hashes(s): return {k: v["sha256"] for k, v in s["files"].items()}


def redact(o):
    t = json.dumps(o, default=str)
    for f in (str(BASE), str(BASE).replace("\\", "/")):
        t = t.replace(json.dumps(f)[1:-1], "<TEST_BASE>")
    return json.loads(t)


def http(method, path, body=None):
    req = Request(MOCK + path, data=json.dumps(body).encode() if body is not None else None, method=method, headers={"Content-Type": "application/json"})
    try:
        with urlopen(req, timeout=120) as r:
            st, pl = r.status, json.loads(r.read() or b"null")
    except HTTPError as e:
        raw = e.read(); st = e.code
        try:
            pl = json.loads(raw)
        except Exception:
            pl = raw.decode("utf-8", "replace")
    log.append(redact({"at": datetime.now(timezone.utc).isoformat(), "request": {"method": method, "path": path, "body": body}, "response": {"status": st, "body": pl}}))
    return st, pl


def check(cid, name, ok, expected, actual):
    st = "PASS" if ok else "FAIL"
    results.append({"id": cid, "check": name, "status": st, "expected": expected, "actual": actual})
    print(f"[{st}] {cid} {name}\n        expected: {expected}\n        actual:   {actual}")
    return ok


def save(name, obj): (EV / name).write_text(json.dumps(redact(obj), indent=2), encoding="utf-8")


def finish():
    save("http_log.json", log)
    (EV / "results.json").write_text(json.dumps(results, indent=2), encoding="utf-8")


def stop(msg):
    finish()
    sys.exit(f"STOP: {msg}")


def outside_ok():
    children = sorted(p.name for p in BASE.iterdir())
    others = all(hashes(snap(BASE / n)) == {k: v["sha256"] for k, v in f.items()} for n, f in OTHER_ROOTS.items())
    return sha(CANARY) == MANIFEST["canary_sha256"] and others, children


if EV.exists():
    sys.exit(f"STOP: {EV} exists")
EV.mkdir()

# ============================ PRE-CHECKS ======================================
print("=== PRE-APPROVAL CHECKS (MOCK backend :8001) ===")
st, plan = http("GET", f"/api/scans/{SCAN_ID}/plan?mode=partial")
_, scan = http("GET", f"/api/scans/{SCAN_ID}")
before = snap(ROOT)
save("snapshot_before_approve.json", before)
ok = True
ok &= check("Q1", "Scan ID, plan ID and mode unchanged", st == 200 and plan.get("scan_id") == SCAN_ID and plan.get("plan_id") == PLAN_ID and plan.get("mode") == "partial",
            f"{SCAN_ID} / {PLAN_ID} / partial", f"HTTP {st} {plan.get('scan_id')} / {plan.get('plan_id')} / {plan.get('mode')}")
ok &= check("Q2", "Plan byte-identical to the reviewed preview (3 operations, exact paths, rows, totals)", plan == REVIEWED,
            "identical to r2_preview_v2/R2_plan_partial_for_review.json", "identical" if plan == REVIEWED else "DIFFERS")
ops = {o["original_relative_path"]: o["destination_relative_path"] for o in plan.get("operations", [])}
stmt = next((d for d in scan.get("documents", []) if d["relative_path"] == STATEMENT), {})
sc = stmt.get("classification") or {}
ok &= check("Q3", "Explicit-null statement still unresolved and routed to Uncategorized/",
            stmt.get("status") == "needs_review" and not stmt.get("user_corrected") and "document_kind" in sc and sc.get("document_kind") is None
            and sc.get("field_profile") == "none" and ops.get(STATEMENT) == "Uncategorized/bank-statement-oct2026.txt",
            "needs_review, not corrected, kind null, profile none, Uncategorized/bank-statement-oct2026.txt",
            f"{stmt.get('status')}, corrected {stmt.get('user_corrected')}, kind {sc.get('document_kind')!r}, profile {sc.get('field_profile')}, {ops.get(STATEMENT)}")
rows = sorted((r["source_filename"], r["status"], r["amount"], r["currency"]) for r in plan.get("report_rows", []))
ok &= check("Q4", "Both receipt rows accepted; no statement row", rows == [("r2/receipts/sunbeam-cafe-receipt.pdf", "accepted", "683.20", "PHP"),
                                                                         ("r2/receipts/tibay-hardware-receipt.csv", "accepted", "2145.00", "PHP")],
            "Sunbeam 683.20, Tibay 2145.00", rows)
ok &= check("Q5", "Original three files with recorded SHA-256 (and nothing else)", hashes(before) == ORIG, "matches manifest",
            "matches" if hashes(before) == ORIG else hashes(before))
probs = []
for d in ops.values():
    rel = Path(d)
    if rel.is_absolute() or ".." in rel.parts or ROOT.resolve() not in (ROOT / rel).resolve().parents:
        probs.append(f"{d}: outside root")
    if os.path.lexists(ROOT / rel):
        probs.append(f"{d}: exists")
ok &= check("Q6", "Destinations inside root, free and unique", not probs and len({d.lower() for d in ops.values()}) == 3, "no problems, 3 unique", probs or "ok")
oo, children = outside_ok()
ok &= check("Q7", "Outside-root canary and other roots unchanged", oo, "unchanged", f"base children {children}")
if not ok:
    stop("a pre-check differs; approval NOT requested")

# ============================ APPROVE ===========================================
print(f"\n=== APPROVING {PLAN_ID} (partial) on {ROOT} via MOCK backend ===")
st, batch = http("POST", f"/api/plans/{PLAN_ID}/approve", {"mode": "partial"})
save("approve_response.json", {"status": st, "body": batch})
print(f"HTTP {st}: {json.dumps(batch)}")
after = snap(ROOT)
save("snapshot_after_approve.json", after)
if not check("S1", "Approval: 3 moved, 0 failed", st == 200 and batch.get("moved") == 3 and batch.get("failed") == [], "HTTP 200, moved=3, failed=[]", f"HTTP {st} {batch}"):
    stop("approval did not succeed as expected; undo NOT attempted")
batch_id, report_rel = batch["batch_id"], batch["report_relative_path"]
exp = {dst: ORIG[src] for src, dst in ops.items()}
actual = {k: v for k, v in hashes(after).items() if k != report_rel}
v = True
v &= check("M1", "Exact-case destinations with original SHA-256", actual == exp, sorted(exp), sorted(actual))
v &= check("M2", "No overwrite (3 files, each with its own bytes)", len(actual) == 3 and sorted(actual.values()) == sorted(ORIG.values()), "3 files", f"{len(actual)} files")
v &= check("M3", "No organized file inside a source folder", not [k for k in after["files"] if any(k.startswith(s + "/") for s in SOURCE_DIRS)], "none",
           [k for k in after["files"] if any(k.startswith(s + "/") for s in SOURCE_DIRS)] or "none")
v &= check("M4", "No temporary report file", not [k for k in after["files"] if k.endswith(".tmp")], "none", "none")
oo, children = outside_ok()
v &= check("M5", "No out-of-root changes", oo, "unchanged", f"base children {children}")
if not v:
    stop("move verification failed; undo NOT attempted")

raw = (ROOT / report_rel).read_bytes()
(EV / "report_copy.csv").write_bytes(raw)
data = [r for r in list(csv.reader(io.StringIO(raw.decode("utf-8").lstrip("﻿"), newline="")))[1:] if r]
c = True
got = sorted((r[0], r[4], r[5]) for r in data)
c &= check("R1", "CSV rows: exactly the two receipts", got == [("r2/receipts/sunbeam-cafe-receipt.pdf", "683.20", "PHP"), ("r2/receipts/tibay-hardware-receipt.csv", "2145.00", "PHP")],
           "Sunbeam 683.20 PHP, Tibay 2145.00 PHP", got)
c &= check("R2", "Explicit-null statement not in the CSV", not [r for r in data if "bank-statement" in r[0]], "absent",
           [r[0] for r in data if "bank-statement" in r[0]] or "absent")
tot = {}
for r in data:
    tot[r[5]] = tot.get(r[5], Decimal(0)) + Decimal(r[4])
c &= check("R3", "Total recomputed from the CSV = PHP 2828.20 (683.20 + 2145.00)", tot == {"PHP": Decimal("2828.20")}, "PHP 2828.20",
           {k: str(x) for k, x in tot.items()})
if not c:
    stop("report verification failed; undo NOT attempted")

# ============================ UNDO ==============================================
print(f"\n=== UNDO {batch_id} ===")
st, undo = http("POST", f"/api/batches/{batch_id}/undo", {})
save("undo_response.json", {"status": st, "body": undo})
print(f"HTTP {st}: {json.dumps(undo)}")
restored = snap(ROOT)
save("snapshot_after_undo.json", restored)
check("U1", "Undo: 3 restored, 0 conflicts", st == 200 and undo.get("restored") == 3 and undo.get("conflicts") == [], "HTTP 200, restored=3, conflicts=[]",
      f"HTTP {st}, restored={undo.get('restored')}, conflicts={undo.get('conflicts')}")
back = {k: restored["files"].get(k, {}).get("sha256") for k in ORIG}
check("U2", "All three original paths and SHA-256 restored", back == ORIG, "3/3 identical", "3/3 identical" if back == ORIG else back)
left = sorted(set(restored["files"]) - set(ORIG))
check("U3", "No organized files remain (only the report may remain)", all(f.startswith("GhostOS Reports/") for f in left), "only GhostOS Reports/*", left or "none")
results.append({"id": "U4", "check": "(observed) report files remaining after undo", "status": "RECORDED", "actual": left})
results.append({"id": "U5", "check": "(observed) empty folders remaining after undo", "status": "RECORDED", "actual": restored["empty_dirs"]})
print(f"[RECORDED] U4 report files remaining: {left}\n[RECORDED] U5 empty folders remaining: {restored['empty_dirs']}")
oo, children = outside_ok()
check("U6", "Outside root still unchanged", oo, "unchanged", f"base children {children}")
finish()
print(f"\nbatch_id {batch_id}; report {report_rel}")
