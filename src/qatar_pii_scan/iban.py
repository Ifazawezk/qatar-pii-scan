"""Qatar IBANs (ISO 13616).

A Qatar IBAN is 29 characters: QA, two check digits, a four letter bank code and
21 account characters. Moving the first four characters to the end and reading
letters as numbers (A=10 ... Z=35) gives a number that is 1 mod 97 for a valid
IBAN (ISO 7064 MOD 97-10).
"""
from __future__ import annotations

import re

QA_IBAN = re.compile(r"QA\d{2}[A-Z]{4}[A-Z0-9]{21}")


def compact(value: str) -> str:
    return re.sub(r"\s+", "", value).upper()


def mod97(iban: str) -> int:
    rearranged = iban[4:] + iban[:4]
    return int("".join(str(int(ch, 36)) for ch in rearranged)) % 97


def is_valid(value: str) -> bool:
    iban = compact(value)
    return bool(QA_IBAN.fullmatch(iban)) and mod97(iban) == 1


def group(iban: str) -> str:
    iban = compact(iban)
    return " ".join(iban[i:i + 4] for i in range(0, len(iban), 4))


def make_iban(bank: str, account: str) -> str:
    """Build a Qatar IBAN with correct check digits, printed in groups of four."""
    bban = bank.upper() + account.upper().rjust(21, "0")
    if not re.fullmatch(r"[A-Z]{4}[A-Z0-9]{21}", bban):
        raise ValueError("bank must be 4 letters and account at most 21 letters or digits")
    check = 98 - mod97("QA00" + bban)
    return group(f"QA{check:02d}{bban}")
