"""Shared test helpers."""

from __future__ import annotations

from pathlib import Path

from app.agents.schemas import MessageAnalysis
from app.core.enums import AnalysisMode
from app.ingest.loader import SeedBundle, load_seed
from app.pipeline import World, build_world
from app.rules.injection import detect_instruction_attempt
from tests.seed_labels import LABELS

DATA_DIR = Path(__file__).resolve().parents[2] / "data"


def seed() -> SeedBundle:
    return load_seed(DATA_DIR)


def labelled_analyses(bundle: SeedBundle) -> dict[str, MessageAnalysis]:
    """Agent A results from the hand labels, with layer-1 injection detection applied."""
    out: dict[str, MessageAnalysis] = {}
    for message in bundle.inbound:
        signals = detect_instruction_attempt(message.subject, message.body)
        out[message.id] = MessageAnalysis(
            inbound_id=message.id,
            mode=AnalysisMode.LLM,
            extraction=None if signals else LABELS[message.id],
            failure=None,
            injection_signals=signals,
        )
    return out


def seed_world(bundle: SeedBundle | None = None) -> World:
    bundle = bundle or seed()
    return build_world(
        bundle.crm,
        bundle.inbound,
        bundle.decisions,
        labelled_analyses(bundle),
        [e.contact_email for e in bundle.events],
    )
