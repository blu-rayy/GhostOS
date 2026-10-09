"""Follow-up probe for F8 (NON-DESTRUCTIVE): effect of a contradictory category correction.

Uses the scan left in memory by document_aware_acceptance.py (pass its scan id).
Only PATCH + GET plan; no approve/undo; verifies the disposable folder is unchanged.

    backend\\.venv\\Scripts\\python.exe tests\\integration\\document_aware_probe_f8.py <scan_id>
"""

import hashlib
import json
import sys
from pathlib import Path
from urllib.error import HTTPError
from urllib.request import Request, urlopen

REPO = Path(__file__).resolve().parents[2]
ROOT = Path.home() / "AppData" / "Local" / "Temp" / "ghostos-docaware" / "R1"
OUT = REPO / "tests" / "reports" / "document_aware_review" / "acceptance" / "probe_f8.json"
BASE_URL = "http://127.0.0.1:8000"
TARGET = "misc/card-statement-sep2026.pdf"


def http(method, path, body=None):
    req = Request(BASE_URL + path, data=json.dumps(body).encode() if body is not None else None, method=method,
                  headers={"Content-Type": "application/json"})
    try:
        with urlopen(req, timeout=120) as r:
            return r.status, json.loads(r.read() or b"null")
    except HTTPError as e:
        return e.code, json.loads(e.read() or b"null")


def tree():
    return {p.relative_to(ROOT).as_posix(): hashlib.sha256(p.read_bytes()).hexdigest() for p in sorted(ROOT.rglob("*")) if p.is_file()}


if OUT.exists():
    sys.exit(f"STOP: {OUT} exists")
scan_id = sys.argv[1]
before = tree()
_, scan = http("GET", f"/api/scans/{scan_id}")
doc = next(d for d in scan["documents"] if d["relative_path"] == TARGET)
st, patched = http("PATCH", f"/api/documents/{doc['file_id']}", {"category": "invoice", "accept": True})
_, plan = http("GET", f"/api/scans/{scan_id}/plan")
dest = next((o["destination_relative_path"] for o in plan["operations"] if o["original_relative_path"] == TARGET), None)
row = next((r for r in plan["report_rows"] if r["source_filename"] == TARGET), None)
dl = next((o["destination_relative_path"] for o in plan["operations"] if o["original_relative_path"] == "identity/drivers-license-record.txt"), None)
result = {
    "patch": {"target": TARGET, "body": {"category": "invoice", "accept": True}, "status": st,
              "classification_after": {k: (patched.get("classification") or {}).get(k) for k in ("category", "document_kind", "field_profile", "date", "amount", "currency")}},
    "card_statement_destination": dest,
    "card_statement_report_row": row,
    "drivers_license_destination_after_F8": dl,
    "totals": plan["totals"],
    "folder_unchanged": tree() == before,
}
OUT.write_text(json.dumps(result, indent=2), encoding="utf-8")
print(json.dumps(result, indent=2))
