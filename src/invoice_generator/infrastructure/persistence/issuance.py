import json
from dataclasses import asdict, replace
from uuid import uuid4

from sqlalchemy import select

from invoice_generator.application.contracts.dto import (
    DraftPdfModel,
    LineTotalsDTO,
    PartyDetails,
    PdfLine,
    TotalsDTO,
)
from invoice_generator.application.contracts.issuance import IssuedInvoice
from invoice_generator.application.ports.persistence import ConflictError, MissingError
from invoice_generator.domain.models import ValidationError
from invoice_generator.infrastructure.persistence.models import (
    DraftRecord,
    InvoiceCounter,
    IssuedRecord,
    RenderJob,
    WorkspaceRecord,
)
from invoice_generator.infrastructure.persistence.repositories import SqlAlchemyAuditLog
from invoice_generator.infrastructure.persistence.workspace import decode_layout, transaction


def decode_model(payload):
    data = json.loads(payload)
    data["firm_details"] = PartyDetails(**data["firm_details"])
    data["customer_details"] = PartyDetails(**data["customer_details"])
    data["lines"] = tuple(PdfLine(**x) for x in data["lines"])
    data["totals"]["lines"] = tuple(LineTotalsDTO(**x) for x in data["totals"]["lines"])
    data["totals"] = TotalsDTO(**data["totals"])
    data["layout"] = decode_layout(data["layout"])
    return DraftPdfModel(**data)


def issued_dto(row):
    model = replace(decode_model(row.payload), status=row.status)
    return IssuedInvoice(
        row.id, row.draft_id, row.financial_year, row.number, row.status, model, row.reason
    )


class IssuedStore:
    def __init__(self, engine):
        self.engine = engine

    def issue(
        self,
        draft_id,
        expected_revision,
        request_id,
        request_hash,
        financial_year,
        model,
        firm_revision,
    ):
        with transaction(self.engine, True) as session:
            retry = session.scalars(
                select(IssuedRecord).where(IssuedRecord.request_id == request_id)
            ).first()
            if retry:
                if retry.request_hash != request_hash:
                    raise ConflictError
                return issued_dto(retry)
            if session.scalars(
                select(IssuedRecord).where(IssuedRecord.draft_id == draft_id)
            ).first():
                raise ValidationError("invoice", "This draft has already been issued.")
            draft = session.get(DraftRecord, draft_id)
            if draft is None or draft.deleted or draft.revision != expected_revision:
                raise ConflictError
            firm = session.get(WorkspaceRecord, ("firm", "main"))
            if firm is None or firm.revision != firm_revision:
                raise ConflictError
            counter = session.get(InvoiceCounter, financial_year)
            if counter is None:
                counter = InvoiceCounter(financial_year=financial_year, next_number=1)
                session.add(counter)
            number = counter.next_number
            if number > 9_999_999_999_999_999:
                raise ValidationError("number", "The invoice number exceeds 16 digits.")
            counter.next_number += 1
            frozen = replace(model, invoice_number=number, status="ISSUED")
            invoice_id = str(uuid4())
            row = IssuedRecord(
                id=invoice_id,
                draft_id=draft_id,
                request_id=request_id,
                request_hash=request_hash,
                financial_year=financial_year,
                number=number,
                invoice_date=model.invoice_date,
                status="ISSUED",
                payload=json.dumps(asdict(frozen)),
                reason="",
            )
            session.add(row)
            session.add(
                RenderJob(invoice_id=invoice_id, state="PENDING", artifact_id="", artifact_name="")
            )
            SqlAlchemyAuditLog(session).append("invoice.issued", invoice_id, number)
            return issued_dto(row)

    def get(self, invoice_id):
        with transaction(self.engine) as session:
            row = session.get(IssuedRecord, invoice_id)
            if row is None:
                raise MissingError
            return issued_dto(row)

    def for_draft(self, draft_id):
        with transaction(self.engine) as session:
            row = session.scalars(
                select(IssuedRecord).where(IssuedRecord.draft_id == draft_id)
            ).first()
            return issued_dto(row) if row else None

    def list(self, start, end):
        with transaction(self.engine) as session:
            rows = session.scalars(
                select(IssuedRecord)
                .where(IssuedRecord.invoice_date >= start, IssuedRecord.invoice_date <= end)
                .order_by(IssuedRecord.invoice_date.desc(), IssuedRecord.number.desc())
            )
            return tuple(issued_dto(x) for x in rows)

    def cancel(self, invoice_id, reason):
        with transaction(self.engine, True) as session:
            row = session.get(IssuedRecord, invoice_id)
            if row is None:
                raise MissingError
            if row.status == "CANCELLED":
                return issued_dto(row)
            row.status, row.reason = "CANCELLED", reason
            job = session.get(RenderJob, invoice_id)
            job.state, job.artifact_id, job.artifact_name = "PENDING", "", ""
            SqlAlchemyAuditLog(session).append("invoice.cancelled", invoice_id, row.number)
            return issued_dto(row)

    def rendered(self, invoice_id, artifact, expected_status):
        with transaction(self.engine, True) as session:
            if session.get(IssuedRecord, invoice_id).status != expected_status:
                raise ConflictError
            job = session.get(RenderJob, invoice_id)
            job.state, job.artifact_id, job.artifact_name = (
                "READY",
                artifact.id,
                artifact.display_name,
            )
