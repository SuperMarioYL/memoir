"""Memoir CLI — ingest, chat, cost, status.

Commands
--------
* ``memoir ingest <notes_dir>`` — build the cache-stable personal-history prefix.
* ``memoir chat``               — talk to DeepSeek with your full context; each
  turn prints the DeepSeek cache-hit cost and the OpenAI equivalent.
* ``memoir cost``               — dollar comparison for your actual prefix.
* ``memoir status``             — manifest + session summary.
"""

from __future__ import annotations

import sys

import click
from rich.console import Console
from rich.table import Table

from . import __version__
from .config import load_config
from .cost import (
    actual_turn_cost,
    estimate_per_turn,
    format_usd,
)
from .deepseek_client import DeepSeekError, chat as deepseek_chat
from .ingest import ingest_folder
from .prefix import assemble_prefix, load_manifest, load_prefix_text, write_prefix
from .session import build_messages, load_session, reset_session, save_session

console = Console()


def _require_prefix(config) -> str:
    """Return the prefix text or exit with a friendly message."""
    text = load_prefix_text(config.paths.home)
    if text is None:
        console.print(
            "[red]No prefix found.[/red] Run [cyan]memoir ingest <notes_dir>[/cyan] first."
        )
        raise SystemExit(1)
    return text


@click.group()
@click.version_option(__version__, prog_name="memoir")
def cli() -> None:
    """Memoir — consumer AI that remembers your whole life on DeepSeek prefix-cache."""


@cli.command()
@click.argument("notes_dir", type=click.Path(exists=True, file_okay=False))
def ingest(notes_dir: str) -> None:
    """Build the cache-stable personal-history prefix from a notes folder."""
    config = load_config()
    sources = ingest_folder(notes_dir)
    if not sources:
        console.print(f"[yellow]No notes (.md/.txt) found in {notes_dir}.[/yellow]")
        raise SystemExit(1)

    prefix = assemble_prefix(sources, model=config.model)
    write_prefix(prefix, config.paths.home)

    table = Table(title=f"Ingested {len(sources)} note(s)", show_header=True)
    table.add_column("Source", style="cyan", no_wrap=True)
    table.add_column("Kind", style="magenta")
    table.add_column("Tokens", justify="right")
    for s in prefix.sources:
        table.add_row(s.path, s.kind, str(s.token_count))
    console.print(table)

    console.print(
        f"\n[green]Prefix assembled.[/green] "
        f"tokens=[bold]{prefix.total_tokens}[/bold]  "
        f"sources=[bold]{len(prefix.sources)}[/bold]  "
        f"hash=[bold]{prefix.prefix_hash}[/bold]  "
        f"cache_stable=[bold]{prefix.cache_stable}[/bold]"
    )
    console.print(f"written to [dim]{config.paths.home}[/dim]")


@cli.command()
@click.option("--reset", is_flag=True, help="Clear the saved conversation before starting.")
def chat(reset: bool) -> None:
    """Chat with DeepSeek over your full personal history.

    Your ingested prefix is sent as the system message every turn. DeepSeek's
    prefix cache discounts the repeated prefix; the cost line shows what you
    paid on DeepSeek vs. what the same turn would cost on GPT-4o.
    """
    config = load_config()
    prefix_text = _require_prefix(config)
    if not config.api_key:
        console.print(
            "[red]DEEPSEEK_API_KEY is not set.[/red] "
            "Run [cyan]export DEEPSEEK_API_KEY=...[/cyan] first."
        )
        raise SystemExit(1)

    session = load_session(config)
    if reset:
        session.clear()
        reset_session(config)

    console.print(
        f"[bold]Memoir chat[/bold] — model [cyan]{config.model}[/cyan], "
        f"prefix loaded. Type your question; Ctrl-D or 'exit' to quit.\n"
    )

    while True:
        try:
            user = console.input("[bold cyan]you>[/bold cyan] ").strip()
        except (EOFError, KeyboardInterrupt):
            console.print("\n[dim]bye[/dim]")
            break
        if not user or user.lower() in {"exit", "quit", ":q"}:
            console.print("[dim]bye[/dim]")
            break

        messages = build_messages(prefix_text, session, user)
        try:
            result = deepseek_chat(config, messages)
        except DeepSeekError as exc:
            console.print(f"[red]error:[/red] {exc}")
            continue

        console.print(f"\n[bold magenta]memoir>[/bold magenta] {result.content}\n")
        session.add("user", user)
        session.add("assistant", result.content)
        save_session(config, session)

        deepseek_cost, openai_cost = actual_turn_cost(
            config,
            cache_hit_tokens=result.cache_hit_tokens,
            cache_miss_tokens=result.cache_miss_tokens,
            completion_tokens=result.completion_tokens,
            prompt_tokens=result.prompt_tokens,
        )
        _print_turn_cost(result, deepseek_cost, openai_cost)


def _print_turn_cost(result, deepseek_cost: float, openai_cost: float) -> None:
    cache_total = result.cache_hit_tokens + result.cache_miss_tokens
    hit_rate = (
        result.cache_hit_tokens / cache_total * 100 if cache_total else 0.0
    )
    console.print(
        f"[dim]tokens: prompt={result.prompt_tokens} "
        f"(cache hit {result.cache_hit_tokens} / miss {result.cache_miss_tokens}, "
        f"{hit_rate:.0f}% hit) · output={result.completion_tokens}[/dim]"
    )
    console.print(
        f"[green]DeepSeek prefix-cache: {format_usd(deepseek_cost)}/turn[/green]  "
        f"[red]OpenAI equivalent: {format_usd(openai_cost)}/turn[/red]"
    )


@cli.command()
@click.option(
    "--output-tokens",
    type=int,
    default=None,
    help="Assumed output tokens per turn for the estimate.",
)
def cost(output_tokens: int | None) -> None:
    """Show the dollar cost comparison for your actual prefix.

    Steady state assumes your prefix lands in DeepSeek's prefix cache (cache
    hit) on every turn after the first. The first-turn (cache miss) line is
    shown for honesty. OpenAI is shown with and without its prompt-caching
    discount.
    """
    config = load_config()
    manifest = load_manifest(config.paths.home)
    if manifest is None:
        console.print(
            "[red]No prefix found.[/red] Run [cyan]memoir ingest <notes_dir>[/cyan] first."
        )
        raise SystemExit(1)

    prefix_tokens = int(manifest.get("total_tokens", 0))
    cb = estimate_per_turn(config, prefix_tokens, output_tokens)

    table = Table(
        title=f"Per-turn cost — prefix {prefix_tokens:,} tokens, "
        f"~{cb.output_tokens} output tokens",
        show_header=True,
    )
    table.add_column("Provider", style="bold")
    table.add_column("Assumption", style="cyan")
    table.add_column("Per turn", justify="right", style="green")
    table.add_row(
        "DeepSeek",
        f"cache hit (steady state) — {config.model}",
        format_usd(cb.deepseek_per_turn),
    )
    table.add_row(
        "DeepSeek",
        "cache miss (first turn)",
        format_usd(cb.deepseek_first_turn),
    )
    table.add_row(
        f"OpenAI {config.openai_model}",
        "no prompt caching",
        format_usd(cb.openai_per_turn),
    )
    table.add_row(
        f"OpenAI {config.openai_model}",
        "with prompt caching (~50% off cached)",
        format_usd(cb.openai_cached_per_turn),
    )
    console.print(table)

    console.print(
        f"\n[green]Savings:[/green] OpenAI no-cache minus DeepSeek steady-state = "
        f"[bold]{format_usd(cb.savings_vs_openai)}[/bold]/turn "
        f"({cb.ratio:.0f}x cheaper on DeepSeek)"
    )
    console.print(
        "[dim]Rates are a published pricing snapshot (2026-09); re-check the "
        "provider pages before quoting.[/dim]"
    )


@cli.command()
def status() -> None:
    """Show the current manifest and session summary."""
    config = load_config()
    manifest = load_manifest(config.paths.home)
    if manifest is None:
        console.print("[yellow]No prefix ingested yet.[/yellow]")
        console.print("Run [cyan]memoir ingest <notes_dir>[/cyan] to build one.")
        return

    table = Table(title="Memoir status", show_header=False)
    table.add_column("field", style="bold cyan")
    table.add_column("value")
    table.add_row("sources", str(manifest.get("source_count", 0)))
    table.add_row("total_tokens", f"{manifest.get('total_tokens', 0):,}")
    table.add_row("prefix_hash", str(manifest.get("prefix_hash", "")))
    table.add_row("cache_stable", str(manifest.get("cache_stable", "")))
    table.add_row("model", str(manifest.get("model", "")))
    table.add_row("home", str(config.paths.home))
    console.print(table)

    session = load_session(config)
    console.print(f"\nsession turns: [bold]{len(session.turns)}[/bold]")


def main() -> None:
    """Entry point referenced by the ``memoir`` console script."""
    try:
        cli()
    except SystemExit:
        raise
    except BrokenPipeError:
        # head/pager closed stdout; exit quietly
        sys.stderr.close()
        raise SystemExit(0)


if __name__ == "__main__":
    main()
