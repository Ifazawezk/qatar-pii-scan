import json

from openpyxl import Workbook

from qatar_pii_scan.cli import main
from qatar_pii_scan.fake import fake_iban, fake_phone, fake_qid
from qatar_pii_scan.report import to_html, to_sarif
from qatar_pii_scan.scanner import Report, scan

QID = fake_qid(9)
PHONE = fake_phone(9)
IBAN = fake_iban(9)


def make_files(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    (tmp_path / "src").mkdir()
    (tmp_path / "src" / "seed.py").write_text(f'ADMIN_PHONE = "{PHONE}"\nqid = "{QID}"\n', encoding="utf-8")
    wb = Workbook()
    wb.active.append(["IBAN"])
    wb.active.append([IBAN])
    wb.save(tmp_path / "payroll file.xlsx")
    return scan(["."])


def test_sarif_shape(tmp_path, monkeypatch):
    report = make_files(tmp_path, monkeypatch)
    sarif = json.loads(to_sarif(report))
    assert sarif["version"] == "2.1.0"
    run = sarif["runs"][0]
    assert [r["id"] for r in run["tool"]["driver"]["rules"]] == [
        "qpii/iban", "qpii/email", "qpii/qid", "qpii/phone", "qpii/passport", "qpii/name"]
    by_rule = {r["ruleId"]: r for r in run["results"]}
    phone = by_rule["qpii/phone"]
    assert phone["level"] == "error"
    region = phone["locations"][0]["physicalLocation"]["region"]
    assert region == {"startLine": 1, "startColumn": 16, "endColumn": 30}
    assert phone["locations"][0]["physicalLocation"]["artifactLocation"] == {"uri": "src/seed.py", "uriBaseId": "%SRCROOT%"}
    iban = by_rule["qpii/iban"]
    assert iban["locations"][0]["physicalLocation"]["artifactLocation"]["uri"] == "payroll%20file.xlsx"
    assert iban["locations"][0]["logicalLocations"][0]["fullyQualifiedName"] == "Sheet!A2"
    assert by_rule["qpii/qid"]["level"] == "error"
    assert len({r["partialFingerprints"]["qpiiFinding/v1"] for r in run["results"]}) == 3


def test_no_full_value_in_any_report(tmp_path, monkeypatch):
    report = make_files(tmp_path, monkeypatch)
    for text in (to_sarif(report), to_html(report)):
        for value in (QID, PHONE, IBAN, IBAN.replace(" ", ""), PHONE.replace(" ", "")):
            assert value not in text


def test_html_summary(tmp_path, monkeypatch):
    report = make_files(tmp_path, monkeypatch)
    html = to_html(report)
    assert "<h2 id=\"f0\">payroll file.xlsx</h2>" in html
    assert "Qatar phone number (1), Qatar ID number (1)" in html
    assert "not a compliance check or a legal opinion" in html
    empty = to_html(Report())
    assert "0 findings in 0 of 0 files" in empty


def test_cli_sarif_and_html(tmp_path, monkeypatch, capsys):
    make_files(tmp_path, monkeypatch)
    assert main(["scan", "src", "--format", "sarif", "-o", "out.sarif", "--html", "out.html"]) == 1
    assert json.loads((tmp_path / "out.sarif").read_text(encoding="utf-8"))["runs"][0]["results"]
    assert (tmp_path / "out.html").read_text(encoding="utf-8").startswith("<!doctype html>")
