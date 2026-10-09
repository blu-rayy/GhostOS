"""Phase 3 acceptance, Stage 2: create disposable test roots (never deletes or overwrites)."""
import hashlib
import json
import platform
import shutil
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

REPO = Path(r"C:\Users\My PC\Documents\Hackathon\GhostOS\GhostOS")
FIXTURES = REPO / "tests" / "fixtures" / "sample_folder"
TRUTH = json.loads((REPO / "tests/fixtures/expected_results/ground_truth.json").read_text(encoding="utf-8"))
BASE = Path(r"C:\Users\My PC\AppData\Local\Temp\ghostos-phase3")
REPORT_DIR = REPO / "tests" / "reports" / "phase3_acceptance"

ROOTS = {
    "A-blocker": ["receipts/bayside-office-mart.pdf", "receipts/tibay-hardware-receipt.csv"],
    "B-acceptance": [
        "inbox/invoice.pdf",
        "archive/2026/invoice.pdf",
        "receipts/sunbeam-cafe-receipt.pdf",
        "receipts/greenleaf-grocer-2026-09-14.txt",
        "downloads/greenleaf-grocer-2026-09-14 (1).txt",
    ],
}
CANARY = BASE / "outside-canary" / "canary.txt"


def sha256(p: Path) -> str:
    return hashlib.sha256(p.read_bytes()).hexdigest()


# Safety: refuse if anything we would create already exists.
targets = [BASE, REPORT_DIR]
existing = [str(t) for t in targets if t.exists()]
if existing:
    sys.exit(f"STOP: already exists, refusing to touch: {existing}")
if REPO in BASE.parents or BASE == REPO:
    sys.exit("STOP: test base is inside the repository")

BASE.mkdir(parents=False)
REPORT_DIR.mkdir(parents=False)
CANARY.parent.mkdir()
CANARY.write_text("outside-root canary; must never change\n", encoding="utf-8")

truth_by_name = {f["filename"]: f for f in TRUTH["files"]}
manifest = {
    "created_at": datetime.now(timezone.utc).isoformat(),
    "base": "<TEST_BASE>",
    "host": platform.platform(),
    "repo_commit": subprocess.run(["git", "rev-parse", "--short", "HEAD"], cwd=REPO, capture_output=True, text=True).stdout.strip(),
    "canary": {"path": "<TEST_BASE>/outside-canary/canary.txt", "sha256": sha256(CANARY)},
    "roots": {},
}
for root_name, files in ROOTS.items():
    root = BASE / root_name
    root.mkdir()
    entries = []
    for rel in files:
        src, dst = FIXTURES / rel, root / rel
        if dst.exists():
            sys.exit(f"STOP: destination exists: {dst}")
        dst.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(src, dst)
        if sha256(src) != sha256(dst):
            sys.exit(f"STOP: copy mismatch for {rel}")
        t = truth_by_name[rel]
        entries.append({
            "relative_path": rel,
            "size_bytes": dst.stat().st_size,
            "sha256": sha256(dst),
            "expected": {k: t[k] for k in (
                "expected_category", "expected_merchant", "expected_date", "expected_amount",
                "expected_currency", "expected_review_required", "duplicate_group", "collision_group")},
        })
    manifest["roots"][root_name] = {"path": f"<TEST_BASE>/{root_name}", "files": entries}

(REPORT_DIR / "00_setup_manifest.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")
print(f"base: {BASE}")
for root_name, info in manifest["roots"].items():
    print(f"\n[{root_name}]  {BASE / root_name}")
    for e in info["files"]:
        print(f"  {e['relative_path']:46} {e['size_bytes']:>6} B  sha256 {e['sha256'][:16]}...")
print(f"\ncanary: {CANARY}  sha256 {manifest['canary']['sha256'][:16]}...")
print(f"manifest: {REPORT_DIR / '00_setup_manifest.json'}")
