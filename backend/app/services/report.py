"""Expense report CSV writer.

The backend owns this CSV. Its format mirrors the frontend's export
(frontend/src/lib/report.ts) so a report written on approve and one exported
from the UI are byte-compatible: header, accepted rows only, CRLF line endings,
formula-injection neutralisation, and quoting.
"""

from __future__ import annotations

from pathlib import Path

from app.services.session_store import ReportRow

HEADER = ["source_file", "merchant", "date", "category", "amount", "currency"]


def _csv_cell(value: str | None) -> str:
    if value is None:
        return ""
    # Neutralise spreadsheet formula injection, then quote when needed.
    safe = f"'{value}" if value[:1] in ("=", "+", "-", "@", "\t", "\r") else value
    if any(ch in safe for ch in ('"', ",", "\n", "\r")):
        return '"' + safe.replace('"', '""') + '"'
    return safe


def to_csv(rows: list[ReportRow]) -> str:
    """Serialize accepted report rows as CSV text (no trailing newline gap)."""
    lines = [",".join(HEADER)]
    for row in rows:
        if row.status != "accepted":
            continue
        lines.append(
            ",".join(
                _csv_cell(v)
                for v in (
                    row.source_filename,
                    row.merchant,
                    row.date,
                    row.category,
                    row.amount,
                    row.currency,
                )
            )
        )
    return "\r\n".join(lines) + "\r\n"


def write_report(root: Path, report_relative_path: str, rows: list[ReportRow]) -> Path:
    """Write the expense CSV relative to the scan root and return the target path."""
    target = root / report_relative_path
    target.parent.mkdir(parents=True, exist_ok=True)
    # BOM for Excel UTF-8 compatibility, matching the frontend export behaviour.
    with open(target, "w", encoding="utf-8", newline="") as f:
        f.write("\ufeff" + to_csv(rows))
    return target
