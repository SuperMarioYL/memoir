"""Configuration: paths, model, and pricing constants.

Pricing reflects DeepSeek-V3 (deepseek-chat) and OpenAI GPT-4o published rates as
of 2026-09. These are the numbers used by ``memoir cost`` and the per-turn cost
line printed by ``memoir chat``. Always re-check the official pricing pages
before quoting these in marketing copy — rates change.
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path


# DeepSeek-V3 (deepseek-chat) published per-million-token rates, USD.
# cache hit: repeated prefix tokens that land in DeepSeek's prefix cache.
# cache miss: input tokens billed at the full input rate.
# See: https://api-docs.deepseek.com/quick_start/pricing
DEEPSEEK_CACHE_HIT_INPUT = 0.07
DEEPSEEK_CACHE_MISS_INPUT = 0.27
DEEPSEEK_OUTPUT = 1.10
DEEPSEEK_MODEL = "deepseek-chat"
DEEPSEEK_BASE_URL = "https://api.deepseek.com"

# OpenAI GPT-4o published per-million-token rates, USD, for the cost comparison.
# GPT-4o also offers prompt caching (~50% off cached input), shown separately.
# See: https://openai.com/api/pricing/
OPENAI_INPUT = 2.50
OPENAI_CACHED_INPUT = 1.25
OPENAI_OUTPUT = 10.00
OPENAI_MODEL = "gpt-4o"

# Default assumption for the steady-state per-turn estimate: most of a turn's
# output is the assistant reply. Used by ``memoir cost`` when no API call is
# made. ``memoir chat`` always uses the real returned token counts instead.
DEFAULT_OUTPUT_TOKENS = 300


def memoir_home() -> Path:
    """Return the on-disk home for Memoir state (``~/.memoir`` by default)."""
    env = os.environ.get("MEMOIR_HOME")
    if env:
        return Path(env).expanduser()
    return Path.home() / ".memoir"


@dataclass
class Paths:
    home: Path
    prefix_file: Path
    manifest_file: Path
    session_file: Path

    @classmethod
    def at(cls, home: Path) -> "Paths":
        return cls(
            home=home,
            prefix_file=home / "prefix.txt",
            manifest_file=home / "manifest.yaml",
            session_file=home / "session.json",
        )

    def ensure(self) -> None:
        self.home.mkdir(parents=True, exist_ok=True)


@dataclass
class Config:
    paths: Paths
    api_key: str | None = None
    model: str = DEEPSEEK_MODEL
    base_url: str = DEEPSEEK_BASE_URL
    # Pricing snapshot (USD per 1M tokens). Kept on Config so tests and cost
    # logic share one source of truth and never import magic numbers directly.
    deepseek_cache_hit_input: float = DEEPSEEK_CACHE_HIT_INPUT
    deepseek_cache_miss_input: float = DEEPSEEK_CACHE_MISS_INPUT
    deepseek_output: float = DEEPSEEK_OUTPUT
    openai_input: float = OPENAI_INPUT
    openai_cached_input: float = OPENAI_CACHED_INPUT
    openai_output: float = OPENAI_OUTPUT
    openai_model: str = OPENAI_MODEL
    default_output_tokens: int = DEFAULT_OUTPUT_TOKENS
    extra: dict = field(default_factory=dict)


def load_config() -> Config:
    """Build a Config from the environment.

    Reads ``DEEPSEEK_API_KEY`` (required for ``chat``, optional for ingest/cost),
    ``DEEPSEEK_MODEL`` and ``DEEPSEEK_BASE_URL`` if overridden, and
    ``MEMOIR_HOME`` if the state dir is relocated.
    """
    home = memoir_home()
    return Config(
        paths=Paths.at(home),
        api_key=os.environ.get("DEEPSEEK_API_KEY"),
        model=os.environ.get("DEEPSEEK_MODEL", DEEPSEEK_MODEL),
        base_url=os.environ.get("DEEPSEEK_BASE_URL", DEEPSEEK_BASE_URL).rstrip("/"),
    )
