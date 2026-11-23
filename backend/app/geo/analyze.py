"""Per prompt × engine findings, all by code (docs/ASSUMPTIONS.md: wrong-claim detection is
code only).

- Mention: the brand name as a whole word, any case ("StarGo" counts: the engine is talking
  about something it calls Stargo, even if it is the wrong company).
- Owned citation: the cited host is an owned domain or a subdomain of one. Never "contains
  stargo": stargo-shipping.com and stargo-travel.example are look-alikes, not ours.
- Competitors: known competitor names as whole words, canonicalised ("Laneframe Docs" →
  Laneframe), from the answer text and from cited hosts.
- Wrong claims (BC-5): a sentence that says Stargo *is* a carrier, broker, forwarder, travel
  or holiday company, or that it moves freight.
"""

from __future__ import annotations

import re
from urllib.parse import urlsplit

from app.geo.schemas import AiAnswer, AnswerState, Finding, WrongClaim

_SENTENCE = re.compile(r"(?<=[.!?])\s+")

# "Stargo is a/an ... <category>" within one sentence.
_WRONG_RULES: list[tuple[str, str]] = [
    ("not a carrier", r"\b(ocean |container |freight )?carrier\b|\bshipping line\b|"
                      r"\bcontainer shipping\b"),
    ("not a travel company", r"\b(holiday|travel|vacation|hotel|flight)s?\b|\bbooking app\b"),
    ("not a broker", r"\b(customs |freight )?broker(age)?\b"),
    ("not a forwarder", r"\b(freight )?forwarder\b"),
]  # fmt: skip
_MOVES_FREIGHT = re.compile(r"\b(moves?|ships?|transports?) (freight|cargo|containers?)\b", re.I)


def host(url: str) -> str:
    return (
        (urlsplit(url if "//" in url else f"//{url}").hostname or "").lower().removeprefix("www.")
    )


def is_owned(url: str, own_domains: list[str]) -> bool:
    h = host(url)
    return any(h == d or h.endswith("." + d) for d in own_domains)


def is_lookalike(url: str, brand: str, own_domains: list[str]) -> bool:
    return not is_owned(url, own_domains) and brand.lower() in host(url).replace("-", "")


def mentions(text: str, brand: str) -> bool:
    return re.search(rf"\b{re.escape(brand)}\b", text, re.IGNORECASE) is not None


def competitors_in(answer: AiAnswer, known: list[str]) -> list[str]:
    found = set()
    hosts = " ".join(host(u) for u in answer.citations)
    for name in known:
        if re.search(rf"\b{re.escape(name)}\b", answer.answer_text, re.IGNORECASE):
            found.add(name)
        slug = re.sub(r"[^a-z0-9]", "", name.lower())
        if slug and slug in hosts.replace("-", "").replace(".", " "):
            found.add(name)
    return sorted(found)


def wrong_claims(text: str, brand: str) -> list[WrongClaim]:
    out: list[WrongClaim] = []
    for sentence in _SENTENCE.split(text):
        if not mentions(sentence, brand):
            continue
        copula = re.search(rf"\b{re.escape(brand)}\b[^.]{{0,40}}?\b(is|are)\s+(a|an|the)\b(.*)",
                           sentence, re.IGNORECASE)  # fmt: skip
        claim_part = copula.group(3) if copula else ""
        for rule, pattern in _WRONG_RULES:
            if claim_part and re.search(pattern, claim_part, re.IGNORECASE):
                out.append(WrongClaim(text=sentence.strip(), contradicts="BC-5", rule=rule))
                break
        else:
            if _MOVES_FREIGHT.search(sentence):
                out.append(WrongClaim(text=sentence.strip(), contradicts="BC-5",
                                      rule="does not move freight"))  # fmt: skip
    return out


def analyse_answer(
    answer: AiAnswer, brand: str, own_domains: list[str], known: list[str]
) -> Finding:
    mentioned = mentions(answer.answer_text, brand)
    owned = [u for u in answer.citations if is_owned(u, own_domains)]
    lookalikes = sorted({host(u) for u in answer.citations if is_lookalike(u, brand, own_domains)})
    wrong = wrong_claims(answer.answer_text, brand)
    state: AnswerState
    if wrong:
        state = "wrong"
    elif mentioned and owned:
        state = "owned"
    elif mentioned:
        state = "mentioned_unowned"
    else:
        state = "absent"
    return Finding(
        answer_id=answer.answer_id,
        prompt_id=answer.prompt_id,
        prompt=answer.prompt,
        engine=answer.engine,
        priority=answer.priority,
        cluster=answer.cluster,
        stargo_mentioned=mentioned,
        owned_citation=bool(owned),
        owned_urls=owned,
        lookalike_domains=lookalikes,
        competitors=competitors_in(answer, known),
        wrong_claims=wrong,
        state=state,
    )
