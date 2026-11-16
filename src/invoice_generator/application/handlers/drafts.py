import logging
import re
from dataclasses import asdict
from datetime import date
from decimal import Decimal
from uuid import UUID, uuid4

from invoice_generator.application.contracts.dto import (
    ApplicationError,
    DateRange,
    DraftDTO,
    DraftInput,
    DraftReference,
    DraftSummary,
    LineInput,
    LineTotalsDTO,
    PartyDetails,
    Result,
    SaveDraftRequest,
    TotalsDTO,
)
from invoice_generator.application.ports.persistence import (
    ConflictError,
    MissingError,
    StorageError,
    UnitOfWorkFactory,
)
from invoice_generator.domain.calculation import calculate
from invoice_generator.domain.models import (
    DraftInvoice,
    DraftLine,
    InvoiceTotals,
    Party,
    TaxMode,
    ValidationError,
)

LOG = logging.getLogger(__name__)


def safe_result(operation):
    """Translate known failures; keep unexpected diagnostics outside the UI."""
    try:
        return Result(value=operation())
    except ValidationError as error:
        return Result(error=ApplicationError("VALIDATION", str(error), error.field))
    except ConflictError:
        return Result(
            error=ApplicationError("CONFLICT", "This record changed. Reload before saving.")
        )
    except MissingError:
        return Result(error=ApplicationError("NOT_FOUND", "This draft is unavailable or deleted."))
    except (StorageError, OSError):
        key = str(uuid4())
        LOG.error("Storage failure [%s]", key, exc_info=True)
        return Result(
            error=ApplicationError(
                "STORAGE_FAILURE", "Could not access storage.", correlation_id=key
            )
        )


def parse_date(raw: str, field: str = "invoice_date") -> date:
    try:
        value = date.fromisoformat(raw)
        if value.isoformat() != raw:
            raise ValueError
        return value
    except ValueError as error:
        raise ValidationError(field, "Use a valid date in YYYY-MM-DD format.") from error


def parse_id(raw: str) -> str:
    try:
        return str(UUID(raw))
    except ValueError as error:
        raise ValidationError("id", "Invalid draft identifier.") from error


def _decimal(raw: str, field: str) -> Decimal:
    if not re.fullmatch(r"\d{1,10}(?:\.\d{1,4})?", raw.strip()):
        raise ValidationError(field, "Use a non-negative decimal with at most four decimal places.")
    return Decimal(raw.strip())


def to_totals(totals: InvoiceTotals) -> TotalsDTO:
    values = asdict(totals)
    values["lines"] = tuple(LineTotalsDTO(**line) for line in values["lines"])
    return TotalsDTO(**values)


def to_dto(draft: DraftInvoice) -> DraftDTO:
    return DraftDTO(
        draft.id,
        draft.revision,
        DraftInput(
            draft.firm_name,
            draft.customer_name,
            draft.invoice_date.isoformat(),
            draft.tax_mode.value,
            tuple(
                LineInput(
                    row.description,
                    str(row.quantity),
                    str(row.unit_price),
                    str(row.gst_rate),
                    row.item_type,
                    row.hsn_sac,
                    row.unit,
                )
                for row in draft.lines
            ),
            PartyDetails(**asdict(draft.firm_details)),
            PartyDetails(**asdict(draft.customer_details)),
            draft.place_of_supply,
            draft.reference,
            draft.due_date,
            draft.notes,
            draft.terms,
            draft.template_id,
        ),
        to_totals(draft.totals),
    )


def _text(raw: str, field: str, maximum: int) -> str:
    value = raw.strip()
    if len(value) > maximum or any(
        (ord(ch) < 32 and ch not in "\n\r\t")
        or 0xD800 <= ord(ch) <= 0xDFFF
        or ord(ch) in (0xFFFE, 0xFFFF)
        for ch in value
    ):
        raise ValidationError(field, f"Use readable text up to {maximum} characters.")
    return value


def _party(details: PartyDetails, field: str) -> Party:
    gstin = _text(details.gstin, f"{field}.gstin", 15).upper()
    if gstin and not re.fullmatch(r"\d{2}[A-Z]{5}\d{4}[A-Z][A-Z0-9]Z[A-Z0-9]", gstin):
        raise ValidationError(f"{field}.gstin", "Enter a 15-character GSTIN or leave it blank.")
    return Party(
        _text(details.address, f"{field}.address", 1000),
        gstin,
        _text(details.state, f"{field}.state", 100),
        _text(details.email, f"{field}.email", 200),
        _text(details.phone, f"{field}.phone", 40),
    )


def _line(line: LineInput, index: int) -> DraftLine:
    prefix = f"lines.{index}"
    if line.item_type not in ("GOODS", "SERVICES"):
        raise ValidationError(f"{prefix}.item_type", "Choose Goods or Services.")
    code = line.hsn_sac.strip()
    if code and not re.fullmatch(r"\d{2,8}", code):
        raise ValidationError(f"{prefix}.hsn_sac", "Use 2 to 8 digits or leave the code blank.")
    return DraftLine(
        _text(line.description, f"{prefix}.description", 500),
        _decimal(line.quantity, f"{prefix}.quantity"),
        _decimal(line.unit_price, f"{prefix}.unit_price"),
        _decimal(line.gst_rate, f"{prefix}.gst_rate"),
        line.item_type,
        code,
        _text(line.unit, f"{prefix}.unit", 20),
    )


def build_draft(data: DraftInput, draft_id: str, revision: int) -> DraftInvoice:
    for field, text in [("firm_name", data.firm_name), ("customer_name", data.customer_name)]:
        if not 1 <= len(_text(text, field, 200)) <= 200:
            raise ValidationError(field, "Use between 1 and 200 characters.")
    try:
        mode = TaxMode(data.tax_mode)
    except ValueError as error:
        raise ValidationError("tax_mode", "Choose CGST_SGST or IGST explicitly.") from error
    lines = tuple(_line(line, index) for index, line in enumerate(data.lines, 1))
    invoice_date = parse_date(data.invoice_date)
    if data.due_date and parse_date(data.due_date, "due_date") < invoice_date:
        raise ValidationError("due_date", "Due date cannot be before the invoice date.")
    if data.template_id not in ("modern", "classic"):
        parse_id(data.template_id)
    return DraftInvoice(
        draft_id,
        revision,
        data.firm_name.strip(),
        data.customer_name.strip(),
        invoice_date,
        mode,
        lines,
        calculate(lines, mode),
        _party(data.firm_details, "firm_details"),
        _party(data.customer_details, "customer_details"),
        _text(data.place_of_supply, "place_of_supply", 100),
        _text(data.reference, "reference", 100),
        data.due_date,
        _text(data.notes, "notes", 3000),
        _text(data.terms, "terms", 2000),
        data.template_id,
    )


class DraftService:
    """Implements the two narrow draft/query ports; does not know Qt or SQLAlchemy."""

    def __init__(self, uow_factory: UnitOfWorkFactory, templates=None):
        self._uow_factory = uow_factory
        self._templates = templates

    def calculate(self, data: DraftInput) -> Result[TotalsDTO]:
        return safe_result(lambda: to_totals(build_draft(data, str(uuid4()), 0).totals))

    def save(self, request: SaveDraftRequest) -> Result[DraftDTO]:
        def operation():
            if request.expected_revision < 0 or (
                request.id is None and request.expected_revision != 0
            ):
                raise ValidationError("revision", "New drafts must start at revision zero.")
            draft_id = parse_id(request.id) if request.id is not None else str(uuid4())
            draft = build_draft(request.data, draft_id, request.expected_revision)
            if self._templates is not None:
                self._templates.get(draft.template_id)
            with self._uow_factory() as uow:
                saved = uow.drafts.save(draft, request.expected_revision)
                uow.audit.append("draft.saved", saved.id, saved.revision)
                uow.commit()
                return to_dto(saved)

        return safe_result(operation)

    def get(self, draft_id: str) -> Result[DraftDTO]:
        def operation():
            with self._uow_factory() as uow:
                return to_dto(uow.drafts.get(parse_id(draft_id)))

        return safe_result(operation)

    def list(self, dates: DateRange) -> Result[tuple[DraftSummary, ...]]:
        def operation():
            start, end = parse_date(dates.start, "start"), parse_date(dates.end, "end")
            if start > end:
                raise ValidationError("date_range", "Start date must not be after end date.")
            with self._uow_factory() as uow:
                return tuple(
                    DraftSummary(
                        x.id,
                        x.revision,
                        x.invoice_date.isoformat(),
                        x.customer_name,
                        x.totals.total_paise,
                        x.firm_name,
                        x.reference,
                    )
                    for x in uow.drafts.list(start, end)
                )

        return safe_result(operation)

    def delete(self, request: DraftReference) -> Result[bool]:
        def operation():
            with self._uow_factory() as uow:
                draft_id = parse_id(request.id)
                uow.drafts.delete(draft_id, request.expected_revision)
                uow.audit.append("draft.deleted", draft_id, request.expected_revision + 1)
                uow.commit()
                return True

        return safe_result(operation)
