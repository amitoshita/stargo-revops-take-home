"""Rules-only Agent A: keyword extraction used when no LLM is configured.

Deliberately conservative. It handles English only; any other language returns
`fallback_unsupported` (→ needs review), because guessing intent in a language it cannot read
would be worse than asking a human. Evidence quotes are sentence spans of the message, so the
same quote check as the LLM path always passes.
"""

from __future__ import annotations

import re
from collections.abc import Iterable

from app.agents.schemas import AgentAOutput, AnalysisFailure, Evidence, InterestLevel, StatedFacts
from app.agents.schemas import TimingHorizon as Timing
from app.core.enums import Intent, ProblemCategory
from app.ingest.normalize import country_from_text, country_name, normalize_country

_EN_WORDS = frozenset(
    {
        "the", "a", "an", "and", "to", "of", "we", "our", "you", "your", "is", "are", "in",
        "for", "on", "with", "this", "that", "it", "be", "can", "would", "please", "i", "my",
        "me", "have", "has", "will", "from", "at", "as", "not",
    }
)  # fmt: skip
_NON_LATIN = re.compile(r"[֐-׿؀-ۿЀ-ӿ一-鿿぀-ヿ]")


def _sentences(text: str) -> list[str]:
    parts = re.split(r"(?<=[.!?])\s+|\n+", text)
    return [p.strip() for p in parts if p.strip()]


def is_english(text: str) -> bool:
    if _NON_LATIN.search(text):
        return False
    words = re.findall(r"[a-zA-Z']+", text.lower())
    if not words:
        return False
    hits = sum(1 for w in words if w in _EN_WORDS)
    return hits >= 2 and hits / len(words) >= 0.15


def _find(sentences: Iterable[str], patterns: Iterable[str]) -> str | None:
    for sentence in sentences:
        for pattern in patterns:
            if re.search(pattern, sentence, re.IGNORECASE):
                return sentence
    return None


_PRICING_ASK = (
    r"(send|share|get|see|your)\s+(us\s+|me\s+)?(the\s+)?pric(ing|es)|pricing (for|info|details)"
    r"|what would [^.?]* cost|how much|\bquote us\b"
)

_INTENT_RULES: list[tuple[Intent, tuple[str, ...]]] = [
    (Intent.UNSUBSCRIBE, (r"\bunsubscribe\b", r"remove me from", r"stop (emailing|contacting)")),
    (Intent.AUTO_REPLY, (r"out of (the )?office", r"automatic reply", r"auto-?reply")),
    (Intent.JOB_SEEKER, (r"\bintern(ship)?\b", r"\bjob\b", r"\bstudent\b", r"\b(cv|resume)\b")),
    (Intent.INVESTOR, (r"funding round", r"\binvest(ing|ment|or)?\b")),
    (Intent.PARTNERSHIP, (r"partnership", r"white-?label", r"\breseller\b")),
    (Intent.NOT_INTERESTED, (r"not interested", r"no interest", r"not (a )?priority")),
    (Intent.DEMO, (r"\bdemo\b",)),
    (Intent.PILOT, (r"\bpilot\b", r"\btrial\b")),
    (Intent.PRICING, (_PRICING_ASK,)),
    (Intent.DEMO, (r"show us", r"see it working", r"see how", r"\bcall\b", r"\bmeeting\b",
                   r"\btalk\b", r"\d+\s*minutes")),
]  # fmt: skip

_EXPLICIT = (r"\bdemo\b", _PRICING_ASK, r"\bpilot\b", r"\btrial\b", r"show us",
             r"see it working", r"see how")  # fmt: skip
_MEETING = (r"\bcall\b", r"\bmeeting\b", r"\btalk\b", r"\d+\s*minutes")
_SOFT = (r"happy to chat", r"looking forward", r"if useful", r"keep in touch")
_INTEREST_RULES: list[tuple[InterestLevel, tuple[str, ...]]] = [
    ("explicit_request", _EXPLICIT),
    ("soft_positive", _SOFT),  # before meeting: "looking forward to our call" is soft
    ("meeting_request", _MEETING),
]

_PROBLEMS: list[tuple[ProblemCategory, tuple[str, ...]]] = [
    (ProblemCategory.INVOICE_RECONCILIATION, (r"reconcil", r"invoice audit")),
    (ProblemCategory.TRADE_DOCUMENT_CHECKING, (r"letters? of credit", r"trade.finance doc")),
    (ProblemCategory.RATE_QUOTING, (r"\brfqs?\b", r"rate requests?", r"rate cards?",
                                    r"quote requests?", r"\bquoting\b", r"each quote",
                                    r"spot rates?")),
    (ProblemCategory.DOCUMENT_EXTRACTION, (r"bills? of lading", r"booking (confirmation|entry)",
                                           r"re-?key", r"\bpdfs?\b", r"declarations",
                                           r"\bawbs?\b", r"document (extraction|automation)")),
]  # fmt: skip

_VOLUME = re.compile(
    r"\b\d[\d,]*\+?\s*(%|hours?|days?|weeks?|documents?|spreadsheets?|customers?|lanes?|"
    r"requests?|quotes?|invoices?|shipments?|a (day|week|month|year))|\bdozens\b|\bhundreds\b|"
    r"weeks every",
    re.IGNORECASE,
)

_VERTICALS = {
    "customs brokerage": "customs brokerage", "customs broker": "customs broker",
    "freight forwarder": "freight forwarder", "forwarder": "freight forwarder",
    "3pl": "3pl", "carrier": "carrier", "trucking": "trucking", "haulage": "trucking",
    "air cargo": "air cargo", "ground handling": "ground handling", "shipper": "shipper",
}  # fmt: skip


_TITLE_AT = re.compile(
    r"(?<!our )(?<!Our )(?<!my )(?<!My )(?<!their )(?<!Their )"
    r"\b((?:VP|SVP|EVP|Vice President|Director|Head|Chief|CEO|COO|CFO|CTO|Founder|Owner|"
    r"Manager|General Manager|Managing Director)\b[A-Za-z &]{0,40}?) at (?:a|an|our|the)\b"
)


def _role(sentences: list[str]) -> tuple[str | None, str | None]:
    for sentence in sentences:
        if match := re.search(r"\bI own an?\b", sentence, re.IGNORECASE):
            return "Owner", sentence
        if match := re.search(
            r"\bI(?: am|'m) (?:an? |the )?([A-Za-z][A-Za-z ]{2,60}?)(?: at\b|[,.]|$)",
            sentence,
        ):
            return match.group(1).strip(), sentence
        if match := re.search(r"\bI run ([a-z ]{3,60}?)(?: at\b|[,.]|$)", sentence, re.I):
            return f"runs {match.group(1).strip()}", sentence
        # A title without "I am": "VP Operations at a Singapore 3PL", "Director of Ops at ...".
        if match := re.search(_TITLE_AT, sentence):
            return match.group(1).strip(), sentence
    return None, None


# Words allowed between "a/an/our" and the vertical in a self-description: size words and a
# country ("a 40-person customs brokerage", "a German freight forwarder", "a Singapore 3PL").
# Anything else ("a few carrier quotes") is not the sender describing their company.
_DEMONYMS = {
    "dutch": "NL", "belgian": "BE", "swedish": "SE", "norwegian": "NO", "danish": "DK",
    "finnish": "FI", "british": "GB", "scottish": "GB", "german": "DE", "austrian": "AT",
    "swiss": "CH", "singaporean": "SG", "american": "US", "israeli": "IL", "french": "FR",
    "spanish": "ES", "italian": "IT", "polish": "PL", "irish": "IE", "portuguese": "PT",
    "australian": "AU", "japanese": "JP", "chinese": "CN", "indian": "IN", "canadian": "CA",
}  # fmt: skip
_SIZE_WORD = re.compile(
    r"\d[\d,]*(-person)?|person|small|mid-?sized?|midsize|large|global|regional|independent|"
    r"leading|growing|family-owned",
    re.IGNORECASE,
)


def _place_code(word: str) -> str | None:
    word = word.removesuffix("-based")
    return _DEMONYMS.get(word.lower()) or normalize_country(word)


def _self_description(text: str) -> tuple[str | None, str | None]:
    """(vertical, ISO-2 country) from "a/an/our <size or country words> <vertical>"."""
    for key, vertical in _VERTICALS.items():
        pattern = rf"\b(?:a|an|our)\s+((?:[\w-]+\s+){{0,2}}?){key}\b"
        for match in re.finditer(pattern, text, re.IGNORECASE):
            words = match.group(1).split()
            codes = [_place_code(w) for w in words]
            if all(c or _SIZE_WORD.fullmatch(w) for w, c in zip(words, codes, strict=True)):
                return vertical, next((c for c in codes if c), None)
    return None, None


def _stated_country(text: str, sentences: list[str], described: str | None) -> str | None:
    """Only from the sender's own words ("in Haifa", "a German forwarder", "Rotterdam-based",
    "based in Denmark"); never from the email domain (docs/ASSUMPTIONS.md, D-add)."""
    if code := country_from_text(" ".join(s for s in sentences if re.search(r"\bin\b", s))):
        return code
    if described:
        return described
    if match := re.search(r"\b([A-Z][a-z]+)-based\b", text):
        return _place_code(match.group(1))
    return None


def _facts(text: str, sentences: list[str]) -> tuple[StatedFacts, str | None]:
    employees = None
    quote = None
    size = r"\b(\d[\d,]*)[- ](?:person|people|employees?|staff|ftes?)\b"
    if match := re.search(size, text, re.IGNORECASE):
        employees = int(match.group(1).replace(",", ""))
    vertical, described = _self_description(text)
    vendor = bool(re.search(r"\bwe (build|make|sell|develop)\b[^.]*\bsoftware\b", text, re.I))
    code = _stated_country(text, sentences, described)
    country = country_name(code) if code else None
    if employees or vertical or vendor or country:
        quote = _find(sentences, [size, r"\bsoftware\b",
                                  *(rf"\b{k}\b" for k in _VERTICALS)])  # fmt: skip
    facts = StatedFacts(
        employees=employees, vertical=vertical, country=country, is_software_vendor=vendor
    )
    return facts, quote


def _timing(text: str) -> tuple[Timing, str | None]:
    rules: list[tuple[Timing, str]] = [
        ("this_week", r"this week|today|tomorrow|on (sunday|monday|tuesday|wednesday|thursday)"),
        ("next_weeks", r"next week|in (two|2|a few) weeks"),
        ("this_quarter", r"this quarter|this month"),
        ("later", r"\bq[1-4]\b|next year|later this year|in a few months"),
    ]
    for horizon, pattern in rules:
        if match := re.search(pattern, text, re.IGNORECASE):
            return horizon, match.group(0)
    return "none", None


def extract(subject: str | None, body: str) -> AgentAOutput | AnalysisFailure:
    text = f"{subject}\n{body}" if subject else body
    if not is_english(body):
        return AnalysisFailure(
            kind="fallback_unsupported",
            detail="rules-only fallback reads English only; a human must review",
        )
    sentences = _sentences(body)
    evidence: list[Evidence] = []

    intent = Intent.OTHER
    for candidate, patterns in _INTENT_RULES:
        if quote := _find(sentences, patterns):
            intent = candidate
            evidence.append(Evidence(field="intent", quote=quote))
            break

    interest: InterestLevel = "none"
    if intent in (Intent.NOT_INTERESTED, Intent.UNSUBSCRIBE):
        interest = "declined"
    elif intent not in (Intent.AUTO_REPLY, Intent.JOB_SEEKER, Intent.INVESTOR):
        for level, patterns in _INTEREST_RULES:
            if quote := _find(sentences, patterns):
                interest = level
                evidence.append(Evidence(field="interest", quote=quote))
                break
    if interest == "soft_positive" and intent == Intent.DEMO:
        intent = Intent.OTHER  # "happy to chat" is not a demo request

    category, problem = ProblemCategory.NONE, None
    for candidate_cat, patterns in _PROBLEMS:
        if quote := _find(sentences, patterns):
            category, problem = candidate_cat, quote
            evidence.append(Evidence(field="data_problem", quote=quote))
            break

    role, role_quote = _role(sentences)
    if role_quote:
        evidence.append(Evidence(field="buyer_role", quote=role_quote))
    facts, facts_quote = _facts(text, sentences)
    if facts_quote and facts_quote not in (e.quote for e in evidence):
        evidence.append(Evidence(field="company_facts", quote=facts_quote))
    timing, _ = _timing(text)

    return AgentAOutput(
        language="en",
        intent=intent,
        interest_level=interest,
        buyer_role=role,
        data_problem=problem[:300] if problem else None,
        problem_category=category,
        volume_stated=bool(problem and _VOLUME.search(body)),
        company_facts=facts,
        timing=timing,
        instruction_attempt=False,  # layer-1 detection runs before this
        evidence=evidence[:8],
    )
