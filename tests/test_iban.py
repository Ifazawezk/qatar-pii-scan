import pytest

from qatar_pii_scan import iban
from qatar_pii_scan.detectors import detect, qid_problem
from qatar_pii_scan.fake import fake_email, fake_iban, fake_phone, fake_qid
from qatar_pii_scan.mask import mask

# The Qatar example from the SWIFT IBAN registry.
REGISTRY_EXAMPLE = "QA58DOHB00001234567890ABCDEFG"


def test_registry_example_is_valid():
    assert iban.is_valid(REGISTRY_EXAMPLE)
    assert iban.is_valid(iban.group(REGISTRY_EXAMPLE))
    assert not iban.is_valid(REGISTRY_EXAMPLE.replace("58", "59"))
    assert not iban.is_valid("QA58DOHB0000123456789")


def test_make_iban_round_trip():
    assert iban.compact(iban.make_iban("DOHB", "00001234567890ABCDEFG")) == REGISTRY_EXAMPLE
    value = fake_iban(7)
    assert value.startswith("QA") and " FAKE " in value and iban.is_valid(value)
    with pytest.raises(ValueError):
        iban.make_iban("D0HB", "1")


def test_detect_ibans_in_text():
    grouped = fake_iban(3)
    found = detect(f"Transfer to {grouped} please")
    assert [(m.kind, m.value, m.confidence) for m in found] == [("iban", grouped, "high")]
    bad = REGISTRY_EXAMPLE.replace("58", "57")
    assert [(m.kind, m.confidence) for m in detect(bad)] == [("iban", "low")]
    assert detect("QA58DOHB0000") == []


def test_iban_wins_over_digits_inside_it():
    value = iban.make_iban("FAKE", "000000028463400012345")
    assert [m.kind for m in detect(value)] == ["iban"]


def test_mask_iban_keeps_country_and_tail():
    masked = mask(fake_iban(12), "iban")
    assert masked.startswith("QA** ****") and masked.replace(" ", "").endswith("*12")
    assert "FAKE" not in masked


def test_fake_values_pass_format_checks():
    assert qid_problem(fake_qid(5)) == ""
    assert fake_qid(5, birth_year=2004, country=356) == "30435600005"
    assert [m.kind for m in detect(fake_phone(1))] == ["phone"]
    assert fake_phone(2, "landline", spaced=False) == "40000002"
    assert detect(fake_email("noor"))[0].confidence == "high"
    with pytest.raises(ValueError):
        fake_qid(1000)
