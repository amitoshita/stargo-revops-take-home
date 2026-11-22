"""Load the seed data pack (crm_export.csv, gtm_events.json)."""

from __future__ import annotations

import csv
import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from app.core.enums import Source
from app.ingest.schemas import (
    CrmContact,
    FeedStatus,
    InboundMessage,
    IngestError,
    PipelineEvent,
    SalesDecision,
)
from app.ingest.validate import (
    parse_crm_row,
    parse_decision,
    parse_inbound,
    parse_pipeline_event,
)


@dataclass
class SeedBundle:
    crm: list[CrmContact] = field(default_factory=list)
    inbound: list[InboundMessage] = field(default_factory=list)
    decisions: list[SalesDecision] = field(default_factory=list)
    events: list[PipelineEvent] = field(default_factory=list)
    feed_status: dict[Source, FeedStatus] = field(default_factory=dict)
    errors: list[IngestError] = field(default_factory=list)
    meta: dict[str, Any] = field(default_factory=dict)


def load_crm(path: Path, bundle: SeedBundle) -> None:
    with path.open(newline="", encoding="utf-8") as handle:
        for row in csv.DictReader(handle):
            parsed = parse_crm_row(row)
            if isinstance(parsed, IngestError):
                bundle.errors.append(parsed)
            else:
                bundle.crm.append(parsed)


def load_events(path: Path, bundle: SeedBundle) -> None:
    payload = json.loads(path.read_text(encoding="utf-8"))
    bundle.meta = dict(payload.get("meta", {}))
    for name, status in payload.get("feed_status", {}).items():
        try:
            source = Source(name)
        except ValueError:
            continue
        bundle.feed_status[source] = "received" if status == "received" else "not_received"
    for raw in payload.get("inbound", []):
        inbound = parse_inbound(raw, origin="seed")
        if isinstance(inbound, IngestError):
            bundle.errors.append(inbound)
        else:
            bundle.inbound.append(inbound)
    for raw in payload.get("sales_decisions", []):
        decision = parse_decision(raw, origin="seed")
        if isinstance(decision, IngestError):
            bundle.errors.append(decision)
        else:
            bundle.decisions.append(decision)
    for raw in payload.get("pipeline_events", []):
        event = parse_pipeline_event(raw)
        if isinstance(event, IngestError):
            bundle.errors.append(event)
        else:
            bundle.events.append(event)


def load_seed(data_dir: Path) -> SeedBundle:
    bundle = SeedBundle()
    load_crm(data_dir / "crm_export.csv", bundle)
    load_events(data_dir / "gtm_events.json", bundle)
    return bundle
