from invoice_generator.application.contracts.dto import (
    ArtifactDTO,
    DraftPdfModel,
    DraftReference,
    PdfLine,
    Result,
)
from invoice_generator.application.handlers.drafts import parse_id, safe_result, to_totals
from invoice_generator.application.ports.documents import IArtifactStore, IDraftPdfRenderer
from invoice_generator.application.ports.persistence import ConflictError, UnitOfWorkFactory


class DraftPdfService:
    def __init__(
        self, uow_factory: UnitOfWorkFactory, renderer: IDraftPdfRenderer, store: IArtifactStore
    ):
        self._uow_factory, self._renderer, self._store = uow_factory, renderer, store

    def export(self, request: DraftReference) -> Result[ArtifactDTO]:
        def operation():
            with self._uow_factory() as uow:
                draft = uow.drafts.get(parse_id(request.id))
                if draft.revision != request.expected_revision:
                    raise ConflictError
            # Capture values, close the DB scope, then do slow document/file work.
            model = DraftPdfModel(
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
                    )
                    for line, total in zip(draft.lines, draft.totals.lines, strict=True)
                ),
                to_totals(draft.totals),
            )
            return self._store.publish_pdf(self._renderer.render(model))

        return safe_result(operation)

    def reveal(self, artifact_id: str) -> Result[bool]:
        def operation():
            self._store.reveal(parse_id(artifact_id))
            return True

        return safe_result(operation)
