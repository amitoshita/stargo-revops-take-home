"""Identity resolution (QLS §3): one person per normalized email or LinkedIn URL.

People are linked only through shared identity keys: an inbound with an email, a CRM row
holding both an email and a LinkedIn URL, and so on. Never by name, city or company.
"""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass, field

from app.core.logging_setup import short_hash
from app.ingest.schemas import CompanyRecord, CrmContact, InboundMessage


def email_key(email: str) -> str:
    return f"e:{email}"


def linkedin_key(linkedin: str) -> str:
    return f"l:{linkedin}"


@dataclass
class Person:
    person_id: str
    crm: CrmContact | None
    emails: set[str] = field(default_factory=set)
    linkedins: set[str] = field(default_factory=set)
    inbound: list[InboundMessage] = field(default_factory=list)  # oldest first
    crm_conflict: bool = False  # keys from two CRM rows met in one person


class _UnionFind:
    def __init__(self) -> None:
        self.parent: dict[str, str] = {}

    def add(self, key: str) -> None:
        self.parent.setdefault(key, key)

    def find(self, key: str) -> str:
        root = key
        while self.parent[root] != root:
            root = self.parent[root]
        while self.parent[key] != root:
            self.parent[key], key = root, self.parent[key]
        return root

    def union(self, a: str, b: str) -> None:
        ra, rb = self.find(a), self.find(b)
        if ra != rb:
            self.parent[max(ra, rb)] = min(ra, rb)


def _keys(email: str | None, linkedin: str | None) -> list[str]:
    keys = []
    if email:
        keys.append(email_key(email))
    if linkedin:
        keys.append(linkedin_key(linkedin))
    return keys


@dataclass
class IdentityIndex:
    persons: dict[str, Person]
    _person_by_key: dict[str, str]

    def person_for_email(self, email: str) -> Person | None:
        pid = self._person_by_key.get(email_key(email))
        return self.persons[pid] if pid else None

    def person_for_inbound(self, inbound: InboundMessage) -> Person:
        for key in _keys(inbound.email, inbound.linkedin):
            if key in self._person_by_key:
                return self.persons[self._person_by_key[key]]
        raise KeyError(inbound.id)


def build_identity(
    crm: Iterable[CrmContact],
    inbound: Iterable[InboundMessage],
    extra_emails: Iterable[str] = (),
) -> IdentityIndex:
    crm_list = sorted(crm, key=lambda c: c.record_id)
    inbound_list = sorted(inbound, key=lambda m: (m.received_at, m.id))
    uf = _UnionFind()

    for group in (
        *(_keys(c.email, c.linkedin) for c in crm_list),
        *(_keys(m.email, m.linkedin) for m in inbound_list),
        *([email_key(e)] for e in extra_emails),
    ):
        for key in group:
            uf.add(key)
        for key in group[1:]:
            uf.union(group[0], key)

    crm_by_root: dict[str, list[CrmContact]] = {}
    for contact in crm_list:
        keys = _keys(contact.email, contact.linkedin)
        if keys:
            crm_by_root.setdefault(uf.find(keys[0]), []).append(contact)

    # A person outside the CRM is named after the key of their earliest inbound message, so
    # the id does not change when a later message adds an email or LinkedIn URL.
    first_key: dict[str, str] = {}
    for message in inbound_list:
        keys = _keys(message.email, message.linkedin)
        first_key.setdefault(uf.find(keys[0]), keys[0])

    persons: dict[str, Person] = {}
    person_by_root: dict[str, str] = {}
    for key in sorted(uf.parent):
        root = uf.find(key)
        if root not in person_by_root:
            contacts = crm_by_root.get(root, [])
            pid = (
                contacts[0].record_id if contacts else f"P-{short_hash(first_key.get(root, root))}"
            )
            person_by_root[root] = pid
            persons[pid] = Person(
                person_id=pid,
                crm=contacts[0] if contacts else None,
                crm_conflict=len(contacts) > 1,
            )
        person = persons[person_by_root[root]]
        kind, _, value = key.partition(":")
        (person.emails if kind == "e" else person.linkedins).add(value)

    person_by_key = {key: person_by_root[uf.find(key)] for key in uf.parent}
    for message in inbound_list:
        persons[person_by_key[_keys(message.email, message.linkedin)[0]]].inbound.append(message)
    return IdentityIndex(persons=persons, _person_by_key=person_by_key)


def build_company_index(crm: Iterable[CrmContact]) -> dict[str, CompanyRecord]:
    """Company facts per normalized domain: first non-empty value in record-id order."""
    grouped: dict[str, list[CrmContact]] = {}
    for contact in sorted(crm, key=lambda c: c.record_id):
        if contact.company_domain:
            grouped.setdefault(contact.company_domain, []).append(contact)
    index: dict[str, CompanyRecord] = {}
    for domain, rows in grouped.items():
        index[domain] = CompanyRecord(
            domain=domain,
            name=next((r.company_name for r in rows if r.company_name), None),
            country=next((r.country for r in rows if r.country), None),
            region=next((r.region for r in rows if r.region), None),
            vertical=next((r.vertical for r in rows if r.vertical), None),
            employees=next((r.employees for r in rows if r.employees is not None), None),
            source_record_ids=[r.record_id for r in rows],
        )
    return index
