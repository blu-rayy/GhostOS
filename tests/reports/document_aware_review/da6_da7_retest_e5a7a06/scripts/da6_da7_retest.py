"""DA-6 / DA-7 regression retest on e5a7a06 (Developer 4 / QA). NON-DESTRUCTIVE: no approve, no undo, no file move.

Part LIVE       real backend 127.0.0.1:8000 + live local model, disposable root DA67-L.
Part INPROCESS  production FastAPI app via TestClient with a MOCKED classifier and its own in-memory
                store, disposable root DA67-M. Used where store internals (plan_revision, plan snapshot)
                must be read directly, and for a deterministic ambiguous-amount receipt.

    backend\\.venv\\Scripts\\python.exe -B tests\\reports\\document_aware_review\\da6_da7_retest_e5a7a06\\scripts\\da6_da7_retest.py
"""
from __future__ import annotations

import copy
import csv
import hashlib
import io
import json
import shutil
import subprocess
import sys
import time
from datetime import datetime, timezone
from decimal import Decimal
from pathlib import Path
from urllib.error import HTTPError
from urllib.request import Request, urlopen

sys.dont_write_bytecode = True
REPO = Path(__file__).resolve().parents[5]
FIX = REPO / "tests" / "fixtures" / "sample_folder"
OUT = REPO / "tests" / "reports" / "document_aware_review" / "da6_da7_retest_e5a7a06"
BASE = Path.home() / "AppData" / "Local" / "Temp" / "ghostos-docaware"
LIVE_ROOT, MOCK_ROOT = BASE / "DA67-L", BASE / "DA67-M"
CANARY = BASE / "DA67-canary" / "canary.txt"
API = "http://127.0.0.1:8000"
sys.path.insert(0, str(REPO / "backend"))

DOCS = {  # relative path in root -> (fixture, expected accepted amount or None)
    "d67/receipts/tibay-hardware-receipt.csv": ("receipts/tibay-hardware-receipt.csv", "2145.00"),   # valid receipt (DA-6 target)
    "d67/archive/2026/invoice.pdf": ("archive/2026/invoice.pdf", "3470.00"),                        # valid invoice (Carabao)
    "d67/receipts/bayside-office-mart.pdf": ("receipts/bayside-office-mart.pdf", None),             # conflicting totals
    "d67/misc/card-statement-sep2026.pdf": ("misc/card-statement-sep2026.pdf", None),               # statement
    "d67/invoices/INV-1043_Pixelforge_Studio.pdf": ("invoices/INV-1043_Pixelforge_Studio.pdf", "18648.00"),
    "d67/receipts/sunbeam-cafe-receipt.pdf": ("receipts/sunbeam-cafe-receipt.pdf", "683.20"),
}
TIB, CAR, BAY, CARD, PIX, SUN = list(DOCS)
results: list[dict] = []
live_log: list[dict] = []


def sha(p): return hashlib.sha256(p.read_bytes()).hexdigest()


def snap(root):
    return {p.relative_to(root).as_posix(): {"sha256": sha(p), "size": p.stat().st_size} for p in sorted(root.rglob("*")) if p.is_file()}


def redact(o):
    t = json.dumps(o, default=str)
    for f in (str(BASE), str(BASE).replace("\\", "/")):
        t = t.replace(json.dumps(f)[1:-1], "<TEST_BASE>")
    return json.loads(t)


def rec(tid, area, method, check, expected, actual, status, owner="Dev 1", note=""):
    results.append({"id": tid, "area": area, "method": method, "check": check, "expected": expected, "actual": actual,
                    "status": status, "owner": owner, "note": note})
    print(f"[{status}] {tid} ({method}) {check}\n      expected: {expected}\n      actual:   {actual}" + (f"\n      note: {note}" if note else ""))


def pf(ok): return "PASS" if ok else "FAIL"


def write(name, obj):
    (OUT / name).parent.mkdir(parents=True, exist_ok=True)
    (OUT / name).write_text(json.dumps(redact(obj), indent=2), encoding="utf-8")


def live(method, path, body=None):
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
    live_log.append(redact({"at": datetime.now(timezone.utc).isoformat(), "request": {"method": method, "path": path, "body": body}, "response": {"status": st, "body": pl}}))
    return st, pl


# ================================================================ Stage 2: setup
for p in (LIVE_ROOT, MOCK_ROOT, CANARY.parent, OUT / "setup"):
    if p.exists():
        sys.exit(f"STOP: {p} exists")
CANARY.parent.mkdir(parents=True)
CANARY.write_text("DA-6/DA-7 retest outside-root canary\n", encoding="utf-8")
for root in (LIVE_ROOT, MOCK_ROOT):
    root.mkdir()
    for rel, (src, _amt) in DOCS.items():
        (root / rel).parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(FIX / src, root / rel)
manifest = {"commit": subprocess.run(["git", "rev-parse", "HEAD"], cwd=REPO, capture_output=True, text=True).stdout.strip(),
            "created_at": datetime.now(timezone.utc).isoformat(), "canary_sha256": sha(CANARY),
            "expected_amounts": {k: v[1] for k, v in DOCS.items()},
            "roots": {"DA67-L": snap(LIVE_ROOT), "DA67-M": snap(MOCK_ROOT)}}
write("setup/manifest.json", manifest)


def fs_unchanged():
    return snap(LIVE_ROOT) == manifest["roots"]["DA67-L"] and snap(MOCK_ROOT) == manifest["roots"]["DA67-M"] and sha(CANARY) == manifest["canary_sha256"]


# ================================================================ PART LIVE
_, status = live("GET", "/api/status")
print(f"LIVE backend model {status['model_name']} external_requests {status['external_requests']}\n")
_, prog = live("POST", "/api/scan", {"root": str(LIVE_ROOT)})
sid = prog["scan_id"]
while prog["state"] == "running":
    time.sleep(1)
    _, prog = live("GET", f"/api/scans/{sid}/progress")
_, scan0 = live("GET", f"/api/scans/{sid}")
write("live/scan_initial.json", scan0)
ID = {d["relative_path"]: d["file_id"] for d in scan0["documents"]}


def ldoc(k):
    _, s = live("GET", f"/api/scans/{sid}")
    return next(d for d in s["documents"] if d["file_id"] == ID[k])


def lplan():
    _, p = live("GET", f"/api/scans/{sid}/plan")
    return p


evidence = {}
for d in scan0["documents"]:
    c = d.get("classification") or {}
    evidence[d["relative_path"]] = {"status": d["status"], "category": c.get("category"), "kind": c.get("document_kind"), "profile": c.get("field_profile"),
                                    "amount": c.get("amount"), "amount_text": c.get("amount_text"), "currency": c.get("currency"),
                                    "evidence_quote": c.get("evidence_quote"), "flags": [f["code"] for f in d["review_flags"]]}
    print(f"  {d['relative_path']:46} {d['status']:12} {c.get('category')}/{c.get('document_kind')}/{c.get('field_profile')} "
          f"amount={c.get('amount')!r} amount_text={c.get('amount_text')!r} flags={[f['code'] for f in d['review_flags']]}")
write("live/amount_evidence.json", evidence)
plan0 = lplan()
write("live/plan_initial.json", plan0)
print()

# ---- live classification vs expectations (amount evidence)
for tid, k in (("E1", PIX), ("E2", SUN), ("E3", TIB), ("E4", CAR)):
    e = evidence[k]
    exp = DOCS[k][1]
    rec(tid, "DA-7 evidence", "LIVE", f"{k} validated amount", f"status ok, amount {exp}",
        f"status {e['status']}, amount {e['amount']!r}, amount_text {e['amount_text']!r}, flags {e['flags']}",
        pf(e["status"] == "ok" and e["amount"] == exp), "Dev 2" if e["amount"] != exp else "")
e = evidence[BAY]
rec("E5", "DA-7 evidence", "LIVE", "Bayside conflicting totals flagged", "needs_review with amount_conflict; amount null",
    f"status {e['status']}, amount {e['amount']!r}, amount_text {e['amount_text']!r}, flags {e['flags']}",
    pf(e["status"] == "needs_review" and "amount_conflict" in e["flags"] and e["amount"] is None))
e = evidence[CARD]
rec("E6", "DA-7 evidence", "LIVE", "Card statement not one expense", "kind statement, profile reference (or non-transaction), no accepted row",
    f"{e['category']}/{e['kind']}/{e['profile']}, flags {e['flags']}; plan row {[r['status'] for r in plan0['report_rows'] if r['source_filename'] == CARD]}",
    pf(e["profile"] != "transaction" and not any(r["source_filename"] == CARD and r["status"] == "accepted" for r in plan0["report_rows"])))


# ---- DA-6: individual invalid corrections (each separately), live
def invalid(tid, key, body, why):
    before_doc, before_plan = ldoc(key), lplan()
    st, resp = live("PATCH", f"/api/documents/{ID[key]}", body)
    after_doc, after_plan = ldoc(key), lplan()
    same_doc, same_plan = after_doc == before_doc, after_plan == before_plan
    write(f"live/da6/{tid}.json", {"body": body, "status": st, "response": resp, "doc_before": before_doc, "doc_after": after_doc,
                                    "plan_before_id": before_plan["plan_id"], "plan_unchanged": same_plan})
    rec(tid, "DA-6", "LIVE", f"PATCH {key.rsplit('/', 1)[1]} {json.dumps(body)}", f"HTTP 422 ({why}); record and plan unchanged",
        f"HTTP {st} {resp.get('detail') if isinstance(resp, dict) else resp}; record {'unchanged' if same_doc else 'CHANGED'}; plan {'unchanged' if same_plan else 'CHANGED'}",
        pf(st == 422 and same_doc and same_plan))


invalid("V1", TIB, {"amount": "abc"}, "unparseable amount")
invalid("V2", TIB, {"date": "2026-13-45"}, "invalid ISO date")
invalid("V3", TIB, {"currency": "XYZ"}, "unsupported currency")
invalid("V4", TIB, {"amount": "9999.99"}, "amount contradicts source evidence")
invalid("V5", TIB, {"destination_relative_path": "../../escape.csv"}, "client destination path")
invalid("V6", TIB, {"operations": [{"file_id": ID[TIB], "destination_relative_path": "C:/Windows/x.csv"}]}, "client operations")
invalid("V7", TIB, {"field_profile": "transaction"}, "client field_profile")
invalid("V8", TIB, {"editable_fields": ["amount"]}, "client editable-field list")
invalid("V9", TIB, {"allowed_fields": ["amount"]}, "client allowed-field list")
invalid("V10", TIB, {"accept": "yes"}, "non-boolean accept")
rec("V11", "DA-6", "LIVE", "filesystem after V1-V10", "unchanged", "unchanged" if fs_unchanged() else "CHANGED", pf(fs_unchanged()))

# ---- DA-7 amount corrections, live
invalid("B1", BAY, {"amount": "1250.00"}, "Bayside subtotal: source is ambiguous")
invalid("B2", BAY, {"amount": "1520.00"}, "Bayside amount due: source is ambiguous")
invalid("C1", CARD, {"amount": "5391.06"}, "statement: no transaction amount")
invalid("C2", CARD, {"category": "invoice", "accept": True}, "statement cannot take a transaction category")
invalid("S1", SUN, {"amount": "610.00"}, "Sunbeam subtotal is not the authoritative total")
if evidence[PIX]["amount"] == "18648.00":
    invalid("P1", PIX, {"amount": "18500.00"}, "Pixelforge subtotal is not the authoritative total")
else:
    rec("P1", "DA-7", "LIVE", "Pixelforge subtotal correction", "422", "skipped: live amount not 18648.00", "BLOCKED", "Dev 2")
# valid, source-supported correction (no accept), then accept-as-is on Bayside (the DA-7 revival path)
st, resp = live("PATCH", f"/api/documents/{ID[SUN]}", {"amount": "683.20"})
rec("S2", "DA-7", "LIVE", "Sunbeam source-supported amount correction {amount: 683.20}", "HTTP 200; amount kept",
    f"HTTP {st}; amount {((resp or {}).get('classification') or {}).get('amount') if isinstance(resp, dict) else resp!r}",
    pf(st == 200 and resp["classification"]["amount"] == "683.20"))
st, resp = live("PATCH", f"/api/documents/{ID[BAY]}", {"accept": True})
p_bay = lplan()
row = next((r for r in p_bay["report_rows"] if r["source_filename"] == BAY), None)
rec("B3", "DA-7", "LIVE", "Bayside accept-as-is {accept: true} (no amount)", "no accepted row; nothing added to totals",
    f"HTTP {st}; flags after {resp.get('review_flags') if isinstance(resp, dict) else '-'}; row {row and (row['status'], row['amount'])}; totals {p_bay['totals']}",
    pf(not (row and row["status"] == "accepted")),
    note=f"live amount_text was {evidence[BAY]['amount_text']!r}; revival needs a parseable amount_text")
st, resp = live("PATCH", f"/api/documents/{ID[CARD]}", {"accept": True})
p_card = lplan()
row = next((r for r in p_card["report_rows"] if r["source_filename"] == CARD), None)
rec("C3", "DA-7", "LIVE", "Card statement accept-as-is", "no accepted row", f"HTTP {st}; row {row and (row['status'], row['amount'])}",
    pf(not (row and row["status"] == "accepted")))

# ---- report filtering: prepare the CSV with the production renderer from the final plan rows
from app.services.report import render_report  # noqa: E402
from app.services.session_store import ReportRow  # noqa: E402

final = lplan()
write("live/plan_final.json", final)
csv_text = render_report([ReportRow(**r) for r in final["report_rows"]])
(OUT / "live" / "prepared_report.csv").write_text(csv_text, encoding="utf-8", newline="")
rows = [r for r in list(csv.reader(io.StringIO(csv_text.lstrip("\ufeff"), newline="")))[1:] if r]
csv_tot = {}
for r in rows:
    csv_tot[r[5]] = csv_tot.get(r[5], Decimal(0)) + Decimal(r[4])
expected_rows = {k: v[1] for k, v in DOCS.items() if v[1] is not None and evidence[k]["amount"] == v[1]}
exp_tot = {"PHP": sum((Decimal(v) for v in expected_rows.values()), Decimal(0))}
rec("R1", "Report", "LIVE + production render_report (prepared, not committed)", "CSV rows = accepted transactions only",
    sorted(expected_rows), sorted(r[0] for r in rows), pf(sorted(r[0] for r in rows) == sorted(expected_rows)))
rec("R2", "Report", "LIVE + render_report", "Totals recomputed from the CSV = independent ground truth = plan totals",
    {k: str(v) for k, v in exp_tot.items()}, {"csv": {k: str(v) for k, v in csv_tot.items()}, "plan": {t["currency"]: t["amount"] for t in final["totals"]}},
    pf(csv_tot == exp_tot and {t["currency"]: Decimal(t["amount"]) for t in final["totals"]} == exp_tot))
rec("R3", "Report", "LIVE", "No Bayside or statement row in the CSV", "absent", [r[0] for r in rows if r[0] in (BAY, CARD)] or "absent",
    pf(not [r for r in rows if r[0] in (BAY, CARD)]))
dests = [o["destination_relative_path"] for o in final["operations"]]
rec("G1", "Plan", "LIVE", "Destinations from the backend map, relative, inside the root, unique",
    "Invoices|Receipts/YYYY-MM, Other, Uncategorized (or GhostOS Organized/...)", dests,
    pf(all(not d.startswith(("/", "\\")) and ".." not in d.split("/") and d.split("/")[0] in ("Invoices", "Receipts", "Other", "Uncategorized", "GhostOS Organized") for d in dests)
       and len({d.lower() for d in dests}) == len(dests)))
# UI regression probe (last; on the valid invoice): exact Check-screen payload with an empty amount field
st, resp = live("PATCH", f"/api/documents/{ID[CAR]}", {"amount": None, "date": None, "merchant": None, "accept": True})
rec("UI1", "UI contract", "LIVE", "Check-screen 'Looks right' payload with empty fields {amount:null, date:null, merchant:null, accept:true}",
    "record behaviour (the UI sends null for empty inputs)", f"HTTP {st} {resp.get('detail') if isinstance(resp, dict) and 'detail' in resp else 'accepted'}",
    "RECORDED", "Dev 1 + Dev 3", note="If 422, the Check screen cannot 'mark checked' a transaction document whose amount field is empty")
rec("G2", "Filesystem", "LIVE", "Live root and canary after all live steps", "unchanged", "unchanged" if fs_unchanged() else "CHANGED", pf(fs_unchanged()))
(OUT / "live" / "http_log.json").write_text(json.dumps(live_log, indent=2), encoding="utf-8")

# ================================================================ PART INPROCESS (mocked classifier)
from fastapi.testclient import TestClient  # noqa: E402
from app.main import app  # noqa: E402
from app.schemas import ClassificationRecord  # noqa: E402
from app.services import local_ai  # noqa: E402
from app.services.session_store import store  # noqa: E402

MOCK = [  # statement markers first (the card statement text also mentions SUNBEAM CAFE)
    ("HARBOR FEDERAL BANK", {"category": "other", "document_kind": "statement", "merchant": None, "date": None, "amount_text": None, "currency": None,
                             "evidence_quote": "Statement balance: PHP 5,391.06", "explanation": "MOCK statement"}),
    ("BAYSIDE OFFICE MART", {"category": "receipt", "document_kind": "receipt", "merchant": "BAYSIDE OFFICE MART", "date": "2026-09-05",
                             "amount_text": "PHP 1,520.00", "currency": "PHP", "evidence_quote": "AMOUNT DUE: PHP 1,520.00", "explanation": "MOCK realistic"}),
    ("SUNBEAM CAFE", {"category": "receipt", "document_kind": "receipt", "merchant": "SUNBEAM CAFE", "date": "2026-09-21", "amount_text": "PHP 683.20",
                      "currency": "PHP", "evidence_quote": "FINAL TOTAL: PHP 683.20", "explanation": "MOCK"}),
    ("PIXELFORGE", {"category": "invoice", "document_kind": "invoice", "merchant": "PIXELFORGE DESIGN STUDIO", "date": "2026-10-02",
                    "amount_text": "PHP 18,648.00", "currency": "PHP", "evidence_quote": "Total Amount Due: PHP 18,648.00", "explanation": "MOCK"}),
    ("CARABAO", {"category": "invoice", "document_kind": "invoice", "merchant": "CARABAO PAPER SUPPLY CO.", "date": "2026-09-18",
                 "amount_text": "PHP 3,470.00", "currency": "PHP", "evidence_quote": "TOTAL AMOUNT DUE: PHP 3,470.00", "explanation": "MOCK"}),
    ("Tibay Hardware", {"category": "receipt", "document_kind": "receipt", "merchant": "Tibay Hardware", "date": "2026-09-27", "amount_text": "2145.00",
                        "currency": "PHP", "evidence_quote": "grand_total,,,2145.00", "explanation": "MOCK"}),
]


def fake_classify(excerpt, **_kw):
    for marker, payload in MOCK:
        if marker in excerpt:
            return local_ai.ClassificationResult(classification=ClassificationRecord.model_validate(payload), elapsed_seconds=0.0)
    raise local_ai.LocalAIResponseError("MOCK: no fixed response")


real = local_ai.classify_excerpt
local_ai.classify_excerpt = fake_classify
mock_log: list[dict] = []
try:
    client = TestClient(app)

    def m(method, path, body=None):
        r = client.request(method, path, json=body)
        try:
            pl = r.json()
        except Exception:
            pl = r.text
        mock_log.append(redact({"request": {"method": method, "path": path, "body": body}, "response": {"status": r.status_code, "body": pl}}))
        return r.status_code, pl

    _, prog = m("POST", "/api/scan", {"root": str(MOCK_ROOT)})
    msid = prog["scan_id"]
    while prog["state"] == "running":
        time.sleep(0.2)
        _, prog = m("GET", f"/api/scans/{msid}/progress")
    _, ms = m("GET", f"/api/scans/{msid}")
    MID = {d["relative_path"]: d["file_id"] for d in ms["documents"]}
    session = store.get_scan(msid)
    bay = next(d for d in session.documents if d.relative_path == BAY)
    rec("M0", "DA-7 evidence", "INPROCESS mocked", "mocked Bayside (amount_text 'PHP 1,520.00') after the real validator",
        "needs_review, amount_conflict, amount null", f"status {bay.status}, flags {[f['code'] for f in bay.review_flags]}, amount {bay.classification.get('amount')!r}",
        pf(bay.status == "needs_review" and any(f["code"] == "amount_conflict" for f in bay.review_flags) and bay.classification.get("amount") is None))
    _, mp = m("GET", f"/api/scans/{msid}/plan")
    plan_id = mp["plan_id"]

    # ---- Stage 5: revision + snapshot unchanged on a rejected correction
    for tid, key, body in (("RV1", TIB, {"amount": "abc"}), ("RV2", TIB, {"currency": "XYZ"}), ("RV3", BAY, {"amount": "1520.00"}),
                           ("RV4", TIB, {"field_profile": "transaction"})):
        rev0 = session.plan_revision
        snap0 = copy.deepcopy(store.get_plan_snapshot(plan_id))
        doc0 = copy.deepcopy(next(d for d in session.documents if d.relative_path == key))
        st, resp = m("PATCH", f"/api/documents/{MID[key]}", body)
        doc1 = next(d for d in session.documents if d.relative_path == key)
        snap1 = store.get_plan_snapshot(plan_id)
        ok = (st == 422 and session.plan_revision == rev0 and snap1 == snap0 and doc1.classification == doc0.classification
              and doc1.review_flags == doc0.review_flags and doc1.status == doc0.status and doc1.user_corrected == doc0.user_corrected)
        rec(tid, "Stage 5", "INPROCESS mocked (store read directly)", f"rejected PATCH {key.rsplit('/', 1)[1]} {json.dumps(body)}",
            "422; plan_revision, plan snapshot, classification, flags, status, user_corrected unchanged",
            f"HTTP {st}; revision {rev0}->{session.plan_revision}; snapshot {'unchanged' if snap1 == snap0 else 'CHANGED'}; "
            f"record {'unchanged' if doc1.classification == doc0.classification and doc1.review_flags == doc0.review_flags and doc1.status == doc0.status else 'CHANGED'}",
            pf(ok))
    snapshot = store.get_plan_snapshot(plan_id)
    rec("RV5", "Stage 5", "INPROCESS", "snapshot still current after rejected corrections", "snapshot.session_revision == session.plan_revision",
        f"{snapshot.session_revision} vs {session.plan_revision}", pf(snapshot.session_revision == session.plan_revision))
    st, _ = m("PATCH", f"/api/documents/{MID[SUN]}", {"amount": "683.20"})
    rec("RV6", "Stage 5", "INPROCESS", "accepted (valid) correction makes the snapshot stale", "200; revision bumped; snapshot.session_revision != plan_revision (approval would get 409 stale)",
        f"HTTP {st}; snapshot {snapshot.session_revision} vs revision {session.plan_revision}", pf(st == 200 and snapshot.session_revision != session.plan_revision))

    # ---- DA-7: accept-as-is on the mocked ambiguous receipt (deterministic revival check)
    st, resp = m("PATCH", f"/api/documents/{MID[BAY]}", {"accept": True})
    _, mp2 = m("GET", f"/api/scans/{msid}/plan")
    row = next((r for r in mp2["report_rows"] if r["source_filename"] == BAY), None)
    rec("M1", "DA-7", "INPROCESS mocked", "Bayside accept-as-is {accept: true} with a parseable but rejected amount_text 'PHP 1,520.00'",
        "no accepted row; amount not revived from raw text",
        f"HTTP {st}; flags after {resp.get('review_flags')}; stored amount {bay.classification.get('amount')!r}; row {row and (row['status'], row['amount'])}; totals {mp2['totals']}",
        pf(not (row and row["status"] == "accepted")), "Dev 1",
        note="accept:true clears review_flags, so the new flag-based gate no longer applies; _build_plan then falls back to _parse_amount(amount_text)" if row and row["status"] == "accepted" else "")
    rec("M2", "Filesystem", "INPROCESS", "mock root and canary", "unchanged", "unchanged" if fs_unchanged() else "CHANGED", pf(fs_unchanged()))
finally:
    local_ai.classify_excerpt = real
(OUT / "inprocess_mock_http_log.json").write_text(json.dumps(mock_log, indent=2), encoding="utf-8")
(OUT / "results.json").write_text(json.dumps(results, indent=2), encoding="utf-8")
counts = {}
for r in results:
    counts[r["status"]] = counts.get(r["status"], 0) + 1
print(f"\n{counts}  live scan {sid}  (no approve/undo)")
