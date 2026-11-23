# Assumptions and decisions

Draft generated from docs/PLAN.md §9 and later clarifications. Amit to edit into final wording.

## Qualification

- **D1 — Tom Becker (C3).** "Benchmarking carrier quotes" is not a listed pain and BC-3 has no product for it. Accepted by sales but not a QL; C3 shown failing. Under D12 he is `nurture`, owner Leo, with a score. QL count = 5.
- **D12 — Accepted but failing C1–C4 (replaces the earlier "accepted → disqualified" rule).** Acceptance never overrides the gate, and an accepted lead uses the same status map as a non-accepted one (D13): fails C1 or C2 → `disqualified`, no owner; fails C3 or C4 → `nurture` with its owner and a score. The decision stays visible as "accepted by <rep>" with the failing condition shown. Its pipeline events stay on record.
- **D13 — Status mapping when not excluded and not all of C1–C4 pass.** C2 fails, or C1 fails on vertical or size → `disqualified`, no owner. C1 fails only on region (D17), C3 or C4 fails, or any condition is unknown → `nurture` with its owner. All four pass → `QL candidate` (or `QL` when accepted).
- **D17 — Outside ICP regions.** If C1 fails only because the region is outside the ICP (vertical and size fit or are unknown) → `nurture`, owner from the QLS §5 routing table, which sends "outside ICP regions" to the Triage queue. If C1 also fails on vertical or size → `disqualified`, no owner. Example: a pasted message from a French freight forwarder → `nurture`, Triage queue. Note: QLS §5 routes "Singapore and APAC" to Mei, so a lead from APAC outside Singapore (e.g. Japan) fails C1 on region but is routed to Mei per that table, not to Triage. Confirmed by Amit.
- **D14 — Accepted with an unknown (none failing).** Not a QL (unknown is not a pass). Stays `QL candidate` with the unknown condition highlighted for the rep. Does not count as a QL.
- **D9 — Wim Peeters.** "Team Lead" is below manager level → C2 fails → `disqualified` (sales also rejected).
- **D5a — Sanne Jansen.** "Not interested now, maybe Q2" → `nurture`.
- **Sales rejection.** A latest decision of `rejected` → `disqualified`, no owner.

## Exclusions

- **D15 — Partnership messages.** Excluded only if the sender is a competitor or vendor: either the CRM marks them (competitor / software-vendor), or Agent A extracts it as a stated fact from the message (e.g. "we build freight software too"). Otherwise a partnership message goes through the normal gate; it will usually fail C4 and become `nurture` with the region owner. Never excluded on intent alone.
- **D3 — Felix Wagner.** No lead status: `needs review` is only for a failed analysis or an instruction attempt (QLS §5) and Felix has no inbound in the data. Not in the lead queue; appears as a CRM contact "accepted 2026-09-24 (earlier week)". PE-002 and PE-009 count as acquisition (deal created after acceptance).
- **Pre-existing deal.** A deal counts as pre-existing when it was created before the person's first inbound and before their first acceptance (QLS §2). Compared by date in Asia/Jerusalem.

- **Interest scale (Agent A).** `explicit_request` (asks for demo / pricing / pilot), `meeting_request` (asks for a call), `soft_positive` (open to a call, "happy to chat"), `none`, `declined`. Any of the first three satisfies C4 ("replies positively to an offer"); a call request is labelled intent `demo`.
- **C3 / C4 when nothing is stated.** No problem stated → C3 `unknown`. A message with no request → C4 `fail` (the evidence exists and shows no ask). C5 with no decision → `unknown`.
- **C2 function.** Marketing, HR, legal and communications roles fail C2 even at manager level (they do not own pricing, operations, procurement, commercial, finance or digital decisions). An owner/founder title needs a company under 200 employees; with size unknown, C2 is `unknown`.

## Identity and hygiene

- **D16 — Several messages from one person.** Conditions use the union of evidence across messages, except interest (C4), which follows the person's latest stance: a later "not interested" overrides earlier interest (C4 fails → nurture), and a later positive message overrides an earlier "not interested". An unsubscribe in any message overrides everything (`suppressed`). An instruction attempt or a failed analysis in any message → `needs review`. Auto-reply excludes only if every message is an auto-reply.
- **D5b — Company facts by domain.** Company facts (employees, vertical, country) may come from the CRM company record via the normalized domain, labelled "from CRM company record". Sources are never inherited.
- Domain normalization uses a small built-in list of multi-part suffixes (`co.uk`, `com.sg`, `co.il`, …) instead of the full Public Suffix List, to avoid a network-fetched dependency.
- A role mailbox (e.g. `ops@company`) is a person of its own; it is never merged with a named colleague at the same company.

## Routing

- **D4 — Owners for excluded / suppressed leads.** No owner, except investor → Founders. A suppression log is kept.
- **D-add — Senders not in the CRM.** Region from the stated country, marked unverified. No country → Triage queue.
- **Needs-review routing ignores message content.** When a message is flagged (instruction attempt or failed analysis), the owner comes from CRM / company-record facts only, never from facts stated in that message.
- **Outside ICP regions → Triage queue** applies to `nurture` leads whose C1 fails only on region (D17), to `needs review` leads, and to leads whose region is unknown.
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
