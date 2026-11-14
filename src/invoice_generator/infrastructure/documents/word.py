from io import BytesIO

from docx import Document
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.oxml import OxmlElement
from docx.oxml.ns import qn
from docx.shared import Mm, Pt, RGBColor

from invoice_generator.application.contracts.dto import DraftPdfModel
from invoice_generator.infrastructure.documents.layout import money, palette, party_lines


class WordDraftRenderer:
    def render(self, model: DraftPdfModel) -> bytes:
        document = Document()
        section = document.sections[0]
        section.page_width, section.page_height = Mm(210), Mm(297)
        section.top_margin = section.bottom_margin = Mm(18)
        section.left_margin = section.right_margin = Mm(16)
        normal = document.styles["Normal"]
        normal.font.name, normal.font.size = "Calibri", Pt(10)
        normal.paragraph_format.space_after = Pt(6)
        for name in ("Title", "Heading 1", "Heading 2"):
            document.styles[name].font.color.rgb = RGBColor(0, 0, 0)
        ink, _tint = palette(model.template_id)
        heading = document.add_heading("DRAFT INVOICE", 0)
        heading.runs[0].font.color.rgb = RGBColor(0, 0, 0)
        document.add_paragraph("For review only. No invoice number allocated.")
        parties = document.add_table(rows=1, cols=2)
        for cell, label, name, details in (
            (parties.cell(0, 0), "FROM", model.firm_name, model.firm_details),
            (parties.cell(0, 1), "BILL TO", model.customer_name, model.customer_details),
        ):
            cell.paragraphs[0].add_run(label).bold = True
            for line in party_lines(name, details):
                cell.add_paragraph(line)
        split = model.tax_mode.replace("_", " + ")
        document.add_paragraph(f"Date: {model.invoice_date}    Tax split: {split}")
        for label, value in (
            ("Due date", model.due_date),
            ("Reference", model.reference),
            ("Place of supply", model.place_of_supply),
        ):
            if value:
                document.add_paragraph(f"{label}: {value}")
        table = document.add_table(rows=1, cols=6)
        table.style = "Table Grid"
        borders = OxmlElement("w:tblBorders")
        for edge in ("top", "left", "bottom", "right", "insideH", "insideV"):
            border = OxmlElement("w:" + edge)
            border.set(qn("w:val"), "single")
            border.set(qn("w:sz"), "4")
            border.set(qn("w:color"), "D9D9D9")
            borders.append(border)
        table._tbl.tblPr.append(borders)
        headers = ["Item / HSN-SAC", "Qty / unit", "Rate (INR)", "GST %", "Taxable", "Total"]
        for cell, text in zip(table.rows[0].cells, headers, strict=True):
            cell.text = text
            shading = OxmlElement("w:shd")
            shading.set(qn("w:fill"), ink)
            cell._tc.get_or_add_tcPr().append(shading)
            for run in cell.paragraphs[0].runs:
                run.font.color.rgb = RGBColor(255, 255, 255)
                run.font.bold = True
                run.font.size = Pt(8)
        repeated = OxmlElement("w:tblHeader")
        table.rows[0]._tr.get_or_add_trPr().append(repeated)
        for line in model.lines:
            description = line.description
            if line.hsn_sac:
                description += f"\n{line.item_type.title()} • {line.hsn_sac}"
            values = [
                description,
                f"{line.quantity} {line.unit}",
                line.unit_price,
                line.gst_rate,
                money(line.taxable_paise),
                money(line.total_paise),
            ]
            for cell, value in zip(table.add_row().cells, values, strict=True):
                cell.text = value
                for paragraph in cell.paragraphs:
                    for run in paragraph.runs:
                        run.font.size = Pt(9)
        widths = [56, 25, 26, 16, 27, 28]
        table.autofit = False
        for column, width in zip(table.columns, widths, strict=True):
            column.width = Mm(width)
        for row in table.rows:
            for cell, width in zip(row.cells, widths, strict=True):
                cell.width = Mm(width)
        for index, row in enumerate(table.rows[1:]):
            for column, cell in enumerate(row.cells):
                shading = OxmlElement("w:shd")
                shading.set(qn("w:fill"), "F5F7F6" if index % 2 == 0 else "FFFFFF")
                cell._tc.get_or_add_tcPr().append(shading)
                for paragraph in cell.paragraphs:
                    paragraph.paragraph_format.space_before = Pt(5)
                    paragraph.paragraph_format.space_after = Pt(5)
                    if column > 0:
                        paragraph.alignment = WD_ALIGN_PARAGRAPH.RIGHT
                    for run in paragraph.runs:
                        run.font.color.rgb = RGBColor(0, 0, 0)
                        run.bold = False
        totals = model.totals
        for label, value in (
            ("Taxable amount", totals.taxable_paise),
            ("CGST", totals.cgst_paise),
            ("SGST", totals.sgst_paise),
            ("IGST", totals.igst_paise),
            ("TOTAL", totals.total_paise),
        ):
            paragraph = document.add_paragraph(f"{label}: INR {money(value)}")
            paragraph.alignment = WD_ALIGN_PARAGRAPH.RIGHT
            if label == "TOTAL":
                paragraph.runs[0].bold = True
        document.add_paragraph(totals.amount_in_words)
        for label, value in (("Notes", model.notes), ("Terms & payment details", model.terms)):
            if value:
                document.add_heading(label, 2)
                document.add_paragraph(value)
        footer = section.footer.paragraphs[0]
        footer.text = "DRAFT • Not an issued tax invoice • Edited Word copies are not authoritative"
        footer.runs[0].font.size = Pt(8)
        document.core_properties.title = "Draft invoice"
        for root in (document._element, document.styles.element):
            for border in root.xpath(".//w:pBdr"):
                border.getparent().remove(border)
        output = BytesIO()
        document.save(output)
        return output.getvalue()
