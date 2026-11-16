from invoice_generator.application.contracts.dto import DraftDTO, DraftInput, SaveDraftRequest
from invoice_generator.application.contracts.interfaces import (
    IArtifactActions,
    IDateRangeExportCommands,
    IDraftPdfCommands,
    IDraftPreviewQueries,
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
        words: IDraftPdfCommands | None = None,
        previews: IDraftPreviewQueries | None = None,
        range_exports: IDateRangeExportCommands | None = None,
        *,
        auth=None,
        firm=None,
        templates=None,
        customers=None,
        items=None,
        backups=None,
        issued=None,
    ):
        self.commands, self.queries = commands, queries
        self.pdfs, self.artifacts = pdfs, artifacts
        self.words, self.previews, self.range_exports = words, previews, range_exports
        self.auth, self.firm_settings, self.templates = auth, firm, templates
        self.customers, self.items, self.backups, self.issued = customers, items, backups, issued
        self.current: DraftDTO | None = None

    def save_request(self, data: DraftInput) -> SaveDraftRequest:
        if self.current is None:
            return SaveDraftRequest(data)
        return SaveDraftRequest(data, self.current.id, self.current.revision)


def display_amount(paise: int) -> str:
    rupees, remainder = divmod(paise, 100)
    digits = str(rupees)
    groups, prefix = [digits[-3:]], digits[:-3]
    while prefix:
        groups.insert(0, prefix[-2:])
        prefix = prefix[:-2]
    return f"INR {','.join(groups)}.{remainder:02d}"
