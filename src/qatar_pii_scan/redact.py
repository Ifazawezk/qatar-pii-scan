"""Write a masked copy of a CSV, Excel or JSON file. The original is never changed."""
from __future__ import annotations

import csv
import io
import json
from pathlib import Path
from typing import Any

from openpyxl import load_workbook

from .detectors import LEVELS, detect
from .mask import mask
from .rules import Allowlist
from .sources import _cell_text, file_kind, read_text


class Redactor:
    def __init__(self, min_confidence: str = "low", allow: Allowlist | None = None, path: str = ""):
        self.floor = LEVELS[min_confidence]
        self.allow = allow
        self.path = path
        self.count = 0

    def text(self, value: str, field: str = "") -> str:
        out = value
        for m in reversed(detect(value, field)):
            if LEVELS[m.confidence] < self.floor:
                continue
            if self.allow and self.allow.allows(m.kind, m.value, self.path):
                continue
            out = out[:m.start] + mask(m.value, m.kind) + out[m.end:]
            self.count += 1
        return out

    def value(self, value: Any, field: str) -> Any:
        text = _cell_text(value)
        if text is None:
            return value
        new = self.text(text, field)
        return value if new == text else new


def redact_csv(src: Path, dst: Path, r: Redactor) -> None:
    raw = src.read_bytes()
    delimiter = "\t" if src.suffix.lower() == ".tsv" else ","
    rows = list(csv.reader(io.StringIO(read_text(src)), delimiter=delimiter))
    header = rows[0] if rows else []
    out = [header] + [
        [r.text(cell, header[j] if j < len(header) else "") for j, cell in enumerate(row)] for row in rows[1:]
    ]
    encoding = "utf-8-sig" if raw.startswith(b"\xef\xbb\xbf") else "utf-8"
    with open(dst, "w", newline="", encoding=encoding) as fh:
        csv.writer(fh, delimiter=delimiter).writerows(out)


def redact_excel(src: Path, dst: Path, r: Redactor) -> None:
    wb = load_workbook(src)
    for ws in wb.worksheets:
        header = [_cell_text(c.value) or "" for c in next(ws.iter_rows(max_row=1), ())]
        for row in ws.iter_rows(min_row=2):
            for cell in row:
                if isinstance(cell.value, str) and cell.value.startswith("="):
                    continue  # leave formulas alone
                field = header[cell.column - 1] if cell.column - 1 < len(header) else ""
                cell.value = r.value(cell.value, field)
    wb.save(dst)


def redact_json(src: Path, dst: Path, r: Redactor) -> None:
    def walk(node: Any, field: str) -> Any:
        if isinstance(node, dict):
            return {k: walk(v, k) for k, v in node.items()}
        if isinstance(node, list):
            return [walk(v, field) for v in node]
        if isinstance(node, bool) or node is None:
            return node
        return r.value(node, field)

    data = walk(json.loads(read_text(src)), "")
    dst.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def redact(src: str | Path, dst: str | Path, min_confidence: str = "low", allow: Allowlist | None = None) -> int:
    """Mask every finding in `src` and write the result to `dst`. Returns how many values were masked."""
    src, dst = Path(src), Path(dst)
    if src.resolve() == dst.resolve():
        raise ValueError("the output must be a different file from the input")
    kind = file_kind(src)
    handlers = {"csv": redact_csv, "excel": redact_excel, "json": redact_json}
    if kind not in handlers:
        raise ValueError("redact works on CSV, TSV, Excel (.xlsx) and JSON files")
    if kind == "excel" and dst.suffix.lower() not in (".xlsx", ".xlsm"):
        raise ValueError("write the Excel copy to an .xlsx file")
    r = Redactor(min_confidence, allow, src.as_posix())
    handlers[kind](src, dst, r)
    return r.count
