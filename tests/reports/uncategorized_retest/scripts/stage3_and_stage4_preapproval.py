"""Uncategorized retest - Stage 3 (root A) and Stage 4 pre-approval (root B).

Root A: scan, blocking preview, then two GUARDED approval requests that must be refused.
Root B: scan, the driver's licence "File it" decision, partial preview. NO approve/commit/undo on B.

    backend\\.venv\\Scripts\\python.exe tests\\reports\\uncategorized_retest\\scripts\\stage3_and_stage4_preapproval.py
"""
import hashlib
import json
import sys
import time
from datetime import datetime, timezone
from decimal import Decimal
from pathlib import Path
from urllib.error import HTTPError
from urllib.request import Request, urlopen

REPO = Path(__file__).resolve().parents[4]
OUT = REPO / "tests" / "reports" / "uncategorized_retest"
BASE = Path.home() / "AppData" / "Local" / "Temp" / "ghostos-uncategorized"
CANARY = BASE / "outside-canary" / "canary.txt"
BASE_URL = "http://127.0.0.1:8000"
MANIFEST = json.loads((OUT / "setup" / "manifest.json").read_text(encoding="utf-8"))

log, results = [], []


def sha(p: Path) -> str:
    return hashlib.sha256(p.read_bytes()).hexdigest()


def snapshot(root: Path) -> dict:
    return {
        "files": {p.relative_to(root).as_posix(): {"sha256": sha(p), "size": p.stat().st_size}
                  for p in sorted(root.rglob("*")) if p.is_file()},
        "dirs": sorted(p.relative_to(root).as_posix() for p in root.rglob("*") if p.is_dir()),
    }


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


def record(tid, check, expected, actual, ok, owner="Dev 1", note=""):
    status = "PASS" if ok is True else "FAIL" if ok is False else ok
    results.append({"id": tid, "check": check, "expected": expected, "actual": actual, "status": status, "owner": owner, "note": note})
    print(f"[{status}] {tid} {check}\n      expected: {expected}\n      actual:   {actual}" + (f"\n      note:     {note}" if note else ""))


def save():
    (OUT / "stage3_stage4_http_log.json").write_text(json.dumps(log, indent=2), encoding="utf-8")
    (OUT / "stage3_stage4_results.json").write_text(json.dumps(results, indent=2), encoding="utf-8")


def stop(msg):
    save()
    sys.exit(f"STOP: {msg}")


def scan(root: Path):
    st, prog = http("POST", "/api/scan", {"root": str(root)})
    if st != 200:
        stop(f"scan failed HTTP {st} {prog}")
    sid = prog["scan_id"]
    while prog["state"] == "running":
        time.sleep(1)
        _, prog = http("GET", f"/api/scans/{sid}/progress")
    _, s = http("GET", f"/api/scans/{sid}")
    return sid, s


for name in ("stage3", "stage4_preapproval"):
    if (OUT / name).exists():
        sys.exit(f"STOP: {OUT / name} exists; refusing to overwrite")
    (OUT / name).mkdir()
canary0 = MANIFEST["canary_sha256"]
_, status = http("GET", "/api/status")
print(f"model {status['model_name']} external_requests={status['external_requests']}\n")

# ============================================================ STAGE 3: root A
A = BASE / "A-normal"
a0 = snapshot(A)
ok = a0 == MANIFEST["roots"]["A-normal"]["snapshot"] and sha(CANARY) == canary0
record("N0", "Root A and canary match the setup manifest", "identical", "identical" if ok else "DIFFERS", ok)
if not ok:
    stop("root A differs from setup")
scan_a, sa = scan(A)
_, plan_a = http("GET", f"/api/scans/{scan_a}/plan")
(OUT / "stage3" / "scan.json").write_text(json.dumps(redact(sa), indent=2), encoding="utf-8")
(OUT / "stage3" / "plan_blocking.json").write_text(json.dumps(redact(plan_a), indent=2), encoding="utf-8")
(OUT / "stage3" / "snapshot_after_preview.json").write_text(json.dumps(snapshot(A), indent=2), encoding="utf-8")
ops_a = {o["original_relative_path"]: o["destination_relative_path"] for o in plan_a["operations"]}
rows_a = {r["source_filename"]: r for r in plan_a["report_rows"]}
print(f"root A scan {scan_a} plan {plan_a['plan_id']} mode={plan_a['mode']} blocking={plan_a['blocking_review_count']}")
for d in sa["documents"]:
    c = d.get("classification") or {}
    print(f"  {d['relative_path']:46} status={d['status']:12} cat={c.get('category')} kind={c.get('document_kind')} "
          f"profile={c.get('field_profile')} flags={[f['code'] for f in d['review_flags']]} -> {ops_a.get(d['relative_path'])}")
print()
expected_a = {
    "inbox-a/receipts/sunbeam-cafe-receipt.pdf": "Receipts/2026-09/sunbeam-cafe-receipt.pdf",
    "inbox-a/identity/birth-certificate.pdf": "Uncategorized/birth-certificate.pdf",
    "inbox-a/receipts/bayside-office-mart.pdf": "Uncategorized/bayside-office-mart.pdf",
    "inbox-a/misc/aircon-payment-note.txt": "Uncategorized/aircon-payment-note.txt",
    "inbox-a/scans/empty-scan.txt": "Uncategorized/empty-scan.txt",
}
docs_a = {d["relative_path"]: d for d in sa["documents"]}
for i, (src, dest) in enumerate(expected_a.items(), 1):
    d = docs_a.get(src, {})
    record(f"N1.{i}", f"blocking preview destination for {src}", f"{dest} (status {'ok' if 'sunbeam' in src else 'needs_review/failed'})",
           f"{ops_a.get(src)} (status {d.get('status')}, flags {[f['code'] for f in d.get('review_flags', [])]})", ops_a.get(src) == dest)
record("N1.6", "No Unsorted/ destination", "none start with Unsorted/", [d for d in ops_a.values() if d.startswith("Unsorted")] or "none",
       not any(d.startswith("Unsorted") for d in ops_a.values()))
record("N1.7", "Birth certificate has no report row", "absent", rows_a.get("inbox-a/identity/birth-certificate.pdf") or "absent",
       "inbox-a/identity/birth-certificate.pdf" not in rows_a)
record("N1.8", "Review warnings present on unresolved documents", "each needs_review/failed document has >=1 flag",
       {k: [f["code"] for f in v["review_flags"]] for k, v in docs_a.items() if v["status"] != "ok"},
       all(v["review_flags"] for v in docs_a.values() if v["status"] != "ok"))
record("N1.9", "Preview does not change root A", "identical to setup", "identical" if snapshot(A) == a0 else "CHANGED", snapshot(A) == a0)

# --- guarded approval requests (must be refused)
if not (plan_a["mode"] == "blocking" and plan_a["blocking_review_count"] > 0):
    record("N2", "Guard for refused approvals", "blocking mode with blocking_review_count > 0",
           f"mode={plan_a['mode']} blocking={plan_a['blocking_review_count']}", "BLOCKED", note="Approval requests NOT sent.")
    stop("guard not satisfied for root A; no approval requests sent")
print(f"=== APPROVAL REQUEST 1 (expect 409): root {A}, plan {plan_a['plan_id']}, mode blocking, blocking={plan_a['blocking_review_count']}, intended change: NONE")
st, body = http("POST", f"/api/plans/{plan_a['plan_id']}/approve", {})
same = snapshot(A) == a0 and sha(CANARY) == canary0
record("N2", "Empty-body (blocking) approval while reviews are open", "HTTP 409 'unresolved review items'; root A and canary unchanged",
       f"HTTP {st} {json.dumps(body)}; filesystem {'unchanged' if same else 'CHANGED'}",
       st == 409 and "unresolved review" in json.dumps(body) and same)
if not same:
    stop("filesystem changed after approval request 1")
print(f"=== APPROVAL REQUEST 2 (expect 409 mode mismatch): plan {plan_a['plan_id']} previewed in blocking mode, body {{mode: partial}}, intended change: NONE")
st, body = http("POST", f"/api/plans/{plan_a['plan_id']}/approve", {"mode": "partial"})
same = snapshot(A) == a0 and sha(CANARY) == canary0
record("N3", "Partial approval against a blocking-mode preview", "HTTP 409 mode mismatch; root A and canary unchanged",
       f"HTTP {st} {json.dumps(body)}; filesystem {'unchanged' if same else 'CHANGED'}",
       st == 409 and "mode" in json.dumps(body).lower() and same)
(OUT / "stage3" / "snapshot_after_refused_approvals.json").write_text(json.dumps(snapshot(A), indent=2), encoding="utf-8")
if not same:
    stop("filesystem changed after approval request 2")
print()

# ============================================================ STAGE 4 (pre-approval): root B
B = BASE / "B-partial"
b0 = snapshot(B)
ok = b0 == MANIFEST["roots"]["B-partial"]["snapshot"] and sha(CANARY) == canary0
record("P0", "Root B and canary match the setup manifest", "identical", "identical" if ok else "DIFFERS", ok)
if not ok:
    stop("root B differs from setup")
scan_b, sb = scan(B)
(OUT / "stage4_preapproval" / "scan.json").write_text(json.dumps(redact(sb), indent=2), encoding="utf-8")
docs_b = {d["relative_path"]: d for d in sb["documents"]}
print(f"root B scan {scan_b}")
for d in sb["documents"]:
    c = d.get("classification") or {}
    print(f"  {d['relative_path']:46} status={d['status']:12} cat={c.get('category')} kind={c.get('document_kind')} "
          f"profile={c.get('field_profile')} amount={c.get('amount')} {c.get('currency')} date={c.get('date')} flags={[f['code'] for f in d['review_flags']]}")
print()
for src, amount in (("inbox-b/receipts/sunbeam-cafe-receipt.pdf", "683.20"), ("inbox-b/receipts/tibay-hardware-receipt.csv", "2145.00")):
    d, c = docs_b[src], docs_b[src].get("classification") or {}
    record(f"P1-{src.rsplit('/', 1)[1]}", f"transaction classified cleanly: {src}", f"status ok, receipt/transaction, PHP {amount}, dated 2026-09",
           f"status {d['status']}, {c.get('category')}/{c.get('field_profile')}, {c.get('currency')} {c.get('amount')}, date {c.get('date')}",
           d["status"] == "ok" and c.get("field_profile") == "transaction" and c.get("amount") == amount and (c.get("date") or "").startswith("2026-09"))
lic_src = "inbox-b/identity/drivers-license-record.txt"
lic = docs_b[lic_src]
lc = lic.get("classification") or {}
pre_ok = lc.get("document_kind") == "identity_or_civil" and lc.get("field_profile") == "none" and all(lc.get(k) in (None, "") for k in ("merchant", "date", "amount", "currency"))
record("P2a", "Licence before the decision: non-transactional, no transaction values",
       "kind identity_or_civil, profile none, merchant/date/amount/currency null",
       f"kind {lc.get('document_kind')}, profile {lc.get('field_profile')}, status {lic['status']}, "
       f"tx={ {k: lc.get(k) for k in ('merchant', 'date', 'amount', 'currency')} }", pre_ok)
if not pre_ok:
    stop("licence classification is not as expected; decision NOT applied")
st, resp = http("PATCH", f"/api/documents/{lic['file_id']}", {"category": "other", "accept": True})
rc = resp.get("classification") or {} if isinstance(resp, dict) else {}
dec_ok = (st == 200 and rc.get("category") == "other" and rc.get("document_kind") == "identity_or_civil" and rc.get("field_profile") == "none"
          and all(rc.get(k) in (None, "") for k in ("merchant", "date", "amount", "currency")) and resp.get("user_corrected") is True)
record("P2b", "'File it' decision {category: other, accept: true} on the licence",
       "HTTP 200; category other; kind/profile unchanged; no transaction values; user_corrected true",
       f"HTTP {st}; category {rc.get('category')}, kind {rc.get('document_kind')}, profile {rc.get('field_profile')}, "
       f"tx={ {k: rc.get(k) for k in ('merchant', 'date', 'amount', 'currency')} }, status {resp.get('status') if isinstance(resp, dict) else '-'}, "
       f"user_corrected {resp.get('user_corrected') if isinstance(resp, dict) else '-'}", dec_ok)
_, sb2 = http("GET", f"/api/scans/{scan_b}")
landed = next(d for d in sb2["documents"] if d["file_id"] == lic["file_id"])["user_corrected"]
record("P2c", "D1 guard: the decision landed on root B's own scan", "user_corrected true on this scan", landed, landed is True)
if not landed:
    stop("D1 interference: decision did not land on root B's scan")

_, plan_b = http("GET", f"/api/scans/{scan_b}/plan?mode=partial")
(OUT / "stage4_preapproval" / "plan_partial_for_review.json").write_text(json.dumps(redact(plan_b), indent=2), encoding="utf-8")
ops_b = {o["original_relative_path"]: o for o in plan_b["operations"]}
expected_b = {
    "inbox-b/receipts/sunbeam-cafe-receipt.pdf": "Receipts/2026-09/sunbeam-cafe-receipt.pdf",
    "inbox-b/receipts/tibay-hardware-receipt.csv": "Receipts/2026-09/tibay-hardware-receipt.csv",
    "inbox-b/identity/drivers-license-record.txt": "Other/drivers-license-record.txt",
    "inbox-b/legal/lease-agreement-summary.pdf": "Uncategorized/lease-agreement-summary.pdf",
    "inbox-b/receipts/bayside-office-mart.pdf": "Uncategorized/bayside-office-mart.pdf",
}
record("P3a", "Partial preview mode and plan id", f"mode partial, plan_{scan_b}", f"mode {plan_b['mode']}, {plan_b['plan_id']}",
       plan_b["mode"] == "partial" and plan_b["plan_id"] == f"plan_{scan_b}")
for i, (src, dest) in enumerate(expected_b.items(), 1):
    actual = ops_b.get(src, {}).get("destination_relative_path")
    record(f"P3.{i}", f"partial destination for {src}", dest, f"{actual} ({ops_b.get(src, {}).get('reason')})", actual == dest)
record("P3.6", "No Unsorted/ destination", "none", [o["destination_relative_path"] for o in plan_b["operations"] if o["destination_relative_path"].startswith("Unsorted")] or "none",
       not any(o["destination_relative_path"].startswith("Unsorted") for o in plan_b["operations"]))
rows = plan_b["report_rows"]
row_summary = [(r["source_filename"], r["status"], r["amount"], r["currency"]) for r in rows]
exp_rows = {("inbox-b/receipts/sunbeam-cafe-receipt.pdf", "accepted", "683.20", "PHP"), ("inbox-b/receipts/tibay-hardware-receipt.csv", "accepted", "2145.00", "PHP")}
record("P4a", "Report rows: only the two accepted receipts", sorted(exp_rows), row_summary, set(row_summary) == exp_rows and len(rows) == 2)
gt_total = Decimal("683.20") + Decimal("2145.00")
totals = {t["currency"]: (t["amount"], t["row_count"]) for t in plan_b["totals"]}
record("P4b", "Totals = independently calculated PHP 2,828.20 (2 rows)", {"PHP": (str(gt_total), 2)}, totals,
       totals == {"PHP": (str(gt_total), 2)})
record("P4c", "Blocking review count reported (lease + Bayside unresolved)", 2, plan_b["blocking_review_count"],
       plan_b["blocking_review_count"] == 2)
flags = {k: [f["code"] for f in docs_b[k]["review_flags"]] for k in ("inbox-b/legal/lease-agreement-summary.pdf", "inbox-b/receipts/bayside-office-mart.pdf")}
record("P4d", "Review warnings visible on the two unresolved documents", "each has >=1 flag", flags, all(flags.values()))
b_same = snapshot(B) == b0
a_same = snapshot(A) == a0
record("P5", "Root B, root A and canary unchanged (no approve/commit/undo on B)", "identical",
       f"B {'identical' if b_same else 'CHANGED'}, A {'identical' if a_same else 'CHANGED'}, canary {'identical' if sha(CANARY) == canary0 else 'CHANGED'}",
       b_same and a_same and sha(CANARY) == canary0)
(OUT / "stage4_preapproval" / "snapshot_after_preview.json").write_text(json.dumps(snapshot(B), indent=2), encoding="utf-8")
save()
counts = {}
for r in results:
    counts[r["status"]] = counts.get(r["status"], 0) + 1
print(f"\n{counts}\nroot A: scan {scan_a} / {plan_a['plan_id']}   root B: scan {scan_b} / {plan_b['plan_id']} (partial)  -- STOPPED before B approval")
