import datetime as dt

import pytest

from qatar_pii_scan.detectors import detect, fold_digits, normalize, qid_problem
from qatar_pii_scan.mask import mask


def kinds(text, field=""):
    return [(m.kind, m.value, m.confidence) for m in detect(text, field)]


def test_email():
    assert kinds("mail noor.k@mail.qa now") == [("email", "noor.k@mail.qa", "high")]
    assert kinds("user@example.com") == [("email", "user@example.com", "low")]
    assert kinds("not an email: a@b") == []


def test_qid_with_and_without_keyword():
    assert kinds("QID: 28463400012") == [("qid", "28463400012", "high")]
    assert kinds("ref 28463400012") == [("qid", "28463400012", "medium")]
    assert kinds("الرقم الشخصي ٢٨٤٦٣٤٠٠٠١٢")[0][2] == "high"


def test_qid_rules():
    today = dt.date(2026, 11, 5)
    assert qid_problem("28463400012", today) == ""
    assert qid_problem("30563400012", today) == ""
    assert "future" in qid_problem("39963400012", today)
    assert "ISO" in qid_problem("28400000012", today)
    assert qid_problem("18463400012", today)


def test_long_numbers_are_not_qids():
    assert kinds("order 284634000123") == []
    assert kinds("amount 28463400012.50") == []


def test_phones():
    assert kinds("call +974 5500 0012") == [("phone", "+974 5500 0012", "high")]
    assert kinds("call 0097444000012") == [("phone", "0097444000012", "high")]
    assert kinds("97455000012") == [("phone", "97455000012", "medium")]
    assert kinds("mobile: 5500-0012") == [("phone", "5500-0012", "medium")]
    assert kinds("ref 5500 0012") == [("phone", "5500 0012", "low")]
    assert kinds("phone=55000012") == [("phone", "55000012", "medium")]
    assert kinds("count=55000012") == []
    assert kinds("جوال ٥٥٠٠٠٠١٢") == [("phone", "٥٥٠٠٠٠١٢", "medium")]


def test_phone_lookalikes_are_skipped():
    assert kinds("phone 2026-03-19 12:30") == []
    assert kinds("phone +974 2500 0012") == []  # 2 is not a Qatar prefix
    assert kinds("v3.5500 0012") == []


def test_overlap_goes_to_the_first_detector():
    found = kinds("55000012@mail.qa")
    assert found == [("email", "55000012@mail.qa", "high")]


def test_offsets_point_at_the_original_text():
    text = "رقم الجوال: ٥٥٠٠٠٠١٢ شكرا"
    m = detect(text)[0]
    assert text[m.start:m.end] == "٥٥٠٠٠٠١٢"


def test_fold_and_normalize():
    assert fold_digits("٠١٢٣ ۴۵") == "0123 45"
    assert normalize("customerPhone") == "customer phone"
    assert normalize("الهويّة") == "الهويه"


@pytest.mark.parametrize("value,kind,masked", [
    ("28463400012", "qid", "*********12"),
    ("+974 5500 0012", "phone", "+974 **** **12"),
    ("55000012", "phone", "******12"),
    ("noor.k@mail.qa", "email", "n***@m***.qa"),
    ("Noor Al-Mansoori", "name", "N*** A***"),
    ("نور المنصوري", "name", "ن*** ا***"),
    ("AB1234567", "passport", "*******67"),
    ("12", "qid", "**"),
])
def test_mask(value, kind, masked):
    assert mask(value, kind) == masked
