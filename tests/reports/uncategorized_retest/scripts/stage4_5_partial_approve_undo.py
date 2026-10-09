"""Uncategorized retest - Stage 4 approval + Stage 5 undo for plan_scan_1cabbc9828aa (partial) on root B.

Pre-checks -> approve once {"mode":"partial"} -> verify -> undo -> verify.
Stops without undo (no unplanned repair) if approval, move or report verification fails.

    backend\\.venv\\Scripts\\python.exe tests\\reports\\uncategorized_retest\\scripts\\stage4_5_partial_approve_undo.py
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

REPO = Path(__file__).resolve().parents[4]
OUT = REPO / "tests" / "reports" / "uncategorized_retest"
EV = OUT / "stage4_5_execute"
BASE = Path.home() / "AppData" / "Local" / "Temp" / "ghostos-uncategorized"
ROOT_A, ROOT_B = BASE / "A-normal", BASE / "B-partial"
CANARY = BASE / "outside-canary" / "canary.txt"
BASE_URL = "http://127.0.0.1:8000"
SCAN_ID, PLAN_ID = "scan_1cabbc9828aa", "plan_scan_1cabbc9828aa"

MANIFEST = json.loads((OUT / "setup" / "manifest.json").read_text(encoding="utf-8"))
REVIEWED = json.loads((OUT / "stage4_preapproval" / "plan_partial_for_review.json").read_text(encoding="utf-8"))
ORIG_B = {k: v["sha256"] for k, v in MANIFEST["roots"]["B-partial"]["snapshot"]["files"].items()}
SNAP_A = MANIFEST["roots"]["A-normal"]["snapshot"]
CANARY_SHA = MANIFEST["canary_sha256"]
UNRESOLVED = {"inbox-b/legal/lease-agreement-summary.pdf", "inbox-b/receipts/bayside-office-mart.pdf"}
SOURCE_DIRS = ["inbox-b", "inbox-b/receipts", "inbox-b/identity", "inbox-b/legal"]

log, results = [], []


def sha(p: Path) -> str:
    return hashlib.sha256(p.read_bytes()).hexdigest()


def snapshot(root: Path) -> dict:
    return {
        "files": {p.relative_to(root).as_posix(): {"sha256": sha(p), "size": p.stat().st_size}
                  for p in sorted(root.rglob("*")) if p.is_file()},
        "dirs": sorted(p.relative_to(root).as_posix() for p in root.rglob("*") if p.is_dir()),
        "empty_dirs": sorted(p.relative_to(root).as_posix() for p in root.rglob("*") if p.is_dir() and not any(p.iterdir())),
    }


def hashes(snap):
    return {k: v["sha256"] for k, v in snap["files"].items()}


def redact(obj):
    text = json.dumps(obj)
    for form in (str(BASE), str(BASE).replace("\\", "/")):
        text = text.replace(json.dumps(form)[1:-1], "<TEST_BASE>")
    return json.loads(text)


def http(method, path, body=None):
    req = Request(BASE_URL + path, data=json.dumps(body).encode() if body is not None else None, method=method,
                  headers={"Content-Type": "application/json"})
    try:
        with urlopen(req, timeout=300) as r:
            st, payload = r.status, json.loads(r.read() or b"null")
    except HTTPError as e:
        raw = e.read()
        st = e.code
        try:
            payload = json.loads(raw)
        except Exception:
            payload = raw.decode("utf-8", "replace")
    log.append(redact({"at": datetime.now(timezone.utc).isoformat(), "request": {"method": method, "path": path, "body": body},
                       "response": {"status": st, "body": payload}}))
    return st, payload


def check(cid, name, ok, expected, actual):
    status = "PASS" if ok else "FAIL"
    results.append({"id": cid, "check": name, "status": status, "expected": expected, "actual": actual})
    print(f"[{status}] {cid} {name}\n        expected: {expected}\n        actual:   {actual}")
    return ok


def save_json(name, obj):
    (EV / name).write_text(json.dumps(redact(obj), indent=2), encoding="utf-8")


def save():
    save_json("http_log.json", log)
    (EV / "results.json").write_text(json.dumps(results, indent=2), encoding="utf-8")


def stop(msg):
    save()
    sys.exit(f"STOP: {msg}")


def outside_ok():
    children = sorted(p.name for p in BASE.iterdir())
    return children == ["A-normal", "B-partial", "outside-canary"] and snapshot(ROOT_A)["files"] == SNAP_A["files"] and sha(CANARY) == CANARY_SHA, children


if EV.exists():
    sys.exit(f"STOP: {EV} exists; this step was already executed")
EV.mkdir()

# ============================ PRE-CHECKS ======================================
print("=== PRE-APPROVAL CHECKS ===")
st, plan = http("GET", f"/api/scans/{SCAN_ID}/plan?mode=partial")
before = snapshot(ROOT_B)
save_json("snapshot_before_approve.json", before)
ok = True
ok &= check("Q1", "Scan ID and plan ID unchanged", st == 200 and plan.get("scan_id") == SCAN_ID and plan.get("plan_id") == PLAN_ID,
            f"{SCAN_ID} / {PLAN_ID}", f"HTTP {st} {plan.get('scan_id')} / {plan.get('plan_id')}")
ok &= check("Q2", "Plan byte-identical to the reviewed partial preview", plan == REVIEWED, "identical to plan_partial_for_review.json",
            "identical" if plan == REVIEWED else "DIFFERS")
ok &= check("Q3", "Preview mode is partial; approval body will be {mode: partial}", plan.get("mode") == "partial", "partial", plan.get("mode"))
ops = {o["original_relative_path"]: o["destination_relative_path"] for o in plan.get("operations", [])}
ok &= check("Q4", "Exactly five operations", len(ops) == 5, 5, len(ops))
ok &= check("Q5", "The two unresolved documents still go to Uncategorized/",
            all(ops.get(u, "").startswith("Uncategorized/") for u in UNRESOLVED), {u: "Uncategorized/..." for u in UNRESOLVED}, {u: ops.get(u) for u in UNRESOLVED})
ok &= check("Q6", "Original five files present with recorded SHA-256 (and nothing else)", hashes(before) == ORIG_B, "matches setup manifest",
            "matches" if hashes(before) == ORIG_B else hashes(before))
problems = []
for d in ops.values():
    rel = Path(d)
    if rel.is_absolute() or ".." in rel.parts or ROOT_B.resolve() not in (ROOT_B / rel).resolve().parents:
        problems.append(f"{d}: outside root")
    if os.path.lexists(ROOT_B / rel):
        problems.append(f"{d}: already exists")
ok &= check("Q7", "Destinations inside root B and currently free", not problems, "no problems", problems or "none")
ok &= check("Q8", "Destinations unique (case-insensitive)", len({d.lower() for d in ops.values()}) == 5, 5, len({d.lower() for d in ops.values()}))
oo, children = outside_ok()
ok &= check("Q9", "Outside-root canary and root A unchanged", oo, "unchanged", f"base children {children}; {'unchanged' if oo else 'CHANGED'}")
if not ok:
    stop("a pre-check differs from the reviewed plan; approval NOT requested")

# ============================ APPROVE (once, partial) ==========================
print(f"\n=== APPROVING {PLAN_ID} (mode partial) on {ROOT_B} ===")
st, batch = http("POST", f"/api/plans/{PLAN_ID}/approve", {"mode": "partial"})
save_json("approve_response.json", {"status": st, "body": batch})
print(f"HTTP {st}: {json.dumps(batch)}")
after = snapshot(ROOT_B)
save_json("snapshot_after_approve.json", after)
if not check("S1", "Partial approval succeeds: 5 moved, 0 failed", st == 200 and batch.get("moved") == 5 and batch.get("failed") == [],
             "HTTP 200, moved=5, failed=[]", f"HTTP {st} {batch}"):
    stop("approval did not succeed as expected; undo NOT attempted")
batch_id, report_rel = batch["batch_id"], batch["report_relative_path"]

v = True
expected_files = {dst: ORIG_B[src] for src, dst in ops.items()}
actual = {k: v_["sha256"] for k, v_ in after["files"].items() if k != report_rel}
v &= check("M1", "Each file at its approved destination with EXACT case and original SHA-256", actual == expected_files,
           sorted(expected_files), sorted(actual))
v &= check("M2", "No overwrite: 5 distinct files, each holding its own source bytes",
           len(actual) == 5 and sorted(actual.values()) == sorted(ORIG_B.values()), "5 files, multiset of hashes = originals", f"{len(actual)} files")
unsorted = [d for d in after["dirs"] if d.lower().startswith("unsorted")]
v &= check("M3", "No Unsorted/ folder created", not unsorted, "none", unsorted or "none")
in_src = [k for k in after["files"] if any(k.startswith(s + "/") for s in SOURCE_DIRS)]
v &= check("M4", "No organized file inside a source folder", not in_src, "none", in_src or "none")
v &= check("M5", "No temporary report file left", not [k for k in after["files"] if k.endswith(".tmp")], "none",
           [k for k in after["files"] if k.endswith(".tmp")] or "none")
oo, children = outside_ok()
v &= check("M6", "Nothing outside root B written; root A and canary unchanged", oo, "unchanged", f"base children {children}; {'unchanged' if oo else 'CHANGED'}")
if not v:
    stop("move verification failed; undo NOT attempted (no unplanned repair)")

# ============================ CSV ==============================================
raw = (ROOT_B / report_rel).read_bytes()
(EV / "report_copy.csv").write_bytes(raw)
rows = list(csv.reader(io.StringIO(raw.decode("utf-8").lstrip("﻿"), newline="")))
header, data = rows[0], [r for r in rows[1:] if r]
c = True
c &= check("R1", "Report written inside root B; BOM, CRLF, header",
           raw.startswith(b"\xef\xbb\xbf") and b"\n" not in raw.replace(b"\r\n", b"") and header == ["source_file", "merchant", "date", "category", "amount", "currency"],
           "GhostOS Reports/expenses-<stamp>.csv", f"{report_rel}; header={header}")
got = sorted((r[0], r[4], r[5]) for r in data)
exp = sorted([("inbox-b/receipts/sunbeam-cafe-receipt.pdf", "683.20", "PHP"), ("inbox-b/receipts/tibay-hardware-receipt.csv", "2145.00", "PHP")])
c &= check("R2", "Exactly two accepted receipt rows (Sunbeam, Tibay)", got == exp, exp, got)
excluded = [r[0] for r in data if any(x in r[0] for x in ("drivers-license", "lease-agreement", "bayside"))]
c &= check("R3", "Licence, lease and Bayside absent from the CSV", not excluded, "absent", excluded or "absent")
csv_total = {}
for r in data:
    csv_total[r[5]] = csv_total.get(r[5], Decimal(0)) + Decimal(r[4])
c &= check("R4", "Totals recomputed from the CSV = PHP 2,828.20", csv_total == {"PHP": Decimal("2828.20")}, {"PHP": "2828.20"},
           {k: str(x) for k, x in csv_total.items()})
if not c:
    stop("report verification failed; undo NOT attempted (no unplanned repair)")

# ============================ UNDO ==============================================
print(f"\n=== UNDO {batch_id} ===")
st, undo = http("POST", f"/api/batches/{batch_id}/undo", {})
save_json("undo_response.json", {"status": st, "body": undo})
print(f"HTTP {st}: {json.dumps(undo)}")
restored = snapshot(ROOT_B)
save_json("snapshot_after_undo.json", restored)
check("U1", "Undo succeeds with no conflicts", st == 200 and undo.get("restored") == 5 and undo.get("conflicts") == [],
      "HTTP 200, restored=5, conflicts=[]", f"HTTP {st}, restored={undo.get('restored')}, conflicts={undo.get('conflicts')}")
back = {k: restored["files"].get(k, {}).get("sha256") for k in ORIG_B}
check("U2", "All five original paths (exact case) restored with original SHA-256", back == ORIG_B, "5/5 identical",
      "5/5 identical" if back == ORIG_B else back)
leftover_files = sorted(set(restored["files"]) - set(ORIG_B))
check("U3", "No organized files remain (only the report may remain)", all(f.startswith("GhostOS Reports/") for f in leftover_files),
      "only GhostOS Reports/*", leftover_files or "none")
check("U4", "Source folders contain only their original files",
      all(k in ORIG_B for k in restored["files"] if any(k.startswith(s + "/") for s in SOURCE_DIRS)), "only originals",
      sorted(k for k in restored["files"] if k.startswith("inbox-b/")))
results.append({"id": "U5", "check": "(observed) report files remaining after undo", "status": "RECORDED", "actual": leftover_files})
results.append({"id": "U6", "check": "(observed) empty folders remaining after undo", "status": "RECORDED", "actual": restored["empty_dirs"]})
print(f"[RECORDED] U5 report files remaining: {leftover_files}\n[RECORDED] U6 empty folders remaining: {restored['empty_dirs']}")
oo, children = outside_ok()
check("U7", "Outside root B still unchanged after undo", oo, "unchanged", f"base children {children}")
save()
print(f"\nbatch_id: {batch_id}  report: {report_rel}")
