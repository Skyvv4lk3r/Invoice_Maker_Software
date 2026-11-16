import base64
from io import BytesIO

from docx import Document
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.oxml import OxmlElement
from docx.oxml.ns import qn
from docx.shared import Mm, Pt, RGBColor
from PIL import Image

from invoice_generator.application.contracts.dto import DraftPdfModel
from invoice_generator.infrastructure.documents.layout import (
    COLUMN_TITLES,
    COLUMN_WEIGHTS,
    effective_layout,
    line_values,
    money,
    party_lines,
)


class WordDraftRenderer:
    def render(self, model: DraftPdfModel) -> bytes:
        layout = effective_layout(model)
        document = Document()
        section = document.sections[0]
        section.page_width, section.page_height = Mm(210), Mm(297)
        section.top_margin = section.bottom_margin = Mm(layout.margin_mm)
        section.left_margin = section.right_margin = Mm(layout.margin_mm)
        font = {"sans": "Calibri", "serif": "Times New Roman", "mono": "Consolas"}[
            layout.font_family
        ]
        normal = document.styles["Normal"]
        normal.font.name, normal.font.size = font, Pt(layout.font_size + 1)
        normal.paragraph_format.space_after = Pt(6)
        for name in ("Title", "Heading 1", "Heading 2"):
            document.styles[name].font.color.rgb = RGBColor(0, 0, 0)
            document.styles[name].font.name = font
        alignment = {
            "left": WD_ALIGN_PARAGRAPH.LEFT,
            "center": WD_ALIGN_PARAGRAPH.CENTER,
            "right": WD_ALIGN_PARAGRAPH.RIGHT,
        }[layout.header_alignment]
        if layout.logo_png:
            paragraph = document.add_paragraph()
            paragraph.alignment = alignment
            raw_logo = base64.b64decode(layout.logo_png)
            with Image.open(BytesIO(raw_logo)) as logo:
                width, height = logo.size
            scale = min(40 / width, 20 / height)
            paragraph.add_run().add_picture(
                BytesIO(raw_logo), width=Mm(width * scale), height=Mm(height * scale)
            )
        title = "DRAFT INVOICE" if model.invoice_number is None else "TAX INVOICE"
        if model.status == "CANCELLED":
            title = "CANCELLED INVOICE"
        document.add_heading(title, 0).alignment = alignment
        document.add_paragraph(
            "For review only. No invoice number allocated."
            if model.invoice_number is None
            else f"Invoice number: {model.invoice_number} • ORIGINAL FOR RECIPIENT"
        )

        def parties():
            table = document.add_table(
                rows=1 if layout.party_layout == "columns" else 2,
                cols=2 if layout.party_layout == "columns" else 1,
            )
            cells = (
                [table.cell(0, 0), table.cell(0, 1)]
                if layout.party_layout == "columns"
                else [table.cell(0, 0), table.cell(1, 0)]
            )
            for cell, label, name, details in (
                (cells[0], "FROM", model.firm_name, model.firm_details),
                (cells[1], "BILL TO", model.customer_name, model.customer_details),
            ):
                cell.paragraphs[0].add_run(label).bold = True
                for line in party_lines(name, details):
                    cell.add_paragraph(line)

        def metadata():
            document.add_paragraph(
                f"Date: {model.invoice_date}    Tax split: {model.tax_mode.replace('_', ' + ')}"
            )
            for label, value in (
                ("Due date", model.due_date),
                ("Reference", model.reference),
                ("Place of supply", model.place_of_supply),
                ("Delivery address", model.shipping_address),
            ):
                if value:
                    document.add_paragraph(f"{label}: {value}")
            if model.invoice_number is not None:
                document.add_paragraph("Reverse charge: No")

        def items():
            table = document.add_table(rows=1, cols=len(layout.columns))
            table.style = "Table Grid"
            borders = OxmlElement("w:tblBorders")
            for edge in ("top", "left", "bottom", "right", "insideH", "insideV"):
                border = OxmlElement("w:" + edge)
                border.set(qn("w:val"), "single")
                border.set(qn("w:sz"), "4")
                border.set(qn("w:color"), "D9D9D9")
                borders.append(border)
            table._tbl.tblPr.append(borders)
            for cell, key in zip(table.rows[0].cells, layout.columns, strict=True):
                cell.text = COLUMN_TITLES[key]
                shading = OxmlElement("w:shd")
                shading.set(qn("w:fill"), layout.accent)
                cell._tc.get_or_add_tcPr().append(shading)
                for run in cell.paragraphs[0].runs:
                    run.font.color.rgb = RGBColor(255, 255, 255)
                    run.font.bold = True
                    run.font.size = Pt(8)
            table.rows[0]._tr.get_or_add_trPr().append(OxmlElement("w:tblHeader"))
            for index, line in enumerate(model.lines):
                values = line_values(line)
                for key, cell in zip(layout.columns, table.add_row().cells, strict=True):
                    cell.text = values[key]
                    shade = OxmlElement("w:shd")
                    shade.set(qn("w:fill"), layout.tint if index % 2 == 0 else "FFFFFF")
                    cell._tc.get_or_add_tcPr().append(shade)
                    for paragraph in cell.paragraphs:
                        paragraph.paragraph_format.space_before = Pt(layout.row_spacing / 2)
                        paragraph.paragraph_format.space_after = Pt(layout.row_spacing / 2)
                        if key != "description":
                            paragraph.alignment = WD_ALIGN_PARAGRAPH.RIGHT
                        for run in paragraph.runs:
                            run.font.size = Pt(layout.font_size)
            table.autofit = False
            widths = [
                (210 - 2 * layout.margin_mm) * COLUMN_WEIGHTS[key] / 178 for key in layout.columns
            ]
            for column, width in zip(table.columns, widths, strict=True):
                column.width = Mm(width)
            for row in table.rows:
                for cell, width in zip(row.cells, widths, strict=True):
                    cell.width = Mm(width)
            document.add_paragraph()

        def totals():
            values = model.totals
            for label, value in (
                ("Taxable amount", values.taxable_paise),
                ("CGST", values.cgst_paise),
                ("SGST", values.sgst_paise),
                ("IGST", values.igst_paise),
                ("TOTAL", values.total_paise),
            ):
                paragraph = document.add_paragraph(f"{label}: INR {money(value)}")
                paragraph.alignment = WD_ALIGN_PARAGRAPH.RIGHT
                if label == "TOTAL":
                    paragraph.runs[0].bold = True
            document.add_paragraph(values.amount_in_words)

        def notes():
            if model.notes and layout.show_notes:
                document.add_heading("Notes", 2)
                document.add_paragraph(model.notes)

        def terms():
            if model.terms and layout.show_terms:
                document.add_heading("Terms and payment details", 2)
                document.add_paragraph(model.terms)

        blocks = {
            "parties": parties,
            "metadata": metadata,
            "items": items,
            "totals": totals,
            "notes": notes,
            "terms": terms,
        }
        for key in layout.section_order:
            blocks[key]()
        if model.signatory and (layout.show_signature or model.invoice_number is not None):
            document.add_paragraph(
                f"For {model.firm_name}\n\n________________________\n"
                f"{model.signatory}\nAuthorised signatory"
            )
        if layout.footer_text:
            document.add_paragraph(layout.footer_text)
        footer = section.footer.paragraphs[0]
        footer.text = (
            "DRAFT • Not an issued tax invoice"
            if model.invoice_number is None
            else f"Invoice {model.invoice_number} • {model.invoice_date} • {model.status}"
        )
        footer.runs[0].font.size = Pt(8)
        document.core_properties.title = "Invoice"
        for root in (document._element, document.styles.element):
            for border in root.xpath(".//w:pBdr"):
                border.getparent().remove(border)
        output = BytesIO()
        document.save(output)
        return output.getvalue()
