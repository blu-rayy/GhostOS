"""Expense report CSV writer.

The backend owns this CSV. Its format mirrors the frontend's export
(frontend/src/lib/report.ts) so a report written on approve and one exported
from the UI are byte-compatible: header, accepted rows only, CRLF line endings,
formula-injection neutralisation, and quoting.
"""

from __future__ import annotations

import os
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


def render_report(rows: list[ReportRow]) -> str:
    """Render the complete report payload without touching the filesystem."""
    return "\ufeff" + to_csv(rows)


def reserve_report_path(root: Path, preferred_relative_path: str) -> str:
    """Reserve a unique final report path without overwriting an old report."""
    preferred = Path(preferred_relative_path)
    parent = root / preferred.parent
    parent.mkdir(parents=True, exist_ok=True)
    stem = preferred.stem
    suffix = preferred.suffix

    for number in range(1, 1000):
        name = f"{stem}{suffix}" if number == 1 else f"{stem} ({number}){suffix}"
        candidate = parent / name
        try:
            fd = os.open(str(candidate), os.O_CREAT | os.O_EXCL | os.O_WRONLY)
        except FileExistsError:
            continue
        else:
            os.close(fd)
            return (preferred.parent / name).as_posix()
    raise FileExistsError("Could not reserve a unique report path")


def write_report_temp(root: Path, temp_relative_path: str, content: str) -> Path:
    """Write and fsync report content to a temporary file in its final directory."""
    target = root / temp_relative_path
    target.parent.mkdir(parents=True, exist_ok=True)
    with open(target, "w", encoding="utf-8", newline="") as stream:
        stream.write(content)
        stream.flush()
        os.fsync(stream.fileno())
    return target


def publish_report(root: Path, temp_relative_path: str, report_relative_path: str) -> Path:
    """Atomically publish a prepared report into its reserved final path."""
    temp = root / temp_relative_path
    target = root / report_relative_path
    if not temp.is_file():
        raise FileNotFoundError("Prepared report file is missing")
    # The final path is reserved by reserve_report_path. A non-empty file here
    # means the reservation was replaced externally; never overwrite it.
    if target.exists() and target.stat().st_size != 0:
        raise FileExistsError("Reserved report path is no longer available")
    os.replace(str(temp), str(target))
    return target


def discard_report_reservation(root: Path, temp_relative_path: str, report_relative_path: str) -> None:
    """Remove only this batch's un-published temporary/reserved report files."""
    temp = root / temp_relative_path
    target = root / report_relative_path
    if temp.exists():
        temp.unlink()
    if target.exists() and target.stat().st_size == 0:
        target.unlink()


def write_report(root: Path, report_relative_path: str, rows: list[ReportRow]) -> Path:
    """Write a report using the safe temporary-file publication workflow."""
    reserved = reserve_report_path(root, report_relative_path)
    temp_relative = (Path(reserved).parent / f".{Path(reserved).name}.tmp").as_posix()
    write_report_temp(root, temp_relative, render_report(rows))
    return publish_report(root, temp_relative, reserved)
