"""Parse the held-out message set (tests/heldout_messages.md). Read-only: never edited here."""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from datetime import date, datetime, timedelta
from pathlib import Path

from app.core.enums import Channel, Source
from app.core.timeutil import IL_TZ
from app.ingest.normalize import normalize_email
from app.ingest.schemas import InboundMessage

WEEK_SUNDAY = date(2026, 10, 4)
DAYS = {"sun": 0, "mon": 1, "tue": 2, "wed": 3, "thu": 4}


@dataclass
class HeldoutCase:
    case_id: str
    channel: str
    source: str | None
    email: str
    messages: list[tuple[str, str]] = field(default_factory=list)  # (day, text)
    expected: dict[str, str] = field(default_factory=dict)

    def inbound(self) -> list[InboundMessage]:
        out = []
        for index, (day, text) in enumerate(self.messages, start=1):
            moment = datetime.combine(
                WEEK_SUNDAY + timedelta(days=DAYS.get(day, 1)), datetime.min.time(), IL_TZ
            ).replace(hour=10)
            out.append(
                InboundMessage(
                    id=f"{self.case_id}-{index}",
                    origin="ui",
                    channel=Channel(self.channel),
                    source=Source(self.source) if self.source else None,
                    received_at=moment,
                    from_name=None,
                    email=normalize_email(self.email),
                    linkedin=None,
                    subject=None,
                    body=text,
                )
            )
        return out


_QUOTED = re.compile(r'"(.*)"\s*$')


def parse_heldout(path: Path) -> list[HeldoutCase]:
    cases: list[HeldoutCase] = []
    current: HeldoutCase | None = None
    for raw in path.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if line.startswith("## "):
            current = HeldoutCase(case_id=line[3:].strip(), channel="other", source=None, email="")
            cases.append(current)
            continue
        if current is None or not line.startswith("- "):
            continue
        key, _, rest = line[2:].partition(":")
        key = key.strip().lower()
        if key == "channel":
            parts = dict(p.split(":", 1) for p in f"channel:{rest}".split(" · "))
            current.channel = parts["channel"].strip()
            current.source = parts.get("source", "").strip() or None
            current.email = parts.get("email", "").strip()
        elif key == "text" or key.startswith("message"):
            match = _QUOTED.search(rest)
            day = re.search(r"\((\w{3})", key)
            if match:
                current.messages.append((day.group(1).lower() if day else "mon", match.group(1)))
        elif key == "expected":
            for item in rest.split(" · "):
                name, _, value = item.partition("=")
                current.expected[name.strip()] = value.strip()
    return cases
