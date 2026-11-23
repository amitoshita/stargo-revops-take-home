"""The held-out file parses (offline). The set itself is never used to tune the prompt."""

from __future__ import annotations

from app.agents.heldout import parse_heldout
from app.core.config import REPO_ROOT

HELDOUT = REPO_ROOT / "backend" / "tests" / "heldout_messages.md"


def test_heldout_parses_into_cases_with_expectations() -> None:
    cases = parse_heldout(HELDOUT)
    assert [c.case_id for c in cases] == ["H1", "H2", "H3", "H4", "H5", "H6"]
    assert all(c.messages and c.expected and c.email for c in cases)
    h6 = cases[-1]
    assert [day for day, _ in h6.messages] == ["mon", "wed"]
    inbound = h6.inbound()
    assert inbound[0].received_at < inbound[1].received_at
    assert all(m.origin == "ui" for m in inbound)
