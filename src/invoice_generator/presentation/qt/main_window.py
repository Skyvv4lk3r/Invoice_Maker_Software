from datetime import date
from importlib.resources import as_file, files

from PySide6.QtCore import QDate, QFile, QIODevice
from PySide6.QtUiTools import QUiLoader
from PySide6.QtWidgets import (
    QAbstractItemView,
    QComboBox,
    QDateEdit,
    QHeaderView,
    QLabel,
    QLineEdit,
    QMainWindow,
    QMessageBox,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
)

from invoice_generator.application.contracts.dto import (
    DateRange,
    DraftInput,
    DraftReference,
    LineInput,
)
from invoice_generator.presentation.qt.tasks import QtTaskBridge
from invoice_generator.presentation.view_model import DraftViewModel, display_amount


class MainWindow(QMainWindow):
    def __init__(self, view_model: DraftViewModel):
        super().__init__()
        self.vm = view_model
        self.bridge = QtTaskBridge(self)
        resource = files("invoice_generator.presentation.qt").joinpath("forms/main_window.ui")
        with as_file(resource) as path:
            file = QFile(str(path))
            if not file.open(QIODevice.OpenModeFlag.ReadOnly):
                raise RuntimeError("Could not load the application form.")
            try:
                form = QUiLoader().load(file)
            finally:
                file.close()
        self.setCentralWidget(form)
        self.setWindowTitle("Invoice Generator — Draft workspace")
        self.resize(1200, 780)
        self.firm = form.findChild(QLineEdit, "firmName")
        self.customer = form.findChild(QLineEdit, "customerName")
        self.invoice_date = form.findChild(QDateEdit, "invoiceDate")
        self.start = form.findChild(QDateEdit, "startDate")
        self.end = form.findChild(QDateEdit, "endDate")
        self.mode = form.findChild(QComboBox, "taxMode")
        self.items = form.findChild(QTableWidget, "itemsTable")
        self.invoices = form.findChild(QTableWidget, "draftsTable")
        self.status = form.findChild(QLabel, "statusLabel")
        self.total = form.findChild(QLabel, "totalLabel")
        self.identity = form.findChild(QLabel, "identityLabel")
        self.reveal_button = form.findChild(QPushButton, "revealButton")
        self.mode.addItem("Choose draft tax split", "")
        self.mode.addItem("CGST + SGST", "CGST_SGST")
        self.mode.addItem("IGST", "IGST")
        today = date.today()
        self.invoice_date.setDate(QDate.currentDate())
        self.start.setDate(QDate(today.year, 1, 1))
        self.end.setDate(QDate(today.year, 12, 31))
        for field in (self.invoice_date, self.start, self.end):
            field.setDisplayFormat("yyyy-MM-dd")
            field.setCalendarPopup(True)
        self.items.setColumnCount(4)
        self.items.setHorizontalHeaderLabels(["Description", "Quantity", "Unit price", "GST %"])
        self.items.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        self.invoices.setColumnCount(3)
        self.invoices.setHorizontalHeaderLabels(["Date", "Customer", "Total"])
        self.invoices.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
        self.invoices.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.invoices.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        actions = {
            "newButton": self.new_draft,
            "saveButton": self.save,
            "calculateButton": self.calculate,
            "pdfButton": lambda: self.save(export_pdf=True),
            "deleteButton": self.delete,
            "refreshButton": self.refresh,
            "addItemButton": self.add_item,
            "removeItemButton": self.remove_item,
            "revealButton": self.reveal,
        }
        for name, action in actions.items():
            # Absorb clicked(bool); it is not the export_pdf argument of save().
            form.findChild(QPushButton, name).clicked.connect(
                lambda _checked=False, fn=action: fn()
            )
        self.invoices.cellDoubleClicked.connect(self.load_selected)
        self._rows = ()
        self._artifact_id = None
        self.reveal_button.setEnabled(False)
        self.add_item()
        self.refresh()

    def _run(self, operation, callback):
        self.centralWidget().setEnabled(False)
        self.status.setText("Working…")

        def finished(result):
            self.centralWidget().setEnabled(True)
            if result.error:
                error = result.error
                self.status.setText(f"{error.field + ': ' if error.field else ''}{error.message}")
                return
            callback(result.value)

        self.bridge.submit(operation, finished)

    def _input(self):
        def text(row, column):
            cell = self.items.item(row, column)
            return cell.text() if cell else ""

        return DraftInput(
            self.firm.text(),
            self.customer.text(),
            self.invoice_date.date().toString("yyyy-MM-dd"),
            self.mode.currentData(),
            tuple(
                LineInput(*(text(row, column) for column in range(4)))
                for row in range(self.items.rowCount())
            ),
        )

    def add_item(self):
        row = self.items.rowCount()
        self.items.insertRow(row)
        for column, value in enumerate(["", "1", "0.00", "0"]):
            self.items.setItem(row, column, QTableWidgetItem(value))

    def remove_item(self):
        row = self.items.currentRow()
        if row >= 0:
            self.items.removeRow(row)

    def new_draft(self):
        self.vm.current = None
        self.customer.clear()
        self.invoice_date.setDate(QDate.currentDate())
        self.mode.setCurrentIndex(0)
        self.items.setRowCount(0)
        self.add_item()
        self.total.setText("Save or calculate to see totals.")
        self.identity.setText("New draft — no invoice number")
        self.status.setText("New draft ready.")
        self.reveal_button.setEnabled(False)
        self._artifact_id = None

    def _show_totals(self, totals):
        self.total.setText(f"Total: {display_amount(totals.total_paise)}\n{totals.amount_in_words}")

    def calculate(self):
        data = self._input()

        def show(totals):
            self._show_totals(totals)
            self.status.setText("Draft totals calculated.")

        self._run(lambda: self.vm.queries.calculate(data), show)

    def save(self, export_pdf=False):
        request = self.vm.save_request(self._input())

        def saved(draft):
            self.vm.current = draft
            self.identity.setText(f"Saved draft — revision {draft.revision} — no invoice number")
            self._show_totals(draft.totals)
            self.reveal_button.setEnabled(False)
            if export_pdf:
                reference = DraftReference(draft.id, draft.revision)
                self._run(lambda: self.vm.pdfs.export(reference), self._pdf_ready)
            else:
                self.refresh(message="Draft saved.")

        self._run(lambda: self.vm.commands.save(request), saved)

    def _pdf_ready(self, artifact):
        self._artifact_id = artifact.id
        self.reveal_button.setEnabled(True)
        self.refresh(message=f"Draft PDF created: {artifact.display_name}")

    def reveal(self):
        artifact_id = self._artifact_id
        if artifact_id:
            self._run(
                lambda: self.vm.artifacts.reveal(artifact_id),
                lambda _: self.status.setText("Opened the export location."),
            )

    def refresh(self, message="Double-click a saved draft to edit it."):
        dates = DateRange(
            self.start.date().toString("yyyy-MM-dd"), self.end.date().toString("yyyy-MM-dd")
        )

        def show(rows):
            self._rows = rows
            self.invoices.setRowCount(len(rows))
            for index, row in enumerate(rows):
                for column, value in enumerate(
                    [row.invoice_date, row.customer_name, display_amount(row.total_paise)]
                ):
                    self.invoices.setItem(index, column, QTableWidgetItem(value))
            self.status.setText(message)

        self._run(lambda: self.vm.queries.list(dates), show)

    def load_selected(self, row, _column):
        draft_id = self._rows[row].id

        def show(draft):
            self.vm.current = draft
            self.firm.setText(draft.data.firm_name)
            self.customer.setText(draft.data.customer_name)
            self.invoice_date.setDate(QDate.fromString(draft.data.invoice_date, "yyyy-MM-dd"))
            self.mode.setCurrentIndex(self.mode.findData(draft.data.tax_mode))
            self.items.setRowCount(len(draft.data.lines))
            for index, line in enumerate(draft.data.lines):
                for column, value in enumerate(
                    [line.description, line.quantity, line.unit_price, line.gst_rate]
                ):
                    self.items.setItem(index, column, QTableWidgetItem(value))
            self.identity.setText(f"Saved draft — revision {draft.revision} — no invoice number")
            self._show_totals(draft.totals)
            self.reveal_button.setEnabled(False)
            self._artifact_id = None
            self.status.setText("Draft loaded.")

        self._run(lambda: self.vm.queries.get(draft_id), show)

    def delete(self):
        draft = self.vm.current
        if draft is None:
            self.status.setText("Load a saved draft first.")
            return
        answer = QMessageBox.question(
            self,
            "Delete draft",
            "Delete this draft from the active list? Its audit record will remain.",
        )
        if answer != QMessageBox.StandardButton.Yes:
            return
        request = DraftReference(draft.id, draft.revision)

        def deleted(_):
            self.new_draft()
            self.refresh(message="Draft deleted from the active list.")

        self._run(lambda: self.vm.commands.delete(request), deleted)

    def closeEvent(self, event):
        if self.bridge.busy:
            self.status.setText("Wait for the current operation before closing.")
            event.ignore()
        else:
            event.accept()
