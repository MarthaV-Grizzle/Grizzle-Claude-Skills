---
name: editorial-review
description: |
  Run a comprehensive editorial review on a draft blog article for any client. This skill cross-references the article against a universal editorial checklist, client-specific content guidelines from ClickUp, the client's "Top reminders and feedback" page, and verifies factual claims (product features, pricing, competitor info) against live product pages. Outputs a structured feedback report to Google Drive.

  MANDATORY TRIGGERS: Use this skill whenever the user mentions "editorial review", "review this draft", "review this article", "content review", "edit check", "checklist review", or provides a draft article and asks for editorial feedback. Also trigger when the user mentions checking an article against client guidelines, verifying product claims in content, or running a QA pass on writer output. If someone pastes or uploads a blog article and mentions a client name, this skill is almost certainly what they need.
---

# Editorial Review Skill

**Version: 2.4** — *When updating this skill, always increment the version (2.3, 2.4, …) and update this line so we know which canonical version we're working from. Do not duplicate this skill into multiple folders — the source of truth is `~/.claude/skills/editorial-review/`.*

You are performing an editorial review of a draft blog article. This is a structured, multi-step process that cross-references the article against three sources of truth: a universal editorial checklist, client-specific content guidelines, and recent client feedback. You also verify factual claims against live sources.

The output is a report document with actionable feedback for the writer, organized by section and checklist item. Every piece of feedback must be traceable to a specific rule or source.

## Before you begin

Read these reference files in the skill directory to understand the review criteria and subagent instructions:

- `references/checklist.md` — The 16-item universal checklist (CL-01 through CL-16)
- `references/agents/checklist_reviewer.md` — Instructions for checklist evaluation
- `references/agents/fact_checker.md` — Instructions for fact-checking claims
- `references/agents/qa_verifier.md` — Instructions for QA verification
- `references/agents/final_qa.md` — Instructions for final QA before output

## Step 0: Gather inputs

You need THREE things from the user before starting:
1. **The draft article** — A Google Doc link, uploaded file, or pasted text
2. **The article brief** — A separate Google Doc link containing the brief the writer was given. This is essential for checking whether the writer followed the brief.
3. **The client name** — Which client this article is for

If the user hasn't provided all three, ask for them. Do NOT proceed without the brief — the checklist evaluates alignment with the brief, and reviewing without it would produce incomplete or inaccurate feedback.

The client name must match a folder in the ClickUp Delivery space (e.g., "Pipedrive", "Tipalti", "Airalo", "Weglot", "HiringBranch", "Smart Panda Labs", "BearingPoint").

## Step 1: Preprocess the article (Python — saves tokens)

Save the article text to a temporary file, then run the preprocessing script:

```bash
python <skill-path>/scripts/preprocess_article.py <article_file> <output_dir>
```

This produces four JSON files in the output directory:
- `structured_sections.json` — Article broken into sections with IDs, types, word counts
- `claims_extract.json` — Factual claims needing verification
- `links_extract.json` — All URLs found in the article
- `article_stats.json` — Word counts, structural flags

Read `article_stats.json` first to see if there are any structural flags (missing H1, metadata issues, etc.). These are "free" findings that cost no tokens.

**CRITICAL — .docx table extraction:** Standard python-docx paragraph iteration silently skips all table content. If the article is a .docx file, you MUST explicitly extract table content separately using `doc.tables` and iterate over rows/cells. Metadata fields, checklists, and comparison tables in Grizzle drafts are almost always in tables. Failure to do this will cause hallucinated findings (e.g. "no links", "empty checklist") that will be factually wrong.

**CRITICAL — .docx deep element inspection (REQUIRED before any visual/structural findings):**

Before recording any finding related to screenshots, images, hyperlinks, or checkboxes, you MUST run the following programmatic inspection against the raw docx XML. Paragraph text alone is not sufficient — python-docx silently skips `<w:drawing>`, `<w:hyperlink>` children, and `<w:sdt>` elements when iterating paragraphs normally.

```python
from docx import Document
from lxml import etree

doc = Document(article_file)
body = doc.element.body

# 1. Screenshots / images — check drawing elements, NOT paragraph text
drawings = body.findall('.//{http://schemas.openxmlformats.org/wordprocessingml/2006/main}drawing')
screenshot_count = len(drawings)
# Only flag "no screenshots" if screenshot_count == 0

# 2. Hyperlinks — check element children, NOT paragraph text
# Paragraph text shows the raw URL; the hyperlink element confirms it is clickable
for para in doc.paragraphs:
    for child in para._element:
        tag = child.tag.split('}')[-1] if '}' in child.tag else child.tag
        if tag == 'hyperlink':
            # This paragraph has a clickable hyperlink — not just plain text

# 3. Checkboxes / SEO checklists — check SDT elements
sdt_elements = body.findall('.//{http://schemas.openxmlformats.org/wordprocessingml/2006/main}sdt')
# SDT elements represent structured content including checkboxes
```

Do NOT report "no screenshots" unless `screenshot_count == 0`. Do NOT report "recommended reading not hyperlinked" unless the hyperlink element check confirms no hyperlink child is present in that paragraph. Do NOT report "SEO checklist not ticked" unless you have confirmed via SDT inspection — always cross-check with the user if uncertain, since SDT elements may be rendered differently across Word versions.

## Step 1b: Fetch the brief

The brief is a Google Doc provided by the user. Use WebFetch to read the brief document. The brief contains the original instructions the writer was given — topic, target keywords, structure guidance, audience notes, etc. This is needed for checklist items that assess whether the writer followed their brief.

Save the brief content alongside the preprocessed article data.

## Step 2: Fetch client documents from ClickUp

### 2a. Discover the full page tree

**MANDATORY — do not skip.** Call `clickup_list_document_pages` with `max_page_depth=-1` before fetching any pages, even if you already have page IDs from search results. Search results only surface pages matching your query terms; they will silently miss pages like CMS Components and Structure Preferences that contain critical formatting rules. The full tree is the only reliable way to know what exists.

```
clickup_list_document_pages(document_id="{doc_id}", max_page_depth=-1)
```

Note IDs for: Content Guidelines parent + all sub-pages, Top Reminders and Feedback, Getting Up to Speed, Guideline Development Notes.

### 2b. Fetch the primary pages

Fetch **Content Guidelines** (parent) and **Top Reminders and Feedback** together in one call.

### 2c. Handle empty or inaccessible pages

Apply these rules to every page fetched — including Content Guidelines, Top Reminders, and any sub-pages:

**If a page is empty or stub** (i.e. `"content": ""`, or fewer than 5 real guideline items, or placeholder text only):
1. Automatically fetch the fallback pages: all **Content Guidelines sub-pages** (Tone of voice, Typography, Preferred spellings, Words to avoid, Structure preferences, Keyword & metadata, Internal links, Images & videos, CMS components, CTAs) plus **Getting Up to Speed** and **Guideline Development Notes**.
2. **PAUSE. Tell the user** which pages were empty and list every page you managed to fetch instead. Ask: "Are these the right sources? Do you have any additional ClickUp pages, PDFs, or external docs I should reference before I proceed?"
3. **Wait for confirmation** before moving to Step 3.

**If any page or document is inaccessible** (fetch error, 404, permissions issue):
1. **PAUSE. Notify the user** immediately, naming the specific page(s) you couldn't access.
2. Ask the user to upload the document directly, or share an alternative link.
3. **Wait** until all accessible or uploaded replacements are in hand, then proceed.

**Even if all pages load successfully:**
- Still **PAUSE** after fetching. List what was accessed and ask: "Please confirm these cover everything, or share any additional resources (e.g. brand guidelines PDF, Notion doc) before I proceed."
- Wait for explicit confirmation before moving to Step 3.

### 2d. What counts as substantive content

Real rules, preferences, or instructions (style rules, tone descriptors, structural requirements). Not substantive: empty strings, "On this page we've included…" placeholders, or fewer than 5 genuine items.

### 2e. Compile guidelines context

Merge all fetched + user-supplied pages into `guidelines_context`. Key things to extract: tone of voice, typography/style rules, structural requirements (ToC, metadata), preferred spellings and words to avoid, internal linking minimums, CTA rules, Top Reminders.

### 2f. Classify pages as citable / non-citable (Python — prevents phantom citations)

Immediately after fetching, run the page classifier. This is the most important anti-hallucination step in the pipeline: it stops the reviewer from later citing rules "from" a guideline page that is actually empty or a template stub.

1. Write every fetched page to a JSON array: `[{page_id, page_title, content, parent_title}, ...]`, save as `pages_input.json`.
2. Run:
   ```bash
   python <skill-path>/scripts/classify_guideline_pages.py pages_input.json guideline_pages_index.json
   ```
3. The output is a per-page index with `"citable": true | false`. Pages marked `"citable": false` cannot be cited as sources of client rules later in the review.

A page is non-citable if any of these apply:
- `content` is empty or whitespace only
- The page contains only placeholder/intro text (e.g. "On this page we've included…")
- Fewer than 5 substantive guideline items

**The checklist reviewer and QA verifier both consult this index.** Any FAIL that cites a non-citable page is a phantom citation and will be removed in Step 5. This is the deterministic guard against inventing a rule from an empty template page (e.g. citing the client's "Words to Avoid" list when that ClickUp page is actually empty).

If the script flags more than 3 pages as non-citable, PAUSE and ask the editor whether the client has additional guideline docs the ClickUp pages don't cover (e.g. a PDF brand book, a Notion doc). Empty ClickUp pages are normal for newer clients and mean those rules haven't been written down yet — not that you should invent them.

### CRITICAL: Never proceed without guidelines

If all pages are empty AND the user provides no alternative sources, STOP. Do not generate client-specific feedback without a source of truth.

## Step 3: Checklist review (section by section)

This is where most of the editorial feedback comes from. Read `references/agents/checklist_reviewer.md` for the full instructions.

**Token efficiency strategy:** Do NOT send the entire article plus entire checklist in one call. Instead, process sections in batches:

1. Read `structured_sections.json`
2. Group sections by type (see the routing table in `references/agents/checklist_reviewer.md`)
3. For each section, evaluate only the applicable checklist items
4. Include the client guidelines, feedback content, AND `guideline_pages_index.json` alongside each section
5. **Before citing any client rule, check `guideline_pages_index.json`.** If the page you would cite is non-citable (`"citable": false`), either reframe the finding as "Editor judgement — not grounded in {client}'s explicit guidelines" / "Article brief", or downgrade to needs_review. Do not cite a non-citable page as the source of a client rule.

For each section, produce a JSON array of checklist results (pass/fail/needs_review) following the format in the checklist reviewer instructions.

**Important:** Some checklist items are article-level, not section-level. After completing all section reviews, do a single pass for:
- CL-05 (Links Quality) — Use `links_extract.json` for this
- CL-11 (Clearscope) — Check if the article mentions a Clearscope score or if there's a reference
- CL-12 (Internal Links) — Use `links_extract.json` plus client guidelines to identify missing key links
- CL-15 (Content Design) — Assess ONLY using the programmatic screenshot count from Step 1. Do not infer from paragraph text. "No screenshots" is only valid if screenshot_count == 0.

**Secondary keyword verification (article-level — do this during CL-11):**

Run a programmatic check of secondary keyword coverage against the FULL article text including tables and all sections:

```python
from docx import Document

doc = Document(article_file)
all_text_parts = []
for para in doc.paragraphs:
    all_text_parts.append(para.text)
for table in doc.tables:
    for row in table.rows:
        for cell in row.cells:
            for para in cell.paragraphs:
                all_text_parts.append(para.text)

full_text = "\n".join(all_text_parts).lower()

for kw in secondary_keywords:
    count = full_text.count(kw.lower())
    # If count > 0, keyword is present. Then check WHERE it appears:
    # If it only appears in the keyword checklist header block (first ~10 paragraphs),
    # that may not count as natural body integration. Check paragraph index.
    for i, part in enumerate(all_text_parts):
        if kw.lower() in part.lower() and i > 10:
            print(f"'{kw}' confirmed in body text at paragraph {i}: {part[:100]}")
```

Report each keyword as confirmed only if it appears in body text (not only in the keyword checklist block at the top of the article). If a keyword appears only in the keyword list, flag it for writer to confirm body integration.

Save all editorial checklist feedback to `checklist_feedback.json`.

## Step 3b: Strategic review (article-level)

After completing the section-by-section editorial review, run the Strategic Review (SR-01 through SR-07). This is a separate, lighter-touch evaluation that assesses the article as a whole.

Read the Strategic Review section in `references/agents/checklist_reviewer.md` for the format and approach.

**Key differences from the editorial review:**
- Strategic items are evaluated at the **article level**, not section-by-section. You need the full picture.
- Feedback is **briefer** — a clear pass or fail with a concise explanation. Not the same depth as editorial items.
- **Same accuracy standard applies.** Every fail must cite what specifically in the article caused it. Do not invent strategic concerns.
- SR-02 and SR-04 require cross-referencing client guidelines for positioning and audience context.

**Token efficiency:** Because this is article-level, you should already have the full structured sections in context from Step 3. Do NOT re-read the article. Use the section data you already have, plus the client guidelines already fetched in Step 2. This should be a single, focused pass.

Save strategic review results to `strategic_feedback.json`.

## Step 4: Fact-checking

Read `references/agents/fact_checker.md` for full instructions.

1. Read `claims_extract.json` from preprocessing
2. Group claims by the product/source they reference
3. For each unique source, fetch the relevant page (feature page, pricing page, competitor site) using the URL access strategy below
4. Compare each claim against what the source actually says
5. Produce a verdict for each claim: accurate, inaccurate, outdated, or unverifiable

**URL access strategy (REQUIRED — never skip a claim because a URL failed):**

WebFetch frequently fails on vendor domains because of the egress allowlist. Always attempt fetches in this order, falling back only when the previous step fails:

1. **FireCrawl first** — call `firecrawl_scrape` with the source URL. FireCrawl runs server-side, returns clean markdown of the rendered page, and is not subject to the same allowlist as WebFetch. This should succeed for the vast majority of public vendor pages.
2. **If FireCrawl is unavailable (MCP not connected) or returns an error**, fall back to WebFetch. Retry once on transient failures.
3. **If both FireCrawl and WebFetch fail**, fall back to Claude in Chrome — it runs inside the user's own browser session and bypasses any server-side restrictions:
   ```
   mcp__Claude_in_Chrome__navigate(url="<url>", tabId=<tabId>)
   content = mcp__Claude_in_Chrome__get_page_text(tabId=<tabId>)
   ```
   Reuse a single tabId across all Chrome fetches in the review (call `mcp__Claude_in_Chrome__tabs_context_mcp` with `createIfEmpty: true` once at the start).
4. **If Chrome `get_page_text` fails** ("No semantic content element found and page body is too large"), fall back to the accessibility tree:
   ```
   mcp__Claude_in_Chrome__read_page(tabId=<tabId>, depth=4)
   ```
   The accessibility tree is sufficient for verifying most factual claims.
5. **If Chrome reports "This site is not allowed due to safety restrictions"** (e.g. has happened with stripe.com), do NOT retry and do NOT fall back silently — record the affected claim(s) as **unverifiable — gated content** and ask the user to paste the relevant page content.
6. **If the page requires login, a CAPTCHA, or is a gated download**, mark the claim as **unverifiable — gated content** and note any redirect URL if the destination changed from the original link in the article.

Never mark a claim as unverifiable solely because one tool in the chain failed. There are three independent fetch paths — exhaust them before concluding a source is unreachable.

**CRITICAL — No fact-check verdict may be based on WebSearch snippets alone.**

Any verdict of INACCURATE, OUTDATED, or FLAG must be grounded in the full-page content retrieved via FireCrawl, WebFetch, or Chrome fetch of the specific source URL. WebSearch snippets are not sufficient evidence. The snippet can easily omit the exact wording or context that would either confirm or refute a claim — and "the snippet didn't say X" is not the same as "the page doesn't say X."

Enforcement rules:

- Before writing any INACCURATE/FLAG verdict, confirm you have a successful FireCrawl, WebFetch, or Chrome fetch result for the source URL in context. If not, do not record the verdict — go fetch it.
- If a claim's source URL is not obviously discoverable (no hyperlink in the article, no candidate URL in links_extract.json), do not fabricate a URL. Mark the claim UNVERIFIABLE — WRITER TO CONFIRM SOURCE and move on.
- If FireCrawl, WebFetch, AND Chrome all fail, escalate to the user immediately. State which URL failed and why. Do not silently downgrade to WebSearch. The user can (a) grant a workaround, (b) paste the relevant page content, or (c) accept that those claims will be flagged UNVERIFIABLE rather than INACCURATE.
- Never write a fact-check finding that relies on "the snippet says X" or "the search result mentions Y." If your evidence is a snippet, your verdict ceiling is UNVERIFIABLE.

**Pricing currency check (do this every time pricing is fact-checked):**

Vendor pricing pages frequently localise to the visitor's region. Pipedrive and Asana have been observed showing EUR by default; Zapier shows GBP by default. If the article quotes USD figures and the live page renders in another currency, flag the claim as OUTDATED with a note that the writer needs to verify on a US-localised render (incognito + USD selector). Do not silently transcribe the EUR/GBP number as the USD figure.

**Case-study paraphrase scope check.**

When an article paraphrases a case-study statistic or a vendor/platform capability, a matching number is not sufficient verification. The paraphrase MUST also preserve:

- **Scope of markets/segments.** A stat like "89% boost in Japanese users" cannot be paraphrased as "89% traffic increases in some markets" — the original is one market, the paraphrase implies many. That is a misleading rewrite even if the number is right.
- **Type of metric.** A user-count increase is not a traffic increase. A revenue uplift is not a visitor uplift. A session-length change is not a conversion change. Paraphrases that swap metric families are INACCURATE.
- **Direction of causation.** "Weglot delivered X" and "X after switching to Weglot" are different claims. The stronger (attributional) form must have explicit support in the source.
- **Intent and context.** Product docs that technically permit a use case but are explicitly designed for a different one (e.g., Craft's multisite "is for sites with the same publishing team") must not be paraphrased in a way that omits the intended design. If the source explicitly frames the feature's intent, the article's description must preserve that framing or add a nuance clause.

Verdict rule: If the paraphrase changes scope, metric type, causation, or omits explicit intent from the source, the verdict is INACCURATE or IMPRECISE — even if the underlying number or capability matches. Record the exact wording from the source and the required rewrite in the finding.

**CRITICAL — Listicle articles: ALL tools must be individually fact-checked.**

If the article is a product listicle (reviews or compares multiple tools/products), you MUST fact-check every tool covered — not just the claims flagged by `claims_extract.json`. The preprocessing script only extracts claims that look like statistics or explicit assertions. Feature descriptions, capability claims, and "best for" conclusions for each tool are equally checkable and equally important.

For each tool in the listicle:
1. Identify the correct product website (be careful — some product names share domain names with unrelated sites, e.g. a product called "OfficeSpace" has its software at `officespacesoftware.com`, not `officespace.com` which is a real estate site)
2. Fetch the product feature page (using the URL access strategy above)
3. Cross-check every feature claim in the article against the product's own marketing copy
4. Flag any claim not confirmed: "carbon footprint tracking," "BIM integration," "visitor approvals," and similar specific differentiating claims are common sources of inaccuracy when writers use AI to draft tool descriptions
5. Do NOT accept plausibility as confirmation — a claim must be explicitly present on the product page to be marked confirmed

**Internal-consistency check (listicles):** Listicle drafts often quote one pricing tier in the comparison table at the top and a different tier in the per-tool body section. Compare every tool's table-row pricing against its body-section pricing and flag any divergence as a FAIL — even if both numbers are individually accurate against the live page.

Save all fact-check results to `factcheck_feedback.json`.

**Token efficiency:**
- Skip claims that are clearly opinion or general knowledge
- Batch claims by source URL — fetch once, verify many
- Use FireCrawl first — it returns clean markdown server-side and is the cheapest reliable path. WebFetch is the next-cheapest fallback. Chrome browsing is the most expensive — only escalate to it when both prior tools fail.

## Known Interpretation Pitfalls — Check Before Finalising Any GL Finding

These are confirmed errors that produce false FAILs. Before recording any client-guideline verdict, verify your reading against these patterns.

### "Check for X" in Top Reminders means X is unwanted — not missing

When a client's Top Reminders says **"Check for [rule]! These keep slipping through,"** the intent is to flag unwanted occurrences of that thing — not to require its presence.

**Pipedrive example:** "Check for Oxford commas!" means Pipedrive style **does not use Oxford commas**. The reminder tells the reviewer to catch any that have crept in. Correct response:
- Oxford comma present in article → **FAIL**
- Oxford comma absent throughout → **PASS**

The general pattern: `"Check for X"` → X is banned/unwanted → fail if found; pass if absent. Do not invert this.

### Gated CTA placeholders — `[CTA: title]` is the complete correct format

For Pipedrive (and most Grizzle clients), the fully correct writer deliverable for a gated CTA is:

```
[CTA: Sales automation guide]
```

accompanied by a comment containing **"found here"** text and a URL pointing to an existing live CTA on the blog. **This tag is not an unfilled placeholder** — the CMS team swaps it at publication. The writer's job ends at inserting the tag + comment + URL.

Verdict rules:
- Tag present WITH "found here" comment + URL → **PASS**
- Tag present but comment/URL is missing → **FAIL** (incomplete format)
- No CTA tag anywhere in the draft → **FAIL** (missing required element)

Do not fail an article simply because `[CTA: …]` is not expanded into live HTML — that is intentional and correct.

### Word-split hyperlinks are NOT duplicate links

Word's XML frequently splits a single visible hyperlink across multiple adjacent `<w:hyperlink>` elements that share the same relationship ID. This is a rendering artifact — not an editorial error. **Never flag "duplicate links" without first confirming programmatically that genuine separate links exist.**

Two `<w:hyperlink>` elements pointing to the same URL are a **genuine duplicate** only if they are separated by one or more non-hyperlinked paragraph children containing actual body text. If they are adjacent siblings — or separated only by whitespace-only `<w:r>` runs — they are a single Word-split link and must be treated as **PASS**.

Run this check before recording any duplicate-link finding:

```python
import zipfile
from lxml import etree

WNS = "http://schemas.openxmlformats.org/wordprocessingml/2006/main"
RNS = "http://schemas.openxmlformats.org/officeDocument/2006/relationships"

with zipfile.ZipFile(article_file) as z:
    rels = etree.parse(z.open("word/_rels/document.xml.rels")).getroot()
    rel_map = {r.get("Id"): r.get("Target") for r in rels}
    doc_xml = etree.parse(z.open("word/document.xml")).getroot()

for para in doc_xml.findall(f".//{{{WNS}}}p"):
    children = list(para)
    seen_urls = {}
    for i, child in enumerate(children):
        tag = child.tag.split("}")[-1] if "}" in child.tag else child.tag
        if tag == "hyperlink":
            rid = child.get(f"{{{RNS}}}id")
            url = rel_map.get(rid, "")
            if url in seen_urls:
                prev_i = seen_urls[url]
                between = children[prev_i + 1:i]
                # Only flag if real prose text exists between the two hyperlinks
                has_body_text = any(
                    c.tag.split("}")[-1] == "r" and
                    any(t.text and t.text.strip() for t in c.findall(f".//{{{WNS}}}t"))
                    for c in between
                    if c.tag.split("}")[-1] != "hyperlink"
                )
                if has_body_text:
                    print(f"GENUINE DUPLICATE at para: {url}")
                # else: Word-split run — not a duplicate, do not flag
            seen_urls[url] = i
```

### CMS- or platform-specific articles — verify cited case-study customers run on that platform

For any article whose headline or premise is specific to a CMS, platform, or technology stack (e.g., "How to make your Craft CMS site multilingual", "WordPress e-commerce guide", "Shopify headless best practices"), every case-study customer cited in the body MUST be verified to run on that platform. Writers frequently pull case-study examples from the client's general customer library without checking each customer's tech stack — and citing a WordPress-hosted customer in a Craft-themed article is misleading context, even if the product being promoted works identically on both platforms.

Process (run once per case-study customer named in the article):

1. Identify the customer's own website from the client's customer library page.
2. Fetch the customer's homepage (or a representative page) using the URL access strategy in Step 4 (FireCrawl → WebFetch → Chrome).
3. Look for platform/CMS indicators: footer credits, powered-by badges, view-source markers (`/wp-content/`, `/_next/`, `/craft-cms/`, `cdn.shopify.com`, etc.), explicit mentions in the case-study copy, or common platform-detection signatures.
4. If the customer runs on a different platform than the article targets, record a FLAG verdict: "Case study cited in a {platform}-specific article, but customer runs on {actual platform}. Editor should either (a) add a caveat that the same capability works across platforms, (b) swap the example for a {platform}-hosted customer, or (c) remove the case study."

This rule applies only to articles whose premise is platform-specific. It does not apply to generic articles on multilingual SEO, translation best practices, internationalisation strategy, etc.

### Cross-client rule contamination — every client-specific FAIL needs a direct quote

Rules that recur across multiple clients (e.g., "include a TOC after the intro", "TL;DR block at the top", "use AP title case for H2s", "Oxford comma required", "FAQ section at the bottom") are not automatically applicable to every client. Before recording a FAIL that cites a client-specific structural or stylistic rule, you MUST:

1. Locate the rule in the specific fetched ClickUp pages for the current client (Content Guidelines or sub-page).
2. Include a direct quote from that page in the Finding & Action column of the report.
3. If you cannot produce a direct quote from the current client's pages, the rule is not a FAIL for this client. Downgrade to NEEDS REVIEW with the note "writer/editor to confirm whether <client> applies this rule," or omit the finding entirely.

Cross-contamination is especially common for: Table of Contents requirements, TL;DR blocks, FAQ sections, internal-link minimums, capitalisation conventions, and punctuation conventions (Oxford comma, em-dash spacing). None of these are universal. Even rules that seem "obviously editorial" must be quoted from the current client's guidelines before being cited as a FAIL.

If the same rule pattern recurs across most clients but each with its own quote, that's fine — the requirement is a client-specific quote, not a shared source. The moment you're about to paraphrase the rule from memory or assert it from experience, stop: re-open the current client's fetched pages and search for the rule by keyword.

Client-specific pitfalls (e.g., "Weglot does not require a TOC", "Napta case study stats confirmed accurate") should live in each client's own project instructions in Cowork — not in the shared skill. This keeps the skill fully client-agnostic while still giving each client's reviews the guardrails specific to that client.

### Secondary keywords — accept plural and minor grammatical variants

When verifying secondary keyword coverage, accept plural forms and minor grammatical variants as valid integrations. For example:
- "crm for electrician businesses" satisfies "crm for electrician business"
- "electrician business CRMs" satisfies "electrician business crm"

Only flag a keyword as missing if **no form** of it — singular, plural, with or without articles — appears anywhere in the article body text. Always check full document text (paragraphs + table cells) when running this check.
### External links — verify they exist before flagging nofollow compliance

Before recording any nofollow-related finding, run a domain-level check on all URLs in `links_extract.json` to confirm that external (non-client-domain) links actually exist in the article body. Many client articles link exclusively to the client's own domain and subdomains. If all links are internal to the client's domain, the nofollow requirement is N/A and must not be flagged.

```python
from urllib.parse import urlparse
import json

with open('links_extract.json') as f:
    links = json.load(f)

client_domain = "pipedrive.com"  # replace per client
external = [l for l in links if client_domain not in urlparse(l['url']).netloc]
print(f"External links in body: {len(external)}")
```

Only flag nofollow compliance if external (non-client-domain) links exist in the article body. Links that appear only in the metadata table (e.g., a brief URL) are not body content — nofollow does not apply to them.

### Competitor characterisation — 'best for' and feature claims require live verification

For any article containing a competitor comparison table or listicle, the "best for" positioning and feature descriptions for each competitor MUST be verified against that tool's current live product page — not recalled from training data. Competitor positioning shifts quickly. Two confirmed patterns of error:

- **Audience positioning**: A tool historically associated with enterprises may now actively market to startups or SMBs (or vice versa). Never assume a tool's target audience from its historical reputation — check the live homepage or product page.
- **Product scope expansion**: A tool known for one category (e.g., project management) may have launched a full product in an adjacent category (e.g., dedicated CRM). Always check whether the article's description matches what is actually on the live product page.

Verdict rule: If the article's "best for" or feature description contradicts the tool's own current marketing copy, flag as INACCURATE and cite the live page URL.

**Note:** This is especially relevant for fast-moving tools like monday.com, Notion, Asana, and ClickUp, all of which have expanded significantly into CRM and sales tooling in recent years.

### Setup guide UI navigation — verify against the product's own knowledge base

Step-by-step setup instructions (navigation paths, button labels, menu names) are among the most frequently outdated content in product-focused articles. UI changes with product updates; writers often copy paths from earlier documentation or outdated help articles.

For any article containing specific navigation instructions, check the product's official support or knowledge base to confirm the stated path still exists. The KB is almost always updated to reflect current UI; the article's instructions may reflect an interface from months or years earlier.

Verification process:
1. Identify any explicit navigation path in the article (e.g., "click the ··· More icon", "go to Settings > Integrations")
2. Search the product's help centre for the equivalent current article
3. Compare the documented path against what the article states

Flag any navigation path that does not match the current KB as OUTDATED, citing: the article's stated path, the correct current path, and the KB source URL with its last-updated date.

**Confirmed example (Pipedrive, April 2026):** The "··· More icon on the left-hand sidebar > Import data" path was replaced by "account menu > Tools and apps > Import data > Import from spreadsheet". Articles written before this UI change will have the wrong navigation. Reference: support.pipedrive.com/en/article/importing-data-into-pipedrive-with-spreadsheets


---

## Step 5: QA Verification

Read `references/agents/qa_verifier.md` for full instructions.

This is a critical anti-hallucination step. Review ALL feedback from Steps 3, 3b, and 4:

0. **Phantom citation sweep (do this first).** Load `guideline_pages_index.json` from Step 2f. For every FAIL whose guideline citation references a page marked `"citable": false`, REMOVE the feedback and log it with reason "phantom citation — cited page is empty/template". Exception: if the citation has been reframed as "Editor judgement — not grounded in {client}'s explicit guidelines" or "Article brief", it can stay. This sweep catches the entire class of failures where the reviewer invented a rule from an empty template page.
1. For each editorial checklist FAIL: Verify the guideline citation actually exists in the client guidelines AND that you can produce a direct quote from the fetched ClickUp page that supports it. If no direct quote is available, the FAIL must be downgraded to NEEDS REVIEW or removed — regardless of how intuitive the rule feels or how common it is across other clients. Verify the content excerpt appears in the article. Verify the interpretation is reasonable.
2. **For any finding about screenshots, images, or hyperlinks:** Re-run the programmatic check from Step 1 to confirm. Never accept "no screenshots" or "link not hyperlinked" as a finding without the programmatic element count confirming it. These are the most common sources of false fails.
3. **Check every GL finding against the "Known Interpretation Pitfalls" section above.** In particular: verify that any "Check for X" reminder has been read as X-is-unwanted, and verify that any `[CTA: …]` verdict reflects whether the comment + URL are present, not whether the tag has been expanded.
4. For each strategic review FAIL: Verify the concern is grounded in what the article actually says (or doesn't say). Strategic fails are easier to hallucinate because they're more subjective — be extra skeptical here.
5. For each fact-check INACCURATE/OUTDATED/FLAG: Confirm a successful FireCrawl, WebFetch, or Chrome fetch result for the source URL is in context. If the only evidence is a WebSearch snippet, the verdict must be downgraded to UNVERIFIABLE. Verify the source URL is appropriate. Verify the correction is plausible. Re-fetch the source page if uncertain before finalising the verdict.
6. Remove any feedback that cites non-existent guidelines or misinterprets rules.
7. Downgrade uncertain fails to needs_review.

Save the verified feedback, overwriting the original files, and save QA notes (removals, downgrades) to `final_qa_notes.json`.

## Step 5b: Independent QA subagent (fact-check verification)

After completing Step 5, spawn a general-purpose subagent to independently verify the fact-check findings. This is a deliberate second opinion — the primary reviewer found the claims, the subagent checks the reasoning. It catches mischaracterisations even when the underlying statistic is technically correct, and picks up additional issues the primary pass may have missed.

**When to run:** Always, if the article contains statistics, named research sources, or percentage figures. Skip only if there are zero checkable claims.

**What to pass the subagent:**

Construct a compact briefing (using Python if needed to build it without wasting tokens) containing:
- The article paragraphs that contain each checked claim (not the whole article — just the relevant excerpts, identified by paragraph ID)
- The fact-check verdicts from Step 4
- The source content retrieved for each claim (the relevant passage, not the entire page)

Include this instruction verbatim in the subagent prompt:

> You are independently verifying fact-check findings for an editorial review. For each claim listed:
> (a) Confirm whether the verdict is accurate based on the source content provided.
> (b) Check whether the claim's framing or surrounding context in the article correctly represents what the source says — a statistic can be numerically correct but still mischaracterise the source's meaning.
> (c) Flag any factual issues in the article excerpts that were not caught in the primary review.
> (d) Check for number-style issues: per the style guide, numbers one through ten must be written as words. Flag any instance where a digit is used instead (e.g. "1 in 10" should be "one in ten", "3 days" should be "three days").
> Return your findings as a structured list: one entry per claim checked, plus any new issues found.

**After the subagent returns:**
1. Review its findings against the primary verdicts
2. If it identifies a mischaracterisation or additional issue, add it to the checklist feedback as a NEEDS REVIEW item (do not auto-fail without re-verifying the source yourself if time permits)
3. Update `factcheck_feedback.json` with any corrections

**Token efficiency:** Pass only article excerpts (paragraph-level), not the full article. The subagent needs enough context to evaluate the claim's framing — not the whole piece.

## Step 6: Assemble the report

Assemble the final report as a .docx file using the `docx` skill. The structure and formatting MUST match the canonical report format below exactly — this is not a guideline, it is the locked output spec.

---

### Canonical report format

#### Document header

The document opens with three lines, all styled as body text (not headings):

```
EDITORIAL REVIEW
{Article Title}
Client: {Client Name}  |  Ref: {Task ID}  |  Date: {DD Month YYYY}
```

#### Review Scorecard

A 3-column table immediately below the header:

| {n} FAILS | {n} NEEDS REVIEW | {n} PASSES |
|-----------|-----------------|------------|

Count totals from your final verified feedback across all categories (editorial checklist + strategic review + fact-check).

#### Executive Summary

**Heading:** `Executive Summary` (Heading 2)

Write 3–5 prose paragraphs:
- Para 1: Overall quality verdict and what the article does well at the highest level
- Para 2: Critical issues (FAILs) — name them specifically so the editor knows what's blocking publication
- Para 3: Close with overall publication-readiness

Keep it honest and specific. Do not write generic filler. Editors and writers read this first.

#### What's Working Well

**Heading:** `What's Working Well` (Heading 2)

A bullet list of 3–5 genuine, specific positives about the article. Reference specific sections, features, or execution choices — not vague praise like "well-written." Each bullet should be 1–2 sentences.

#### Section 1: Editorial Checklist Findings

**Heading:** `Section 1: Editorial Checklist Findings` (Heading 2)

Intro line (body text): "Findings are grouped by category. FAIL items require writer action before the draft is ready for publication. NEEDS REVIEW items require editor or client-team input."

Group checklist items into sub-sections by category. Each sub-section is a Heading 3 in the format `1A — {Category Name}`. Use these categories:

- **1A — Structure & Metadata** — Items about ToC, slug, author, metadata, page title, word count
- **1B — Style & Punctuation** — Items about Oxford commas, numbers, capitalisation, typography rules
- **1C — Sources & Statistics** — Items about stat sourcing, hedged language, broken source links
- **1D — Links** — Items about hyperlinks (internal, external, nofollow, broken links)
- **1E — Brief Alignment** — Items about brief completeness, missing sections, missing content
- **1F — Needs Review** — Any NEEDS REVIEW items that don't fit the above categories, or cross-cutting items requiring editor/client input

Only include categories that have at least one finding. Do not include empty categories.

**Table format for each sub-section:**

Each sub-section has its own table with these exact column headers:

| ID / Status | Item | Finding & Action |
|-------------|------|-----------------|

- **ID / Status column**: The checklist reference (e.g., `CL-01`) on the first line, and the verdict (`FAIL`, `NEEDS REVIEW`, or `PASS`) on the second line. Example cell content: `CL-01\nFAIL`
- **Item column**: Short label for the checklist item (e.g., `Table of Contents`, `Oxford comma`, `Slug unfilled`)
- **Finding & Action column**: The full finding first, then a blank line, then `Action: {specific instruction}` for FAILs and NEEDS REVIEWs. For PASSes: just the brief confirmation, no Action line needed.

Do NOT include PASS items unless the pass is worth explicitly noting (e.g., a pass on something that was a previous recurring issue). Omit routine passes entirely to keep the report focused.

#### Section 2: Strategic Review

**Heading:** `Section 2: Strategic Review` (Heading 2)

One table with the same column format as the checklist:

| ID / Status | Item | Finding & Notes |

Include all SR items (SR-01 through SR-07). For passes, include a brief confirmation. For fails, include an Action line.

#### Section 3: Fact-Check Results

**Heading:** `Section 3: Fact-Check Results` (Heading 2)

Opening line: "All pricing claims were verified against live product pages on {date}."

One table:

| ID / Status | Claim | Finding & Action |

- **ID / Status**: `FC-01` + verdict (`ACCURATE`, `OUTDATED?`, `UNVERIFIED`, `FLAG`, `BROKEN LINK`, `MINOR`)
- **Claim**: Short description of the claim checked
- **Finding & Action**: What was found, and for non-ACCURATE verdicts, an Action line

#### Section 4: Standing Issues & Patterns

**Heading:** `Section 4: Standing Issues & Patterns` (Heading 2)

Opening line: "The following patterns are noted across this review for tracking in the client's Top Reminders:"

A bullet list of patterns observed that:
- Appear more than once in this article, OR
- Match a pre-existing pattern from the client's Top Reminders, OR
- Suggest a systemic issue (e.g., writer unfamiliar with a specific guideline)

Close with a one-line attribution: "This review was generated using the Grizzle editorial review pipeline. All findings have been verified against {Client}'s ClickUp content guidelines and live product pages as of {date}."

---

### Important format rules

1. **Never use a flat sequential checklist table.** All checklist items MUST be grouped into the 1A–1F categories above. No single "Editorial Checklist Review" table with CL-01 through CL-n listed sequentially.
2. **Never add a "Priority Action List" section.** Actions belong inside the Finding & Action column of each row, not in a separate summary table at the end.
3. **Status is embedded in the ID cell**, not in a separate Verdict column.
4. **"What's Working Well"** — not "Positives."
5. **Numbered sections** (Section 1:, Section 2:, etc.) for all major sections after the Executive Summary.
6. PASS items are generally omitted from checklist tables unless specifically noteworthy. The tables should show what needs fixing, not everything that was checked.

## Step 7: Final QA

Read `references/agents/final_qa.md` for full instructions.

Before delivering the report, run one final QA pass on the assembled report:

1. Verify every guideline citation in the report text against the actual guidelines. **Re-run the phantom citation sweep using `guideline_pages_index.json`** — if any FAIL still cites a non-citable page, remove or reframe it.
2. Verify every content excerpt quote against the actual article
3. Check that the executive summary accurately reflects the findings
4. Check that positives are genuine and specific, not generic filler
5. Look for hallucination red flags
6. **For any FAIL verdict:** Confirm it is supported by (a) a cited guideline and (b) a specific quote or programmatic finding from the article. Fails without both should be downgraded to NEEDS REVIEW.
7. **Format compliance check:** Confirm the assembled report conforms to the canonical report format defined in Step 6 — scorecard present with accurate counts, 1A–1F sub-section structure, ID/Status cell format, cross-references resolve, no flat sequential checklist table, no separate Priority Action List section.

If the final QA identifies issues, fix them in the report before delivering.

## Step 8: Deliver to Google Drive

Convert the final markdown report to a .docx file and upload to Google Drive. If the Google Drive MCP is not connected, save the .docx to the workspace folder and provide a download link.

The report filename should be: `Editorial Review - {Client Name} - {Article Title} - {Date}.docx`

### Step 8a: Apply table styling (REQUIRED for every report)

Pandoc's default markdown-to-docx conversion builds the report's tables with **no visible borders** (only a single bottom border on each header row). In Word, the tables then render as what looks like plain text blocks — the editor cannot scan findings row by row, and the report loses readability. This applies to every client review, not a specific one.

After generating the .docx, **always** post-process it with the styling script:

```bash
python <skill-path>/scripts/style_report_tables.py "<path to .docx>"
```

This adds, for every table in the report:
- Single-line 0.5pt grey (#808080) borders on all six edges (top / left / bottom / right / insideH / insideV)
- Matching borders on every cell
- #F2F2F2 shading on the header row

The script edits the file in place and is idempotent — safe to re-run. Do not skip this step. Do not try to substitute it with a pandoc `--reference-doc` template unless you have tested that the resulting tables render with visible borders in Word; pandoc's table style mapping is fragile and the post-processing path is reliable.

## Step 9: Present the file (REQUIRED — always the final step)

After saving the report, **always** call `mcp__cowork__present_files` so the report appears as a clickable card in the user's chat. This is required every time — do not skip it even if you have already shared a file link.

```
mcp__cowork__present_files(files=[{"file_path": "<absolute path to the .docx file>"}])
```

This is the last action of every review run. Users cannot reliably access files without it.

## Token budget awareness

The preprocessing script handles the heavy parsing work without using Claude tokens. Here's roughly where tokens go:

- **Step 2 (ClickUp fetch):** ~2-4 tool calls, minimal tokens
- **Step 3 (Checklist review):** The biggest token consumer. Process sections in batches to keep each call focused. A 2000-word article with 10 sections should need roughly 3-5 Claude calls, not 10.
- **Step 4 (Fact-checking):** Depends on number of claims. For listicle articles, budget one fetch (FireCrawl preferred, falling back through WebFetch and Chrome) per tool covered. Typically 5-10 fetches for a 7-tool listicle.
- **Steps 5-7 (QA):** Moderate token use — these only process the feedback, not the whole article.

If the article is very long (3000+ words), consider batching sections in groups of 3-4 rather than one at a time.
