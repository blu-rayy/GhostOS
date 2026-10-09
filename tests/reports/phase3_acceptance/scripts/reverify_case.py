"""Re-verify S3/S5/S6 from the tree captured immediately after approval, using
Windows (case-insensitive) path semantics. Reads saved evidence only."""
import json
from pathlib import Path

OUT = Path(r"C:\Users\My PC\Documents\Hackathon\GhostOS\GhostOS\tests\reports\phase3_acceptance")
setup = json.loads((OUT / "00_setup_manifest.json").read_text(encoding="utf-8"))
manifest = {e["relative_path"]: e["sha256"] for e in setup["roots"]["B-acceptance"]["files"]}
plan = json.loads((OUT / "B_03_plan_snapshot_for_approval.json").read_text(encoding="utf-8"))
after = json.loads((OUT / "B_05b_tree_after_approve.json").read_text(encoding="utf-8"))
batch = json.loads((OUT / "B_06_approve_response.json").read_text(encoding="utf-8"))["body"]

files_ci = {k.lower(): (k, v) for k, v in after["files"].items()}
rows, ok_all = [], True
for op in plan["operations"]:
    src, dst = op["original_relative_path"], op["destination_relative_path"]
    actual_path, actual_sha = files_ci.get(dst.lower(), (None, None))
    ok = actual_sha == manifest[src] and src.lower() not in files_ci
    ok_all &= ok
    rows.append({"planned_destination": dst, "actual_path_on_disk": actual_path, "case_matches_plan": actual_path == dst,
                 "sha256_matches_original": actual_sha == manifest[src], "source_removed": src.lower() not in files_ci})
expected_ci = {op["destination_relative_path"].lower() for op in plan["operations"]} | {batch["report_relative_path"].lower()}
unexpected = sorted(k for k in files_ci if k not in expected_ci)
result = {
    "method": "case-insensitive comparison of B_05b_tree_after_approve.json against the approved plan (Windows path semantics)",
    "per_operation": rows,
    "S3_ci": "PASS" if ok_all else "FAIL",
    "S5_ci": "PASS" if all(r["sha256_matches_original"] for r in rows if "greenleaf" in r["planned_destination"]) else "FAIL",
    "S6_ci": "PASS" if not unexpected else "FAIL",
    "unexpected_files_ci": unexpected,
    "case_mismatches": [r for r in rows if not r["case_matches_plan"]],
}
(OUT / "B_10_case_insensitive_reverification.json").write_text(json.dumps(result, indent=2), encoding="utf-8")
for r in rows:
    print(f"{r['planned_destination']:58} -> on disk: {r['actual_path_on_disk']:58} case_ok={r['case_matches_plan']} sha_ok={r['sha256_matches_original']} src_removed={r['source_removed']}")
print(f"\nS3 (case-insensitive): {result['S3_ci']}   S5: {result['S5_ci']}   S6: {result['S6_ci']}  unexpected={unexpected}")
print(f"directories after approve: {after['dirs']}")
