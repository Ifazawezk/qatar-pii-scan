import json

import pytest

from qatar_pii_scan.cli import main
from qatar_pii_scan.fake import fake_email, fake_qid
from qatar_pii_scan.rules import value_hash

QID = fake_qid(7)


@pytest.fixture
def repo(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    (tmp_path / "users.csv").write_text(f"id,qid,full_name\n1,{QID},Sara Yousef\n", encoding="utf-8")
    (tmp_path / "notes.txt").write_text("nothing here\n", encoding="utf-8")
    return tmp_path


def test_text_output_and_exit_code(repo, capsys):
    assert main(["scan"]) == 1
    out = capsys.readouterr().out
    assert "users.csv  row 2, column qid        qid   *********07  high" in out
    assert "2 findings in 1 of 2 files: 1 high, 0 medium, 1 low" in out
    assert QID not in out and "Sara Yousef" not in out


def test_fail_on_levels(repo, capsys):
    (repo / "users.csv").write_text("id,full_name\n1,Sara Yousef\n", encoding="utf-8")
    assert main(["scan"]) == 0
    assert main(["scan", "--fail-on", "low"]) == 1
    assert main(["scan", "--fail-on", "never", "--min-confidence", "high"]) == 0


def test_json_output_file(repo, capsys):
    assert main(["scan", "--format", "json", "-o", "r.json", "--fail-on", "never"]) == 0
    data = json.loads((repo / "r.json").read_text(encoding="utf-8"))
    assert data["counts"] == {"high": 1, "medium": 0, "low": 1}
    assert data["findings"][0]["masked"] == "*********07"
    assert "Law No. 13 of 2016" in data["note"]
    assert QID not in (repo / "r.json").read_text(encoding="utf-8")
    assert "2 findings" in capsys.readouterr().out


def test_default_allowlist_and_ignore(repo, capsys):
    (repo / ".qpii-allow").write_text(f"sha256:{value_hash(QID)}\nkind:name\n", encoding="utf-8")
    (repo / "logs").mkdir()
    (repo / "logs" / "a.log").write_text(fake_email("x"), encoding="utf-8")
    (repo / ".qpiiignore").write_text("logs/\n", encoding="utf-8")
    assert main(["scan"]) == 0
    assert "0 findings" in capsys.readouterr().out


def test_hash_command(capsys):
    assert main(["hash", "+974 5000 0001"]) == 0
    assert capsys.readouterr().out.strip() == f"sha256:{value_hash('+97450000001')}"


def test_errors(repo, capsys):
    assert main(["scan", "missing-folder"]) == 2
    (repo / "bad-allow").write_text("kind:dna\n", encoding="utf-8")
    assert main(["scan", "--allowlist", "bad-allow"]) == 2
    assert "unknown kind" in capsys.readouterr().err
