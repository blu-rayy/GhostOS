"""DA-5 retest - corrected B2 (new scan, model omits document_kind) on a fresh root DA5-R3,
and a fresh preview of the candidate approval batch DA5-R2. NON-DESTRUCTIVE (no approve/undo).

Talks to the MOCK backend on 127.0.0.1:8001 (restarted with the corrected marker order).

    backend\\.venv\\Scripts\\python.exe -B tests\\reports\\document_aware_review\\da5_retest_3c60bb3\\scripts\\da5_b2_rerun_and_r2_preview.py
"""
import hashlib
import json
import shutil
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from urllib.error import HTTPError
from urllib.request import Request, urlopen

REPO = Path(__file__).resolve().parents[5]
FIX = REPO / "tests" / "fixtures" / "sample_folder"
OUT = REPO / "tests" / "reports" / "document_aware_review" / "da5_retest_3c60bb3"
BASE = Path.home() / "AppData" / "Local" / "Temp" / "ghostos-docaware"
R2, R3 = BASE / "DA5-R2", BASE / "DA5-R3"
CANARY = BASE / "DA5-canary" / "canary.txt"
MOCK = "http://127.0.0.1:8001"
MANIFEST = json.loads((OUT / "setup" / "manifest.json").read_text(encoding="utf-8"))
log, results = [], []


def sha(p): return hashlib.sha256(p.read_bytes()).hexdigest()


def snap(root):
    return {"files": {p.relative_to(root).as_posix(): {"sha256": sha(p), "size": p.stat().st_size} for p in sorted(root.rglob("*")) if p.is_file()},
            "dirs": sorted(p.relative_to(root).as_posix() for p in root.rglob("*") if p.is_dir())}


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


def rec(tid, check, expected, actual, status, owner="Dev 1", note=""):
    results.append({"id": tid, "case": "B new-scan omission (corrected)" if tid.startswith("B2") else "R2 preview", "method": "MOCKED classifier",
                    "check": check, "expected": expected, "actual": actual, "status": status, "owner": owner, "note": note})
    print(f"[{status}] {tid} {check}\n      expected: {expected}\n      actual:   {actual}" + (f"\n      note: {note}" if note else ""))


def scan(root):
    _, prog = http("POST", "/api/scan", {"root": str(root)})
    sid = prog["scan_id"]
    while prog["state"] == "running":
        time.sleep(0.3)
        _, prog = http("GET", f"/api/scans/{sid}/progress")
    _, s = http("GET", f"/api/scans/{sid}")
    return sid, s


for p in (R3, OUT / "b2_rerun", OUT / "r2_preview_v2"):
    if p.exists():
        sys.exit(f"STOP: {p} exists")
(OUT / "b2_rerun").mkdir(); (OUT / "r2_preview_v2").mkdir()
R3.mkdir()
CARD = "r3/misc/card-statement-sep2026.pdf"
(R3 / CARD).parent.mkdir(parents=True)
shutil.copy2(FIX / "misc/card-statement-sep2026.pdf", R3 / CARD)
r3_0 = snap(R3)
(OUT / "b2_rerun" / "R3_snapshot_initial.json").write_text(json.dumps(r3_0, indent=2), encoding="utf-8")
r2_0 = MANIFEST["roots"]["DA5-R2"]["snapshot"]
if snap(R2) != r2_0 or sha(CANARY) != MANIFEST["canary_sha256"]:
    sys.exit("STOP: R2 or canary differs from setup")

# ---- B2 corrected
sid3, s3 = scan(R3)
d = s3["documents"][0]
c = d.get("classification") or {}
(OUT / "b2_rerun" / "R3_scan.json").write_text(json.dumps(redact(s3), indent=2), encoding="utf-8")
rec("B2a'", "mocked response really omits document_kind (harness check)", "explanation 'MOCK: kind omitted'", c.get("explanation"),
    "PASS" if c.get("explanation") == "MOCK: kind omitted" else "FAIL", "QA harness")
_, pb = http("GET", f"/api/scans/{sid3}/plan")
dest = next((o["destination_relative_path"] for o in pb["operations"] if o["original_relative_path"] == CARD), None)
row = next((r for r in pb["report_rows"] if r["source_filename"] == CARD), None)
rec("B2a", "how a NEW scan with the kind omitted is treated", "record (developer contract: legacy category fallback)",
    f"API kind {c.get('document_kind')}, profile {c.get('field_profile')}, status {d['status']}, flags {[f['code'] for f in d['review_flags']]}, "
    f"amount {c.get('amount')!r}, amount_text {c.get('amount_text')!r}; blocking dest {dest}; row {row and (row['status'], row['amount'])}", "RECORDED")
st, _ = http("PATCH", f"/api/documents/{d['file_id']}", {"accept": True})
_, pa = http("GET", f"/api/scans/{sid3}/plan")
dest2 = next((o["destination_relative_path"] for o in pa["operations"] if o["original_relative_path"] == CARD), None)
row2 = next((r for r in pa["report_rows"] if r["source_filename"] == CARD), None)
counted = bool(row2 and row2["status"] == "accepted")
rec("B2b", "accept-as-is on that statement", "not counted (QA safety rule); legacy compatibility would allow it",
    f"HTTP {st}; destination {dest2}; row {row2 and (row2['status'], row2['amount'])}; totals {pa['totals']}",
    "FAIL" if counted else "PASS", "Dev 1 + team",
    note="Counted as an expense via the legacy fallback for a NEW model response without document_kind." if counted else "")
rec("B2c", "R3 unchanged", "unchanged", "unchanged" if snap(R3) == r3_0 else "CHANGED", "PASS" if snap(R3) == r3_0 else "FAIL")

# ---- R2 fresh preview (candidate approval batch); no PATCH, no approve
sid2, s2 = scan(R2)
_, p2b = http("GET", f"/api/scans/{sid2}/plan")
_, p2 = http("GET", f"/api/scans/{sid2}/plan?mode=partial")
for name, obj in (("R2_scan.json", s2), ("R2_plan_blocking.json", p2b), ("R2_plan_partial_for_review.json", p2)):
    (OUT / "r2_preview_v2" / name).write_text(json.dumps(redact(obj), indent=2), encoding="utf-8")
ok = snap(R2) == r2_0 and sha(CANARY) == MANIFEST["canary_sha256"]
rec("G4", "R2 scan + previews wrote nothing; canary unchanged", "unchanged", "unchanged" if ok else "CHANGED", "PASS" if ok else "FAIL")
(OUT / "b2_rerun" / "http_log.json").write_text(json.dumps(log, indent=2), encoding="utf-8")
(OUT / "b2_rerun" / "results.json").write_text(json.dumps(results, indent=2), encoding="utf-8")

print(f"\nR2 scan {sid2}  plan {p2['plan_id']}  mode {p2['mode']}  blocking {p2['blocking_review_count']}")
for doc in s2["documents"]:
    cc = doc.get("classification") or {}
    print(f"  doc {doc['relative_path']:40} status {doc['status']:12} kind {cc.get('document_kind')!s:8} profile {cc.get('field_profile')} flags {[f['code'] for f in doc['review_flags']]}")
for o in p2["operations"]:
    print(f"  op  {o['original_relative_path']:40} -> {o['destination_relative_path']}  ({o['reason']})")
print(f"  rows   {[(r['source_filename'], r['status'], r['amount'], r['currency']) for r in p2['report_rows']]}")
print(f"  totals {p2['totals']}")
