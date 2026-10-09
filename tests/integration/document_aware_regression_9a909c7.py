"""Targeted document-aware regression for backend commit 9a909c7 (Developer 4 / QA). NON-DESTRUCTIVE.

Part LIVE   - real backend on 127.0.0.1:8000 + real local model, disposable copy in
              %LOCALAPPDATA%\\Temp\\ghostos-docaware\\R2. Scan, preview, PATCH, plan only.
Part MOCK   - in a separate in-process FastAPI TestClient whose model call is REPLACED by a
              controlled response with document_kind = null. Same production routes,
              orchestrator, validator and plan builder; no real model; separate in-memory store.
Part UNIT   - production document_awareness / _build_plan called directly on constructed records.

Never calls approve or undo; verifies the disposable folders are byte-identical after every step.

    backend\\.venv\\Scripts\\python.exe tests\\integration\\document_aware_regression_9a909c7.py
"""

from __future__ import annotations

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

REPO = Path(__file__).resolve().parents[2]
FIX = REPO / "tests" / "fixtures" / "sample_folder"
# Optional run suffix (e.g. --suffix _rerun1) so a re-run never reuses earlier folders or evidence.
SUFFIX = sys.argv[sys.argv.index("--suffix") + 1] if "--suffix" in sys.argv else ""
OUT = REPO / "tests" / "reports" / "document_aware_review" / f"regression_9a909c7{SUFFIX}"
BASE = Path.home() / "AppData" / "Local" / "Temp" / "ghostos-docaware"
LIVE_ROOT = BASE / f"R2{SUFFIX}"
MOCK_ROOT = BASE / f"R2-mock{SUFFIX}"
BASE_URL = "http://127.0.0.1:8000"

LIVE_FILES = {
    "bank_statement": "misc/bank-statement-oct2026.txt",
    "card_statement": "misc/card-statement-sep2026.pdf",
    "birth_certificate": "identity/birth-certificate.pdf",
    "drivers_license": "identity/drivers-license-record.txt",
    "receipt": "receipts/sunbeam-cafe-receipt.pdf",
}
MOCK_FILES = {"bank_statement": "misc/bank-statement-oct2026.txt", "card_statement": "misc/card-statement-sep2026.pdf"}

results: list[dict] = []
live_log: list[dict] = []
mock_log: list[dict] = []


def sha(p: Path) -> str:
    return hashlib.sha256(p.read_bytes()).hexdigest()


def tree(root: Path) -> dict:
    return {p.relative_to(root).as_posix(): sha(p) for p in sorted(root.rglob("*")) if p.is_file()}


def redact(obj):
    text = json.dumps(obj, default=str)
    for root, tag in ((LIVE_ROOT, "<ROOT_R2>"), (MOCK_ROOT, "<ROOT_R2_MOCK>"), (BASE, "<TEST_BASE>")):
        for form in (str(root), str(root).replace("\\", "/")):
            text = text.replace(json.dumps(form)[1:-1], tag)
    return json.loads(text)


def record(tid, test, method, inp, expected, actual, status, owner="", note=""):
    results.append({"id": tid, "test": test, "method": method, "input": inp, "expected": expected,
                    "actual": actual, "status": status, "owner": owner, "note": note})
    print(f"[{status}] {tid} ({method}) {inp}\n      expected: {expected}\n      actual:   {actual}" + (f"\n      note:     {note}" if note else ""))


def copy_set(root: Path, files: dict) -> dict:
    root.mkdir(parents=True)
    for rel in files.values():
        (root / rel).parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(FIX / rel, root / rel)
    return tree(root)


# ============================================================ preflight
for p in (LIVE_ROOT, MOCK_ROOT, OUT):
    if p.exists():
        sys.exit(f"STOP: {p} already exists; refusing to reuse or overwrite")
OUT.mkdir(parents=True)
commit = subprocess.run(["git", "rev-parse", "HEAD"], cwd=REPO, capture_output=True, text=True).stdout.strip()


# ============================================================ PART LIVE
def live(method, path, body=None):
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
    live_log.append(redact({"at": datetime.now(timezone.utc).isoformat(), "request": {"method": method, "path": path, "body": body},
                            "response": {"status": st, "body": payload}}))
    return st, payload


_, status = live("GET", "/api/status")
env = {"commit": commit, "model_name": status.get("model_name"), "model_endpoint": status.get("model_endpoint"),
       "external_requests": status.get("external_requests"), "run_at": datetime.now(timezone.utc).isoformat()}
print(f"commit {commit}  model {env['model_name']}\n")

live_before = copy_set(LIVE_ROOT, LIVE_FILES)
st, prog = live("POST", "/api/scan", {"root": str(LIVE_ROOT)})
scan_id = prog["scan_id"]
while prog["state"] == "running":
    time.sleep(1)
    _, prog = live("GET", f"/api/scans/{scan_id}/progress")
_, scan = live("GET", f"/api/scans/{scan_id}")
fid = {k: next(d["file_id"] for d in scan["documents"] if d["relative_path"] == rel) for k, rel in LIVE_FILES.items()}
_, plan_initial = live("GET", f"/api/scans/{scan_id}/plan")
initial = {k: (next(d for d in scan["documents"] if d["file_id"] == fid[k]).get("classification") or {}) for k in LIVE_FILES}
for k, c in initial.items():
    print(f"  live {k:18} category={c.get('category')} kind={c.get('document_kind')} profile={c.get('field_profile')} amount={c.get('amount')}")
print()


def plan_view(plan, key, rel):
    dest = next((o["destination_relative_path"] for o in plan["operations"] if o["original_relative_path"] == rel), None)
    row = next((r for r in plan["report_rows"] if r["source_filename"] == rel), None)
    return dest, row


# ---- A: DA-1 category switch on non-transactional documents
a_inputs = {"card_statement": {"category": "invoice", "accept": True}, "drivers_license": {"category": "receipt", "accept": True}}
a_resp = {}
for key, body in a_inputs.items():
    st, resp = live("PATCH", f"/api/documents/{fid[key]}", body)
    a_resp[key] = (st, resp)
# Guard against D1 (cross-scan file_id lookup): the corrections must have landed on THIS scan.
_, own = live("GET", f"/api/scans/{scan_id}")
landed = {k: next(d for d in own["documents"] if d["file_id"] == fid[k])["user_corrected"] for k in a_inputs}
if not all(landed.values()):
    record("A0", "D1 guard", "live", "corrections landed on this run's scan", "user_corrected true on this scan",
           landed, "BLOCKED", "Dev 1", note="Another scan with the same file_ids received the corrections (D1). Run invalid.")
    (OUT / "results.json").write_text(json.dumps(results, indent=2), encoding="utf-8")
    (OUT / "live_http_log.json").write_text(json.dumps(live_log, indent=2), encoding="utf-8")
    sys.exit("STOP: D1 interference detected; live results would be invalid.")
record("A0", "D1 guard", "live", "corrections landed on this run's scan", "user_corrected true on this scan", landed, "PASS")
_, plan_a = live("GET", f"/api/scans/{scan_id}/plan")
for key, body in a_inputs.items():
    st, resp = a_resp[key]
    c = resp.get("classification") if isinstance(resp, dict) else {}
    record(f"A1-{key}", "DA-1 correction outcome", "live", f"PATCH {LIVE_FILES[key]} {json.dumps(body)}",
           "record whether accepted or rejected",
           f"HTTP {st}; stored category={c.get('category') if c else '-'}, kind={c.get('document_kind') if c else '-'}, profile={c.get('field_profile') if c else '-'}",
           "CONTRACT DECISION REQUIRED", "Dev 1 + team",
           note="Spec asks the backend to reject contradictory combinations; the correction is accepted but neutralised in planning." if st == 200 else "")
    dest, row = plan_view(plan_a, key, LIVE_FILES[key])
    record(f"A2-{key}", "DA-1 routing", "live", f"plan after the category switch for {LIVE_FILES[key]}",
           "destination under Other/ (not Invoices/ or Receipts/); no report row", f"destination={dest}; report_row={row}",
           "PASS" if (dest or "").startswith(("Other/", "GhostOS Organized/Other/")) and row is None else "FAIL", "Dev 1")
totals_a = {t["currency"]: t["amount"] for t in plan_a["totals"]}
record("A3", "DA-1 totals", "live", "plan totals after the category switches", "receipt only: {'PHP': '683.20'}",
       totals_a, "PASS" if totals_a == {"PHP": "683.20"} else "FAIL", "Dev 1")
record("A4", "no writes", "live", "after A", "folder unchanged", "unchanged" if tree(LIVE_ROOT) == live_before else "CHANGED",
       "PASS" if tree(LIVE_ROOT) == live_before else "FAIL", "Dev 1")

# ---- C: F6 document_kind correction (record only)
c_cases = [("birth_certificate", {"document_kind": "receipt"}), ("birth_certificate", {"document_kind": 5})]
for i, (key, body) in enumerate(c_cases, 1):
    st, resp = live("PATCH", f"/api/documents/{fid[key]}", body)
    c = resp.get("classification") if isinstance(resp, dict) else None
    _, plan_c = live("GET", f"/api/scans/{scan_id}/plan")
    dest, row = plan_view(plan_c, key, LIVE_FILES[key])
    record(f"C{i}", "F6 kind correction", "live", f"PATCH {LIVE_FILES[key]} {json.dumps(body)}", "record current behaviour",
           f"HTTP {st}; " + (f"kind={c.get('document_kind')}, profile={c.get('field_profile')}, status={resp.get('status')}; plan destination={dest}, report_row={row and row['status']}"
                             if c else f"detail={resp.get('detail') if isinstance(resp, dict) else resp}"),
           "CONTRACT DECISION REQUIRED", "Dev 1 + team")

# ---- D: statement reclassification to receipt, then an amount
bank = LIVE_FILES["bank_statement"]
steps = [
    ("D1", {"amount": "9120.50", "currency": "PHP", "accept": True}, "amount on a statement before any kind change"),
    ("D2", {"document_kind": "receipt"}, "user changes the kind to receipt"),
    ("D3", {"merchant": "Sample National Bank", "date": "2026-09-30", "amount": "9120.50", "currency": "PHP", "accept": True},
     "user enters payment details and accepts"),
]
for tid, body, what in steps:
    st, resp = live("PATCH", f"/api/documents/{fid['bank_statement']}", body)
    c = resp.get("classification") if isinstance(resp, dict) else None
    _, plan_d = live("GET", f"/api/scans/{scan_id}/plan")
    dest, row = plan_view(plan_d, "bank_statement", bank)
    totals = {t["currency"]: t["amount"] for t in plan_d["totals"]}
    record(tid, f"statement reclassification: {what}", "live", f"PATCH {bank} {json.dumps(body)}",
           "record behaviour; eligibility for totals",
           f"HTTP {st}; " + (f"kind={c.get('document_kind')}, profile={c.get('field_profile')}, status={resp.get('status')}; "
                             if c else f"detail={resp.get('detail') if isinstance(resp, dict) else resp}; ")
           + f"destination={dest}; report_row={row and row['status']}; totals={totals}",
           "CONTRACT DECISION REQUIRED" if tid != "D1" else ("PASS" if st == 422 else "FAIL"), "Dev 1 + team" if tid != "D1" else "Dev 1",
           note="D1 expects 422 because a statement's profile is 'reference'." if tid == "D1" else "")
record("D4", "no writes", "live", "after C and D", "folder unchanged", "unchanged" if tree(LIVE_ROOT) == live_before else "CHANGED",
       "PASS" if tree(LIVE_ROOT) == live_before else "FAIL", "Dev 1")

# ============================================================ PART UNIT (explicit-null stored records)
sys.path.insert(0, str(REPO / "backend"))
from app.services.document_awareness import field_profile_for_classification  # noqa: E402
from app.services import orchestrator  # noqa: E402
from app.services.session_store import DocumentRecord, ScanSession  # noqa: E402

base_cls = {"category": "invoice", "merchant": "Sample National Bank", "date": "2026-09-30", "amount_text": "PHP 9,120.50",
            "amount": "9120.50", "currency": "PHP", "evidence_quote": "Closing balance: PHP 9,120.50", "evidence_verified": True, "explanation": "x"}
for tid, cls, label in (("B1", {**base_cls, "document_kind": None}, "explicit null kind"),
                        ("B2", dict(base_cls), "kind key absent (legacy record)")):
    prof = field_profile_for_classification(cls)
    session = ScanSession(scan_id="unit", root=str(BASE / "unit-not-created"), scanned_at="", state="done")
    session.documents.append(DocumentRecord(file_id="u1", relative_path="misc/statement.txt", file_type="txt", size_bytes=1,
                                            sha256="0" * 64, excerpt="", status="ok", classification=cls))
    plan_u = orchestrator._build_plan(session)
    dest = plan_u.operations[0].destination_relative_path if plan_u.operations else None
    row = plan_u.report_rows[0].status if plan_u.report_rows else None
    record(tid, f"DA-5 {label}", "controlled unit (production functions, constructed record, status ok)",
           f"classification category=invoice, {label}", "profile none; no report row; destination Other/" if tid == "B1" else "record legacy behaviour",
           f"profile={prof}; destination={dest}; report_row={row}; totals={[(t.currency, t.amount) for t in plan_u.totals]}",
           ("PASS" if prof == "none" and row is None and (dest or "").startswith("Other/") else "FAIL") if tid == "B1" else "CONTRACT DECISION REQUIRED",
           "Dev 1")

# ============================================================ PART MOCK (new scan, model returns no kind)
from fastapi.testclient import TestClient  # noqa: E402
from app.main import app  # noqa: E402
from app.schemas import ClassificationRecord  # noqa: E402
from app.services import local_ai  # noqa: E402

MOCK_RESPONSES = {
    "bank-statement-oct2026.txt": {"category": "invoice", "document_kind": None, "merchant": "SAMPLE NATIONAL BANK",
                                   "date": "2026-09-30", "amount_text": "PHP 9,120.50", "currency": "PHP",
                                   "evidence_quote": "Closing balance: PHP 9,120.50", "explanation": "MOCK: kind withheld"},
    "card-statement-sep2026.pdf": {"category": "invoice", "document_kind": None, "merchant": "HARBOR FEDERAL BANK",
                                   "date": "2026-09-25", "amount_text": "PHP 5,391.06", "currency": "PHP",
                                   "evidence_quote": "Statement balance: PHP 5,391.06", "explanation": "MOCK: kind withheld"},
}
real_classify = local_ai.classify_excerpt


def fake_classify(excerpt, **_kw):
    for name, payload in MOCK_RESPONSES.items():
        marker = "SAMPLE NATIONAL BANK" if name.startswith("bank") else "HARBOR FEDERAL BANK"
        if marker in excerpt:
            return local_ai.ClassificationResult(classification=ClassificationRecord.model_validate(payload), elapsed_seconds=0.0)
    raise AssertionError("unexpected excerpt in mock")


mock_before = copy_set(MOCK_ROOT, MOCK_FILES)
local_ai.classify_excerpt = fake_classify
try:
    client = TestClient(app)

    def mock(method, path, body=None):
        r = client.request(method, path, json=body)
        try:
            payload = r.json()
        except Exception:
            payload = r.text
        mock_log.append(redact({"request": {"method": method, "path": path, "body": body}, "response": {"status": r.status_code, "body": payload}}))
        return r.status_code, payload

    st, prog = mock("POST", "/api/scan", {"root": str(MOCK_ROOT)})
    mscan = prog["scan_id"]
    while prog["state"] == "running":
        time.sleep(0.2)
        _, prog = mock("GET", f"/api/scans/{mscan}/progress")
    _, ms = mock("GET", f"/api/scans/{mscan}")
    _, mplan = mock("GET", f"/api/scans/{mscan}/plan")
    from app.services.session_store import store as mock_store
    stored = {d.relative_path: d for d in mock_store.get_scan(mscan).documents}
    for key, rel in MOCK_FILES.items():
        d = next(x for x in ms["documents"] if x["relative_path"] == rel)
        c = d.get("classification") or {}
        dest, row = plan_view(mplan, key, rel)
        raw_has_key = "document_kind" in (stored[rel].classification or {})
        unsafe = c.get("field_profile") == "transaction"
        record(f"B3-{key}", "DA-5 new scan, model returns no document_kind", "MOCKED model response via in-process TestClient",
               f"scan {rel} with mocked category=invoice, document_kind=null",
               "profile none; not eligible for totals; routed safely",
               f"stored kind key present={raw_has_key}; API kind={c.get('document_kind')}, profile={c.get('field_profile')}; "
               f"status={d['status']} flags={[f['code'] for f in d['review_flags']]}; destination={dest}; report_row={row and row['status']}",
               "FAIL" if unsafe else "PASS", "Dev 1")
        # The single explicit user action that would make it count: accept as-is (Check: 'Looks right · mark checked').
        st2, resp2 = mock("PATCH", f"/api/documents/{d['file_id']}", {"accept": True})
        _, mplan2 = mock("GET", f"/api/scans/{mscan}/plan")
        dest2, row2 = plan_view(mplan2, key, rel)
        totals2 = {t["currency"]: t["amount"] for t in mplan2["totals"]}
        record(f"B4-{key}", "DA-5 after the user accepts as-is", "MOCKED model response via in-process TestClient",
               f"PATCH {rel} {{accept: true}}", "statement never counted",
               f"HTTP {st2}; destination={dest2}; report_row={row2 and row2['status']}; totals={totals2}",
               "FAIL" if row2 and row2["status"] == "accepted" else "PASS", "Dev 1")
finally:
    local_ai.classify_excerpt = real_classify
record("B5", "no writes", "MOCKED in-process", "after B3/B4", "mock folder unchanged",
       "unchanged" if tree(MOCK_ROOT) == mock_before else "CHANGED", "PASS" if tree(MOCK_ROOT) == mock_before else "FAIL", "Dev 1")

# ============================================================ save
(OUT / "environment.json").write_text(json.dumps(env, indent=2), encoding="utf-8")
(OUT / "live_http_log.json").write_text(json.dumps(live_log, indent=2), encoding="utf-8")
(OUT / "mock_http_log.json").write_text(json.dumps(mock_log, indent=2), encoding="utf-8")
(OUT / "live_scan_initial.json").write_text(json.dumps(redact(scan), indent=2), encoding="utf-8")
(OUT / "live_plan_initial.json").write_text(json.dumps(redact(plan_initial), indent=2), encoding="utf-8")
(OUT / "results.json").write_text(json.dumps(results, indent=2), encoding="utf-8")
counts = {}
for r in results:
    counts[r["status"]] = counts.get(r["status"], 0) + 1
print(f"\n{counts}  live scan={scan_id}  (no approve/undo was requested)")
