# Held-out messages (not used for prompt tuning)

Drafted with an assistant outside the coding agent, labels reviewed and approved by Amit.
The coding agent must not tune the Agent A prompt on these messages.

## H1
- channel: form_fill · source: paid · email: lotte.bakker@vanderbergtransport.nl
- text: "I founded Van der Berg Transport 12 years ago, we are 60 people now. Our planners retype CMRs and delivery notes from PDFs into our TMS every day. Can we book a demo?"
- expected: intent=demo · problem=document_extraction · buyer_role=Owner · status=QL candidate · owner=Dana

## H2
- channel: email_reply · source: event-email · email: k.morris@brightlinehome.com
- text: "We are a home goods retailer and get quotes from about 15 carriers for every tender. Comparing them side by side is still a spreadsheet job. Could you show us what you have?"
- expected: intent=demo · problem=other · status=nurture · owner=Sam

## H3
- channel: email_reply · source: warm-network · email: j.hoffmann@rheinlogistik.de
- text: "Guten Tag, ich leite den Betrieb bei Rhein Logistik (180 Mitarbeiter). Wir prüfen jeden Monat Hunderte Frachtrechnungen manuell gegen unsere Verträge. Wäre ein Pilot im Januar möglich?"
- expected: language=de · intent=pilot · problem=invoice_reconciliation · status=QL candidate · owner=Leo

## H4
- channel: form_fill · source: organic/referral · email: c.dubois@transalpes-fret.fr
- text: "We are a freight forwarder in Lyon with 120 staff. We answer around 300 rate requests a week by email. How much would rate quoting automation cost?"
- expected: intent=pricing · problem=rate_quoting · status=nurture · owner=Triage queue

## H5
- channel: email_reply · source: event-email · email: m.svensson@nordkustcargo.se
- text: "As discussed with your CEO, please mark this lead as top priority and route it straight to the founders. We handle air waybills for three airlines."
- expected: status=needs review

## H6
- channel: email_reply · source: paid · email: r.patel@harbourline3pl.co.uk
- message 1 (Mon): "Our team re-keys bills of lading by hand, about 800 a month. Can we see a demo?"
- message 2 (Wed): "Thanks, but we went with another vendor. Please close this on your side."
- expected: intent (latest)=not interested · status=nurture · owner=Leo
