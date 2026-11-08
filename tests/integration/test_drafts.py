from dataclasses import replace

from sqlalchemy import func, select

from invoice_generator.application.contracts.dto import DateRange, DraftReference, SaveDraftRequest
from invoice_generator.bootstrap import build_backend
from invoice_generator.infrastructure.persistence.models import AuditRecord, DraftRecord
from invoice_generator.infrastructure.persistence.repositories import SqlAlchemyDraftUnitOfWork


def test_save_reopen_update_and_conflict(backend, sample):
    first = backend.commands.save(SaveDraftRequest(sample)).value
    assert first.revision == 1
    assert first.totals.total_paise == 23600
    second_client = build_backend(backend.directory)
    try:
        loaded = second_client.queries.get(first.id).value
        updated = second_client.commands.save(
            SaveDraftRequest(replace(sample, customer_name="Updated"), loaded.id, loaded.revision)
        )
        assert updated.value.revision == 2
        stale = backend.commands.save(SaveDraftRequest(sample, first.id, first.revision))
        assert stale.error.code == "CONFLICT"
        assert backend.queries.get(first.id).value.data.customer_name == "Updated"
    finally:
        second_client.close()


def test_dates_are_inclusive_and_deletion_is_audited(backend, sample):
    ids = []
    for day in ["2026-03-31", "2026-04-01", "2026-04-30", "2026-05-01"]:
        ids.append(
            backend.commands.save(SaveDraftRequest(replace(sample, invoice_date=day))).value.id
        )
    rows = backend.queries.list(DateRange("2026-04-01", "2026-04-30")).value
    assert {row.id for row in rows} == {ids[1], ids[2]}
    assert backend.commands.delete(DraftReference(ids[1], 1)).value is True
    assert backend.queries.get(ids[1]).error.code == "NOT_FOUND"
    assert len(backend.queries.list(DateRange("2026-04-01", "2026-04-30")).value) == 1
    with backend._engine.connect() as connection:
        assert connection.scalar(select(func.count()).select_from(DraftRecord)) == 4
        assert connection.scalar(select(func.count()).select_from(AuditRecord)) == 5


def test_invalid_date_range_returns_typed_error(backend):
    assert backend.queries.list(DateRange("2026-05-01", "2026-04-01")).error.code == "VALIDATION"


def test_write_and_audit_roll_back_together(backend, sample):
    from uuid import uuid4

    from invoice_generator.application.handlers.drafts import build_draft

    draft = build_draft(sample, str(uuid4()), 0)
    with SqlAlchemyDraftUnitOfWork(backend._engine) as uow:
        uow.drafts.save(draft, 0)
        uow.audit.append("draft.saved", draft.id, 1)
        # Abandon before commit to simulate a failing later step.
    assert backend.queries.get(draft.id).error.code == "NOT_FOUND"
    with backend._engine.connect() as connection:
        assert connection.scalar(select(func.count()).select_from(AuditRecord)) == 0


def test_deleted_draft_cannot_be_resurrected_by_stale_save(backend, sample):
    draft = backend.commands.save(SaveDraftRequest(sample)).value
    backend.commands.delete(DraftReference(draft.id, draft.revision))
    result = backend.commands.save(SaveDraftRequest(sample, draft.id, draft.revision))
    assert result.error.code == "CONFLICT"
