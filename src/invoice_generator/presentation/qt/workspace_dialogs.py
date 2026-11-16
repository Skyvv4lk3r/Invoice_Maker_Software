from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QAbstractItemView,
    QCheckBox,
    QComboBox,
    QDialog,
    QFileDialog,
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPlainTextEdit,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QTabWidget,
    QVBoxLayout,
    QWidget,
)

from invoice_generator.application.contracts.dto import PartyDetails
from invoice_generator.application.contracts.workspace import (
    CustomerRecord,
    FirmProfile,
    ItemRecord,
)
from invoice_generator.presentation.qt.authentication import RecoveryDialog, password_field
from invoice_generator.presentation.qt.tasks import QtTaskBridge


class ServiceDialog(QDialog):
    def __init__(self, title, parent=None):
        super().__init__(parent)
        self.setWindowTitle(title)
        self.resize(820, 680)
        self.bridge = QtTaskBridge(self)
        self.root = QVBoxLayout(self)
        self.root.setContentsMargins(24, 24, 24, 24)
        heading = QLabel(title)
        heading.setStyleSheet("font-size: 24px; font-weight: 700; color: #214C39")
        self.root.addWidget(heading)
        self.body = QVBoxLayout()
        self.root.addLayout(self.body, 1)
        self.status = QLabel()
        self.status.setWordWrap(True)
        self.root.addWidget(self.status)
        close = QPushButton("Close")
        close.clicked.connect(self.reject)
        self.root.addWidget(close, alignment=Qt.AlignmentFlag.AlignRight)

    def run(self, operation, callback):
        self.setEnabled(False)
        self.status.setText("Working…")

        def done(result):
            self.setEnabled(True)
            if result.error:
                self.status.setText(result.error.message)
            else:
                self.status.clear()
                callback(result.value)

        self.bridge.submit(operation, done)

    def reject(self):
        if not self.bridge.busy:
            super().reject()


class PartyForm(QWidget):
    def __init__(self):
        super().__init__()
        self.form = QFormLayout(self)
        self.address = QPlainTextEdit()
        self.address.setMaximumHeight(75)
        self.gstin, self.state, self.email, self.phone = (QLineEdit() for _ in range(4))
        self.state.setPlaceholderText("e.g. 24 Gujarat")
        for label, value in (
            ("Address", self.address),
            ("GSTIN", self.gstin),
            ("State / GST code", self.state),
            ("Email", self.email),
            ("Phone", self.phone),
        ):
            self.form.addRow(label, value)

    def data(self):
        return PartyDetails(
            self.address.toPlainText(),
            self.gstin.text(),
            self.state.text(),
            self.email.text(),
            self.phone.text(),
        )

    def fill(self, data):
        self.address.setPlainText(data.address)
        for key in ("gstin", "state", "email", "phone"):
            getattr(self, key).setText(getattr(data, key))


class FirmDialog(ServiceDialog):
    def __init__(self, settings, templates, parent=None):
        super().__init__("Firm settings", parent)
        self.settings, self.templates = settings, templates
        self.profile = None
        self.name, self.signatory = QLineEdit(), QLineEdit()
        self.party = PartyForm()
        self.bank, self.terms = QPlainTextEdit(), QPlainTextEdit()
        self.bank.setMaximumHeight(70)
        self.terms.setMaximumHeight(70)
        self.template = QComboBox()
        self.mode = QComboBox()
        self.mode.addItem("Review required · Drafts only", "REVIEW_REQUIRED")
        self.mode.addItem("Confirmed: ordinary invoices without IRN", "MANUAL_CONFIRMED")
        self.mode.addItem("E-invoicing / IRN required · Drafts only", "EINVOICE_REQUIRED")
        tabs = QTabWidget()
        self.body.addWidget(tabs)
        details, invoicing = QWidget(), QWidget()
        tabs.addTab(details, "Firm and payment details")
        tabs.addTab(invoicing, "Invoice defaults")
        form = QFormLayout(details)
        form.addRow("Legal firm name", self.name)
        form.addRow(self.party)
        form.addRow("Bank / payment details", self.bank)
        form.addRow("Authorised signatory", self.signatory)
        other = QFormLayout(invoicing)
        other.addRow("Default document layout", self.template)
        other.addRow("Default terms", self.terms)
        other.addRow("Invoice applicability", self.mode)
        self.confirm = QCheckBox(
            "I have verified that this firm can issue ordinary domestic "
            "taxable invoices without an IRN."
        )
        other.addRow(self.confirm)
        note = QLabel(
            "Supported issuance: INR, domestic ordinary taxable goods/services, "
            "CGST+SGST or IGST, no reverse charge, exports, SEZ, cess, exempt "
            "or nil-rated supplies. Tax rates and HSN/SAC classification "
            "must be verified by the operator. Sign printed invoices where "
            "required. Cancellation here is a local record, not a GST portal "
            "action."
        )
        note.setWordWrap(True)
        other.addRow(note)
        save = QPushButton("Save firm settings")
        save.clicked.connect(self.save)
        self.body.addWidget(save)
        self.run(templates.list, self._templates)

    def _templates(self, rows):
        for row in rows:
            self.template.addItem(f"{row.layout.name} · v{row.version}", row.id)
        self.run(self.settings.get, self.fill)

    def fill(self, profile):
        self.profile = profile
        self.name.setText(profile.name)
        self.party.fill(profile.details)
        self.bank.setPlainText(profile.bank_details)
        self.terms.setPlainText(profile.default_terms)
        self.signatory.setText(profile.signatory)
        self.template.setCurrentIndex(max(0, self.template.findData(profile.default_template)))
        self.mode.setCurrentIndex(self.mode.findData(profile.invoice_mode))
        self.confirm.setChecked(profile.invoice_mode == "MANUAL_CONFIRMED")

    def save(self):
        if self.profile is None:
            return
        if self.mode.currentData() == "MANUAL_CONFIRMED" and not self.confirm.isChecked():
            self.status.setText("Confirm invoice applicability first, or keep Drafts only.")
            return
        data = FirmProfile(
            self.name.text(),
            self.party.data(),
            self.bank.toPlainText(),
            self.terms.toPlainText(),
            self.template.currentData(),
            self.signatory.text(),
            self.mode.currentData(),
            self.profile.revision,
        )

        def saved(value):
            self.profile = value
            self.status.setText("Firm settings saved. New invoices use these defaults.")

        self.run(lambda: self.settings.save(data), saved)


class CatalogDialog(ServiceDialog):
    def __init__(self, service, kind, parent=None, choose=False):
        super().__init__("Customers" if kind == "customer" else "Products & services", parent)
        self.service, self.kind, self.current, self.selected = service, kind, None, None
        self.rows = ()
        self.search = QLineEdit()
        self.search.setPlaceholderText("Search saved records…")
        self.search.textChanged.connect(self.filter)
        self.body.addWidget(self.search)
        self.table = QTableWidget(0, 2)
        self.table.setHorizontalHeaderLabels(["Name / description", "GSTIN / unit price"])
        self.table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.table.horizontalHeader().setStretchLastSection(True)
        self.table.setColumnWidth(0, 420)
        self.table.cellClicked.connect(self.load_row)
        self.body.addWidget(self.table)
        self.name = QLineEdit()
        form = QFormLayout()
        form.addRow("Customer name" if kind == "customer" else "Description", self.name)
        self.body.addLayout(form)
        if kind == "customer":
            self.party = PartyForm()
            self.body.addWidget(self.party)
        else:
            self.price, self.rate, self.code, self.unit = (QLineEdit() for _ in range(4))
            self.type = QComboBox()
            self.type.addItem("Goods", "GOODS")
            self.type.addItem("Services", "SERVICES")
            for label, widget in (
                ("Unit price INR", self.price),
                ("GST %", self.rate),
                ("Type", self.type),
                ("HSN / SAC", self.code),
                ("Unit", self.unit),
            ):
                form.addRow(label, widget)
        actions = QHBoxLayout()
        for label, action in (
            ("New", self.new),
            ("Save record", self.save),
            ("Delete record", self.delete),
        ):
            button = QPushButton(label)
            button.clicked.connect(action)
            actions.addWidget(button)
        if choose:
            button = QPushButton("Use selected record")
            button.clicked.connect(self.use_selected)
            actions.addWidget(button)
        self.body.addLayout(actions)
        self.new()
        self.refresh()

    def refresh(self):
        self.run(self.service.list, lambda rows: (setattr(self, "rows", rows), self.filter()))

    def filter(self):
        query = self.search.text().casefold()
        self.visible_rows = tuple(
            row
            for row in self.rows
            if query in (row.name if self.kind == "customer" else row.description).casefold()
        )
        self.table.setRowCount(len(self.visible_rows))
        for index, row in enumerate(self.visible_rows):
            values = (
                [row.name, row.details.gstin]
                if self.kind == "customer"
                else [row.description, row.unit_price]
            )
            for column, text in enumerate(values):
                self.table.setItem(index, column, QTableWidgetItem(text))

    def new(self):
        self.current = None
        self.name.clear()
        if self.kind == "customer":
            self.party.fill(PartyDetails())
        else:
            self.price.setText("0.00")
            self.rate.setText("0")
            self.code.clear()
            self.unit.setText("Nos")

    def load_row(self, index, _column):
        row = self.visible_rows[index]
        self.current = row
        if self.kind == "customer":
            self.name.setText(row.name)
            self.party.fill(row.details)
        else:
            self.name.setText(row.description)
            self.price.setText(row.unit_price)
            self.rate.setText(row.gst_rate)
            self.type.setCurrentIndex(self.type.findData(row.item_type))
            self.code.setText(row.hsn_sac)
            self.unit.setText(row.unit)

    def save(self):
        record_id, revision = (self.current.id, self.current.revision) if self.current else ("", 0)
        if self.kind == "customer":
            record = CustomerRecord(self.name.text(), self.party.data(), record_id, revision)
        else:
            record = ItemRecord(
                self.name.text(),
                self.price.text(),
                self.rate.text(),
                self.type.currentData(),
                self.code.text(),
                self.unit.text(),
                record_id,
                revision,
            )

        def saved(row):
            self.current = row
            self.refresh()

        self.run(lambda: self.service.save(record), saved)

    def delete(self):
        if self.current is None:
            return
        if (
            QMessageBox.question(
                self,
                "Delete record",
                (
                    "Remove this record from the catalog? Existing invoices keep "
                    "their captured details."
                ),
            )
            != QMessageBox.StandardButton.Yes
        ):
            return
        row = self.current
        self.run(
            lambda: self.service.delete(row.id, row.revision),
            lambda _: (self.new(), self.refresh()),
        )

    def use_selected(self):
        if self.current:
            self.selected = self.current
            self.accept()
        else:
            self.status.setText("Select a saved record first.")


class SecurityDialog(ServiceDialog):
    def __init__(self, auth, firm, parent=None):
        super().__init__("Security & activity", parent)
        self.auth = auth
        self.current, self.new, self.confirm = password_field(), password_field(), password_field()
        form = QFormLayout()
        for label, value in (
            ("Current password", self.current),
            ("New password", self.new),
            ("Confirm password", self.confirm),
        ):
            form.addRow(label, value)
        self.body.addLayout(form)
        change = QPushButton("Change password and recovery code")
        change.clicked.connect(self.change_password)
        self.body.addWidget(change)
        self.events = QTableWidget(0, 3)
        self.events.setHorizontalHeaderLabels(["Time (UTC)", "Action", "Record"])
        self.events.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.events.horizontalHeader().setStretchLastSection(True)
        self.body.addWidget(QLabel("Recent activity · latest 500 events"))
        self.body.addWidget(self.events)
        self.run(firm.audit, self.show_events)

    def show_events(self, entries):
        self.events.setRowCount(len(entries))
        for row, event in enumerate(entries):
            for column, value in enumerate((event.occurred_at[:19], event.action, event.record_id)):
                self.events.setItem(row, column, QTableWidgetItem(value))

    def change_password(self):
        if self.new.text() != self.confirm.text():
            self.status.setText("The passwords do not match.")
            return
        current, new = self.current.text(), self.new.text()

        def changed(key):
            self.current.clear()
            self.new.clear()
            self.confirm.clear()
            RecoveryDialog(key.code, self).exec()
            self.accept()

        self.run(lambda: self.auth.change_password(current, new), changed)


class BackupDialog(ServiceDialog):
    def __init__(self, backups, parent=None):
        super().__init__("Backup & recovery", parent)
        self.backups = backups
        self.resize(700, 400)
        note = QLabel(
            "Encrypted backups contain the database, firm account, customers, "
            "templates, issued snapshots and exported files. Keep the backup "
            "passphrase separately. Restoring creates a verified copy in "
            "an empty folder and leaves the active workspace unchanged."
        )
        note.setWordWrap(True)
        self.body.addWidget(note)
        self.password, self.confirm = password_field(), password_field()
        form = QFormLayout()
        form.addRow("Backup passphrase", self.password)
        form.addRow("Confirm for a new backup", self.confirm)
        self.body.addLayout(form)
        create, restore = (
            QPushButton("Create encrypted backup…"),
            QPushButton("Restore to an empty folder…"),
        )
        create.clicked.connect(self.create)
        restore.clicked.connect(self.restore)
        self.body.addWidget(create)
        self.body.addWidget(restore)

    def create(self):
        if self.password.text() != self.confirm.text():
            self.status.setText("The backup passphrases do not match.")
            return
        path, _ = QFileDialog.getSaveFileName(
            self, "Save encrypted backup", "firm-backup.invobak", "Encrypted backup (*.invobak)"
        )
        if not path:
            return
        password = self.password.text()
        self.run(
            lambda: self.backups.create(path, password),
            lambda artifact: self.status.setText("Backup saved: " + artifact.display_name),
        )

    def restore(self):
        source, _ = QFileDialog.getOpenFileName(
            self, "Select backup", "", "Encrypted backup (*.invobak)"
        )
        if not source:
            return
        destination = QFileDialog.getExistingDirectory(self, "Select an empty restore folder")
        if not destination:
            return
        password = self.password.text()

        def restored(path):
            self.status.setText(
                "Verified workspace restored to: "
                + path
                + "\nChoose this folder using Open workspace on the sign-in screen."
            )

        self.run(lambda: self.backups.restore_copy(source, password, destination), restored)
