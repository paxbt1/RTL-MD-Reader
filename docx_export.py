"""Create an editable Word document from the sanitized preview HTML."""

from dataclasses import dataclass, replace
from io import BytesIO

from docx import Document
from docx.enum.table import WD_CELL_VERTICAL_ALIGNMENT
from docx.oxml import OxmlElement
from docx.oxml.ns import qn
from docx.shared import Pt, RGBColor
from lxml import html as lxml_html


GREEN = RGBColor(23, 77, 59)
BODY = RGBColor(41, 54, 46)
LINK = RGBColor(22, 128, 93)
FONT = "Vazirmatn"
BLOCK_TAGS = {"p", "h1", "h2", "h3", "h4", "h5", "h6", "pre", "ul", "ol", "blockquote", "table", "hr", "div"}


@dataclass(frozen=True)
class Context:
    rtl: bool = True
    scale: float = 1.0
    quote: bool = False


def set_bidi(paragraph, rtl):
    ppr = paragraph._p.get_or_add_pPr()
    bidi = ppr.find(qn("w:bidi"))
    if bidi is None:
        bidi = OxmlElement("w:bidi")
        ppr.append(bidi)
    bidi.set(qn("w:val"), "1" if rtl else "0")
    alignment = ppr.find(qn("w:jc"))
    if alignment is None:
        alignment = OxmlElement("w:jc")
        ppr.append(alignment)
    alignment.set(qn("w:val"), "start")


def set_shading(element, fill):
    properties = element._element.get_or_add_pPr() if hasattr(element, "_p") else element._tc.get_or_add_tcPr()
    shading = properties.find(qn("w:shd"))
    if shading is None:
        shading = OxmlElement("w:shd")
        properties.append(shading)
    shading.set(qn("w:fill"), fill)


def set_border(paragraph, side, color, size=8):
    ppr = paragraph._p.get_or_add_pPr()
    borders = ppr.find(qn("w:pBdr"))
    if borders is None:
        borders = OxmlElement("w:pBdr")
        ppr.append(borders)
    border = OxmlElement(f"w:{side}")
    border.set(qn("w:val"), "single")
    border.set(qn("w:sz"), str(size))
    border.set(qn("w:color"), color)
    borders.append(border)


def set_complex_bold(run):
    run.bold = True
    properties = run._r.get_or_add_rPr()
    if properties.find(qn("w:bCs")) is None:
        properties.append(OxmlElement("w:bCs"))


def font_for(run, size, color=BODY, bold=False, italic=False, code=False):
    run.font.name = "DejaVu Sans Mono" if code else FONT
    run.font.size = Pt(size)
    run.font.color.rgb = color
    run.bold = bold
    run.italic = italic
    properties = run._r.get_or_add_rPr()
    fonts = properties.rFonts
    fonts.set(qn("w:cs"), run.font.name)
    fonts.set(qn("w:eastAsia"), run.font.name)
    complex_size = properties.find(qn("w:szCs"))
    if complex_size is None:
        complex_size = OxmlElement("w:szCs")
        properties.append(complex_size)
    complex_size.set(qn("w:val"), str(round(size * 2)))
    if bold:
        set_complex_bold(run)
    if italic:
        complex_italic = OxmlElement("w:iCs")
        properties.append(complex_italic)
    return run


def add_inline(paragraph, element, size, options=None):
    options = options or {}

    def text(value, opts):
        if not value:
            return
        display_value = f"\u2066{value}\u2069" if opts.get("code") else value
        run = font_for(
            paragraph.add_run(display_value), size * (0.83 if opts.get("code") else 1),
            LINK if opts.get("link") else RGBColor(155, 75, 61) if opts.get("code") else BODY,
            opts.get("bold", False), opts.get("italic", False), opts.get("code", False),
        )
        if opts.get("link"):
            run.underline = True
        if opts.get("strike"):
            run.font.strike = True

    text(element.text, options)
    for child in element:
        tag = child.tag.lower() if isinstance(child.tag, str) else ""
        if tag == "br":
            paragraph.add_run().add_break()
        elif tag == "img":
            text(child.get("alt") or "[تصویر]", options)
        elif tag in {"ul", "ol", "table"}:
            pass
        else:
            next_options = dict(options)
            if tag in {"strong", "b"}:
                next_options["bold"] = True
            elif tag in {"em", "i"}:
                next_options["italic"] = True
            elif tag == "del":
                next_options["strike"] = True
            elif tag == "code":
                next_options["code"] = True
            elif tag == "a":
                next_options["link"] = True
            add_inline(paragraph, child, size, next_options)
        text(child.tail, options)


def add_paragraph(container, element, context, base_size, tag="p", prefix=""):
    style = f"Heading {min(int(tag[1]), 6)}" if tag.startswith("h") and tag[1:].isdigit() else "Normal"
    paragraph = container.add_paragraph(style=style)
    set_bidi(paragraph, context.rtl)
    scale = {"h1": 1.85, "h2": 1.42, "h3": 1.18}.get(tag, 1.0)
    size = base_size * context.scale * scale
    paragraph.paragraph_format.line_spacing = 1.6 if tag.startswith("h") else 2.05
    paragraph.paragraph_format.space_after = Pt(size * (0.55 if tag.startswith("h") else 1.1))
    if tag.startswith("h"):
        paragraph.paragraph_format.space_before = Pt(size * 1.2)
        paragraph.paragraph_format.keep_with_next = True
        for run in paragraph.runs:
            run.font.color.rgb = GREEN
        if tag == "h1":
            set_border(paragraph, "bottom", "DFEAE1", 12)
    if context.quote:
        set_shading(paragraph, "F4F9F4")
        set_border(paragraph, "right", "63B38B", 24)
        paragraph.paragraph_format.right_indent = Pt(12)
        paragraph.paragraph_format.left_indent = Pt(12)
    if prefix:
        font_for(paragraph.add_run(prefix), size, GREEN, bold=True)
    add_inline(paragraph, element, size)
    if tag.startswith("h"):
        for run in paragraph.runs:
            set_complex_bold(run)
            run.font.color.rgb = GREEN
    return paragraph


def set_table_borders(table):
    properties = table._tbl.tblPr
    borders = properties.find(qn("w:tblBorders"))
    if borders is None:
        borders = OxmlElement("w:tblBorders")
        properties.append(borders)
    for side in ("top", "left", "bottom", "right", "insideH", "insideV"):
        border = OxmlElement(f"w:{side}")
        border.set(qn("w:val"), "single")
        border.set(qn("w:sz"), "5")
        border.set(qn("w:color"), "DBE7DC")
        borders.append(border)


def set_cell_margin(cell, twips=120):
    properties = cell._tc.get_or_add_tcPr()
    margins = properties.find(qn("w:tcMar"))
    if margins is None:
        margins = OxmlElement("w:tcMar")
        properties.append(margins)
    for side in ("top", "start", "bottom", "end"):
        item = OxmlElement(f"w:{side}")
        item.set(qn("w:w"), str(twips))
        item.set(qn("w:type"), "dxa")
        margins.append(item)


def add_table(document, element, context, base_size, content_width):
    rows = element.xpath("./thead/tr | ./tbody/tr | ./tr | ./tfoot/tr")
    if not rows:
        return
    column_count = max(len(row.xpath("./th | ./td")) for row in rows)
    if not column_count:
        return
    table = document.add_table(rows=len(rows), cols=column_count)
    table.autofit = False
    set_table_borders(table)
    if context.rtl:
        visual = OxmlElement("w:bidiVisual")
        table._tbl.tblPr.append(visual)
    weights = [10] * column_count
    for row in rows:
        for index, cell in enumerate(row.xpath("./th | ./td")):
            weights[index] = max(weights[index], min(len(" ".join(cell.itertext())), 60))
    total = sum(weights)
    widths = [Pt(content_width * weight / total) for weight in weights]
    for index, column in enumerate(table.columns):
        column.width = widths[index]
    for row_index, row in enumerate(rows):
        is_header = row.getparent().tag == "thead" or row_index == 0 and bool(row.xpath("./th"))
        if is_header:
            header = OxmlElement("w:tblHeader")
            header.set(qn("w:val"), "true")
            table.rows[row_index]._tr.get_or_add_trPr().append(header)
        for column_index, source_cell in enumerate(row.xpath("./th | ./td")):
            cell = table.cell(row_index, column_index)
            cell.width = widths[column_index]
            cell.vertical_alignment = WD_CELL_VERTICAL_ALIGNMENT.CENTER
            set_cell_margin(cell)
            if is_header:
                set_shading(cell, "F0F7F1")
            elif row_index % 2 == 0:
                set_shading(cell, "FBFDFB")
            paragraph = cell.paragraphs[0]
            set_bidi(paragraph, context.rtl)
            paragraph.paragraph_format.line_spacing = 1.5
            paragraph.paragraph_format.space_after = Pt(0)
            add_inline(paragraph, source_cell, base_size * context.scale * .92)
            if is_header:
                for run in paragraph.runs:
                    set_complex_bold(run)
                    run.font.color.rgb = GREEN
    document.add_paragraph().paragraph_format.space_after = Pt(3)


def add_blocks(document, parent, context, base_size, content_width, list_depth=0):
    for element in parent:
        tag = element.tag.lower() if isinstance(element.tag, str) else ""
        if tag == "div":
            classes = set((element.get("class") or "").split())
            next_context = context
            if "align-left" in classes:
                next_context = replace(next_context, rtl=False)
            elif "align-right" in classes:
                next_context = replace(next_context, rtl=True)
            for name, factor in (("size-small", .85), ("size-large", 1.25), ("size-xlarge", 1.5)):
                if name in classes:
                    next_context = replace(next_context, scale=next_context.scale * factor)
            add_blocks(document, element, next_context, base_size, content_width, list_depth)
        elif tag in {"p", "h1", "h2", "h3", "h4", "h5", "h6"}:
            add_paragraph(document, element, context, base_size, tag)
        elif tag == "blockquote":
            add_blocks(document, element, replace(context, quote=True), base_size, content_width, list_depth)
        elif tag in {"ul", "ol"}:
            for index, item in enumerate(element.xpath("./li"), 1):
                paragraph = add_paragraph(document, item, context, base_size, prefix="• " if tag == "ul" else f"{index}. ")
                paragraph.paragraph_format.right_indent = Pt(14 * (list_depth + 1)) if context.rtl else Pt(0)
                paragraph.paragraph_format.left_indent = Pt(14 * (list_depth + 1)) if not context.rtl else Pt(0)
                for nested in item:
                    if isinstance(nested.tag, str) and nested.tag.lower() in {"ul", "ol"}:
                        add_blocks(document, item, context, base_size, content_width, list_depth + 1)
                        break
        elif tag == "pre":
            paragraph = document.add_paragraph()
            set_bidi(paragraph, False)
            set_shading(paragraph, "24332B")
            paragraph.paragraph_format.space_before = Pt(10)
            paragraph.paragraph_format.space_after = Pt(12)
            paragraph.paragraph_format.left_indent = Pt(12)
            paragraph.paragraph_format.right_indent = Pt(12)
            paragraph.paragraph_format.line_spacing = 1.7
            font_for(paragraph.add_run("".join(element.itertext()).rstrip("\n")), base_size * context.scale * .83, RGBColor(234, 244, 233), code=True)
        elif tag == "table":
            add_table(document, element, context, base_size, content_width)
        elif tag == "hr":
            paragraph = document.add_paragraph()
            set_border(paragraph, "bottom", "DCE9DF")
        elif tag in BLOCK_TAGS:
            add_blocks(document, element, context, base_size, content_width, list_depth)


def export_docx(markup, zoom=100, width=700):
    zoom = max(70, min(160, int(zoom)))
    width = max(320, min(1600, int(width)))
    base_size = 17 * zoom / 100 * .75
    content_width = width * .75
    document = Document()
    section = document.sections[0]
    section.page_width = Pt(content_width + 36)
    section.page_height = Pt(841.89)
    section.left_margin = Pt(18)
    section.right_margin = Pt(18)
    section.top_margin = Pt(24)
    section.bottom_margin = Pt(24)
    normal = document.styles["Normal"]
    normal.font.name = FONT
    normal.font.size = Pt(base_size)
    normal.font.color.rgb = BODY
    root = lxml_html.fragment_fromstring(markup, create_parent="div")
    add_blocks(document, root, Context(), base_size, content_width)
    output = BytesIO()
    document.save(output)
    return output.getvalue()
