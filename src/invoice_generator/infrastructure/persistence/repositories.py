import json
from dataclasses import asdict, replace
from datetime import UTC, date, datetime
from decimal import Decimal
from uuid import uuid4

from sqlalchemy import select, update
from sqlalchemy.exc import IntegrityError, SQLAlchemyError
from sqlalchemy.orm import Session

from invoice_generator.application.ports.persistence import (
    ConflictError,
    MissingError,
    StorageError,
)
from invoice_generator.domain.models import (
    DraftInvoice,
    DraftLine,
    InvoiceTotals,
    LineTotals,
    TaxMode,
)
from invoice_generator.infrastructure.persistence.models import AuditRecord, DraftRecord


def encode(draft: DraftInvoice) -> str:
    return json.dumps(asdict(draft), default=str, ensure_ascii=False, sort_keys=True)


def decode(payload: str) -> DraftInvoice:
    data = json.loads(payload)
    totals = data.pop("totals")
    totals["lines"] = tuple(LineTotals(**row) for row in totals["lines"])
    data["lines"] = tuple(
        DraftLine(
            row["description"],
            Decimal(row["quantity"]),
            Decimal(row["unit_price"]),
            Decimal(row["gst_rate"]),
        )
        for row in data["lines"]
    )
    data["invoice_date"] = date.fromisoformat(data["invoice_date"])
    data["tax_mode"] = TaxMode(data["tax_mode"])
    return DraftInvoice(**data, totals=InvoiceTotals(**totals))


class SqlAlchemyDraftRepository:
    def __init__(self, session: Session):
        self._session = session

    def get(self, draft_id: str) -> DraftInvoice:
        row = self._session.get(DraftRecord, draft_id)
        if row is None or row.deleted:
            raise MissingError
        return decode(row.payload)

    def list(self, start: date, end: date) -> tuple[DraftInvoice, ...]:
        query = (
            select(DraftRecord)
            .where(
                DraftRecord.deleted.is_(False),
                DraftRecord.invoice_date >= start.isoformat(),
                DraftRecord.invoice_date <= end.isoformat(),
            )
            .order_by(DraftRecord.invoice_date.desc(), DraftRecord.id)
        )
        return tuple(decode(row.payload) for row in self._session.scalars(query))

    def save(self, draft: DraftInvoice, expected_revision: int) -> DraftInvoice:
        saved = replace(draft, revision=expected_revision + 1)
        values = {
            "revision": saved.revision,
            "invoice_date": saved.invoice_date.isoformat(),
            "payload": encode(saved),
        }
        if expected_revision == 0:
            self._session.add(DraftRecord(id=saved.id, deleted=False, **values))
            try:
                self._session.flush()
            except IntegrityError as error:
                raise ConflictError from error
        else:
            result = self._session.execute(
                update(DraftRecord)
                .where(
                    DraftRecord.id == saved.id,
                    DraftRecord.revision == expected_revision,
                    DraftRecord.deleted.is_(False),
                )
                .values(**values)
            )
            if result.rowcount != 1:
                raise ConflictError
        return saved

    def delete(self, draft_id: str, expected_revision: int) -> None:
        result = self._session.execute(
            update(DraftRecord)
            .where(
                DraftRecord.id == draft_id,
                DraftRecord.revision == expected_revision,
                DraftRecord.deleted.is_(False),
            )
            .values(deleted=True, revision=expected_revision + 1)
        )
        if result.rowcount != 1:
            raise ConflictError


class SqlAlchemyAuditLog:
    def __init__(self, session: Session):
        self._session = session

    def append(self, action: str, draft_id: str, revision: int) -> None:
        self._session.add(
            AuditRecord(
                id=str(uuid4()),
                action=action,
                draft_id=draft_id,
                revision=revision,
                occurred_at=datetime.now(UTC).isoformat(),
            )
        )


class SqlAlchemyDraftUnitOfWork:
    """One session/transaction per operation. Repositories never commit."""

    def __init__(self, engine):
        self._engine = engine

    def __enter__(self):
        self._session = Session(self._engine)
        self.drafts = SqlAlchemyDraftRepository(self._session)
        self.audit = SqlAlchemyAuditLog(self._session)
        return self

    def commit(self):
        try:
            self._session.commit()
        except SQLAlchemyError as error:
            raise StorageError from error

    def __exit__(self, exc_type, exc, traceback):
        self._session.close()  # Rolls back any transaction not committed.
        if isinstance(exc, SQLAlchemyError):
            raise StorageError from exc
