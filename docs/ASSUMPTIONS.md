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

- **Vertical.** Taken only from the CRM, the CRM company record or what the sender states; never inferred from a company name ("Van der Berg Transport" leaves the vertical unknown). An unrecognised vertical is **unknown, never a fail**: C1 fails on vertical only when the vertical clearly maps to a non-ICP category (software vendor, consulting, education, investor, marketing/advertising agency, recruiting). Otherwise C1 is unknown, so the lead is `nurture` with its owner (or `QL candidate` once accepted), never disqualified. Losing a real lead to a vocabulary gap is the worst outcome. ICP synonyms map to their vertical: logistics / logistics provider / logistics company / 3PL → 3pl; freight company / forwarding / Spedition → freight-forwarder; shipping company → carrier; transport / haulage company → trucking; cargo handling → ground-handling; customs agency → customs-broker. A non-ICP word wins over an ICP word ("logistics software" is a software vendor). A stated freight buyer (retailer, manufacturer, wholesaler, distributor, importer/exporter, e-commerce) maps to `shipper` (QLS C1 "shippers with material freight spend"); the freight spend stays unverified.

## Identity and hygiene

- **D16 — Several messages from one person (revised).** Only successfully analysed messages without an instruction attempt are evidence. Conditions use the union of their evidence, except interest (C4), which follows the latest stance among them: a later "not interested" overrides earlier interest, and a later positive message overrides an earlier "not interested". A message whose analysis failed, or that contains an instruction attempt (layer 1 or Agent A), adds no evidence and removes none: it sets a visible "needs review" flag on the lead (reason and message id, in the queue, the lead page and the KPI caveats). The lead's status, owner, score and QL gate come from the usable messages only. If no message is usable, the status is `needs review`, routed on CRM facts only. An unsubscribe overrides everything only when it comes from a usable message. Auto-reply excludes only if every usable message is an auto-reply. Why: the KPI must change only through sales decisions dated in the week, and message content must not change the result, so a garbage reply or an injection from an accepted person cannot take them out of the count.
- **D5b — Company facts by domain.** Company facts (employees, vertical, country) may come from the CRM company record via the normalized domain, labelled "from CRM company record". Sources are never inherited.
- Domain normalization uses a small built-in list of multi-part suffixes (`co.uk`, `com.sg`, `co.il`, …) instead of the full Public Suffix List, to avoid a network-fetched dependency.
- A role mailbox (e.g. `ops@company`) is a person of its own; it is never merged with a named colleague at the same company.

## Routing

- **D4 — Owners for excluded / suppressed leads.** No owner, except investor → Founders. A suppression log is kept.
- **D-add — Senders not in the CRM.** Region from the stated country, marked unverified. No country → Triage queue. A country-code email domain (`.nl`, `.de`, `.co.uk`) is never used as a region signal: it is a guess, and unknown stays unknown (QLS §3). A human in the Triage queue decides.
- **Needs-review routing ignores message content.** When a message is flagged (instruction attempt or failed analysis), the owner comes from CRM / company-record facts only, never from facts stated in that message.
- **Outside ICP regions → Triage queue** applies to `nurture` leads whose C1 fails only on region (D17), to `needs review` leads, and to leads whose region is unknown.
- Region mapping: Benelux = NL, BE, LU; Nordics = SE, NO, DK, FI, IS; UK = GB; DACH = DE, AT, CH. APAC outside Singapore routes to Mei but is outside the ICP regions (C1 region fails).

## KPI

- **D2 — Pipeline events** count by their own date for any person who is not an existing customer or a pre-existing open deal (they need not be a QL). Meetings booked = 4.
- **D7 — Reporting window** is the half-open interval [Sun 00:00, Fri 00:00) Asia/Jerusalem.
- **A past week's pack is built only from what was known before the next reporting week began** (Sun 00:00 Asia/Jerusalem; for Oct 4–8 that is Sun 11 Oct 00:00). People, statuses and counts are rebuilt from messages received before that moment (so Friday/Saturday queued inbound such as Marcus still counts) and decisions dated before the week ends. Records outside the week (decisions, pipeline events) are listed under "Not counted" only if dated before that moment, e.g. a Friday meeting (PE-012). Activity after it (a paste, a decision, a flagged message) cannot change numbers, lists or caveats. Consequences for Oct 4–8: SD-010 (Priya, Sun 11 Oct 09:00) is after the cutoff and is not listed; Priya appears instead as a queued QL candidate (IN-017), which explains why she is not counted. Rejecting a QL today does not remove them from their past week.
- **D8 — Several decisions for one person.** The latest decision wins; full history is visible.
- **Decisions belong to a person.** A decision is matched to a person by normalized email or LinkedIn URL (either may be blank, as for inbound). Seed decisions carry their contact email; a UI decision stores the person's email and LinkedIn (whichever exist) and the person id. A LinkedIn-only sender can therefore be accepted and counts as a QL once per person.

## LLM and fallback

- **D6 — No-key mode.** Agent A outputs for the 21 seed inbound are recorded fixtures: captured once from the real LLM, committed, labelled "recorded fixture", regenerated with a script. Pasted messages use the rules-only fallback when there is no key.
- **D11 — Provider.** Groq free tier. The plan chose Groq `llama-3.3-70b-versatile`; Groq retired it (HTTP 404, "model does not exist"), so the app uses Groq `openai/gpt-oss-120b`. The provider decision is unchanged.
- Rationale is a code template built from evidence only. GEO wrong-claim detection is code only.

## AI visibility

- **D10 — Top gap P6** ("alternatives to Laneframe") gets the brief, under BC-5: the competitor name only in the title and FAQ questions.

## AI visibility (GEO)

- **Gap formula (plan §6).** gap = priority × Σ over engines of g(state) × fit; g: owned 0, mentioned without an owned citation 0.5, absent 1, wrong claim 1.5; fit = 1 if a BC-3 product answers the need, else 0. Ties: more competitors present first. P8 (rate benchmarking for shippers) scores 0: no BC-3 product, so it is not a content gap.
- **Owned citation** = host is `stargo.co` or a subdomain. A host that merely contains "stargo" (stargo-shipping.com, stargo-travel.example) is a look-alike and goes to the risk table.
- **A mention by another company named StarGo counts as a mention with a wrong claim** (P5-CHA), not as absent: the engine tells buyers something false about "Stargo".
- **Unknown vendors** not in `known_competitors` (e.g. "ClearDoc Trade" in P4-CHA) are not detected; only the listed competitors are tracked.
- **Brief generation.** The LLM gets the buyer's question and the approved claims library only. Groq's JSON mode sometimes rejects long outputs (`json_validate_failed`); the brief then retries once without JSON mode and parses the reply itself. Schema validation and the claim validator apply either way.
- **Claim validator limits.** It blocks untagged claims, unknown refs, figures not in the cited claims, competitors outside the title / FAQ questions, customer lists and BC-5 category claims; it warns on hype words and on claims sharing no words with their sources. It does not check meaning: a paraphrase that goes slightly beyond its source (e.g. "eliminates manual lookup steps" tagged BC-3a) passes. A human reviews before publishing.

## Reply drafts

- **Same claim rules as the brief (BC-1, BC-4, BC-5, BC-6).** The draft prompt allows only the BC-3 product line for the lead's problem, no outcome promises, and results only by quoting the category's proof points (PP-1 for rate quoting; PP-2, PP-3 for document extraction) with their numbers unchanged. Every LLM draft is checked in code for outcome promises ("eliminate", "guarantee", "100%", "zero errors", "fully automated", and Hebrew equivalents), figures not in an approved proof point (scheduling numbers such as "a 30-minute call" or "10:00" are allowed), competitor names, customer names, BC-5 category claims, hype words and links. A failed check falls back to the template, and the reasons are stored with the draft and shown on the lead page.
- **Language.** The LLM draft is written in the language of the person's latest usable message (Agent A's `language`), with BC facts translated faithfully. The template is English only; when the lead wrote in another language the draft says so in its flags.
