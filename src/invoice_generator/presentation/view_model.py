from invoice_generator.application.contracts.dto import DraftDTO, DraftInput, SaveDraftRequest
from invoice_generator.application.contracts.interfaces import (
    IArtifactActions,
    IDraftPdfCommands,
    IInvoiceDraftCommands,
    IInvoiceQueries,
)


class DraftViewModel:
    """Presentation state and injected capabilities; no business calculations."""

    def __init__(
        self,
        commands: IInvoiceDraftCommands,
        queries: IInvoiceQueries,
        pdfs: IDraftPdfCommands,
        artifacts: IArtifactActions,
    ):
        self.commands, self.queries = commands, queries
        self.pdfs, self.artifacts = pdfs, artifacts
        self.current: DraftDTO | None = None

    def save_request(self, data: DraftInput) -> SaveDraftRequest:
        if self.current is None:
            return SaveDraftRequest(data)
        return SaveDraftRequest(data, self.current.id, self.current.revision)


def display_amount(paise: int) -> str:
    rupees, remainder = divmod(paise, 100)
    return f"INR {rupees:,}.{remainder:02d}"
