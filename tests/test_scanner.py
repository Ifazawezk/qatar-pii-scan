import json

import pytest
from openpyxl import Workbook

from qatar_pii_scan.fake import fake_email, fake_iban, fake_phone, fake_qid
from qatar_pii_scan.scanner import scan, scan_file
from qatar_pii_scan.sources import csv_pieces, json_pieces

QID = fake_qid(12)
PHONE = fake_phone(34)
IBAN = fake_iban(56)
EMAIL = fake_email("noor.k")


def test_text_file_locations(tmp_path):
    f = tmp_path / "app.log"
    f.write_text(f"start\n2026-03-01 INFO login ok for {EMAIL}\nsms sent to {PHONE}\n", encoding="utf-8")
    found = scan_file(f, "app.log")
    assert [(x.kind, x.line, x.column) for x in found] == [("email", 2, 30), ("phone", 3, 13)]
    assert found[0].where == "line 2, col 30"
    line = f.read_text(encoding="utf-8").splitlines()[1]
    assert line[found[0].column - 1:found[0].end_column - 1] == EMAIL


def test_csv_cells_use_the_header(tmp_path):
    pieces = csv_pieces(f"id,full_name,mobile\n1,Noor Al-Mansoori,{PHONE.replace(' ', '')[4:]}\n")
    assert [(p.field, p.line, p.column) for p in pieces] == [("id", 2, 1), ("full_name", 2, 3), ("mobile", 2, 20)]
    f = tmp_path / "c.csv"
    f.write_text(f"id,full_name,mobile,qid\n1,Noor Al-Mansoori,50000034,{QID}\n", encoding="utf-8")
    found = scan_file(f, "c.csv")
    assert [(x.kind, x.confidence, x.where) for x in found] == [
        ("name", "low", "row 2, column full_name"),
        ("phone", "medium", "row 2, column mobile"),
        ("qid", "high", "row 2, column qid"),
    ]


def test_excel_cells_and_numbers(tmp_path):
    wb = Workbook()
    ws = wb.active
    ws.title = "Staff"
    ws.append(["Name", "QID", "IBAN"])
    ws.append(["Sara Yousef", int(QID), IBAN])
    wb.save(tmp_path / "s.xlsx")
    found = scan_file(tmp_path / "s.xlsx", "s.xlsx")
    assert [(x.kind, x.where, x.line) for x in found] == [("name", "Staff!A2", None), ("qid", "Staff!B2", None), ("iban", "Staff!C2", None)]


def test_json_pointers_and_lines(tmp_path):
    doc = {"customers": [{"id": 1, "contact": {"phone": PHONE, "email": EMAIL}}, {"id": 2, "qid": int(QID)}]}
    text = json.dumps(doc, indent=2)
    pieces = {p.where: p for p in json_pieces(text)}
    assert pieces["/customers/0/contact/email"].line == 7
    assert pieces["/customers/1/qid"].field == "qid"
    f = tmp_path / "d.json"
    f.write_text(text, encoding="utf-8")
    found = scan_file(f, "d.json")
    assert [(x.kind, x.where) for x in found] == [
        ("phone", "/customers/0/contact/phone"),
        ("email", "/customers/0/contact/email"),
        ("qid", "/customers/1/qid"),
    ]
    lines = text.splitlines()
    email = found[1]
    assert lines[email.line - 1][email.column - 1:email.end_column - 1] == EMAIL


def test_broken_json_falls_back_to_lines(tmp_path):
    f = tmp_path / "x.json"
    f.write_text('{"phone": "' + PHONE + '",', encoding="utf-8")
    assert [x.where for x in scan_file(f, "x.json")] == ["line 1, col 12"]


def test_scan_walks_folders_and_skips(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    (tmp_path / "src").mkdir()
    (tmp_path / "src" / "settings.py").write_text(f'SUPPORT = "{EMAIL}"\n', encoding="utf-8")
    (tmp_path / "node_modules").mkdir()
    (tmp_path / "node_modules" / "x.js").write_text(f"'{EMAIL}'", encoding="utf-8")
    (tmp_path / "blob.bin").write_bytes(b"\0\1" + EMAIL.encode())
    (tmp_path / "bad.xlsx").write_text("not a workbook", encoding="utf-8")
    report = scan(["."])
    assert report.files == ["src/settings.py"]
    assert dict(report.skipped) == {"bad.xlsx": "could not read: BadZipFile", "blob.bin": "binary"}
    assert [x.path for x in report.findings] == ["src/settings.py"]
    assert report.counts() == {"high": 1, "medium": 0, "low": 0}


def test_min_confidence(tmp_path):
    f = tmp_path / "n.txt"
    f.write_text(f"Mr. Karim Haddad, {QID}\n", encoding="utf-8")
    assert [x.kind for x in scan_file(f, "n.txt")] == ["name", "qid"]
    assert [x.kind for x in scan_file(f, "n.txt", "medium")] == ["qid"]


def test_finding_dict_has_no_value(tmp_path):
    f = tmp_path / "a.txt"
    f.write_text(QID, encoding="utf-8")
    finding = scan_file(f, "a.txt")[0]
    assert "value" not in finding.to_dict()
    assert QID not in repr(finding) and QID not in json.dumps(finding.to_dict())


def test_missing_path():
    with pytest.raises(FileNotFoundError):
        scan(["does/not/exist"])
