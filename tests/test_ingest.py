"""Tests for note ingestion (m1)."""

from pathlib import Path

import pytest

from memoir.ingest import content_hash_of, ingest_folder, read_source


def _write(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


def test_ingest_reads_md_and_txt(tmp_path):
    _write(tmp_path / "2024.md", "# January\nnotes")
    _write(tmp_path / "todo.txt", "buy milk")
    _write(tmp_path / "image.png", "not a note")  # ignored

    sources = ingest_folder(tmp_path)
    paths = sorted(s.rel_path for s in sources)
    assert paths == ["2024.md", "todo.txt"]
    kinds = {s.rel_path: s.kind for s in sources}
    assert kinds["2024.md"] == "markdown"
    assert kinds["todo.txt"] == "text"


def test_ingest_skips_hidden_files_and_dirs(tmp_path):
    _write(tmp_path / ".secret.md", "hidden")
    _write(tmp_path / "real.md", "visible")
    _write(tmp_path / "sub" / "nested.md", "deep")
    _write(tmp_path / ".git" / "config.md", "git")

    sources = ingest_folder(tmp_path)
    paths = sorted(s.rel_path for s in sources)
    assert paths == ["real.md", "sub/nested.md"]


def test_ingest_is_deterministic_across_calls(tmp_path):
    _write(tmp_path / "a.md", "alpha")
    _write(tmp_path / "b.md", "beta")
    first = ingest_folder(tmp_path)
    second = ingest_folder(tmp_path)
    assert [s.content_hash for s in first] == [s.content_hash for s in second]


def test_content_hash_is_stable():
    assert content_hash_of("hello") == content_hash_of("hello")
    assert content_hash_of("hello") != content_hash_of("hello!")


def test_ingest_raises_on_missing_dir(tmp_path):
    missing = tmp_path / "does-not-exist"
    with pytest.raises(FileNotFoundError):
        ingest_folder(missing)


def test_read_source_skips_non_note(tmp_path):
    root = tmp_path
    _write(root / "note.md", "x")
    _write(root / "data.json", "{}")
    assert read_source(root, root / "note.md") is not None
    assert read_source(root, root / "data.json") is None
