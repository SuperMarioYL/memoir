"""Tests for note ingestion (m1) and skipped-file surfacing (m4)."""

import os
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

    result = ingest_folder(tmp_path)
    paths = sorted(s.rel_path for s in result.sources)
    assert paths == ["2024.md", "todo.txt"]
    kinds = {s.rel_path: s.kind for s in result.sources}
    assert kinds["2024.md"] == "markdown"
    assert kinds["todo.txt"] == "text"


def test_ingest_skips_hidden_files_and_dirs(tmp_path):
    _write(tmp_path / ".secret.md", "hidden")
    _write(tmp_path / "real.md", "visible")
    _write(tmp_path / "sub" / "nested.md", "deep")
    _write(tmp_path / ".git" / "config.md", "git")

    result = ingest_folder(tmp_path)
    paths = sorted(s.rel_path for s in result.sources)
    assert paths == ["real.md", "sub/nested.md"]


def test_ingest_is_deterministic_across_calls(tmp_path):
    _write(tmp_path / "a.md", "alpha")
    _write(tmp_path / "b.md", "beta")
    first = ingest_folder(tmp_path)
    second = ingest_folder(tmp_path)
    assert [s.content_hash for s in first.sources] == [s.content_hash for s in second.sources]


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


# ---- v0.3.0: note decoding ------------------------------------------------


def test_read_source_strips_utf8_bom(tmp_path):
    (tmp_path / "bom.md").write_bytes("\ufeff# title\nbody\n".encode("utf-8"))
    src = read_source(tmp_path, tmp_path / "bom.md")
    assert src is not None
    assert src.content.startswith("# title")
    assert "\ufeff" not in src.content


def test_ingest_reports_non_utf8_notes_instead_of_mangling_them(tmp_path):
    # A GB18030 note used to be decoded with errors="replace", so the Chinese
    # text became U+FFFD in the prefix while ingest reported success.
    (tmp_path / "gbk.md").write_bytes("我的中文笔记".encode("gb18030"))
    _write(tmp_path / "ok.md", "# fine\n")

    result = ingest_folder(tmp_path)
    assert [s.rel_path for s in result.sources] == ["ok.md"]
    assert [s.rel_path for s in result.skipped] == ["gbk.md"]
    assert "UTF-8" in result.skipped[0].reason
    assert all("\ufffd" not in s.content for s in result.sources)


@pytest.mark.skipif(
    not hasattr(os, "geteuid") or os.geteuid() == 0,
    reason="unreadable-file setup needs a non-root user",
)
def test_ingest_records_unreadable_files_instead_of_dropping_them(tmp_path):
    _write(tmp_path / "locked.md", "secret")
    _write(tmp_path / "open.md", "readable")
    (tmp_path / "locked.md").chmod(0o000)

    result = ingest_folder(tmp_path)
    assert [s.rel_path for s in result.sources] == ["open.md"]
    assert [s.rel_path for s in result.skipped] == ["locked.md"]
    assert result.skipped[0].reason  # carries the OS error text
