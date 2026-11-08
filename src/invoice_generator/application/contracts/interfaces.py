from typing import Protocol

from invoice_generator.application.contracts.dto import (
    ArtifactDTO,
    DateRange,
    DraftDTO,
    DraftInput,
    DraftReference,
    DraftSummary,
    Result,
    SaveDraftRequest,
    TotalsDTO,
)


class IInvoiceDraftCommands(Protocol):
    def save(self, request: SaveDraftRequest) -> Result[DraftDTO]: ...
    def delete(self, request: DraftReference) -> Result[bool]: ...


class IInvoiceQueries(Protocol):
    def calculate(self, data: DraftInput) -> Result[TotalsDTO]: ...
    def get(self, draft_id: str) -> Result[DraftDTO]: ...
    def list(self, dates: DateRange) -> Result[tuple[DraftSummary, ...]]: ...


class IDraftPdfCommands(Protocol):
    """Milestone-1 draft export. Issued-document jobs are a separate future port."""

    def export(self, request: DraftReference) -> Result[ArtifactDTO]: ...


class IArtifactActions(Protocol):
    def reveal(self, artifact_id: str) -> Result[bool]: ...
