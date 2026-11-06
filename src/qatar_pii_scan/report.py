"""Text, JSON, SARIF and HTML reports. Only masked values ever reach these."""
from __future__ import annotations

import hashlib
import json
from collections import Counter, defaultdict
from html import escape
from pathlib import PurePosixPath, PureWindowsPath
from urllib.parse import quote

from . import __version__
from .detectors import KINDS
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


SARIF_LEVEL = {"high": "error", "medium": "warning", "low": "note"}
RULE_HELP = {
    "iban": "A Qatar IBAN with valid MOD 97 check digits (low confidence when the check digits fail).",
    "email": "An email address (low confidence for reserved example domains).",
    "qid": "11 digits in the Qatar ID layout: century digit, birth year, nationality code, serial.",
    "phone": "A Qatar phone number: +974 or 974 and 8 digits starting with 3, 4, 5, 6 or 7.",
    "passport": "A passport-like number next to the word passport or جواز.",
    "name": "A possible person name. A heuristic, always low confidence.",
}


def _uri(path: str) -> dict:
    if PurePosixPath(path).is_absolute() or PureWindowsPath(path).is_absolute():
        return {"uri": "file:///" + quote(path.lstrip("/"))}
    return {"uri": quote(path), "uriBaseId": "%SRCROOT%"}


def to_sarif(report: Report) -> str:
    kinds = list(KINDS)
    rules = [{
        "id": f"qpii/{kind}",
        "name": KINDS[kind].title().replace(" ", "").replace("-", ""),
        "shortDescription": {"text": f"{KINDS[kind]} in the file"},
        "fullDescription": {"text": RULE_HELP[kind]},
        "help": {"text": RULE_HELP[kind] + " Remove it, mask it, or add it to .qpii-allow if it is expected."},
        "defaultConfiguration": {"level": "warning"},
        "properties": {"tags": ["privacy", "personal-data"]},
    } for kind in kinds]
    results = []
    for f in report.findings:
        region = {"startLine": f.line or 1}
        if f.column:
            region.update(startColumn=f.column, endColumn=f.end_column)
        location: dict = {"physicalLocation": {"artifactLocation": _uri(f.path), "region": region}}
        if f.line is None:
            location["logicalLocations"] = [{"fullyQualifiedName": f.where, "kind": "element"}]
        fingerprint = hashlib.sha256(f"{f.path}|{f.kind}|{f.where}|{f.masked}".encode("utf-8")).hexdigest()
        results.append({
            "ruleId": f"qpii/{f.kind}",
            "ruleIndex": kinds.index(f.kind),
            "level": SARIF_LEVEL[f.confidence],
            "message": {"text": f"{f.label} {f.masked} at {f.where} ({f.confidence} confidence: {f.reason})"},
            "locations": [location],
            "partialFingerprints": {"qpiiFinding/v1": fingerprint[:32]},
            "properties": {"confidence": f.confidence},
        })
    return json.dumps({
        "$schema": "https://json.schemastore.org/sarif-2.1.0.json",
        "version": "2.1.0",
        "runs": [{
            "tool": {"driver": {"name": "qatar-pii-scan", "version": __version__, "rules": rules}},
            "columnKind": "unicodeCodePoints",
            "results": results,
        }],
    }, ensure_ascii=False, indent=2)


CSS = """
:root { --bg: #fcfcfa; --fg: #1f2428; --muted: #5d6870; --line: #e0e3e6; --high: #b3261e; --medium: #9a5b00; --low: #4f6b8a; }
@media (prefers-color-scheme: dark) {
  :root { --bg: #16191c; --fg: #e5e7e9; --muted: #9ba6ae; --line: #2d3338; --high: #f28b82; --medium: #f2b866; --low: #9fbadb; }
}
body { background: var(--bg); color: var(--fg); font: 14px/1.45 system-ui, sans-serif; max-width: 1000px; margin: 24px auto; padding: 0 16px; }
h1 { font-size: 20px; margin-bottom: 4px; } h2 { font-size: 15px; margin: 28px 0 6px; overflow-wrap: anywhere; }
p { color: var(--muted); margin-top: 0; }
.wrap { overflow-x: auto; }
table { border-collapse: collapse; width: 100%; }
th, td { text-align: left; padding: 5px 8px; border-bottom: 1px solid var(--line); white-space: nowrap; }
th { color: var(--muted); font-weight: 600; }
.high { color: var(--high); font-weight: 600; } .medium { color: var(--medium); } .low { color: var(--low); }
"""


def to_html(report: Report) -> str:
    by_file: dict[str, list] = defaultdict(list)
    for f in report.findings:
        by_file[f.path].append(f)
    rows, sections = [], []
    for path in sorted(by_file):
        found = by_file[path]
        c = Counter(f.confidence for f in found)
        kinds = ", ".join(f"{KINDS[k]} ({n})" for k, n in Counter(f.kind for f in found).most_common())
        rows.append(f'<tr><td><a href="#f{len(rows)}">{escape(path)}</a></td><td class="high">{c["high"]}</td>'
                    f'<td class="medium">{c["medium"]}</td><td class="low">{c["low"]}</td><td>{escape(kinds)}</td></tr>')
        body = "".join(
            f'<tr><td>{escape(f.where)}</td><td>{escape(f.label)}</td><td dir="auto">{escape(f.masked)}</td>'
            f'<td class="{f.confidence}">{f.confidence}</td><td>{escape(f.reason)}</td></tr>'
            for f in found)
        sections.append(f'<h2 id="f{len(sections)}">{escape(path)}</h2><div class="wrap"><table><thead><tr><th>where</th>'
                        f"<th>kind</th><th>value (masked)</th><th>confidence</th><th>why</th></tr></thead>"
                        f"<tbody>{body}</tbody></table></div>")
    skipped = "".join(f"<li>{escape(p)}: {escape(r)}</li>" for p, r in report.skipped)
    return (
        '<!doctype html>\n<html lang="en"><head><meta charset="utf-8">'
        '<meta name="viewport" content="width=device-width, initial-scale=1">'
        f"<title>PII scan</title><style>{CSS}</style></head><body><h1>PII scan</h1>"
        f"<p>{escape(summary(report))}</p><p>{escape(NOTE)}</p>"
        '<div class="wrap"><table><thead><tr><th>file</th><th>high</th><th>medium</th><th>low</th><th>kinds</th></tr></thead>'
        f'<tbody>{"".join(rows)}</tbody></table></div>{"".join(sections)}'
        + (f"<h2>Skipped</h2><ul>{skipped}</ul>" if skipped else "")
        + "</body></html>\n"
    )
