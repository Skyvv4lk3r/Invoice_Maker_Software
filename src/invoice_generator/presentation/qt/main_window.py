import time
from dataclasses import replace
from datetime import date
from importlib.resources import as_file, files
from uuid import uuid4

from PySide6.QtCore import (
    QBuffer,
    QByteArray,
    QDate,
    QEvent,
    QFile,
    QIODevice,
    QSignalBlocker,
    Qt,
    QTimer,
)
from PySide6.QtGui import QAction, QColor, QKeySequence
from PySide6.QtPdf import QPdfDocument
from PySide6.QtPdfWidgets import QPdfView
from PySide6.QtUiTools import QUiLoader
from PySide6.QtWidgets import (
    QAbstractItemView,
    QApplication,
    QCheckBox,
    QComboBox,
    QDateEdit,
    QDialog,
    QHeaderView,
    QInputDialog,
    QLabel,
    QLineEdit,
    QMainWindow,
    QMenu,
    QMessageBox,
    QPlainTextEdit,
    QPushButton,
    QStackedWidget,
    QTableWidget,
    QTableWidgetItem,
    QTabWidget,
    QWidget,
)

from invoice_generator.application.contracts.dto import (
    DateRange,
    DraftInput,
    DraftReference,
    LineInput,
    PartyDetails,
)
from invoice_generator.application.contracts.issuance import IssueRequest
from invoice_generator.presentation.qt.authentication import AuthenticationDialog
from invoice_generator.presentation.qt.issued_dialog import IssuedDialog
from invoice_generator.presentation.qt.tasks import QtTaskBridge
from invoice_generator.presentation.qt.template_designer import TemplateDesigner
from invoice_generator.presentation.qt.workspace_dialogs import (
    BackupDialog,
    CatalogDialog,
    FirmDialog,
    SecurityDialog,
)
from invoice_generator.presentation.view_model import DraftViewModel, display_amount


class MainWindow(QMainWindow):
    def __init__(self, view_model: DraftViewModel):
        super().__init__()
        self.vm = view_model
        self.bridge = QtTaskBridge(self)
        self._loading = True
        self._firm_profile = None
        self._locking = False
        self._last_touch = 0
        self._dirty = False
        self._generation = 0
        self._exclusive = False
        self._artifact_id = None
        self._all_rows = self._rows = ()
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
        self.setStyleSheet(
            files("invoice_generator.presentation.qt").joinpath("styles/workspace.qss").read_text()
        )
        self.setWindowTitle("invo. — Invoice workspace")
        self.resize(1440, 960)
        self.setMinimumSize(1080, 720)
        self.firm = self.find(QLineEdit, "firmName")
        self.customer = self.find(QLineEdit, "customerName")
        self.invoice_date = self.find(QDateEdit, "invoiceDate")
        self.start, self.end = self.find(QDateEdit, "startDate"), self.find(QDateEdit, "endDate")
        self.due = self.find(QDateEdit, "dueDate")
        self.due_enabled = self.find(QCheckBox, "dueEnabled")
        self.mode, self.template = self.find(QComboBox, "taxMode"), self.find(QComboBox, "template")
        self.items, self.invoices = (
            self.find(QTableWidget, "itemsTable"),
            self.find(QTableWidget, "draftsTable"),
        )
        self.status, self.total = self.find(QLabel, "statusLabel"), self.find(QLabel, "totalLabel")
        self.identity = self.find(QLabel, "identityLabel")
        self.reveal_button = self.find(QPushButton, "revealButton")
        self.pages, self.tabs = (
            self.find(QStackedWidget, "pages"),
            self.find(QTabWidget, "editorTabs"),
        )
        self.search = self.find(QLineEdit, "search")
        self.record_type = self.find(QComboBox, "recordType")
        self.record_type.addItem("Drafts", "drafts")
        self.record_type.addItem("Issued invoices", "issued")
        self.record_type.currentIndexChanged.connect(lambda: self.refresh())
        self.mode.addItem("Choose tax split", "")
        self.mode.addItem("CGST + SGST", "CGST_SGST")
        self.mode.addItem("IGST", "IGST")
        self.template.addItem("Modern · Forest", "modern")
        self.template.addItem("Classic · Slate", "classic")
        today = date.today()
        fy = today.year if today.month >= 4 else today.year - 1
        self.start.setDate(QDate(fy, 4, 1))
        self.end.setDate(QDate(fy + 1, 3, 31))
        self.invoice_date.setDate(QDate.currentDate())
        self.due.setDate(QDate.currentDate().addDays(30))
        self.due.setEnabled(False)
        for field in (self.invoice_date, self.start, self.end, self.due):
            field.setDisplayFormat("dd MMM yyyy")
            field.setCalendarPopup(True)
        self.items.setColumnCount(8)
        self.items.setHorizontalHeaderLabels(
            [
                "DESCRIPTION",
                "QTY",
                "UNIT PRICE",
                "GST %",
                "TYPE",
                "HSN / SAC",
                "UNIT",
                "TOTAL (INR)",
            ]
        )
        self.items.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        for column, width in enumerate([240, 65, 100, 60, 95, 85, 65, 110]):
            self.items.setColumnWidth(column, width)
        self.items.verticalHeader().setDefaultSectionSize(46)
        self.invoices.setColumnCount(5)
        self.invoices.setHorizontalHeaderLabels(
            ["CUSTOMER", "DATE", "REFERENCE", "STATUS", "TOTAL"]
        )
        self.invoices.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        for column, width in [(1, 145), (2, 170), (3, 110), (4, 170)]:
            self.invoices.setColumnWidth(column, width)
        self.invoices.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.invoices.verticalHeader().setDefaultSectionSize(56)
        for table in (self.items, self.invoices):
            table.verticalHeader().hide()
            table.setShowGrid(False)
            table.setAlternatingRowColors(True)
            table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
            table.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self.pdf_document = QPdfDocument(self)
        self.pdf_view = QPdfView(self)
        self.pdf_view.setDocument(self.pdf_document)
        self.pdf_view.setPageMode(QPdfView.PageMode.MultiPage)
        self.pdf_view.setZoomMode(QPdfView.ZoomMode.FitInView)
        zoom = self.find(QComboBox, "previewZoom")
        zoom.addItem("Whole page", QPdfView.ZoomMode.FitInView)
        zoom.addItem("Page width", QPdfView.ZoomMode.FitToWidth)
        zoom.currentIndexChanged.connect(lambda: self.pdf_view.setZoomMode(zoom.currentData()))
        self.find(QWidget, "pdfContainer").layout().addWidget(self.pdf_view)
        self.pdf_buffer = QBuffer(self)
        self.auto_timer = QTimer(self)
        self.auto_timer.setSingleShot(True)
        self.auto_timer.setInterval(450)
        self.auto_timer.timeout.connect(self._auto_calculate)
        actions = {
            "newButton": self.new_draft,
            "composeButton": self.new_draft,
            "libraryButton": self.show_library,
            "backButton": self.show_library,
            "saveButton": self.save,
            "calculateButton": self.calculate,
            "deleteButton": self.delete,
            "refreshButton": self.refresh,
            "addItemButton": self.add_item,
            "removeItemButton": self.remove_item,
            "revealButton": self.reveal,
            "previewButton": self.preview,
            "refreshPreviewButton": self.preview,
            "bundleButton": self.export_range,
            "openButton": self.open_selected,
            "firmSettingsButton": self.open_firm_settings,
            "customersButton": lambda: self.open_catalog("customer"),
            "catalogButton": lambda: self.open_catalog("item"),
            "designerButton": self.open_designer,
            "backupButton": self.open_backups,
            "securityButton": self.open_security,
            "lockButton": self.lock_workspace,
            "pickCustomerButton": self.pick_customer,
            "pickItemButton": self.pick_item,
            "issueButton": self.issue_invoice,
        }
        for name, action in actions.items():
            self.find(QPushButton, name).clicked.connect(lambda _checked=False, fn=action: fn())
        export_menu = QMenu(self)
        export_menu.addAction("Save & export PDF", lambda: self.save(export_pdf=True))
        word_action = export_menu.addAction(
            "Save & export Word (.docx)", lambda: self.save(export_word=True)
        )
        word_action.setEnabled(self.vm.words is not None)
        self.find(QPushButton, "exportButton").setMenu(export_menu)
        self.find(QPushButton, "bundleButton").setEnabled(self.vm.range_exports is not None)
        for name in ("previewButton", "refreshPreviewButton"):
            self.find(QPushButton, name).setEnabled(self.vm.previews is not None)
        self.invoices.cellDoubleClicked.connect(self.load_selected)
        self.search.textChanged.connect(self._filter_rows)
        for prefix in ("firm", "customer"):
            panel = self.find(QWidget, prefix + "ExtraDetails")
            panel.hide()
            self.find(QPushButton, prefix + "DetailsToggle").toggled.connect(panel.setVisible)
            for suffix in ("Name", "Gstin", "State", "Email", "Phone"):
                self.find(QLineEdit, prefix + suffix).textChanged.connect(self._edited)
            self.find(QPlainTextEdit, prefix + "Address").textChanged.connect(self._edited)
        for name in ("reference", "placeOfSupply"):
            self.find(QLineEdit, name).textChanged.connect(self._edited)
        for name in ("notes", "terms"):
            self.find(QPlainTextEdit, name).textChanged.connect(self._edited)
        self.items.itemChanged.connect(self._edited)
        for field in (self.invoice_date, self.due):
            field.dateChanged.connect(self._edited)
        for field in (self.mode, self.template):
            field.currentIndexChanged.connect(self._edited)
        self.due_enabled.toggled.connect(self.due.setEnabled)
        self.due_enabled.toggled.connect(self._edited)
        for key, action in [
            (QKeySequence.StandardKey.Save, self.save),
            (QKeySequence.StandardKey.New, self.new_draft),
        ]:
            shortcut = QAction(self)
            shortcut.setShortcut(QKeySequence(key))
            shortcut.triggered.connect(lambda _checked=False, fn=action: fn())
            self.addAction(shortcut)
        self.add_item()
        self._loading = False
        self._baseline = self._input()
        self.reveal_button.setEnabled(False)
        self._set_page(0)
        self.lock_timer = QTimer(self)
        self.lock_timer.setInterval(10000)
        self.lock_timer.timeout.connect(self.check_lock)
        if self.vm.auth:
            QApplication.instance().installEventFilter(self)
            self.lock_timer.start()
            self.load_workspace_defaults()
        else:
            for name in (
                "firmSettingsButton",
                "customersButton",
                "catalogButton",
                "designerButton",
                "backupButton",
                "securityButton",
                "lockButton",
                "issueButton",
                "pickCustomerButton",
                "pickItemButton",
            ):
                self.find(QPushButton, name).hide()
            self.record_type.hide()
            self.refresh()

    def find(self, kind, name):
        widget = self.centralWidget().findChild(kind, name)
        if widget is None:
            raise RuntimeError(f"Missing interface element: {name}")
        return widget

    def _status(self, message, error=False):
        self.status.setText(message)
        self.status.setProperty("error", error)
        self.status.style().unpolish(self.status)
        self.status.style().polish(self.status)

    def _set_page(self, index):
        self.pages.setCurrentIndex(index)
        self.find(QLabel, "pageTitle").setText("Sales invoices" if index == 0 else "Invoice editor")
        for name, active in (("libraryButton", index == 0), ("composeButton", index == 1)):
            button = self.find(QPushButton, name)
            button.setProperty("active", active)
            button.style().unpolish(button)
            button.style().polish(button)

    def _run(self, operation, callback):
        self.auto_timer.stop()
        self._exclusive = True
        self.centralWidget().setEnabled(False)
        self._status("Working…")

        def finished(result):
            self._exclusive = False
            self.centralWidget().setEnabled(True)
            if result.error:
                error = result.error
                if error.code == "AUTH_REQUIRED" and self.vm.auth:
                    QTimer.singleShot(0, self.lock_workspace)
                self._status(f"{error.field + ': ' if error.field else ''}{error.message}", True)
                return
            callback(result.value)

        self.bridge.submit(operation, finished)

    def _party_input(self, prefix):
        return PartyDetails(
            self.find(QPlainTextEdit, prefix + "Address").toPlainText(),
            self.find(QLineEdit, prefix + "Gstin").text(),
            self.find(QLineEdit, prefix + "State").text(),
            self.find(QLineEdit, prefix + "Email").text(),
            self.find(QLineEdit, prefix + "Phone").text(),
        )

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
                LineInput(
                    *(text(row, column) for column in range(4)),
                    self.items.cellWidget(row, 4).currentData(),
                    text(row, 5),
                    text(row, 6),
                )
                for row in range(self.items.rowCount())
            ),
            self._party_input("firm"),
            self._party_input("customer"),
            self.find(QLineEdit, "placeOfSupply").text(),
            self.find(QLineEdit, "reference").text(),
            self.due.date().toString("yyyy-MM-dd") if self.due_enabled.isChecked() else "",
            self.find(QPlainTextEdit, "notes").toPlainText(),
            self.find(QPlainTextEdit, "terms").toPlainText(),
            self.template.currentData(),
        )

    def _edited(self, *_args):
        if self._loading:
            return
        self._generation += 1
        self._dirty = self._input() != self._baseline
        self._identity()
        self._artifact_id = None
        self.reveal_button.setEnabled(False)
        self.pdf_document.close()
        self.find(QLabel, "previewHint").setText(
            "Details changed. Refresh the preview to see the current draft."
        )
        self._clear_totals()
        self.auto_timer.start()

    def _identity(self):
        saved = (
            f"Saved draft · revision {self.vm.current.revision}" if self.vm.current else "New draft"
        )
        self.identity.setText(saved + ("  •  Unsaved changes" if self._dirty else ""))
        self.find(QPushButton, "deleteButton").setEnabled(self.vm.current is not None)

    def _clear_totals(self):
        self.total.setText("—")
        self.find(QLabel, "stickyTotal").setText("Total  —")
        for name in ("taxable", "cgst", "sgst", "igst"):
            self.find(QLabel, name + "Amount").setText("—")
        self.find(QLabel, "wordsLabel").setText("Complete the required fields to calculate.")
        with QSignalBlocker(self.items):
            for row in range(self.items.rowCount()):
                item = self.items.item(row, 7)
                if item:
                    item.setText("—")

    def add_item(self, line=None):
        if self.items.rowCount() >= 200:
            self._status("An invoice can contain up to 200 items.", True)
            return
        line = line or LineInput("", "1", "0.00", "0")
        with QSignalBlocker(self.items):
            row = self.items.rowCount()
            self.items.insertRow(row)
            values = [
                line.description,
                line.quantity,
                line.unit_price,
                line.gst_rate,
                "",
                line.hsn_sac,
                line.unit,
                "—",
            ]
            for column, value in enumerate(values):
                item = QTableWidgetItem(value)
                if column == 7:
                    item.setFlags(item.flags() & ~Qt.ItemFlag.ItemIsEditable)
                    item.setTextAlignment(
                        Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter
                    )
                self.items.setItem(row, column, item)
            kind = QComboBox()
            kind.addItem("Goods", "GOODS")
            kind.addItem("Service", "SERVICES")
            kind.setCurrentIndex(kind.findData(line.item_type))
            self.items.setCellWidget(row, 4, kind)
            kind.currentIndexChanged.connect(self._edited)
        self._edited()

    def remove_item(self):
        row = self.items.currentRow()
        if row < 0:
            self._status("Select an item to remove.")
            return
        self.items.removeRow(row)
        self._edited()

    def _confirm_leave(self, action):
        if not self._dirty:
            action()
            return
        answer = QMessageBox.question(
            self,
            "Unsaved changes",
            "Save your changes before leaving this draft?",
            QMessageBox.StandardButton.Save
            | QMessageBox.StandardButton.Discard
            | QMessageBox.StandardButton.Cancel,
            QMessageBox.StandardButton.Save,
        )
        if answer == QMessageBox.StandardButton.Save:
            self.save(on_saved=action)
        elif answer == QMessageBox.StandardButton.Discard:
            self._dirty = False
            action()

    def new_draft(self):
        def reset():
            self.vm.current = None
            self._loading = True
            self.customer.clear()
            for name in ("Gstin", "State", "Email", "Phone"):
                self.find(QLineEdit, "customer" + name).clear()
            self.find(QPlainTextEdit, "customerAddress").clear()
            for name in ("reference", "placeOfSupply"):
                self.find(QLineEdit, name).clear()
            for name in ("notes", "terms"):
                self.find(QPlainTextEdit, name).clear()
            self.invoice_date.setDate(QDate.currentDate())
            self.due_enabled.setChecked(False)
            self.mode.setCurrentIndex(0)
            self.items.setRowCount(0)
            self.add_item()
            self.apply_firm_defaults()
            self._loading = False
            self._dirty = False
            self._generation += 1
            self._baseline = self._input()
            self._identity()
            self._clear_totals()
            self._artifact_id = None
            self.reveal_button.setEnabled(False)
            self.pdf_document.close()
            self._set_page(1)
            self.tabs.setCurrentIndex(0)
            self._status("New draft ready. Your firm details have been kept for this session.")
            self.customer.setFocus()

        self._confirm_leave(reset)

    def show_library(self):
        self._confirm_leave(lambda: (self._set_page(0), self.refresh()))

    def _show_totals(self, totals):
        self.total.setText(display_amount(totals.total_paise))
        self.find(QLabel, "stickyTotal").setText("Total  " + display_amount(totals.total_paise))
        self.find(QLabel, "wordsLabel").setText(totals.amount_in_words)
        for name, value in (
            ("taxable", totals.taxable_paise),
            ("cgst", totals.cgst_paise),
            ("sgst", totals.sgst_paise),
            ("igst", totals.igst_paise),
        ):
            self.find(QLabel, name + "Amount").setText(display_amount(value))
        with QSignalBlocker(self.items):
            for row, line in enumerate(totals.lines):
                if row < self.items.rowCount():
                    self.items.item(row, 7).setText(
                        display_amount(line.total_paise).removeprefix("INR ")
                    )

    def _auto_calculate(self):
        if self.bridge.busy:
            self.auto_timer.start()
            return
        data, generation = self._input(), self._generation

        def show(result):
            if generation != self._generation or self._exclusive:
                return
            if result.error:
                self._clear_totals()
                self._status(result.error.message, True)
            else:
                self._show_totals(result.value)
                self._status("Totals updated. Save when you are ready.")

        self.bridge.submit(lambda: self.vm.queries.calculate(data), show)

    def calculate(self):
        data = self._input()
        self._run(
            lambda: self.vm.queries.calculate(data),
            lambda totals: (self._show_totals(totals), self._status("Draft totals calculated.")),
        )

    def save(self, export_pdf=False, export_word=False, on_saved=None):
        request = self.vm.save_request(self._input())

        def saved(draft):
            self.vm.current = draft
            self._dirty = False
            self._baseline = self._input()
            self._identity()
            self._show_totals(draft.totals)
            self.reveal_button.setEnabled(False)
            if export_pdf or export_word:
                reference = DraftReference(draft.id, draft.revision)
                service = self.vm.words if export_word else self.vm.pdfs
                self._run(lambda: service.export(reference), self._export_ready)
            elif on_saved:
                on_saved()
            else:
                self.refresh(message="Draft saved on this device.")

        self._run(lambda: self.vm.commands.save(request), saved)

    def _export_ready(self, artifact):
        self._artifact_id = artifact.id
        self.reveal_button.setEnabled(True)
        self.refresh(message=f"Export ready: {artifact.display_name}")

    def preview(self):
        if not self.vm.previews:
            return
        data = self._input()

        def show(content):
            self.pdf_document.close()
            self.pdf_buffer.close()
            self.pdf_buffer.setData(QByteArray(content))
            self.pdf_buffer.open(QIODevice.OpenModeFlag.ReadOnly)
            self.pdf_document.load(self.pdf_buffer)
            self.find(QLabel, "previewHint").setText(
                "Actual PDF preview of the current form • DRAFT • No invoice number allocated"
            )
            self.tabs.setCurrentIndex(1)
            self._status("Preview ready. Your draft has not been saved by this action.")

        self._run(lambda: self.vm.previews.preview(data), show)

    def reveal(self):
        artifact_id = self._artifact_id
        if artifact_id:
            self._run(
                lambda: self.vm.artifacts.reveal(artifact_id),
                lambda _: self._status("Opened the export location."),
            )

    def _dates(self):
        return DateRange(
            self.start.date().toString("yyyy-MM-dd"), self.end.date().toString("yyyy-MM-dd")
        )

    def export_range(self):
        if not self.vm.range_exports:
            return
        dates = self._dates()
        if self.record_type.currentData() == "issued" and self.vm.issued:
            self._run(lambda: self.vm.issued.export_range(dates), self._export_ready)
            return

        def done(receipt):
            self._artifact_id = receipt.artifact.id
            self.reveal_button.setEnabled(True)
            self._status(
                f"Package ready: {receipt.invoice_count} drafts. "
                "Use Show latest export to find the ZIP."
            )

        self._run(lambda: self.vm.range_exports.export_range(dates), done)

    def refresh(self, message="Select a record to open it, or create a new invoice."):
        dates = self._dates()
        issued = self.record_type.currentData() == "issued" and self.vm.issued is not None

        def show(rows):
            if issued:
                self._issued_records = {row.id: row for row in rows}
                from invoice_generator.application.contracts.dto import DraftSummary

                rows = tuple(
                    DraftSummary(
                        row.id,
                        row.model.revision,
                        row.model.invoice_date,
                        row.model.customer_name,
                        row.model.totals.total_paise,
                        row.model.firm_name,
                        str(row.number),
                    )
                    for row in rows
                )
            else:
                self._issued_records = {}
            self._all_rows = rows
            self.invoices.setHorizontalHeaderLabels(
                ["CUSTOMER", "DATE", "INVOICE NO." if issued else "REFERENCE", "STATUS", "TOTAL"]
            )
            self.find(QPushButton, "openButton").setText(
                "Open selected invoice" if issued else "Open selected draft"
            )
            self.find(QLabel, "countCaption").setText(
                "ISSUED RECORDS" if issued else "SAVED DRAFTS"
            )
            self.find(QLabel, "valueCaption").setText(
                "ACTIVE INVOICE VALUE" if issued else "DRAFT VALUE"
            )
            self.find(QLabel, "rangeHint").setText(
                "ZIP includes every record in this date range, regardless of search."
            )
            self.find(QLabel, "countValue").setText(str(len(rows)))
            self.find(QLabel, "valueValue").setText(
                display_amount(
                    sum(
                        row.total_paise
                        for row in rows
                        if not issued or self._issued_records[row.id].status == "ISSUED"
                    )
                )
            )
            self.find(QLabel, "rangeValue").setText(
                QDate.fromString(dates.start, "yyyy-MM-dd").toString("dd MMM yy")
                + " — "
                + QDate.fromString(dates.end, "yyyy-MM-dd").toString("dd MMM yy")
            )
            self._filter_rows()
            self._status(message)

        service = self.vm.issued if issued else self.vm.queries
        self._run(lambda: service.list(dates), show)

    def _filter_rows(self):
        query = self.search.text().strip().casefold()
        self._rows = tuple(
            row
            for row in self._all_rows
            if query in f"{row.customer_name} {row.firm_name} {row.reference}".casefold()
        )
        self.invoices.setRowCount(len(self._rows))
        for index, row in enumerate(self._rows):
            for column, value in enumerate(
                [
                    row.customer_name,
                    QDate.fromString(row.invoice_date, "yyyy-MM-dd").toString("dd MMM yyyy"),
                    row.reference or "—",
                    self._issued_records[row.id].status
                    if row.id in getattr(self, "_issued_records", {})
                    else "DRAFT",
                    display_amount(row.total_paise),
                ]
            ):
                item = QTableWidgetItem(value)
                if column == 3:
                    item.setForeground(QColor("#8B7445"))
                if column == 4:
                    item.setTextAlignment(
                        Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter
                    )
                self.invoices.setItem(index, column, item)
        self.find(QLabel, "emptyLabel").setVisible(not self._rows)
        self.find(QLabel, "emptyLabel").setText(
            "No records match this search or date range."
            if self.search.text() or self._all_rows
            else "No records in this date range. Create your first invoice to get started."
        )
        self.find(QLabel, "resultsLabel").setText(
            f"{len(self._rows)} of {len(self._all_rows)} records shown"
        )
        self.find(QPushButton, "openButton").setEnabled(bool(self._rows))

    def open_selected(self):
        row = self.invoices.currentRow()
        if row >= 0:
            self.load_selected(row, 0)
        else:
            self._status("Select a draft in the list first.")

    def load_selected(self, row, _column):
        if not 0 <= row < len(self._rows):
            return
        draft_id = self._rows[row].id
        if draft_id in getattr(self, "_issued_records", {}):
            IssuedDialog(
                self.vm.issued, self.vm.artifacts, self._issued_records[draft_id], self
            ).exec()
            self.refresh()
            return

        def show(draft):
            self._loading = True
            self.vm.current = draft
            data = draft.data
            self.firm.setText(data.firm_name)
            self.customer.setText(data.customer_name)
            self.invoice_date.setDate(QDate.fromString(data.invoice_date, "yyyy-MM-dd"))
            self.mode.setCurrentIndex(self.mode.findData(data.tax_mode))
            self.template.setCurrentIndex(self.template.findData(data.template_id))
            for prefix, details in (
                ("firm", data.firm_details),
                ("customer", data.customer_details),
            ):
                self.find(QPlainTextEdit, prefix + "Address").setPlainText(details.address)
                for suffix, value in (
                    ("Gstin", details.gstin),
                    ("State", details.state),
                    ("Email", details.email),
                    ("Phone", details.phone),
                ):
                    self.find(QLineEdit, prefix + suffix).setText(value)
            self.find(QLineEdit, "reference").setText(data.reference)
            self.find(QLineEdit, "placeOfSupply").setText(data.place_of_supply)
            self.find(QPlainTextEdit, "notes").setPlainText(data.notes)
            self.find(QPlainTextEdit, "terms").setPlainText(data.terms)
            self.due_enabled.setChecked(bool(data.due_date))
            if data.due_date:
                self.due.setDate(QDate.fromString(data.due_date, "yyyy-MM-dd"))
            self.items.setRowCount(0)
            for line in data.lines:
                self.add_item(line)
            self._loading = False
            self._generation += 1
            self._dirty = False
            self._baseline = self._input()
            self._identity()
            self._show_totals(draft.totals)
            self.reveal_button.setEnabled(False)
            self._artifact_id = None
            self.pdf_document.close()
            self._set_page(1)
            self.tabs.setCurrentIndex(0)
            self._status("Draft loaded. Changes are saved only when you choose Save draft.")

        self._confirm_leave(lambda: self._run(lambda: self.vm.queries.get(draft_id), show))

    def delete(self):
        draft = self.vm.current
        if draft is None:
            return
        answer = QMessageBox.question(
            self,
            "Delete draft",
            "Delete this draft from the active list? Its audit history is retained.",
        )
        if answer != QMessageBox.StandardButton.Yes:
            return
        request = DraftReference(draft.id, draft.revision)

        def deleted(_):
            self._dirty = False
            self.vm.current = None
            self.new_draft()
            self._set_page(0)
            self.refresh(message="Draft deleted from the active list.")

        self._run(lambda: self.vm.commands.delete(request), deleted)

    def closeEvent(self, event):
        if self.bridge.busy:
            self._status("Wait for the current operation before closing.")
            event.ignore()
        elif self._dirty:
            event.ignore()
            self._confirm_leave(lambda: QTimer.singleShot(0, self.close))
        else:
            self.auto_timer.stop()
            if self.vm.auth:
                self.lock_timer.stop()
                QApplication.instance().removeEventFilter(self)
                self.vm.auth.logout()
            self.pdf_document.close()
            event.accept()

    def eventFilter(self, watched, event):
        if (
            self.vm.auth
            and not self._locking
            and event.type()
            in (
                QEvent.Type.KeyPress,
                QEvent.Type.MouseButtonPress,
                QEvent.Type.Wheel,
                QEvent.Type.MouseMove,
            )
        ):
            now = time.monotonic()
            if now - self._last_touch > 30:
                self._last_touch = now
                result = self.vm.auth.touch()
                if result.error:
                    QTimer.singleShot(0, self.lock_workspace)
        return super().eventFilter(watched, event)

    def check_lock(self):
        if not self.vm.auth or self._locking:
            return
        result = self.vm.auth.state()
        if result.error or not result.value.signed_in:
            self.lock_workspace()

    def lock_workspace(self):
        if not self.vm.auth or self._locking:
            return
        if any(bridge.busy for bridge in self.findChildren(QtTaskBridge)):
            QTimer.singleShot(500, self.lock_workspace)
            return
        self._locking = True
        self.auto_timer.stop()
        dialogs = [dialog for dialog in self.findChildren(QDialog) if dialog.isVisible()]
        for dialog in dialogs:
            dialog.hide()
        self.hide()
        self.vm.auth.logout()
        login = AuthenticationDialog(self.vm.auth)
        while True:
            outcome = login.exec()
            if outcome == QDialog.DialogCode.Accepted or not self._dirty:
                break
            answer = QMessageBox.question(
                login,
                "Unsaved invoice",
                "Exit and discard the unsaved invoice edits?",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                QMessageBox.StandardButton.No,
            )
            if answer == QMessageBox.StandardButton.Yes:
                break
        if outcome == QDialog.DialogCode.Accepted:
            self.show()
            for dialog in dialogs:
                dialog.show()
            self._locking = False
            self._status("Workspace unlocked. Unsaved edits are still available.")
        else:
            for dialog in dialogs:
                dialog.reject()
            # Explicit discard was confirmed above if the editor had unsaved changes.
            self._dirty = False
            self.close()
            QApplication.instance().quit()

    def load_workspace_defaults(self):
        def profile_loaded(profile):
            self._firm_profile = profile

            def layouts_loaded(rows):
                selected = self.template.currentData()
                self._loading = True
                self.template.clear()
                for row in rows:
                    self.template.addItem(f"{row.layout.name} · v{row.version}", row.id)
                self.template.setCurrentIndex(max(0, self.template.findData(selected)))
                if self.vm.current is None and not self._dirty:
                    self.apply_firm_defaults()
                    self._baseline = self._input()
                self._loading = False
                mode = profile.invoice_mode
                self.find(QLabel, "buildLabel").setText(
                    "Signed in · "
                    + profile.name
                    + (
                        " · Domestic ordinary GST issuance enabled"
                        if mode == "MANUAL_CONFIRMED"
                        else " · Review invoice applicability in Firm settings"
                    )
                )
                self.refresh()

            self._run(self.vm.templates.list, layouts_loaded)

        self._run(self.vm.firm_settings.get, profile_loaded)

    def apply_firm_defaults(self):
        profile = self._firm_profile
        if profile is None:
            return
        self.firm.setText(profile.name)
        self.firm.setReadOnly(True)
        self.find(QPlainTextEdit, "firmAddress").setPlainText(profile.details.address)
        for suffix, key in (
            ("Gstin", "gstin"),
            ("State", "state"),
            ("Email", "email"),
            ("Phone", "phone"),
        ):
            self.find(QLineEdit, "firm" + suffix).setText(getattr(profile.details, key))
        self.find(QLineEdit, "firmGstin").setReadOnly(True)
        terms = profile.default_terms
        if profile.bank_details:
            terms += "\n\n" + profile.bank_details
        self.find(QPlainTextEdit, "terms").setPlainText(terms)
        self.template.setCurrentIndex(max(0, self.template.findData(profile.default_template)))

    def open_firm_settings(self):
        if self.vm.firm_settings:
            FirmDialog(self.vm.firm_settings, self.vm.templates, self).exec()
            self.load_workspace_defaults()

    def open_catalog(self, kind):
        service = self.vm.customers if kind == "customer" else self.vm.items
        if service:
            CatalogDialog(service, kind, self).exec()

    def pick_customer(self):
        if not self.vm.customers:
            return
        dialog = CatalogDialog(self.vm.customers, "customer", self, choose=True)
        if dialog.exec() != QDialog.DialogCode.Accepted or not dialog.selected:
            return
        customer = dialog.selected
        self._loading = True
        self.customer.setText(customer.name)
        self.find(QPlainTextEdit, "customerAddress").setPlainText(customer.details.address)
        for suffix, key in (
            ("Gstin", "gstin"),
            ("State", "state"),
            ("Email", "email"),
            ("Phone", "phone"),
        ):
            self.find(QLineEdit, "customer" + suffix).setText(getattr(customer.details, key))
        self._loading = False
        self._edited()

    def pick_item(self):
        if not self.vm.items:
            return
        dialog = CatalogDialog(self.vm.items, "item", self, choose=True)
        if dialog.exec() != QDialog.DialogCode.Accepted or not dialog.selected:
            return
        item = dialog.selected
        if self.items.rowCount() == 1 and not self.items.item(0, 0).text():
            self.items.setRowCount(0)
        self.add_item(
            LineInput(
                item.description,
                "1",
                item.unit_price,
                item.gst_rate,
                item.item_type,
                item.hsn_sac,
                item.unit,
            )
        )

    def open_designer(self):
        if not self.vm.templates:
            return
        data = self._input()
        if (
            not data.customer_name
            or not data.tax_mode
            or not data.lines
            or not data.lines[0].description
        ):
            data = replace(
                data,
                firm_name=data.firm_name or "Example Firm",
                customer_name="Sample Customer",
                tax_mode="CGST_SGST",
                lines=(
                    LineInput("Sample service", "2", "1500", "18", "SERVICES", "998314", "Hours"),
                ),
            )
        TemplateDesigner(self.vm.templates, data, self).exec()
        self.load_workspace_defaults()

    def open_backups(self):
        if self.vm.backups:
            BackupDialog(self.vm.backups, self).exec()

    def open_security(self):
        if self.vm.auth:
            SecurityDialog(self.vm.auth, self.vm.firm_settings, self).exec()
            self.check_lock()

    def issue_invoice(self):
        if not self.vm.issued:
            return

        def issue_saved():
            draft = self.vm.current
            shipping, accepted = QInputDialog.getMultiLineText(
                self,
                "Delivery address",
                "Confirm the delivery address for this invoice:",
                draft.data.customer_details.address,
            )
            if not accepted:
                return
            answer = QMessageBox.question(
                self,
                "Issue invoice",
                f"Issue this invoice for {draft.data.customer_name}?\n"
                f"Date: {draft.data.invoice_date}\n"
                f"Total: {display_amount(draft.totals.total_paise)}\n\n"
                "The next number is allocated once and these invoice details become read-only. "
                "Use this only for the supported ordinary taxable supply workflow.",
            )
            if answer != QMessageBox.StandardButton.Yes:
                return
            request = IssueRequest(draft.id, draft.revision, str(uuid4()), shipping)

            def issued(invoice):
                self._dirty = False
                self.vm.current = None
                self.record_type.setCurrentIndex(self.record_type.findData("issued"))
                self._set_page(0)
                self._status(
                    f"Invoice {invoice.number} issued. Open it to export the saved document."
                )
                if not self.bridge.busy:
                    self.refresh()

            self._run(lambda: self.vm.issued.issue(request), issued)

        if self._dirty or self.vm.current is None:
            self.save(on_saved=issue_saved)
        else:
            issue_saved()
