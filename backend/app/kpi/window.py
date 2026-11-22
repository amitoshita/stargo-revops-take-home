"""Reporting week (QLS §6): Sunday 00:00 to Thursday 23:59 Asia/Jerusalem.

Implemented as the half-open interval [Sun 00:00, Fri 00:00) in IL time (D7).
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, timedelta

from app.core.timeutil import il_midnight, to_il


@dataclass(frozen=True)
class ReportingWindow:
    sunday: date

    def __post_init__(self) -> None:
        if self.sunday.weekday() != 6:
            raise ValueError("a reporting week starts on a Sunday")

    @property
    def start(self) -> datetime:
        return il_midnight(self.sunday)

    @property
    def end_exclusive(self) -> datetime:
        return il_midnight(self.sunday + timedelta(days=5))

    @property
    def last_day(self) -> date:
        return self.sunday + timedelta(days=4)

    def contains(self, moment: datetime) -> bool:
        return self.start <= to_il(moment) < self.end_exclusive

    def label(self) -> str:
        return f"Sun {self.sunday:%-d %b} – Thu {self.last_day:%-d %b %Y} (Asia/Jerusalem)"


WEEK_UNDER_REVIEW = ReportingWindow(date(2026, 10, 4))
