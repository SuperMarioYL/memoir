"""Cost comparison: DeepSeek prefix-cache vs. OpenAI full-price re-send.

Two entry points:

* :func:`estimate_per_turn` — the steady-state per-turn estimate used by
  ``memoir cost``. Assumes the prefix lands in DeepSeek's prefix cache
  (cache hit) on every turn after the first, which is the steady state the
  product is designed for.
* :func:`actual_turn_cost` — the real per-turn cost computed from the
  DeepSeek API's returned ``usage`` (cache_hit/miss/output). Used by
  ``memoir chat`` so the printed cost line reflects what actually happened.

Pricing lives on :class:`memoir.config.Config` so there is a single source of
truth and tests can override rates.
"""

from __future__ import annotations

from dataclasses import dataclass

from .config import Config


@dataclass
class CostBreakdown:
    """A side-by-side cost figure for one turn."""

    prefix_tokens: int
    output_tokens: int
    # DeepSeek, steady state: prefix billed at the cache-HIT rate.
    deepseek_per_turn: float
    # DeepSeek, first turn: prefix billed at the cache-MISS rate (no cache yet).
    deepseek_first_turn: float
    # OpenAI GPT-4o, no prompt caching: prefix at full input rate.
    openai_per_turn: float
    # OpenAI GPT-4o, with its prompt-caching discount (~50% off cached input).
    openai_cached_per_turn: float

    @property
    def savings_vs_openai(self) -> float:
        return self.openai_per_turn - self.deepseek_per_turn

    @property
    def ratio(self) -> float:
        if self.deepseek_per_turn <= 0:
            return float("inf")
        return self.openai_per_turn / self.deepseek_per_turn


def _per_million(tokens: int, rate: float) -> float:
    return tokens * rate / 1_000_000.0


def estimate_per_turn(
    config: Config, prefix_tokens: int, output_tokens: int | None = None
) -> CostBreakdown:
    """Estimate the per-turn cost for a prefix of ``prefix_tokens`` tokens.

    Steady-state assumes the whole prefix is a DeepSeek cache hit. The first
    turn (cache miss) is shown for honesty. OpenAI is shown both without and
    with its prompt-caching discount.
    """
    out = config.default_output_tokens if output_tokens is None else output_tokens

    deepseek_per_turn = _per_million(prefix_tokens, config.deepseek_cache_hit_input) + _per_million(
        out, config.deepseek_output
    )
    deepseek_first_turn = _per_million(
        prefix_tokens, config.deepseek_cache_miss_input
    ) + _per_million(out, config.deepseek_output)
    openai_per_turn = _per_million(prefix_tokens, config.openai_input) + _per_million(
        out, config.openai_output
    )
    openai_cached_per_turn = _per_million(
        prefix_tokens, config.openai_cached_input
    ) + _per_million(out, config.openai_output)

    return CostBreakdown(
        prefix_tokens=prefix_tokens,
        output_tokens=out,
        deepseek_per_turn=deepseek_per_turn,
        deepseek_first_turn=deepseek_first_turn,
        openai_per_turn=openai_per_turn,
        openai_cached_per_turn=openai_cached_per_turn,
    )


def actual_turn_cost(
    config: Config,
    cache_hit_tokens: int,
    cache_miss_tokens: int,
    completion_tokens: int,
    prompt_tokens: int,
) -> tuple[float, float]:
    """Compute (deepseek_actual, openai_equivalent) from real API usage.

    DeepSeek uses its real cache split. OpenAI-equivalent assumes the same
    prompt length billed at GPT-4o's full input rate (the worst case the
    product is positioned against) — that is the "what OpenAI would charge"
    line printed each turn.
    """
    deepseek = _per_million(cache_hit_tokens, config.deepseek_cache_hit_input) + _per_million(
        cache_miss_tokens, config.deepseek_cache_miss_input
    ) + _per_million(completion_tokens, config.deepseek_output)
    openai = _per_million(prompt_tokens, config.openai_input) + _per_million(
        completion_tokens, config.openai_output
    )
    return deepseek, openai


def format_usd(amount: float) -> str:
    """Format a USD amount for display: tiny amounts keep more digits."""
    if amount < 0.01:
        return f"${amount:.4f}"
    if amount < 1.0:
        return f"${amount:.3f}"
    return f"${amount:.2f}"
