from __future__ import annotations

from app.core.enums import Source
from app.ingest.identity import IdentityIndex, build_company_index, build_identity
from app.ingest.loader import SeedBundle
from tests.helpers import seed


def _index() -> tuple[SeedBundle, IdentityIndex]:
    bundle = seed()
    extra = [d.contact_email for d in bundle.decisions] + [e.contact_email for e in bundle.events]
    return bundle, build_identity(bundle.crm, bundle.inbound, extra)


def test_loader_counts_and_rejects_in019() -> None:
    bundle = seed()
    assert len(bundle.crm) == 19
    assert len(bundle.inbound) == 20  # IN-019 rejected
    assert len(bundle.decisions) == 11
    assert len(bundle.events) == 12
    assert [e.record_ref for e in bundle.errors] == ["IN-019"]
    assert set(bundle.errors[0].reasons) == {"invalid email address", "message text is empty"}
    assert bundle.feed_status[Source.HISTORICAL_REACTIVATION] == "not_received"


def test_loader_is_deterministic() -> None:
    assert seed().inbound == seed().inbound


def test_same_person_across_channels() -> None:
    _, index = _index()
    pieter = index.persons["HS-1004"]
    assert [m.id for m in pieter.inbound] == ["IN-002", "IN-003"]  # email + LinkedIn
    anouk = index.persons["HS-1001"]
    assert [m.id for m in anouk.inbound] == ["IN-001", "IN-021"]  # case-different email


def test_linkedin_bridges_to_crm_email() -> None:
    _, index = _index()
    tom = index.persons["HS-1013"]
    assert [m.id for m in tom.inbound] == ["IN-009"]
    assert index.person_for_email("tom.becker@kestrelsc.com") is tom


def test_role_mailbox_not_merged_with_colleague() -> None:
    bundle, index = _index()
    ops = next(m for m in bundle.inbound if m.id == "IN-010")
    person = index.person_for_inbound(ops)
    assert person.crm is None
    assert person.person_id != "HS-1015"


def test_same_company_different_people() -> None:
    bundle, index = _index()
    sanne = index.person_for_inbound(next(m for m in bundle.inbound if m.id == "IN-013"))
    assert sanne.person_id == "HS-1002"
    assert sanne is not index.persons["HS-1001"]


def test_free_email_sender_without_crm() -> None:
    bundle, index = _index()
    yossi = index.person_for_inbound(next(m for m in bundle.inbound if m.id == "IN-011"))
    assert yossi.crm is None and yossi.person_id.startswith("P-")


def test_duplicate_decision_emails_resolve_to_one_person() -> None:
    _, index = _index()
    assert index.person_for_email("rachel.lim@lionport.com.sg") is index.persons["HS-1009"]


def test_every_person_has_at_most_one_crm_row() -> None:
    _, index = _index()
    assert not any(p.crm_conflict for p in index.persons.values())


def test_company_index_by_normalized_domain() -> None:
    companies = build_company_index(seed().crm)
    nordhaven = companies["nordhavenfreight.com"]
    assert nordhaven.employees == 850
    assert set(nordhaven.source_record_ids) == {"HS-1001", "HS-1002", "HS-1003"}
    assert companies["halden-fwd.de"].country == "DE"


def test_crm_normalization() -> None:
    crm = {c.record_id: c for c in seed().crm}
    assert crm["HS-1002"].company_domain == "nordhavenfreight.com"
    assert crm["HS-1002"].country == "NL"
    assert crm["HS-1002"].vertical == "freight-forwarder"
    assert crm["HS-1002"].employees is None  # unknown stays unknown on the row
    assert crm["HS-1008"].country == "GB"
    assert crm["HS-1011"].is_customer is True
    assert crm["HS-1013"].linkedin == "linkedin.com/in/tombecker-logistics"
