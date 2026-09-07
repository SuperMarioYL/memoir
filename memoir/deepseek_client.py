"""DeepSeek API client.

DeepSeek exposes an OpenAI-compatible chat completions endpoint. The response
``usage`` carries ``prompt_cache_hit_tokens`` and ``prompt_cache_miss_tokens``
in addition to the standard fields — those are what make the prefix-cache
economics visible to the user each turn.
"""

from __future__ import annotations

from dataclasses import dataclass

import httpx

from .config import Config


@dataclass
class ChatResult:
    """One chat-completion result plus the token/cache accounting."""

    content: str
    prompt_tokens: int
    completion_tokens: int
    cache_hit_tokens: int
    cache_miss_tokens: int

    @property
    def total_tokens(self) -> int:
        return self.prompt_tokens + self.completion_tokens


class DeepSeekError(RuntimeError):
    """Raised when the DeepSeek API returns an unrecoverable error."""


def _parse_usage(usage: dict | None) -> tuple[int, int, int, int]:
    """Return (prompt, completion, cache_hit, cache_miss) from raw usage.

    DeepSeek returns ``prompt_cache_hit_tokens`` / ``prompt_cache_miss_tokens``.
    Older or non-DeepSeek-compatible responses may omit them; default to 0.
    """
    if not usage:
        return 0, 0, 0, 0
    prompt = int(usage.get("prompt_tokens", 0) or 0)
    completion = int(usage.get("completion_tokens", 0) or 0)
    cache_hit = int(usage.get("prompt_cache_hit_tokens", 0) or 0)
    cache_miss = int(usage.get("prompt_cache_miss_tokens", 0) or 0)
    return prompt, completion, cache_hit, cache_miss


def chat(config: Config, messages: list[dict]) -> ChatResult:
    """Send ``messages`` to DeepSeek and return the parsed :class:`ChatResult`.

    Raises :class:`DeepSeekError` on auth failure, HTTP error, or a malformed
    response body — callers print a friendly message and keep the REPL alive.
    """
    if not config.api_key:
        raise DeepSeekError(
            "DEEPSEEK_API_KEY is not set. Run `export DEEPSEEK_API_KEY=...` "
            "before `memoir chat`."
        )
    url = f"{config.base_url}/chat/completions"
    payload = {
        "model": config.model,
        "messages": messages,
        "stream": False,
    }
    headers = {
        "Authorization": f"Bearer {config.api_key}",
        "Content-Type": "application/json",
    }
    try:
        resp = httpx.post(url, json=payload, headers=headers, timeout=120.0)
    except httpx.HTTPError as exc:
        raise DeepSeekError(f"network error talking to DeepSeek: {exc}") from exc

    if resp.status_code == 401:
        raise DeepSeekError("DeepSeek rejected the API key (401).")
    if resp.status_code >= 400:
        raise DeepSeekError(
            f"DeepSeek API error {resp.status_code}: {resp.text[:300]}"
        )

    try:
        body = resp.json()
    except ValueError as exc:
        raise DeepSeekError(f"non-JSON response from DeepSeek: {exc}") from exc

    try:
        choice = body["choices"][0]["message"]
        content = choice.get("content", "") or ""
    except (KeyError, IndexError) as exc:
        raise DeepSeekError(f"unexpected DeepSeek response shape: {body}") from exc

    prompt, completion, cache_hit, cache_miss = _parse_usage(body.get("usage"))
    return ChatResult(
        content=content,
        prompt_tokens=prompt,
        completion_tokens=completion,
        cache_hit_tokens=cache_hit,
        cache_miss_tokens=cache_miss,
    )
