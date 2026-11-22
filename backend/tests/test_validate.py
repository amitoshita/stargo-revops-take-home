from __future__ import annotations

from typing import Any

import pytest

from app.core.enums import Channel, Source
from app.ingest.schemas import InboundMessage, IngestError
from app.ingest.validate import parse_decision, parse_inbound


def _raw(**overrides: Any) -> dict[str, Any]:
    base: dict[str, Any] = {
        "id": "UI-1",
        "channel": "form_fill",
        "source": "paid",
        "received_at": "2026-10-05T10:00:00+03:00",
        "from_name": "Test Person",
        "from_email": "Test@Example.com",
        "linkedin_url": None,
        "subject": "Hi",
        "body": "Please send a demo.",
    }
    base.update(overrides)
    return base


def test_valid_inbound_is_normalized() -> None:
    parsed = parse_inbound(_raw(), origin="ui")
    assert isinstance(parsed, InboundMessage)
    assert parsed.email == "test@example.com"
    assert parsed.channel is Channel.FORM_FILL
    assert parsed.source is Source.PAID


def test_blank_source_means_not_recorded() -> None:
    parsed = parse_inbound(_raw(source=""), origin="ui")
    assert isinstance(parsed, InboundMessage) and parsed.source is None


def test_linkedin_only_is_valid() -> None:
    parsed = parse_inbound(
        _raw(from_email="", linkedin_url="https://www.linkedin.com/in/x-y/"), origin="ui"
    )
    assert isinstance(parsed, InboundMessage) and parsed.linkedin == "linkedin.com/in/x-y"


@pytest.mark.parametrize(
    ("overrides", "reason"),
    [
        ({"from_email": "asdf@asdf", "body": ""}, "invalid email address"),
        ({"from_email": "asdf@asdf", "body": ""}, "message text is empty"),
        ({"from_email": "", "linkedin_url": ""}, "an email address or a LinkedIn URL is required"),
        ({"linkedin_url": "https://example.com/in/x"}, "invalid LinkedIn profile URL"),
        ({"received_at": "2026-10-05T10:00:00"}, "time zone offset"),
        ({"source": "billboard"}, "unknown source"),
        ({"channel": "fax"}, "unknown channel"),
        ({"body": "x" * 5001}, "longer than 5000"),
    ],
)
def test_invalid_inbound_reports_reason(overrides: dict[str, Any], reason: str) -> None:
    parsed = parse_inbound(_raw(**overrides), origin="ui")
    assert isinstance(parsed, IngestError)
    assert any(reason in r for r in parsed.reasons)


def test_errors_never_contain_message_content() -> None:
    parsed = parse_inbound(_raw(from_email="bad", body="SECRET BODY"), origin="ui")
    assert isinstance(parsed, IngestError)
    assert "SECRET" not in parsed.model_dump_json()
    assert "bad" not in " ".join(parsed.reasons)


def test_missing_id_gets_anonymous_ref() -> None:
    raw = _raw(from_email="bad")
    raw.pop("id")
    parsed = parse_inbound(raw, origin="ui")
    assert isinstance(parsed, IngestError) and parsed.record_ref.startswith("anon-")


def test_decision_email_normalized() -> None:
    parsed = parse_decision(
        {
            "id": "SD-004",
            "contact_email": "Rachel.Lim@lionport.com.sg",
            "decision": "accepted",
            "decided_by": "Mei",
            "decided_at": "2026-10-06T08:16:00+03:00",
            "note": "",
        },
        origin="seed",
    )
    assert not isinstance(parsed, IngestError)
    assert parsed.contact_email == "rachel.lim@lionport.com.sg"
    assert parsed.note is None
