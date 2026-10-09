"""Uncategorized retest - Stage 2 setup only. Creates two disposable roots; never deletes or overwrites.

    backend\\.venv\\Scripts\\python.exe tests\\reports\\uncategorized_retest\\scripts\\setup_roots.py
"""
import hashlib
import json
import shutil
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

REPO = Path(__file__).resolve().parents[4]
FIX = REPO / "tests" / "fixtures" / "sample_folder"
OUT = REPO / "tests" / "reports" / "uncategorized_retest"
BASE = Path.home() / "AppData" / "Local" / "Temp" / "ghostos-uncategorized"
CANARY = BASE / "outside-canary" / "canary.txt"

# Unique top-level folders keep every file_id distinct across roots and other clients (D1 workaround).
ROOTS = {
    "A-normal": {
        "inbox-a/receipts/sunbeam-cafe-receipt.pdf": "receipts/sunbeam-cafe-receipt.pdf",      # clear receipt
        "inbox-a/identity/birth-certificate.pdf": "identity/birth-certificate.pdf",            # non-transactional
        "inbox-a/receipts/bayside-office-mart.pdf": "receipts/bayside-office-mart.pdf",        # unresolved review (amount conflict)
        "inbox-a/misc/aircon-payment-note.txt": "misc/aircon-payment-note.txt",                # uncertain / missing date
        "inbox-a/scans/empty-scan.txt": None,                                                  # synthetic unreadable (0 bytes)
    },
    "B-partial": {
        "inbox-b/receipts/sunbeam-cafe-receipt.pdf": "receipts/sunbeam-cafe-receipt.pdf",      # transaction 1
        "inbox-b/receipts/tibay-hardware-receipt.csv": "receipts/tibay-hardware-receipt.csv",  # transaction 2
        "inbox-b/identity/drivers-license-record.txt": "identity/drivers-license-record.txt",  # non-transactional (decided "File it")
        "inbox-b/legal/lease-agreement-summary.pdf": "legal/lease-agreement-summary.pdf",      # non-transactional (left undecided)
        "inbox-b/receipts/bayside-office-mart.pdf": "receipts/bayside-office-mart.pdf",        # unresolved review
    },
}


def sha(p: Path) -> str:
    return hashlib.sha256(p.read_bytes()).hexdigest()


def snapshot(root: Path) -> dict:
    return {
        "files": {p.relative_to(root).as_posix(): {"sha256": sha(p), "size": p.stat().st_size}
                  for p in sorted(root.rglob("*")) if p.is_file()},
        "dirs": sorted(p.relative_to(root).as_posix() for p in root.rglob("*") if p.is_dir()),
    }


targets = [BASE / name for name in ROOTS] + [CANARY.parent, OUT / "setup"]
existing = [str(t) for t in targets if t.exists()]
if existing:
    sys.exit(f"STOP: already exists, refusing to touch: {existing}")

BASE.mkdir(exist_ok=True)
CANARY.parent.mkdir()
CANARY.write_text("outside-root canary for the Uncategorized retest; must never change\n", encoding="utf-8")
(OUT / "setup").mkdir(parents=True)

manifest = {
    "created_at": datetime.now(timezone.utc).isoformat(),
    "commit": subprocess.run(["git", "rev-parse", "HEAD"], cwd=REPO, capture_output=True, text=True).stdout.strip(),
    "base": "<TEST_BASE>",
    "canary_sha256": sha(CANARY),
    "roots": {},
}
for name, files in ROOTS.items():
    root = BASE / name
    root.mkdir()
    for rel, src in files.items():
        dst = root / rel
        dst.parent.mkdir(parents=True, exist_ok=True)
        if src is None:
            dst.write_bytes(b"")
        else:
            shutil.copy2(FIX / src, dst)
            assert sha(dst) == sha(FIX / src)
    manifest["roots"][name] = {"path": f"<TEST_BASE>/{name}", "fixture_source": files, "snapshot": snapshot(root)}
    (OUT / "setup" / f"{name}_snapshot_initial.json").write_text(json.dumps(snapshot(root), indent=2), encoding="utf-8")

(OUT / "setup" / "manifest.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")
print(f"base: {BASE}")
for name, info in manifest["roots"].items():
    print(f"\n[{name}] {BASE / name}")
    for rel, meta in info["snapshot"]["files"].items():
        print(f"  {rel:50} {meta['size']:>6} B  {meta['sha256']}")
print(f"\ncanary: {CANARY} {manifest['canary_sha256'][:16]}")
