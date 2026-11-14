import csv
import json
from io import BytesIO, StringIO
from zipfile import ZIP_DEFLATED, ZipFile

from invoice_generator.application.contracts.dto import DateRange, DraftPdfModel
from invoice_generator.application.ports.documents import IDraftPdfRenderer


def csv_text(value: str) -> str:
    # Protect spreadsheet users from formulas in names, descriptions and other entered text.
    if value.lstrip().startswith(("=", "+", "-", "@")) or value.startswith(("\t", "\r", "\n")):
        return "'" + value
    return value


def decimal_money(paise: int) -> str:
    rupees, remainder = divmod(paise, 100)
    return f"{rupees}.{remainder:02d}"


def csv_bytes(rows: list[list]) -> bytes:
    output = StringIO(newline="")
    csv.writer(output, quoting=csv.QUOTE_ALL).writerows(rows)
    return output.getvalue().encode("utf-8-sig")


class DraftBundleRenderer:
    def __init__(self, pdf: IDraftPdfRenderer, word: IDraftPdfRenderer):
        self._pdf, self._word = pdf, word

    def render(self, models: tuple[DraftPdfModel, ...], dates: DateRange) -> bytes:
        invoices = [
            [
                "Status",
                "Draft ID",
                "Revision",
                "Date",
                "Firm",
                "Firm GSTIN",
                "Customer",
                "Customer GSTIN",
                "Place of supply",
                "Tax split",
                "Reference",
                "Taxable INR",
                "CGST INR",
                "SGST INR",
                "IGST INR",
                "Total INR",
            ]
        ]
        lines = [
            [
                "Status",
                "Draft ID",
                "Revision",
                "Date",
                "Line",
                "Type",
                "Description",
                "HSN/SAC",
                "Quantity",
                "Unit",
                "Unit price INR",
                "GST %",
                "Taxable INR",
                "CGST INR",
                "SGST INR",
                "IGST INR",
                "Total INR",
            ]
        ]
        output = BytesIO()
        manifest = {
            "schema_version": 1,
            "status": "DRAFT",
            "start": dates.start,
            "end": dates.end,
            "count": len(models),
            "invoices": [],
        }
        with ZipFile(output, "w", ZIP_DEFLATED) as archive:
            for model in models:
                totals = model.totals
                invoices.append(
                    [
                        "DRAFT",
                        model.draft_id,
                        model.revision,
                        model.invoice_date,
                        *[
                            csv_text(value)
                            for value in (
                                model.firm_name,
                                model.firm_details.gstin,
                                model.customer_name,
                                model.customer_details.gstin,
                                model.place_of_supply,
                                model.tax_mode,
                                model.reference,
                            )
                        ],
                        *[
                            decimal_money(value)
                            for value in (
                                totals.taxable_paise,
                                totals.cgst_paise,
                                totals.sgst_paise,
                                totals.igst_paise,
                                totals.total_paise,
                            )
                        ],
                    ]
                )
                for number, line in enumerate(model.lines, 1):
                    lines.append(
                        [
                            "DRAFT",
                            model.draft_id,
                            model.revision,
                            model.invoice_date,
                            number,
                            line.item_type,
                            csv_text(line.description),
                            line.hsn_sac,
                            line.quantity,
                            csv_text(line.unit),
                            line.unit_price,
                            line.gst_rate,
                            *[
                                decimal_money(value)
                                for value in (
                                    line.taxable_paise,
                                    line.cgst_paise,
                                    line.sgst_paise,
                                    line.igst_paise,
                                    line.total_paise,
                                )
                            ],
                        ]
                    )
                stem = f"{model.invoice_date}-{model.draft_id}-r{model.revision}"
                pdf_name, word_name = f"pdf/{stem}.pdf", f"word/{stem}.docx"
                archive.writestr(pdf_name, self._pdf.render(model))
                archive.writestr(word_name, self._word.render(model))
                manifest["invoices"].append(
                    {
                        "id": model.draft_id,
                        "revision": model.revision,
                        "pdf": pdf_name,
                        "word": word_name,
                    }
                )
            archive.writestr("invoices.csv", csv_bytes(invoices))
            archive.writestr("line-items.csv", csv_bytes(lines))
            archive.writestr("manifest.json", json.dumps(manifest, indent=2))
            archive.writestr(
                "README.txt",
                (
                    "DRAFT REVIEW PACKAGE — NOT A GST RETURN\n"
                    "Contains all non-deleted saved drafts whose invoice dates are in the "
                    "inclusive "
                    f"range {dates.start} to {dates.end}. Unsaved edits are not included.\n"
                    "PDFs, Word copies and CSV registers use the same captured draft revisions.\n"
                    "All amounts are INR. GST rates and split are manually supplied draft inputs.\n"
                    "No invoice numbers have been allocated. "
                    "Verify and issue invoices before filing.\n"
                    "Do not use this package as a completed GST filing or import format.\n"
                    "Spreadsheet-sensitive text is prefixed with an apostrophe.\n"
                ),
            )
        return output.getvalue()
