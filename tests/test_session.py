"""Tests for session storage hardening (m4), conversation folding (m5) and fold
durability across a re-ingest (v0.3.0)."""

import shutil

import yaml
from pathlib import Path

from click.testing import CliRunner

from memoir.cli import cli
from memoir.config import Config, Paths
from memoir.session import Session, folded_block, load_session, save_session, Turn

NOTES = Path(__file__).resolve().parent.parent / "examples" / "notes"


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

    outputs = []
    for i in range(2):
        home = tmp_path / f"home{i}"
        home.mkdir()
        _ingest_examples(home, monkeypatch)
        _save_turns(home, pairs)
        monkeypatch.setenv("MEMOIR_HOME", str(home))
        result = CliRunner().invoke(cli, ["fold"])
        assert result.exit_code == 0, result.output
        outputs.append((home / "prefix.txt").read_bytes())

    # Two independent folds of identical turns must produce identical bytes.
    assert outputs[0] == outputs[1]


# ---- fold durability across a re-ingest (v0.3.0) ---------------------------


def _manifest(home: Path) -> dict:
    return yaml.safe_load((home / "manifest.yaml").read_text(encoding="utf-8"))


def test_fold_survives_reingest(tmp_path, monkeypatch):
    """Re-ingesting notes must not discard folded conversation.

    Until v0.3.0 the folded block lived only in prefix.txt and every ingest
    rebuilt that file from the notes folder, so the documented "add a note, then
    ingest again" flow erased the conversation without a warning.
    """
    notes = tmp_path / "notes"
    shutil.copytree(NOTES, notes)
    home = tmp_path / "home"
    monkeypatch.setenv("MEMOIR_HOME", str(home))
    runner = CliRunner()

    assert runner.invoke(cli, ["ingest", str(notes)]).exit_code == 0
    _save_turns(home, [("user", "Where did I travel?"), ("assistant", "Lisbon, in May.")])
    assert runner.invoke(cli, ["fold"]).exit_code == 0

    folded_hash = _manifest(home)["prefix_hash"]
    assert "Lisbon, in May." in (home / "prefix.txt").read_text(encoding="utf-8")
    assert (home / "folded.md").exists()

    # Re-ingesting the unchanged notes reproduces exactly what fold produced.
    assert runner.invoke(cli, ["ingest", str(notes)]).exit_code == 0
    assert _manifest(home)["prefix_hash"] == folded_hash

    # Adding a note and re-ingesting keeps the folded turns and adds the note.
    (notes / "extra.md").write_text("# Extra\nremember this too\n", encoding="utf-8")
    assert runner.invoke(cli, ["ingest", str(notes)]).exit_code == 0
    prefix = (home / "prefix.txt").read_text(encoding="utf-8")
    assert "Lisbon, in May." in prefix
    assert "remember this too" in prefix
