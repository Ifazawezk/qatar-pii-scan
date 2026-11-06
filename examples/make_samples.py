"""Generate the sample files in examples/sample. Every value is made up.

QIDs use serials 00001 to 00999, IBANs use the bank code FAKE, emails use
example.qa and phones the +974 5000, 6000 and 4000 blocks. See qatar_pii_scan/fake.py.

    python examples/make_samples.py
"""
from __future__ import annotations

import csv
import json
from pathlib import Path

from openpyxl import Workbook

from qatar_pii_scan.fake import fake_email, fake_iban, fake_phone, fake_qid

OUT = Path(__file__).parent / "sample"
AR_DIGITS = str.maketrans("0123456789", "٠١٢٣٤٥٦٧٨٩")

PEOPLE = [
    ("Noor Al-Mansoori", "نور المنصوري", 1991, 634),
    ("Karim Haddad", "كريم حداد", 1987, 422),
    ("Sara Yousef", "سارة يوسف", 2001, 400),
    ("Arjun Menon", "أرجون مينون", 1994, 356),
    ("Maya Santos", "مايا سانتوس", 1989, 608),
]


def customers() -> None:
    with open(OUT / "customers.csv", "w", newline="", encoding="utf-8-sig") as fh:
        w = csv.writer(fh)
        w.writerow(["id", "full_name", "الاسم", "qid", "mobile", "email", "city"])
        for i, (en, ar, year, country) in enumerate(PEOPLE, 1):
            mobile = fake_phone(i, spaced=i % 2 == 0)
            if i == 3:
                mobile = mobile.translate(AR_DIGITS)
            w.writerow([i, en, ar, fake_qid(i, year, country), mobile, fake_email(en.split()[0].lower()), "Doha"])


def payroll() -> None:
    wb = Workbook()
    ws = wb.active
    ws.title = "Payroll"
    ws.append(["Employee", "QID", "IBAN", "Basic (QAR)"])
    for i, (en, _, year, country) in enumerate(PEOPLE, 1):
        ws.append([en, int(fake_qid(i + 10, year, country)), fake_iban(i), 9000 + 750 * i])
    broken = fake_iban(99).replace(" ", "")
    ws.append(["Test row", "", broken[:2] + "00" + broken[4:], 0])
    wb.save(OUT / "payroll.xlsx")


def orders() -> None:
    data = {"orders": [
        {"id": "SO-1001", "total": 420.5, "customer": {"name": "Karim Haddad", "phone": fake_phone(2, spaced=False),
                                                       "email": fake_email("karim")}},
        {"id": "SO-1002", "total": 99, "customer": {"name": "مايا سانتوس", "contact": {"mobile": "974" + fake_phone(5, "mobile2", spaced=False)}}},
        {"id": "SO-1003", "total": 12, "customer": {"name": "Guest", "email": "guest@example.com"}},
    ]}
    (OUT / "orders.json").write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def app_log() -> None:
    lines = [
        "2026-03-02 08:14:03 INFO  api  GET /health 200 3ms",
        f"2026-03-02 08:15:41 INFO  auth login ok user={fake_email('noor')} ip=10.0.4.12",
        f"2026-03-02 08:16:09 WARN  sms  delivery slow to {fake_phone(1)} (retry 1)",
        f"2026-03-02 09:02:55 INFO  kyc  passport no: AB{fake_qid(3)[4:11]} verified for Mr. Arjun Menon",
        "2026-03-02 09:03:10 INFO  kyc  تم التحقق من هوية السيد كريم حداد",
        f"2026-03-02 09:05:00 DEBUG pay  refund to {fake_iban(4)} queued",
        f"2026-03-02 09:06:12 DEBUG test fixture {fake_email('fixture')}  # qpii:ignore",
        "2026-03-02 09:07:30 INFO  jobs nightly export finished rows=50001234",
    ]
    (OUT / "app.log").write_text("\n".join(lines) + "\n", encoding="utf-8")


def seed_script() -> None:
    code = f'''"""Seed data for local development."""

ADMIN_EMAIL = "{fake_email('admin')}"
SUPPORT_LINE = "{fake_phone(9, 'landline')}"

TEST_USERS = [
    {{"name": "Maya Santos", "qid": "{fake_qid(7, 1989, 608)}", "phone": "{fake_phone(7, spaced=False)}"}},
]
'''
    (OUT / "seed_users.py").write_text(code, encoding="utf-8")


def main() -> None:
    OUT.mkdir(exist_ok=True)
    customers()
    payroll()
    orders()
    app_log()
    seed_script()
    print(f"wrote 5 sample files to {OUT}")


if __name__ == "__main__":
    main()
