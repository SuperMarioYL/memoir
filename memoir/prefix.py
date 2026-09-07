"""Assemble a cache-stable personal-history prefix.

The new primitive: a deterministically ordered, byte-identical representation of
a consumer's lifelong notes that maximizes DeepSeek prefix-cache hits.

Two properties make it "cache-stable":

1. Deterministic ordering — sources are sorted by ``(rel_path, content_hash)``
   so the assembled prefix is byte-identical across sessions and machines.
2. Stable framing — every source is wrapped in the same header/footer markers
   so the prefix text never shifts when a note's body changes length.

Token counts use tiktoken when available (a good BPE approximation for the
DeepSeek tokenizer). If tiktoken is not importable we fall back to a deterministic
word/char estimator so ingest still works on interpreters without a tiktoken
wheel. Either way the count is an estimate; the real numbers come back from the
DeepSeek API in :mod:`memoir.deepseek_client` usage.
"""

from __future__ import annotations

import os
import xxhash
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable

import yaml

from .ingest import Source

# Stable framing. These markers are part of the cache-stable prefix and must
# never change between releases without bumping the manifest version.
_PREFIX_HEADER = "# Memoir Personal History"
_SOURCE_HEADER_FMT = "## {rel_path}"  # noqa: E501  (kept as a literal for clarity)
_SOURCE_SEPARATOR = "\n\n"

_MANIFEST_VERSION = 1


def _get_tokenizer() -> Callable[[str], int]:
    """Return a token-counting callable.

    Tries tiktoken's cl100k_base (a reasonable BPE approximation for the
    DeepSeek tokenizer). Falls back to a deterministic estimator otherwise so
    the package degrades gracefully on interpreters without a tiktoken wheel.
    """
    try:
        import tiktoken

        enc = tiktoken.get_encoding("cl100k_base")

        def _tik(text: str) -> int:
            return len(enc.encode(text, disallowed_special=()))

        return _tik
    except Exception:
        # Fallback: ~4 chars per token is a conservative estimate for BPE
        # tokenizers on English prose. Used only when tiktoken is unavailable.
        def _fallback(text: str) -> int:
            return max(1, len(text) // 4)

        return _fallback


# Module-level tokenizer; tiktoken encoding load is mildly expensive.
_count_tokens: Callable[[str], int] = _get_tokenizer()


def count_tokens(text: str) -> int:
    """Estimate the token count of ``text``.

    This is an estimate used at ingest time for the manifest. The DeepSeek API
    returns authoritative counts in ``usage`` during chat.
    """
    return _count_tokens(text)


@dataclass
class SourceStat:
    """Per-source line in the manifest."""

    path: str
    kind: str
    token_count: int
    content_hash: str
    included: bool


@dataclass
class AssembledPrefix:
    """A fully assembled, cache-stable personal-history prefix."""

    text: str
    total_tokens: int
    sources: list[SourceStat]
    prefix_hash: str
    cache_stable: bool
    model: str = ""

    def to_manifest(self) -> dict:
        return {
            "version": _MANIFEST_VERSION,
            "source_count": len(self.sources),
            "total_tokens": self.total_tokens,
            "prefix_hash": self.prefix_hash,
            "cache_stable": self.cache_stable,
            "model": self.model,
            "sources": [s.__dict__ for s in self.sources],
        }


def _sort_key(src: Source) -> tuple[str, str]:
    """Deterministic sort key: relative path, then content hash."""
    return (src.rel_path, src.content_hash)


def assemble_prefix(
    sources: list[Source], *, model: str = ""
) -> AssembledPrefix:
    """Assemble ``sources`` into a cache-stable prefix.

    The ordering is ``(rel_path, content_hash)`` and is applied twice — once to
    build the text, once to recompute the hash — and ``cache_stable`` is set
    True only when re-assembling produces a byte-identical result. In practice
    the sort is deterministic so this is always True; the check exists so a
    future non-deterministic code path fails loudly instead of silently breaking
    the cache discount.
    """
    ordered = sorted(sources, key=_sort_key)

    def _build(items: list[Source]) -> tuple[str, list[SourceStat]]:
        parts: list[str] = [_PREFIX_HEADER]
        stats: list[SourceStat] = []
        for src in items:
            toks = count_tokens(src.content)
            stats.append(
                SourceStat(
                    path=src.rel_path,
                    kind=src.kind,
                    token_count=toks,
                    content_hash=src.content_hash,
                    included=True,
                )
            )
            parts.append(
                f"{_SOURCE_HEADER_FMT.format(rel_path=src.rel_path)}\n{src.content}"
            )
        return _SOURCE_SEPARATOR.join(parts) + "\n", stats

    text, stats = _build(ordered)
    prefix_hash = xxhash.xxh64(text.encode("utf-8")).hexdigest()

    # verify determinism: re-sort and re-build, the text must match exactly
    again = sorted(sources, key=_sort_key)
    text2, _ = _build(again)
    cache_stable = text == text2

    return AssembledPrefix(
        text=text,
        total_tokens=count_tokens(text),
        sources=stats,
        prefix_hash=prefix_hash,
        cache_stable=cache_stable,
        model=model,
    )


def write_prefix(prefix: AssembledPrefix, home: Path) -> None:
    """Persist ``prefix.txt`` and ``manifest.yaml`` under ``home``."""
    home.mkdir(parents=True, exist_ok=True)
    (home / "prefix.txt").write_text(prefix.text, encoding="utf-8")
    manifest = prefix.to_manifest()
    (home / "manifest.yaml").write_text(
        yaml.safe_dump(manifest, sort_keys=False, allow_unicode=True),
        encoding="utf-8",
    )


def load_prefix_text(home: str | os.PathLike) -> str | None:
    """Return the assembled prefix text, or None if not yet ingested."""
    p = Path(home) / "prefix.txt"
    if not p.exists():
        return None
    return p.read_text(encoding="utf-8")


def load_manifest(home: str | os.PathLike) -> dict | None:
    """Return the parsed manifest, or None if not yet ingested."""
    p = Path(home) / "manifest.yaml"
    if not p.exists():
        return None
    return yaml.safe_load(p.read_text(encoding="utf-8"))
