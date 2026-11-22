from __future__ import annotations

import logging
import socket
from datetime import date

import pytest

from app.core.logging_setup import RedactingFilter, redact, short_hash
from app.core.timeutil import parse_aware, to_il, week_containing


@pytest.mark.parametrize(
    ("raw", "expected_il"),
    [
        ("2026-10-05T11:20:00Z", "2026-10-05T14:20:00+03:00"),
        ("2026-10-08T21:30:00Z", "2026-10-09T00:30:00+03:00"),
        ("2026-10-04T09:12:00+03:00", "2026-10-04T09:12:00+03:00"),
        # After DST ends (25 Oct 2026) Israel is UTC+2: offsets must come from zoneinfo.
        ("2026-10-26T10:00:00Z", "2026-10-26T12:00:00+02:00"),
    ],
)
def test_to_il_uses_zoneinfo(raw: str, expected_il: str) -> None:
    assert to_il(parse_aware(raw)).isoformat() == expected_il


def test_naive_timestamp_rejected() -> None:
    with pytest.raises(ValueError):
        parse_aware("2026-10-05T11:20:00")


@pytest.mark.parametrize(
    ("raw", "sunday"),
    [
        ("2026-10-04T00:00:00+03:00", date(2026, 10, 4)),
        ("2026-10-08T20:30:00Z", date(2026, 10, 4)),
        ("2026-10-08T21:30:00Z", date(2026, 10, 4)),  # Friday 00:30 IL still in the Sun-Sat span
        ("2026-10-11T09:00:00+03:00", date(2026, 10, 11)),
    ],
)
def test_week_containing(raw: str, sunday: date) -> None:
    assert week_containing(parse_aware(raw)) == sunday


def test_redact_removes_emails_and_linkedin() -> None:
    text = "from Anouk.DeVries@NordhavenFreight.com via https://www.linkedin.com/in/x-y/"
    assert redact(text) == "from [email] via [linkedin]"


def test_log_filter_redacts_args(caplog: pytest.LogCaptureFixture) -> None:
    logger = logging.getLogger("t")
    logger.addFilter(RedactingFilter())
    with caplog.at_level(logging.INFO):
        logger.info("contact %s", "p.claes@balticacargo.eu")
    assert "balticacargo" not in caplog.text


def test_short_hash_stable() -> None:
    assert short_hash("x") == short_hash("x") and len(short_hash("x")) == 12


def test_network_is_blocked() -> None:
    with pytest.raises(RuntimeError):
        socket.create_connection(("example.com", 80))
