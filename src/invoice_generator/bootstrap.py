"""Composition root: the sole place that chooses concrete screens and adapters."""

import argparse
import logging
import os
from dataclasses import dataclass
from datetime import date
from pathlib import Path

from platformdirs import user_data_path

from invoice_generator.application.contracts.dto import (
    DraftInput,
    DraftReference,
    LineInput,
    SaveDraftRequest,
)
from invoice_generator.application.contracts.interfaces import (
    IArtifactActions,
    IDraftPdfCommands,
    IInvoiceDraftCommands,
    IInvoiceQueries,
)
from invoice_generator.application.handlers.documents import DraftPdfService
from invoice_generator.application.handlers.drafts import DraftService
from invoice_generator.infrastructure.documents.pdf import ReportLabDraftRenderer
from invoice_generator.infrastructure.files import LocalArtifactStore
from invoice_generator.infrastructure.persistence.database import create_database
from invoice_generator.infrastructure.persistence.repositories import SqlAlchemyDraftUnitOfWork


@dataclass
class Backend:
    commands: IInvoiceDraftCommands
    queries: IInvoiceQueries
    pdfs: IDraftPdfCommands
    artifacts: IArtifactActions
    directory: Path
    _engine: object

    def close(self):
        self._engine.dispose()


def build_backend(directory: Path) -> Backend:
    directory = directory.expanduser().resolve()
    engine = create_database(directory / "invoices.db")

    def uow_factory():
        return SqlAlchemyDraftUnitOfWork(engine)

    drafts = DraftService(uow_factory)
    documents = DraftPdfService(
        uow_factory, ReportLabDraftRenderer(), LocalArtifactStore(directory / "exports")
    )
    return Backend(drafts, drafts, documents, documents, directory, engine)


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description="Invoice Generator development build")
    parser.add_argument("--data-dir", type=Path, help="Override local application data directory")
    parser.add_argument(
        "--demo", action="store_true", help="Save a fictional draft and PDF without Qt"
    )
    parser.add_argument(
        "--smoke", action="store_true", help="Open the desktop window and exit after startup"
    )
    args = parser.parse_args(argv)
    directory = args.data_dir or Path(
        os.environ.get(
            "INVOICE_GENERATOR_DATA_DIR", user_data_path("InvoiceGenerator", appauthor=False)
        )
    )
    logging.basicConfig(level=logging.WARNING)
    backend = build_backend(directory)
    try:
        if args.demo:
            saved = backend.commands.save(
                SaveDraftRequest(
                    DraftInput(
                        "Demo Firm",
                        "Sample Customer",
                        date.today().isoformat(),
                        "CGST_SGST",
                        (LineInput("Example goods", "2", "100.00", "18"),),
                    )
                )
            )
            if saved.error:
                print(saved.error.message)
                return 1
            artifact = backend.pdfs.export(DraftReference(saved.value.id, saved.value.revision))
            if artifact.error:
                print(artifact.error.message)
                return 1
            rupees, remainder = divmod(saved.value.totals.total_paise, 100)
            print(f"Saved draft {saved.value.id}; total INR {rupees}.{remainder:02d}")
            print(backend.directory / "exports" / artifact.value.display_name)
            return 0
        # Lazy GUI imports: backend-only installations never need PySide6.
        from PySide6.QtCore import QTimer
        from PySide6.QtWidgets import QApplication

        from invoice_generator.presentation.qt.main_window import MainWindow
        from invoice_generator.presentation.view_model import DraftViewModel

        app = QApplication.instance() or QApplication([])
        app.setApplicationName("Invoice Generator")
        window = MainWindow(
            DraftViewModel(backend.commands, backend.queries, backend.pdfs, backend.artifacts)
        )
        window.show()
        if args.smoke:
            QTimer.singleShot(250, window.close)
        return app.exec()
    finally:
        backend.close()
