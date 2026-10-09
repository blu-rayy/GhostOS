"""Leave-for-review STATE retest - Stage 5 (human-approved): guarded partial approval of plan_scan_1d788bbc1289, verify, undo, verify.

Stops (no approval / no undo) on any precondition mismatch. No deletes, no repairs.

    backend\\.venv\\Scripts\\python.exe -B tests\\reports\\leave_for_review_state_retest\\scripts\\stage5_approve_undo.py
"""
import hashlib
import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path
from urllib.error import HTTPError
from urllib.request import Request, urlopen

sys.dont_write_bytecode = True
REPO = Path(__file__).resolve().parents[4]
OUT = REPO / "tests" / "reports" / "leave_for_review_state_retest"
EV = OUT / "stage5"
BASE = Path.home() / "AppData" / "Local" / "Temp" / "ghostos-leave-state"
ROOT = BASE / "LS1"
MROOT = BASE / "LS1-inprocess"
CANARY = BASE / "outside-canary" / "canary.txt"
API = "http://127.0.0.1:8000"
SCAN, PLAN = "scan_1d788bbc1289", "plan_scan_1d788bbc1289"
BAY, LEASE = "ls/receipts/bayside-office-mart.pdf", "ls/legal/lease-agreement-summary.pdf"
BIRTH, SUN = "ls/identity/birth-certificate.pdf", "ls/receipts/sunbeam-cafe-receipt.pdf"
EXPECTED_OPS = {BAY: "Uncategorized/bayside-office-mart.pdf", LEASE: "Uncategorized/lease-agreement-summary.pdf",
                BIRTH: "Other/birth-certificate.pdf", SUN: "Receipts/2026-09/sunbeam-cafe-receipt.pdf"}
EXPECTED_ROW = ["ls/receipts/sunbeam-cafe-receipt.pdf", "SUNBEAM CAFE", "2026-09-21", "receipt", "683.20", "PHP"]
log, results = [], []


def sha(p): return hashlib.sha256(p.read_bytes()).hexdigest()


def snap(root):
    return {p.relative_to(root).as_posix(): {"sha256": sha(p), "size": p.stat().st_size} for p in sorted(root.rglob("*")) if p.is_file()}


def dirs(root): return sorted(p.relative_to(root).as_posix() for p in root.rglob("*") if p.is_dir())


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


def save(name, obj):
    EV.mkdir(parents=True, exist_ok=True)
    (EV / name).write_text(json.dumps(redact(obj), indent=2), encoding="utf-8")


def rec(tid, check, expected, actual, ok):
    status = ok if isinstance(ok, str) else ("PASS" if ok else "FAIL")
    results.append({"id": tid, "check": check, "expected": expected, "actual": actual, "status": status})
    print(f"[{status}] {tid} {check}\n      expected: {expected}\n      actual:   {actual}")
    return status == "PASS"


def finish(msg=None):
    save("http_log.json", log)
    (EV / "results.json").write_text(json.dumps(results, indent=2), encoding="utf-8")
    c = {}
    for r in results:
        c[r["status"]] = c.get(r["status"], 0) + 1
    print(f"\n{c}" + (f"\n{msg}" if msg else ""))
    sys.exit(1 if msg else 0)


def exact_case(root, rel):
    cur = root
    for part in rel.split("/"):
        if part not in os.listdir(cur):
            return False
        cur = cur / part
    return cur.is_file()


def state(d):
    return {"status": d["status"], "review_disposition": d.get("review_disposition"), "user_corrected": d["user_corrected"],
            "flags": [f["code"] for f in d["review_flags"]], "category": (d.get("classification") or {}).get("category")}


if EV.exists():
    sys.exit(f"STOP: {EV} exists")
manifest = json.loads((OUT / "setup" / "manifest.json").read_text(encoding="utf-8"))
before = json.loads((OUT / "state_before_corrections.json").read_text(encoding="utf-8"))
reviewed = json.loads((OUT / "plan_partial_for_review.json").read_text(encoding="utf-8"))
mfst, inproc_mfst, canary_sha = manifest["snapshot"], manifest["inprocess_snapshot"], manifest["canary_sha256"]

# ---------------- preconditions ----------------
_, plan = http("GET", f"/api/scans/{SCAN}/plan?mode=partial")
save("plan_refetched.json", plan)
ops = {o["original_relative_path"]: o["destination_relative_path"] for o in plan["operations"]}
ok = [rec("A1", "Re-fetched plan matches reviewed plan", f"scan {SCAN}; plan {PLAN}; partial; blocking 2; 4 ops {EXPECTED_OPS}",
          f"scan {plan.get('scan_id')}; plan {plan.get('plan_id')}; {plan.get('mode')}; blocking {plan.get('blocking_review_count')}; {ops}",
          plan.get("scan_id") == SCAN and plan.get("plan_id") == PLAN and plan.get("mode") == "partial" and plan.get("blocking_review_count") == 2
          and ops == EXPECTED_OPS and plan["operations"] == reviewed["operations"] and plan["report_rows"] == reviewed["report_rows"]
          and plan["totals"] == reviewed["totals"])]
_, scan = http("GET", f"/api/scans/{SCAN}")
save("scan_before_approve.json", scan)
docs = {d["relative_path"]: d for d in scan["documents"]}
st = {k: state(d) for k, d in docs.items()}
ok.append(rec("A2", "Left-for-review documents unchanged", "leave_for_review / needs_review / original flags",
              {k: st[k] for k in (BAY, LEASE)},
              all(st[k]["review_disposition"] == "leave_for_review" and st[k]["status"] == "needs_review" and st[k]["flags"] == before[k]["flags"] for k in (BAY, LEASE))))
ok.append(rec("A3", "Birth certificate filed; receipt accepted", "birth: filed/ok/other -> Other/; Sunbeam: ok, accepted row",
              {BIRTH: st[BIRTH], SUN: st[SUN], "rows": [(r["source_filename"], r["status"]) for r in plan["report_rows"]]},
              st[BIRTH]["review_disposition"] == "filed" and st[BIRTH]["status"] == "ok" and ops[BIRTH] == EXPECTED_OPS[BIRTH]
              and st[SUN]["status"] == "ok" and [(r["source_filename"], r["status"]) for r in plan["report_rows"]] == [(SUN, "accepted")]))
cur = snap(ROOT)
ok.append(rec("A4", "Original hashes", "4 files match setup manifest; no other files in root", "match" if cur == mfst else cur, cur == mfst))
free = {d: not (ROOT / d).exists() for d in EXPECTED_OPS.values()}
contained = all((ROOT / d).resolve().is_relative_to(ROOT.resolve()) for d in EXPECTED_OPS.values())
ok.append(rec("A5", "Destinations free and contained", "all destinations absent; all inside root; no GhostOS Reports yet",
              {"free": free, "contained": contained, "reports_dir": (ROOT / "GhostOS Reports").exists()},
              all(free.values()) and contained and not (ROOT / "GhostOS Reports").exists()))
ok.append(rec("A6", "Outside-root canary and in-process copy", "unchanged", f"canary {'unchanged' if sha(CANARY) == canary_sha else 'CHANGED'}; "
              f"in-process {'unchanged' if snap(MROOT) == inproc_mfst else 'CHANGED'}", sha(CANARY) == canary_sha and snap(MROOT) == inproc_mfst))
if not all(ok):
    finish("STOP: precondition mismatch - no approval sent")

# ---------------- approve once ----------------
print(f"\n=== APPROVE {PLAN} mode=partial ===")
code, ap = http("POST", f"/api/plans/{PLAN}/approve", {"mode": "partial"})
save("approve_response.json", {"status": code, "body": ap})
batch = ap.get("batch_id") if isinstance(ap, dict) else None
if not rec("V0", "Approval accepted", "HTTP 200 with batch_id", f"HTTP {code}; batch {batch}", code == 200 and bool(batch)):
    finish("STOP: approval failed - no undo attempted")

after = snap(ROOT)
save("snapshot_after_approve.json", {"files": after, "dirs": dirs(ROOT)})
case_ok = {d: exact_case(ROOT, d) for d in EXPECTED_OPS.values()}
rec("V1", "Exact-case destinations exist", "all 4 True", case_ok, all(case_ok.values()))
hash_ok = {s: after.get(d, {}).get("sha256") == mfst[s]["sha256"] for s, d in EXPECTED_OPS.items()}
rec("V2", "Destination hashes equal setup manifest (no overwrite, byte-identical)", "all 4 True", hash_ok, all(hash_ok.values()))
gone = {s: not (ROOT / s).exists() for s in EXPECTED_OPS}
src_dirs = sorted({str(Path(s).parent.as_posix()) for s in EXPECTED_OPS})
left = [p for p in after if any(p.startswith(d + "/") for d in src_dirs)]
rec("V3", "No organized files left in source paths/directories", "originals gone; no files under ls/", {"originals_gone": gone, "files_under_source_dirs": left},
    all(gone.values()) and not left)
csvs = sorted(p for p in after if p.startswith("GhostOS Reports/"))
extra = sorted(set(after) - set(EXPECTED_OPS.values()) - set(csvs))
rec("V4", "Only expected files in root", "4 destinations + 1 report CSV", {"csvs": csvs, "unexpected": extra}, len(csvs) == 1 and not extra)
rows = []
if csvs:
    raw = (ROOT / csvs[0]).read_bytes()
    text = raw.decode("utf-8-sig")
    (EV / "report_csv_copy.csv").write_bytes(raw)
    rows = [line.split(",") for line in text.splitlines()]
rec("V5", "CSV contains exactly the Sunbeam row", f"header + {EXPECTED_ROW}", rows,
    rows == [["source_file", "merchant", "date", "category", "amount", "currency"], EXPECTED_ROW])
leave_in_csv = any(BAY in r or LEASE in r or "bayside" in ",".join(r).lower() or "lease" in ",".join(r).lower() for r in rows)
_, scan2 = http("GET", f"/api/scans/{SCAN}")
save("scan_after_approve.json", scan2)
st2 = {d["file_id"]: state(d) for d in scan2["documents"]}
unres = {k: st2[docs[k]["file_id"]] for k in (BAY, LEASE)}
rec("V6", "Left-for-review documents remain unresolved and are absent from CSV", "needs_review / leave_for_review / flags kept; not in CSV",
    {"states": unres, "in_csv": leave_in_csv},
    not leave_in_csv and all(v["status"] == "needs_review" and v["review_disposition"] == "leave_for_review" and v["flags"] == before[k]["flags"] for k, v in unres.items()))
rec("V7", "No out-of-root writes", "canary + in-process copy unchanged; base holds only LS1, LS1-inprocess, outside-canary",
    {"canary": sha(CANARY) == canary_sha, "inprocess": snap(MROOT) == inproc_mfst, "base": sorted(os.listdir(BASE))},
    sha(CANARY) == canary_sha and snap(MROOT) == inproc_mfst and sorted(os.listdir(BASE)) == ["LS1", "LS1-inprocess", "outside-canary"])
if any(r["status"] != "PASS" for r in results):
    finish("STOP: post-approval check failed - undo NOT attempted")

# ---------------- undo ----------------
print(f"\n=== UNDO {batch} ===")
code, un = http("POST", f"/api/batches/{batch}/undo")
save("undo_response.json", {"status": code, "body": un})
rec("U0", "Undo accepted", "HTTP 200", f"HTTP {code}", code == 200)
fin = snap(ROOT)
save("snapshot_after_undo.json", {"files": fin, "dirs": dirs(ROOT)})
restored = {s: fin.get(s, {}).get("sha256") == m["sha256"] for s, m in mfst.items()}
rec("U1", "All four original paths and hashes restored", "all 4 True", restored, all(restored.values()))
rec("U2", "Destinations vacated", "no file at any destination", {d: (ROOT / d).exists() for d in EXPECTED_OPS.values()},
    not any((ROOT / d).exists() for d in EXPECTED_OPS.values()))
leftover_files = sorted(set(fin) - set(mfst))
empty_dirs = [d for d in dirs(ROOT) if not any((ROOT / d).iterdir())]
rec("U3", "Leftover CSV after undo (known behaviour, recorded separately)", "only the report CSV remains", leftover_files,
    leftover_files == csvs)
rec("U4", "Empty folders after undo (known behaviour, recorded separately)", "recorded", empty_dirs, "PASS")
rec("U5", "Canary and in-process copy unchanged after undo", "unchanged",
    {"canary": sha(CANARY) == canary_sha, "inprocess": snap(MROOT) == inproc_mfst}, sha(CANARY) == canary_sha and snap(MROOT) == inproc_mfst)
print(f"\nbatch {batch}")
finish()
