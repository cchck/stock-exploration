"""Add a clickable table of contents to a Word report (edits the file in place).

Each Heading 2 / Heading 3 gets a bookmark; the TOC is a standard Word TOC field whose
entries are internal hyperlinks to those bookmarks (click to jump), with dot leaders and
PAGEREF page numbers. The document is flagged to refresh fields on open, so Word / WPS fill
in the page numbers. Running the script again replaces the previous TOC.

Usage: .venv/bin/python scripts/add_report_toc.py report.docx
"""

from __future__ import annotations

import sys

from docx import Document
from docx.oxml import OxmlElement
from docx.oxml.ns import qn

LEVELS = {"Heading 2": 0, "Heading 3": 1}
MARK = "_TocReport"


def el(tag: str, **attrs) -> OxmlElement:
    e = OxmlElement(tag)
    for k, v in attrs.items():
        e.set(qn(k), str(v))
    return e


def run(text: str | None = None, *, fld: str | None = None, instr: str | None = None, size: float = 10.5,
        bold: bool = False, color: str | None = None) -> OxmlElement:
    r = el("w:r")
    rpr = el("w:rPr")
    rpr.append(el("w:rFonts", **{"w:ascii": "Times New Roman", "w:hAnsi": "Times New Roman", "w:eastAsia": "宋体"}))
    if bold:
        rpr.append(el("w:b"))
    if color:
        rpr.append(el("w:color", **{"w:val": color}))
    rpr.append(el("w:sz", **{"w:val": int(size * 2)}))
    r.append(rpr)
    if fld:
        r.append(el("w:fldChar", **{"w:fldCharType": fld}))
    elif instr:
        t = el("w:instrText", **{"xml:space": "preserve"})
        t.text = instr
        r.append(t)
    elif text == "\t":
        r.append(el("w:tab"))
    elif text is not None:
        t = el("w:t", **{"xml:space": "preserve"})
        t.text = text
        r.append(t)
    return r


def para(left_cm: float, right_tab_twips: int, space_after: float = 3) -> OxmlElement:
    p = el("w:p")
    ppr = el("w:pPr")
    tabs = el("w:tabs")
    tabs.append(el("w:tab", **{"w:val": "right", "w:leader": "dot", "w:pos": right_tab_twips}))
    ppr.append(tabs)
    ppr.append(el("w:spacing", **{"w:after": int(space_after * 20), "w:line": 300, "w:lineRule": "auto"}))
    ppr.append(el("w:ind", **{"w:left": int(left_cm * 567)}))
    p.append(ppr)
    return p


def remove_old(doc) -> None:
    body = doc.element.body
    for p in list(body.iterchildren()):
        if p.get(qn("w:rsidR")) == "00TOC000":
            body.remove(p)
    # drop only our own bookmarks (matched by name, then their ends by id)
    ids = set()
    for b in list(body.iter(qn("w:bookmarkStart"))):
        if (b.get(qn("w:name")) or "").startswith(MARK):
            ids.add(b.get(qn("w:id")))
            b.getparent().remove(b)
    for b in list(body.iter(qn("w:bookmarkEnd"))):
        if b.get(qn("w:id")) in ids:
            b.getparent().remove(b)


def add_toc(path: str) -> None:
    doc = Document(path)
    remove_old(doc)
    sec = doc.sections[0]
    right = int((sec.page_width - sec.left_margin - sec.right_margin) / 635)  # EMU -> twips
    heads = [(p, LEVELS[p.style.name]) for p in doc.paragraphs if p.style.name in LEVELS]
    if not heads:
        raise ValueError("no Heading 2 / Heading 3 paragraphs")
    entries = []
    for k, (p, lvl) in enumerate(heads, 1):
        name = f"{MARK}{k:03d}"
        bid = str(9000 + k)
        p._p.insert(1 if p._p.pPr is not None else 0, el("w:bookmarkStart", **{"w:id": bid, "w:name": name}))
        p._p.append(el("w:bookmarkEnd", **{"w:id": bid}))
        entries.append((p.text.strip(), lvl, name))
    first = heads[0][0]._p
    insert_at = first  # TOC sits between the intro rule and the first chapter
    block = []
    title = para(0, right, space_after=8)
    title.append(run("目　录", size=16, bold=True, color="1F3A5F"))
    block.append(title)
    for idx, (text, lvl, name) in enumerate(entries):
        p = para(0.0 if lvl == 0 else 0.75, right)
        if idx == 0:
            p.append(run(fld="begin"))
            p.append(run(instr=' TOC \\o "2-3" \\h \\z \\u '))
            p.append(run(fld="separate"))
        h = el("w:hyperlink", **{"w:anchor": name, "w:history": 1})
        h.append(run(text, bold=(lvl == 0), size=11 if lvl == 0 else 10.5))
        h.append(run("\t"))
        h.append(run(fld="begin"))
        h.append(run(instr=f" PAGEREF {name} \\h "))
        h.append(run(fld="separate"))
        h.append(run(""))
        h.append(run(fld="end"))
        p.append(h)
        if idx == len(entries) - 1:
            p.append(run(fld="end"))
        block.append(p)
    brk = el("w:p")
    br = el("w:r")
    br.append(el("w:br", **{"w:type": "page"}))
    brk.append(br)
    block.append(brk)
    for p in block:
        p.set(qn("w:rsidR"), "00TOC000")
        insert_at.addprevious(p)
    # refresh fields (page numbers) when the document is opened
    settings = doc.settings.element
    for old in settings.findall(qn("w:updateFields")):
        settings.remove(old)
    settings.append(el("w:updateFields", **{"w:val": "true"}))
    doc.save(path)
    print(f"TOC with {len(entries)} entries -> {path}")


if __name__ == "__main__":
    add_toc(sys.argv[1])
