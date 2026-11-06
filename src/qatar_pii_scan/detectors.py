"""Detectors for personal data in one piece of text.

Each detector returns matches with offsets into the original text. Arabic-Indic and
Persian digits are folded to 0-9 first; that keeps the length, so offsets still
point at the original characters.

Format rules:
- Qatar ID: 11 digits. The first is 2 or 3 (birth century), then two digits of the
  birth year, a three digit ISO 3166-1 numeric nationality code and a five digit
  serial. There is no public check digit, so a format match is all we can test.
  Source: Microsoft Purview, "Qatari ID card number entity definition".
- Phone: +974, no trunk prefix, 8 digit numbers. Mobiles start with 3, 5, 6 or 7,
  fixed lines with 4. Source: Qatar's numbering plan as filed with the ITU.
"""
from __future__ import annotations

import datetime as dt
import re
from dataclasses import dataclass
from typing import Callable

from . import iban

LEVELS = {"low": 1, "medium": 2, "high": 3}
KINDS = {
    "iban": "Qatar IBAN",
    "email": "Email address",
    "qid": "Qatar ID number",
    "phone": "Qatar phone number",
    "passport": "Passport-like number",
    "name": "Person name",
}

_DIGITS = str.maketrans("٠١٢٣٤٥٦٧٨٩۰۱۲۳۴۵۶۷۸۹", "01234567890123456789")
_HARAKAT = re.compile(r"[ؐ-ًؚ-ٰٟـ]")


@dataclass(frozen=True)
class Match:
    kind: str
    start: int
    end: int
    value: str
    confidence: str
    reason: str


def fold_digits(text: str) -> str:
    return text.translate(_DIGITS)


def normalize(text: str) -> str:
    """Lower case, no harakat or tatweel, one alef, ة as ه, ى as ي. For keyword checks only."""
    s = re.sub(r"([a-z])([A-Z])", r"\1 \2", text).lower()
    s = _HARAKAT.sub("", s)
    s = re.sub("[أإآٱ]", "ا", s).replace("ة", "ه").replace("ى", "ي")
    return re.sub(r"[_\-.]+", " ", s)


def has_keyword(context: str, words: tuple[str, ...]) -> bool:
    for word in words:
        if word.isascii():
            if re.search(rf"(?<![a-z]){re.escape(word)}(?![a-z])", context):
                return True
        elif word in context:
            return True
    return False


PHONE_WORDS = ("phone", "mobile", "mob", "tel", "telephone", "cell", "whatsapp", "contact", "msisdn",
               "هاتف", "جوال", "موبايل", "تلفون", "رقم التواصل")
QID_WORDS = ("qid", "qatar id", "qatarid", "national id", "id number", "id no", "resident permit", "rp",
             "الرقم الشخصي", "البطاقه الشخصيه", "رقم الهويه", "الهويه", "رقم البطاقه")

EMAIL = re.compile(
    r"(?<![\w.+-])[A-Za-z0-9][A-Za-z0-9._%+-]*@[A-Za-z0-9](?:[A-Za-z0-9-]*[A-Za-z0-9])?"
    r"(?:\.[A-Za-z0-9](?:[A-Za-z0-9-]*[A-Za-z0-9])?)*\.[A-Za-z]{2,24}(?![\w-])"
)
RESERVED_DOMAINS = re.compile(r"(^|\.)(example\.(com|org|net)|example|test|invalid|localhost)$", re.I)

QID = re.compile(r"(?<![\d.])[23]\d{10}(?![\d.])")
PHONE_INTL = re.compile(r"(?<![\w+])(?:\+|00)\s?974[\s.-]?[3-7]\d{3}[\s.-]?\d{4}(?!\d)")
PHONE_974 = re.compile(r"(?<![\d.])974[3-7]\d{7}(?![\d.])")
PHONE_SPACED = re.compile(r"(?<![\d+.:/-])[3-7]\d{3}[ -]\d{4}(?![\d.:/-])")
PHONE_PLAIN = re.compile(r"(?<![\d+.])[3-7]\d{7}(?![\d.])")


def qid_problem(digits: str, today: dt.date | None = None) -> str:
    """"" if `digits` fits the Qatar ID format, else the reason it does not."""
    if not re.fullmatch(r"[23]\d{10}", digits):
        return "not 11 digits starting with 2 or 3"
    year = (1900 if digits[0] == "2" else 2000) + int(digits[1:3])
    if year > (today or dt.date.today()).year:
        return f"birth year {year} is in the future"
    if not 4 <= int(digits[3:6]) <= 894:
        return f"{digits[3:6]} is outside the ISO 3166-1 numeric range"
    return ""


def find_emails(text: str, folded: str, context: str) -> list[Match]:
    out = []
    for m in EMAIL.finditer(text):
        domain = m.group().rsplit("@", 1)[1]
        if RESERVED_DOMAINS.search(domain):
            out.append(Match("email", m.start(), m.end(), m.group(), "low", "reserved example domain"))
        else:
            out.append(Match("email", m.start(), m.end(), m.group(), "high", "email address"))
    return out


def find_qids(text: str, folded: str, context: str) -> list[Match]:
    out = []
    keyword = has_keyword(context, QID_WORDS)
    for m in QID.finditer(folded):
        if qid_problem(m.group()):
            continue
        level, reason = ("high", "Qatar ID format, ID keyword nearby") if keyword else ("medium", "Qatar ID format")
        out.append(Match("qid", m.start(), m.end(), text[m.start():m.end()], level, reason))
    return out


def find_phones(text: str, folded: str, context: str) -> list[Match]:
    out = []
    keyword = has_keyword(context, PHONE_WORDS)
    for m in PHONE_INTL.finditer(folded):
        out.append(Match("phone", m.start(), m.end(), text[m.start():m.end()], "high", "+974 number"))
    for m in PHONE_974.finditer(folded):
        out.append(Match("phone", m.start(), m.end(), text[m.start():m.end()], "medium", "974 and 8 digits"))
    for m in PHONE_SPACED.finditer(folded):
        level = "medium" if keyword else "low"
        out.append(Match("phone", m.start(), m.end(), text[m.start():m.end()], level, "8 digits written like a phone number"))
    if keyword:
        for m in PHONE_PLAIN.finditer(folded):
            out.append(Match("phone", m.start(), m.end(), text[m.start():m.end()], "medium", "8 digits, phone keyword nearby"))
    return out


IBAN_TEXT = re.compile(r"(?<![A-Za-z0-9])QA\d{2}(?: ?[A-Za-z0-9]){25}(?![A-Za-z0-9])", re.I)


def find_ibans(text: str, folded: str, context: str) -> list[Match]:
    out = []
    for m in IBAN_TEXT.finditer(folded):
        value = text[m.start():m.end()]
        candidate = iban.compact(m.group())
        if not iban.QA_IBAN.fullmatch(candidate):
            continue
        if iban.mod97(candidate) == 1:
            out.append(Match("iban", m.start(), m.end(), value, "high", "Qatar IBAN, check digits valid"))
        else:
            out.append(Match("iban", m.start(), m.end(), value, "low", "Qatar IBAN shape, check digits do not match"))
    return out


PASSPORT_WORDS = ("passport", "passport no", "جواز", "جواز السفر", "رقم الجواز")
PASSPORT = re.compile(r"(?<![A-Za-z0-9])(?:[A-Za-z]{1,2}\d{6,8}|\d{8,9})(?![A-Za-z0-9])")


def find_passports(text: str, folded: str, context: str) -> list[Match]:
    """Only with a passport keyword in the line or field name. Formats differ by country."""
    if not has_keyword(context, PASSPORT_WORDS):
        return []
    return [Match("passport", m.start(), m.end(), text[m.start():m.end()], "medium", "passport keyword nearby")
            for m in PASSPORT.finditer(folded)]


# Names are a guess. Everything below is low confidence.
NAME_FIELD = re.compile(r"(?<![a-z])(name|full name|first name|last name|surname|customer|employee|contact person"
                        r"|الاسم|اسم)(?![a-z])")
NOT_PERSON = re.compile(r"(?<![a-z])(file|host|user|product|company|sheet|table|column|field|bucket|domain|server"
                        r"|app|project|event|class|module|package|branch|tag|org|shop|store|brand|item|service"
                        r"|queue|topic|image|repo|path|type|db|database|schema|model|display|key|bank)(?![a-z])")
LATIN_WORD = r"[A-Z][a-z]+(?:[-'][A-Z]?[a-z]+)*"
ARABIC_WORD = r"[\u0621-\u064A]{2,}"
NAME_VALUE = re.compile(rf"^\s*(?:{LATIN_WORD}(?:\s+{LATIN_WORD}){{0,4}}|{ARABIC_WORD}(?:\s+{ARABIC_WORD}){{0,5}})\s*$")
HONORIFIC_EN = re.compile(rf"\b(?:Mr|Mrs|Ms|Miss|Dr|Eng)\.?\s+({LATIN_WORD}(?:\s+{LATIN_WORD}){{0,3}})")
HONORIFIC_AR = re.compile(rf"(?:السيد|السيدة|الأستاذ|الأستاذة|الدكتور|الدكتورة|المهندس|المهندسة)\s+({ARABIC_WORD}(?:\s+{ARABIC_WORD}){{0,3}})")
NAME_ASSIGN = re.compile(rf"""(?i:\b(?:full_?name|first_?name|last_?name|customer_?name|name))["']?\s*[:=]\s*["']?({LATIN_WORD}(?:\s+{LATIN_WORD}){{1,3}})""")
ARABIC_NASAB = re.compile(rf"{ARABIC_WORD}\s+(?:بن|بنت)\s+{ARABIC_WORD}(?:\s+{ARABIC_WORD})?")


def is_name_field(field: str) -> bool:
    f = normalize(field)
    return bool(NAME_FIELD.search(f)) and not NOT_PERSON.search(f)


def find_names(text: str, folded: str, context: str, field: str = "") -> list[Match]:
    if field and is_name_field(field) and NAME_VALUE.match(text):
        s = len(text) - len(text.lstrip())
        return [Match("name", s, len(text.rstrip()), text.strip(), "low", "value in a name field")]
    out = []
    for pattern, reason in ((HONORIFIC_EN, "title before a name"), (HONORIFIC_AR, "title before a name"),
                            (NAME_ASSIGN, "assigned to a name variable")):
        for m in pattern.finditer(text):
            out.append(Match("name", m.start(1), m.end(1), m.group(1), "low", reason))
    for m in ARABIC_NASAB.finditer(text):
        out.append(Match("name", m.start(), m.end(), m.group(), "low", "Arabic name with bin or bint"))
    return out


Detector = Callable[[str, str, str], list[Match]]
DETECTORS: list[Detector] = [find_ibans, find_emails, find_qids, find_phones, find_passports]


def detect(text: str, field: str = "") -> list[Match]:
    """All matches in `text`. `field` is a column header or JSON key, if there is one."""
    if not text:
        return []
    folded = fold_digits(text)
    context = normalize(f"{field} {text}")
    taken: list[Match] = []
    runs = [d(text, folded, context) for d in DETECTORS] + [find_names(text, folded, context, field)]
    for found in runs:
        for m in sorted(found, key=lambda m: -LEVELS[m.confidence]):
            if all(m.end <= t.start or m.start >= t.end for t in taken):
                taken.append(m)
    return sorted(taken, key=lambda m: m.start)
