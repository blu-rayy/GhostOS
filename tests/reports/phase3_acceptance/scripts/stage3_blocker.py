"""Phase 3 acceptance, Stage 3: unresolved-review blocker on root A.

Approval is only ever requested when the snapshot being approved has
blocking_review_count > 0, so no file can move. The stale-plan check uses a
no-op correction (accept=false), so no ambiguous data is ever accepted.
"""
import hashlib
import json
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from urllib.error import HTTPError
from urllib.request import Request, urlopen

BASE_URL = "http://127.0.0.1:8000"
ROOT = Path(r"C:\Users\My PC\AppData\Local\Temp\ghostos-phase3\A-blocker")
CANARY = Path(r"C:\Users\My PC\AppData\Local\Temp\ghostos-phase3\outside-canary\canary.txt")
OUT = Path(r"C:\Users\My PC\Documents\Hackathon\GhostOS\GhostOS\tests\reports\phase3_acceptance")
EXPECTED_FILES = {"receipts/bayside-office-mart.pdf", "receipts/tibay-hardware-receipt.csv"}

log: list[dict] = []
results: list[dict] = []


def redact(obj):
    text = json.dumps(obj)
    for form in (str(ROOT), str(ROOT).replace("\\", "/")):
        text = text.replace(json.dumps(form)[1:-1], "<ROOT_A>")
    return json.loads(text)


def http(method, path, body=None):
    data = json.dumps(body).encode() if body is not None else None
    req = Request(BASE_URL + path, data=data, method=method, headers={"Content-Type": "application/json"})
    try:
        with urlopen(req, timeout=120) as r:
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


def fingerprint() -> dict:
    files = {p.relative_to(ROOT).as_posix(): hashlib.sha256(p.read_bytes()).hexdigest()
             for p in sorted(ROOT.rglob("*")) if p.is_file()}
    return {"files": files, "canary": hashlib.sha256(CANARY.read_bytes()).hexdigest()}


def record(test, status, expected, actual, evidence=""):
    results.append({"test": test, "status": status, "expected": expected, "actual": actual, "evidence": evidence})
    print(f"[{status:11}] {test}\n              expected: {expected}\n              actual:   {actual}")


def save(name, obj):
    (OUT / name).write_text(json.dumps(redact(obj), indent=2), encoding="utf-8")


# ---- preconditions ---------------------------------------------------------
if not ROOT.is_dir() or {p.relative_to(ROOT).as_posix() for p in ROOT.rglob("*") if p.is_file()} != EXPECTED_FILES:
    sys.exit(f"STOP: root A is missing or does not contain exactly the expected files: {ROOT}")
fp = {"before": fingerprint()}
st, status = http("GET", "/api/status")
print(f"backend status HTTP {st}: model={status.get('model_name')} external_requests={status.get('external_requests')}")

# ---- scan --------------------------------------------------------------------
st, prog = http("POST", "/api/scan", {"root": str(ROOT)})
assert st == 200, (st, prog)
scan_id = prog["scan_id"]
t0 = time.perf_counter()
while prog["state"] == "running" and time.perf_counter() - t0 < 600:
    time.sleep(1)
    st, prog = http("GET", f"/api/scans/{scan_id}/progress")
st, scan = http("GET", f"/api/scans/{scan_id}")
save("A_02_scan_result.json", scan)
fp["after_scan"] = fingerprint()
print(f"\nscan {scan_id}: state={prog['state']} in {time.perf_counter() - t0:.1f}s")
for d in scan["documents"]:
    c = d.get("classification") or {}
    print(f"  {d['relative_path']:40} status={d['status']:12} category={c.get('category')} amount={c.get('amount')} "
          f"{c.get('currency')} flags={[f['code'] for f in d['review_flags']]}")

# ---- preview (snapshot 1) ----------------------------------------------------
st, plan1 = http("GET", f"/api/scans/{scan_id}/plan")
save("A_03_plan_snapshot1.json", plan1)
fp["after_preview"] = fingerprint()
record("A1 Scan does not modify root A", "PASS" if fp["after_scan"] == fp["before"] else "FAIL",
       "identical file set and SHA-256", "identical" if fp["after_scan"] == fp["before"] else "CHANGED")
record("A2 Preview does not modify root A", "PASS" if fp["after_preview"] == fp["before"] else "FAIL",
       "identical file set and SHA-256", "identical" if fp["after_preview"] == fp["before"] else "CHANGED")

# ---- approval attempt 1 (must be rejected) -----------------------------------
print("\n=== APPROVAL ATTEMPT 1 (expected rejection) ===")
print(f"root:      {ROOT}\nscan_id:   {scan_id}\nplan_id:   {plan1['plan_id']}\n"
      f"blocking_review_count: {plan1['blocking_review_count']}")
for op in plan1["operations"]:
    print(f"  op: {op['original_relative_path']} -> {op['destination_relative_path']}  ({op['reason']})")
print("intended filesystem change: NONE (request must be refused because review items are unresolved)")
if plan1["blocking_review_count"] <= 0:
    record("A3 Approval rejected while review is unresolved", "BLOCKED",
           "a blocking review item in root A", "blocking_review_count=0, approval NOT attempted")
    save("A_01_http_log.json", log); save("A_05_fingerprints.json", fp); save("A_06_results.json", results)
    sys.exit("STOP: no blocking review in root A; approval was not requested.")
st, resp = http("POST", f"/api/plans/{plan1['plan_id']}/approve", {})
fp["after_approve_1"] = fingerprint()
ok = st == 409 and "unresolved review" in json.dumps(resp) and fp["after_approve_1"] == fp["before"]
record("A3 Approval rejected while review is unresolved", "PASS" if ok else "FAIL",
       "HTTP 409 'unresolved review items', no file moved or changed",
       f"HTTP {st} {json.dumps(resp)}; files {'unchanged' if fp['after_approve_1'] == fp['before'] else 'CHANGED'}")

# ---- stale-snapshot check (no data accepted) ---------------------------------
target = next((d for d in scan["documents"] if d["status"] == "needs_review"), None)
merchant = (target.get("classification") or {}).get("merchant") or "Bayside Office Mart"
print(f"\n=== NO-OP CORRECTION (accept=false) on {target['relative_path']}: merchant={merchant!r} ===")
st, patched = http("PATCH", f"/api/documents/{target['file_id']}", {"merchant": merchant, "accept": False})
save("A_04_patch_response.json", {"status": st, "body": patched})
record("A4 No-op correction keeps the document in review", "PASS" if st == 200 and patched["status"] == "needs_review" and not patched["user_corrected"] else "FAIL",
       "HTTP 200, status needs_review, user_corrected false", f"HTTP {st}, status {patched.get('status')}, user_corrected {patched.get('user_corrected')}")

print("\n=== APPROVAL ATTEMPT 2 on the OLD snapshot (expected rejection: stale) ===")
print(f"root: {ROOT}\nscan_id: {scan_id}\nplan_id: {plan1['plan_id']} (snapshot taken before the correction)\n"
      "intended filesystem change: NONE")
st, resp = http("POST", f"/api/plans/{plan1['plan_id']}/approve", {})
fp["after_approve_2"] = fingerprint()
ok = st == 409 and "stale" in json.dumps(resp).lower() and fp["after_approve_2"] == fp["before"]
record("A5 Stale snapshot rejected after a correction", "PASS" if ok else "FAIL",
       "HTTP 409 'Plan is stale; refresh the preview', no file moved or changed",
       f"HTTP {st} {json.dumps(resp)}; files {'unchanged' if fp['after_approve_2'] == fp['before'] else 'CHANGED'}")

# ---- fresh preview (read-only; NOT approved) ----------------------------------
st, plan2 = http("GET", f"/api/scans/{scan_id}/plan")
save("A_03b_plan_snapshot2_after_correction.json", plan2)
record("A6 Fresh preview still blocked after a non-accepting correction",
       "PASS" if plan2["blocking_review_count"] > 0 else "FAIL",
       "blocking_review_count > 0 (nothing was accepted)", f"blocking_review_count={plan2['blocking_review_count']} (not approved)")

fp["final"] = fingerprint()
record("A7 Root A and outside canary unchanged at end of Stage 3",
       "PASS" if fp["final"] == fp["before"] else "FAIL", "identical to setup", "identical" if fp["final"] == fp["before"] else "CHANGED")

save("A_01_http_log.json", log)
save("A_05_fingerprints.json", fp)
save("A_06_results.json", results)
print(f"\nsaved: {OUT}")
