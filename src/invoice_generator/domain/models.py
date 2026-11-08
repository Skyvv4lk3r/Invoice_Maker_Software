"""Pure business values. No UI, database, or document-library dependencies."""

from dataclasses import dataclass
from datetime import date
from decimal import ROUND_HALF_UP, Decimal
from enum import StrEnum

MAX_PAISE = 99_999_999_999


class ValidationError(ValueError):
    def __init__(self, field: str, message: str):
        super().__init__(message)
        self.field = field


class TaxMode(StrEnum):
    CGST_SGST = "CGST_SGST"
    IGST = "IGST"


def paise(value: Decimal) -> int:
    if not value.is_finite() or not Decimal(0) <= value <= Decimal(MAX_PAISE) / 100:
        raise ValidationError("amount", "Amount is outside the supported draft range.")
    return int((value * 100).quantize(Decimal("1"), rounding=ROUND_HALF_UP))


def financial_year_start(invoice_date: date) -> int:
    """An internal key; never prepend this to the printed invoice number."""
    return invoice_date.year if invoice_date.month >= 4 else invoice_date.year - 1


@dataclass(frozen=True)
class DraftLine:
    description: str
    quantity: Decimal
    unit_price: Decimal
    gst_rate: Decimal


@dataclass(frozen=True)
class LineTotals:
    taxable_paise: int
    cgst_paise: int
    sgst_paise: int
    igst_paise: int
    total_paise: int


@dataclass(frozen=True)
class InvoiceTotals:
    lines: tuple[LineTotals, ...]
    taxable_paise: int
    cgst_paise: int
    sgst_paise: int
    igst_paise: int
    total_paise: int
    amount_in_words: str


@dataclass(frozen=True)
class DraftInvoice:
    id: str
    revision: int
    firm_name: str
    customer_name: str
    invoice_date: date
    tax_mode: TaxMode
    lines: tuple[DraftLine, ...]
    totals: InvoiceTotals
