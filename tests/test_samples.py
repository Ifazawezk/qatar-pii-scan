import json
from pathlib import Path

from openpyxl import load_workbook

from qatar_pii_scan.fake import fake_iban, fake_phone, fake_qid
from qatar_pii_scan.redact import redact
from qatar_pii_scan.report import to_html, to_json, to_sarif, to_text
from qatar_pii_scan.scanner import scan

SAMPLE = Path(__file__).resolve().parent.parent / "examples" / "sample"


def test_sample_folder_counts():
    report = scan([SAMPLE])
    assert len(report.files) == 5
    assert report.counts() == {"high": 29, "medium": 7, "low": 22}
    kinds = {f.kind for f in report.findings}
    assert kinds == {"iban", "email", "qid", "phone", "passport", "name"}


def test_no_sample_value_leaks_into_reports():
    report = scan([SAMPLE])
    outputs = [to_text(report), to_json(report), to_sarif(report), to_html(report)]
    for f in report.findings:
        for out in outputs:
            assert f.value not in out, (f.kind, f.where)


def test_sample_values_are_the_documented_fakes():
    text = (SAMPLE / "customers.csv").read_text(encoding="utf-8-sig")
    assert fake_qid(1, 1991, 634) in text
    payroll = load_workbook(SAMPLE / "payroll.xlsx").active
    assert payroll["C2"].value == fake_iban(1) and " FAKE " in payroll["C2"].value
    assert fake_phone(1) in (SAMPLE / "app.log").read_text(encoding="utf-8")


def test_redacted_samples_scan_clean(tmp_path):
    for name in ("customers.csv", "payroll.xlsx", "orders.json"):
        redact(SAMPLE / name, tmp_path / name)
    assert scan([tmp_path]).findings == []
    assert json.loads((tmp_path / "orders.json").read_text(encoding="utf-8"))["orders"][2]["customer"]["email"] == "g***@e***.com"
