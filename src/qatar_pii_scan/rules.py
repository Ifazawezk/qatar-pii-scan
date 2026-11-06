"""Ignore file, allowlist and inline ignores.

.qpiiignore holds one path pattern per line: `*.min.js`, `tests/fixtures/`,
`docs/**/*.md`. A pattern with no slash matches the file name anywhere.

.qpii-allow holds one entry per line:
    support@company.qa      a value you expect, compared without spaces or dashes
    sha256:<hex>            the same, as a SHA-256 of the value (see `qpii hash`),
                            so the allowlist itself holds no personal data
    regex:<pattern>         a regular expression the whole value must match
    kind:name [glob]        turn a detector off, everywhere or for matching paths

A line containing `qpii:ignore` is skipped, which works as a comment in most languages.
"""
from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass, field
from fnmatch import fnmatch
from pathlib import Path, PurePosixPath

from .detectors import KINDS, fold_digits

INLINE_IGNORE = "qpii:ignore"


def _lines(path: str | Path) -> list[str]:
    out = []
    for raw in Path(path).read_text(encoding="utf-8-sig").splitlines():
        line = raw.strip()
        if line and not line.startswith("#"):
            out.append(line)
    return out


def load_ignore(path: str | Path) -> list[str]:
    return _lines(path)


def is_ignored(path: str, patterns: list[str]) -> bool:
    name = PurePosixPath(path).name
    for pattern in patterns:
        if pattern.endswith("/"):
            folder = pattern.strip("/")
            if f"/{path}".find(f"/{folder}/") >= 0:
                return True
        elif "/" in pattern:
            pattern = pattern.lstrip("/")
            if fnmatch(path, pattern) or fnmatch(path, pattern.replace("**/", "")):
                return True
        elif fnmatch(name, pattern):
            return True
    return False


def normalize_value(value: str) -> str:
    return re.sub(r"[\s\-.()]", "", fold_digits(value)).lower()


def value_hash(value: str) -> str:
    return hashlib.sha256(normalize_value(value).encode("utf-8")).hexdigest()


@dataclass
class Allowlist:
    values: set[str] = field(default_factory=set)
    hashes: set[str] = field(default_factory=set)
    patterns: list[re.Pattern] = field(default_factory=list)
    kinds: list[tuple[str, str | None]] = field(default_factory=list)

    @classmethod
    def load(cls, path: str | Path) -> "Allowlist":
        allow = cls()
        for n, line in enumerate(_lines(path), 1):
            if line.startswith("sha256:"):
                allow.hashes.add(line[7:].strip().lower())
            elif line.startswith("regex:"):
                try:
                    allow.patterns.append(re.compile(line[6:].strip()))
                except re.error as exc:
                    raise ValueError(f"{path}: bad regex on entry {n}: {exc}") from exc
            elif line.startswith("kind:"):
                kind, _, glob = line[5:].strip().partition(" ")
                if kind not in KINDS:
                    raise ValueError(f"{path}: unknown kind {kind!r}, use one of {', '.join(KINDS)}")
                allow.kinds.append((kind, glob.strip() or None))
            else:
                allow.values.add(normalize_value(line))
        return allow

    def allows(self, kind: str, value: str, path: str) -> bool:
        for k, glob in self.kinds:
            if k == kind and (glob is None or is_ignored(path, [glob])):
                return True
        norm = normalize_value(value)
        if norm in self.values or (self.hashes and value_hash(value) in self.hashes):
            return True
        return any(p.fullmatch(value) for p in self.patterns)
