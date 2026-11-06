"""Split files into pieces of text that each know where they came from.

Text and code: one piece per line. CSV: one per cell, with the header as the field.
Excel: one per cell, as Sheet!C4. JSON: one per string or number, as a JSON pointer.
"""
from __future__ import annotations

import csv
import io
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from openpyxl import load_workbook
from openpyxl.utils import get_column_letter

MAX_BYTES = 20 * 1024 * 1024


@dataclass
class Piece:
    text: str
    field: str
    line: int | None
    column: int | None  # 1-based column where `text` starts on that line
    where: str


def file_kind(path: Path) -> str:
    suffix = path.suffix.lower()
    if suffix in (".csv", ".tsv"):
        return "csv"
    if suffix in (".xlsx", ".xlsm"):
        return "excel"
    if suffix == ".json":
        return "json"
    return "text"


def is_binary(path: Path) -> bool:
    with open(path, "rb") as fh:
        return b"\0" in fh.read(8192)


def read_text(path: Path) -> str:
    raw = path.read_bytes()
    for encoding in ("utf-8-sig", "cp1256"):
        try:
            return raw.decode(encoding)
        except UnicodeDecodeError:
            continue
    return raw.decode("latin-1")


def text_pieces(text: str) -> list[Piece]:
    return [Piece(line, "", n, 1, f"line {n}") for n, line in enumerate(text.splitlines(), 1)]


def csv_pieces(text: str, delimiter: str = ",") -> list[Piece]:
    lines = text.splitlines()
    reader = csv.reader(io.StringIO(text), delimiter=delimiter)
    header: list[str] = []
    pieces = []
    for row in reader:
        if not header:
            header = [h.strip() for h in row]
            continue
        line = reader.line_num
        raw = lines[line - 1] if line - 1 < len(lines) else ""
        cursor = 0
        for j, cell in enumerate(row):
            name = header[j] if j < len(header) else f"column {j + 1}"
            idx = raw.find(cell, cursor) if cell else -1
            column = idx + 1 if idx >= 0 else None
            if idx >= 0:
                cursor = idx + len(cell)
            if cell.strip():
                pieces.append(Piece(cell, name, line, column, f"row {line}, column {name}"))
    return pieces


def _cell_text(value: Any) -> str | None:
    if isinstance(value, bool) or value is None:
        return None
    if isinstance(value, str):
        return value
    if isinstance(value, int):
        return str(value)
    if isinstance(value, float) and value.is_integer() and abs(value) < 1e15:
        return str(int(value))
    return None


def excel_pieces(path: Path) -> list[Piece]:
    wb = load_workbook(path, read_only=True, data_only=True)
    pieces = []
    try:
        for ws in wb.worksheets:
            header: list[str] = []
            for r, row in enumerate(ws.iter_rows(values_only=True), 1):
                if r == 1:
                    header = [_cell_text(v) or "" for v in row]
                for c, value in enumerate(row, 1):
                    text = _cell_text(value)
                    if not text or not text.strip():
                        continue
                    field = header[c - 1] if r > 1 and c - 1 < len(header) else ""
                    pieces.append(Piece(text, field, None, None, f"{ws.title}!{get_column_letter(c)}{r}"))
    finally:
        wb.close()
    return pieces


def _pointer_part(key: str) -> str:
    return key.replace("~", "~0").replace("/", "~1")


def json_pieces(text: str) -> list[Piece]:
    data = json.loads(text)
    pieces: list[Piece] = []
    cursor = 0

    def locate(node: Any) -> int | None:
        nonlocal cursor
        for literal in dict.fromkeys([json.dumps(node, ensure_ascii=False), json.dumps(node)]):
            idx = text.find(literal, cursor)
            if idx >= 0:
                cursor = idx + len(literal)
                return idx
        return None

    def walk(node: Any, pointer: str, field: str) -> None:
        if isinstance(node, dict):
            for key, value in node.items():
                locate(key)
                walk(value, f"{pointer}/{_pointer_part(key)}", key)
        elif isinstance(node, list):
            for i, value in enumerate(node):
                walk(value, f"{pointer}/{i}", field)
        elif isinstance(node, (str, int, float)) and not isinstance(node, bool):
            idx = locate(node)
            value = _cell_text(node)
            if value is None or not value.strip():
                return
            line = column = None
            if idx is not None:
                line = text.count("\n", 0, idx) + 1
                column = idx - (text.rfind("\n", 0, idx) + 1) + 1 + (1 if isinstance(node, str) else 0)
            pieces.append(Piece(value, field, line, column, pointer or "/"))

    walk(data, "", "")
    return pieces


def pieces_for(path: Path) -> list[Piece]:
    kind = file_kind(path)
    if kind == "excel":
        return excel_pieces(path)
    text = read_text(path)
    if kind == "csv":
        return csv_pieces(text, "\t" if path.suffix.lower() == ".tsv" else ",")
    if kind == "json":
        try:
            return json_pieces(text)
        except json.JSONDecodeError:
            return text_pieces(text)
    return text_pieces(text)
