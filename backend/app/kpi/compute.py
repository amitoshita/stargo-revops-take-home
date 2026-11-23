"""Weekly KPI pack (QLS §6). Pure function over stored records and assessments.

- QLs count in the week of the (latest) acceptance, once per person, only if the gate says QL.
- Meetings and opportunities count by their own date, any cohort (D2).
- Customers go to the expansion line; pre-existing open deals are left out of acquisition.
- Source = source of the person's earliest inbound; a feed not received is unknown, not 0.
"""

from __future__ import annotations

from collections.abc import Iterable, Mapping
from datetime import datetime, timedelta

from app.core.enums import Source, Status
from app.core.timeutil import il_midnight, to_il
from app.ingest.identity import Person
from app.ingest.schemas import FeedStatus, PipelineEvent, SalesDecision
from app.kpi.schemas import (
    TARGETS,
    ExcludedRecord,
    ExpansionLine,
    KpiMetric,
    KpiPack,
    MetricKey,
    RecordRef,
    SourceRow,
)
from app.kpi.window import ReportingWindow
from app.pipeline import World, as_of, assess_all, ran_modes
from app.rules.exclusions import is_pre_existing_deal

LABELS: dict[MetricKey, str] = {
    "qls": "QLs",
    "meetings_booked": "Meetings booked",
    "meetings_held": "Meetings held",
    "opportunities": "Opportunities created",
}
EVENT_METRIC: dict[str, MetricKey] = {
    "meeting_booked": "meetings_booked",
    "meeting_held": "meetings_held",
    "opportunity_created": "opportunities",
}
EVENT_EXPANSION_FIELD = {
    "meeting_booked": "meetings_booked",
    "meeting_held": "meetings_held",
    "opportunity_created": "opportunities",
}


def _il(moment: datetime) -> str:
    return to_il(moment).strftime("%Y-%m-%d %H:%M")


def person_name(person: Person) -> str | None:
    if person.crm and person.crm.full_name:
        return person.crm.full_name
    for message in person.inbound:
        if message.from_name:
            return message.from_name
    return None


def _decision_ref(decision: SalesDecision, person: Person) -> RecordRef:
    return RecordRef(
        record_id=decision.id,
        person_id=person.person_id,
        name=person_name(person),
        detail=f"{decision.decision} by {decision.decided_by} at {_il(decision.decided_at)} IL",
    )


def _event_ref(event: PipelineEvent, person: Person | None) -> RecordRef:
    return RecordRef(
        record_id=event.id,
        person_id=person.person_id if person else "unknown",
        name=person_name(person) if person else None,
        detail=f"{event.type.replace('_', ' ')} at {_il(event.occurred_at)} IL",
    )


def _first_acceptance(decisions: list[SalesDecision]) -> datetime | None:
    accepted = [d.decided_at for d in decisions if d.decision == "accepted"]
    return min(accepted) if accepted else None


def compute_pack(
    full: World,
    events: Iterable[PipelineEvent],
    feed_status: Mapping[Source, FeedStatus],
    window: ReportingWindow,
    generated_at: datetime,
) -> KpiPack:
    """The pack for one week, as it stood then. Built from messages received before the next
    reporting week starts (so Fri/Sat queued inbound counts) and decisions dated before the
    week ends. Later activity cannot change it. Records outside the week are listed only if
    dated before the next week began (e.g. a Friday decision or a Friday meeting)."""
    next_start = il_midnight(window.sunday + timedelta(days=7))
    world = as_of(full, next_start, window.end_exclusive)
    assessments = assess_all(world)

    def listable(moment: datetime) -> bool:
        """One principle: the pack shows only what was known before the next week began."""
        return moment < next_start

    records: dict[MetricKey, list[RecordRef]] = {key: [] for key in TARGETS}
    expansion: dict[str, list[RecordRef]] = {
        "accepted": [],
        "meetings_booked": [],
        "meetings_held": [],
        "opportunities": [],
    }
    excluded: list[ExcludedRecord] = []
    qls: list[tuple[datetime, Person, RecordRef]] = []

    # ---- QLs and expansion acceptances (by decided_at) -------------------
    for pid, decisions in sorted(world.decisions_by_person.items()):
        person = world.identity.persons[pid]
        name = person_name(person)
        latest = decisions[-1]
        assessment = assessments.get(pid)
        superseded = decisions[:-1]
        for old in superseded:
            excluded.append(
                ExcludedRecord(
                    record_id=old.id,
                    name=name,
                    reason=f"superseded by later decision {latest.id} (latest decision wins)",
                )
            )
        if not window.contains(latest.decided_at):
            excluded.append(
                ExcludedRecord(
                    record_id=latest.id,
                    name=name,
                    reason=f"decided {_il(latest.decided_at)} IL, outside the week",
                )
            )
            continue
        if latest.decision == "rejected":
            excluded.append(ExcludedRecord(record_id=latest.id, name=name, reason="rejected"))
            continue
        if person.crm and person.crm.is_customer:
            if assessment and assessment.status in (Status.SUPPRESSED, Status.NEEDS_REVIEW):
                excluded.append(
                    ExcludedRecord(
                        record_id=latest.id,
                        name=name,
                        reason=f"customer, but status is {assessment.status.value}",
                    )
                )
                continue
            expansion["accepted"].append(_decision_ref(latest, person))
            continue
        if assessment is None:
            excluded.append(
                ExcludedRecord(
                    record_id=latest.id,
                    name=name,
                    reason="accepted, but no inbound to assess",
                )
            )
            continue
        if assessment.status != Status.QL:
            excluded.append(
                ExcludedRecord(
                    record_id=latest.id,
                    name=name,
                    reason=f"accepted, but status is {assessment.status.value}: "
                    f"{assessment.rationale}",
                )
            )
            continue
        qls.append((latest.decided_at, person, _decision_ref(latest, person)))

    for late in sorted(full.decisions, key=lambda d: (d.decided_at, d.id)):
        if late.decided_at < window.end_exclusive:
            continue  # already in the as-of view
        who = world.identity.person_for_contact(*late.identity_keys)
        if who is None or not listable(late.decided_at):
            continue
        excluded.append(
            ExcludedRecord(
                record_id=late.id,
                name=person_name(who),
                reason=f"decided {_il(late.decided_at)} IL, outside the week",
            )
        )

    qls.sort(key=lambda item: (item[0], item[2].record_id))
    records["qls"] = [ref for _, _, ref in qls]

    # ---- pipeline events (by their own date) -------------------------------
    for event in sorted(events, key=lambda e: (e.occurred_at, e.id)):
        who = world.identity.person_for_email(event.contact_email)
        name = person_name(who) if who else None
        if not window.contains(event.occurred_at):
            if not listable(event.occurred_at):
                continue
            excluded.append(
                ExcludedRecord(
                    record_id=event.id,
                    name=name,
                    reason=f"{event.type.replace('_', ' ')} at {_il(event.occurred_at)} IL, "
                    "outside the week",
                )
            )
            continue
        crm = who.crm if who else None
        if crm and crm.is_customer:
            expansion[EVENT_EXPANSION_FIELD[event.type]].append(_event_ref(event, who))
            continue
        decisions = world.decisions_by_person.get(who.person_id, []) if who else []
        first_inbound = to_il(who.inbound[0].received_at).date() if who and who.inbound else None
        if is_pre_existing_deal(crm, first_inbound, _first_acceptance(decisions)):
            excluded.append(
                ExcludedRecord(
                    record_id=event.id,
                    name=name,
                    reason="pre-existing open deal (not acquisition)",
                )
            )
            continue
        records[EVENT_METRIC[event.type]].append(_event_ref(event, who))

    # ---- QLs by first-touch source ----------------------------------------
    by_source: dict[Source | None, list[RecordRef]] = {}
    for _, person, ref in qls:
        earliest = person.inbound[0]
        by_source.setdefault(earliest.source, []).append(
            ref.model_copy(update={"detail": f"earliest inbound {earliest.id}"})
        )
    rows: list[SourceRow] = []
    for source in Source:
        refs = by_source.get(source, [])
        status = feed_status.get(source)
        if status != "received":  # not received, or not reported at all: unknown, never 0
            rows.append(
                SourceRow(
                    source=source,
                    count=len(refs) or None,
                    feed_status=status,
                    records=refs,
                    note=f"feed {'not received' if status else 'status not reported'}: "
                    + ("unknown" if not refs else f"at least {len(refs)}"),
                )
            )
        else:
            rows.append(SourceRow(source=source, count=len(refs), feed_status=status, records=refs))
    rows.append(
        SourceRow(
            source="source not recorded",
            count=len(by_source.get(None, [])),
            feed_status=None,
            records=by_source.get(None, []),
        )
    )

    # ---- leads not counted, for honesty -------------------------------------
    for pid, assessment in sorted(assessments.items()):
        ctx = world.leads[pid]
        name = person_name(world.identity.persons[pid])
        if assessment.status == Status.QL_CANDIDATE and not ctx.decisions:
            excluded.append(
                ExcludedRecord(
                    record_id=ctx.inbound[-1].id,
                    name=name,
                    reason="QL candidate awaiting sales acceptance (queued)",
                )
            )
        elif assessment.status == Status.NEEDS_REVIEW:
            excluded.append(
                ExcludedRecord(
                    record_id=ctx.inbound[-1].id,
                    name=name,
                    reason="needs review: a human must decide before it can count",
                )
            )
    for person in world.identity.persons.values():
        crm = person.crm
        if crm and crm.lead_status and "ql" in crm.lead_status.lower() and not person.inbound:
            excluded.append(
                ExcludedRecord(
                    record_id=crm.record_id,
                    name=person_name(person),
                    reason=f"CRM status '{crm.lead_status}' is not evidence "
                    "(no inbound, no acceptance)",
                )
            )

    caveats = [
        f"Feed '{s.value}' was not received: its numbers are unknown, and totals may be "
        "understated."
        for s, st in sorted(feed_status.items())
        if st == "not_received"
    ] + [
        f"Feed '{s.value}' status was not reported: its numbers are unknown."
        for s in Source
        if s not in feed_status
    ]
    needs_review = sum(1 for a in assessments.values() if a.status == Status.NEEDS_REVIEW)
    if needs_review:
        caveats.append(f"{needs_review} lead(s) in needs review are not counted until decided.")
    flagged = [
        f"{pid} ({', '.join(f.inbound_id for f in a.review_flags)})"
        for pid, a in sorted(assessments.items())
        if a.review_flags and a.status != Status.NEEDS_REVIEW
    ]
    if flagged:
        caveats.append(
            "Messages awaiting review (they change nothing until a human decides): "
            + "; ".join(flagged)
        )

    return KpiPack(
        week_start=window.sunday,
        week_end=window.last_day,
        generated_at=generated_at,
        analysis_modes=ran_modes(a for ctx in world.leads.values() for a in ctx.analyses),
        metrics=[
            KpiMetric(
                key=k,
                label=LABELS[k],
                actual=len(records[k]),
                target=TARGETS[k],
                records=records[k],
            )
            for k in TARGETS
        ],
        by_source=rows,
        expansion=ExpansionLine.model_validate(expansion),
        excluded=excluded,
        caveats=caveats,
    )
