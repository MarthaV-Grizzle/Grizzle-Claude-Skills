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

**Pattern to flag:** "Other CRM systems for email marketing include Salesforce,
HubSpot and Zoho CRM." — names competitors with no differentiation language.

**What to require instead:** A brief, fact-based positioning note explaining why
Pipedrive is the recommended answer (e.g. "Salesforce and HubSpot are more complex
and enterprise-focused; Pipedrive is designed for ease of use by smaller sales
teams"). The differentiation must be research-backed, not asserted.

Flag as **FAIL (CL-04 / Brief alignment)** if competitors are named in FAQs without
any differentiation argument.

*Confirmed gap: PIPEBLOG1106 (June 2026) — FAQ answer listed Salesforce, HubSpot,
and Zoho with no Pipedrive differentiation.*

---

## Fact-check guardrails

### Twilio Segment ≠ CRM
Twilio Segment is a **customer data platform (CDP)**, not a CRM. If an article cites
a case study hosted on `customers.twilio.com` and describes the company as "using
their CRM", that is a factual mischaracterisation — they were using Twilio Segment
or another Twilio communication product.

- Flag as **INACCURATE** if Twilio or Twilio Segment is described as, or implied to
  be, a CRM.
- The underlying case study data may still be valid — the fix is to accurately
  describe what product was used, or remove the CRM framing.

*Confirmed issue: PIPEBLOG1106 (June 2026) — Drift/Twilio Segment case study framed
as "Drift used its CRM".*

### Case studies hosted on third-party platforms
When a case study URL is on a third-party platform (e.g. `customers.twilio.com`,
`customers.salesforce.com`), the hosting company is **not necessarily** the product
being used. Always verify what specific product or service the featured customer was
actually using — it may be the host's product, or a completely different tool.

Writers frequently conflate the hosting domain with the product described. Do not
accept "the case study is on [vendor].com, therefore the company used [vendor's
product]" as verification.

---

## Company acquisition awareness

Confirm the current status of any named third-party company, especially fast-moving
sales tech vendors. Known acquisitions relevant to Pipedrive content:

- **Drift** → acquired by Salesloft (February 2024). Articles referring to "Drift"
  as a standalone platform are factually outdated. Update to "Drift (now part of
  Salesloft)" or swap the example.

Check for similar issues with any company described in the article that operates in
CRM-adjacent categories (sales engagement, conversational marketing, revenue
intelligence). These sectors see frequent M&A.
