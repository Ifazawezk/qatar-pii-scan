import json

import pytest
from openpyxl import Workbook, load_workbook

from qatar_pii_scan.cli import main
from qatar_pii_scan.fake import fake_email, fake_iban, fake_phone, fake_qid
from qatar_pii_scan.redact import redact
from qatar_pii_scan.rules import Allowlist
from qatar_pii_scan.scanner import scan

QID = fake_qid(21)
PHONE = fake_phone(21)
EMAIL = fake_email("sara.y")
IBAN = fake_iban(21)


def test_csv_copy_is_masked_and_original_kept(tmp_path):
    src = tmp_path / "in.csv"
    original = f"id,full_name,mobile,notes\n1,Sara Yousef,{PHONE},mail {EMAIL} today\n"
    src.write_bytes(b"\xef\xbb\xbf" + original.encode("utf-8"))
    count = redact(src, tmp_path / "out.csv")
    assert count == 3
    out = (tmp_path / "out.csv").read_bytes()
    assert out.startswith(b"\xef\xbb\xbf")
    text = out.decode("utf-8-sig")
    assert "S*** Y***" in text and "+974 **** **21" in text and "mail s***@e***.qa today" in text
    assert src.read_bytes().decode("utf-8-sig") == original


def test_min_confidence_keeps_names(tmp_path):
    src = tmp_path / "in.csv"
    src.write_text(f"full_name,qid\nSara Yousef,{QID}\n", encoding="utf-8")
    assert redact(src, tmp_path / "out.csv", min_confidence="medium") == 1
    assert "Sara Yousef,*********21" in (tmp_path / "out.csv").read_text(encoding="utf-8")


def test_excel_copy(tmp_path):
    wb = Workbook()
    ws = wb.active
    ws.append(["Name", "QID", "IBAN", "Total"])
    ws.append(["Sara Yousef", int(QID), IBAN, "=SUM(1,2)"])
    wb.save(tmp_path / "in.xlsx")
    assert redact(tmp_path / "in.xlsx", tmp_path / "out.xlsx") == 3
    row = [c.value for c in load_workbook(tmp_path / "out.xlsx").active[2]]
    assert row[0] == "S*** Y***" and row[1] == "*********21" and row[2].startswith("QA** ")
    assert row[3] == "=SUM(1,2)"
    assert scan([tmp_path / "out.xlsx"]).findings == []


def test_json_copy(tmp_path):
    src = tmp_path / "in.json"
    src.write_text(json.dumps({"users": [{"qid": int(QID), "phone": PHONE, "active": True, "name": "سارة يوسف"}]}),
                   encoding="utf-8")
    assert redact(src, tmp_path / "out.json") == 3
    data = json.loads((tmp_path / "out.json").read_text(encoding="utf-8"))
    assert data["users"][0] == {"qid": "*********21", "phone": "+974 **** **21", "active": True, "name": "س*** ي***"}


def test_allowlist_values_survive(tmp_path):
    src = tmp_path / "in.json"
    src.write_text(json.dumps({"support": EMAIL}), encoding="utf-8")
    (tmp_path / "allow").write_text(EMAIL + "\n", encoding="utf-8")
    assert redact(src, tmp_path / "out.json", allow=Allowlist.load(tmp_path / "allow")) == 0


def test_refusals(tmp_path):
    src = tmp_path / "in.csv"
    src.write_text("a\n1\n", encoding="utf-8")
    with pytest.raises(ValueError, match="different file"):
        redact(src, src)
    with pytest.raises(ValueError, match="CSV"):
        redact(tmp_path / "x.log", tmp_path / "y.log")
    wb = Workbook()
    wb.save(tmp_path / "in.xlsx")
    with pytest.raises(ValueError, match="xlsx"):
        redact(tmp_path / "in.xlsx", tmp_path / "out.csv")


def test_cli_redact(tmp_path, monkeypatch, capsys):
    monkeypatch.chdir(tmp_path)
    (tmp_path / "in.csv").write_text(f"qid\n{QID}\n", encoding="utf-8")
    assert main(["redact", "in.csv", "-o", "masked.csv"]) == 0
    assert "masked 1 values, wrote masked.csv" in capsys.readouterr().out
    assert main(["redact", "in.csv", "-o", "in.csv"]) == 2
