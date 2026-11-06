import pytest

from qatar_pii_scan.fake import fake_email, fake_phone, fake_qid
from qatar_pii_scan.rules import Allowlist, is_ignored, load_ignore, normalize_value, value_hash
from qatar_pii_scan.scanner import scan


def test_ignore_patterns():
    pats = ["*.min.js", "tests/fixtures/", "docs/**/*.md"]
    assert is_ignored("web/app.min.js", pats)
    assert is_ignored("tests/fixtures/users.csv", pats)
    assert is_ignored("pkg/tests/fixtures/a.json", pats)
    assert is_ignored("docs/guide/setup.md", pats)
    assert is_ignored("docs/setup.md", pats)
    assert not is_ignored("src/app.js", pats)
    assert not is_ignored("tests/test_x.py", pats)


def test_normalize_and_hash():
    assert normalize_value("+974 5000-0001") == "+97450000001"
    assert normalize_value("+٩٧٤ ٥٠٠٠ ٠٠٠١") == "+97450000001"
    assert value_hash("+974 5000 0001") == value_hash("+97450000001")


def test_allowlist_file(tmp_path):
    f = tmp_path / "allow"
    f.write_text(
        "# known values\n"
        "support@example.qa\n"
        f"sha256:{value_hash(fake_phone(1))}\n"
        "regex:\\+974 4000 \\d{4}\n"
        "kind:name\n"
        "kind:qid tests/*\n",
        encoding="utf-8",
    )
    allow = Allowlist.load(f)
    assert allow.allows("email", "SUPPORT@example.qa", "a.txt")
    assert allow.allows("phone", "+97450000001", "a.txt")
    assert allow.allows("phone", "+974 4000 1234", "a.txt")
    assert not allow.allows("phone", "+974 5000 0002", "a.txt")
    assert allow.allows("name", "Anyone", "a.txt")
    assert allow.allows("qid", fake_qid(1), "tests/data.csv")
    assert not allow.allows("qid", fake_qid(1), "src/data.csv")


def test_allowlist_errors(tmp_path):
    f = tmp_path / "allow"
    f.write_text("kind:dna\n", encoding="utf-8")
    with pytest.raises(ValueError, match="unknown kind"):
        Allowlist.load(f)
    f.write_text("regex:(\n", encoding="utf-8")
    with pytest.raises(ValueError, match="bad regex"):
        Allowlist.load(f)


def test_scan_with_rules(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    (tmp_path / "keep.txt").write_text(f"{fake_email('a')}\n{fake_email('b')}  # qpii:ignore\n", encoding="utf-8")
    (tmp_path / "skip.log").write_text(fake_email("c"), encoding="utf-8")
    (tmp_path / ".qpiiignore").write_text("*.log\n", encoding="utf-8")
    (tmp_path / ".qpii-allow").write_text("a@example.qa\n", encoding="utf-8")
    plain = scan(["."])
    assert len(plain.findings) == 2
    filtered = scan(["."], ignore=load_ignore(".qpiiignore"), allow=Allowlist.load(".qpii-allow"))
    assert filtered.findings == []
    assert "skip.log" not in filtered.files
