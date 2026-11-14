from importlib.resources import files
from io import BytesIO
from xml.sax.saxutils import escape

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

from invoice_generator.application.contracts.dto import DraftPdfModel
from invoice_generator.infrastructure.documents.layout import money, palette, party_lines


class ReportLabDraftRenderer:
    """Renders the prepared financial model; never computes tax or allocates numbers."""

    def __init__(self):
        # Ship with ReportLab's bundled Latin fonts, avoiding viewer-dependent substitution.
        font_dir = files("reportlab").joinpath("fonts")
        for name, filename in (("InvoiceRegular", "Vera.ttf"), ("InvoiceBold", "VeraBd.ttf")):
            if name not in pdfmetrics.getRegisteredFontNames():
                pdfmetrics.registerFont(TTFont(name, str(font_dir.joinpath(filename))))

    def render(self, model: DraftPdfModel) -> bytes:
        output = BytesIO()
        doc = SimpleDocTemplate(
            output,
            pagesize=A4,
            leftMargin=16 * mm,
            rightMargin=16 * mm,
            topMargin=16 * mm,
            bottomMargin=20 * mm,
            title="Draft invoice",
        )
        ink, tint = palette(model.template_id)
        styles = getSampleStyleSheet()
        for style in styles.byName.values():
            if hasattr(style, "fontName"):
                style.fontName = "InvoiceBold" if "Bold" in style.fontName else "InvoiceRegular"
        body = ParagraphStyle("InvoiceBody", parent=styles["BodyText"], fontSize=9, leading=13)
        small = ParagraphStyle("InvoiceSmall", parent=body, fontSize=8, leading=11)
        title = ParagraphStyle(
            "InvoiceTitle",
            parent=styles["Title"],
            alignment=0,
            fontSize=28,
            leading=32,
            textColor=colors.HexColor("#" + ink),
            spaceAfter=12,
        )

        def p(text, style=body):
            return Paragraph(escape(text).replace("\n", "<br/>"), style)

        story = [
            p("DRAFT INVOICE", title),
            p("For review • No invoice number allocated", small),
            Spacer(1, 8 * mm),
        ]
        parties = []
        for heading, name, details in (
            ("FROM", model.firm_name, model.firm_details),
            ("BILL TO", model.customer_name, model.customer_details),
        ):
            parties.append(
                [p(heading, styles["Heading5"]), *[p(line) for line in party_lines(name, details)]]
            )
        party_table = Table([parties], colWidths=[89 * mm, 89 * mm])
        party_table.setStyle(
            TableStyle(
                [
                    ("VALIGN", (0, 0), (-1, -1), "TOP"),
                    ("LEFTPADDING", (0, 0), (-1, -1), 0),
                    ("RIGHTPADDING", (0, 0), (-1, -1), 12),
                ]
            )
        )
        story.extend([party_table, Spacer(1, 6 * mm)])
        metadata = [
            f"Date: {model.invoice_date}",
            f"Tax split: {model.tax_mode.replace('_', ' + ')}",
        ]
        if model.due_date:
            metadata.append("Due: " + model.due_date)
        if model.reference:
            metadata.append("Reference: " + model.reference)
        if model.place_of_supply:
            metadata.append("Place of supply: " + model.place_of_supply)
        story.extend([p("   |   ".join(metadata), small), Spacer(1, 5 * mm)])
        rows = [["ITEM / HSN-SAC", "QTY / UNIT", "RATE (INR)", "GST %", "TAXABLE", "TOTAL"]]
        for line in model.lines:
            description = line.description
            if line.hsn_sac:
                description += f"\n{line.item_type.title()} • {line.hsn_sac}"
            rows.append(
                [
                    p(description, small),
                    p(f"{line.quantity} {line.unit}", small),
                    p(line.unit_price, small),
                    p(line.gst_rate, small),
                    p(money(line.taxable_paise), small),
                    p(money(line.total_paise), small),
                ]
            )
        table = Table(
            rows, colWidths=[56 * mm, 25 * mm, 26 * mm, 16 * mm, 27 * mm, 28 * mm], repeatRows=1
        )
        table.setStyle(
            TableStyle(
                [
                    ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#" + ink)),
                    ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
                    ("FONTNAME", (0, 0), (-1, 0), "InvoiceBold"),
                    ("FONTSIZE", (0, 0), (-1, -1), 7.5),
                    ("VALIGN", (0, 0), (-1, -1), "TOP"),
                    (
                        "ROWBACKGROUNDS",
                        (0, 1),
                        (-1, -1),
                        [colors.white, colors.HexColor("#FAFBFC")],
                    ),
                    ("TOPPADDING", (0, 0), (-1, -1), 9),
                    ("BOTTOMPADDING", (0, 0), (-1, -1), 9),
                    ("LINEBELOW", (0, 0), (-1, -1), 0.35, colors.HexColor("#DFE5E4")),
                ]
            )
        )
        story.extend([table, Spacer(1, 6 * mm)])
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
        summary_table = Table(summary, colWidths=[43 * mm, 40 * mm], hAlign="RIGHT")
        summary_table.setStyle(
            TableStyle(
                [
                    ("FONTNAME", (0, 0), (-1, -1), "InvoiceRegular"),
                    ("FONTNAME", (0, -1), (-1, -1), "InvoiceBold"),
                    ("BACKGROUND", (0, -1), (-1, -1), colors.HexColor("#" + tint)),
                    ("ALIGN", (1, 0), (-1, -1), "RIGHT"),
                    ("TOPPADDING", (0, 0), (-1, -1), 7),
                    ("BOTTOMPADDING", (0, 0), (-1, -1), 7),
                ]
            )
        )
        story.extend([summary_table, Spacer(1, 5 * mm), p(totals.amount_in_words)])
        for heading, value in (("Notes", model.notes), ("Terms & payment details", model.terms)):
            if value:
                story.extend([Spacer(1, 4 * mm), p(heading, styles["Heading4"]), p(value)])

        def decorate(canvas, _document):
            canvas.saveState()
            canvas.setFillColor(colors.HexColor("#F1F4F3"))
            canvas.setFont("InvoiceBold", 64)
            canvas.translate(A4[0] / 2, A4[1] / 2)
            canvas.rotate(35)
            canvas.drawCentredString(0, 0, "DRAFT")
            canvas.restoreState()
            canvas.saveState()
            canvas.setFont("InvoiceRegular", 8)
            canvas.setFillColor(colors.HexColor("#65736F"))
            canvas.drawString(16 * mm, 10 * mm, "Draft only • Not an issued tax invoice")
            canvas.drawRightString(A4[0] - 16 * mm, 10 * mm, f"Page {doc.page}")
            canvas.restoreState()

        doc.build(story, onFirstPage=decorate, onLaterPages=decorate)
        return output.getvalue()
