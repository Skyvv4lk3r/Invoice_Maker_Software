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
                "Record ID",
                "Invoice number",
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
                "Record ID",
                "Invoice number",
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
            "status": "ISSUED_REGISTER"
            if any(model.invoice_number for model in models)
            else "DRAFT",
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
                        model.status,
                        model.draft_id,
                        model.invoice_number or "",
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
                            model.status,
                            model.draft_id,
                            model.invoice_number or "",
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
                stem = (
                    f"{model.invoice_date}-{model.invoice_number or 'draft'}-"
                    f"{model.draft_id}-r{model.revision}"
                )
                pdf_name, word_name = f"pdf/{stem}.pdf", f"word/{stem}.docx"
                archive.writestr(pdf_name, self._pdf.render(model))
                archive.writestr(word_name, self._word.render(model))
                manifest["invoices"].append(
                    {
                        "id": model.draft_id,
                        "revision": model.revision,
                        "number": model.invoice_number,
                        "status": model.status,
                        "pdf": pdf_name,
                        "word": word_name,
                    }
                )
            archive.writestr("invoices.csv", csv_bytes(invoices))
            archive.writestr("line-items.csv", csv_bytes(lines))
            archive.writestr("manifest.json", json.dumps(manifest, indent=2))
            issued = any(model.invoice_number is not None for model in models)
            description = (
                "ISSUED INVOICE REGISTER — NOT A GST PORTAL IMPORT FILE\n"
                "Cancelled invoices are included with status CANCELLED; exclude or reconcile them "
                "appropriately when preparing returns. Word copies are editable references.\n"
                if issued
                else "DRAFT REVIEW PACKAGE — NOT A GST RETURN\nNo numbers allocated.\n"
            )
            archive.writestr(
                "README.txt",
                description + f"Inclusive invoice-date range: {dates.start} to {dates.end}.\n"
                "Documents and registers use the same captured snapshots. All amounts are INR.\n"
                "No filing or delivery is performed. Spreadsheet-sensitive text is escaped.\n",
            )
        return output.getvalue()
