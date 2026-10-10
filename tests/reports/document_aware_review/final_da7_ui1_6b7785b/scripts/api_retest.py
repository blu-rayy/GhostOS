"""Final DA-7 + UI1 integration retest on 6b7785b (Developer 4 / QA) - API and in-process part.
NON-DESTRUCTIVE: no approve, no undo, no file move.

Creates the fresh base (API root, UI root, in-process root, canary). The UI root is only scanned
later by scripts/ui_retest.mjs through the real frontend.

Part LIVE       real backend 127.0.0.1:8000 (restarted on 6b7785b) + live model, root API-L (prefix fa/).
Part INPROCESS  production app via TestClient, MOCKED classifier, own store, root M (prefix fm/).

    backend\\.venv\\Scripts\\python.exe -B tests\\reports\\document_aware_review\\final_da7_ui1_6b7785b\\scripts\\api_retest.py
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
OUT = REPO / "tests" / "reports" / "document_aware_review" / "final_da7_ui1_6b7785b"
BASE = Path.home() / "AppData" / "Local" / "Temp" / "ghostos-final-da7ui1"
ROOTS = {"API-L": "fa", "UI-L": "fu", "M": "fm", "M2": "fn"}  # distinct prefixes: D1 matches file_id across scans
CANARY = BASE / "outside-canary" / "canary.txt"
API = "http://127.0.0.1:8000"
sys.path.insert(0, str(REPO / "backend"))

# Fictional synthetic receipt with no amount printed anywhere (written by this script, not a fixture).
NOTE_TEXT = ("KANTO MARKET STALL 14\nCash note - no official receipt issued\nDate: 2026-09-12\n"
             "Items: rice (2 bags), cooking oil (1 bottle)\nAmount not written on this note\n")
FILES = {  # suffix -> (fixture or None, source-supported authoritative total or None)
    "receipts/bayside-office-mart.pdf": ("receipts/bayside-office-mart.pdf", None),
    "invoices/INV-1043_Pixelforge_Studio.pdf": ("invoices/INV-1043_Pixelforge_Studio.pdf", "18648.00"),
    "receipts/sunbeam-cafe-receipt.pdf": ("receipts/sunbeam-cafe-receipt.pdf", "683.20"),
    "receipts/kanto-stall-cash-note.txt": (None, None),
}
results: list[dict] = []
live_log: list[dict] = []


def k(prefix, suffix): return f"{prefix}/{suffix}"


BAY, PIX, SUN, NOTE = (k("fa", s) for s in FILES)
MBAY, MPIX, MSUN, MNOTE = (k("fm", s) for s in FILES)
NBAY = k("fn", "receipts/bayside-office-mart.pdf")


def sha(p): return hashlib.sha256(p.read_bytes()).hexdigest()


def snap(root):
    return {p.relative_to(root).as_posix(): {"sha256": sha(p), "size": p.stat().st_size} for p in sorted(root.rglob("*")) if p.is_file()}


def redact(o):
    t = json.dumps(o, default=str)
    for f in (str(BASE), str(BASE).replace("\\", "/")):
        t = t.replace(json.dumps(f)[1:-1], "<TEST_BASE>")
    return json.loads(t)


def rec(tid, method, check, expected, actual, status, owner="Dev 1", note=""):
    results.append(redact({"id": tid, "method": method, "check": check, "expected": expected, "actual": actual, "status": status, "owner": owner, "note": note}))
    print(f"[{status}] {tid} ({method}) {check}\n      expected: {expected}\n      actual:   {actual}" + (f"\n      note: {note}" if note else ""))


def pf(ok): return "PASS" if ok else "FAIL"


def write(name, obj):
    (OUT / name).parent.mkdir(parents=True, exist_ok=True)
    (OUT / name).write_text(json.dumps(redact(obj), indent=2, default=str), encoding="utf-8")


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


def view(d):
    c = d.get("classification") or {}
    return {"status": d["status"], "user_corrected": d["user_corrected"], "review_disposition": d.get("review_disposition"),
            "category": c.get("category"), "document_kind": c.get("document_kind"), "field_profile": c.get("field_profile"),
            "merchant": c.get("merchant"), "date": c.get("date"), "amount": c.get("amount"), "amount_text": c.get("amount_text"),
            "currency": c.get("currency"), "evidence_quote": c.get("evidence_quote"), "evidence_verified": c.get("evidence_verified"),
            "flags": [f["code"] for f in d["review_flags"]]}


def row_of(plan, key): return [r for r in plan["report_rows"] if r["source_filename"] == key]


def detail(resp): return resp.get("detail") if isinstance(resp, dict) and "detail" in resp else ("ok" if isinstance(resp, dict) else resp)


# ================================================================ setup
for p in (BASE, OUT / "setup"):
    if p.exists():
        sys.exit(f"STOP: {p} exists")
BASE.mkdir()
CANARY.parent.mkdir()
CANARY.write_text("final DA-7 + UI1 retest outside-root canary\n", encoding="utf-8")
for root_name, prefix in ROOTS.items():
    for suffix, (src, _a) in FILES.items():
        dst = BASE / root_name / prefix / suffix
        dst.parent.mkdir(parents=True, exist_ok=True)
        if src:
            shutil.copy2(FIX / src, dst)
        else:
            dst.write_bytes(NOTE_TEXT.encode("utf-8"))
manifest = {"commit": subprocess.run(["git", "rev-parse", "HEAD"], cwd=REPO, capture_output=True, text=True).stdout.strip(),
            "created_at": datetime.now(timezone.utc).isoformat(), "canary_sha256": sha(CANARY),
            "authoritative_totals": {s: v[1] for s, v in FILES.items()}, "fixture_source": {s: v[0] or "synthetic (written by script)" for s, v in FILES.items()},
            "roots": {r: snap(BASE / r) for r in ROOTS}}
write("setup/manifest.json", manifest)
for r in ROOTS:
    for rel, m in manifest["roots"][r].items():
        print(f"  {r:6} {rel:46} {m['size']:>6} B  {m['sha256']}")


def fs_unchanged():
    return all(snap(BASE / r) == manifest["roots"][r] for r in ROOTS) and sha(CANARY) == manifest["canary_sha256"]


# ================================================================ LIVE
_, status = live("GET", "/api/status")
write("live/status.json", status)
print(f"\nLIVE model {status.get('model_name')} loaded {status.get('model_loaded')} external_requests {status.get('external_requests')}")
_, prog = live("POST", "/api/scan", {"root": str(BASE / "API-L")})
sid = prog["scan_id"]
while prog["state"] == "running":
    time.sleep(1)
    _, prog = live("GET", f"/api/scans/{sid}/progress")
_, scan0 = live("GET", f"/api/scans/{sid}")
write("live/scan_initial.json", scan0)
ID = {d["relative_path"]: d["file_id"] for d in scan0["documents"]}
init = {d["relative_path"]: view(d) for d in scan0["documents"]}
write("live/state_initial.json", init)
for key, v in init.items():
    print(f"  {key:46} {v}")
_, plan0 = live("GET", f"/api/scans/{sid}/plan")
write("live/plan_initial.json", plan0)
print()


def ldoc(key):
    _, s = live("GET", f"/api/scans/{sid}")
    return next(d for d in s["documents"] if d["file_id"] == ID[key])


def lplan():
    _, p = live("GET", f"/api/scans/{sid}/plan")
    return p


def attempt(tid, key, body, label):
    d0, p0 = ldoc(key), lplan()
    st, resp = live("PATCH", f"/api/documents/{ID[key]}", body)
    d1, p1 = ldoc(key), lplan()
    write(f"live/patch_{tid}.json", {"request": body, "status": st, "response": resp, "doc_before": d0, "doc_after": d1, "plan_before": p0, "plan_after": p1})
    return st, resp, d0, d1, p0, p1


# ---- Stage 3: Bayside
b = init[BAY]
rec("L-B1", "LIVE", "Bayside after scan: conflicting amount untrusted", "needs_review; amount_conflict; canonical amount null",
    {x: b[x] for x in ("status", "flags", "amount", "amount_text", "evidence_quote", "evidence_verified")},
    pf(b["status"] == "needs_review" and "amount_conflict" in b["flags"] and b["amount"] is None))
st, resp, d0, d1, p0, p1 = attempt("B2", BAY, {"accept": True}, "Bayside accept")
rec("L-B2", "LIVE", "Bayside PATCH {accept: true}", "422 (amount_text non-empty -> full guard); record and plan unchanged",
    f"HTTP {st} {detail(resp)}; record {'unchanged' if d1 == d0 else view(d1)}; plan {'unchanged' if p1 == p0 else 'CHANGED'}",
    pf(st == 422 and d1 == d0 and p1 == p0),
    note=f"live amount_text {b['amount_text']!r}: the contract only routes to the guard when amount_text is non-empty")
st, resp, d0, d1, p0, p1 = attempt("B3", BAY, {"amount": "1520.00", "accept": True}, "Bayside amount due")
rec("L-B3", "LIVE", "Bayside {amount: 1520.00, accept: true} (ambiguous source)", "422; record and plan unchanged",
    f"HTTP {st} {detail(resp)}; record {'unchanged' if d1 == d0 else 'CHANGED'}; plan {'unchanged' if p1 == p0 else 'CHANGED'}", pf(st == 422 and d1 == d0 and p1 == p0))

# ---- Stage 4/5 controls: valid corrections
for tid, key in (("C1", PIX), ("C2", SUN)):
    exp = FILES[key.split("/", 1)[1]][1]
    body = {"amount": exp, "accept": True}
    st, resp, d0, d1, p0, p1 = attempt(tid, key, body, "valid")
    a = view(d1)
    rec(f"L-{tid}", "LIVE", f"{key.rsplit('/', 1)[1]} {json.dumps(body)} (source-supported authoritative total)", f"200; amount {exp}; ok; disposition filed; no flags",
        f"HTTP {st}; amount {a['amount']}; {a['status']}; {a['review_disposition']}; flags {a['flags']}; evidence {a['evidence_quote']!r}",
        pf(st == 200 and a["amount"] == exp and a["status"] == "ok" and a["review_disposition"] == "filed" and not a["flags"]))
# invalid corrections stay atomic
for tid, key, body in (("V1", SUN, {"amount": "610.00", "accept": True}), ("V2", PIX, {"amount": "18500.00"}), ("V3", SUN, {"currency": "XYZ"}),
                       ("V4", SUN, {"amount": None, "accept": True}), ("V5", SUN, {"amount": "", "accept": True})):
    st, resp, d0, d1, p0, p1 = attempt(tid, key, body, "invalid")
    rec(f"L-{tid}", "LIVE", f"invalid {key.rsplit('/', 1)[1]} {json.dumps(body)}", "422; record and plan unchanged",
        f"HTTP {st} {detail(resp)}; record {'unchanged' if d1 == d0 else 'CHANGED'}; plan {'unchanged' if p1 == p0 else 'CHANGED'}", pf(st == 422 and d1 == d0 and p1 == p0))

# ---- Stage 5: filed-uncounted on the genuinely amount-less note (live model output decides the path)
n = init[NOTE]
rec("L-N1", "LIVE", "Amount-less cash note after scan", "transaction profile; amount null; amount_text empty; missing_amount",
    {x: n[x] for x in ("status", "category", "field_profile", "flags", "amount", "amount_text", "currency", "evidence_quote")},
    pf(n["field_profile"] == "transaction" and n["amount"] is None and not (n["amount_text"] or "").strip() and "missing_amount" in n["flags"]), "Dev 2",
    note="live model output; FAIL here means the precondition for the live filed-uncounted path was not produced")
if n["field_profile"] == "transaction" and n["amount"] is None and not (n["amount_text"] or "").strip():
    st, resp, d0, d1, p0, p1 = attempt("N2", NOTE, {"accept": True}, "filed uncounted")
    a = view(d1)
    rows = row_of(p1, NOTE)
    rec("L-N2", "LIVE", "Cash note {accept: true}", "200; disposition filed_uncounted; status ok; amount null; row not accepted; not in totals",
        f"HTTP {st}; {a['review_disposition']}; {a['status']}; amount {a['amount']}; flags {a['flags']}; rows {[(r['status'], r['amount']) for r in rows]}; totals {p1['totals']}",
        pf(st == 200 and a["review_disposition"] == "filed_uncounted" and a["status"] == "ok" and a["amount"] is None and all(r["status"] != "accepted" and r["amount"] is None for r in rows)))
    st, resp, d0, d1, p0, p1 = attempt("N3", NOTE, {"amount": "500.00", "accept": True}, "invent amount")
    rec("L-N3", "LIVE", "Cash note invented amount {amount: 500.00} after filed-uncounted", "422; record and plan unchanged",
        f"HTTP {st} {detail(resp)}; record {'unchanged' if d1 == d0 else 'CHANGED'}; plan {'unchanged' if p1 == p0 else 'CHANGED'}", pf(st == 422 and d1 == d0 and p1 == p0))
else:
    rec("L-N2", "LIVE", "Cash note {accept: true} (filed-uncounted)", "200 filed_uncounted", "not sent: live precondition not met (see L-N1)", "BLOCKED", "Dev 2")

# ---- report rows, CSV and totals
from app.services.report import render_report  # noqa: E402
from app.services.session_store import ReportRow  # noqa: E402

final = lplan()
write("live/plan_final.json", final)
_, pfinal = live("GET", f"/api/scans/{sid}/plan?mode=partial")
write("live/plan_final_partial.json", pfinal)
csv_text = render_report([ReportRow(**r) for r in final["report_rows"]])
(OUT / "live" / "prepared_report.csv").write_text(csv_text, encoding="utf-8", newline="")
csv_rows = [r for r in list(csv.reader(io.StringIO(csv_text.lstrip("﻿"), newline="")))[1:] if r]
csv_tot = {}
for r in csv_rows:
    csv_tot[r[5]] = csv_tot.get(r[5], Decimal(0)) + Decimal(r[4])
indep = {"PHP": Decimal("18648.00") + Decimal("683.20")}
rec("L-R1", "LIVE + production render_report (prepared, not committed)", "CSV rows", f"exactly Pixelforge 18648.00 and Sunbeam 683.20",
    [(r[0], r[4], r[5]) for r in csv_rows], pf(sorted((r[0], r[4]) for r in csv_rows) == sorted([(PIX, "18648.00"), (SUN, "683.20")])))
rec("L-R2", "LIVE", "Totals: independent 18648.00 + 683.20 = CSV = plan (blocking and partial)", {kk: str(v) for kk, v in indep.items()},
    {"csv": {kk: str(v) for kk, v in csv_tot.items()}, "plan": final["totals"], "partial": pfinal["totals"]},
    pf(csv_tot == indep and {t["currency"]: Decimal(t["amount"]) for t in final["totals"]} == indep
       and {t["currency"]: Decimal(t["amount"]) for t in pfinal["totals"]} == indep))
rec("L-R3", "LIVE", "PHP 1,520.00 (and 1,250.00) absent from rows and totals; Bayside not accepted", "absent",
    {"bayside_rows": [(r["status"], r["amount"]) for r in row_of(final, BAY)], "amounts_in_rows": sorted({r["amount"] for r in final["report_rows"] if r["amount"]})},
    pf(all(r["status"] != "accepted" and r["amount"] is None for r in row_of(final, BAY))
       and not any(r["amount"] in ("1520.00", "1250.00") for r in final["report_rows"])))
rec("L-R4", "LIVE", "Blocking count / destinations", "Bayside still blocking; destinations from backend map",
    {"blocking": final["blocking_review_count"], "ops": {o["original_relative_path"]: o["destination_relative_path"] for o in final["operations"]}},
    pf(final["blocking_review_count"] >= 1))
rec("L-G1", "LIVE", "All roots and canary after live part", "unchanged", "unchanged" if fs_unchanged() else "CHANGED", pf(fs_unchanged()))
(OUT / "live" / "http_log.json").write_text(json.dumps(live_log, indent=2), encoding="utf-8")

# ================================================================ INPROCESS (mocked classifier)
from fastapi.testclient import TestClient  # noqa: E402
from app.main import app  # noqa: E402
from app.schemas import ClassificationRecord  # noqa: E402
from app.services import local_ai  # noqa: E402
from app.services.session_store import store  # noqa: E402

MOCK = {
    "BAYSIDE OFFICE MART": {"category": "receipt", "document_kind": "receipt", "merchant": "BAYSIDE OFFICE MART", "date": "2026-09-05",
                            "amount_text": "PHP 1,520.00", "currency": "PHP", "evidence_quote": "AMOUNT DUE: PHP 1,520.00", "explanation": "MOCK"},
    "SUNBEAM CAFE": {"category": "receipt", "document_kind": "receipt", "merchant": "SUNBEAM CAFE", "date": "2026-09-21", "amount_text": "PHP 683.20",
                     "currency": "PHP", "evidence_quote": "FINAL TOTAL: PHP 683.20", "explanation": "MOCK"},
    "PIXELFORGE": {"category": "invoice", "document_kind": "invoice", "merchant": "PIXELFORGE DESIGN STUDIO", "date": "2026-10-02",
                   "amount_text": "PHP 18,648.00", "currency": "PHP", "evidence_quote": "Total Amount Due: PHP 18,648.00", "explanation": "MOCK"},
    "KANTO MARKET": {"category": "receipt", "document_kind": "receipt", "merchant": "KANTO MARKET STALL 14", "date": "2026-09-12",
                     "amount_text": None, "currency": None, "evidence_quote": "Date: 2026-09-12", "explanation": "MOCK no amount"},
}
mode = {"bayside_amount_text": "PHP 1,520.00"}


def fake_classify(excerpt, **_kw):
    for marker, payload in MOCK.items():
        if marker in excerpt:
            p = dict(payload)
            if marker == "BAYSIDE OFFICE MART":
                p["amount_text"] = mode["bayside_amount_text"]
            return local_ai.ClassificationResult(classification=ClassificationRecord.model_validate(p), elapsed_seconds=0.0)
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

    def mscan(root):
        _, pr = m("POST", "/api/scan", {"root": str(BASE / root)})
        s = pr["scan_id"]
        while pr["state"] == "running":
            time.sleep(0.2)
            _, pr = m("GET", f"/api/scans/{s}/progress")
        return s

    def mdoc(sess, key): return next(d for d in sess.documents if d.relative_path == key)

    def guarded(tid, sess, plan_id, key, body, label, expect=422):
        d = mdoc(sess, key)
        rev0, snap0, d0 = sess.plan_revision, copy.deepcopy(store.get_plan_snapshot(plan_id)), copy.deepcopy(d)
        st, resp = m("PATCH", f"/api/documents/{d.file_id}", body)
        same = (d.classification == d0.classification and d.review_flags == d0.review_flags and d.status == d0.status
                and d.user_corrected == d0.user_corrected and d.review_disposition == d0.review_disposition)
        snap_same = store.get_plan_snapshot(plan_id) == snap0
        rec(tid, "INPROCESS mocked (store read directly)", f"{label} {json.dumps(body)}", "422; revision, snapshot and record unchanged",
            f"HTTP {st} {detail(resp)}; revision {rev0}->{sess.plan_revision}; snapshot {'unchanged' if snap_same else 'CHANGED'}; record {'unchanged' if same else 'CHANGED'}",
            pf(st == expect and sess.plan_revision == rev0 and snap_same and same))

    # ---- session 1: Bayside with parseable rejected amount_text (DA-7 revival case)
    s1 = mscan("M")
    sess1 = store.get_scan(s1)
    _, mp = m("GET", f"/api/scans/{s1}/plan")
    pid1 = mp["plan_id"]
    bd = mdoc(sess1, MBAY)
    rec("M-B1", "INPROCESS mocked", "Bayside amount_text 'PHP 1,520.00' after real validator", "needs_review; amount_conflict; amount null",
        f"{bd.status}; {[f['code'] for f in bd.review_flags]}; amount {bd.classification.get('amount')!r}",
        pf(bd.status == "needs_review" and any(f["code"] == "amount_conflict" for f in bd.review_flags) and bd.classification.get("amount") is None))
    guarded("M-B2", sess1, pid1, MBAY, {"accept": True}, "Bayside accept")
    guarded("M-B3", sess1, pid1, MBAY, {"amount": "1520.00", "accept": True}, "Bayside amount due")
    guarded("M-V1", sess1, pid1, MSUN, {"amount": "610.00", "accept": True}, "Sunbeam subtotal")
    guarded("M-V2", sess1, pid1, MSUN, {"currency": "XYZ"}, "Sunbeam bad currency")
    guarded("M-V3", sess1, pid1, MSUN, {"amount": None, "accept": True}, "Sunbeam null amount")
    nd = mdoc(sess1, MNOTE)
    rec("M-N1", "INPROCESS mocked", "Cash note (amount_text null) after real validator", "needs_review; missing_amount; amount null",
        f"{nd.status}; {[f['code'] for f in nd.review_flags]}; amount {nd.classification.get('amount')!r}",
        pf(nd.status == "needs_review" and any(f["code"] == "missing_amount" for f in nd.review_flags) and nd.classification.get("amount") is None))
    flags_before = [f["code"] for f in nd.review_flags]
    r0 = sess1.plan_revision
    st, resp = m("PATCH", f"/api/documents/{nd.file_id}", {"accept": True})
    _, mp2 = m("GET", f"/api/scans/{s1}/plan")
    _, mp2p = m("GET", f"/api/scans/{s1}/plan?mode=partial")
    nrow = row_of(mp2, MNOTE)
    rec("M-N2", "INPROCESS mocked", "Cash note {accept: true} -> filed-uncounted",
        "200; filed_uncounted; ok; amount null; revision +1; row not accepted; not in totals; not blocking",
        f"HTTP {st}; {nd.review_disposition}; {nd.status}; amount {nd.classification.get('amount')!r}; flags {flags_before}->{[f['code'] for f in nd.review_flags]}; "
        f"revision {r0}->{sess1.plan_revision}; row {[(r['status'], r['amount']) for r in nrow]}; totals {mp2['totals']}; blocking {mp2['blocking_review_count']}; "
        f"dest {[o['destination_relative_path'] for o in mp2['operations'] if o['original_relative_path'] == MNOTE]}",
        pf(st == 200 and nd.review_disposition == "filed_uncounted" and nd.status == "ok" and nd.classification.get("amount") is None
           and sess1.plan_revision == r0 + 1 and all(r["status"] != "accepted" and r["amount"] is None for r in nrow)
           and not any(r["source_filename"] == MNOTE for r in mp2p["report_rows"] if r["status"] == "accepted")))
    _, mp_now = m("GET", f"/api/scans/{s1}/plan")
    guarded("M-N3", sess1, mp_now["plan_id"], MNOTE, {"amount": "500.00", "accept": True}, "Cash note invented amount after filed-uncounted")
    pd, sd = mdoc(sess1, MPIX), mdoc(sess1, MSUN)
    st1, _ = m("PATCH", f"/api/documents/{pd.file_id}", {"amount": "18648.00", "accept": True})
    st2, _ = m("PATCH", f"/api/documents/{sd.file_id}", {"amount": "683.20", "accept": True})
    _, mp3 = m("GET", f"/api/scans/{s1}/plan")
    write("inprocess/session1_plan_final.json", mp3)
    acc = sorted((r["source_filename"], r["amount"]) for r in mp3["report_rows"] if r["status"] == "accepted")
    rec("M-C1", "INPROCESS mocked", "Valid Pixelforge/Sunbeam corrections; accepted rows and totals", "200/200; rows Pixelforge 18648.00 + Sunbeam 683.20 only; PHP 19331.20",
        f"HTTP {st1}/{st2}; accepted {acc}; totals {mp3['totals']}",
        pf(st1 == 200 and st2 == 200 and acc == sorted([(MPIX, "18648.00"), (MSUN, "683.20")])
           and [(t["currency"], t["amount"]) for t in mp3["totals"]] == [("PHP", "19331.20")]))

    # ---- session 2: Bayside where the model returned NO amount_text (conflicting source, empty amount)
    mode["bayside_amount_text"] = None
    s2 = mscan("M2")
    sess2 = store.get_scan(s2)
    b2 = mdoc(sess2, NBAY)
    fl2 = [f["code"] for f in b2.review_flags]
    rec("M-E1", "INPROCESS mocked", "Bayside with amount_text null (model gave no amount) after real validator", "needs_review; amount_conflict present",
        f"{b2.status}; flags {fl2}; amount {b2.classification.get('amount')!r}", pf(b2.status == "needs_review" and "amount_conflict" in fl2))
    r0 = sess2.plan_revision
    st, resp = m("PATCH", f"/api/documents/{b2.file_id}", {"accept": True})
    _, mp4 = m("GET", f"/api/scans/{s2}/plan")
    write("inprocess/session2_bayside_no_amount_text.json", {"flags_before": fl2, "status": st, "response": resp, "plan_after": mp4})
    brow = row_of(mp4, NBAY)
    rec("M-E2", "INPROCESS mocked", "Bayside (conflict, empty amount_text) {accept: true}: amount never counted",
        "no accepted row; amount null; nothing added to totals", f"HTTP {st}; row {[(r['status'], r['amount']) for r in brow]}; totals {mp4['totals']}",
        pf(all(r["status"] != "accepted" and r["amount"] is None for r in brow) and not any(r["amount"] in ("1520.00", "1250.00") for r in mp4["report_rows"])))
    rec("M-E3", "INPROCESS mocked", "Bayside (conflict, empty amount_text) {accept: true}: conflict guard",
        "422 and amount_conflict kept (commit message: 'Conflicting/unsupported amounts keep the full guard')",
        f"HTTP {st}; disposition {b2.review_disposition}; status {b2.status}; flags {fl2}->{[f['code'] for f in b2.review_flags]}",
        pf(st == 422 and "amount_conflict" in [f["code"] for f in b2.review_flags]), "Dev 1",
        note="filed-uncounted eligibility checks only that amount/amount_text are empty, not which flags exist; the UI blocks this path (AMOUNT_FLAGS)")
    rec("M-G1", "INPROCESS", "All roots and canary after in-process part", "unchanged", "unchanged" if fs_unchanged() else "CHANGED", pf(fs_unchanged()))
finally:
    local_ai.classify_excerpt = real

(OUT / "inprocess" / "http_log.json").parent.mkdir(parents=True, exist_ok=True)
(OUT / "inprocess" / "http_log.json").write_text(json.dumps(mock_log, indent=2, default=str), encoding="utf-8")
(OUT / "results_api.json").write_text(json.dumps(results, indent=2, default=str), encoding="utf-8")
counts = {}
for r in results:
    counts[r["status"]] = counts.get(r["status"], 0) + 1
print(f"\n{counts}  live scan {sid}  (no approve/undo)")
