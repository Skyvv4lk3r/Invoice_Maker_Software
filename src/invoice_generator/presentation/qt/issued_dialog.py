from PySide6.QtCore import QBuffer, QByteArray, QIODevice
from PySide6.QtPdf import QPdfDocument
from PySide6.QtPdfWidgets import QPdfView
from PySide6.QtWidgets import QHBoxLayout, QInputDialog, QLabel, QMessageBox, QPushButton

from invoice_generator.presentation.qt.workspace_dialogs import ServiceDialog


class IssuedDialog(ServiceDialog):
    def __init__(self, service, artifacts, invoice, parent=None):
        super().__init__(f"Invoice {invoice.number}", parent)
        self.resize(900, 850)
        self.service, self.artifacts, self.invoice = service, artifacts, invoice
        self.info = QLabel()
        self.body.addWidget(self.info)
        self.pdf = QPdfDocument(self)
        self.buffer = QBuffer(self)
        self.view = QPdfView()
        self.view.setDocument(self.pdf)
        self.view.setPageMode(QPdfView.PageMode.MultiPage)
        self.view.setZoomMode(QPdfView.ZoomMode.FitInView)
        self.body.addWidget(self.view)
        actions = QHBoxLayout()
        for label, action in (
            ("Export PDF", lambda: self.export("pdf")),
            ("Export Word", lambda: self.export("docx")),
            ("Cancel invoice", self.cancel),
        ):
            button = QPushButton(label)
            button.clicked.connect(action)
            actions.addWidget(button)
        self.body.addLayout(actions)
        self.refresh()

    def refresh(self):
        self.info.setText(
            f"{self.invoice.status} · {self.invoice.model.customer_name} · "
            f"{self.invoice.model.invoice_date} · Financial year "
            f"{self.invoice.financial_year}–{self.invoice.financial_year + 1}"
        )

        def show(content):
            self.pdf.close()
            self.buffer.close()
            self.buffer.setData(QByteArray(content))
            self.buffer.open(QIODevice.OpenModeFlag.ReadOnly)
            self.pdf.load(self.buffer)

        invoice_id = self.invoice.id
        self.run(lambda: self.service.preview(invoice_id), show)

    def export(self, format):
        invoice_id = self.invoice.id

        def ready(artifact):
            self.run(
                lambda: self.artifacts.reveal(artifact.id),
                lambda _: self.status.setText("Export ready: " + artifact.display_name),
            )

        self.run(lambda: self.service.export(invoice_id, format), ready)

    def cancel(self):
        if self.invoice.status == "CANCELLED":
            self.status.setText("This invoice is already cancelled.")
            return
        reason, accepted = QInputDialog.getMultiLineText(
            self,
            "Cancellation reason",
            (
                "Provide the reason. This retains the number and original invoice; "
                "it does not update the GST portal or replace any required credit "
                "note."
            ),
        )
        if not accepted:
            return
        if (
            QMessageBox.question(
                self,
                "Cancel invoice",
                f"Mark invoice {self.invoice.number} as cancelled? The number will not be reused.",
            )
            != QMessageBox.StandardButton.Yes
        ):
            return
        invoice_id = self.invoice.id

        def cancelled(invoice):
            self.invoice = invoice
            self.refresh()

        self.run(lambda: self.service.cancel(invoice_id, reason), cancelled)
