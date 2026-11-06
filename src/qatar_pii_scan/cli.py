"""qpii command line."""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

from . import __version__
from .detectors import LEVELS
from .report import NOTE, summary, to_html, to_json, to_sarif, to_text
from .rules import Allowlist, load_ignore, value_hash
from .scanner import scan

CONFIDENCE = list(LEVELS)


def _default(given: str | None, name: str) -> str | None:
    if given:
        return given
    return name if Path(name).is_file() else None


def write(text: str, output: str | None) -> None:
    if output:
        Path(output).write_text(text, encoding="utf-8")
    else:
        sys.stdout.write(text if text.endswith("\n") else text + "\n")


def cmd_scan(args) -> int:
    ignore_file = _default(args.ignore_file, ".qpiiignore")
    allow_file = _default(args.allowlist, ".qpii-allow")
    report = scan(
        args.paths or ["."],
        min_confidence=args.min_confidence,
        ignore=load_ignore(ignore_file) if ignore_file else None,
        allow=Allowlist.load(allow_file) if allow_file else None,
    )
    renderers = {"text": to_text, "json": to_json, "sarif": to_sarif}
    write(renderers[args.format](report), args.output)
    if args.html:
        Path(args.html).write_text(to_html(report), encoding="utf-8")
    if args.output:
        print(summary(report))
    if args.fail_on == "never":
        return 0
    floor = LEVELS[args.fail_on]
    return 1 if any(LEVELS[f.confidence] >= floor for f in report.findings) else 0


def cmd_hash(args) -> int:
    print(f"sha256:{value_hash(args.value)}")
    return 0


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="qpii", description="Find personal data in Qatar formats. " + NOTE)
    p.add_argument("--version", action="version", version=f"%(prog)s {__version__}")
    sub = p.add_subparsers(dest="command", required=True)

    s = sub.add_parser("scan", help="scan files and folders")
    s.add_argument("paths", nargs="*", help="files or folders (default: current folder)")
    s.add_argument("--format", choices=["text", "json", "sarif"], default="text")
    s.add_argument("--html", help="also write an HTML summary per file")
    s.add_argument("-o", "--output", help="write the report to a file instead of the screen")
    s.add_argument("--min-confidence", choices=CONFIDENCE, default="low", help="hide findings below this level")
    s.add_argument("--fail-on", choices=CONFIDENCE + ["never"], default="medium",
                   help="exit with 1 when a finding is at this level or above (default: medium)")
    s.add_argument("--ignore-file", help="path patterns to skip (default: .qpiiignore if present)")
    s.add_argument("--allowlist", help="known values to accept (default: .qpii-allow if present)")

    h = sub.add_parser("hash", help="print the allowlist hash of a value")
    h.add_argument("value")
    return p


def main(argv: list[str] | None = None) -> int:
    for stream in (sys.stdout, sys.stderr):
        try:
            stream.reconfigure(encoding="utf-8", errors="replace")  # Arabic on a Windows console
        except (AttributeError, ValueError):
            pass
    args = build_parser().parse_args(argv)
    commands = {"scan": cmd_scan, "hash": cmd_hash}
    try:
        return commands[args.command](args)
    except (OSError, ValueError) as exc:
        print(f"qpii: {exc}", file=sys.stderr)
        return 2
