"""
Classify ClickUp guideline pages into "citable" (has real rules) vs "empty template"
vs "partial". Writes `guideline_pages_index.json` which the checklist reviewer and
QA verifier consult before citing any rule.

This exists because Claude will otherwise fabricate rules from empty template pages
(an empty "Words to avoid" placeholder becomes a "{client}'s Words to Avoid list"
citation in a FAIL). Catching empty pages deterministically before review runs is
cheaper than catching fabricated citations after review runs. Applies to every
client this skill serves — not specific to one.

Usage:
    python classify_guideline_pages.py <pages_input.json> <output_file>

Input format (one JSON object per ClickUp page, already fetched by Step 2):
    [
        {
            "page_id": "abc123",
            "page_title": "Words to avoid",
            "content": "On this page, we'll include any words or phrases...",
            "parent_title": "Content Guidelines"
        },
        ...
    ]

Output format (`guideline_pages_index.json`):
    {
        "Words to avoid": {
            "page_id": "abc123",
            "status": "empty_template",
            "citable": false,
            "rule_count": 0,
            "reason": "Only placeholder text found; no substantive rules.",
            "snippet": "On this page, we'll include any words..."
        },
        "Preferred spellings": {
            "page_id": "def456",
            "status": "citable",
            "citable": true,
            "rule_count": 7,
            "reason": "7 substantive spelling rules found.",
            "snippet": "e-commerce instead of eCommerce or ecommerce..."
        }
    }
"""

import json
import re
import sys
from pathlib import Path

# Phrases that indicate a ClickUp page is a template/placeholder with no real content.
TEMPLATE_PHRASES = [
    "on this page we'll",
    "on this page we will",
    "on this page, we'll",
    "on this page, we will",
    "we'll include any",
    "add this to the",
    "avoid using these words in the draft",
    "avoid using these words:",
    "any words or phrases the client has asked",
    "this is a placeholder",
    "to be filled",
    "to be added",
    "to be added.]",
    "to be confirmed",
    "tbc",
    "tbd",
    "[placeholder]",
    "[placeholder ",
    "placeholder —",
    "placeholder -",
    "coming soon",
]

# Phrases that look like real rules (imperative or declarative statements about writing).
# Used as a positive signal in borderline cases.
RULE_SIGNAL_PHRASES = [
    "use ",
    "avoid ",
    "don't ",
    "never ",
    "always ",
    "prefer ",
    "spell ",
    "capitalise",
    "capitalize",
    "lowercase",
    "uppercase",
    "should be",
    "must be",
    "instead of",
    "rather than",
]

# Bullet / list markers that typically signal enumerated rules.
LIST_MARKERS_RE = re.compile(r"(?m)^\s*[-*•]\s+|\s*\d+[.)]\s+")


def count_rules(content: str) -> int:
    """Count probable rules in a page. Heuristic but effective for Grizzle ClickUp pages."""
    if not content:
        return 0

    lines = [ln.strip() for ln in content.split("\n") if ln.strip()]
    # Drop lines that are clearly just template placeholder prose
    lines = [
        ln
        for ln in lines
        if not any(p in ln.lower() for p in TEMPLATE_PHRASES)
    ]

    # Count bullet/numbered list items that look like real rules (not just "- TBD")
    # Require the item to be >15 chars AND contain a rule-signal verb OR an "X instead of Y" pattern
    list_items = []
    for ln in lines:
        if not LIST_MARKERS_RE.match(ln):
            continue
        stripped = LIST_MARKERS_RE.sub("", ln, count=1).strip()
        if len(stripped) < 15:
            continue  # Too short to be a real rule
        lower = stripped.lower()
        has_rule_signal = any(p in lower for p in RULE_SIGNAL_PHRASES)
        # "X instead of Y" and "X not Y" are common rule shapes even without imperative verbs
        has_contrast = " instead of " in lower or " not " in lower or " rather than " in lower
        if has_rule_signal or has_contrast:
            list_items.append(ln)

    # Count standalone lines that contain rule-signal phrases
    rule_lines = [
        ln
        for ln in lines
        if not LIST_MARKERS_RE.match(ln)
        and any(p in ln.lower() for p in RULE_SIGNAL_PHRASES)
        and len(ln) > 10
    ]

    return len(list_items) + len(rule_lines)


def classify_page(page: dict) -> dict:
    """Classify a single guideline page. Returns the index entry for this page."""
    title = page.get("page_title") or "Unknown"
    content = (page.get("content") or "").strip()
    page_id = page.get("page_id", "")

    # Empty or near-empty
    if len(content) < 50:
        return {
            "page_id": page_id,
            "status": "empty",
            "citable": False,
            "rule_count": 0,
            "reason": "Page content is empty or near-empty (<50 chars).",
            "snippet": content[:200],
        }

    content_lower = content.lower()
    has_template_phrase = any(p in content_lower for p in TEMPLATE_PHRASES)
    rule_count = count_rules(content)

    # Empty template: has placeholder phrase AND fewer than 3 substantive rules
    if has_template_phrase and rule_count < 3:
        return {
            "page_id": page_id,
            "status": "empty_template",
            "citable": False,
            "rule_count": rule_count,
            "reason": (
                "Page contains only placeholder text "
                f"(template phrase detected; {rule_count} substantive rules)."
            ),
            "snippet": content[:200],
        }

    # Partial: some rules but not many
    if rule_count < 3:
        return {
            "page_id": page_id,
            "status": "partial",
            "citable": False,
            "rule_count": rule_count,
            "reason": (
                f"Only {rule_count} substantive rules found — too thin to cite as a "
                "source of truth. Flag if a FAIL relies on this page."
            ),
            "snippet": content[:200],
        }

    # Citable
    return {
        "page_id": page_id,
        "status": "citable",
        "citable": True,
        "rule_count": rule_count,
        "reason": f"{rule_count} substantive rules found.",
        "snippet": content[:200],
    }


def build_index(pages: list) -> tuple:
    """Build the full index from a list of page dicts.

    Returns (index, warnings). The warnings list flags duplicate page titles —
    otherwise the second occurrence silently overwrites the first in the index.
    """
    index = {}
    warnings = []
    seen_titles = {}
    for page in pages:
        title = page.get("page_title") or "Unknown"
        if title in seen_titles:
            warnings.append(
                f"Duplicate page_title '{title}' — page_ids {seen_titles[title]} "
                f"and {page.get('page_id')}. Later page overwrites earlier in index. "
                "Consider disambiguating titles or keying by parent+title."
            )
        seen_titles[title] = page.get("page_id")
        index[title] = classify_page(page)
    return index, warnings


def main():
    if len(sys.argv) != 3:
        print(__doc__)
        sys.exit(2)

    input_path = Path(sys.argv[1])
    output_path = Path(sys.argv[2])

    with input_path.open("r", encoding="utf-8") as f:
        pages = json.load(f)

    if not isinstance(pages, list):
        print("Input file must be a JSON array of page objects.", file=sys.stderr)
        sys.exit(2)

    index, warnings = build_index(pages)

    with output_path.open("w", encoding="utf-8") as f:
        json.dump(index, f, indent=2, ensure_ascii=False)

    # Human-readable summary to stdout for the operator
    citable = [t for t, e in index.items() if e["citable"]]
    empty = [t for t, e in index.items() if e["status"] == "empty_template"]
    partial = [t for t, e in index.items() if e["status"] == "partial"]
    truly_empty = [t for t, e in index.items() if e["status"] == "empty"]

    print(f"Guideline pages classified: {len(index)} total")
    print(f"  Citable:        {len(citable)}  {sorted(citable)}")
    print(f"  Empty template: {len(empty)}    {sorted(empty)}")
    print(f"  Partial:        {len(partial)}  {sorted(partial)}")
    print(f"  Empty:          {len(truly_empty)}  {sorted(truly_empty)}")
    if warnings:
        print()
        print("Warnings:")
        for w in warnings:
            print(f"  ! {w}")
    print()
    print(f"Index written to: {output_path}")


if __name__ == "__main__":
    main()
