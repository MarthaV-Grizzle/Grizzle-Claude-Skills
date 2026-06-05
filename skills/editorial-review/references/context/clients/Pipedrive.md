# Pipedrive — Client-Specific Review Notes

This file captures confirmed pitfalls, capitalisation rules, and fact-check guardrails
from past Pipedrive reviews. Load alongside the ClickUp guidelines at Step 2e.

---

## Tone of Voice pitfalls

### Informal vocabulary (confirmed offenders)
Writers regularly drift into casual language that sits below Pipedrive's
professional-casual register. Run a deliberate word-level scan — this is easy to miss
on a general read-through. Flag any of the following as **FAIL (CL-03)**:

- **Colloquial intensifiers / quantifiers:** "tons of", "a lot of", "loads of"
- **Informal verbs in a professional context:** "pester", "bug", "hassle", "nag"
- **Casual transitions explicitly banned in Pipedrive TOV guidelines:**
  "Spoiler alert:", "And hey,", "Well,", "kick things off",
  "No surprises here", "Remember what we just said", "That actually leads us to"

*Confirmed examples from PIPEBLOG1106 (June 2026):* "pester" in key takeaways;
"tons of" in body text. Both passed a general CL-03 read-through and were only
caught by the editor.

### Tentative language on definitive product claims
Pipedrive's "be positive, lead with the do" principle applies to how CRM capabilities
are described. Overuse of "can", "could", "might" when a benefit is known and certain
reads as weak and undermines the article's authority.

- ❌ "CRMs can help you personalise emails…"
- ✅ "CRMs help you personalise emails…"

Flag patterns where a section consistently hedges definitive product benefits with
"can/could/might" rather than stating them directly. Cite the "Be positive / lead
with the do" TOV guideline.

---

## FAQ competitive differentiation

When a FAQ answer names Salesforce, HubSpot, Zoho, or other CRM competitors, it
**must** include Pipedrive's competitive differentiation — not just list alternatives
neutrally.

Flag as **FAIL (CL-04 / Brief alignment)** if competitors are named in FAQs without
any differentiation argument.

*Confirmed gap: PIPEBLOG1106 (June 2026) — FAQ answer listed Salesforce, HubSpot,
and Zoho with no Pipedrive differentiation.*

---

## Fact-check guardrails

### Twilio Segment ≠ CRM
Twilio Segment is a **customer data platform (CDP)**, not a CRM. Flag as **INACCURATE**
if it is described as or implied to be a CRM.

*Confirmed issue: PIPEBLOG1106 (June 2026)*

### Case studies hosted on third-party platforms
The hosting domain is not necessarily the product being used. Always verify what the
featured customer was actually using — do not accept "the case study is on [vendor].com"
as verification.

---

## Company acquisition awareness

- **Drift** → acquired by Salesloft (February 2024). Update to "Drift (now part of
  Salesloft)" or swap the example.

Check CRM-adjacent vendors (sales engagement, conversational marketing, revenue
intelligence) for similar M&A issues.

---

## Editor-confirmed rules (PIPEBLOG1103, June 2026)

### Clearscope — competitor name exclusion
Competitor CRM brand names in the Clearscope unused terms list can be excluded from
the A++ target. Do not flag them as missed keyword opportunities.

### Nofollow comment scope
The nofollow comment must wrap the **complete anchor text phrase**, not a single word.
Anchor text should be 3–5 words — flag one-word and 5+ word anchors.

### Image sources (separate from alt text)
Images require two things:
1. **Alt text** — `[Keyword][Pipedrive][one to two words to describe shot]`, as a comment
2. **Source comment** — separate comment crediting/linking the image source

These are distinct. A passing alt text check does not cover the source requirement.

### One-sentence paragraph openers
Pipedrive editors prefer one-line / one-sentence openers throughout — not just in the
intro. Flag multi-clause opening paragraphs in body sections.

---

## Confirmed case study stats (verified June 2026)

| Case study | Confirmed stat | Source |
|---|---|---|
| Expanish | Team of 3, ~600 web leads/month, conversion 15%→30% | pipedrive.com/en/case-studies/expanish-case-study |
| Marmelada Market | Sales process time cut >50%; productivity +20% | pipedrive.com/en/case-studies/marmelada-case-study |

---

## Pricing notes (June 2026)

- Plan names: **Lite, Growth, Premium, Ultimate**
- Pricing page defaults to EUR — verify USD on a US-localised render
- AI notifications (e.g. "Next best actions") are **Premium plan and above only**

---

## Standing patterns to watch

- Oxford commas recurring — check programmatically
- Stats attributed by name but not hyperlinked — verify all stat hyperlinks
- UK region URLs (e.g. klaviyo.com/uk) — replace with global/US versions
- Metadata fields (slug, author, secondary KW checklist) left as placeholders
- FAQ section goes **after** Final thoughts (updated 5/5/26)
