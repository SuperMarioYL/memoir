"""Conversation session: turn storage and message assembly.

A session is the conversation history on top of the stable prefix. The prefix
goes into the system message (byte-identical across turns); turns are appended
as user/assistant messages. DeepSeek's prefix cache caches the stable system
prefix, so only new turns are billed at the full input rate.
"""

from __future__ import annotations

import json
import os
from dataclasses import dataclass, field, asdict
from pathlib import Path

from .config import Config

_SYSTEM_PROMPT_TMPL = (
    "You are Memoir, a personal AI that remembers the user's whole life. "
    "Answer using the full personal-history context below. When the answer "
    "depends on something the user wrote, ground it in that content.\n\n"
    "--- BEGIN PERSONAL HISTORY ---\n{prefix}\n--- END PERSONAL HISTORY ---"
)


@dataclass
class Turn:
    role: str  # "user" or "assistant"
    content: str


@dataclass
class Session:
    turns: list[Turn] = field(default_factory=list)

    def add(self, role: str, content: str) -> None:
        self.turns.append(Turn(role=role, content=content))

    def clear(self) -> None:
        self.turns.clear()


def load_session(config: Config) -> Session:
    p = config.paths.session_file
    if not p.exists():
        return Session()
    try:
        data = json.loads(p.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        # A corrupt session behaves like a missing one: start fresh rather
        # than crash the REPL.
        return Session()
    if not isinstance(data, dict):
        return Session()
    turns: list[Turn] = []
    for t in data.get("turns", []):
        if (
            isinstance(t, dict)
            and isinstance(t.get("role"), str)
            and isinstance(t.get("content"), str)
            and t["role"] in ("user", "assistant")
        ):
            turns.append(Turn(role=t["role"], content=t["content"]))
    return Session(turns=turns)


def save_session(config: Config, session: Session) -> None:
    config.paths.ensure()
    payload = {"turns": [asdict(t) for t in session.turns]}
    config.paths.session_file.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8"
    )


def reset_session(config: Config) -> None:
    """Delete the on-disk session so the next ``chat`` starts fresh."""
    p = config.paths.session_file
    if p.exists():
        p.unlink()


def system_message(prefix_text: str) -> dict:
    """Build the stable system message that carries the personal-history prefix."""
    return {"role": "system", "content": _SYSTEM_PROMPT_TMPL.format(prefix=prefix_text)}


def build_messages(prefix_text: str, session: Session, new_user: str | None) -> list[dict]:
    """Assemble the DeepSeek message list.

    The system message (with the full prefix) is always first and byte-identical
    across turns — that is the cache-stable anchor. Conversation turns follow.
    If ``new_user`` is given it is appended as the final user message.
    """
    messages: list[dict] = [system_message(prefix_text)]
    for t in session.turns:
        messages.append({"role": t.role, "content": t.content})
    if new_user is not None:
        messages.append({"role": "user", "content": new_user})
    return messages


def folded_block(turns: list[Turn]) -> str:
    """Render conversation turns as a deterministic block for the prefix.

    Used by ``memoir fold``. No timestamps: the same turns always render to the
    same bytes, so the folded prefix keeps the cache-stability property (the
    prefix changes once per fold, then is stable again).
    """
    parts = ["## Folded conversation"]
    for t in turns:
        label = "user" if t.role == "user" else "assistant"
        parts.append(f"### {label}\n{t.content}")
    return "\n\n".join(parts) + "\n"
