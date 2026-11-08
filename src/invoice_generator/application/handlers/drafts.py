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
            error=ApplicationError("CONFLICT", "This draft changed. Reload before saving.")
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
    values.pop("lines")
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
                    row.description, str(row.quantity), str(row.unit_price), str(row.gst_rate)
                )
                for row in draft.lines
            ),
        ),
        to_totals(draft.totals),
    )


def build_draft(data: DraftInput, draft_id: str, revision: int) -> DraftInvoice:
    for field, text in [("firm_name", data.firm_name), ("customer_name", data.customer_name)]:
        if not 1 <= len(text.strip()) <= 200:
            raise ValidationError(field, "Use between 1 and 200 characters.")
    try:
        mode = TaxMode(data.tax_mode)
    except ValueError as error:
        raise ValidationError("tax_mode", "Choose CGST_SGST or IGST explicitly.") from error
    lines = tuple(
        DraftLine(
            line.description.strip(),
            _decimal(line.quantity, f"lines.{index}.quantity"),
            _decimal(line.unit_price, f"lines.{index}.unit_price"),
            _decimal(line.gst_rate, f"lines.{index}.gst_rate"),
        )
        for index, line in enumerate(data.lines, 1)
    )
    return DraftInvoice(
        draft_id,
        revision,
        data.firm_name.strip(),
        data.customer_name.strip(),
        parse_date(data.invoice_date),
        mode,
        lines,
        calculate(lines, mode),
    )


class DraftService:
    """Implements the two narrow draft/query ports; does not know Qt or SQLAlchemy."""

    def __init__(self, uow_factory: UnitOfWorkFactory):
        self._uow_factory = uow_factory

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
