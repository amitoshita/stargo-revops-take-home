"""Application service: the one place that wires storage, agents, rules and KPI together.

Seed data and pasted messages take the same path: validate → store → analyse (Agent A) →
rules over all stored records. The rules view is rebuilt from stored records on every read,
so a stored decision always shows up and nothing depends on in-memory state.
The LLM is called only for Agent A on a new message and for a draft a human asks for.
"""

from __future__ import annotations

import logging
from collections.abc import Iterable
from dataclasses import dataclass
from datetime import date
from pathlib import Path
from typing import Any, Literal

from app.agents.agent_b import build_agent_b, wants_draft
from app.agents.analyzer import analyze_message
from app.agents.fixtures import FixtureStore, RecordedReply, message_hash
from app.agents.llm_client import GroqClient, LLMClient
from app.agents.schemas import AgentAOutput, AgentBOutput, MessageAnalysis
from app.core.config import Settings
from app.core.enums import AnalysisMode, Status
from app.core.timeutil import now_il, parse_aware
from app.geo.brief import (
    BRIEF_PROMPT_VERSION,
    assemble,
    build_user,
    generate_brief,
    parse_brief,
    template_brief,
)
from app.geo.claims import load_claims
from app.geo.report import build_report, competitors
from app.geo.report import render_markdown as render_geo
from app.geo.schemas import ContentBrief, ContentBriefDraft, GeoReport
from app.ingest.identity import Person
from app.ingest.loader import load_seed
from app.ingest.schemas import InboundMessage, IngestError, SalesDecision
from app.ingest.validate import parse_decision, parse_inbound
from app.kpi.compute import compute_pack, person_name
from app.kpi.export import export, render
from app.kpi.schemas import KpiPack
from app.kpi.window import ReportingWindow
from app.pipeline import World, assess_all, build_world
from app.rules.schemas import Assessment
from app.storage.repository import Repository

log = logging.getLogger(__name__)

ANALYSIS = "analysis"
DRAFT = "agent_b"
KPI = "kpi_pack"
GEO = "geo_report"
BRIEF = "geo_brief"
MODE_LABEL = {True: "llm", False: "rules-only fallback mode"}


class ServiceError(Exception):
    """A request the service refuses, with reasons safe to show (no message content)."""

    def __init__(self, status: int, reasons: list[str]) -> None:
        super().__init__("; ".join(reasons))
        self.status = status
        self.reasons = reasons


@dataclass(frozen=True)
class Snapshot:
    """Everything derived from stored records at one moment."""

    world: World
    analyses: dict[str, MessageAnalysis]
    assessments: dict[str, Assessment]


class Service:
    def __init__(
        self,
        settings: Settings,
        repo: Repository | None = None,
        client: LLMClient | None = None,
        fixtures: FixtureStore | None = None,
        *,
        use_llm: bool | None = None,
    ) -> None:
        self.settings = settings
        self.repo = repo or Repository(settings.db_path)
        enabled = settings.llm_enabled if use_llm is None else use_llm
        self.client: LLMClient | None = client
        if self.client is None and enabled and settings.llm_api_key:
            self.client = GroqClient.from_settings(settings)
        self.fixtures = fixtures or FixtureStore(settings.fixtures_dir / "agent_a")

    # ---- mode ---------------------------------------------------------------
    @property
    def llm_enabled(self) -> bool:
        return self.client is not None

    def mode(self) -> dict[str, Any]:
        return {
            "llm_enabled": self.llm_enabled,
            "label": MODE_LABEL[self.llm_enabled],
            "model": self.client.model if self.client else None,
            "seed_analysis": AnalysisMode.RECORDED_FIXTURE.value,
            "pasted_analysis": (
                AnalysisMode.LLM if self.llm_enabled else AnalysisMode.RULES_ONLY
            ).value,
        }

    # ---- bootstrap ----------------------------------------------------------
    def bootstrap(self) -> None:
        """Seed on first run, then analyse any stored message without an analysis."""
        if not self.repo.is_seeded():
            self.repo.seed(load_seed(self.settings.data_dir))
            log.info("seeded database")
        stored = self.repo.list_docs(ANALYSIS, MessageAnalysis)
        for message in self.repo.list_inbound():
            if message.id not in stored:
                self._analyse(message)

    def _analyse(self, message: InboundMessage) -> MessageAnalysis:
        analysis = analyze_message(message, client=self.client, fixtures=self.fixtures)
        self.repo.put_doc(ANALYSIS, message.id, analysis)
        return analysis

    # ---- snapshot -------------------------------------------------------------
    def snapshot(self) -> Snapshot:
        analyses = self.repo.list_docs(ANALYSIS, MessageAnalysis)
        world = build_world(
            self.repo.list_crm(),
            self.repo.list_inbound(),
            self.repo.list_decisions(),
            analyses,
            [e.contact_email for e in self.repo.list_events()],
        )
        return Snapshot(world, analyses, assess_all(world))

    def require_lead(self, snap: Snapshot, person_id: str) -> Person:
        if person_id not in snap.world.leads:
            raise ServiceError(404, [f"no lead with id {person_id}"])
        return snap.world.identity.persons[person_id]

    # ---- paste a new inbound message --------------------------------------------
    def paste(self, form: dict[str, Any]) -> tuple[InboundMessage, str]:
        raw = {
            "id": self.repo.next_ui_id("UI-IN-", "inbound"),
            "channel": form.get("channel") or "other",
            "source": form.get("source") or None,
            "received_at": form.get("received_at") or now_il().isoformat(),
            "from_name": form.get("from_name"),
            "from_email": form.get("from_email"),
            "linkedin_url": form.get("linkedin_url"),
            "subject": form.get("subject"),
            "body": form.get("body"),
        }
        parsed = parse_inbound(raw, "ui")
        if isinstance(parsed, IngestError):
            self.repo.add_ingest_error(parsed)
            log.info("paste rejected ref=%s reasons=%d", parsed.record_ref, len(parsed.reasons))
            raise ServiceError(422, parsed.reasons)
        self.repo.add_inbound(parsed)
        self._analyse(parsed)
        snap = self.snapshot()
        return parsed, snap.world.identity.person_for_inbound(parsed).person_id

    # ---- sales decision --------------------------------------------------------
    def decide(
        self,
        person_id: str,
        decision: Literal["accepted", "rejected"],
        decided_by: str,
        decided_at: str | None,
        note: str | None,
    ) -> SalesDecision:
        snap = self.snapshot()
        person = self.require_lead(snap, person_id)
        email = (person.crm.email if person.crm else None) or min(person.emails, default=None)
        if email is None:
            raise ServiceError(422, ["this person has no email address; a decision needs one"])
        if decided_at:
            try:
                parse_aware(decided_at)
            except ValueError:
                raise ServiceError(
                    422, ["decided_at must be an ISO time with a UTC offset"]
                ) from None
        parsed = parse_decision(
            {
                "id": self.repo.next_ui_id("UI-SD-", "decisions"),
                "contact_email": email,
                "decision": decision,
                "decided_by": decided_by,
                "decided_at": decided_at or now_il().isoformat(),
                "note": note,
            },
            "ui",
        )
        if isinstance(parsed, IngestError):
            raise ServiceError(422, parsed.reasons)
        self.repo.add_decision(parsed)
        self.repo.delete_docs(KPI)  # stored packs are recomputed on next read
        log.info("decision stored ref=%s person=%s", parsed.id, person_id)
        return parsed

    # ---- reply draft (explicit human action) -----------------------------------
    def draft(self, person_id: str) -> AgentBOutput:
        snap = self.snapshot()
        person = self.require_lead(snap, person_id)
        assessment = snap.assessments[person_id]
        latest = self.latest_extraction(snap, person_id)
        if not wants_draft(assessment, latest):
            raise ServiceError(409, [f"no draft for status '{assessment.status.value}'"])
        first = (person.crm.first_name if person.crm else None) or _first_name(person)
        output = build_agent_b(person_id, assessment, latest, first_name=first, client=self.client)
        self.repo.put_doc(DRAFT, person_id, output)
        return output

    def stored_draft(self, snap: Snapshot, person_id: str) -> AgentBOutput | None:
        stored = self.repo.get_doc(DRAFT, person_id, AgentBOutput)
        if stored is None:
            return None
        current = snap.assessments.get(person_id)
        if current is None or not wants_draft(current, self.latest_extraction(snap, person_id)):
            return None  # status changed since the draft (e.g. now suppressed): never show it
        return stored

    @staticmethod
    def latest_extraction(snap: Snapshot, person_id: str) -> AgentAOutput | None:
        ctx = snap.world.leads[person_id]
        for analysis in reversed(ctx.analyses):
            if analysis.extraction is not None:
                return analysis.extraction
        return None

    # ---- KPI --------------------------------------------------------------------
    def kpi(self, week: date) -> KpiPack:
        if week.weekday() != 6:
            raise ServiceError(422, ["week must start on a Sunday (Asia/Jerusalem)"])
        snap = self.snapshot()
        pack = compute_pack(
            snap.world,
            snap.assessments,
            self.repo.list_events(),
            self.repo.feed_status(),
            ReportingWindow(week),
            now_il(),
            modes=ran_modes(snap.analyses.values()),
        )
        self.repo.put_doc(KPI, week.isoformat(), pack)
        return pack

    def kpi_markdown(self, week: date) -> str:
        return render(self.kpi(week), extra=self._geo_markdown())

    def export_kpi(self, week: date, path: Path) -> str:
        return export(self.kpi(week), path, extra=self._geo_markdown())

    # ---- GEO --------------------------------------------------------------------
    @property
    def _answers_path(self) -> Path:
        return self.settings.data_dir / "ai_answers.json"

    @property
    def _claims(self) -> dict[str, str]:
        return load_claims(self.settings.data_dir / "brand_context.md")

    def geo_report(self) -> GeoReport:
        report = build_report(self._answers_path)
        self.repo.put_doc(GEO, "latest", report)
        return report

    def brief(self) -> ContentBrief:
        """The stored brief for the top gap; else the recorded LLM brief; else the template."""
        top = self.geo_report().gaps[0]
        stored = self.repo.get_doc(BRIEF, top.prompt_id, ContentBrief)
        if stored is not None:
            return stored
        brief = self._recorded_brief(top.prompt_id) or self._template_brief(top.prompt_id)
        self.repo.put_doc(BRIEF, top.prompt_id, brief)
        return brief

    def regenerate_brief(self) -> ContentBrief:
        """Explicit human action: a live LLM brief if a key is set, else the template."""
        top = self.geo_report().gaps[0]
        if self.client is None:
            brief = self._template_brief(top.prompt_id)
        else:
            result, _ = generate_brief(self.client, top, self._claims)
            if isinstance(result, str):
                brief = self._template_brief(top.prompt_id, note=f"LLM brief unusable: {result}")
            else:
                brief = self._assemble(result, top.prompt_id, "llm", self.client.model)
        self.repo.put_doc(BRIEF, top.prompt_id, brief)
        return brief

    def brief_fixture_path(self, prompt_id: str) -> Path:
        return self.settings.fixtures_dir / "geo" / f"brief_{prompt_id}.json"

    def brief_input_hash(self, prompt_id: str) -> str:
        gap = next(g for g in self.geo_report().gaps if g.prompt_id == prompt_id)
        return message_hash(BRIEF_PROMPT_VERSION, build_user(gap, self._claims))

    def _recorded_brief(self, prompt_id: str) -> ContentBrief | None:
        path = self.brief_fixture_path(prompt_id)
        if not path.is_file():
            return None
        try:
            recorded = RecordedReply.model_validate_json(path.read_text(encoding="utf-8"))
        except ValueError:
            log.warning("unreadable brief fixture prompt=%s", prompt_id)
            return None
        if recorded.raw is None or recorded.message_sha256 != self.brief_input_hash(prompt_id):
            return None
        result = parse_brief(recorded.raw)
        if isinstance(result, str):
            return self._template_brief(prompt_id, note=f"recorded LLM brief unusable: {result}")
        return self._assemble(result, prompt_id, "recorded fixture", recorded.model)

    def _template_brief(self, prompt_id: str, note: str | None = None) -> ContentBrief:
        gap = next(g for g in self.geo_report().gaps if g.prompt_id == prompt_id)
        return self._assemble(template_brief(gap, self._claims), prompt_id, "template", None, note)

    def _assemble(
        self,
        draft: ContentBriefDraft,
        prompt_id: str,
        mode: Literal["llm", "recorded fixture", "template"],
        model: str | None,
        note: str | None = None,
    ) -> ContentBrief:
        return assemble(
            draft,
            prompt_id=prompt_id,
            mode=mode,
            model=model,
            claims=self._claims,
            competitors=competitors(self._answers_path),
            generated_at=now_il(),
            note=note,
        )

    def _geo_markdown(self) -> str:
        return render_geo(self.geo_report(), self.brief())

    # ---- logs and side lists ------------------------------------------------------
    def suppression_log(self) -> list[dict[str, Any]]:
        snap = self.snapshot()
        rows = []
        for pid, assessment in sorted(snap.assessments.items()):
            if assessment.status != Status.SUPPRESSED:
                continue
            ctx = snap.world.leads[pid]
            trigger = next(
                (a.inbound_id for a in ctx.analyses
                 if a.extraction and a.extraction.intent.value == "unsubscribe"),
                ctx.inbound[-1].id,
            )  # fmt: skip
            when = next(m.received_at for m in ctx.inbound if m.id == trigger)
            rows.append({
                "person_id": pid,
                "name": person_name(snap.world.identity.persons[pid]),
                "inbound_id": trigger,
                "requested_at": when,
            })  # fmt: skip
        return rows

    def crm_contacts_with_activity(self) -> list[dict[str, Any]]:
        """People with decisions or pipeline events but no inbound (e.g. Felix, D3)."""
        snap = self.snapshot()
        events = self.repo.list_events()
        out = []
        for pid, person in sorted(snap.world.identity.persons.items()):
            if person.inbound or person.crm is None:
                continue
            decisions = snap.world.decisions_by_person.get(pid, [])
            person_events = [e for e in events if e.contact_email in person.emails]
            if not decisions and not person_events:
                continue
            out.append({
                "person_id": pid,
                "name": person_name(person),
                "company": person.crm.company_name,
                "decisions": decisions,
                "events": sorted(person_events, key=lambda e: e.occurred_at),
                "note": "CRM contact with no inbound in the data: no lead status",
            })  # fmt: skip
        return out

    def ingest_errors(self) -> list[IngestError]:
        return self.repo.list_ingest_errors()


def ran_modes(analyses: Iterable[MessageAnalysis]) -> list[AnalysisMode]:
    """Modes of analyses that actually ran (an injection stop runs no analysis)."""
    return sorted({a.mode for a in analyses if a.extraction is not None or a.failure is not None})


def _first_name(person: Person) -> str | None:
    for message in person.inbound:
        if message.from_name:
            return message.from_name.split()[0]
    return None
