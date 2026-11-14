from dataclasses import asdict
from uuid import uuid4

from invoice_generator.application.contracts.dto import (
    ArtifactDTO,
    DateRange,
    DraftInput,
    DraftPdfModel,
    DraftReference,
    ExportReceipt,
    PartyDetails,
    PdfLine,
    Result,
)
from invoice_generator.application.handlers.drafts import (
    build_draft,
    parse_date,
    parse_id,
    safe_result,
    to_totals,
)
from invoice_generator.application.ports.documents import (
    IArtifactStore,
    IDraftBundleRenderer,
    IDraftPdfRenderer,
)
from invoice_generator.application.ports.persistence import ConflictError, UnitOfWorkFactory
from invoice_generator.domain.models import DraftInvoice, ValidationError


def document_model(draft: DraftInvoice) -> DraftPdfModel:
    """One immutable financial snapshot shared by PDF, Word and the export register."""
    return DraftPdfModel(
        draft.id,
        draft.revision,
        draft.firm_name,
        draft.customer_name,
        draft.invoice_date.isoformat(),
        draft.tax_mode.value,
        tuple(
            PdfLine(
                line.description,
                str(line.quantity),
                str(line.unit_price),
                str(line.gst_rate),
                total.taxable_paise,
                total.total_paise,
                line.item_type,
                line.hsn_sac,
                line.unit,
                total.cgst_paise,
                total.sgst_paise,
                total.igst_paise,
            )
            for line, total in zip(draft.lines, draft.totals.lines, strict=True)
        ),
        to_totals(draft.totals),
        PartyDetails(**asdict(draft.firm_details)),
        PartyDetails(**asdict(draft.customer_details)),
        draft.place_of_supply,
        draft.reference,
        draft.due_date,
        draft.notes,
        draft.terms,
        draft.template_id,
    )


class DraftPdfService:
    def __init__(
        self,
        uow_factory: UnitOfWorkFactory,
        renderer: IDraftPdfRenderer,
        store: IArtifactStore,
        extension: str = "pdf",
    ):
        self._uow_factory, self._renderer, self._store = uow_factory, renderer, store
        self._extension = extension

    def export(self, request: DraftReference) -> Result[ArtifactDTO]:
        def operation():
            with self._uow_factory() as uow:
                draft = uow.drafts.get(parse_id(request.id))
                if draft.revision != request.expected_revision:
                    raise ConflictError
            data = self._renderer.render(document_model(draft))
            if self._extension == "pdf":
                return self._store.publish_pdf(data)
            return self._store.publish(data, self._extension)

        return safe_result(operation)

    def preview(self, data: DraftInput) -> Result[bytes]:
        return safe_result(
            lambda: self._renderer.render(document_model(build_draft(data, str(uuid4()), 0)))
        )

    def reveal(self, artifact_id: str) -> Result[bool]:
        def operation():
            self._store.reveal(parse_id(artifact_id))
            return True

        return safe_result(operation)


class DateRangeExportService:
    def __init__(
        self, uow_factory: UnitOfWorkFactory, renderer: IDraftBundleRenderer, store: IArtifactStore
    ):
        self._uow_factory, self._renderer, self._store = uow_factory, renderer, store

    def export_range(self, dates: DateRange) -> Result[ExportReceipt]:
        def operation():
            start, end = parse_date(dates.start, "start"), parse_date(dates.end, "end")
            if start > end:
                raise ValidationError("date_range", "Start date must not be after end date.")
            with self._uow_factory() as uow:
                # One SELECT captures all matching rows and revisions before slow rendering.
                models = tuple(document_model(draft) for draft in uow.drafts.list(start, end))
            if not models:
                raise ValidationError("date_range", "No saved drafts in this date range.")
            artifact = self._store.publish(self._renderer.render(models, dates), "zip")
            return ExportReceipt(artifact, len(models))

        return safe_result(operation)
