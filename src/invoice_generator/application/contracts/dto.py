"""The public boundary: immutable values only, usable without Qt or SQLAlchemy."""

from dataclasses import dataclass


@dataclass(frozen=True)
class ApplicationError:
    code: str
    message: str
    field: str = ""
    correlation_id: str = ""


@dataclass(frozen=True)
class Result[T]:
    value: T | None = None
    error: ApplicationError | None = None

    def __post_init__(self):
        if (self.value is None) == (self.error is None):
            raise ValueError("A result has exactly one value or error.")


@dataclass(frozen=True)
class LineInput:
    description: str
    quantity: str
    unit_price: str
    gst_rate: str


@dataclass(frozen=True)
class DraftInput:
    firm_name: str
    customer_name: str
    invoice_date: str
    tax_mode: str
    lines: tuple[LineInput, ...]


@dataclass(frozen=True)
class TotalsDTO:
    taxable_paise: int
    cgst_paise: int
    sgst_paise: int
    igst_paise: int
    total_paise: int
    amount_in_words: str


@dataclass(frozen=True)
class DraftDTO:
    id: str
    revision: int
    data: DraftInput
    totals: TotalsDTO


@dataclass(frozen=True)
class SaveDraftRequest:
    data: DraftInput
    id: str | None = None
    expected_revision: int = 0


@dataclass(frozen=True)
class DraftReference:
    id: str
    expected_revision: int


@dataclass(frozen=True)
class DateRange:
    start: str
    end: str


@dataclass(frozen=True)
class DraftSummary:
    id: str
    revision: int
    invoice_date: str
    customer_name: str
    total_paise: int


@dataclass(frozen=True)
class ArtifactDTO:
    id: str
    display_name: str


@dataclass(frozen=True)
class PdfLine:
    description: str
    quantity: str
    unit_price: str
    gst_rate: str
    taxable_paise: int
    total_paise: int


@dataclass(frozen=True)
class DraftPdfModel:
    draft_id: str
    revision: int
    firm_name: str
    customer_name: str
    invoice_date: str
    tax_mode: str
    lines: tuple[PdfLine, ...]
    totals: TotalsDTO
