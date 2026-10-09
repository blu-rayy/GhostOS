"""DA-5 retest - Stages 2-4 (NON-DESTRUCTIVE). Talks to the MOCK backend on 127.0.0.1:8001.

Creates DA5-R1 (state tests) and DA5-R2 (candidate approval batch, preview only) under
%LOCALAPPDATA%\\Temp\\ghostos-docaware, plus an outside-root canary. No approve/undo calls.

    backend\\.venv\\Scripts\\python.exe -B tests\\reports\\document_aware_review\\da5_retest_3c60bb3\\scripts\\da5_stage2_4.py
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

sys.dont_write_bytecode = True
REPO = Path(__file__).resolve().parents[5]
FIX = REPO / "tests" / "fixtures" / "sample_folder"
OUT = REPO / "tests" / "reports" / "document_aware_review" / "da5_retest_3c60bb3"
BASE = Path.home() / "AppData" / "Local" / "Temp" / "ghostos-docaware"
R1, R2 = BASE / "DA5-R1", BASE / "DA5-R2"
CANARY = BASE / "DA5-canary" / "canary.txt"
MOCK = "http://127.0.0.1:8001"
sys.path.insert(0, str(REPO / "backend"))

FILES = {
    R1: {"r1/receipts/sunbeam-cafe-receipt.pdf": "receipts/sunbeam-cafe-receipt.pdf",
         "r1/receipts/tibay-hardware-receipt.csv": "receipts/tibay-hardware-receipt.csv",
         "r1/misc/bank-statement-oct2026.txt": "misc/bank-statement-oct2026.txt",      # mocked explicit-null kind
         "r1/misc/card-statement-sep2026.pdf": "misc/card-statement-sep2026.pdf"},     # mocked kind OMITTED
    R2: {"r2/receipts/sunbeam-cafe-receipt.pdf": "receipts/sunbeam-cafe-receipt.pdf",
         "r2/receipts/tibay-hardware-receipt.csv": "receipts/tibay-hardware-receipt.csv",
         "r2/misc/bank-statement-oct2026.txt": "misc/bank-statement-oct2026.txt"},     # mocked explicit-null kind
}
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


def rec(tid, case, method, check, expected, actual, status, owner="Dev 1", note=""):
    results.append({"id": tid, "case": case, "method": method, "check": check, "expected": expected, "actual": actual, "status": status, "owner": owner, "note": note})
    print(f"[{status}] {tid} ({method}) {check}\n      expected: {expected}\n      actual:   {actual}" + (f"\n      note: {note}" if note else ""))


def pf(ok): return "PASS" if ok else "FAIL"


def write(name, obj): (OUT / name).write_text(json.dumps(redact(obj), indent=2), encoding="utf-8")


# ================= Stage 2: setup =================
for p in (R1, R2, CANARY.parent, OUT / "setup"):
    if p.exists():
        sys.exit(f"STOP: {p} exists")
CANARY.parent.mkdir(parents=True)
CANARY.write_text("DA-5 retest outside-root canary\n", encoding="utf-8")
(OUT / "setup").mkdir()
manifest = {"commit": subprocess.run(["git", "rev-parse", "HEAD"], cwd=REPO, capture_output=True, text=True).stdout.strip(),
            "created_at": datetime.now(timezone.utc).isoformat(), "canary_sha256": sha(CANARY), "roots": {}}
for root, files in FILES.items():
    root.mkdir()
    for rel, src in files.items():
        (root / rel).parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(FIX / src, root / rel)
    manifest["roots"][root.name] = {"files": files, "snapshot": snap(root)}
write("setup/manifest.json", manifest)
r1_0, r2_0 = snap(R1), snap(R2)
_, st_ = http("GET", "/api/status")
print(f"MOCK backend status: {st_}\n")


def unchanged(): return snap(R1) == r1_0 and snap(R2) == r2_0 and sha(CANARY) == manifest["canary_sha256"]


# ================= Stage 3B1: legacy record (field genuinely omitted), unit level =================
from app.schemas import ClassificationRecord  # noqa: E402
from app.services.document_awareness import field_profile_for_classification, document_kind_for_classification  # noqa: E402
from app.services import orchestrator  # noqa: E402
from app.services.session_store import DocumentRecord, ScanSession  # noqa: E402

legacy = {"category": "invoice", "merchant": "Legacy Vendor", "date": "2026-09-01", "amount_text": "PHP 100.00", "amount": "100.00",
          "currency": "PHP", "evidence_quote": "x", "evidence_verified": True, "explanation": "legacy"}
assert "document_kind" not in legacy
s = ScanSession(scan_id="unit", root=str(BASE / "unit-not-created"), scanned_at="", state="done")
s.documents.append(DocumentRecord(file_id="L1", relative_path="old/legacy-invoice.pdf", file_type="pdf", size_bytes=1, sha256="0" * 64,
                                  excerpt="", status="ok", classification=dict(legacy)))
pl = orchestrator._build_plan(s)
rec("B1a", "B legacy", "unit (stored legacy record, no document_kind key)", "profile and derived kind",
    "category fallback: kind invoice, profile transaction", f"kind {document_kind_for_classification(legacy)}, profile {field_profile_for_classification(legacy)}",
    pf(field_profile_for_classification(legacy) == "transaction" and document_kind_for_classification(legacy) == "invoice"))
rec("B1b", "B legacy", "unit (_build_plan)", "legacy invoice plan and report row", "Invoices/2026-09/, accepted row PHP 100.00",
    f"{pl.operations[0].destination_relative_path}, row {pl.report_rows[0].status if pl.report_rows else None} {pl.report_rows[0].amount if pl.report_rows else ''}",
    pf(pl.operations[0].destination_relative_path == "Invoices/2026-09/legacy-invoice.pdf" and pl.report_rows and pl.report_rows[0].status == "accepted"))
m_omit = ClassificationRecord.model_validate({k: v for k, v in legacy.items() if k not in ("amount", "evidence_verified")})
m_null = ClassificationRecord.model_validate({**{k: v for k, v in legacy.items() if k not in ("amount", "evidence_verified")}, "document_kind": None})
rec("B1c", "B legacy vs A null", "unit (ClassificationRecord.field_profile)", "omitted field vs explicit null",
    "omitted -> transaction (legacy); explicit null -> none", f"omitted -> {m_omit.field_profile}; explicit null -> {m_null.field_profile}",
    pf(m_omit.field_profile == "transaction" and m_null.field_profile == "none"))

# ================= Stage 4a: /api/classify (mocked classifier) =================
for tid, text, exp_profile, exp_op in (("K1", "MOCK-STATEMENT account summary", "reference", False),
                                       ("K2", "MOCK-IDENTITY civil record", "none", False),
                                       ("K3", "MOCK-NULLKIND PHP 100.00", "none", False),
                                       ("K4", "MOCK-OMITKIND PHP 100.00", "transaction", True),
                                       ("K5", "SUNBEAM CAFE FINAL TOTAL: PHP 683.20", "transaction", True)):
    st, r = http("POST", "/api/classify", {"file_id": tid.lower(), "text_excerpt": text})
    op = r.get("proposed_operation") if isinstance(r, dict) else None
    ok = st == 200 and r.get("field_profile") == exp_profile and (op is not None) == exp_op
    rec(tid, "classify", "MOCKED classifier via /api/classify", f"excerpt '{text.split()[0]}'",
        f"HTTP 200, profile {exp_profile}, transaction operation {'proposed' if exp_op else 'NOT proposed'}",
        f"HTTP {st}, kind {(r.get('classification') or {}).get('document_kind') if isinstance(r, dict) else '-'}, profile {r.get('field_profile') if isinstance(r, dict) else '-'}, "
        f"op {op and op.get('destination_relative_path')}, needs_review {r.get('needs_review') if isinstance(r, dict) else '-'}, reason {r.get('review_reason') if isinstance(r, dict) else '-'}",
        pf(ok), note="K4 = legacy compatibility (field omitted)" if tid == "K4" else "")

# ================= Stage 3/4 on R1 (mocked scan) =================
st, prog = http("POST", "/api/scan", {"root": str(R1)})
sid = prog["scan_id"]
while prog["state"] == "running":
    time.sleep(0.3)
    _, prog = http("GET", f"/api/scans/{sid}/progress")
_, scan = http("GET", f"/api/scans/{sid}")
write("R1_scan_initial.json", scan)
docs = {d["relative_path"]: d for d in scan["documents"]}
ID = {k: docs[k]["file_id"] for k in docs}
BANK, CARD, SUN, TIB = "r1/misc/bank-statement-oct2026.txt", "r1/misc/card-statement-sep2026.pdf", "r1/receipts/sunbeam-cafe-receipt.pdf", "r1/receipts/tibay-hardware-receipt.csv"
for k, d in docs.items():
    c = d.get("classification") or {}
    print(f"  {k:42} status={d['status']:12} cat={c.get('category')} kind={c.get('document_kind')} profile={c.get('field_profile')} amount={c.get('amount')} flags={[f['code'] for f in d['review_flags']]}")
print()
from app.services.session_store import store as _unused  # noqa: E402,F401  (server store is in the mock process; not accessible here)


def plan(mode):
    _, p = http("GET", f"/api/scans/{sid}/plan?mode={mode}")
    return p, {o["original_relative_path"]: o["destination_relative_path"] for o in p["operations"]}, {r["source_filename"]: r for r in p["report_rows"]}


def doc(k):
    _, s_ = http("GET", f"/api/scans/{sid}")
    return next(d for d in s_["documents"] if d["file_id"] == ID[k])


# ---- A: explicit null
c = docs[BANK]["classification"]
flags = [f["code"] for f in docs[BANK]["review_flags"]]
rec("A1", "A explicit null", "MOCKED scan", "GET exposes conservative state",
    "document_kind null, field_profile none, status needs_review, flag uncertain_document_kind",
    f"kind {c.get('document_kind')!r}, profile {c.get('field_profile')}, status {docs[BANK]['status']}, flags {flags}",
    pf(c.get("document_kind") is None and "document_kind" in c and c.get("field_profile") == "none" and docs[BANK]["status"] == "needs_review" and "uncertain_document_kind" in flags))
rec("A2", "A explicit null", "MOCKED scan", "no expense amount carried", "amount null (no parsed expense amount)", f"amount {c.get('amount')!r}, amount_text {c.get('amount_text')!r}",
    pf(c.get("amount") is None), note="amount_text is the model's raw text; it is not an expense amount")
pb, ob, rb = plan("blocking")
pp, op_, rp = plan("partial")
write("R1_plan_blocking.json", pb); write("R1_plan_partial.json", pp)
rec("A3", "A explicit null", "MOCKED scan", "blocking and partial destinations", "Uncategorized/ in both; no report row in either",
    f"blocking {ob.get(BANK)} row={rb.get(BANK) and rb[BANK]['status']}; partial {op_.get(BANK)} row={rp.get(BANK) and rp[BANK]['status']}",
    pf(ob.get(BANK, "").startswith("Uncategorized/") and op_.get(BANK, "").startswith("Uncategorized/") and BANK not in rb and BANK not in rp))

# ---- C: valid receipt
cs = docs[SUN]["classification"]
rec("C1", "C valid receipt", "MOCKED scan", "kind/profile/status", "receipt, transaction, ok, no flags",
    f"{cs.get('document_kind')}, {cs.get('field_profile')}, {docs[SUN]['status']}, {[f['code'] for f in docs[SUN]['review_flags']]}",
    pf(cs.get("document_kind") == "receipt" and cs.get("field_profile") == "transaction" and docs[SUN]["status"] == "ok"))
rec("C2", "C valid receipt", "MOCKED scan", "destination and report row", "Receipts/2026-09/sunbeam-cafe-receipt.pdf; one accepted row PHP 683.20",
    f"{ob.get(SUN)}; row {rb.get(SUN) and (rb[SUN]['status'], rb[SUN]['amount'], rb[SUN]['currency'])}",
    pf(ob.get(SUN) == "Receipts/2026-09/sunbeam-cafe-receipt.pdf" and rb.get(SUN, {}).get("status") == "accepted" and rb[SUN]["amount"] == "683.20"))

# ---- B2: NEW scan whose model response omits the kind (distinct from the legacy record in B1)
cc = docs[CARD]["classification"]
rec("B2a", "B new-scan omission", "MOCKED scan (model JSON without document_kind)", "how the omitted kind is treated",
    "record behaviour (developer contract: legacy compatibility)",
    f"stored kind key -> API kind {cc.get('document_kind')}, profile {cc.get('field_profile')}, status {docs[CARD]['status']}, flags {[f['code'] for f in docs[CARD]['review_flags']]}, "
    f"blocking dest {ob.get(CARD)}, row {rb.get(CARD) and rb[CARD]['status']}", "RECORDED")

rec("G1", "G", "MOCKED", "scan + previews wrote nothing", "R1, R2, canary unchanged", "unchanged" if unchanged() else "CHANGED", pf(unchanged()))

# ---- invalid / contradictory corrections
def correction(tid, case, key, body, expect_status, why):
    before = doc(key)
    st, r = http("PATCH", f"/api/documents/{ID[key]}", body)
    after = doc(key)
    same = after == before
    exp_txt = f"HTTP {expect_status}" + ("; record unchanged" if expect_status == 422 else "")
    ok = st == expect_status and (same if expect_status == 422 else True)
    rec(tid, case, "MOCKED", f"PATCH {key} {json.dumps(body)}", f"{exp_txt} ({why})",
        f"HTTP {st} {r.get('detail') if isinstance(r, dict) and 'detail' in r else ''}; record {'unchanged' if same else 'CHANGED'}"
        + ("" if same else f" -> status {after['status']}, category {(after.get('classification') or {}).get('category')}, kind {(after.get('classification') or {}).get('document_kind')}, "
                           f"profile {(after.get('classification') or {}).get('field_profile')}, amount {(after.get('classification') or {}).get('amount')!r}, date {(after.get('classification') or {}).get('date')!r}, currency {(after.get('classification') or {}).get('currency')!r}"),
        pf(ok))
    return st


correction("X1", "A explicit null", BANK, {"amount": "9120.50", "accept": True}, 422, "profile none forbids transaction fields")
correction("X2", "A explicit null", BANK, {"merchant": "Sample National Bank", "date": "2026-09-30", "currency": "PHP"}, 422, "profile none")
correction("X3", "A explicit null", BANK, {"field_profile": "transaction"}, 422, "backend-controlled field")
correction("X4", "C receipt", TIB, {"amount": "abc", "accept": True}, 422, "invalid decimal amount")
correction("X5", "C receipt", TIB, {"date": "2026-13-45"}, 422, "invalid date")
correction("X6", "C receipt", TIB, {"currency": "XYZ"}, 422, "unsupported currency")
correction("X7", "A explicit null", BANK, {"document_kind": 5}, 422, "invalid kind type")

# accept-as-is on the explicit-null record
st, r = http("PATCH", f"/api/documents/{ID[BANK]}", {"accept": True})
p_after, o_after, r_after = plan("blocking")
rec("A4", "A explicit null", "MOCKED", "accept-as-is {accept: true}", "never an expense row",
    f"HTTP {st}; destination {o_after.get(BANK)}; row {r_after.get(BANK) and r_after[BANK]['status']}; totals {p_after['totals']}",
    pf(st == 200 and BANK not in r_after))
correction("A5", "A explicit null", BANK, {"category": "invoice", "accept": True}, 200, "category switch: recorded, contract decision")
p5, o5, r5 = plan("blocking")
rec("A5b", "A explicit null", "MOCKED", "after the category switch", "still no expense row", f"destination {o5.get(BANK)}; row {r5.get(BANK) and r5[BANK]['status']}",
    pf(BANK not in r5))
# full explicit reclassification (contract decision path)
st1, _ = http("PATCH", f"/api/documents/{ID[BANK]}", {"document_kind": "invoice"})
st2, r2_ = http("PATCH", f"/api/documents/{ID[BANK]}", {"merchant": "Sample National Bank", "date": "2026-09-30", "amount": "9120.50", "currency": "PHP", "accept": True})
p6, o6, r6 = plan("blocking")
rec("A6", "A explicit null", "MOCKED", "explicit reclassification: PATCH kind=invoice, then payment details + accept",
    "record behaviour (permitted decision?)", f"HTTP {st1}, {st2}; destination {o6.get(BANK)}; row {r6.get(BANK) and (r6[BANK]['status'], r6[BANK]['amount'])}",
    "CONTRACT DECISION REQUIRED", "Dev 1 + team")

# accept-as-is on the omitted-kind statement (B2)
st, r = http("PATCH", f"/api/documents/{ID[CARD]}", {"accept": True})
p7, o7, r7 = plan("blocking")
row7 = r7.get(CARD)
rec("B2b", "B new-scan omission", "MOCKED", "accept-as-is on a statement whose kind was omitted by the model",
    "not counted (QA safety rule) / legacy compatibility (developer contract)",
    f"HTTP {st}; destination {o7.get(CARD)}; row {row7 and (row7['status'], row7['amount'])}; totals {p7['totals']}",
    "FAIL" if row7 and row7["status"] == "accepted" else "PASS", "Dev 1 + team",
    note="Counts as an expense through the legacy fallback when a NEW model response omits document_kind." if row7 and row7["status"] == "accepted" else "")
rec("G2", "G", "MOCKED", "after all corrections and previews", "R1, R2, canary unchanged", "unchanged" if unchanged() else "CHANGED", pf(unchanged()))
write("R1_plan_final.json", p7)

# ================= R2: candidate approval batch (preview only) =================
st, prog = http("POST", "/api/scan", {"root": str(R2)})
sid2 = prog["scan_id"]
while prog["state"] == "running":
    time.sleep(0.3)
    _, prog = http("GET", f"/api/scans/{sid2}/progress")
_, scan2 = http("GET", f"/api/scans/{sid2}")
_, p2b = http("GET", f"/api/scans/{sid2}/plan")
_, p2 = http("GET", f"/api/scans/{sid2}/plan?mode=partial")
write("R2_scan.json", scan2); write("R2_plan_blocking.json", p2b); write("R2_plan_partial_for_review.json", p2)
rec("G3", "G", "MOCKED", "R2 preview wrote nothing", "unchanged", "unchanged" if unchanged() else "CHANGED", pf(unchanged()))

(OUT / "http_log_stage2_4.json").write_text(json.dumps(log, indent=2), encoding="utf-8")
(OUT / "results_stage2_4.json").write_text(json.dumps(results, indent=2), encoding="utf-8")
counts = {}
for r_ in results:
    counts[r_["status"]] = counts.get(r_["status"], 0) + 1
print(f"\n{counts}")
print(f"R1 scan {sid}; R2 scan {sid2} plan {p2['plan_id']} mode {p2['mode']} blocking {p2['blocking_review_count']}")
for o in p2["operations"]:
    print(f"  R2 op: {o['original_relative_path']} -> {o['destination_relative_path']} ({o['reason']})")
print(f"  R2 report rows: {[(r_['source_filename'], r_['status'], r_['amount'], r_['currency']) for r_ in p2['report_rows']]}")
print(f"  R2 totals: {p2['totals']}")
