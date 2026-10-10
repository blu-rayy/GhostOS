"""Copy a short, curated subset of sample_folder/ into a messy demo folder.

The full 28-file sample takes about 3 minutes to read on a 4 GB laptop GPU. This
9-file set reads in about a minute and still shows every story beat: receipts and
invoices, two currencies kept apart, amounts that disagree, a prompt injection,
and important papers (birth certificate, two passports, a land title) that are
filed without ever reaching the totals.

Files are copied byte for byte from sample_folder/, so ground_truth.json still
describes them; only the folder layout and one filename differ.

Usage (from the repository root):
    py tests/fixtures/make_demo_folder.py                         # -> %USERPROFILE%\\Documents\\GhostOS Demo
    py tests/fixtures/make_demo_folder.py --out "D:\\Demo folder"

It never deletes or overwrites. If the target already exists, delete it (or use
"Put files back" in GhostOS) and run again. Never point GhostOS at sample_folder/ itself.
"""

from __future__ import annotations

import argparse
import shutil
import sys
from pathlib import Path

SAMPLE_DIR = Path(__file__).resolve().parent / "sample_folder"

# demo path -> sample_folder path. Ordered as a story: money first, then the traps,
# then the important papers.
DEMO_FILES: dict[str, str] = {
    "Downloads/sunbeam-cafe-receipt.pdf": "receipts/sunbeam-cafe-receipt.pdf",
    "Downloads/INV-1043_Pixelforge_Studio.pdf": "invoices/INV-1043_Pixelforge_Studio.pdf",
    "Downloads/scan_0042.pdf": "downloads/scan_0042.pdf",
    "Desktop/kestrel-cowork-KC-7781.pdf": "invoices/kestrel-cowork-KC-7781.pdf",
    "Desktop/bayside-office-mart.pdf": "receipts/bayside-office-mart.pdf",
    "Desktop/README_FIRST.txt": "notes/README_FIRST.txt",
    "Documents/birth-certificate.pdf": "identity/birth-certificate.pdf",
    "Documents/passport-details.txt": "important/passport-details.txt",
    "Documents/IMPORTANT - land title TCT-T-458812.pdf": "important/IMPORTANT - land title TCT-T-458812.pdf",
}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("--out", type=Path, default=Path.home() / "Documents" / "GhostOS Demo")
    args = parser.parse_args()
    out: Path = args.out.resolve()

    if out == SAMPLE_DIR or SAMPLE_DIR in out.parents:
        print(f"Refusing to write inside {SAMPLE_DIR}.")
        return 1
    if out.exists():
        print(f"{out} already exists. Delete it (or put the files back in GhostOS) and run again.")
        return 1

    for dest, src in DEMO_FILES.items():
        target = out / dest
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(SAMPLE_DIR / src, target)
    print(f"Wrote {len(DEMO_FILES)} files to {out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
