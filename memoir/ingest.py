"""Ingest personal notes from a local folder.

Reads ``.md`` and ``.txt`` files recursively, computes a content hash per file,
and returns a list of :class:`Source` objects. No network, no embeddings, no
retrieval — full-context only.
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

import xxhash

# Extensions treated as plain-text personal notes for v0.1.
NOTE_EXTENSIONS = {".md", ".markdown", ".txt"}

# Directories that should never be treated as personal notes.
SKIP_DIRS = {
    ".git",
    ".svn",
    ".hg",
    "node_modules",
    "__pycache__",
    ".venv",
    "venv",
}


@dataclass(frozen=True)
class Source:
    """One ingested note file.

    ``rel_path`` is the path relative to the ingested folder, used for
    deterministic ordering. ``content_hash`` is xxhash64 of the raw text so the
    ordering key is stable even if a path is renamed.
    """

    rel_path: str
    abs_path: str
    kind: str  # "markdown" or "text"
    content: str
    content_hash: str


def content_hash_of(text: str) -> str:
    """Return the xxhash64 of ``text`` (hex string)."""
    return xxhash.xxh64(text.encode("utf-8")).hexdigest()


def _kind_for(suffix: str) -> str:
    if suffix in {".md", ".markdown"}:
        return "markdown"
    return "text"


def read_source(root: Path, path: Path) -> Source | None:
    """Read a single file into a Source, or None if it is not a note.

    ``root`` is the ingested folder; ``path`` is the file within it. The
    relative path is computed from ``root`` so ordering is reproducible across
    machines.
    """
    suffix = path.suffix.lower()
    if suffix not in NOTE_EXTENSIONS:
        return None
    try:
        raw = path.read_bytes()
    except OSError:
        return None
    try:
        text = raw.decode("utf-8")
    except UnicodeDecodeError:
        text = raw.decode("utf-8", errors="replace")
    try:
        rel = path.relative_to(root).as_posix()
    except ValueError:
        rel = path.name
    return Source(
        rel_path=rel,
        abs_path=str(path),
        kind=_kind_for(suffix),
        content=text,
        content_hash=content_hash_of(text),
    )


def ingest_folder(notes_dir: str | os.PathLike) -> list[Source]:
    """Walk ``notes_dir`` recursively and return every note Source.

    Hidden files and ``SKIP_DIRS`` are skipped. The returned list is NOT sorted
    here — :func:`memoir.prefix.assemble_prefix` owns the deterministic order so
    the cache-stability property lives in one place.
    """
    root = Path(notes_dir).expanduser().resolve()
    if not root.exists():
        raise FileNotFoundError(f"notes folder not found: {root}")
    if not root.is_dir():
        raise NotADirectoryError(f"not a directory: {root}")

    sources: list[Source] = []
    for dirpath, dirnames, filenames in os.walk(root):
        # prune in-place so os.walk does not descend into ignored dirs
        dirnames[:] = [
            d for d in dirnames if d not in SKIP_DIRS and not d.startswith(".")
        ]
        for name in sorted(filenames):
            if name.startswith("."):
                continue
            src = read_source(root, Path(dirpath) / name)
            if src is not None:
                sources.append(src)
    return sources
