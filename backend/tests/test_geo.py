"""GEO: findings, gap ranking (plan §6), risk table, claim validator, brief paths (offline)."""

from __future__ import annotations

import json
from dataclasses import replace
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app.core.config import REPO_ROOT, load_settings
from app.geo.analyze import is_lookalike, is_owned, wrong_claims
from app.geo.brief import generate_brief, template_brief
from app.geo.claims import load_claims
from app.geo.report import build_report
from app.geo.schemas import Claimed, ContentBriefDraft, GeoReport
from app.geo.validator import publishable, validate_brief
from app.main import create_app
from app.service import Service
from tests.fakes import FakeLLM

DATA = REPO_ROOT / "data"
CLAIMS = load_claims(DATA / "brand_context.md")
COMPETITORS = ["Laneframe", "QuoteHarbor", "Rateway AI", "DocuFreight"]
REPORT: GeoReport = build_report(DATA / "ai_answers.json")
FINDINGS = {f.answer_id: f for f in REPORT.findings}


@pytest.mark.parametrize(
    ("answer_id", "state"),
    [
        ("P1-PER", "owned"),
        ("P2-PER", "mentioned_unowned"),  # cited from stargo-shipping.com, a look-alike
        ("P5-CHA", "wrong"),  # holiday booking app
        ("P5-GEM", "wrong"),  # ocean carrier
        ("P5-PER", "owned"),
        ("P7-GEM", "owned"),
        ("P6-CHA", "absent"),
    ],
)
def test_answer_states(answer_id: str, state: str) -> None:
    assert FINDINGS[answer_id].state == state


def test_owned_domain_check_is_exact() -> None:
    owned = ["stargo.co"]
    assert is_owned("https://stargo.co/rate-quoting", owned)
    assert is_owned("https://www.stargo.co", owned) and is_owned("https://docs.stargo.co/x", owned)
    assert not is_owned("https://stargo-shipping.com/news", owned)
    assert not is_owned("https://stargo.co.evil.com", owned)
    assert is_lookalike("https://stargo-travel.example/reviews", "Stargo", owned)


def test_competitors_are_canonicalised() -> None:
    assert FINDINGS["P2-CHA"].competitors == ["DocuFreight", "Laneframe"]  # "Laneframe Docs"
    assert FINDINGS["P3-GEM"].competitors == ["QuoteHarbor", "Rateway AI"]  # "QuoteHarbor Audit"
    assert FINDINGS["P5-CHA"].competitors == []


def test_wrong_claim_rules() -> None:
    assert [w.rule for w in wrong_claims("Stargo is an ocean carrier.", "Stargo")] == [
        "not a carrier"
    ]
    assert wrong_claims("Stargo extracts data for freight forwarders.", "Stargo") == []
    assert wrong_claims("Stargo moves freight across Europe.", "Stargo")[0].rule == (
        "does not move freight"
    )


def test_gap_ranking_matches_plan() -> None:
    ranked = [(g.prompt_id, g.score) for g in REPORT.gaps]
    assert ranked == [
        ("P6", 9), ("P2", 7.5), ("P1", 6), ("P3", 6), ("P4", 4), ("P5", 3), ("P7", 2), ("P8", 0),
    ]  # fmt: skip
    p1, p3 = REPORT.gaps[2], REPORT.gaps[3]
    assert len(p1.competitors) > len(p3.competitors)  # tie broken by competitors present
    assert REPORT.gaps[-1].fit == 0  # benchmarking: no BC-3 product


def test_risk_table_keeps_low_priority_brand_risks() -> None:
    risks = {(r.answer_id, r.kind) for r in REPORT.risks}
    assert risks == {
        ("P2-PER", "lookalike_citation"),
        ("P5-CHA", "wrong_claim"),
        ("P5-CHA", "lookalike_citation"),
        ("P5-GEM", "wrong_claim"),
    }


# ---- claim validator -------------------------------------------------------------


def good_draft() -> ContentBriefDraft:
    return template_brief(REPORT.gaps[0], CLAIMS)


def with_paragraph(text: str, refs: list[str]) -> ContentBriefDraft:
    draft = good_draft()
    section = draft.sections[0].model_copy(update={"paragraphs": [Claimed(text=text, refs=refs)]})
    return draft.model_copy(update={"sections": [section, *draft.sections[1:]]})


def test_template_brief_passes_for_every_fit_gap() -> None:
    for gap in REPORT.gaps:
        if gap.fit:
            flags = validate_brief(template_brief(gap, CLAIMS), CLAIMS, COMPETITORS)
            assert flags == [], (gap.prompt_id, flags)


@pytest.mark.parametrize(
    ("text", "refs", "rule"),
    [
        ("Stargo cuts quoting costs by 40%.", ["BC-3a"], "figure not in the cited claims"),
        ("Quotes go out in under 15 minutes.", [], "untagged claim"),
        ("Quotes are drafted for analysts.", ["BC-9"], "unknown or non-citable reference"),
        ("Quotes are drafted for analysts.", ["BC-5"], "unknown or non-citable reference"),
        ("Unlike Laneframe, Stargo drafts quotes.", ["BC-3a"], "competitor named in an answer"),
        ("Stargo is used by Acme Freight for quotes.", ["BC-3a"], "customer names"),
        ("Stargo is a freight forwarder that quotes rates.", ["BC-3a"], "BC-5: Stargo is"),
    ],
)
def test_validator_blocks_unsupported_claims(text: str, refs: list[str], rule: str) -> None:
    flags = validate_brief(with_paragraph(text, refs), CLAIMS, COMPETITORS)
    assert any(f.severity == "block" and f.rule.startswith(rule) for f in flags), flags
    assert not publishable(flags)


def test_validator_allows_competitor_in_title_and_faq_question_only() -> None:
    draft = good_draft()
    assert "Laneframe" in draft.title and "Laneframe" in draft.faq[0].question
    assert publishable(validate_brief(draft, CLAIMS, COMPETITORS))
    heading = draft.sections[0].model_copy(update={"heading": "Why teams leave Laneframe"})
    bad = draft.model_copy(update={"sections": [heading, *draft.sections[1:]]})
    assert not publishable(validate_brief(bad, CLAIMS, COMPETITORS))


def test_validator_enforces_contract_and_warns_on_hype() -> None:
    draft = good_draft()
    short = draft.model_copy(update={"direct_answer": Claimed(text="Too short.", refs=["BC-1"])})
    assert any("40–60 words" in f.rule for f in validate_brief(short, CLAIMS, COMPETITORS))
    two = draft.model_copy(update={"sections": draft.sections[:2], "faq": draft.faq[:2]})
    rules = {f.rule.split(" (")[0] for f in validate_brief(two, CLAIMS, COMPETITORS)}
    assert {"BC-7: 3–5 sections required", "BC-7: 3–5 FAQ questions required"} <= rules
    hype = with_paragraph("A revolutionary agent drafts quotes for analysts.", ["BC-3a"])
    flags = validate_brief(hype, CLAIMS, COMPETITORS)
    assert [f.severity for f in flags if "hype" in f.rule] == ["warn"]


def test_pp_figure_with_its_ref_is_allowed() -> None:
    text = "A pilot cut median spot-quote turnaround from about 3 hours to under 15 minutes."
    assert publishable(validate_brief(with_paragraph(text, ["PP-1"]), CLAIMS, COMPETITORS))
    assert not publishable(validate_brief(with_paragraph(text, ["BC-3a"]), CLAIMS, COMPETITORS))


# ---- brief generation paths ----------------------------------------------------------


def test_llm_brief_bad_json_is_reported() -> None:
    result, raw = generate_brief(FakeLLM(reply="Here is your brief!"), REPORT.gaps[0], CLAIMS)
    assert result == "invalid JSON" and raw is not None


def test_llm_brief_gets_only_question_and_claims() -> None:
    llm = FakeLLM(reply=good_draft().model_dump_json())
    result, _ = generate_brief(llm, REPORT.gaps[0], CLAIMS)
    assert isinstance(result, ContentBriefDraft)
    sent = json.loads(llm.calls[0][1])
    assert set(sent) == {"buyer_question", "primary_claims", "approved_claims"}
    assert sent["primary_claims"] == ["BC-3a", "PP-1"]


def service(tmp_path: Path, client: FakeLLM | None = None, fixtures: Path | None = None) -> Service:
    base = load_settings(read_dotenv=False)
    settings = replace(base, db_path=tmp_path / "g.db", llm_api_key=None,
                       fixtures_dir=fixtures or base.fixtures_dir)  # fmt: skip
    return Service(settings, client=client)


def test_recorded_llm_brief_is_used_without_a_key(tmp_path: Path) -> None:
    brief = service(tmp_path).brief()
    assert brief.prompt_id == "P6"
    assert brief.mode == "recorded fixture" and brief.model == "openai/gpt-oss-120b"
    assert brief.publishable


def test_no_fixture_and_no_key_gives_template(tmp_path: Path) -> None:
    brief = service(tmp_path, fixtures=tmp_path / "none").brief()
    assert brief.mode == "template" and brief.publishable and brief.flags == []


def test_regenerate_with_unsafe_llm_brief_is_flagged_not_hidden(tmp_path: Path) -> None:
    bad = with_paragraph("Unlike Laneframe, Stargo cuts costs by 40%.", ["BC-3a"])
    svc = service(tmp_path, client=FakeLLM(reply=bad.model_dump_json()))
    brief = svc.regenerate_brief()
    assert brief.mode == "llm" and not brief.publishable
    assert {f.rule.split(":")[0] for f in brief.flags if f.severity == "block"} >= {
        "figure not in the cited claims (BC-5)", "competitor named in an answer (BC-5)",
    }  # fmt: skip
    assert svc.brief().mode == "llm"  # stored, shown with its flags


def test_geo_api_and_kpi_section(tmp_path: Path) -> None:
    with TestClient(create_app(service(tmp_path))) as api:
        report = api.get("/api/geo").json()
        assert report["gaps"][0]["prompt_id"] == "P6"
        assert api.get("/api/geo/brief").json()["mode"] == "recorded fixture"
        assert api.post("/api/geo/brief").json()["mode"] == "template"  # no key
        md = api.get("/api/kpi/markdown").text
    assert "## AI visibility (GEO)" in md and "P6 alternatives to Laneframe" in md
    assert md.index("## AI visibility") < md.index("## Note to the CRO")
