"""Document-aware review acceptance test (Developer 4 / QA). NON-DESTRUCTIVE.

Exercises the live backend (POST /api/scan, GET plan, PATCH corrections) on a
disposable copy of synthetic fixtures. It NEVER calls approve or undo, so no
file is moved; it verifies that the disposable folder is byte-identical after
every step. Corrections only change the backend's in-memory scan session.

Run from the repository root with one fresh backend on 127.0.0.1:8000:

    backend\\.venv\\Scripts\\python.exe tests\\integration\\document_aware_acceptance.py

Writes results to tests/reports/document_aware_review/ (refuses to overwrite).
Expectations come from the contract in docs/design/document-aware-review.md and,
where present, tests/fixtures/expected_results/ground_truth.json. QA-derived
expectations for fixtures without an expected_document_kind are labelled.
"""

from __future__ import annotations

import copy
import hashlib
import json
import shutil
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from urllib.error import HTTPError
from urllib.parse import urlparse
from urllib.request import Request, urlopen

sys.dont_write_bytecode = True

REPO = Path(__file__).resolve().parents[2]
FIXTURES = REPO / "tests" / "fixtures" / "sample_folder"
TRUTH = {f["filename"]: f for f in json.loads((REPO / "tests/fixtures/expected_results/ground_truth.json").read_text(encoding="utf-8"))["files"]}
OUT = REPO / "tests" / "reports" / "document_aware_review"
BASE = Path.home() / "AppData" / "Local" / "Temp" / "ghostos-docaware"
ROOT = BASE / "R1"
BASE_URL = "http://127.0.0.1:8000"

# label -> (fixture path, expected kind, expected profile, expectation source)
DOCS = {
    "receipt": ("receipts/sunbeam-cafe-receipt.pdf", "receipt", "transaction", "QA (contract: single POS transaction)"),
    "birth_certificate": ("identity/birth-certificate.pdf", "identity_or_civil", "none", "ground truth"),
    "drivers_license": ("identity/drivers-license-record.txt", "identity_or_civil", "none", "ground truth"),
    "bank_statement": ("misc/bank-statement-oct2026.txt", "statement", "reference", "ground truth"),
    "card_statement": ("misc/card-statement-sep2026.pdf", "statement", "reference", "QA (contract: card statement)"),
    "legal": ("legal/lease-agreement-summary.pdf", "legal", "none", "ground truth"),
    "medical": ("medical/prescription-note.txt", "medical", "none", "ground truth"),
    "uncertain_note": ("misc/aircon-payment-note.txt", "uncertain", "none", "QA (ground-truth category uncertain)"),
    "utility_bill": ("invoices/meralite-power-bill-sep2026.txt", "invoice", "transaction", "ground truth category=invoice (contract lists utility statements as 'statement': DECISION NEEDED)"),
}
TX_FIELDS = ("merchant", "date", "amount", "currency")
FIXED_MAP_PREFIXES = ("Invoices/", "Receipts/", "Other/", "Needs Review/", "GhostOS Organized")

log: list[dict] = []
results: list[dict] = []


def sha(p: Path) -> str:
    return hashlib.sha256(p.read_bytes()).hexdigest()


def tree() -> dict[str, str]:
    return {p.relative_to(ROOT).as_posix(): sha(p) for p in sorted(ROOT.rglob("*")) if p.is_file()}


def redact(obj):
    text = json.dumps(obj)
    for root, tag in ((ROOT, "<ROOT_DA>"), (BASE, "<TEST_BASE>")):
        for form in (str(root), str(root).replace("\\", "/")):
            text = text.replace(json.dumps(form)[1:-1], tag)
    return json.loads(text)


def http(method, path, body=None):
    if urlparse(BASE_URL).hostname not in {"127.0.0.1", "localhost"}:
        sys.exit("Refusing non-loopback backend")
    req = Request(BASE_URL + path, data=json.dumps(body).encode() if body is not None else None, method=method,
                  headers={"Content-Type": "application/json"})
    try:
        with urlopen(req, timeout=300) as r:
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


def record(tid, scenario, inp, expected, actual, ok, owner, note=""):
    status = {True: "PASS", False: "FAIL", None: "NOT TESTED"}[ok]
    results.append({"id": tid, "scenario": scenario, "input": inp, "expected": expected, "actual": actual,
                    "status": status, "owner_if_failing": owner, "note": note})
    print(f"[{status:10}] {tid} {inp}\n             expected: {expected}\n             actual:   {actual}")


# ---------------------------------------------------------------- setup
for p in (ROOT, OUT / "acceptance"):
    if p.exists():
        sys.exit(f"STOP: {p} already exists; refusing to reuse or overwrite")
ROOT.mkdir(parents=True)
(OUT / "acceptance").mkdir(parents=True)
setup = {}
for label, (rel, *_rest) in DOCS.items():
    dst = ROOT / rel
    dst.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(FIXTURES / rel, dst)
    setup[rel] = sha(dst)
    assert setup[rel] == sha(FIXTURES / rel)
before = tree()

# ---------------------------------------------------------------- scan + preview (read-only)
st, prog = http("POST", "/api/scan", {"root": str(ROOT)})
scan_id = prog["scan_id"]
while prog["state"] == "running":
    time.sleep(1)
    _, prog = http("GET", f"/api/scans/{scan_id}/progress")
_, scan = http("GET", f"/api/scans/{scan_id}")
_, plan0 = http("GET", f"/api/scans/{scan_id}/plan")
docs = {d["relative_path"]: d for d in scan["documents"]}
fid = {label: docs[rel]["file_id"] for label, (rel, *_r) in DOCS.items()}
rows0 = {r["source_filename"]: r for r in plan0["report_rows"]}


def doc_now(label):
    _, s = http("GET", f"/api/scans/{scan_id}")
    return next(d for d in s["documents"] if d["file_id"] == fid[label])


def cls(label):
    return docs[DOCS[label][0]].get("classification") or {}


print(f"scan {scan_id}: {len(scan['documents'])} documents\n")
summary = []
for label, (rel, ekind, eprof, src) in DOCS.items():
    c, d = cls(label), docs[rel]
    summary.append({"label": label, "file": rel, "category": c.get("category"), "document_kind": c.get("document_kind"),
                    "field_profile": c.get("field_profile"), "merchant": c.get("merchant"), "date": c.get("date"),
                    "amount": c.get("amount"), "currency": c.get("currency"), "status": d["status"],
                    "flags": [f["code"] for f in d["review_flags"]], "expected_kind": ekind, "expected_profile": eprof,
                    "expectation_source": src, "report_row": rows0.get(rel, {}).get("status")})
    print(f"  {label:18} cat={c.get('category'):9} kind={c.get('document_kind')!s:18} profile={c.get('field_profile')!s:11} "
          f"amount={c.get('amount')} status={d['status']} flags={[f['code'] for f in d['review_flags']]}")
print()
record("G1", "G", "scan + preview", "no file written or changed", "unchanged" if tree() == before else "CHANGED", tree() == before, "Dev 1")

# ---------------------------------------------------------------- per-kind classification (A-E)
for tid, label, scen in (("A1", "receipt", "A"), ("B1", "birth_certificate", "B"), ("B1b", "drivers_license", "B"),
                         ("C1", "bank_statement", "C"), ("C1b", "card_statement", "C"), ("D1", "legal", "D"),
                         ("D2", "medical", "D"), ("E1", "uncertain_note", "E"), ("X1", "utility_bill", "decision")):
    rel, ekind, eprof, src = DOCS[label]
    c = cls(label)
    ok = c.get("document_kind") == ekind and c.get("field_profile") == eprof
    record(tid, scen, f"{rel} classification", f"kind={ekind}, profile={eprof} [{src}]",
           f"kind={c.get('document_kind')}, profile={c.get('field_profile')}, category={c.get('category')}", ok,
           "Dev 2 (classifier)" if c.get("document_kind") != ekind else "Dev 1 (profile derivation)")

for tid, label in (("B2", "birth_certificate"), ("B2b", "drivers_license"), ("C2", "bank_statement"), ("C2b", "card_statement"),
                   ("D3", "legal"), ("D4", "medical")):
    c = cls(label)
    invented = {k: c.get(k) for k in TX_FIELDS if c.get(k) not in (None, "")}
    record(tid, "B/C/D", f"{DOCS[label][0]} transaction fields in API response",
           "merchant/date/amount/currency all null (no invented values)", invented or "all null", not invented, "Dev 2 / Dev 1",
           note="flag transaction_fields_on_non_transactional present" if any(f["code"] == "transaction_fields_on_non_transactional" for f in docs[DOCS[label][0]]["review_flags"]) else "")

for tid, label in (("B3", "birth_certificate"), ("C3", "bank_statement"), ("C3b", "card_statement"), ("D5", "legal"), ("D6", "medical")):
    rel = DOCS[label][0]
    d = docs[rel]
    record(tid, "B/C/D", f"{rel} needs an explicit decision", "status needs_review (blocks approval until decided)",
           d["status"], d["status"] == "needs_review", "Dev 1")

non_tx = [DOCS[l][0] for l in ("birth_certificate", "drivers_license", "bank_statement", "card_statement", "legal", "medical")]
leaked = [r for r in non_tx if r in rows0]
record("C4", "C/G", "initial plan report rows", "no report row for statement/identity/legal/medical", leaked or "none", not leaked, "Dev 1")
r_receipt = rows0.get(DOCS["receipt"][0])
record("A2", "A", "receipt report row", "accepted row PHP 683.20",
       f"{r_receipt and r_receipt['status']} {r_receipt and r_receipt['amount']} {r_receipt and r_receipt['currency']}",
       bool(r_receipt) and r_receipt["status"] == "accepted" and r_receipt["amount"] == "683.20", "Dev 1 / Dev 2")

# ---------------------------------------------------------------- F: contradictions + trust boundary (each must leave the record unchanged)
def must_reject(tid, label, body, why):
    before_doc = doc_now(label)
    st, resp = http("PATCH", f"/api/documents/{fid[label]}", body)
    after_doc = doc_now(label)
    ok = st == 422 and after_doc == before_doc
    record(tid, "F", f"PATCH {DOCS[label][0]} {json.dumps(body)}", f"HTTP 422 ({why}); record unchanged",
           f"HTTP {st} {resp if isinstance(resp, str) else resp.get('detail')}; record {'unchanged' if after_doc == before_doc else 'CHANGED'}",
           ok, "Dev 1")


must_reject("F1", "birth_certificate", {"amount": "100.00", "accept": True}, "transaction field on profile none")
must_reject("F2", "birth_certificate", {"merchant": "City Registry", "date": "2026-10-01"}, "transaction fields on profile none")
must_reject("F3", "bank_statement", {"amount": "5391.06", "currency": "PHP", "accept": True}, "statement is not one expense")
must_reject("F4", "medical", {"field_profile": "transaction"}, "backend-controlled field")
must_reject("F5", "legal", {"destination_relative_path": "../../escape.pdf"}, "backend-controlled field")
must_reject("F6", "birth_certificate", {"document_kind": "receipt"}, "kind is not client-editable")
must_reject("F7", "receipt", {"editable_fields": ["amount"], "accept": True}, "backend-controlled field")

# F8: category switch to a transaction category on a non-transactional record (contract: reject contradictory combinations)
before_doc = doc_now("drivers_license")
st, resp = http("PATCH", f"/api/documents/{fid['drivers_license']}", {"category": "receipt", "accept": True})
after_doc = doc_now("drivers_license")
record("F8", "F", f"PATCH {DOCS['drivers_license'][0]} {{category: receipt, accept: true}}",
       "rejected as contradictory (identity_or_civil cannot be filed as a receipt); record unchanged",
       f"HTTP {st}; category now {(after_doc.get('classification') or {}).get('category')}, profile {(after_doc.get('classification') or {}).get('field_profile')}, status {after_doc['status']}",
       st == 422 and after_doc == before_doc, "Dev 1",
       note="Not rejected: only merchant/date/amount/currency are checked against the profile." if st != 422 else "")

# F9 (positive control): receipt keeps the transaction correction flow
st, resp = http("PATCH", f"/api/documents/{fid['receipt']}", {"merchant": "Sunbeam Cafe", "amount": "683.20", "currency": "PHP", "accept": True})
rc = (resp or {}).get("classification") or {} if isinstance(resp, dict) else {}
record("A3", "A", "PATCH receipt {merchant, amount, currency, accept}", "HTTP 200; values kept; profile stays transaction",
       f"HTTP {st}; merchant={rc.get('merchant')} amount={rc.get('amount')} profile={rc.get('field_profile')}",
       st == 200 and rc.get("amount") == "683.20" and rc.get("field_profile") == "transaction", "Dev 1")

# ---------------------------------------------------------------- B/C/D/E: explicit decisions (frontend NON_TRANSACTION_DECISIONS payloads)
FILE = {"category": "other", "accept": True}
LEAVE = {"category": "uncertain", "accept": True}
decisions = {"birth_certificate": FILE, "bank_statement": FILE, "card_statement": FILE, "legal": FILE, "medical": LEAVE}
if cls("uncertain_note").get("field_profile") != "transaction":
    decisions["uncertain_note"] = LEAVE
for label, body in decisions.items():
    st, resp = http("PATCH", f"/api/documents/{fid[label]}", body)
    c = resp.get("classification") or {} if isinstance(resp, dict) else {}
    invented = {k: c.get(k) for k in TX_FIELDS if c.get(k) not in (None, "")}
    record(f"DEC-{label}", "B/C/D/E", f"decision {'file' if body is FILE else 'leave'} on {DOCS[label][0]}",
           "HTTP 200; user_corrected; no transaction values", f"HTTP {st}; status={resp.get('status') if isinstance(resp, dict) else resp}; invented={invented or 'none'}",
           st == 200 and not invented, "Dev 1")

_, plan1 = http("GET", f"/api/scans/{scan_id}/plan")
ops1 = {o["original_relative_path"]: o["destination_relative_path"] for o in plan1["operations"]}
rows1 = {r["source_filename"]: r for r in plan1["report_rows"]}
expect_dest = {"birth_certificate": "Other/", "bank_statement": "Other/", "card_statement": "Other/", "legal": "Other/", "medical": "Needs Review/"}
if "uncertain_note" in decisions:
    expect_dest["uncertain_note"] = "Needs Review/"
for label, prefix in expect_dest.items():
    rel = DOCS[label][0]
    dest = ops1.get(rel, "(no operation)")
    record(f"G2-{label}", "B/C/D/E/G", f"plan destination for {rel} after decision", f"starts with {prefix} (fixed backend map)",
           dest, dest.startswith(prefix) or dest.startswith("GhostOS Organized/" + prefix), "Dev 1")
leaked1 = [r for r in non_tx if r in rows1]
record("G3", "C/G", "report rows after all decisions", "no row for any non-transactional document", leaked1 or "none", not leaked1, "Dev 1")
unmapped = [d for d in ops1.values() if not d.startswith(FIXED_MAP_PREFIXES)]
record("G4", "G", "every planned destination", "from the fixed map (Invoices|Receipts/YYYY-MM, Other, Needs Review, GhostOS Organized/...)",
       unmapped or "all from fixed map", not unmapped, "Dev 1")
totals1 = {t["currency"]: t["amount"] for t in plan1["totals"]}
record("C5", "C", "plan totals after decisions", "statement balances and transactions excluded; receipt counted",
       totals1, all(r not in rows1 or rows1[r]["status"] != "accepted" for r in non_tx), "Dev 1")
record("G5", "G", "after all corrections + plan refresh", "no file written or changed; no approve/undo requested",
       "unchanged" if tree() == before else "CHANGED", tree() == before, "Dev 1")
ub = rows1.get(DOCS["utility_bill"][0])
record("X2", "decision", "utility bill in totals", "ground truth: accepted invoice PHP 3412.75 / contract: utility statement excluded",
       f"kind={cls('utility_bill').get('document_kind')}; report row={ub['status'] if ub else 'none'}", None, "Dev 1 + Dev 4 (decision)",
       note="Contract and ground truth disagree; reported as a decision, not graded.")

# ---------------------------------------------------------------- F: model trust boundary (schema level, no model call)
sys.path.insert(0, str(REPO / "backend"))
from pydantic import ValidationError  # noqa: E402
from app.schemas import ClassificationRecord  # noqa: E402

for tid, payload, why in (("F10", {"category": "other", "document_kind": "medical", "field_profile": "transaction"}, "model-supplied field_profile"),
                          ("F11", {"category": "receipt", "destination_relative_path": "../x.pdf"}, "model-supplied path"),
                          ("F12", {"category": "receipt", "editable_fields": ["amount"]}, "model-supplied field list")):
    try:
        ClassificationRecord.model_validate(payload)
        outcome, ok = "ACCEPTED", False
    except ValidationError:
        outcome, ok = "rejected (ValidationError, extra=forbid)", True
    record(tid, "F", f"model output with {why}", "rejected by ClassificationRecord", outcome, ok, "Dev 1 / Dev 2")
rec = ClassificationRecord.model_validate({"category": "other", "document_kind": "bank_statement"})
record("F13", "F", "model kind alias 'bank_statement'", "normalized to statement, profile reference",
       f"{rec.document_kind}/{rec.field_profile}", rec.document_kind == "statement" and rec.field_profile == "reference", "Dev 1")
rec = ClassificationRecord.model_validate({"category": "invoice", "document_kind": None})
record("F14", "F", "model returns document_kind=null with category=invoice", "safe default (not transaction) OR documented fallback",
       f"profile={rec.field_profile}", None, "Dev 1 (decision)",
       note="Legacy fallback derives 'transaction' from category; a statement labelled invoice with a null kind would be countable. Not observed in this run.")

# ---------------------------------------------------------------- save
(OUT / "acceptance" / "setup_hashes.json").write_text(json.dumps(redact({"root": str(ROOT), "files": setup}), indent=2), encoding="utf-8")
(OUT / "acceptance" / "classification_summary.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")
(OUT / "acceptance" / "plan_initial.json").write_text(json.dumps(redact(plan0), indent=2), encoding="utf-8")
(OUT / "acceptance" / "plan_after_decisions.json").write_text(json.dumps(redact(plan1), indent=2), encoding="utf-8")
(OUT / "acceptance" / "http_log.json").write_text(json.dumps(log, indent=2), encoding="utf-8")
(OUT / "acceptance" / "results.json").write_text(json.dumps(results, indent=2), encoding="utf-8")
counts = {s: sum(r["status"] == s for r in results) for s in ("PASS", "FAIL", "NOT TESTED")}
print(f"\n{counts}  scan={scan_id}  (no approve/undo was requested)")
