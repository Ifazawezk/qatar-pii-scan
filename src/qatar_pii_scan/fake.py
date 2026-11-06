"""Fake values for tests and examples. They pass the format checks but are made up.

- IBANs use the bank code FAKE, which no bank uses, with real MOD 97 check digits.
- Qatar IDs use serials 00001 to 00999, so they are easy to spot in a file.
- Emails use example.qa and phones use +974 5000, +974 6000 and +974 4000 blocks.
"""
from __future__ import annotations

from .iban import make_iban

FAKE_BANK = "FAKE"


def fake_iban(n: int) -> str:
    return make_iban(FAKE_BANK, f"{n:021d}")


def fake_qid(n: int, birth_year: int = 1990, country: int = 634) -> str:
    if not 1 <= n <= 999:
        raise ValueError("fake QID serials run from 1 to 999")
    century = "2" if birth_year < 2000 else "3"
    return f"{century}{birth_year % 100:02d}{country:03d}{n:05d}"


def fake_phone(n: int, kind: str = "mobile", spaced: bool = True) -> str:
    block = {"mobile": "5000", "mobile2": "6000", "landline": "4000"}[kind]
    number = f"{block}{n:04d}"
    return f"+974 {number[:4]} {number[4:]}" if spaced else number


def fake_email(local: str) -> str:
    return f"{local}@example.qa"
