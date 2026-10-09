"""DA-7 fresh regression retest on 0641adb (Developer 4 / QA). NON-DESTRUCTIVE: no approve, no undo, no file move.

Part LIVE       real backend 127.0.0.1:8000 (restarted on 0641adb, dedicated to this test) + live local model, root D7-L.
Part INPROCESS  production FastAPI app via TestClient with a MOCKED classifier and its own store, root D7-M.
                Used to read plan_revision / plan snapshot directly and for a deterministic Bayside whose
                rejected amount_text ("PHP 1,520.00") is parseable, i.e. the exact revival case.

    backend\\.venv\\Scripts\\python.exe -B tests\\reports\\document_aware_review\\da7_retest_0641adb\\scripts\\da7_retest.py
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
RUN = __import__("os").environ.get("DA7_RUN", "")  # "" = run 1, "2" = run 2 (fresh base/prefix to avoid D1 file_id reuse)
OUT = REPO / "tests" / "reports" / "document_aware_review" / "da7_retest_0641adb" / (f"run{RUN}" if RUN else "")
BASE = Path.home() / "AppData" / "Local" / "Temp" / ("ghostos-da7" + (f"-run{RUN}" if RUN else ""))
PFX = "d7" + ("bcdefg"[int(RUN) - 2] if RUN else "")
LIVE_ROOT, MOCK_ROOT = BASE / "D7-L", BASE / "D7-M"
CANARY = BASE / "outside-canary" / "canary.txt"
API = "http://127.0.0.1:8000"
sys.path.insert(0, str(REPO / "backend"))

DOCS = {  # relative path -> (fixture, source-supported authoritative total or None)
    f"{PFX}/receipts/bayside-office-mart.pdf": ("receipts/bayside-office-mart.pdf", None),
    f"{PFX}/invoices/INV-1043_Pixelforge_Studio.pdf": ("invoices/INV-1043_Pixelforge_Studio.pdf", "18648.00"),
    f"{PFX}/receipts/sunbeam-cafe-receipt.pdf": ("receipts/sunbeam-cafe-receipt.pdf", "683.20"),
}
BAY, PIX, SUN = list(DOCS)
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


def rec(tid, method, check, expected, actual, status, owner="Dev 1", note=""):
    results.append({"id": tid, "method": method, "check": check, "expected": expected, "actual": actual, "status": status, "owner": owner, "note": note})
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


def view(d):
    c = d.get("classification") or {}
    return {"status": d["status"], "user_corrected": d["user_corrected"], "review_disposition": d.get("review_disposition"),
            "category": c.get("category"), "document_kind": c.get("document_kind"), "field_profile": c.get("field_profile"),
            "merchant": c.get("merchant"), "date": c.get("date"), "amount": c.get("amount"), "amount_text": c.get("amount_text"),
            "currency": c.get("currency"), "evidence_quote": c.get("evidence_quote"), "evidence_verified": c.get("evidence_verified"),
            "flags": [f["code"] for f in d["review_flags"]]}


def row_of(plan, key): return [r for r in plan["report_rows"] if r["source_filename"] == key]


# ================================================================ Stage 2: setup
for p in (BASE, OUT / "setup"):
    if p.exists():
        sys.exit(f"STOP: {p} exists")
BASE.mkdir()
CANARY.parent.mkdir()
CANARY.write_text("DA-7 fresh retest outside-root canary\n", encoding="utf-8")
for root in (LIVE_ROOT, MOCK_ROOT):
    root.mkdir()
    for rel, (src, _a) in DOCS.items():
        (root / rel).parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(FIX / src, root / rel)
manifest = {"commit": subprocess.run(["git", "rev-parse", "HEAD"], cwd=REPO, capture_output=True, text=True).stdout.strip(),
            "created_at": datetime.now(timezone.utc).isoformat(), "canary_sha256": sha(CANARY),
            "authoritative_totals": {k: v[1] for k, v in DOCS.items()}, "fixture_source": {k: v[0] for k, v in DOCS.items()},
            "roots": {"D7-L": snap(LIVE_ROOT), "D7-M": snap(MOCK_ROOT)}}
write("setup/manifest.json", manifest)
for rel, m in manifest["roots"]["D7-L"].items():
    print(f"  {rel:46} {m['size']:>6} B  {m['sha256']}")


def fs_unchanged():
    return snap(LIVE_ROOT) == manifest["roots"]["D7-L"] and snap(MOCK_ROOT) == manifest["roots"]["D7-M"] and sha(CANARY) == manifest["canary_sha256"]


# ================================================================ LIVE scan
_, status = live("GET", "/api/status")
print(f"\nLIVE model {status.get('model_name')} external_requests {status.get('external_requests')}")
_, prog = live("POST", "/api/scan", {"root": str(LIVE_ROOT)})
sid = prog["scan_id"]
while prog["state"] == "running":
    time.sleep(1)
    _, prog = live("GET", f"/api/scans/{sid}/progress")
_, scan0 = live("GET", f"/api/scans/{sid}")
write("live/scan_initial.json", scan0)
ID = {d["relative_path"]: d["file_id"] for d in scan0["documents"]}
init = {d["relative_path"]: view(d) for d in scan0["documents"]}
write("live/state_initial.json", init)
for k, v in init.items():
    print(f"  {k:46} {v}")
_, plan0 = live("GET", f"/api/scans/{sid}/plan")
write("live/plan_initial.json", plan0)
print()


def ldoc(k):
    _, s = live("GET", f"/api/scans/{sid}")
    return next(d for d in s["documents"] if d["file_id"] == ID[k])


def lplan():
    _, p = live("GET", f"/api/scans/{sid}/plan")
    return p


# ================================================================ Stage 3: Bayside (live)
b = init[BAY]
rec("B1", "LIVE", "Bayside classification and flags after scan", "needs_review; amount_conflict; canonical amount null",
    {k: b[k] for k in ("status", "flags", "amount", "amount_text", "evidence_quote", "evidence_verified", "document_kind", "field_profile")},
    pf(b["status"] == "needs_review" and "amount_conflict" in b["flags"] and b["amount"] is None))
r0 = row_of(plan0, BAY)
rec("B2", "LIVE", "Bayside initial plan/report eligibility", "one row, status needs_review, amount null; not in totals",
    {"rows": [(r["status"], r["amount"]) for r in r0], "totals": plan0["totals"]},
    pf(len(r0) == 1 and r0[0]["status"] != "accepted" and r0[0]["amount"] is None))
bdoc0, bplan0 = ldoc(BAY), lplan()
st, resp = live("PATCH", f"/api/documents/{ID[BAY]}", {"accept": True})
bdoc1, bplan1 = ldoc(BAY), lplan()
write("live/bayside_accept.json", {"request": {"accept": True}, "status": st, "response": resp, "doc_before": bdoc0, "doc_after": bdoc1,
                                   "plan_before": bplan0, "plan_after": bplan1})
rec("B3", "LIVE", "Bayside PATCH {accept: true}", "rejected (422); amount conflict not cleared",
    f"HTTP {st} {resp.get('detail') if isinstance(resp, dict) and 'detail' in resp else view(resp) if isinstance(resp, dict) else resp}", pf(st == 422))
rec("B4", "LIVE", "Bayside record unchanged after rejected accept", "classification, flags, status, user_corrected, disposition identical",
    "unchanged" if bdoc1 == bdoc0 else {"before": view(bdoc0), "after": view(bdoc1)}, pf(bdoc1 == bdoc0))
rec("B5", "LIVE", "Fresh plan after rejected accept", "identical to the plan before; Bayside row not accepted, amount null",
    {"plan_unchanged": bplan1 == bplan0, "bayside_rows": [(r["status"], r["amount"]) for r in row_of(bplan1, BAY)], "totals": bplan1["totals"]},
    pf(bplan1 == bplan0 and all(r["status"] != "accepted" and r["amount"] is None for r in row_of(bplan1, BAY))))

# ================================================================ Stage 4: valid controls (live)
corrections = {}
for tid, key in (("C1", PIX), ("C2", SUN)):
    exp = DOCS[key][1]
    v = init[key]
    body = {"amount": exp, "accept": True}
    st, resp = live("PATCH", f"/api/documents/{ID[key]}", body)
    after = view(ldoc(key))
    corrections[key] = {"request": body, "status": st, "response": resp, "state_before": v, "state_after": after}
    rec(tid, "LIVE", f"{key.rsplit('/', 1)[1]} correction {json.dumps(body)} (source-supported authoritative total)",
        f"HTTP 200; amount {exp}; status ok; no flags; evidence verified",
        f"HTTP {st}; amount {after['amount']}; status {after['status']}; flags {after['flags']}; evidence {after['evidence_quote']!r} verified={after['evidence_verified']}"
        f"; scan-time amount {v['amount']!r} flags {v['flags']}",
        pf(st == 200 and after["amount"] == exp and after["status"] == "ok" and not after["flags"]),
        "Dev 1" if st != 200 else "", note="" if v["status"] == "ok" else f"scan-time status {v['status']} (model output; Dev 2)")
write("live/valid_corrections.json", corrections)

final = lplan()
write("live/plan_final.json", final)
for tid, key in (("C3", PIX), ("C4", SUN)):
    rows = row_of(final, key)
    rec(tid, "LIVE", f"{key.rsplit('/', 1)[1]} report row", f"exactly one accepted row, amount {DOCS[key][1]} PHP",
        [(r["status"], r["amount"], r["currency"]) for r in rows], pf(len(rows) == 1 and rows[0]["status"] == "accepted" and rows[0]["amount"] == DOCS[key][1]))

from app.services.report import render_report  # noqa: E402
from app.services.session_store import ReportRow  # noqa: E402

csv_text = render_report([ReportRow(**r) for r in final["report_rows"]])
(OUT / "live" / "prepared_report.csv").write_text(csv_text, encoding="utf-8", newline="")
csv_rows = [r for r in list(csv.reader(io.StringIO(csv_text.lstrip("﻿"), newline="")))[1:] if r]
csv_tot = {}
for r in csv_rows:
    csv_tot[r[5]] = csv_tot.get(r[5], Decimal(0)) + Decimal(r[4])
indep = {"PHP": Decimal(DOCS[PIX][1]) + Decimal(DOCS[SUN][1])}
rec("R1", "LIVE + production render_report (prepared, not committed)", "CSV rows", f"{sorted([PIX, SUN])}; no Bayside",
    sorted(r[0] for r in csv_rows), pf(sorted(r[0] for r in csv_rows) == sorted([PIX, SUN])))
rec("R2", "LIVE + render_report", "Totals: independent (18648.00 + 683.20) = CSV = plan", {k: str(v) for k, v in indep.items()},
    {"csv": {k: str(v) for k, v in csv_tot.items()}, "plan": {t["currency"]: t["amount"] for t in final["totals"]}},
    pf(csv_tot == indep and {t["currency"]: Decimal(t["amount"]) for t in final["totals"]} == indep))
bay_final = row_of(final, BAY)
rec("R3", "LIVE", "Bayside raw amount_text absent from rows and totals", "Bayside row not accepted, amount null; total excludes 1,520 / 1,250",
    {"bayside_rows": [(r["status"], r["amount"]) for r in bay_final], "bayside_amount_text": init[BAY]["amount_text"], "totals": final["totals"]},
    pf(all(r["status"] != "accepted" and r["amount"] is None for r in bay_final) and csv_tot == indep))
rec("G1", "LIVE", "Live root, mock root and canary", "unchanged", "unchanged" if fs_unchanged() else "CHANGED", pf(fs_unchanged()))
(OUT / "live" / "http_log.json").write_text(json.dumps(live_log, indent=2), encoding="utf-8")

# ================================================================ INPROCESS (mocked classifier)
from fastapi.testclient import TestClient  # noqa: E402
from app.main import app  # noqa: E402
from app.schemas import ClassificationRecord  # noqa: E402
from app.services import local_ai, orchestrator  # noqa: E402
from app.services.session_store import store  # noqa: E402

MOCK = [
    ("BAYSIDE OFFICE MART", {"category": "receipt", "document_kind": "receipt", "merchant": "BAYSIDE OFFICE MART", "date": "2026-09-05",
                             "amount_text": "PHP 1,520.00", "currency": "PHP", "evidence_quote": "AMOUNT DUE: PHP 1,520.00", "explanation": "MOCK"}),
    ("SUNBEAM CAFE", {"category": "receipt", "document_kind": "receipt", "merchant": "SUNBEAM CAFE", "date": "2026-09-21", "amount_text": "PHP 683.20",
                      "currency": "PHP", "evidence_quote": "FINAL TOTAL: PHP 683.20", "explanation": "MOCK"}),
    ("PIXELFORGE", {"category": "invoice", "document_kind": "invoice", "merchant": "PIXELFORGE DESIGN STUDIO", "date": "2026-10-02",
                    "amount_text": "PHP 18,648.00", "currency": "PHP", "evidence_quote": "Total Amount Due: PHP 18,648.00", "explanation": "MOCK"}),
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
    rec("M0", "INPROCESS mocked", "Bayside with parseable rejected amount_text 'PHP 1,520.00' after the real validator",
        "needs_review; amount_conflict; canonical amount null", f"status {bay.status}; flags {[f['code'] for f in bay.review_flags]}; amount {bay.classification.get('amount')!r}; amount_text {bay.classification.get('amount_text')!r}",
        pf(bay.status == "needs_review" and any(f["code"] == "amount_conflict" for f in bay.review_flags) and bay.classification.get("amount") is None))
    _, mp0 = m("GET", f"/api/scans/{msid}/plan")
    plan_id = mp0["plan_id"]
    rev0, snap0, bay0 = session.plan_revision, copy.deepcopy(store.get_plan_snapshot(plan_id)), copy.deepcopy(bay)
    st, resp = m("PATCH", f"/api/documents/{MID[BAY]}", {"accept": True})
    snap1 = store.get_plan_snapshot(plan_id)
    same = (bay.classification == bay0.classification and bay.review_flags == bay0.review_flags and bay.status == bay0.status
            and bay.user_corrected == bay0.user_corrected and getattr(bay, "review_disposition", None) == getattr(bay0, "review_disposition", None))
    rec("M1", "INPROCESS mocked (store read directly)", "Bayside {accept: true} with parseable amount_text (revival case)",
        "422; plan_revision, plan snapshot, classification, flags, status, user_corrected, disposition unchanged",
        f"HTTP {st} {resp.get('detail') if isinstance(resp, dict) else resp}; revision {rev0}->{session.plan_revision}; "
        f"snapshot {'unchanged' if snap1 == snap0 else 'CHANGED'}; record {'unchanged' if same else 'CHANGED'}",
        pf(st == 422 and session.plan_revision == rev0 and snap1 == snap0 and same))
    _, mp1 = m("GET", f"/api/scans/{msid}/plan")
    rows = row_of(mp1, BAY)
    rec("M2", "INPROCESS mocked", "Fresh plan after rejected accept", "Bayside row not accepted, amount null; totals exclude 1,520",
        {"rows": [(r["status"], r["amount"]) for r in rows], "totals": mp1["totals"]},
        pf(all(r["status"] != "accepted" and r["amount"] is None for r in rows) and all(r["amount"] != "1520.00" for r in mp1["report_rows"])))

    # Code-level plan-builder probe on a DEEP COPY (the API is not bypassed; the live/mocked store is not touched):
    # a record that is ok, unflagged, has no canonical amount but a parseable amount_text must not yield an amount.
    probe = copy.deepcopy(session)
    pb = next(d for d in probe.documents if d.relative_path == BAY)
    pb.status, pb.review_flags, pb.user_corrected = "ok", [], True
    pb.classification["amount"] = None
    built = orchestrator._build_plan(probe, "partial")
    prow = [r for r in built.report_rows if r.source_filename == BAY]
    rec("M3", "INPROCESS code-level probe on a deep copy of the session", "_build_plan with amount null + amount_text 'PHP 1,520.00' (no fallback)",
        "row amount null and not accepted; totals exclude it", {"rows": [(r.status, r.amount) for r in prow], "totals": [t.model_dump() if hasattr(t, 'model_dump') else t for t in built.totals]},
        pf(all(r.amount is None and r.status != "accepted" for r in prow) and all(r.amount != "1520.00" for r in built.report_rows)))
    r_before = session.plan_revision
    st, _ = m("PATCH", f"/api/documents/{MID[SUN]}", {"amount": "683.20", "accept": True})
    rec("M4", "INPROCESS", "Revision check: valid Sunbeam correction still bumps revision", "200; revision +1",
        f"HTTP {st}; revision {r_before}->{session.plan_revision}", pf(st == 200 and session.plan_revision == r_before + 1))
    rec("G2", "INPROCESS", "Roots and canary after in-process part", "unchanged", "unchanged" if fs_unchanged() else "CHANGED", pf(fs_unchanged()))
finally:
    local_ai.classify_excerpt = real

rec("X1", "pytest", "Full backend suite on 0641adb", "all pass", "1 failed, 185 passed, 2 skipped: "
    "test_session.py::test_accept_without_amount_field_files_uncounted_and_null_is_rejected (expects 200 for {accept:true} on a missing_amount receipt; now 422)",
    "FAIL", "Dev 1 + Dev 3", note="0641adb conflicts with the UI1 fix 47520ec; tracked separately from DA-7")
rec("X2", "-", "Offline and symlink tests", "-", "not performed", "NOT TESTED", "QA")
(OUT / "inprocess_mock_http_log.json").write_text(json.dumps(mock_log, indent=2), encoding="utf-8")
(OUT / "results.json").write_text(json.dumps(results, indent=2, default=str), encoding="utf-8")
counts = {}
for r in results:
    counts[r["status"]] = counts.get(r["status"], 0) + 1
print(f"\n{counts}  live scan {sid}  (no approve/undo)")
