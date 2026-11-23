"""KPI pack contract."""

from __future__ import annotations

from datetime import date, datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, computed_field

from app.core.enums import AnalysisMode, Source
from app.ingest.schemas import FeedStatus

MetricKey = Literal["qls", "meetings_booked", "meetings_held", "opportunities"]

TARGETS: dict[MetricKey, int] = {
    "qls": 25,
    "meetings_booked": 15,
    "meetings_held": 12,
    "opportunities": 5,
}


class _Frozen(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")


class RecordRef(_Frozen):
    record_id: str  # decision or event id
    person_id: str
    name: str | None
    detail: str  # e.g. "accepted by Dana at 2026-10-05 09:40 IL"


class KpiMetric(_Frozen):
    key: MetricKey
    label: str
    actual: int
    target: int
    records: list[RecordRef]

    @computed_field  # type: ignore[prop-decorator]
    @property
    def gap(self) -> int:
        return self.actual - self.target


class SourceRow(_Frozen):
    source: Source | Literal["source not recorded"]
    count: int | None  # None = unknown (feed not received, nothing to show)
    feed_status: FeedStatus | None
    records: list[RecordRef]
    note: str | None = None


class ExpansionLine(_Frozen):
    accepted: list[RecordRef] = Field(default_factory=list)
    meetings_booked: list[RecordRef] = Field(default_factory=list)
    meetings_held: list[RecordRef] = Field(default_factory=list)
    opportunities: list[RecordRef] = Field(default_factory=list)


class ExcludedRecord(_Frozen):
    record_id: str
    name: str | None
    reason: str


class KpiPack(_Frozen):
    week_start: date
    week_end: date
    timezone: str = "Asia/Jerusalem"
    generated_at: datetime
    analysis_modes: list[AnalysisMode]
    metrics: list[KpiMetric]
    by_source: list[SourceRow]
    expansion: ExpansionLine
    excluded: list[ExcludedRecord]
    caveats: list[str]

    def metric(self, key: MetricKey) -> KpiMetric:
        return next(m for m in self.metrics if m.key == key)
