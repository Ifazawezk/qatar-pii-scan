"""Masking. Every report and the redact command go through `mask`, so no output
ever holds a full value."""
from __future__ import annotations

import re

_PHONE_PREFIX = re.compile(r"^(?:\+|00)\s?974[\s.-]?|^974(?=\d{8}$)")


def _keep_tail(value: str, keep: int = 2) -> str:
    """Star every letter and digit except the last `keep`, leaving separators alone."""
    total = sum(ch.isalnum() for ch in value)
    if total <= keep + 2:
        return "".join("*" if ch.isalnum() else ch for ch in value)
    out, seen = [], 0
    for ch in value:
        if ch.isalnum():
            seen += 1
            out.append(ch if seen > total - keep else "*")
        else:
            out.append(ch)
    return "".join(out)


def mask(value: str, kind: str) -> str:
    if kind == "email":
        local, _, domain = value.rpartition("@")
        labels = domain.split(".")
        return f"{local[:1]}***@{labels[0][:1]}***.{labels[-1]}"
    if kind == "name":
        return " ".join(word[:1] + "***" for word in value.split())
    if kind == "phone":
        prefix = _PHONE_PREFIX.match(value)
        head = prefix.group() if prefix else ""
        return head + _keep_tail(value[len(head):])
    if kind == "iban":
        return value[:2] + _keep_tail(value[2:])
    return _keep_tail(value)
