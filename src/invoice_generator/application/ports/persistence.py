from collections.abc import Callable
from datetime import date
from types import TracebackType
from typing import Protocol

from invoice_generator.domain.models import DraftInvoice


class ConflictError(Exception):
    pass


class MissingError(Exception):
    pass


class StorageError(Exception):
    pass


class IDraftRepository(Protocol):
    def get(self, draft_id: str) -> DraftInvoice: ...
    def list(self, start: date, end: date) -> tuple[DraftInvoice, ...]: ...
    def save(self, draft: DraftInvoice, expected_revision: int) -> DraftInvoice: ...
    def delete(self, draft_id: str, expected_revision: int) -> None: ...


class IAuditLog(Protocol):
    def append(self, action: str, draft_id: str, revision: int) -> None: ...


class IDraftUnitOfWork(Protocol):
    drafts: IDraftRepository
    audit: IAuditLog

    def __enter__(self) -> "IDraftUnitOfWork": ...
    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        tb: TracebackType | None,
    ) -> None: ...
    def commit(self) -> None: ...


UnitOfWorkFactory = Callable[[], IDraftUnitOfWork]
