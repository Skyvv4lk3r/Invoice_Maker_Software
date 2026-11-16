"""Firm, identity, catalog and template values at the public desktop boundary."""

from dataclasses import dataclass, field
from typing import Protocol

from invoice_generator.application.contracts.dto import (
    ArtifactDTO,
    DraftInput,
    PartyDetails,
    Result,
)
from invoice_generator.application.contracts.layout import InvoiceLayout


@dataclass(frozen=True)
class AccountState:
    configured: bool
    signed_in: bool
    username: str = ""


@dataclass(frozen=True)
class OwnerSetup:
    firm_name: str
    username: str
    password: str = field(repr=False)


@dataclass(frozen=True)
class RecoveryKey:
    code: str = field(repr=False)


@dataclass(frozen=True)
class FirmProfile:
    name: str
    details: PartyDetails = PartyDetails()
    bank_details: str = ""
    default_terms: str = "Payment within 30 days."
    default_template: str = "modern"
    signatory: str = ""
    invoice_mode: str = "REVIEW_REQUIRED"
    revision: int = 0


@dataclass(frozen=True)
class TemplateVersion:
    id: str
    version: int
    layout: InvoiceLayout


@dataclass(frozen=True)
class CustomerRecord:
    name: str
    details: PartyDetails = PartyDetails()
    id: str = ""
    revision: int = 0


@dataclass(frozen=True)
class ItemRecord:
    description: str
    unit_price: str = "0.00"
    gst_rate: str = "0"
    item_type: str = "GOODS"
    hsn_sac: str = ""
    unit: str = "Nos"
    id: str = ""
    revision: int = 0


@dataclass(frozen=True)
class AuditEntry:
    action: str
    record_id: str
    revision: int
    occurred_at: str


class IAuthentication(Protocol):
    def state(self) -> Result[AccountState]: ...
    def setup(self, request: OwnerSetup) -> Result[RecoveryKey]: ...
    def login(self, username: str, password: str) -> Result[bool]: ...
    def logout(self) -> Result[bool]: ...
    def touch(self) -> Result[bool]: ...
    def change_password(self, current: str, new: str) -> Result[RecoveryKey]: ...
    def recover(
        self, username: str, recovery_code: str, new_password: str
    ) -> Result[RecoveryKey]: ...


class IFirmSettings(Protocol):
    def get(self) -> Result[FirmProfile]: ...
    def save(self, profile: FirmProfile) -> Result[FirmProfile]: ...
    def audit(self) -> Result[tuple[AuditEntry, ...]]: ...


class ITemplateCatalog(Protocol):
    def preview(self, layout: InvoiceLayout, data: DraftInput) -> Result[bytes]: ...
    def list(self) -> Result[tuple[TemplateVersion, ...]]: ...
    def save(
        self, layout: InvoiceLayout, template_id: str = "", expected_version: int = 0
    ) -> Result[TemplateVersion]: ...
    def normalize_logo(self, content: bytes) -> Result[str]: ...
    def import_layout(self, content: bytes) -> Result[TemplateVersion]: ...
    def export_layout(self, template_id: str) -> Result[bytes]: ...


class ICustomerCatalog(Protocol):
    def list(self) -> Result[tuple[CustomerRecord, ...]]: ...
    def save(self, record: CustomerRecord) -> Result[CustomerRecord]: ...
    def delete(self, record_id: str, revision: int) -> Result[bool]: ...


class IItemCatalog(Protocol):
    def list(self) -> Result[tuple[ItemRecord, ...]]: ...
    def save(self, record: ItemRecord) -> Result[ItemRecord]: ...
    def delete(self, record_id: str, revision: int) -> Result[bool]: ...


class IBackupCommands(Protocol):
    def create(self, destination: str, passphrase: str) -> Result[ArtifactDTO]: ...
    def restore_copy(self, source: str, passphrase: str, destination: str) -> Result[str]: ...
