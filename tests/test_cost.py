"""Tests for cost comparison (m3)."""

import pytest

from memoir.config import Config, Paths
from memoir.cost import (
    actual_turn_cost,
    estimate_per_turn,
    format_usd,
)


@pytest.fixture()
def config(tmp_path) -> Config:
    # Fixed-rate config (defaults from module constants) at a tmp home so the
    # tests never touch ~/.memoir or read environment variables.
    return Config(paths=Paths.at(tmp_path))


def test_estimate_per_turn_steady_state_uses_cache_hit_rate(config):
    cb = estimate_per_turn(config, prefix_tokens=20_000, output_tokens=300)
    # DeepSeek steady state: 20000 * 0.07/1M + 300 * 1.10/1M
    expected_deepseek = 20_000 * 0.07 / 1_000_000 + 300 * 1.10 / 1_000_000
    assert abs(cb.deepseek_per_turn - expected_deepseek) < 1e-9


def test_estimate_first_turn_uses_cache_miss_rate(config):
    cb = estimate_per_turn(config, prefix_tokens=20_000, output_tokens=300)
    expected_first = 20_000 * 0.27 / 1_000_000 + 300 * 1.10 / 1_000_000
    assert abs(cb.deepseek_first_turn - expected_first) < 1e-9


def test_openai_no_cache_is_far_more_expensive(config):
    cb = estimate_per_turn(config, prefix_tokens=20_000, output_tokens=300)
    expected_openai = 20_000 * 2.50 / 1_000_000 + 300 * 10.00 / 1_000_000
    assert abs(cb.openai_per_turn - expected_openai) < 1e-9
    assert cb.openai_per_turn > cb.deepseek_per_turn
    assert cb.ratio > 1


def test_actual_turn_cost_with_full_cache_hit_is_cheap(config):
    # All 20k prefix tokens land in cache; nothing missed.
    deepseek, openai = actual_turn_cost(
        config,
        cache_hit_tokens=20_000,
        cache_miss_tokens=0,
        completion_tokens=300,
        prompt_tokens=20_000,
    )
    expected = 20_000 * 0.07 / 1_000_000 + 300 * 1.10 / 1_000_000
    assert abs(deepseek - expected) < 1e-9
    assert openai > deepseek


def test_actual_turn_cost_with_no_cache_is_expensive(config):
    # No cache hit at all — full cache-miss rate on the prefix.
    deepseek, openai = actual_turn_cost(
        config,
        cache_hit_tokens=0,
        cache_miss_tokens=20_000,
        completion_tokens=300,
        prompt_tokens=20_000,
    )
    expected = 20_000 * 0.27 / 1_000_000 + 300 * 1.10 / 1_000_000
    assert abs(deepseek - expected) < 1e-9


def test_savings_and_ratio(config):
    cb = estimate_per_turn(config, prefix_tokens=20_000, output_tokens=300)
    assert cb.savings_vs_openai == pytest.approx(
        cb.openai_per_turn - cb.deepseek_per_turn
    )
    assert cb.ratio == pytest.approx(cb.openai_per_turn / cb.deepseek_per_turn)


def test_format_usd_scales_precision():
    assert format_usd(0.001234).startswith("$0.0012")
    assert format_usd(0.5) == "$0.500"
    assert format_usd(12.0) == "$12.00"
