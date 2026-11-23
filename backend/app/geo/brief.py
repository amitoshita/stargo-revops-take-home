"""Content brief for the top gap: LLM generation (validated) with a template fallback.

The model gets the buyer's question, the approved claims library with ids, the BC-7
contract and the BC-5 rules. Its JSON is schema-validated; then the code validator flags or
blocks claims. The template is built only from approved claim text, so it always passes.
"""

from __future__ import annotations

import json
import re
from datetime import datetime
from typing import Literal

from pydantic import ValidationError

from app.agents.llm_client import LLMClient, LLMError
from app.geo.schemas import (
    BriefSection,
    Claimed,
    ContentBrief,
    ContentBriefDraft,
    FaqItem,
    GapScore,
    ValidatorFlag,
)
from app.geo.validator import publishable, validate_brief

BRIEF_PROMPT_VERSION = "geo-brief-v1"
BriefMode = Literal["llm", "recorded fixture", "template"]

# Cluster → (product claim id, proof point ids) used by the template and suggested to the LLM.
CLUSTER_CLAIMS: dict[str, tuple[str, list[str]]] = {
    "rate-quoting": ("BC-3a", ["PP-1"]),
    "competitive": ("BC-3a", ["PP-1"]),
    "document-extraction": ("BC-3b", ["PP-2"]),
    "air-cargo": ("BC-3b", ["PP-3"]),
    "invoice-audit": ("BC-3c", []),
    "trade-finance": ("BC-3d", []),
    "brand": ("BC-1", []),
}

SYSTEM = """You write a content brief for an article that AI answer engines can quote. The
company is Stargo. You may only state facts that appear in the approved claims you are
given, and every factual sentence must cite the claim ids it comes from.

Rules (from the brand context, all mandatory):
- BC-7 contract: a title that matches the buyer's question; a direct answer of 40 to 60
  words as the first paragraph; 3 to 5 sections with descriptive headings; an FAQ of 3 to 5
  questions; every factual claim tagged with the BC or PP id it comes from; a suggested
  schema.org type.
- BC-5: no customer names; no ROI or accuracy figures other than those in PP-1 to PP-3;
  no statements about competitors' products, pricing or weaknesses. A competitor's name may
  appear ONLY in the title or in an FAQ question that repeats the buyer's own question,
  never in an answer, heading or paragraph. Stargo is not a carrier, broker, forwarder or
  travel company and does not move freight.
- BC-6 voice: plain, specific, operator to operator, short sentences, no hype words.

Return ONE JSON object:
{"title": str,
 "direct_answer": {"text": str, "refs": [ids]},
 "sections": [{"heading": str, "paragraphs": [{"text": str, "refs": [ids]}]}],
 "faq": [{"question": str, "answer": [{"text": str, "refs": [ids]}]}],
 "schema_org_type": str}
JSON only, no markdown."""


def build_user(gap: GapScore, claims: dict[str, str]) -> str:
    product, proofs = CLUSTER_CLAIMS.get(gap.cluster, ("BC-1", []))
    return json.dumps(
        {
            "buyer_question": gap.prompt,
            "primary_claims": [product, *proofs],
            "approved_claims": claims,
        },
        ensure_ascii=False,
        indent=1,
    )


def parse_brief(raw: str) -> ContentBriefDraft | str:
    """Return the validated draft, or a short reason it could not be used."""
    text = raw.strip()
    if text.startswith("```"):
        text = re.sub(r"^```(?:json)?\s*|\s*```$", "", text)
    try:
        return ContentBriefDraft.model_validate(json.loads(text))
    except json.JSONDecodeError:
        return "invalid JSON"
    except ValidationError as exc:
        fields = sorted({".".join(str(p) for p in e["loc"]) for e in exc.errors()})[:5]
        return "schema invalid: " + ", ".join(fields)


def generate_brief(
    client: LLMClient, gap: GapScore, claims: dict[str, str]
) -> tuple[ContentBriefDraft | str, str | None]:
    """One call in the provider's JSON mode; if the provider rejects the output (it validates
    JSON server-side and can fail on long structures), one retry without it. Either way the
    reply is parsed and schema-validated here, then checked by the claim validator."""
    user = build_user(gap, claims)
    raw: str | None = None
    for json_mode in (True, False):
        try:
            raw = client.complete(SYSTEM, user, json_mode=json_mode, ref=gap.prompt_id)
        except LLMError as exc:
            if json_mode and exc.kind == "model_error":
                continue
            return f"LLM call failed: {exc.kind}", None
        break
    if raw is None:
        return "LLM call failed: model_error", None
    return parse_brief(raw), raw


def _lower(text: str) -> str:
    return text[0].lower() + text[1:] if text else text


def _c(text: str, *refs: str) -> Claimed:
    return Claimed(text=text, refs=list(refs))


def template_brief(gap: GapScore, claims: dict[str, str]) -> ContentBriefDraft:
    """Built from approved claim text only. Deterministic; used without a key or on failure."""
    product_id, proofs = CLUSTER_CLAIMS.get(gap.cluster, ("BC-1", []))
    product = claims.get(product_id, claims["BC-1"])
    if product_id.startswith("BC-3"):
        name, _, what = product.partition(". ")
        lead = f"Stargo's {name} {what[0].lower()}{what[1:].rstrip('.')}."
    else:
        name, what, lead = "Stargo", product, product
    # Direct answer: approved sentences until the 40–60 word window is reached.
    candidates = [
        (lead, product_id),
        ("Humans stay in control: agents draft, people approve.", "BC-1"),
        ("Stargo builds agentic AI that turns messy enterprise documents, emails and datasets "
         "into trusted operational transactions.", "BC-1"),
        (f"It is built for {_lower(claims['BC-2'])}", "BC-2"),
    ]  # fmt: skip
    parts: list[str] = []
    refs: list[str] = []
    for sentence, ref in candidates:
        if sentence in parts or len(" ".join(parts).split()) >= 40:
            continue
        if len(" ".join([*parts, sentence]).split()) > 60:
            continue
        parts.append(sentence)
        refs += [ref] if ref not in refs else []
    direct = " ".join(parts)
    sections = [
        BriefSection(
            heading=f"What {'the ' + name if name != 'Stargo' else name} does",
            paragraphs=[_c(lead, product_id)],
        ),
        BriefSection(
            heading="How people stay in control",
            paragraphs=[_c("Humans stay in control: agents draft, people approve.", "BC-1")],
        ),
        BriefSection(
            heading="Who it is for",
            paragraphs=[_c(f"Stargo serves {_lower(claims['BC-2'])}", "BC-2")],
        ),
    ]
    for proof in proofs:
        sections.insert(1, BriefSection(heading="Results from a pilot",
                                        paragraphs=[_c(claims[proof], proof)]))  # fmt: skip
    faq = [
        FaqItem(
            question=gap.prompt[0].upper() + gap.prompt[1:] + "?", answer=[_c(lead, product_id)]
        ),
        FaqItem(
            question="Does a person approve the output?",
            answer=[_c("Yes. Agents draft, people approve.", "BC-1")],
        ),
        FaqItem(
            question="Which companies is Stargo built for?", answer=[_c(claims["BC-2"], "BC-2")]
        ),
    ]
    return ContentBriefDraft(
        title=gap.prompt[0].upper() + gap.prompt[1:],
        direct_answer=_c(direct, *refs),
        sections=sections,
        faq=faq,
        schema_org_type="Article",
    )


def assemble(
    draft: ContentBriefDraft,
    *,
    prompt_id: str,
    mode: BriefMode,
    model: str | None,
    claims: dict[str, str],
    competitors: list[str],
    generated_at: datetime,
    note: str | None = None,
) -> ContentBrief:
    """Run the claim validator and package the brief with its flags."""
    flags = validate_brief(draft, claims, competitors)
    if note:
        flags.insert(0, ValidatorFlag(location="generator", rule=note, severity="warn", text=""))
    return ContentBrief(
        prompt_id=prompt_id,
        draft=draft,
        mode=mode,
        model=model,
        flags=flags,
        publishable=publishable(flags),
        generated_at=generated_at,
    )
