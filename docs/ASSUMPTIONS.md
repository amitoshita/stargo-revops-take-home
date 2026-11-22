# Assumptions and decisions

Draft generated from docs/PLAN.md §9 and later clarifications. Amit to edit into final wording.

## Qualification

- **D1 — Tom Becker (C3).** "Benchmarking carrier quotes" is not a listed pain and BC-3 has no product for it. Accepted by sales but not a QL; C3 shown failing. QL count = 5.
- **D12 — Accepted but failing C1–C4.** Status `disqualified`, no owner (literal QLS §5). The decision stays visible as "accepted by <rep>" with the failing condition shown. Its pipeline events stay on record.
- **D13 — Status mapping when not excluded and not all of C1–C4 pass (no acceptance yet).** C1 or C2 fails → `disqualified`, no owner. C3 or C4 fails, or any condition is unknown → `nurture` with the region owner. All four pass → `QL candidate`.
- **D14 — Accepted with an unknown (none failing).** Not a QL (unknown is not a pass). Stays `QL candidate` with the unknown condition highlighted for the rep. Does not count as a QL.
- **D9 — Wim Peeters.** "Team Lead" is below manager level → C2 fails → `disqualified` (sales also rejected).
- **D5a — Sanne Jansen.** "Not interested now, maybe Q2" → `nurture`.
- **Sales rejection.** A latest decision of `rejected` → `disqualified`, no owner.

## Exclusions

- **D15 — Partnership messages.** Excluded only if the sender is a competitor or vendor: either the CRM marks them (competitor / software-vendor), or Agent A extracts it as a stated fact from the message (e.g. "we build freight software too"). Otherwise a partnership message goes through the normal gate; it will usually fail C4 and become `nurture` with the region owner. Never excluded on intent alone.
- **D3 — Felix Wagner.** No lead status: `needs review` is only for a failed analysis or an instruction attempt (QLS §5) and Felix has no inbound in the data. Not in the lead queue; appears as a CRM contact "accepted 2026-09-24 (earlier week)". PE-002 and PE-009 count as acquisition (deal created after acceptance).
- **Pre-existing deal.** A deal counts as pre-existing when it was created before the person's first inbound and before their first acceptance (QLS §2). Compared by date in Asia/Jerusalem.

## Identity and hygiene

- **D16 — Several messages from one person.** Conditions use the union of evidence across messages, except interest (C4), which follows the person's latest stance: a later "not interested" overrides earlier interest (C4 fails → nurture), and a later positive message overrides an earlier "not interested". An unsubscribe in any message overrides everything (`suppressed`). An instruction attempt or a failed analysis in any message → `needs review`. Auto-reply excludes only if every message is an auto-reply.
- **D5b — Company facts by domain.** Company facts (employees, vertical, country) may come from the CRM company record via the normalized domain, labelled "from CRM company record". Sources are never inherited.
- Domain normalization uses a small built-in list of multi-part suffixes (`co.uk`, `com.sg`, `co.il`, …) instead of the full Public Suffix List, to avoid a network-fetched dependency.
- A role mailbox (e.g. `ops@company`) is a person of its own; it is never merged with a named colleague at the same company.

## Routing

- **D4 — Owners for excluded / suppressed leads.** No owner, except investor → Founders. A suppression log is kept.
- **D-add — Senders not in the CRM.** Region from the stated country, marked unverified. No country → Triage queue.
- Region mapping: Benelux = NL, BE, LU; Nordics = SE, NO, DK, FI, IS; UK = GB; DACH = DE, AT, CH. APAC outside Singapore routes to Mei but is outside the ICP regions (C1 region fails).

## KPI

- **D2 — Pipeline events** count by their own date for any person who is not an existing customer or a pre-existing open deal (they need not be a QL). Meetings booked = 4.
- **D7 — Reporting window** is the half-open interval [Sun 00:00, Fri 00:00) Asia/Jerusalem.
- **D8 — Several decisions for one person.** The latest decision wins; full history is visible.

## LLM and fallback

- **D6 — No-key mode.** Agent A outputs for the 21 seed inbound are recorded fixtures: captured once from the real LLM, committed, labelled "recorded fixture", regenerated with a script. Pasted messages use the rules-only fallback when there is no key.
- **D11 — Provider.** Groq free tier, `llama-3.3-70b-versatile`.
- Rationale is a code template built from evidence only. GEO wrong-claim detection is code only.

## AI visibility

- **D10 — Top gap P6** ("alternatives to Laneframe") gets the brief, under BC-5: the competitor name only in the title and FAQ questions.
