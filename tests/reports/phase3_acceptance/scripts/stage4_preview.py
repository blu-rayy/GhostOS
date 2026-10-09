"""Phase 3 acceptance, Stage 4 (part 1, READ-ONLY): scan + preview root B. No approval, no correction."""
import hashlib
import json
import sys
import time
from datetime import datetime, timezone
from decimal import Decimal
from pathlib import Path
from urllib.error import HTTPError
from urllib.request import Request, urlopen

BASE_URL = "http://127.0.0.1:8000"
ROOT = Path(r"C:\Users\My PC\AppData\Local\Temp\ghostos-phase3\B-acceptance")
CANARY = Path(r"C:\Users\My PC\AppData\Local\Temp\ghostos-phase3\outside-canary\canary.txt")
OUT = Path(r"C:\Users\My PC\Documents\Hackathon\GhostOS\GhostOS\tests\reports\phase3_acceptance")
MANIFEST = json.loads((OUT / "00_setup_manifest.json").read_text(encoding="utf-8"))["roots"]["B-acceptance"]["files"]
log = []


def redact(obj):
    text = json.dumps(obj)
    for form in (str(ROOT), str(ROOT).replace("\\", "/")):
        text = text.replace(json.dumps(form)[1:-1], "<ROOT_B>")
    return json.loads(text)


def http(method, path, body=None):
    req = Request(BASE_URL + path, data=json.dumps(body).encode() if body is not None else None, method=method,
                  headers={"Content-Type": "application/json"})
    try:
        with urlopen(req, timeout=120) as r:
            status, payload = r.status, json.loads(r.read() or b"null")
    except HTTPError as e:
        status, payload = e.code, e.read().decode("utf-8", "replace")
    log.append(redact({"at": datetime.now(timezone.utc).isoformat(), "request": {"method": method, "path": path, "body": body},
                       "response": {"status": status, "body": payload}}))
    return status, payload


def fingerprint():
    return {"files": {p.relative_to(ROOT).as_posix(): hashlib.sha256(p.read_bytes()).hexdigest()
                      for p in sorted(ROOT.rglob("*")) if p.is_file()},
            "canary": hashlib.sha256(CANARY.read_bytes()).hexdigest()}


expected_set = {e["relative_path"]: e["sha256"] for e in MANIFEST}
before = fingerprint()
if before["files"] != expected_set:
    sys.exit("STOP: root B does not match the setup manifest")

st, prog = http("POST", "/api/scan", {"root": str(ROOT)})
scan_id = prog["scan_id"]
while prog["state"] == "running":
    time.sleep(1)
    st, prog = http("GET", f"/api/scans/{scan_id}/progress")
st, scan = http("GET", f"/api/scans/{scan_id}")
st, plan = http("GET", f"/api/scans/{scan_id}/plan")
after = fingerprint()

(OUT / "B_01_http_log_preview.json").write_text(json.dumps(log, indent=2), encoding="utf-8")
(OUT / "B_02_scan_result.json").write_text(json.dumps(redact(scan), indent=2), encoding="utf-8")
(OUT / "B_03_plan_snapshot_for_approval.json").write_text(json.dumps(redact(plan), indent=2), encoding="utf-8")
(OUT / "B_00_fingerprint_before.json").write_text(json.dumps({"before_scan": before, "after_preview": after}, indent=2), encoding="utf-8")

truth = {e["relative_path"]: e["expected"] for e in MANIFEST}
by_id = {d["file_id"]: d for d in scan["documents"]}
print(f"root:    {ROOT}\nscan_id: {scan_id}\nplan_id: {plan['plan_id']}\nblocking_review_count: {plan['blocking_review_count']}")
print(f"preview left root B and canary unchanged: {after == before}\n")
print("CLASSIFICATION vs GROUND TRUTH")
for d in scan["documents"]:
    c, t = d.get("classification") or {}, truth[d["relative_path"]]
    match = (c.get("category") == t["expected_category"] and c.get("date") == t["expected_date"]
             and c.get("amount") is not None and Decimal(c["amount"]) == Decimal(t["expected_amount"])
             and c.get("currency") == t["expected_currency"])
    print(f"  {d['relative_path']:46} {d['status']:12} {c.get('category')}/{c.get('merchant')}/{c.get('date')}/"
          f"{c.get('amount')} {c.get('currency')} flags={[f['code'] for f in d['review_flags']]} "
          f"duplicate_of={(by_id.get(d['duplicate_of']) or {}).get('relative_path')}  matches_truth={match}")
print("\nPROPOSED OPERATIONS")
for op in plan["operations"]:
    print(f"  {op['original_relative_path']:46} -> {op['destination_relative_path']}  "
          f"{'[collision suffix]' if op['collision_suffixed'] else ''} ({op['reason']})")
print("\nREPORT ROWS IN PLAN")
for r in plan["report_rows"]:
    print(f"  {r['status']:12} {r['source_filename']:46} {r['merchant']} {r['date']} {r['amount']} {r['currency']}")
print(f"\nPLAN TOTALS: {plan['totals']}")
