import base64
from importlib.resources import files
from io import BytesIO
from xml.sax.saxutils import escape

from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER, TA_LEFT, TA_RIGHT
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.platypus import Image, Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

from invoice_generator.application.contracts.dto import DraftPdfModel
from invoice_generator.infrastructure.documents.layout import (
    COLUMN_TITLES,
    COLUMN_WEIGHTS,
    effective_layout,
    line_values,
    money,
    party_lines,
)


class ReportLabDraftRenderer:
    """Renders validated document configuration and prepared, immutable amounts."""

    def __init__(self):
        font_dir = files("reportlab").joinpath("fonts")
        for name, filename in (("InvoiceRegular", "Vera.ttf"), ("InvoiceBold", "VeraBd.ttf")):
            if name not in pdfmetrics.getRegisteredFontNames():
                pdfmetrics.registerFont(TTFont(name, str(font_dir.joinpath(filename))))

    def render(self, model: DraftPdfModel) -> bytes:
        layout = effective_layout(model)
        output = BytesIO()
        margin = layout.margin_mm * mm
        width = A4[0] - 2 * margin
        doc = SimpleDocTemplate(
            output,
            pagesize=A4,
            leftMargin=margin,
            rightMargin=margin,
            topMargin=margin,
            bottomMargin=max(margin, 20 * mm),
            title="Invoice",
        )
        regular, bold = {
            "sans": ("InvoiceRegular", "InvoiceBold"),
            "serif": ("Times-Roman", "Times-Bold"),
            "mono": ("Courier", "Courier-Bold"),
        }[layout.font_family]
        styles = getSampleStyleSheet()
        for style in styles.byName.values():
            if hasattr(style, "fontName"):
                style.fontName = bold if "Bold" in style.fontName else regular
        body = ParagraphStyle(
            "InvoiceBody",
            fontName=regular,
            fontSize=layout.font_size,
            leading=layout.font_size + 4,
            spaceAfter=4,
        )
        small = ParagraphStyle(
            "InvoiceSmall",
            parent=body,
            fontSize=max(8, layout.font_size - 1),
            leading=layout.font_size + 2,
        )
        align = {"left": TA_LEFT, "center": TA_CENTER, "right": TA_RIGHT}[layout.header_alignment]
        title = ParagraphStyle(
            "InvoiceTitle",
            fontName=bold,
            alignment=align,
            fontSize=26,
            leading=30,
            textColor=colors.HexColor("#" + layout.accent),
            spaceAfter=10,
        )

        def p(text, style=body):
            return Paragraph(escape(str(text)).replace("\n", "<br/>"), style)

        title_text = "DRAFT INVOICE" if model.invoice_number is None else "TAX INVOICE"
        if model.status == "CANCELLED":
            title_text = "CANCELLED INVOICE"
        story = []
        if layout.logo_png:
            logo = Image(BytesIO(base64.b64decode(layout.logo_png)))
            ratio = min(45 * mm / logo.imageWidth, 20 * mm / logo.imageHeight)
            logo.drawWidth, logo.drawHeight = logo.imageWidth * ratio, logo.imageHeight * ratio
            logo.hAlign = layout.header_alignment.upper()
            story.extend([logo, Spacer(1, 4 * mm)])
        story.append(p(title_text, title))
        story.append(
            p(
                "For review • No invoice number allocated"
                if model.invoice_number is None
                else f"Invoice number: {model.invoice_number} • ORIGINAL FOR RECIPIENT",
                small,
            )
        )
        story.append(Spacer(1, 5 * mm))
        blocks = {}
        parties = [
            [p(label, styles["Heading5"]), *[p(line) for line in party_lines(name, details)]]
            for label, name, details in (
                ("FROM", model.firm_name, model.firm_details),
                ("BILL TO", model.customer_name, model.customer_details),
            )
        ]
        party_table = Table(
            [parties] if layout.party_layout == "columns" else [[x] for x in parties],
            colWidths=[width / 2, width / 2] if layout.party_layout == "columns" else [width],
        )
        party_table.setStyle(
            TableStyle(
                [
                    ("VALIGN", (0, 0), (-1, -1), "TOP"),
                    ("LEFTPADDING", (0, 0), (-1, -1), 0),
                    ("RIGHTPADDING", (0, 0), (-1, -1), 12),
                ]
            )
        )
        blocks["parties"] = [party_table]
        metadata = [
            f"Date: {model.invoice_date}",
            f"Tax split: {model.tax_mode.replace('_', ' + ')}",
        ]
        for label, value in (
            ("Due", model.due_date),
            ("Reference", model.reference),
            ("Place of supply", model.place_of_supply),
        ):
            if value:
                metadata.append(label + ": " + value)
        blocks["metadata"] = [p("   |   ".join(metadata), small)]
        if model.invoice_number is not None:
            blocks["metadata"].append(p("Reverse charge: No", small))
        if model.shipping_address:
            blocks["metadata"].append(p("Delivery address: " + model.shipping_address, small))
        columns = layout.columns
        rows = [
            [
                p(
                    COLUMN_TITLES[key],
                    ParagraphStyle("Header", parent=small, textColor=colors.white, fontName=bold),
                )
                for key in columns
            ]
        ]
        for line in model.lines:
            values = line_values(line)
            rows.append([p(values[key], small) for key in columns])
        table = Table(
            rows, colWidths=[width * COLUMN_WEIGHTS[key] / 178 for key in columns], repeatRows=1
        )
        table.setStyle(
            TableStyle(
                [
                    ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#" + layout.accent)),
                    ("VALIGN", (0, 0), (-1, -1), "TOP"),
                    (
                        "ROWBACKGROUNDS",
                        (0, 1),
                        (-1, -1),
                        [colors.white, colors.HexColor("#" + layout.tint)],
                    ),
                    ("TOPPADDING", (0, 0), (-1, -1), layout.row_spacing),
                    ("BOTTOMPADDING", (0, 0), (-1, -1), layout.row_spacing),
                    ("LINEBELOW", (0, 0), (-1, -1), 0.35, colors.HexColor("#DFE5E4")),
                ]
            )
        )
        blocks["items"] = [table]
        totals = model.totals
        summary = [
            [label, "INR " + money(value)]
            for label, value in (
                ("Taxable amount", totals.taxable_paise),
                ("CGST", totals.cgst_paise),
                ("SGST", totals.sgst_paise),
                ("IGST", totals.igst_paise),
                ("TOTAL", totals.total_paise),
            )
        ]
        summary_table = Table(summary, colWidths=[47 * mm, 43 * mm], hAlign="RIGHT")
        summary_table.setStyle(
            TableStyle(
                [
                    ("FONTNAME", (0, 0), (-1, -1), regular),
                    ("FONTNAME", (0, -1), (-1, -1), bold),
                    ("BACKGROUND", (0, -1), (-1, -1), colors.HexColor("#" + layout.tint)),
                    ("ALIGN", (1, 0), (-1, -1), "RIGHT"),
                    ("TOPPADDING", (0, 0), (-1, -1), 7),
                    ("BOTTOMPADDING", (0, 0), (-1, -1), 7),
                ]
            )
        )
        blocks["totals"] = [summary_table, Spacer(1, 4 * mm), p(totals.amount_in_words)]
        blocks["notes"] = (
            [p("Notes", styles["Heading4"]), p(model.notes)]
            if model.notes and layout.show_notes
            else []
        )
        blocks["terms"] = (
            [p("Terms & payment details", styles["Heading4"]), p(model.terms)]
            if model.terms and layout.show_terms
            else []
        )
        for section in layout.section_order:
            if blocks[section]:
                story.extend([*blocks[section], Spacer(1, 5 * mm)])
        if model.signatory and (layout.show_signature or model.invoice_number is not None):
            story.extend(
                [
                    Spacer(1, 8 * mm),
                    p("For " + model.firm_name),
                    p("____________________________"),
                    p(model.signatory + " • Authorised signatory"),
                ]
            )
        if layout.footer_text:
            story.append(p(layout.footer_text, small))

        def decorate(canvas, _document):
            if model.invoice_number is None or model.status == "CANCELLED":
                canvas.saveState()
                canvas.setFillColor(colors.HexColor("#F1F4F3"))
                canvas.setFont(bold, 64)
                canvas.translate(A4[0] / 2, A4[1] / 2)
                canvas.rotate(35)
                canvas.drawCentredString(
                    0, 0, "DRAFT" if model.invoice_number is None else "CANCELLED"
                )
                canvas.restoreState()
            canvas.saveState()
            canvas.setFont(regular, 8)
            canvas.setFillColor(colors.HexColor("#65736F"))
            footer = (
                "Draft only • Not an issued tax invoice"
                if model.invoice_number is None
                else f"Invoice {model.invoice_number} • {model.invoice_date}"
            )
            canvas.drawString(margin, 10 * mm, footer)
            canvas.drawRightString(A4[0] - margin, 10 * mm, f"Page {doc.page}")
            canvas.restoreState()

        doc.build(story, onFirstPage=decorate, onLaterPages=decorate)
        return output.getvalue()
