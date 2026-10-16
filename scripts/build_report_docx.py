"""Build report/replication_report_zh.docx from report/replication_report_zh.md (with the
figures embedded). Handles the Markdown subset the report uses: headings, paragraphs,
block quotes, bulleted and numbered lists (nested by indentation), tables, images,
horizontal rules, fenced code blocks, and inline **bold** / `code`.

Usage: .venv/bin/python scripts/build_report_docx.py
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

from docx import Document
from docx.enum.table import WD_TABLE_ALIGNMENT
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.oxml import OxmlElement
from docx.oxml.ns import qn
from docx.shared import Cm, Pt, RGBColor

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "report" / "replication_report_zh.md"
OUT = ROOT / "report" / "replication_report_zh.docx"

BODY_CN, HEAD_CN, LATIN, MONO = "宋体", "黑体", "Times New Roman", "Menlo"
ACCENT = RGBColor(0x1F, 0x3A, 0x5F)


def set_fonts(run, cn: str = BODY_CN, latin: str = LATIN, size: float | None = None, bold: bool | None = None):
    run.font.name = latin
    rpr = run._element.get_or_add_rPr()
    fonts = rpr.find(qn("w:rFonts"))
    if fonts is None:
        fonts = OxmlElement("w:rFonts")
        rpr.insert(0, fonts)
    for attr in ("w:ascii", "w:hAnsi", "w:cs"):
        fonts.set(qn(attr), latin)
    fonts.set(qn("w:eastAsia"), cn)
    if size:
        run.font.size = Pt(size)
    if bold is not None:
        run.bold = bold


def style_fonts(doc: Document) -> None:
    for name, cn, size, color in (("Normal", BODY_CN, 10.5, None), ("Heading 1", HEAD_CN, 16, ACCENT),
                                  ("Heading 2", HEAD_CN, 13.5, ACCENT), ("Heading 3", HEAD_CN, 12, ACCENT),
                                  ("Title", HEAD_CN, 20, ACCENT)):
        st = doc.styles[name]
        st.font.name = LATIN
        st.font.size = Pt(size)
        if color:
            st.font.color.rgb = color
        rpr = st.element.get_or_add_rPr()
        fonts = rpr.find(qn("w:rFonts"))
        if fonts is None:
            fonts = OxmlElement("w:rFonts")
            rpr.insert(0, fonts)
        for attr in ("w:ascii", "w:hAnsi", "w:cs"):
            fonts.set(qn(attr), LATIN)
        fonts.set(qn("w:eastAsia"), cn)
        for a in ("w:asciiTheme", "w:hAnsiTheme", "w:eastAsiaTheme", "w:cstheme"):
            if fonts.get(qn(a)) is not None:
                del fonts.attrib[qn(a)]
    pf = doc.styles["Normal"].paragraph_format
    pf.space_after = Pt(4)
    pf.line_spacing = 1.25


INLINE = re.compile(r"(\*\*.+?\*\*|`[^`]+`)")


def add_inline(par, text: str, size: float | None = None, bold_all: bool = False, color=None):
    text = text.replace("\\|", "|")
    for part in INLINE.split(text):
        if not part:
            continue
        if part.startswith("**") and part.endswith("**"):
            r = par.add_run(part[2:-2])
            set_fonts(r, size=size, bold=True)
        elif part.startswith("`") and part.endswith("`"):
            r = par.add_run(part[1:-1])
            set_fonts(r, cn=BODY_CN, latin=MONO, size=(size or 10.5) - 1)
        else:
            r = par.add_run(part)
            set_fonts(r, size=size, bold=True if bold_all else None)
        if color is not None:
            r.font.color.rgb = color


def shade(cell, hex_fill: str):
    tcpr = cell._element.get_or_add_tcPr()
    shd = OxmlElement("w:shd")
    shd.set(qn("w:val"), "clear")
    shd.set(qn("w:color"), "auto")
    shd.set(qn("w:fill"), hex_fill)
    tcpr.append(shd)


def add_table(doc, rows: list[list[str]]):
    header, body = rows[0], rows[1:]
    ncol = len(header)
    t = doc.add_table(rows=1 + len(body), cols=ncol)
    t.style = "Table Grid"
    t.alignment = WD_TABLE_ALIGNMENT.CENTER
    tblpr = t._tbl.tblPr
    borders = OxmlElement("w:tblBorders")
    for edge in ("top", "left", "bottom", "right", "insideH", "insideV"):
        e = OxmlElement(f"w:{edge}")
        for k, v in (("w:val", "single"), ("w:sz", "4"), ("w:space", "0"), ("w:color", "A6A6A6")):
            e.set(qn(k), v)
        borders.append(e)
    tblpr.append(borders)
    usable = 16.0  # cm, A4 with 2.5 cm margins
    # first column narrower when it holds labels
    lens = [max(len(r[i]) if i < len(r) else 0 for r in rows) for i in range(ncol)]
    tot = sum(max(l, 4) for l in lens)
    widths = [usable * max(l, 4) / tot for l in lens]
    for i, row in enumerate(rows):
        for j in range(ncol):
            cell = t.cell(i, j)
            cell.width = Cm(widths[j])
            par = cell.paragraphs[0]
            par.paragraph_format.space_after = Pt(0)
            par.paragraph_format.line_spacing = 1.1
            add_inline(par, row[j].strip() if j < len(row) else "", size=9, bold_all=(i == 0))
            if i == 0:
                shade(cell, "DCE6F0")
    doc.add_paragraph().paragraph_format.space_after = Pt(2)


def hr(doc):
    p = doc.add_paragraph()
    ppr = p._p.get_or_add_pPr()
    bdr = OxmlElement("w:pBdr")
    b = OxmlElement("w:bottom")
    for k, v in (("w:val", "single"), ("w:sz", "6"), ("w:space", "1"), ("w:color", "999999")):
        b.set(qn(k), v)
    bdr.append(b)
    ppr.append(bdr)


def list_par(doc, text: str, level: int, marker: str | None):
    """A list item as a paragraph with a hanging indent; marker = number like '1.' or None
    for a bullet (bullet glyph varies by level)."""
    p = doc.add_paragraph()
    pf = p.paragraph_format
    indent = 0.75 + 0.65 * level
    pf.left_indent = Cm(indent)
    pf.first_line_indent = Cm(-0.5)
    pf.space_after = Pt(2)
    glyph = marker or ("•", "◦", "▪")[min(level, 2)]
    r = p.add_run(glyph + " ")
    set_fonts(r)
    add_inline(p, text)
    return p


def build() -> Path:
    lines = SRC.read_text(encoding="utf-8").splitlines()
    doc = Document()
    sec = doc.sections[0]
    sec.page_width, sec.page_height = Cm(21.0), Cm(29.7)
    for side in ("left_margin", "right_margin"):
        setattr(sec, side, Cm(2.5))
    sec.top_margin = sec.bottom_margin = Cm(2.3)
    style_fonts(doc)
    i = 0
    first_h1 = True
    while i < len(lines):
        line = lines[i]
        s = line.rstrip()
        if not s.strip():
            i += 1
            continue
        if s.startswith("```"):
            i += 1
            while i < len(lines) and not lines[i].startswith("```"):
                p = doc.add_paragraph()
                p.paragraph_format.left_indent = Cm(0.75)
                p.paragraph_format.space_after = Pt(0)
                r = p.add_run(lines[i])
                set_fonts(r, latin=MONO, size=9)
                i += 1
            i += 1
            continue
        if s.strip() == "---":
            hr(doc)
            i += 1
            continue
        m = re.match(r"^(#{1,3})\s+(.*)", s)
        if m:
            level = len(m.group(1))
            if level == 1 and first_h1:
                p = doc.add_paragraph(style="Title")
                add_inline(p, m.group(2))
                p.alignment = WD_ALIGN_PARAGRAPH.CENTER
                first_h1 = False
            else:
                p = doc.add_heading(level=level)
                add_inline(p, m.group(2), color=ACCENT)
                for r in p.runs:
                    set_fonts(r, cn=HEAD_CN)
            i += 1
            continue
        m = re.match(r"^!\[(.*?)\]\((.*?)\)", s.strip())
        if m:
            img = (SRC.parent / m.group(2)).resolve()
            if not img.exists():
                raise FileNotFoundError(img)
            p = doc.add_paragraph()
            p.alignment = WD_ALIGN_PARAGRAPH.CENTER
            p.add_run().add_picture(str(img), width=Cm(14.5))
            cap = doc.add_paragraph()
            cap.alignment = WD_ALIGN_PARAGRAPH.CENTER
            add_inline(cap, m.group(1), size=9, color=RGBColor(0x55, 0x55, 0x55))
            i += 1
            continue
        if s.startswith("|"):
            rows = []
            while i < len(lines) and lines[i].startswith("|"):
                cells = [c for c in re.split(r"(?<!\\)\|", lines[i].strip())[1:-1]]
                if not all(re.fullmatch(r"\s*:?-{2,}:?\s*", c) for c in cells):
                    rows.append(cells)
                i += 1
            add_table(doc, rows)
            continue
        if s.startswith(">"):
            while i < len(lines) and lines[i].startswith(">"):
                body = lines[i][1:].strip()
                if body:
                    if body.startswith("- "):
                        p = list_par(doc, body[2:], 0, None)
                    else:
                        p = doc.add_paragraph()
                        add_inline(p, body)
                    p.paragraph_format.left_indent = Cm(0.9 if body.startswith("- ") else 0.4)
                    for r in p.runs:
                        r.font.color.rgb = RGBColor(0x44, 0x44, 0x44)
                i += 1
            continue
        m = re.match(r"^(\s*)(-|\d+\.)\s+(.*)", line)
        if m:
            indent = len(m.group(1).expandtabs(4))
            level = 0 if indent < 2 else (1 if indent < 5 else 2)
            marker = None if m.group(2) == "-" else m.group(2)
            text = m.group(3)
            i += 1
            # continuation lines of the same item (indented, not a new item)
            while i < len(lines) and lines[i].strip() and not re.match(r"^\s*(-|\d+\.)\s+", lines[i]) \
                    and lines[i].startswith(" ") and not lines[i].lstrip().startswith(("|", "!", "```")):
                text += lines[i].strip()
                i += 1
            list_par(doc, text, level, marker)
            continue
        # paragraph (join soft-wrapped lines)
        text = s.strip()
        i += 1
        while i < len(lines) and lines[i].strip() and not re.match(r"^(\s*(-|\d+\.)\s|#|\||!|>|```|---)", lines[i]):
            text += lines[i].strip()
            i += 1
        p = doc.add_paragraph()
        add_inline(p, text)
    doc.core_properties.title = "用 CSMAR 复现三篇 A 股论文"
    doc.save(OUT)
    return OUT


if __name__ == "__main__":
    print(build())
    sys.exit(0)
