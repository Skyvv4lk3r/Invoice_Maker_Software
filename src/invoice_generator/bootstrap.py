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
    IDateRangeExportCommands,
    IDraftPdfCommands,
    IDraftPreviewQueries,
    IInvoiceDraftCommands,
    IInvoiceQueries,
)
from invoice_generator.application.contracts.issuance import IInvoiceIssuance
from invoice_generator.application.contracts.workspace import (
    IAuthentication,
    IBackupCommands,
    ICustomerCatalog,
    IFirmSettings,
    IItemCatalog,
    ITemplateCatalog,
    OwnerSetup,
)
from invoice_generator.application.handlers.authentication import AuthenticationService
from invoice_generator.application.handlers.backups import BackupService
from invoice_generator.application.handlers.documents import DateRangeExportService, DraftPdfService
from invoice_generator.application.handlers.drafts import DraftService
from invoice_generator.application.handlers.issuance import IssuanceService
from invoice_generator.application.handlers.secured import AuthorizedCapability
from invoice_generator.application.handlers.workspace import (
    CustomerService,
    FirmService,
    ItemService,
    TemplateService,
)
from invoice_generator.infrastructure.backups import EncryptedBackupStore
from invoice_generator.infrastructure.documents.bundle import DraftBundleRenderer
from invoice_generator.infrastructure.documents.pdf import ReportLabDraftRenderer
from invoice_generator.infrastructure.documents.word import WordDraftRenderer
from invoice_generator.infrastructure.files import LocalArtifactStore
from invoice_generator.infrastructure.images import LogoNormalizer
from invoice_generator.infrastructure.persistence.database import create_database
from invoice_generator.infrastructure.persistence.issuance import IssuedStore
from invoice_generator.infrastructure.persistence.repositories import SqlAlchemyDraftUnitOfWork
from invoice_generator.infrastructure.persistence.workspace import (
    CatalogStore,
    FirmStore,
    IdentityStore,
    TemplateStore,
)
from invoice_generator.infrastructure.security import ArgonPasswordHasher


@dataclass
class Backend:
    commands: IInvoiceDraftCommands
    queries: IInvoiceQueries
    pdfs: IDraftPdfCommands
    artifacts: IArtifactActions
    directory: Path
    _engine: object
    words: IDraftPdfCommands
    previews: IDraftPreviewQueries
    range_exports: IDateRangeExportCommands
    auth: IAuthentication
    firm: IFirmSettings
    templates: ITemplateCatalog
    customers: ICustomerCatalog
    items: IItemCatalog
    backups: IBackupCommands
    issued: IInvoiceIssuance

    def close(self):
        self._engine.dispose()


def build_backend(directory: Path) -> Backend:
    directory = directory.expanduser().resolve()
    engine = create_database(directory / "invoices.db")

    def uow_factory():
        return SqlAlchemyDraftUnitOfWork(engine)

    authentication = AuthenticationService(IdentityStore(engine), ArgonPasswordHasher())
    templates, firms = TemplateStore(engine), FirmStore(engine)
    drafts = DraftService(uow_factory, templates)
    store = LocalArtifactStore(directory / "exports")
    pdf, word = ReportLabDraftRenderer(), WordDraftRenderer()
    documents = DraftPdfService(uow_factory, pdf, store, templates=templates)
    words = DraftPdfService(uow_factory, word, store, "docx", templates)
    bundles = DraftBundleRenderer(pdf, word)
    ranges = DateRangeExportService(uow_factory, bundles, store, templates)
    issuance = IssuanceService(
        uow_factory, IssuedStore(engine), firms, templates, pdf, word, bundles, store
    )

    def secure(service, *methods):
        return AuthorizedCapability(service, authentication, methods)

    return Backend(
        commands=secure(drafts, "save", "delete"),
        queries=secure(drafts, "get", "list", "calculate"),
        pdfs=secure(documents, "export"),
        artifacts=secure(documents, "reveal"),
        directory=directory,
        _engine=engine,
        words=secure(words, "export"),
        previews=secure(documents, "preview"),
        range_exports=secure(ranges, "export_range"),
        auth=authentication,
        firm=secure(FirmService(firms, templates), "get", "save", "audit"),
        templates=secure(
            TemplateService(templates, LogoNormalizer(), pdf),
            "list",
            "save",
            "normalize_logo",
            "import_layout",
            "export_layout",
            "preview",
        ),
        customers=secure(
            CustomerService(CatalogStore(engine, "customer")), "list", "save", "delete"
        ),
        items=secure(ItemService(CatalogStore(engine, "item")), "list", "save", "delete"),
        backups=secure(BackupService(EncryptedBackupStore(directory)), "create", "restore_copy"),
        issued=secure(
            issuance, "issue", "list", "get", "export", "cancel", "export_range", "preview"
        ),
    )


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
            import secrets

            state = backend.auth.state().value
            if state.configured:
                print(
                    "Demo requires a new empty data directory; existing workspaces require sign-in."
                )
                return 1
            backend.auth.setup(OwnerSetup("Demo Firm", "demo-owner", secrets.token_urlsafe(24)))
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

        from invoice_generator.presentation.qt.authentication import AuthenticationDialog
        from invoice_generator.presentation.qt.main_window import MainWindow
        from invoice_generator.presentation.view_model import DraftViewModel

        app = QApplication.instance() or QApplication([])
        app.setApplicationName("Invoice Generator")
        while True:
            login = AuthenticationDialog(backend.auth, allow_workspace=True)
            if args.smoke:
                QTimer.singleShot(250, login.reject)
            outcome = login.exec()
            if login.workspace_path:
                replacement = build_backend(Path(login.workspace_path))
                backend.close()
                backend = replacement
                continue
            if outcome != login.DialogCode.Accepted:
                return 0
            break
        window = MainWindow(
            DraftViewModel(
                backend.commands,
                backend.queries,
                backend.pdfs,
                backend.artifacts,
                backend.words,
                backend.previews,
                backend.range_exports,
                auth=backend.auth,
                firm=backend.firm,
                templates=backend.templates,
                customers=backend.customers,
                items=backend.items,
                backups=backend.backups,
                issued=backend.issued,
            )
        )
        window.show()
        if args.smoke:
            QTimer.singleShot(250, window.close)
        return app.exec()
    finally:
        backend.close()
