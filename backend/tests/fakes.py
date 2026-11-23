"""A fake LLM for offline tests. Records every prompt it receives."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, field

from app.agents.llm_client import LLMError


@dataclass
class FakeLLM:
    reply: str | Callable[[str, str], str] = "{}"
    error: LLMError | None = None
    model: str = "fake-model"
    calls: list[tuple[str, str]] = field(default_factory=list)

    def complete(self, system: str, user: str, *, json_mode: bool, ref: str) -> str:
        self.calls.append((system, user))
        if self.error is not None:
            raise self.error
        return self.reply(system, user) if callable(self.reply) else self.reply
