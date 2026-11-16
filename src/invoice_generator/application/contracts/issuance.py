from dataclasses import dataclass
from typing import Protocol

from invoice_generator.application.contracts.dto import (
    ArtifactDTO,
    DateRange,
    DraftPdfModel,
    Result,
)


@dataclass(frozen=True)
class IssueRequest:
    draft_id: str
    expected_revision: int
    request_id: str
    shipping_address: str


@dataclass(frozen=True)
class IssuedInvoice:
    id: str
    draft_id: str
    financial_year: int
    number: int
    status: str
    model: DraftPdfModel
    cancellation_reason: str = ""


class IInvoiceIssuance(Protocol):
    def issue(self, request: IssueRequest) -> Result[IssuedInvoice]: ...
    def list(self, dates: DateRange) -> Result[tuple[IssuedInvoice, ...]]: ...
    def get(self, invoice_id: str) -> Result[IssuedInvoice]: ...
    def preview(self, invoice_id: str) -> Result[bytes]: ...
    def export(self, invoice_id: str, format: str = "pdf") -> Result[ArtifactDTO]: ...
    def cancel(self, invoice_id: str, reason: str) -> Result[IssuedInvoice]: ...
    def export_range(self, dates: DateRange) -> Result[ArtifactDTO]: ...
