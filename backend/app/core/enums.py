"""Shared vocabularies from the brief and ql_standard.md."""

from __future__ import annotations

from enum import StrEnum


class Channel(StrEnum):
    FORM_FILL = "form_fill"
    EMAIL_REPLY = "email_reply"
    LINKEDIN_DM = "linkedin_dm"
    OTHER = "other"


class Source(StrEnum):
    EVENT_EMAIL = "event-email"
    PAID = "paid"
    HISTORICAL_REACTIVATION = "historical-reactivation"
    NEW_CONNECTION = "new-connection"
    WARM_NETWORK = "warm-network"
    ORGANIC_REFERRAL = "organic/referral"


class Status(StrEnum):
    QL_CANDIDATE = "QL candidate"
    QL = "QL"
    EXCLUDED = "excluded"
    DISQUALIFIED = "disqualified"
    NURTURE = "nurture"
    SUPPRESSED = "suppressed"
    NEEDS_REVIEW = "needs review"


class Intent(StrEnum):
    DEMO = "demo"
    PRICING = "pricing"
    PILOT = "pilot"
    NOT_INTERESTED = "not interested"
    UNSUBSCRIBE = "unsubscribe"
    AUTO_REPLY = "auto-reply"
    PARTNERSHIP = "partnership"
    INVESTOR = "investor"
    JOB_SEEKER = "job seeker"
    OTHER = "other"


class Region(StrEnum):
    BENELUX = "benelux"
    NORDICS = "nordics"
    UK = "uk"
    DACH = "dach"
    SINGAPORE = "singapore"
    APAC_OTHER = "apac_other"
    US = "us"
    ISRAEL = "israel"
    OTHER = "other"


ICP_REGIONS: frozenset[Region] = frozenset(
    {
        Region.BENELUX,
        Region.NORDICS,
        Region.UK,
        Region.DACH,
        Region.SINGAPORE,
        Region.US,
        Region.ISRAEL,
    }
)


class ProblemCategory(StrEnum):
    RATE_QUOTING = "rate_quoting"
    DOCUMENT_EXTRACTION = "document_extraction"
    INVOICE_RECONCILIATION = "invoice_reconciliation"
    TRADE_DOCUMENT_CHECKING = "trade_document_checking"
    OTHER = "other"
    NONE = "none"


SOLVED_PROBLEMS: frozenset[ProblemCategory] = frozenset(
    {
        ProblemCategory.RATE_QUOTING,
        ProblemCategory.DOCUMENT_EXTRACTION,
        ProblemCategory.INVOICE_RECONCILIATION,
        ProblemCategory.TRADE_DOCUMENT_CHECKING,
    }
)


class AnalysisMode(StrEnum):
    LLM = "llm"
    RECORDED_FIXTURE = "recorded fixture"
    RULES_ONLY = "rules-only fallback"
