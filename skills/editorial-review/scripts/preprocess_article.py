#!/usr/bin/env python3
"""
Preprocesses a draft article to reduce token usage in the Editorial Review skill.

Supports .docx and .md/.txt inputs.
For .docx: extracts paragraphs AND table cells in document order, and reads all
hyperlinks from the relationship map (they are NOT present in paragraph text).

Outputs:
1. structured_sections.json — Article broken into labeled sections with IDs
2. claims_extract.json — Factual claims, product mentions, pricing, competitor refs
3. links_extract.json — All URLs found in the article (including docx hyperlinks)
4. article_stats.json — Word counts, structural flags, table/link counts

Usage:
    python preprocess_article.py <input_file> <output_dir>
"""

import json
import re
import sys
import os
from pathlib import Path

# ── Heading style name → markdown level map ──────────────────────────────────
_HEADING_STYLE_MAP = {
    "title": 1, "heading1": 1, "heading 1": 1,
    "heading2": 2, "heading 2": 2,
    "heading3": 3, "heading 3": 3,
    "heading4": 4, "heading 4": 4,
    "heading5": 5, "heading 5": 5,
    "heading6": 6, "heading 6": 6,
}


def load_docx(path: str) -> tuple[str, list[dict]]:
    """
    Load a .docx file and return:
      - markdown_text: full article as markdown (headings, body paragraphs, table rows)
      - hyperlinks: list of {url, anchor_text} dicts from the relationship map

    IMPORTANT: Iterates doc.element.body children in document order so tables are
    inserted at the correct position in the text (not appended at the end).
    Hyperlinks are extracted from doc.part.rels — they are invisible to paragraph
    text iteration and would be silently lost otherwise.
    """
    from docx import Document
    from docx.oxml.ns import qn

    doc = Document(path)
    lines = []
    table_count = 0

    for block in doc.element.body:
        tag = block.tag.split("}")[-1]

        if tag == "p":
            # Get paragraph style
            style_elem = block.find(".//" + qn("w:pStyle"))
            style_name = (style_elem.get(qn("w:val")) if style_elem is not None else "").lower()
            level = _HEADING_STYLE_MAP.get(style_name, 0)

            para_text = "".join(r.text or "" for r in block.findall(".//" + qn("w:t"))).strip()
            if not para_text:
                continue

            if level:
                lines.append(f"{'#' * level} {para_text}")
            else:
                lines.append(para_text)

        elif tag == "tbl":
            table_count += 1
            lines.append(f"\n[TABLE {table_count}]")
            for row in block.findall(".//" + qn("w:tr")):
                cells = []
                for cell in row.findall(".//" + qn("w:tc")):
                    cell_text = "".join(r.text or "" for r in cell.findall(".//" + qn("w:t"))).strip()
                    cells.append(cell_text)
                row_text = " | ".join(cells)
                if row_text.strip(" |"):
                    lines.append(row_text)
            lines.append(f"[/TABLE {table_count}]\n")

    # Extract hyperlinks from relationship map (NOT available in paragraph text)
    hyperlinks = []
    seen_urls = set()
    for rId, rel in doc.part.rels.items():
        if "hyperlink" in str(rel.reltype).lower():
            url = rel.target_ref
            if url and url not in seen_urls:
                seen_urls.add(url)
                # Try to find anchor text for this rId in the XML
                anchor = ""
                for hl in doc.element.body.iter(qn("w:hyperlink")):
                    if hl.get(qn("r:id")) == rId:
                        anchor = "".join(r.text or "" for r in hl.findall(".//" + qn("w:t")))
                        break
                hyperlinks.append({
                    "url": url,
                    "anchor_text": anchor or None,
                    "type": classify_link(url),
                })

    return "\n".join(lines), hyperlinks, table_count


def parse_sections(text: str) -> list[dict]:
    """Split article into sections by headings. Each section gets a unique ID."""
    lines = text.split("\n")
    sections = []
    current_section = {
        "id": "section-0",
        "heading": "(Preamble / Meta)",
        "heading_level": 0,
        "body_lines": [],
        "line_start": 1,
    }

    heading_pattern = re.compile(r"^(#{1,6})\s+(.*)")

    for i, line in enumerate(lines):
        match = heading_pattern.match(line)
        if match:
            # Close previous section
            current_section["body"] = "\n".join(current_section["body_lines"]).strip()
            current_section["word_count"] = len(current_section["body"].split())
            del current_section["body_lines"]
            if current_section["body"] or current_section["heading_level"] > 0:
                sections.append(current_section)

            level = len(match.group(1))
            heading_text = match.group(2).strip()
            current_section = {
                "id": f"section-{len(sections)}",
                "heading": heading_text,
                "heading_level": level,
                "body_lines": [],
                "line_start": i + 1,
            }
        else:
            current_section["body_lines"].append(line)

    # Close final section
    current_section["body"] = "\n".join(current_section["body_lines"]).strip()
    current_section["word_count"] = len(current_section["body"].split())
    del current_section["body_lines"]
    if current_section["body"] or current_section["heading_level"] > 0:
        sections.append(current_section)

    return sections


def classify_section(section: dict, all_sections: list[dict]) -> str:
    """Classify a section type for checklist routing."""
    heading = section["heading"].lower()
    level = section["heading_level"]
    idx = all_sections.index(section)

    if level == 0:
        return "preamble_meta"
    if level == 1:
        return "title"
    if idx <= 2 and level == 2:
        return "intro"
    if any(kw in heading for kw in ["conclusion", "summary", "final", "wrap", "takeaway", "key point"]):
        return "conclusion"
    if any(kw in heading for kw in ["faq", "frequently asked", "question"]):
        return "faq"
    if any(kw in heading for kw in ["tldr", "tl;dr", "at a glance", "quick summary"]):
        return "tldr"
    return "body"


def extract_claims(sections: list[dict]) -> list[dict]:
    """
    Extract statements that look like factual claims needing verification.
    Uses heuristics to find product features, pricing, stats, comparisons.
    """
    claims = []

    # Patterns that suggest verifiable claims
    pricing_pattern = re.compile(
        r"(\$[\d,]+(?:\.\d{2})?(?:\s*/\s*(?:mo|month|year|yr|user|seat))?|"
        r"(?:free|premium|enterprise|starter|basic|pro|business)\s+(?:plan|tier|pricing))",
        re.IGNORECASE,
    )

    stat_pattern = re.compile(
        r"(\d+(?:\.\d+)?%|\d+(?:,\d{3})+|\d+x\s|"
        r"\d+\+?\s*(?:million|billion|thousand|users|customers|companies|countries|integrations|features))",
        re.IGNORECASE,
    )

    feature_pattern = re.compile(
        r"(?:offers?|provides?|includes?|supports?|enables?|allows?|features?|comes?\s+with|"
        r"has\s+(?:a|an|built-in)|can\s+(?:be\s+used|help|automate|integrate))\s+(.{10,80})",
        re.IGNORECASE,
    )

    comparison_pattern = re.compile(
        r"(?:better\s+than|worse\s+than|compared\s+to|unlike|similar\s+to|"
        r"alternative\s+to|competitor|vs\.?|versus)\s+(\w+)",
        re.IGNORECASE,
    )

    product_name_pattern = re.compile(
        r"(?:called|named|known\s+as|branded\s+as|formerly|now\s+called|rebranded\s+to)\s+([A-Z][\w\s]{2,30})",
    )

    for section in sections:
        sentences = re.split(r"(?<=[.!?])\s+", section["body"])
        for sentence in sentences:
            sentence = sentence.strip()
            if len(sentence) < 15:
                continue

            claim_types = []

            if pricing_pattern.search(sentence):
                claim_types.append("pricing")
            if stat_pattern.search(sentence):
                claim_types.append("statistic")
            if feature_pattern.search(sentence):
                claim_types.append("product_feature")
            if comparison_pattern.search(sentence):
                claim_types.append("competitor_comparison")
            if product_name_pattern.search(sentence):
                claim_types.append("product_naming")

            if claim_types:
                claims.append({
                    "section_id": section["id"],
                    "section_heading": section["heading"],
                    "claim_text": sentence,
                    "claim_types": claim_types,
                    "needs_source_check": True,
                })

    return claims


def extract_links(text: str) -> list[dict]:
    """Extract all URLs and categorize them."""
    url_pattern = re.compile(r"https?://[^\s\)>\]\"']+")
    md_link_pattern = re.compile(r"\[([^\]]+)\]\((https?://[^\)]+)\)")

    links = []
    seen_urls = set()

    # Markdown links first (have anchor text)
    for match in md_link_pattern.finditer(text):
        url = match.group(2)
        if url not in seen_urls:
            seen_urls.add(url)
            links.append({
                "url": url,
                "anchor_text": match.group(1),
                "type": classify_link(url),
            })

    # Plain URLs
    for match in url_pattern.finditer(text):
        url = match.group(0).rstrip(".,;:)")
        if url not in seen_urls:
            seen_urls.add(url)
            links.append({
                "url": url,
                "anchor_text": None,
                "type": classify_link(url),
            })

    return links


def classify_link(url: str) -> str:
    """Classify a link as internal, external-credible, or external-other."""
    # This is a basic heuristic; the skill will need the client domain to classify internal links
    credible_domains = [
        "wikipedia.org", "harvard.edu", "mit.edu", "stanford.edu",
        "gov", ".edu", "gartner.com", "forrester.com", "mckinsey.com",
        "hbr.org", "reuters.com", "bloomberg.com", "statista.com",
        "g2.com", "capterra.com", "trustradius.com",
    ]
    url_lower = url.lower()
    if any(domain in url_lower for domain in credible_domains):
        return "external_credible"
    return "external"


def compute_stats(sections: list[dict], claims: list[dict], links: list[dict]) -> dict:
    """Compute article-level statistics."""
    total_words = sum(s["word_count"] for s in sections)
    has_h1 = any(s["heading_level"] == 1 for s in sections)
    # Check ALL sections (metadata table may live under a Heading1, not in the preamble)
    has_meta = any(
        any(kw in s["body"].lower() for kw in ["meta description", "editorial title", "page title", "slug", "seo"])
        for s in sections
    )
    heading_count = sum(1 for s in sections if s["heading_level"] >= 2)
    short_sections = [s for s in sections if s["word_count"] < 50 and s["heading_level"] >= 2]

    return {
        "total_words": total_words,
        "total_sections": len(sections),
        "heading_count": heading_count,
        "has_h1": has_h1,
        "has_meta_section": has_meta,
        "total_claims_to_verify": len(claims),
        "total_links": len(links),
        "short_sections": [{"id": s["id"], "heading": s["heading"], "words": s["word_count"]} for s in short_sections],
        "structural_flags": build_structural_flags(sections, has_h1, has_meta, short_sections),
    }


def build_structural_flags(sections, has_h1, has_meta, short_sections) -> list[str]:
    """Flag obvious structural issues before Claude even looks at the article."""
    flags = []
    if not has_h1:
        flags.append("MISSING_H1: No H1 heading found")
    if not has_meta:
        flags.append("MISSING_META: No metadata section detected (categories, meta description, SEO box)")
    if len(short_sections) > 0:
        flags.append(f"SHORT_SECTIONS: {len(short_sections)} sections have fewer than 50 words")
    # Check for very long sections (walls of text)
    long_sections = [s for s in sections if s["word_count"] > 500 and s["heading_level"] >= 2]
    if long_sections:
        flags.append(f"LONG_SECTIONS: {len(long_sections)} sections exceed 500 words — may need subheadings or white space")
    return flags


def main():
    if len(sys.argv) < 3:
        print("Usage: python preprocess_article.py <input_file> <output_dir>")
        sys.exit(1)

    input_file = sys.argv[1]
    output_dir = sys.argv[2]

    os.makedirs(output_dir, exist_ok=True)

    # ── Load input — docx or plain text ──────────────────────────────────────
    docx_hyperlinks = []
    table_count = 0
    if input_file.lower().endswith(".docx"):
        text, docx_hyperlinks, table_count = load_docx(input_file)
    else:
        with open(input_file, "r", encoding="utf-8") as f:
            text = f.read()

    # Parse
    sections = parse_sections(text)

    # Classify each section
    for section in sections:
        section["section_type"] = classify_section(section, sections)

    # Extract — merge docx hyperlinks with any plain-text URLs found in the text
    claims = extract_claims(sections)
    text_links = extract_links(text)
    # Merge: docx_hyperlinks take priority (they have anchor text); add any plain-text
    # URLs not already captured
    seen = {h["url"] for h in docx_hyperlinks}
    for lnk in text_links:
        if lnk["url"] not in seen:
            docx_hyperlinks.append(lnk)
            seen.add(lnk["url"])
    links = docx_hyperlinks

    stats = compute_stats(sections, claims, links)
    stats["table_count"] = table_count
    stats["docx_hyperlink_count"] = len(docx_hyperlinks)

    # Write outputs
    with open(os.path.join(output_dir, "structured_sections.json"), "w") as f:
        json.dump(sections, f, indent=2)

    with open(os.path.join(output_dir, "claims_extract.json"), "w") as f:
        json.dump(claims, f, indent=2)

    with open(os.path.join(output_dir, "links_extract.json"), "w") as f:
        json.dump(links, f, indent=2)

    with open(os.path.join(output_dir, "article_stats.json"), "w") as f:
        json.dump(stats, f, indent=2)

    print(f"Preprocessing complete:")
    print(f"  Sections: {len(sections)}")
    print(f"  Claims to verify: {len(claims)}")
    print(f"  Links found: {len(links)}")
    print(f"  Structural flags: {len(stats['structural_flags'])}")
    for flag in stats["structural_flags"]:
        print(f"    - {flag}")


if __name__ == "__main__":
    main()
