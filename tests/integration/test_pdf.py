from dataclasses import replace
from pathlib import Path

from invoice_generator.application.contracts.dto import DraftReference, SaveDraftRequest
from invoice_generator.application.handlers.documents import DraftPdfService
from invoice_generator.infrastructure.documents.pdf import ReportLabDraftRenderer
from invoice_generator.infrastructure.files import LocalArtifactStore
from invoice_generator.infrastructure.persistence.repositories import SqlAlchemyDraftUnitOfWork


def test_pdf_export_and_stale_revision(backend, sample):
    data = replace(
        sample,
        customer_name="A & B <Example>",
        lines=tuple(
            replace(sample.lines[0], description=f"Item {i} <goods> & services") for i in range(80)
        ),
    )
    saved = backend.commands.save(SaveDraftRequest(data)).value
    artifact = backend.pdfs.export(DraftReference(saved.id, saved.revision)).value
    pdf = backend.directory / "exports" / artifact.display_name
    assert pdf.read_bytes().startswith(b"%PDF-")
    assert pdf.stat().st_size > 1000
    assert not tuple(pdf.parent.glob("*.tmp"))
    backend.commands.save(SaveDraftRequest(sample, saved.id, saved.revision))
    assert backend.pdfs.export(DraftReference(saved.id, saved.revision)).error.code == "CONFLICT"


def test_pdf_failure_does_not_change_saved_draft(backend, sample):
    saved = backend.commands.save(SaveDraftRequest(sample)).value

    class FailingStore:
        def publish_pdf(self, _data):
            raise OSError("disk unavailable")

    service = DraftPdfService(
        lambda: SqlAlchemyDraftUnitOfWork(backend._engine), ReportLabDraftRenderer(), FailingStore()
    )
    result = service.export(DraftReference(saved.id, saved.revision))
    assert result.error.code == "STORAGE_FAILURE"
    assert backend.queries.get(saved.id).value == saved


def test_artifacts_cannot_escape_the_export_directory(tmp_path):
    store = LocalArtifactStore(tmp_path)
    artifact = store.publish_pdf(b"%PDF-test")
    assert Path(artifact.display_name).name == artifact.display_name
    assert (tmp_path / artifact.display_name).read_bytes() == b"%PDF-test"
