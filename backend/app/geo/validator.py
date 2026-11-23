"""Claim validator for content briefs. Code, not a model: it must be able to block.

Block (not publishable):
- BC-7 contract: 40–60 word direct answer, 3–5 sections, 3–5 FAQ items, a schema.org type.
- A claim with no BC/PP reference, or a reference that is not a citable claim.
- A number that is not in the cited claims (BC-5: no ROI or accuracy figures beyond PP-1–3).
- A competitor name anywhere except the title and FAQ questions (BC-5).
- Customer names or "used by / trusted by" lists (BC-5: none are approved).
- Saying Stargo is a carrier, broker, forwarder or travel company, or moves freight (BC-5).
Warn (publishable, but a human should look):
- Hype words (BC-6).
- A claim that shares no content words with the sources it cites (possible weak support).
"""

from __future__ import annotations

import re
from typing import Literal

from app.geo.analyze import wrong_claims
from app.geo.claims import CITABLE, figures_in
from app.geo.schemas import Claimed, ContentBriefDraft, ValidatorFlag

HYPE = re.compile(
    r"\b(revolutionary|game-?changing|cutting-edge|world-class|best-in-class|disruptive|"
    r"seamless(ly)?|unparalleled|next-gen(eration)?)\b",
    re.IGNORECASE,
)
CUSTOMERS = re.compile(
    r"\b(customers?|clients?|users?) (such as|like|including|include)\b"
    r"|\b(used|trusted|chosen|loved|adopted|deployed) (by|at)\b"
    r"|\b(in use|live|in production) at\b|\bcase stud(y|ies) (with|from)\b",
    re.IGNORECASE,
)
# "Acme uses Stargo", "Maersk chose Stargo": a capitalised name doing something with Stargo.
NAMED_USER = re.compile(
    r"\b[A-Z][\w&.-]+ (uses|use|chose|choose|relies on|switched to|runs) Stargo\b"
)
# BC-5 self-descriptions the engine-answer check would miss (no "Stargo is a ..." copula).
SELF_CATEGORY = re.compile(
    r"\b(we are|we're|our (company|platform|product|team) is|stargo,)\s+(a|an|the)\b[^.]{0,40}?"
    r"\b(carrier|shipping line|forwarder|broker(age)?|travel|holiday|airline)\b",
    re.IGNORECASE,
)
STOP = frozenset(
    {
        "the", "and", "for", "with", "from", "that", "this", "into", "your", "their", "them",
        "they", "what", "when", "which", "while", "about", "after", "before", "more", "most",
        "than", "then", "also", "each", "such", "have", "will", "can", "stargo", "under",
        "over", "reached", "reach", "cut", "cuts", "pilot", "pilots", "team", "teams",
    }
)  # fmt: skip


def _content_words(text: str) -> set[str]:
    return {w for w in re.findall(r"[a-z]{4,}", text.lower()) if w not in STOP}


def _check_claim(
    claim: Claimed,
    location: str,
    claims: dict[str, str],
    competitors: list[str],
    flags: list[ValidatorFlag],
    *,
    competitor_allowed: bool = False,
) -> None:
    def flag(rule: str, severity: Literal["block", "warn"] = "block") -> None:
        flags.append(
            ValidatorFlag(location=location, rule=rule, severity=severity, text=claim.text)
        )

    if not claim.refs:
        flag("untagged claim: every claim must cite a BC or PP id")
    unknown = [r for r in claim.refs if not CITABLE.match(r) or r not in claims]
    if unknown:
        flag(f"unknown or non-citable reference: {', '.join(unknown)}")
    cited = " ".join(claims.get(r, "") for r in claim.refs)
    words = _content_words(claim.text)
    for figure in sorted(figures_in(claim.text)):
        # The figure must come from a cited source that is about this claim, so one PP cannot
        # lend its number to an unrelated statement.
        support = [
            r for r in claim.refs
            if figure in figures_in(claims.get(r, ""))
            and len(words & _content_words(claims.get(r, ""))) >= 2
        ]  # fmt: skip
        if not support:
            flag(f"figure not in the cited claims (BC-5): {figure}")
    if not competitor_allowed:
        named = [c for c in competitors if re.search(rf"\b{re.escape(c)}\b", claim.text, re.I)]
        if named:
            flag(f"competitor named in an answer (BC-5): {', '.join(named)}")
    if CUSTOMERS.search(claim.text) or NAMED_USER.search(claim.text):
        flag("customer names or 'used by' list (BC-5: none approved)")
    for wrong in wrong_claims(claim.text, "Stargo"):
        flag(f"BC-5: Stargo is {wrong.rule}")
    if SELF_CATEGORY.search(claim.text):
        flag("BC-5: Stargo is not a carrier, broker, forwarder or travel company")
    if HYPE.search(claim.text):
        flag("hype word (BC-6)", "warn")
    if claim.refs and not unknown and not (_content_words(claim.text) & _content_words(cited)):
        flag("claim shares no content words with its cited sources: check support", "warn")


def _check_headline(
    text: str,
    location: str,
    competitors: list[str],
    flags: list[ValidatorFlag],
    *,
    competitor_allowed: bool,
) -> None:
    """Titles, headings and FAQ questions carry no refs, so they may make no claims at all."""

    def flag(rule: str, severity: Literal["block", "warn"] = "block") -> None:
        flags.append(ValidatorFlag(location=location, rule=rule, severity=severity, text=text))

    if figures_in(text):
        flag("figure in a title, heading or question (no source can back it there)")
    if CUSTOMERS.search(text) or NAMED_USER.search(text):
        flag("customer names or 'used by' list (BC-5: none approved)")
    if wrong_claims(text, "Stargo") or SELF_CATEGORY.search(text):
        flag("BC-5: Stargo is not a carrier, broker, forwarder or travel company")
    if not competitor_allowed:
        named = [c for c in competitors if re.search(rf"\b{re.escape(c)}\b", text, re.I)]
        if named:
            flag(f"competitor named in a heading (BC-5): {', '.join(named)}")
    if HYPE.search(text) or re.search(r"#\s*1\b|\bthe best\b|\bleading\b", text, re.I):
        flag("hype or superlative (BC-6)", "warn")


def validate_brief(
    draft: ContentBriefDraft, claims: dict[str, str], competitors: list[str]
) -> list[ValidatorFlag]:
    flags: list[ValidatorFlag] = []

    def structural(location: str, rule: str, text: str) -> None:
        flags.append(ValidatorFlag(location=location, rule=rule, severity="block", text=text))

    words = len(draft.direct_answer.text.split())
    if not 40 <= words <= 60:
        structural("direct_answer", f"BC-7: direct answer must be 40–60 words (has {words})",
                   draft.direct_answer.text)  # fmt: skip
    if not 3 <= len(draft.sections) <= 5:
        structural("sections", f"BC-7: 3–5 sections required (has {len(draft.sections)})", "")
    if not 3 <= len(draft.faq) <= 5:
        structural("faq", f"BC-7: 3–5 FAQ questions required (has {len(draft.faq)})", "")
    if not draft.schema_org_type.strip():
        structural("schema_org_type", "BC-7: a schema.org type is required", "")

    _check_headline(draft.title, "title", competitors, flags, competitor_allowed=True)
    _check_claim(draft.direct_answer, "direct_answer", claims, competitors, flags)
    for i, section in enumerate(draft.sections):
        _check_headline(
            section.heading, f"sections[{i}].heading", competitors, flags, competitor_allowed=False
        )
        for j, paragraph in enumerate(section.paragraphs):
            _check_claim(paragraph, f"sections[{i}].paragraphs[{j}]", claims, competitors, flags)
    for i, item in enumerate(draft.faq):
        _check_headline(
            item.question, f"faq[{i}].question", competitors, flags, competitor_allowed=True
        )
        for j, answer in enumerate(item.answer):
            _check_claim(answer, f"faq[{i}].answer[{j}]", claims, competitors, flags)
    return flags


def publishable(flags: list[ValidatorFlag]) -> bool:
    return not any(f.severity == "block" for f in flags)
