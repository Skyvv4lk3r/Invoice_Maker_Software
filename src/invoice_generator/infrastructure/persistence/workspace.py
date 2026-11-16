import json
from contextlib import contextmanager
from dataclasses import asdict, replace
from uuid import uuid4

from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError, SQLAlchemyError
from sqlalchemy.orm import Session

from invoice_generator.application.contracts.dto import PartyDetails
from invoice_generator.application.contracts.workspace import (
    AuditEntry,
    CustomerRecord,
    FirmProfile,
    InvoiceLayout,
    ItemRecord,
    TemplateVersion,
)
from invoice_generator.application.ports.persistence import (
    ConflictError,
    MissingError,
    StorageError,
)
from invoice_generator.application.ports.workspace import OwnerCredentials
from invoice_generator.domain.models import ValidationError
from invoice_generator.infrastructure.persistence.models import (
    AuditRecord,
    IssuedRecord,
    OwnerRecord,
    TemplateRecord,
    WorkspaceRecord,
)
from invoice_generator.infrastructure.persistence.repositories import SqlAlchemyAuditLog


@contextmanager
def transaction(engine, write=False):
    try:
        with engine.connect().execution_options(immediate=write) as connection, connection.begin():
            with Session(bind=connection) as session:
                yield session
                session.flush()
    except IntegrityError as error:
        raise ConflictError from error
    except SQLAlchemyError as error:
        raise StorageError from error


def decode_layout(payload):
    data = json.loads(payload) if isinstance(payload, str) else dict(payload)
    for key in ("columns", "section_order"):
        if key in data:
            data[key] = tuple(data[key])
    return InvoiceLayout(**data)


class IdentityStore:
    def __init__(self, engine):
        self.engine = engine

    def get_owner(self):
        with transaction(self.engine) as session:
            row = session.get(OwnerRecord, 1)
            return (
                None
                if row is None
                else OwnerCredentials(
                    row.username,
                    row.password_hash,
                    row.recovery_hash,
                    row.epoch,
                    row.failures,
                    float(row.locked_until),
                )
            )

    def create_owner(self, owner, firm):
        with transaction(self.engine, True) as session:
            session.add(
                OwnerRecord(id=1, **{**asdict(owner), "locked_until": str(owner.locked_until)})
            )
            session.add(
                WorkspaceRecord(
                    kind="firm",
                    id="main",
                    revision=1,
                    payload=json.dumps(asdict(firm)),
                    deleted=False,
                )
            )
            SqlAlchemyAuditLog(session).append("owner.created", "owner", 1)

    def record_attempt(self, expected_epoch, success, now):
        with transaction(self.engine, True) as session:
            owner = session.get(OwnerRecord, 1)
            if owner is None or owner.epoch != expected_epoch:
                raise ConflictError
            if success:
                owner.failures, owner.locked_until = 0, "0"
            else:
                owner.failures += 1
                if owner.failures >= 5:
                    owner.locked_until = str(now + 300)
                    owner.failures = 0
            SqlAlchemyAuditLog(session).append(
                "owner.login" if success else "owner.login_failed", "owner", owner.epoch
            )

    def replace_credentials(self, expected_epoch, password_hash, recovery_hash):
        with transaction(self.engine, True) as session:
            owner = session.get(OwnerRecord, 1)
            if owner is None or owner.epoch != expected_epoch:
                raise ConflictError
            owner.password_hash, owner.recovery_hash = password_hash, recovery_hash
            owner.epoch += 1
            owner.failures, owner.locked_until = 0, "0"
            SqlAlchemyAuditLog(session).append("owner.credentials_changed", "owner", owner.epoch)


class FirmStore:
    def __init__(self, engine):
        self.engine = engine

    def get(self):
        with transaction(self.engine) as session:
            row = session.get(WorkspaceRecord, ("firm", "main"))
            if row is None:
                raise MissingError
            data = json.loads(row.payload)
            data["details"] = PartyDetails(**data["details"])
            return FirmProfile(**data)

    def save(self, profile):
        with transaction(self.engine, True) as session:
            row = session.get(WorkspaceRecord, ("firm", "main"))
            if row is None or row.revision != profile.revision:
                raise ConflictError
            old_gstin = json.loads(row.payload)["details"]["gstin"]
            if old_gstin != profile.details.gstin and session.scalar(
                select(IssuedRecord.id).limit(1)
            ):
                raise ValidationError("gstin", "A workspace with issued invoices keeps its GSTIN.")
            result = replace(profile, revision=profile.revision + 1)
            row.revision, row.payload = result.revision, json.dumps(asdict(result))
            SqlAlchemyAuditLog(session).append("firm.saved", "main", result.revision)
            return result

    def audit(self):
        with transaction(self.engine) as session:
            rows = session.scalars(
                select(AuditRecord).order_by(AuditRecord.occurred_at.desc()).limit(500)
            )
            return tuple(AuditEntry(x.action, x.draft_id, x.revision, x.occurred_at) for x in rows)


BUILTINS = {
    "modern": TemplateVersion("modern", 1, InvoiceLayout(name="Modern")),
    "classic": TemplateVersion(
        "classic", 1, InvoiceLayout(name="Classic", accent="303C4B", tint="F0F1F3")
    ),
}


class TemplateStore:
    def __init__(self, engine):
        self.engine = engine

    def list(self):
        with transaction(self.engine) as session:
            latest = dict(BUILTINS)
            for row in session.scalars(select(TemplateRecord).order_by(TemplateRecord.version)):
                latest[row.id] = TemplateVersion(row.id, row.version, decode_layout(row.payload))
            return tuple(latest.values())

    def get(self, template_id, version=None):
        if template_id in BUILTINS:
            return BUILTINS[template_id]
        with transaction(self.engine) as session:
            query = select(TemplateRecord).where(TemplateRecord.id == template_id)
            if version is not None:
                query = query.where(TemplateRecord.version == version)
            row = session.scalars(query.order_by(TemplateRecord.version.desc())).first()
            if row is None:
                raise MissingError
            return TemplateVersion(row.id, row.version, decode_layout(row.payload))

    def save(self, template, expected_version):
        with transaction(self.engine, True) as session:
            current = (
                session.scalar(
                    select(func.max(TemplateRecord.version)).where(TemplateRecord.id == template.id)
                )
                or 0
            )
            if current != expected_version:
                raise ConflictError
            saved = replace(template, version=current + 1)
            session.add(
                TemplateRecord(
                    id=saved.id, version=saved.version, payload=json.dumps(asdict(saved.layout))
                )
            )
            SqlAlchemyAuditLog(session).append("template.saved", saved.id, saved.version)
            return saved


class CatalogStore:
    def __init__(self, engine, kind):
        self.engine, self.kind = engine, kind

    def _decode(self, row):
        data = json.loads(row.payload)
        if self.kind == "customer":
            data["details"] = PartyDetails(**data["details"])
            return CustomerRecord(**data)
        return ItemRecord(**data)

    def list(self):
        with transaction(self.engine) as session:
            rows = session.scalars(
                select(WorkspaceRecord).where(
                    WorkspaceRecord.kind == self.kind, WorkspaceRecord.deleted.is_(False)
                )
            )
            return tuple(self._decode(x) for x in rows)

    def save(self, record):
        record_id = record.id or str(uuid4())
        with transaction(self.engine, True) as session:
            row = session.get(WorkspaceRecord, (self.kind, record_id))
            if row is None:
                if record.revision != 0:
                    raise ConflictError
                row = WorkspaceRecord(
                    kind=self.kind, id=record_id, revision=0, payload="", deleted=False
                )
                session.add(row)
            elif row.deleted or row.revision != record.revision:
                raise ConflictError
            saved = replace(record, id=record_id, revision=record.revision + 1)
            row.revision, row.payload = saved.revision, json.dumps(asdict(saved))
            SqlAlchemyAuditLog(session).append(self.kind + ".saved", record_id, saved.revision)
            return saved

    def delete(self, record_id, revision):
        with transaction(self.engine, True) as session:
            row = session.get(WorkspaceRecord, (self.kind, record_id))
            if row is None or row.deleted or row.revision != revision:
                raise ConflictError
            row.deleted, row.revision = True, revision + 1
            SqlAlchemyAuditLog(session).append(self.kind + ".deleted", record_id, row.revision)
