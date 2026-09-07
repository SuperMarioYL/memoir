"""Tests for prefix assembly — the cache-stability primitive (m1)."""

from memoir.ingest import Source, content_hash_of
from memoir.prefix import (
    assemble_prefix,
    load_manifest,
    load_prefix_text,
    write_prefix,
)


def _src(path: str, content: str) -> Source:
    return Source(
        rel_path=path,
        abs_path=f"/notes/{path}",
        kind="markdown" if path.endswith(".md") else "text",
        content=content,
        content_hash=content_hash_of(content),
    )


def test_assemble_is_deterministic_regardless_of_input_order():
    """The same sources in any order must produce a byte-identical prefix."""
    a = [_src("a.md", "alpha"), _src("b.md", "beta"), _src("c.txt", "gamma")]
    b = list(reversed(a))
    p1 = assemble_prefix(a)
    p2 = assemble_prefix(b)
    assert p1.text == p2.text
    assert p1.prefix_hash == p2.prefix_hash
    assert p1.cache_stable is True
    assert p2.cache_stable is True


def test_prefix_hash_changes_when_content_changes():
    a = assemble_prefix([_src("a.md", "alpha")])
    b = assemble_prefix([_src("a.md", "alpha!")])
    assert a.prefix_hash != b.prefix_hash


def test_assemble_marks_cache_stable_true():
    p = assemble_prefix([_src("z.md", "zeta"), _src("a.md", "alpha")])
    assert p.cache_stable is True
    # ordering is by rel_path, so a.md precedes z.md
    assert p.sources[0].path == "a.md"
    assert p.sources[1].path == "z.md"


def test_manifest_has_expected_fields():
    p = assemble_prefix([_src("a.md", "alpha")], model="deepseek-chat")
    m = p.to_manifest()
    assert m["source_count"] == 1
    assert m["total_tokens"] == p.total_tokens
    assert m["prefix_hash"] == p.prefix_hash
    assert m["cache_stable"] is True
    assert m["model"] == "deepseek-chat"
    assert m["sources"][0]["path"] == "a.md"
    assert m["sources"][0]["included"] is True


def test_write_and_load_round_trip(tmp_path):
    p = assemble_prefix([_src("a.md", "alpha"), _src("b.md", "beta")])
    write_prefix(p, tmp_path)
    loaded = load_prefix_text(tmp_path)
    assert loaded is not None
    assert loaded == p.text
    m = load_manifest(tmp_path)
    assert m is not None
    assert m["source_count"] == 2
    assert m["prefix_hash"] == p.prefix_hash


def test_load_returns_none_when_absent(tmp_path):
    assert load_prefix_text(tmp_path) is None
    assert load_manifest(tmp_path) is None
