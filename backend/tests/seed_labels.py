"""Hand-labelled Agent A outputs for the seed inbound (my reading of each message).

Used two ways: as a fake LLM in rules tests, and as the labelled eval set that recorded
LLM fixtures are scored against. IN-010 has no label: layer-1 injection detection stops it
before Agent A. IN-019 is rejected at ingest.
"""

from __future__ import annotations

from typing import Any

from app.agents.schemas import AgentAOutput


def _a(**kw: Any) -> AgentAOutput:
    base: dict[str, Any] = {
        "language": "en",
        "intent": "other",
        "interest_level": "none",
        "buyer_role": None,
        "data_problem": None,
        "problem_category": "none",
        "volume_stated": False,
        "company_facts": {},
        "timing": "none",
        "instruction_attempt": False,
        "evidence": [],
    }
    base.update(kw)
    return AgentAOutput.model_validate(base)


LABELS: dict[str, AgentAOutput] = {
    "IN-001": _a(
        intent="demo",
        interest_level="explicit_request",
        data_problem="~400 emailed spot rate requests a week, 3-4 hours per quote",
        problem_category="rate_quoting",
        volume_stated=True,
        timing="next_weeks",
        evidence=[
            {"field": "data_problem", "quote": "around 400 spot rate requests a week by email"},
            {"field": "interest", "quote": "I would like to see a demo next week"},
        ],
    ),
    "IN-002": _a(
        intent="demo",
        interest_level="meeting_request",
        data_problem="re-keys booking confirmations and invoices from PDFs into the TMS",
        problem_category="document_extraction",
        volume_stated=True,
        timing="this_week",
        evidence=[
            {
                "field": "data_problem",
                "quote": "re-keys booking confirmations and invoices from PDFs into our TMS",
            },
            {"field": "interest", "quote": "Can we talk on Sunday or Monday?"},
        ],
    ),
    "IN-003": _a(
        interest_level="soft_positive",
        evidence=[{"field": "interest", "quote": "Looking forward to our call."}],
    ),
    "IN-004": _a(
        intent="auto-reply",
        evidence=[{"field": "intent", "quote": "I am out of the office until 12 October"}],
    ),
    "IN-005": _a(
        intent="pilot",
        interest_level="explicit_request",
        data_problem="pricing team handles RFQs from 30+ customers in Excel",
        problem_category="rate_quoting",
        volume_stated=True,
        timing="this_quarter",
        evidence=[
            {
                "field": "data_problem",
                "quote": "Our pricing team handles RFQs from more than 30 customers, all in Excel",
            },
            {"field": "interest", "quote": "whether a 4-week pilot is possible this quarter"},
        ],
    ),
    "IN-006": _a(
        intent="pricing",
        interest_level="explicit_request",
        data_problem="wants document extraction at a second station",
        problem_category="document_extraction",
        evidence=[
            {
                "field": "data_problem",
                "quote": "The document extraction has been working well at our Dallas station",
            },
            {"field": "interest", "quote": "Please send pricing."},
        ],
    ),
    "IN-007": _a(
        data_problem="PoC on bills of lading",
        problem_category="document_extraction",
        evidence=[{"field": "data_problem", "quote": "20 sample bills of lading for the PoC"}],
    ),
    "IN-008": _a(
        intent="partnership",
        interest_level="meeting_request",
        company_facts={"is_software_vendor": True},
        timing="this_week",
        evidence=[
            {"field": "company_facts", "quote": "We build freight pricing software as well"},
            {"field": "intent", "quote": "explore a white-label partnership"},
        ],
    ),
    "IN-009": _a(
        intent="demo",
        interest_level="meeting_request",
        buyer_role="runs logistics procurement",
        data_problem="benchmarking carrier quotes across ~2,000 tendered lanes is manual",
        problem_category="other",
        volume_stated=True,
        company_facts={"company_name": "Kestrel"},
        evidence=[
            {"field": "data_problem", "quote": "benchmarking carrier quotes is still manual"},
            {"field": "interest", "quote": "Open to a 30-minute call."},
        ],
    ),
    "IN-011": _a(
        intent="pricing",
        interest_level="explicit_request",
        buyer_role="Owner",
        data_problem="import declarations prepared manually from invoices and packing lists",
        problem_category="document_extraction",
        company_facts={"employees": 40, "country": "Israel", "vertical": "customs brokerage"},
        evidence=[
            {"field": "company_facts", "quote": "I own a 40-person customs brokerage in Haifa"},
            {
                "field": "data_problem",
                "quote": "We process import declarations from supplier invoices and packing "
                "lists manually",
            },
            {"field": "interest", "quote": "What would document automation cost us"},
        ],
    ),
    "IN-012": _a(
        language="he",
        intent="demo",
        interest_level="meeting_request",
        data_problem="dozens of quote requests a day over WhatsApp and email, priced manually",
        problem_category="rate_quoting",
        volume_stated=True,
        timing="this_week",
        evidence=[
            {
                "field": "data_problem",
                "quote": "אנחנו מקבלים עשרות בקשות להצעות מחיר ביום בוואטסאפ ובמייל ומתמחרים "
                "הכול ידנית",
                "translation": "We get dozens of quote requests a day on WhatsApp and email "
                "and price everything manually",
            },
            {
                "field": "interest",
                "quote": "אשמח לשיחה השבוע",
                "translation": "Happy to have a call this week",
            },
        ],
    ),
    "IN-013": _a(
        language="nl",
        intent="not interested",
        interest_level="declined",
        timing="later",
        evidence=[
            {
                "field": "interest",
                "quote": "Op dit moment hebben we geen interesse",
                "translation": "At the moment we are not interested",
            }
        ],
    ),
    "IN-014": _a(
        intent="unsubscribe",
        interest_level="declined",
        evidence=[{"field": "intent", "quote": "Please remove me from your mailing list."}],
    ),
    "IN-015": _a(
        intent="job seeker",
        buyer_role="data science student",
        evidence=[{"field": "intent", "quote": "would love to join Stargo as an intern"}],
    ),
    "IN-016": _a(
        intent="investor",
        evidence=[{"field": "intent", "quote": "learn more about your next funding round"}],
    ),
    "IN-017": _a(
        intent="demo",
        interest_level="explicit_request",
        data_problem="weeks every quarter reconciling carrier invoices against contracted rates",
        problem_category="invoice_reconciliation",
        volume_stated=True,
        evidence=[
            {
                "field": "data_problem",
                "quote": "reconciling carrier invoices against contracted rates",
            },
            {"field": "interest", "quote": "Can you show us how this works?"},
        ],
    ),
    "IN-018": _a(
        intent="demo",
        interest_level="explicit_request",
        data_problem="rate cards spread over ~40 spreadsheets",
        problem_category="rate_quoting",
        volume_stated=True,
        evidence=[
            {"field": "data_problem", "quote": "Our rate cards live in about 40 spreadsheets."},
            {"field": "interest", "quote": "send me times for a demo"},
        ],
    ),
    "IN-020": _a(
        intent="other",
        interest_level="soft_positive",
        data_problem="manual booking entry",
        problem_category="document_extraction",
        evidence=[
            {"field": "data_problem", "quote": "We still have the issue with manual booking entry"},
            {"field": "interest", "quote": "Happy to chat if useful."},
        ],
    ),
    "IN-021": _a(
        intent="demo",
        interest_level="explicit_request",
        data_problem="rate quoting automation",
        problem_category="rate_quoting",
        evidence=[{"field": "interest", "quote": "Requesting a demo of rate quoting automation."}],
    ),
}
