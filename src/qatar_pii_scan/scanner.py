"""Walk files and directories and collect findings with masked values."""
from __future__ import annotations

import os
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Iterable

from .detectors import KINDS, LEVELS, detect
from .mask import mask
from .rules import INLINE_IGNORE, Allowlist, is_ignored
from .sources import MAX_BYTES, file_kind, is_binary, pieces_for

SKIP_DIRS = {".git", ".hg", ".svn", "node_modules", ".venv", "venv", "__pycache__", ".pytest_cache",
             ".mypy_cache", "dist", "build", ".tox", ".idea", ".vscode"}
SKIP_SUFFIXES = {".png", ".jpg", ".jpeg", ".gif", ".pdf", ".zip", ".gz", ".exe", ".dll", ".so", ".pyc",
                 ".woff", ".woff2", ".ico", ".mp3", ".mp4", ".parquet", ".xls"}
SKIP_NAMES = {".qpii-allow", ".qpiiignore"}  # the allowlist is meant to hold known values


@dataclass
class Finding:
    path: str
    kind: str
    confidence: str
    reason: str
    masked: str
    where: str
    line: int | None
    column: int | None
    end_column: int | None
    value: str = field(repr=False, compare=False)

    @property
    def label(self) -> str:
        return KINDS[self.kind]

    def to_dict(self) -> dict:
        out = asdict(self)
        out.pop("value")
        return out


@dataclass
class Report:
    findings: list[Finding] = field(default_factory=list)
    files: list[str] = field(default_factory=list)
    skipped: list[tuple[str, str]] = field(default_factory=list)

    def counts(self) -> dict[str, int]:
        out = {level: 0 for level in ("high", "medium", "low")}
        for f in self.findings:
            out[f.confidence] += 1
        return out


def display_path(path: Path) -> str:
    """Relative to the current folder when possible, so SARIF paths match the repo."""
    try:
        return path.resolve().relative_to(Path.cwd().resolve()).as_posix()
    except ValueError:
        return path.resolve().as_posix()


def scan_file(path: Path, shown: str, min_confidence: str = "low", allow: Allowlist | None = None) -> list[Finding]:
    floor = LEVELS[min_confidence]
    findings = []
    for piece in pieces_for(path):
        if INLINE_IGNORE in piece.text:
            continue
        for m in detect(piece.text, piece.field):
            if LEVELS[m.confidence] < floor:
                continue
            if allow and allow.allows(m.kind, m.value, shown):
                continue
            column = piece.column + m.start if piece.column else None
            end = piece.column + m.end if piece.column else None
            where = f"{piece.where}, col {column}" if piece.where.startswith("line") and column else piece.where
            findings.append(Finding(shown, m.kind, m.confidence, m.reason, mask(m.value, m.kind), where,
                                    piece.line, column, end, m.value))
    return findings


def iter_files(paths: Iterable[Path]) -> Iterable[Path]:
    """Files under `paths`, skipping tool and dependency folders."""
    for path in paths:
        if path.is_file():
            yield path
            continue
        if not path.exists():
            raise FileNotFoundError(f"no such file or folder: {path}")
        for dirpath, dirnames, filenames in os.walk(path):
            dirnames[:] = sorted(d for d in dirnames if d not in SKIP_DIRS)
            for name in sorted(filenames):
                yield Path(dirpath) / name


def scan(paths: Iterable[str | Path], min_confidence: str = "low", ignore: list[str] | None = None,
         allow: Allowlist | None = None) -> Report:
    report = Report()
    for file in iter_files(Path(p) for p in paths):
        shown = display_path(file)
        if file.suffix.lower() in SKIP_SUFFIXES or file.name in SKIP_NAMES or (ignore and is_ignored(shown, ignore)):
            continue
        if file.stat().st_size > MAX_BYTES:
            report.skipped.append((shown, "larger than 20 MB"))
            continue
        if file_kind(file) != "excel" and is_binary(file):
            report.skipped.append((shown, "binary"))
            continue
        try:
            found = scan_file(file, shown, min_confidence, allow)
        except Exception as exc:  # a broken file should not stop the scan
            report.skipped.append((shown, f"could not read: {exc.__class__.__name__}"))
            continue
        report.files.append(shown)
        report.findings.extend(found)
    return report
