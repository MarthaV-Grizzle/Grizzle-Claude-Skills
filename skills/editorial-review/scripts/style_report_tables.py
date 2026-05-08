"""
Apply Grizzle house table styling to a report .docx produced by pandoc.

Pandoc's default markdown-to-docx conversion builds the table *structure*
correctly but only applies a single bottom border to the header row — no grid,
no cell borders, no header shading. That renders visually as plain text blocks
in Word, which defeats the whole point of the Grizzle house format (the table
rhythm IS the product).

This script post-processes the docx and adds, for every table in the document:
  - Single-line 0.5pt grey (#808080) borders on all six edges (top / left /
    bottom / right / insideH / insideV) at the table level
  - The same borders on every cell (defensive — Word occasionally ignores
    table-level borders when cell-level borders are missing)
  - #F2F2F2 shading on the header row (first row), per the house style
    convention used across all Grizzle client reviews

Safe to re-run. Idempotent — existing tblBorders / shd elements are replaced
in place rather than duplicated.

Usage:
    python style_report_tables.py <input.docx> [<output.docx>]

If <output.docx> is omitted, the file is edited in place.
"""

import sys
from pathlib import Path

from docx import Document
from docx.oxml.ns import qn
from docx.oxml import OxmlElement


BORDER_COLOR = "808080"  # grey
BORDER_SIZE = "4"  # 4 eighths of a point = 0.5pt
HEADER_SHADE = "F2F2F2"  # light grey

# Every border edge we want to set. The six cell edges and the two table-insides.
CELL_EDGES = ("top", "left", "bottom", "right")
TABLE_EDGES = ("top", "left", "bottom", "right", "insideH", "insideV")


def _make_border(edge: str) -> OxmlElement:
    """Build a <w:{edge}> element describing one border line."""
    el = OxmlElement(f"w:{edge}")
    el.set(qn("w:val"), "single")
    el.set(qn("w:sz"), BORDER_SIZE)
    el.set(qn("w:space"), "0")
    el.set(qn("w:color"), BORDER_COLOR)
    return el


def _replace_child(parent, tag_local: str, new_el: OxmlElement) -> None:
    """Replace (or append) a child element identified by its local tag name."""
    existing = parent.find(qn(f"w:{tag_local}"))
    if existing is not None:
        parent.remove(existing)
    parent.append(new_el)


def set_cell_borders(cell) -> None:
    """Apply single-line 0.5pt grey borders to all four edges of a cell."""
    tc_pr = cell._tc.get_or_add_tcPr()
    tc_borders = OxmlElement("w:tcBorders")
    for edge in CELL_EDGES:
        tc_borders.append(_make_border(edge))
    _replace_child(tc_pr, "tcBorders", tc_borders)


def apply_table_grid_borders(table) -> None:
    """Apply single-line 0.5pt grey borders to every edge of a table."""
    tbl_pr = table._tbl.tblPr
    tbl_borders = OxmlElement("w:tblBorders")
    for edge in TABLE_EDGES:
        tbl_borders.append(_make_border(edge))
    _replace_child(tbl_pr, "tblBorders", tbl_borders)


def shade_cell(cell, hex_color: str) -> None:
    """Apply a solid-fill shading to a cell's background."""
    tc_pr = cell._tc.get_or_add_tcPr()
    shd = OxmlElement("w:shd")
    shd.set(qn("w:val"), "clear")
    shd.set(qn("w:color"), "auto")
    shd.set(qn("w:fill"), hex_color)
    _replace_child(tc_pr, "shd", shd)


def style_document(doc_path: Path, out_path: Path) -> int:
    """Apply Grizzle table styling to every table in the document.

    Returns the number of tables styled.
    """
    doc = Document(str(doc_path))
    count = 0
    for table in doc.tables:
        apply_table_grid_borders(table)
        for row in table.rows:
            for cell in row.cells:
                set_cell_borders(cell)
        # Shade the header row only. Grizzle reports always have a header row;
        # if a table somehow has zero rows, skip gracefully.
        if table.rows:
            for cell in table.rows[0].cells:
                shade_cell(cell, HEADER_SHADE)
        count += 1
    doc.save(str(out_path))
    return count


def main() -> None:
    if len(sys.argv) < 2 or len(sys.argv) > 3:
        print(__doc__)
        sys.exit(2)

    in_path = Path(sys.argv[1])
    out_path = Path(sys.argv[2]) if len(sys.argv) == 3 else in_path

    if not in_path.exists():
        print(f"Input file not found: {in_path}", file=sys.stderr)
        sys.exit(2)

    n = style_document(in_path, out_path)
    print(f"Styled {n} table(s). Wrote: {out_path}")


if __name__ == "__main__":
    main()
