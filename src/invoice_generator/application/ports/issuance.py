from typing import Protocol

from invoice_generator.application.contracts.dto import ArtifactDTO, DraftPdfModel
from invoice_generator.application.contracts.issuance import IssuedInvoice


class IIssuedStore(Protocol):
    def issue(
        self,
        draft_id: str,
        expected_revision: int,
        request_id: str,
        request_hash: str,
        financial_year: int,
        model: DraftPdfModel,
        firm_revision: int,
    ) -> IssuedInvoice: ...
    def get(self, invoice_id: str) -> IssuedInvoice: ...
    def for_draft(self, draft_id: str) -> IssuedInvoice | None: ...
    def list(self, start: str, end: str) -> tuple[IssuedInvoice, ...]: ...
    def cancel(self, invoice_id: str, reason: str) -> IssuedInvoice: ...
    def rendered(self, invoice_id: str, artifact: ArtifactDTO, expected_status: str) -> None: ...
