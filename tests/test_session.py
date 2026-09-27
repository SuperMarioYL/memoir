"""Tests for session storage hardening (m4) and conversation folding (m5)."""

import yaml
from pathlib import Path

from click.testing import CliRunner

from memoir.cli import cli
from memoir.config import Config, Paths
from memoir.session import Session, folded_block, load_session, save_session, Turn


def _config(tmp_path: Path) -> Config:
    return Config(paths=Paths.at(tmp_path))


def _save_turns(tmp_path: Path, pairs: list[tuple[str, str]]) -> None:
    session = Session(turns=[Turn(role=r, content=c) for r, c in pairs])
    save_session(_config(tmp_path), session)


# ---- load_session hardening (m4) ------------------------------------------


def test_load_session_missing_file_is_empty(tmp_path):
    assert load_session(_config(tmp_path)).turns == []


def test_load_session_corrupt_json_starts_fresh(tmp_path):
    (tmp_path / "session.json").write_text("{not json", encoding="utf-8")
    assert load_session(_config(tmp_path)).turns == []


def test_load_session_non_dict_payload_starts_fresh(tmp_path):
    (tmp_path / "session.json").write_text("[1, 2, 3]", encoding="utf-8")
    assert load_session(_config(tmp_path)).turns == []


def test_load_session_drops_malformed_turns(tmp_path):
    (tmp_path / "session.json").write_text(
        '{"turns": [{"role": "user", "content": "keep"},'
        ' {"role": "system", "content": "wrong role"},'
        ' {"role": "user"},'
        ' "junk",'
        ' {"role": "assistant", "content": "keep too"}]}',
        encoding="utf-8",
    )
    turns = load_session(_config(tmp_path)).turns
    assert [(t.role, t.content) for t in turns] == [
        ("user", "keep"),
        ("assistant", "keep too"),
    ]


def test_session_round_trip(tmp_path):
    config = _config(tmp_path)
    session = Session(turns=[Turn(role="user", content="q"), Turn(role="assistant", content="a")])
    save_session(config, session)
    loaded = load_session(config)
    assert [(t.role, t.content) for t in loaded.turns] == [
        ("user", "q"),
        ("assistant", "a"),
    ]


# ---- folded_block determinism (m5) -----------------------------------------


def test_folded_block_is_deterministic():
    turns = [Turn(role="user", content="q1"), Turn(role="assistant", content="a1")]
    # Same turns in the same order -> byte-identical output (no timestamps).
    assert folded_block(turns) == folded_block(
        [Turn(role="user", content="q1"), Turn(role="assistant", content="a1")]
    )


def test_folded_block_labels_roles():
    block = folded_block([Turn(role="user", content="hi"), Turn(role="assistant", content="hello")])
    assert "### user\nhi" in block
    assert "### assistant\nhello" in block
    assert block.startswith("## Folded conversation")


# ---- fold command end-to-end (m5, no network) ------------------------------


def _ingest_examples(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setenv("MEMOIR_HOME", str(tmp_path))
    runner = CliRunner()
    result = runner.invoke(cli, ["ingest", str(Path(__file__).resolve().parent.parent / "examples" / "notes")])
    assert result.exit_code == 0, result.output


def test_fold_command_appends_turns_and_clears_session(tmp_path, monkeypatch):
    _ingest_examples(tmp_path, monkeypatch)
    _save_turns(tmp_path, [("user", "What did I decide about DeepSeek?"), ("assistant", "You chose it for the cache pricing.")])

    monkeypatch.setenv("MEMOIR_HOME", str(tmp_path))
    runner = CliRunner()
    result = runner.invoke(cli, ["fold"])
    assert result.exit_code == 0, result.output

    prefix_text = (tmp_path / "prefix.txt").read_text(encoding="utf-8")
    assert "## Folded conversation" in prefix_text
    assert "What did I decide about DeepSeek?" in prefix_text
    assert not (tmp_path / "session.json").exists()

    manifest = yaml.safe_load((tmp_path / "manifest.yaml").read_text(encoding="utf-8"))
    assert manifest["prefix_hash"]  # hash updated alongside the text


def test_fold_command_without_session_is_noop(tmp_path, monkeypatch):
    _ingest_examples(tmp_path, monkeypatch)
    before = (tmp_path / "prefix.txt").read_bytes()

    monkeypatch.setenv("MEMOIR_HOME", str(tmp_path))
    runner = CliRunner()
    result = runner.invoke(cli, ["fold"])
    assert result.exit_code == 0, result.output
    assert "No conversation to fold" in result.output
    assert (tmp_path / "prefix.txt").read_bytes() == before


def test_fold_is_deterministic_for_same_turns(tmp_path, monkeypatch):
    pairs = [("user", "q"), ("assistant", "a")]

    hashes = []
    for _ in range(2):
        # Re-ingest so each fold starts from the same base prefix; otherwise
        # the second fold would extend the first fold's output.
        _ingest_examples(tmp_path, monkeypatch)
        _save_turns(tmp_path, pairs)
        monkeypatch.setenv("MEMOIR_HOME", str(tmp_path))
        result = CliRunner().invoke(cli, ["fold"])
        assert result.exit_code == 0, result.output
        hashes.append((tmp_path / "prefix.txt").read_bytes())

    # Two folds of identical turns must produce byte-identical prefixes.
    assert hashes[0] == hashes[1]
