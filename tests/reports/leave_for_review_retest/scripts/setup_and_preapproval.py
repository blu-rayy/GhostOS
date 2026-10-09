"""Leave-for-review routing retest (Developer 4 / QA): setup + API checks + preview. NO approve/undo.

Uses the REAL backend on 127.0.0.1:8000 (live local model) and sends the exact payloads that
frontend/src/lib/viewModel.ts NON_TRANSACTION_DECISIONS sends:
    leave = {"category": "uncertain", "accept": true}
    file  = {"category": "other",     "accept": true}

    backend\\.venv\\Scripts\\python.exe -B tests\\reports\\leave_for_review_retest\\scripts\\setup_and_preapproval.py
"""
import hashlib
import json
import shutil
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from urllib.error import HTTPError
from urllib.request import Request, urlopen

REPO = Path(__file__).resolve().parents[4]
FIX = REPO / "tests" / "fixtures" / "sample_folder"
OUT = REPO / "tests" / "reports" / "leave_for_review_retest"
BASE = Path.home() / "AppData" / "Local" / "Temp" / "ghostos-leave-review"
# L1 and outside-canary/ were left behind (empty folder + canary) by a first attempt that stopped on a
# wrong REPO path before any scan; they are not reused or deleted.
ROOT = BASE / "L2"
CANARY = BASE / "outside-canary-2" / "canary.txt"
API = "http://127.0.0.1:8000"
LEAVE = {"category": "uncertain", "accept": True}   # NON_TRANSACTION_DECISIONS.leave
FILE = {"category": "other", "accept": True}        # NON_TRANSACTION_DECISIONS.file
FILES = {
    "lv/legal/lease-agreement-summary.pdf": "legal/lease-agreement-summary.pdf",     # unresolved -> "Leave for review"
    "lv/identity/birth-certificate.pdf": "identity/birth-certificate.pdf",           # non-transactional -> "File it"
    "lv/receipts/sunbeam-cafe-receipt.pdf": "receipts/sunbeam-cafe-receipt.pdf",     # transaction control
}
LEASE, BIRTH, SUN = list(FILES)
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
    req = Request(API + path, data=json.dumps(body).encode() if body is not None else None, method=method, headers={"Content-Type": "application/json"})
    try:
        with urlopen(req, timeout=300) as r:
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
    results.append({"id": tid, "check": check, "expected": expected, "actual": actual, "status": status, "owner": owner, "note": note})
    print(f"[{status}] {tid} {check}\n      expected: {expected}\n      actual:   {actual}" + (f"\n      note: {note}" if note else ""))


def pf(ok): return "PASS" if ok else "FAIL"


def save(name, obj): (OUT / name).write_text(json.dumps(redact(obj), indent=2), encoding="utf-8")


# ---------------- setup ----------------
for p in (ROOT, CANARY.parent, OUT / "setup"):
    if p.exists():
        sys.exit(f"STOP: {p} exists")
CANARY.parent.mkdir(parents=True)
CANARY.write_text("leave-for-review retest outside-root canary\n", encoding="utf-8")
ROOT.mkdir()
(OUT / "setup").mkdir()
for rel, src in FILES.items():
    (ROOT / rel).parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(FIX / src, ROOT / rel)
    assert sha(ROOT / rel) == sha(FIX / src)
s0 = snap(ROOT)
manifest = {"commit": subprocess.run(["git", "rev-parse", "HEAD"], cwd=REPO, capture_output=True, text=True).stdout.strip(),
            "created_at": datetime.now(timezone.utc).isoformat(), "root": "<TEST_BASE>/L2", "fixture_source": FILES,
            "snapshot": s0, "canary_sha256": sha(CANARY)}
save("setup/manifest.json", manifest)
for rel, m in s0["files"].items():
    print(f"  {rel:42} {m['size']:>6} B  {m['sha256']}")


def unchanged(): return snap(ROOT) == s0 and sha(CANARY) == manifest["canary_sha256"]


# ---------------- scan ----------------
_, status = http("GET", "/api/status")
print(f"\nREAL backend: model {status['model_name']}, external_requests {status['external_requests']}")
st, prog = http("POST", "/api/scan", {"root": str(ROOT)})
sid = prog["scan_id"]
while prog["state"] == "running":
    time.sleep(1)
    _, prog = http("GET", f"/api/scans/{sid}/progress")
_, scan = http("GET", f"/api/scans/{sid}")
save("scan_initial.json", scan)
docs = {d["relative_path"]: d for d in scan["documents"]}
for k, d in docs.items():
    c = d.get("classification") or {}
    print(f"  {k:42} status={d['status']:12} cat={c.get('category')} kind={c.get('document_kind')} profile={c.get('field_profile')} flags={[f['code'] for f in d['review_flags']]}")
print()
lc, bc, sc = (docs[k].get("classification") or {} for k in (LEASE, BIRTH, SUN))
pre = (docs[LEASE]["status"] == "needs_review" and lc.get("field_profile") != "transaction"
       and docs[BIRTH]["status"] == "needs_review" and bc.get("field_profile") != "transaction"
       and docs[SUN]["status"] == "ok" and sc.get("field_profile") == "transaction")
rec("S0", "Preconditions from the live scan", "lease and birth certificate unresolved + non-transactional (the UI shows Leave/File buttons); receipt ok + transaction",
    f"lease {docs[LEASE]['status']}/{lc.get('document_kind')}/{lc.get('field_profile')}; birth {docs[BIRTH]['status']}/{bc.get('document_kind')}/{bc.get('field_profile')}; "
    f"receipt {docs[SUN]['status']}/{sc.get('document_kind')}/{sc.get('field_profile')}", pf(pre))
if not pre:
    save("http_log.json", log); (OUT / "results.json").write_text(json.dumps(results, indent=2), encoding="utf-8")
    sys.exit("STOP: live classification does not match the scenario; no decisions applied")
_, plan0 = http("GET", f"/api/scans/{sid}/plan")
save("plan_before_decisions.json", plan0)
rec("S1", "Scan and first preview wrote nothing", "unchanged", "unchanged" if unchanged() else "CHANGED", pf(unchanged()))

# ---------------- decisions (exact UI payloads) ----------------
st, rl = http("PATCH", f"/api/documents/{docs[LEASE]['file_id']}", LEAVE)
save("patch_leave.json", {"request": LEAVE, "status": st, "response": rl})
c = rl.get("classification") or {}
rec("L1", "PATCH 'Leave for review' on the lease (exact UI payload)", "HTTP 200; category uncertain; kind/profile unchanged; no transaction values",
    f"HTTP {st}; category {c.get('category')}, kind {c.get('document_kind')}, profile {c.get('field_profile')}, tx={ {k: c.get(k) for k in ('merchant', 'date', 'amount', 'currency')} }",
    pf(st == 200 and c.get("category") == "uncertain" and c.get("document_kind") == lc.get("document_kind") and c.get("field_profile") == lc.get("field_profile")
       and all(c.get(k) in (None, "") for k in ("merchant", "date", "amount", "currency"))))
rec("L2", "Review flags / status after 'Leave for review'", "review state preserved (per test request)",
    f"status {rl.get('status')}, user_corrected {rl.get('user_corrected')}, review_flags {rl.get('review_flags')}",
    pf(bool(rl.get("review_flags")) and rl.get("status") == "needs_review"), "Dev 1 + team",
    note="accept:true clears review_flags and sets status ok by design; the review intent is kept only as category 'uncertain' + Uncategorized/ routing")
st, rb = http("PATCH", f"/api/documents/{docs[BIRTH]['file_id']}", FILE)
save("patch_file_it.json", {"request": FILE, "status": st, "response": rb})
c = rb.get("classification") or {}
rec("F1", "PATCH 'File it' on the birth certificate (exact UI payload)", "HTTP 200; category other; no transaction values",
    f"HTTP {st}; category {c.get('category')}, kind {c.get('document_kind')}, profile {c.get('field_profile')}, status {rb.get('status')}",
    pf(st == 200 and c.get("category") == "other" and all(c.get(k) in (None, "") for k in ("merchant", "date", "amount", "currency"))))
_, own = http("GET", f"/api/scans/{sid}")
landed = {k: next(d for d in own["documents"] if d["relative_path"] == k)["user_corrected"] for k in (LEASE, BIRTH)}
rec("D1g", "D1 guard: both decisions landed on this scan", "both true", landed, pf(all(landed.values())))

# ---------------- preview ----------------
_, plan = http("GET", f"/api/scans/{sid}/plan")
save("plan_for_review.json", plan)
ops = {o["original_relative_path"]: (o["destination_relative_path"], o["reason"]) for o in plan["operations"]}
for tid, k, dest in (("P1", LEASE, "Uncategorized/lease-agreement-summary.pdf"), ("P2", BIRTH, "Other/birth-certificate.pdf"),
                     ("P3", SUN, "Receipts/2026-09/sunbeam-cafe-receipt.pdf")):
    rec(tid, f"planned destination for {k}", dest, f"{ops.get(k, (None,))[0]} ({ops.get(k, (None, None))[1]})", pf(ops.get(k, (None,))[0] == dest))
rows = [(r["source_filename"], r["status"], r["amount"], r["currency"]) for r in plan["report_rows"]]
rec("P4", "Report rows", "only the receipt: accepted PHP 683.20", rows, pf(rows == [(SUN, "accepted", "683.20", "PHP")]))
rec("P5", "Blocking reviews and mode", "mode blocking, blocking_review_count 0", f"mode {plan['mode']}, blocking {plan['blocking_review_count']}",
    pf(plan["mode"] == "blocking" and plan["blocking_review_count"] == 0))
rec("P6", "Corrections and preview wrote nothing", "unchanged", "unchanged" if unchanged() else "CHANGED", pf(unchanged()))
rec("UI", "Actual frontend click on 'Leave for review'", "observed in a browser", "not performed (no browser automation in this run)", "NOT TESTED", "QA",
    note="Payload verified from frontend code (viewModel.ts NON_TRANSACTION_DECISIONS) and frontend unit test documentAware.test.ts:61")

save("http_log.json", log)
(OUT / "results.json").write_text(json.dumps(results, indent=2), encoding="utf-8")
counts = {}
for r in results:
    counts[r["status"]] = counts.get(r["status"], 0) + 1
print(f"\n{counts}\nscan {sid}  plan {plan['plan_id']}  mode {plan['mode']}  blocking {plan['blocking_review_count']}")
for k, (d, why) in ops.items():
    print(f"  {k:42} -> {d}  ({why})")
print(f"  totals {plan['totals']}")
