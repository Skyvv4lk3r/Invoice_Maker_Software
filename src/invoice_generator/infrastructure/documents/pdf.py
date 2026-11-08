from io import BytesIO
from xml.sax.saxutils import escape

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

from invoice_generator.application.contracts.dto import DraftPdfModel


def money(paise: int) -> str:
    rupees, remainder = divmod(paise, 100)
    return f"{rupees:,}.{remainder:02d}"


class ReportLabDraftRenderer:
    """Format a prepared model. Never calculate tax or allocate numbers here."""

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
        styles = getSampleStyleSheet()
        body = styles["BodyText"]
        story = [
            Paragraph("DRAFT INVOICE", styles["Title"]),
            Paragraph(escape(model.firm_name), styles["Heading2"]),
            Paragraph("Customer: " + escape(model.customer_name), body),
            Paragraph(
                f"Date: {escape(model.invoice_date)} | Draft revision: {model.revision}", body
            ),
            Paragraph("No invoice number allocated. For review only.", body),
            Spacer(1, 6 * mm),
        ]
        rows = [["Description", "Qty", "Rate (INR)", "GST %", "Taxable", "Total"]]
        for row in model.lines:
            rows.append(
                [
                    Paragraph(escape(row.description), body),
                    row.quantity,
                    row.unit_price,
                    row.gst_rate,
                    money(row.taxable_paise),
                    money(row.total_paise),
                ]
            )
        table = Table(
            rows, colWidths=[56 * mm, 17 * mm, 26 * mm, 18 * mm, 29 * mm, 32 * mm], repeatRows=1
        )
        table.setStyle(
            TableStyle(
                [
                    ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#173b4b")),
                    ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
                    ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
                    ("FONTSIZE", (0, 0), (-1, -1), 8),
                    ("VALIGN", (0, 0), (-1, -1), "TOP"),
                    ("ALIGN", (1, 1), (-1, -1), "RIGHT"),
                    ("BOTTOMPADDING", (0, 0), (-1, -1), 8),
                    ("TOPPADDING", (0, 0), (-1, -1), 8),
                    ("LINEBELOW", (0, 0), (-1, -1), 0.4, colors.HexColor("#cbd5df")),
                ]
            )
        )
        story.extend([table, Spacer(1, 5 * mm)])
        totals = model.totals
        for label, value in [
            ("Taxable", totals.taxable_paise),
            ("CGST", totals.cgst_paise),
            ("SGST", totals.sgst_paise),
            ("IGST", totals.igst_paise),
            ("Grand total", totals.total_paise),
        ]:
            story.append(Paragraph(f"{label}: INR {money(value)}", body))
        story.extend(
            [
                Spacer(1, 3 * mm),
                Paragraph(escape(totals.amount_in_words), body),
                Paragraph("Draft tax split: " + escape(model.tax_mode), body),
            ]
        )

        def decorate(canvas, _document):
            canvas.saveState()
            canvas.setFillColor(colors.HexColor("#e9edf0"))
            canvas.setFont("Helvetica-Bold", 64)
            canvas.translate(A4[0] / 2, A4[1] / 2)
            canvas.rotate(35)
            canvas.drawCentredString(0, 0, "DRAFT")
            canvas.restoreState()
            canvas.saveState()
            canvas.setFont("Helvetica", 8)
            canvas.drawString(16 * mm, 10 * mm, "Draft only - not an issued tax invoice")
            canvas.drawRightString(A4[0] - 16 * mm, 10 * mm, f"Page {doc.page}")
            canvas.restoreState()

        doc.build(story, onFirstPage=decorate, onLaterPages=decorate)
        return output.getvalue()
