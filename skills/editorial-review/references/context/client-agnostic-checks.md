# Client-Agnostic Supplementary Checks

These eight checks apply to **every review, regardless of client**. Load this file
at the start of Step 3 alongside the client guidelines. Each check maps to an
existing checklist item (CL-06, CL-07, CL-09, CL-16) so findings slot cleanly
into the report's 1A–1F categories.

All checks here were identified as recurring misses during the WEGBLOG013 Weglot
review (May 2026) and are documented in that session's QA audit.

---

## §1 — Brand first-mention (CL-06)

Every named third-party brand or customer makes more sense to the reader when it
arrives with a brief descriptor on first use. Writers and AI-assisted drafts
frequently drop names without context.

**What to check:** On the first appearance of any named brand, SaaS tool, customer
company, or research firm in the article body, confirm a brief descriptor is present.

- Good: "SEO platform SmartKeyword", "resource management software Napta",
  "SaaS analytics firm ChartMogul"
- Flag: "SmartKeyword postponed its multilingual project..." (no descriptor)

Exceptions: household-name brands (Google, Salesforce, etc.), brands where a
descriptor was established earlier in the same section.

Flag as **FAIL (CL-06)** if missing.

---

## §2 — Table cell punctuation (CL-09)

The typography rule about full stops on long bullet items applies equally to table
cells — it's the same principle: complete sentences need closing punctuation.

**What to check:** For every table in the article, inspect cells that contain one or
more complete sentences. The final sentence in the cell must end with a full stop.
Short label cells (a word or short fragment) don't need one.

Flag cells with complete sentences missing a closing full stop as **FAIL (CL-09)**.

---

## §3 — Table cell sentence case (CL-09)

In two-column tables structured as Signal/Explanation, Feature/Description, or
similar label-plus-expansion patterns, the explanation cell reads as a continuation
of its label — so it should start with a lowercase letter, not a capital.

**What to check:** In any label/explanation table, check whether the explanation
cells begin with a capital letter. If the cell begins with a capital (other than a
proper noun), it's likely a case error.

Example (correct):
- Signal: "Strong Domestic Product-Market Fit"
- Explanation: "check for signs of consistent retention..." ← lowercase

Flag as **FAIL (CL-09)** if explanation cells start with an unnecessary capital.

Before flagging, confirm this pattern applies by checking examples in the client's
live blog — some clients do capitalise these cells intentionally.

---

## §4 — Currency format (CL-09)

Currency names written out in full ("Dollars", "Euros", "Pounds") read as informal
and inconsistent in business content. Standard abbreviations are preferred.

**What to check:** Scan body text and tables for written-out currency names used as
labels or amounts. Flag and replace:
- "Dollars" → USD
- "Euros" → EUR
- "Pounds" → GBP
- "Yen" → JPY

Does **not** apply to idiomatic/rhetorical usage ("the dollar cost of...").

Flag as **FAIL (CL-09)** if found.

---

## §5 — Unsourced body claims (CL-07)

CL-07 verifies the accuracy of cited stats — but claims that *should* have a source
and don't are equally risky. A confident-sounding assertion without a link can't be
verified by the editor or the reader.

**What to check:** Scan body paragraphs for sentences that:
- Make a quantified claim about user or customer behaviour
  (e.g. "customers are X more likely to...", "Y% of buyers prefer...")
- State a market trend as established fact with no supporting link

Flag as **NEEDS REVIEW (CL-07)** if a claim of this type has no hyperlinked source.

Do **not** flag: general knowledge, the client's own product claims (covered by
fact-check), or claims attributed to a source that's hyperlinked nearby.

---

## §6 — Brief data requirements (CL-16)

Brief alignment checks usually focus on structure and topics — but briefs often
contain explicit requests to include specific data or statistics that writers miss.

**What to check:** When reviewing the brief, scan for instructions like:
- "cite credible market data"
- "include a stat on..."
- "add data/evidence for..."
- "use [specific] research report"

Then verify whether the writer fulfilled each one. This is a separate check from
structural alignment — it targets explicit evidence requests.

Flag as **FAIL (CL-16)** if an explicit data request in the brief was not addressed.

---

## §7 — Case study source verification (fact-checker)

Customer story pages open with a headline stat box and then continue with a longer
narrative body. Process details, personnel descriptions, and methodology notes
(e.g. "freelance SEO experts", specific hiring criteria, workflow steps) almost
always appear in the narrative — not in the stat box.

**Rule:** Never flag a case study detail as unsupported unless you have read the
complete fetched page and confirmed the detail is absent throughout. Stopping at the
headline stats and concluding "not in source" is a documented cause of false-negative
fact-check findings (confirmed: WEGBLOG013, Napta case study, May 2026).

---

## §8 — Stat paraphrase accuracy (subagent rule)

When the independent QA subagent evaluates a stat paraphrase, it must check all four
dimensions — not just whether the number is right:

1. **Exact figure** — is the number precise, or an approximation that understates
   the actual result? ("exceed 80%" when the stat is 89% is INACCURATE)
2. **Directional qualifiers** — "at least", "up to", "over" must be preserved;
   dropping them converts a floor into an exact claim
3. **Scope** — correct segment, market, and time period?
4. **Two-stat conflation** — if the article merges two separate findings from the
   same source into one sentence, flag INACCURATE even if both underlying numbers
   are individually correct

Both the ON24 figure understatement and the ChartMogul NRR conflation in WEGBLOG013
were caught by applying these four checks. Neither would have been caught by a simple
number-match.
