"""Test-wide fixtures. Every test runs fully offline: outbound sockets are blocked."""

from __future__ import annotations

import socket
from collections.abc import Iterator
from typing import Any

import pytest


class NetworkBlockedError(RuntimeError):
    pass


@pytest.fixture(autouse=True)
def _block_network(monkeypatch: pytest.MonkeyPatch) -> Iterator[None]:
    def guard(*_args: Any, **_kwargs: Any) -> None:
        raise NetworkBlockedError("network access is disabled in tests")

    monkeypatch.setattr(socket.socket, "connect", guard)
    monkeypatch.setattr(socket, "create_connection", guard)
    monkeypatch.delenv("GROQ_API_KEY", raising=False)
    yield
