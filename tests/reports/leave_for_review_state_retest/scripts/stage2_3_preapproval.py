"""Leave-for-review STATE retest (bf99c68) - setup + non-destructive checks. No successful approval, no undo.

REAL backend 127.0.0.1:8000 (live model). Sends the exact UI payloads from
frontend/src/lib/viewModel.ts NON_TRANSACTION_DECISIONS:
    leave = {"category": "uncertain", "accept": true}
    file  = {"category": "other",     "accept": true}
The only approval request is the guarded blocking-mode one, which must be refused (409).
An in-process part (production app, mocked classifier, own store) reads plan_revision directly.

    backend\\.venv\\Scripts\\python.exe -B tests\\reports\\leave_for_review_state_retest\\scripts\\stage2_3_preapproval.py
"""
import copy
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

sys.dont_write_bytecode = True
REPO = Path(__file__).resolve().parents[4]
FIX = REPO / "tests" / "fixtures" / "sample_folder"
OUT = REPO / "tests" / "reports" / "leave_for_review_state_retest"
BASE = Path.home() / "AppData" / "Local" / "Temp" / "ghostos-leave-state"
ROOT = BASE / "LS1"
MROOT = BASE / "LS1-inprocess"
CANARY = BASE / "outside-canary" / "canary.txt"
API = "http://127.0.0.1:8000"
LEAVE = {"category": "uncertain", "accept": True}
FILE = {"category": "other", "accept": True}
FILES = {
    "ls/receipts/bayside-office-mart.pdf": "receipts/bayside-office-mart.pdf",       # existing flag (amount_conflict) -> Leave (API)
    "ls/legal/lease-agreement-summary.pdf": "legal/lease-agreement-summary.pdf",     # non-transaction with flags -> Leave (UI-realistic)
    "ls/identity/birth-certificate.pdf": "identity/birth-certificate.pdf",           # control: File it -> Other/
    "ls/receipts/sunbeam-cafe-receipt.pdf": "receipts/sunbeam-cafe-receipt.pdf",     # control: valid receipt
}
BAY, LEASE, BIRTH, SUN = list(FILES)
LEAVE_TARGETS = (BAY, LEASE)
log, results = [], []
sys.path.insert(0, str(REPO / "backend"))


def sha(p): return hashlib.sha256(p.read_bytes()).hexdigest()


def snap(root):
    return {p.relative_to(root).as_posix(): {"sha256": sha(p), "size": p.stat().st_size} for p in sorted(root.rglob("*")) if p.is_file()}


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


def save(name, obj):
    (OUT / name).parent.mkdir(parents=True, exist_ok=True)
    (OUT / name).write_text(json.dumps(redact(obj), indent=2), encoding="utf-8")


def state(d):
    c = d.get("classification") or {}
    return {"status": d["status"], "user_corrected": d["user_corrected"], "review_disposition": d.get("review_disposition"),
            "flags": [f["code"] for f in d["review_flags"]], "category": c.get("category"), "document_kind": c.get("document_kind"),
            "field_profile": c.get("field_profile"), "merchant": c.get("merchant"), "date": c.get("date"), "amount": c.get("amount"),
            "currency": c.get("currency")}


# ---------------- setup ----------------
for p in (BASE, OUT / "setup"):
    if p.exists():
        sys.exit(f"STOP: {p} exists")
BASE.mkdir()
CANARY.parent.mkdir()
CANARY.write_text("leave-for-review state retest outside-root canary\n", encoding="utf-8")
for root in (ROOT, MROOT):
    root.mkdir()
    for rel, src in FILES.items():
        (root / rel).parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(FIX / src, root / rel)
manifest = {"commit": subprocess.run(["git", "rev-parse", "HEAD"], cwd=REPO, capture_output=True, text=True).stdout.strip(),
            "created_at": datetime.now(timezone.utc).isoformat(), "root": "<TEST_BASE>/LS1", "fixture_source": FILES,
            "snapshot": snap(ROOT), "inprocess_snapshot": snap(MROOT), "canary_sha256": sha(CANARY)}
save("setup/manifest.json", manifest)
for rel, m in manifest["snapshot"].items():
    print(f"  {rel:42} {m['size']:>6} B  {m['sha256']}")


def unchanged(): return snap(ROOT) == manifest["snapshot"] and snap(MROOT) == manifest["inprocess_snapshot"] and sha(CANARY) == manifest["canary_sha256"]


# ---------------- scan ----------------
_, prog = http("POST", "/api/scan", {"root": str(ROOT)})
sid = prog["scan_id"]
while prog["state"] == "running":
    time.sleep(1)
    _, prog = http("GET", f"/api/scans/{sid}/progress")
_, scan0 = http("GET", f"/api/scans/{sid}")
save("scan_initial.json", scan0)
docs = {d["relative_path"]: d for d in scan0["documents"]}
before = {k: state(d) for k, d in docs.items()}
save("state_before_corrections.json", before)
print()
for k, s in before.items():
    print(f"  {k:42} {s}")
print()
pre = (before[BAY]["status"] == "needs_review" and "amount_conflict" in before[BAY]["flags"] and before[LEASE]["status"] == "needs_review"
       and before[LEASE]["flags"] and before[BIRTH]["status"] == "needs_review" and before[SUN]["status"] == "ok")
rec("S0", "Live scan preconditions", "Bayside needs_review+amount_conflict; lease needs_review with flags; birth certificate needs_review; Sunbeam ok",
    {k: (v["status"], v["flags"]) for k, v in before.items()}, pf(pre))
if not pre:
    save("http_log.json", log); (OUT / "results.json").write_text(json.dumps(results, indent=2), encoding="utf-8")
    sys.exit("STOP: preconditions not met")
rec("S1", "review_disposition exposed before any correction", "'none' on every document",
    {k: v["review_disposition"] for k, v in before.items()}, pf(all(v["review_disposition"] == "none" for v in before.values())))

# ---------------- Leave for review (exact UI payload) ----------------
for i, k in enumerate(LEAVE_TARGETS, 1):
    st, resp = http("PATCH", f"/api/documents/{docs[k]['file_id']}", LEAVE)
    _, g = http("GET", f"/api/scans/{sid}")
    after_get = state(next(d for d in g["documents"] if d["relative_path"] == k))
    after_patch = state(resp) if isinstance(resp, dict) and "status" in resp else {}
    save(f"leave_{i}_{k.rsplit('/', 1)[1]}.json", {"request": LEAVE, "status": st, "response": resp, "state_before": before[k], "state_after_get": after_get})
    b = before[k]
    for src, s in (("PATCH response", after_patch), ("GET", after_get)):
        tx_same = all(s.get(f) == b[f] for f in ("merchant", "date", "amount", "currency"))
        ok = (st == 200 and s.get("review_disposition") == "leave_for_review" and s.get("status") == "needs_review" and s.get("flags") == b["flags"]
              and s.get("category") == "uncertain" and tx_same and s.get("user_corrected") is True)
        rec(f"L{i}-{'P' if src.startswith('PATCH') else 'G'}", f"Leave for review on {k.rsplit('/', 1)[1]} ({src})",
            f"200; disposition leave_for_review; status needs_review; flags preserved {b['flags']}; category uncertain; merchant/date/amount/currency unchanged",
            f"HTTP {st}; disposition {s.get('review_disposition')}; status {s.get('status')}; flags {s.get('flags')}; category {s.get('category')}; "
            f"tx {'unchanged' if tx_same else {f: s.get(f) for f in ('merchant', 'date', 'amount', 'currency')}}; user_corrected {s.get('user_corrected')}", pf(ok))

# ---------------- File it control ----------------
st, resp = http("PATCH", f"/api/documents/{docs[BIRTH]['file_id']}", FILE)
s = state(resp)
save("file_it_birth_certificate.json", {"request": FILE, "status": st, "response": resp})
rec("F1", "File it on the birth certificate (control: behaviour stays separate)", "200; disposition filed; status ok; flags cleared; category other",
    f"HTTP {st}; disposition {s['review_disposition']}; status {s['status']}; flags {s['flags']}; category {s['category']}",
    pf(st == 200 and s["review_disposition"] == "filed" and s["status"] == "ok" and s["flags"] == [] and s["category"] == "other"))

# ---------------- blocking preview + guarded refused approval ----------------
_, pb = http("GET", f"/api/scans/{sid}/plan")
save("plan_blocking.json", pb)
ob = {o["original_relative_path"]: o["destination_relative_path"] for o in pb["operations"]}
rec("B1", "Blocking preview counts the left-for-review documents", "mode blocking; blocking_review_count 2 (Bayside, lease)",
    f"mode {pb['mode']}; blocking {pb['blocking_review_count']}", pf(pb["mode"] == "blocking" and pb["blocking_review_count"] == 2))
rec("B2", "Blocking preview destinations", "Bayside, lease -> Uncategorized/; birth -> Other/; Sunbeam -> Receipts/2026-09/",
    ob, pf(ob.get(BAY) == "Uncategorized/bayside-office-mart.pdf" and ob.get(LEASE) == "Uncategorized/lease-agreement-summary.pdf"
           and ob.get(BIRTH) == "Other/birth-certificate.pdf" and ob.get(SUN) == "Receipts/2026-09/sunbeam-cafe-receipt.pdf"))
if pb["mode"] == "blocking" and pb["blocking_review_count"] > 0:
    print(f"\n=== GUARDED blocking approval (expect 409): plan {pb['plan_id']}, blocking={pb['blocking_review_count']}, intended change NONE ===")
    st, resp = http("POST", f"/api/plans/{pb['plan_id']}/approve", {})
    rec("B3", "Default blocking approval with left-for-review items", "HTTP 409 unresolved review items; filesystem unchanged",
        f"HTTP {st} {resp}; filesystem {'unchanged' if unchanged() else 'CHANGED'}", pf(st == 409 and "unresolved" in json.dumps(resp) and unchanged()))
else:
    rec("B3", "Default blocking approval", "409", "NOT SENT: blocker absent", "BLOCKED")

# ---------------- partial preview ----------------
_, pp = http("GET", f"/api/scans/{sid}/plan?mode=partial")
save("plan_partial_for_review.json", pp)
op = {o["original_relative_path"]: o["destination_relative_path"] for o in pp["operations"]}
rows = [(r["source_filename"], r["status"], r["amount"], r["currency"]) for r in pp["report_rows"]]
rec("P1", "Partial preview destinations", "Bayside, lease -> Uncategorized/; birth -> Other/; Sunbeam -> Receipts/2026-09/", op,
    pf(op == ob))
rec("P2", "Partial preview report rows", "only Sunbeam accepted PHP 683.20; no row for left-for-review documents", rows,
    pf(rows == [(SUN, "accepted", "683.20", "PHP")]))
rec("P3", "Partial preview totals and mode", "mode partial; PHP 683.20", f"mode {pp['mode']}; totals {pp['totals']}; blocking {pp['blocking_review_count']}",
    pf(pp["mode"] == "partial" and [(t["currency"], t["amount"]) for t in pp["totals"]] == [("PHP", "683.20")]))
_, g = http("GET", f"/api/scans/{sid}")
still = {k: state(next(d for d in g["documents"] if d["relative_path"] == k)) for k in LEAVE_TARGETS}
rec("P4", "Left-for-review documents still unresolved after previews", "status needs_review, disposition leave_for_review, flags preserved",
    {k: (v["status"], v["review_disposition"], v["flags"]) for k, v in still.items()},
    pf(all(v["status"] == "needs_review" and v["review_disposition"] == "leave_for_review" and v["flags"] == before[k]["flags"] for k, v in still.items())))
rec("G1", "Scans, corrections, previews and refused approval wrote nothing", "root, in-process root and canary unchanged", "unchanged" if unchanged() else "CHANGED", pf(unchanged()))

# ---------------- in-process: plan revision on Leave for review (mocked classifier) ----------------
from fastapi.testclient import TestClient  # noqa: E402
from app.main import app  # noqa: E402
from app.schemas import ClassificationRecord  # noqa: E402
from app.services import local_ai  # noqa: E402
from app.services.session_store import store  # noqa: E402

PAY = {"category": "receipt", "document_kind": "receipt", "merchant": "BAYSIDE OFFICE MART", "date": "2026-09-05", "amount_text": "PHP 1,520.00",
       "currency": "PHP", "evidence_quote": "AMOUNT DUE: PHP 1,520.00", "explanation": "MOCK"}
real = local_ai.classify_excerpt
local_ai.classify_excerpt = lambda excerpt, **kw: (local_ai.ClassificationResult(ClassificationRecord.model_validate(PAY), 0.0)
                                                   if "BAYSIDE" in excerpt else (_ for _ in ()).throw(local_ai.LocalAIResponseError("MOCK: not used")))
try:
    client = TestClient(app)
    r = client.post("/api/scan", json={"root": str(MROOT)}).json()
    while r["state"] == "running":
        time.sleep(0.2)
        r = client.get(f"/api/scans/{r['scan_id']}/progress").json()
    msid = r["scan_id"]
    sess = store.get_scan(msid)
    client.get(f"/api/scans/{msid}/plan?mode=partial")
    snapshot = store.get_plan_snapshot(f"plan_{msid}")
    bdoc = next(d for d in sess.documents if d.relative_path == BAY)
    rev0, flags0 = sess.plan_revision, copy.deepcopy(bdoc.review_flags)
    resp = client.patch(f"/api/documents/{bdoc.file_id}", json=LEAVE)
    rec("RV1", "In-process (mocked classifier): Leave for review bumps plan_revision; stored record keeps flags; old partial snapshot becomes stale",
        "200; revision +1; disposition leave_for_review; status needs_review; flags preserved; snapshot.session_revision != plan_revision",
        f"HTTP {resp.status_code}; revision {rev0}->{sess.plan_revision}; disposition {bdoc.review_disposition}; status {bdoc.status}; "
        f"flags {'preserved' if bdoc.review_flags == flags0 else bdoc.review_flags}; snapshot rev {snapshot.session_revision}",
        pf(resp.status_code == 200 and sess.plan_revision == rev0 + 1 and bdoc.review_disposition == "leave_for_review" and bdoc.status == "needs_review"
           and bdoc.review_flags == flags0 and snapshot.session_revision != sess.plan_revision))
finally:
    local_ai.classify_excerpt = real

rec("UI1", "Frontend handling of review_disposition (code inspection)", "UI treats leave_for_review as unresolved in blocking mode",
    "frontend has no review_disposition; isBlocking/isNeeds = status needs_review && !user_corrected -> a left-for-review document counts as decided",
    "FAIL", "Dev 3", note="In blocking mode the UI would enable 'Continue to totals' and the backend then refuses approval (409). Partial mode is unaffected.")
rec("UI2", "Actual browser click on 'Leave for review'", "observed in a browser", "not performed (no browser automation in this run)", "NOT TESTED", "QA")

save("http_log.json", log)
(OUT / "results.json").write_text(json.dumps(results, indent=2), encoding="utf-8")
counts = {}
for r_ in results:
    counts[r_["status"]] = counts.get(r_["status"], 0) + 1
print(f"\n{counts}\nscan {sid}  partial plan {pp['plan_id']}  mode {pp['mode']}  blocking {pp['blocking_review_count']}")
for k, d in op.items():
    print(f"  {k:42} -> {d}")
