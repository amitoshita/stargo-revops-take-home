from __future__ import annotations

from pathlib import Path

from pydantic import BaseModel

from app.core.enums import Source
from app.ingest.schemas import InboundMessage, SalesDecision
from app.ingest.validate import parse_decision, parse_inbound
from app.storage.repository import Repository
from tests.helpers import seed


class _Doc(BaseModel):
    value: int


def test_seed_once_and_survive_restart(tmp_path: Path) -> None:
    db = tmp_path / "t.db"
    repo = Repository(db)
    assert repo.seed(seed()) is True
    assert repo.seed(seed()) is False  # idempotent

    restarted = Repository(db)
    assert len(restarted.list_crm()) == 19
    assert len(restarted.list_inbound()) == 20
    assert len(restarted.list_decisions()) == 11
    assert len(restarted.list_events()) == 12
    assert [e.record_ref for e in restarted.list_ingest_errors()] == ["IN-019"]
    assert restarted.feed_status()[Source.HISTORICAL_REACTIVATION] == "not_received"


def test_ui_records_persist_in_order(tmp_path: Path) -> None:
    db = tmp_path / "t.db"
    repo = Repository(db)
    repo.seed(seed())
    inbound_id = repo.next_ui_id("UI-IN-", "inbound")
    message = parse_inbound(
        {
            "id": inbound_id,
            "channel": "form_fill",
            "received_at": "2026-10-10T10:00:00+03:00",
            "from_email": "new@example.com",
            "body": "demo please",
        },
        origin="ui",
    )
    assert isinstance(message, InboundMessage)
    repo.add_inbound(message)
    decision = parse_decision(
        {
            "id": repo.next_ui_id("UI-SD-", "decisions"),
            "contact_email": "new@example.com",
            "decision": "accepted",
            "decided_by": "Leo",
            "decided_at": "2026-10-10T11:00:00+03:00",
        },
        origin="ui",
    )
    assert isinstance(decision, SalesDecision)
    repo.add_decision(decision)

    restarted = Repository(db)
    assert restarted.list_inbound()[-1].id == "UI-IN-001"
    assert restarted.list_decisions()[-1].id == "UI-SD-001"
    assert restarted.next_ui_id("UI-SD-", "decisions") == "UI-SD-002"


def test_documents_roundtrip(tmp_path: Path) -> None:
    repo = Repository(tmp_path / "t.db")
    repo.put_doc("x", "a", _Doc(value=1))
    repo.put_doc("x", "a", _Doc(value=2))
    assert repo.get_doc("x", "a", _Doc) == _Doc(value=2)
    assert repo.get_doc("x", "missing", _Doc) is None
    assert list(repo.list_docs("x", _Doc)) == ["a"]
    repo.delete_docs("x")
    assert repo.list_docs("x", _Doc) == {}
