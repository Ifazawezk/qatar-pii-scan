"""Text and JSON reports. Only masked values ever reach these."""
from __future__ import annotations

import json

from . import __version__
from .scanner import Report

LAW = "Law No. 13 of 2016 on Protecting Personal Data Privacy"
NOTE = ("qatar-pii-scan points at data that looks personal. It is not a compliance check or a legal "
        f"opinion under {LAW} or any other law.")


def summary(report: Report) -> str:
    c = report.counts()
    with_hits = len({f.path for f in report.findings})
    return (f"{len(report.findings)} findings in {with_hits} of {len(report.files)} files: "
            f"{c['high']} high, {c['medium']} medium, {c['low']} low")


def to_text(report: Report) -> str:
    rows = [(f.path, f.where, f.kind, f.masked, f.confidence) for f in report.findings]
    lines = []
    if rows:
        widths = [max(len(r[i]) for r in rows) for i in range(4)]
        for r in rows:
            lines.append("  ".join(cell.ljust(w) for cell, w in zip(r[:4], widths)) + "  " + r[4])
        lines.append("")
    for path, why in report.skipped:
        lines.append(f"skipped {path}: {why}")
    lines.append(summary(report))
    return "\n".join(lines)


def to_json(report: Report) -> str:
    return json.dumps({
        "tool": "qatar-pii-scan",
        "version": __version__,
        "files_scanned": len(report.files),
        "counts": report.counts(),
        "findings": [f.to_dict() for f in report.findings],
        "skipped": [{"path": p, "reason": r} for p, r in report.skipped],
        "note": NOTE,
    }, ensure_ascii=False, indent=2)
