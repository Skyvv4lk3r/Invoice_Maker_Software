from pathlib import Path

from PySide6.QtCore import QBuffer, QByteArray, QIODevice, Qt
from PySide6.QtPdf import QPdfDocument
from PySide6.QtPdfWidgets import QPdfView
from PySide6.QtWidgets import (
    QAbstractItemView,
    QCheckBox,
    QColorDialog,
    QComboBox,
    QFileDialog,
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QMessageBox,
    QPushButton,
    QScrollArea,
    QSpinBox,
    QSplitter,
    QVBoxLayout,
    QWidget,
)

from invoice_generator.application.contracts.layout import InvoiceLayout
from invoice_generator.presentation.qt.workspace_dialogs import ServiceDialog


class TemplateDesigner(ServiceDialog):
    def __init__(self, templates, preview_data, parent=None):
        super().__init__("Invoice layout designer", parent)
        self.resize(1280, 860)
        self.templates, self.preview_data = templates, preview_data
        self.current = None
        self.logo = ""
        self.versions = ()
        toolbar = QHBoxLayout()
        self.selector = QComboBox()
        self.selector.currentIndexChanged.connect(self.select_template)
        toolbar.addWidget(self.selector, 1)
        for label, callback in (
            ("Save as new", lambda: self.save(True)),
            ("Save new version", lambda: self.save(False)),
            ("Import layout", self.import_layout),
            ("Export layout", self.export_layout),
        ):
            button = QPushButton(label)
            button.clicked.connect(callback)
            toolbar.addWidget(button)
        self.body.addLayout(toolbar)
        splitter = QSplitter()
        self.body.addWidget(splitter, 1)
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        panel = QWidget()
        form = QFormLayout(panel)
        scroll.setWidget(panel)
        splitter.addWidget(scroll)
        self.name, self.accent, self.tint, self.footer = (QLineEdit() for _ in range(4))
        self.font = self.combo([("Sans serif", "sans"), ("Serif", "serif"), ("Monospace", "mono")])
        self.alignment = self.combo([("Left", "left"), ("Centre", "center"), ("Right", "right")])
        self.parties = self.combo([("Side by side", "columns"), ("Stacked", "stacked")])
        self.size, self.margin, self.spacing = QSpinBox(), QSpinBox(), QSpinBox()
        self.size.setRange(8, 12)
        self.margin.setRange(10, 25)
        self.spacing.setRange(4, 12)
        form.addRow("Template name", self.name)
        for label, field in (("Accent colour", self.accent), ("Row tint", self.tint)):
            row = QHBoxLayout()
            row.addWidget(field)
            choose = QPushButton("Choose…")
            choose.clicked.connect(lambda _checked=False, f=field: self.choose_colour(f))
            row.addWidget(choose)
            form.addRow(label, row)
        for label, control in (
            ("Font", self.font),
            ("Body size (pt)", self.size),
            ("Page margin (mm)", self.margin),
            ("Header alignment", self.alignment),
            ("Firm / customer layout", self.parties),
            ("Row spacing", self.spacing),
            ("Footer message", self.footer),
        ):
            form.addRow(label, control)
        self.notes, self.terms, self.signature = (
            QCheckBox("Show notes"),
            QCheckBox("Show payment terms"),
            QCheckBox("Show signature area"),
        )
        for check in (self.notes, self.terms, self.signature):
            form.addRow(check)
        logo_row = QHBoxLayout()
        self.logo_label = QLabel("No logo")
        add_logo, clear_logo = QPushButton("Choose logo…"), QPushButton("Remove")
        add_logo.clicked.connect(self.choose_logo)
        clear_logo.clicked.connect(
            lambda: (setattr(self, "logo", ""), self.logo_label.setText("No logo"))
        )
        logo_row.addWidget(self.logo_label)
        logo_row.addWidget(add_logo)
        logo_row.addWidget(clear_logo)
        form.addRow("Logo", logo_row)
        self.columns, self.sections = QListWidget(), QListWidget()
        for name, listing in (
            ("Invoice column order", self.columns),
            ("Document section order", self.sections),
        ):
            listing.setDragDropMode(QAbstractItemView.DragDropMode.InternalMove)
            listing.setMaximumHeight(145)
            form.addRow(name, listing)
            controls = QHBoxLayout()
            for text, delta in (("Move up", -1), ("Move down", 1)):
                button = QPushButton(text)
                button.clicked.connect(lambda _checked=False, w=listing, d=delta: self.move(w, d))
                controls.addWidget(button)
            form.addRow(controls)
        info = QLabel(
            "Reorder sections and columns by dragging or using Move up/down. "
            "Required invoice facts remain present. Saving a version keeps "
            "earlier versions available to issued invoices."
        )
        info.setWordWrap(True)
        form.addRow(info)
        viewer = QWidget()
        view_layout = QVBoxLayout(viewer)
        view_layout.addWidget(QLabel("Actual PDF preview · sample data unless an invoice is open"))
        preview = QPushButton("Refresh preview")
        preview.clicked.connect(self.preview)
        view_layout.addWidget(preview)
        self.pdf = QPdfDocument(self)
        self.buffer = QBuffer(self)
        self.view = QPdfView(self)
        self.view.setDocument(self.pdf)
        self.view.setPageMode(QPdfView.PageMode.MultiPage)
        self.view.setZoomMode(QPdfView.ZoomMode.FitInView)
        view_layout.addWidget(self.view)
        splitter.addWidget(viewer)
        splitter.setSizes([500, 650])
        self.refresh()

    @staticmethod
    def combo(entries):
        field = QComboBox()
        for label, value in entries:
            field.addItem(label, value)
        return field

    @staticmethod
    def move(listing, delta):
        row = listing.currentRow()
        if 0 <= row + delta < listing.count():
            item = listing.takeItem(row)
            listing.insertItem(row + delta, item)
            listing.setCurrentRow(row + delta)

    def choose_colour(self, field):
        value = QColorDialog.getColor(parent=self)
        if value.isValid():
            field.setText(value.name().lstrip("#").upper())

    def refresh(self, select_id=None):
        def show(rows):
            self.versions = rows
            self.selector.blockSignals(True)
            self.selector.clear()
            for row in rows:
                self.selector.addItem(f"{row.layout.name} · v{row.version}", row.id)
            self.selector.setCurrentIndex(max(0, self.selector.findData(select_id)))
            self.selector.blockSignals(False)
            self.current = None
            self.select_template(self.selector.currentIndex())

        self.run(self.templates.list, show)

    def select_template(self, index):
        if not 0 <= index < len(self.versions):
            return
        if self.current and self.data() != self.current.layout:
            answer = QMessageBox.question(
                self,
                "Unsaved template",
                "Discard changes and select another template?",
                QMessageBox.StandardButton.Discard | QMessageBox.StandardButton.Cancel,
                QMessageBox.StandardButton.Cancel,
            )
            if answer != QMessageBox.StandardButton.Discard:
                self.selector.blockSignals(True)
                self.selector.setCurrentIndex(self.selector.findData(self.current.id))
                self.selector.blockSignals(False)
                return
        self.current = self.versions[index]
        layout = self.current.layout
        self.name.setText(layout.name)
        self.accent.setText(layout.accent)
        self.tint.setText(layout.tint)
        self.font.setCurrentIndex(self.font.findData(layout.font_family))
        self.alignment.setCurrentIndex(self.alignment.findData(layout.header_alignment))
        self.parties.setCurrentIndex(self.parties.findData(layout.party_layout))
        self.size.setValue(layout.font_size)
        self.margin.setValue(layout.margin_mm)
        self.spacing.setValue(layout.row_spacing)
        self.footer.setText(layout.footer_text)
        self.notes.setChecked(layout.show_notes)
        self.terms.setChecked(layout.show_terms)
        self.signature.setChecked(layout.show_signature)
        self.logo = layout.logo_png
        self.logo_label.setText("Logo attached" if self.logo else "No logo")
        self.columns.clear()
        self.fill_order(self.columns, layout.columns)
        self.sections.clear()
        self.fill_order(self.sections, layout.section_order)
        self.pdf.close()

    @staticmethod
    def fill_order(widget, keys):
        labels = {
            "description": "Item description",
            "quantity": "Quantity and unit",
            "unit_price": "Unit price",
            "gst_rate": "GST rate",
            "taxable": "Taxable amount",
            "total": "Line total",
            "parties": "Firm and customer",
            "metadata": "Invoice details",
            "items": "Items",
            "totals": "Totals and amount in words",
            "notes": "Notes",
            "terms": "Payment terms",
        }
        for key in keys:
            item = QListWidgetItem(labels[key])
            item.setData(Qt.ItemDataRole.UserRole, key)
            widget.addItem(item)

    def reject(self):
        if self.bridge.busy:
            return
        if self.current and self.data() != self.current.layout:
            answer = QMessageBox.question(
                self,
                "Unsaved template",
                "Discard the unsaved layout changes?",
                QMessageBox.StandardButton.Discard | QMessageBox.StandardButton.Cancel,
                QMessageBox.StandardButton.Cancel,
            )
            if answer != QMessageBox.StandardButton.Discard:
                return
        self.pdf.close()
        super().reject()

    def data(self):
        return InvoiceLayout(
            self.name.text(),
            self.accent.text().lstrip("#"),
            self.tint.text().lstrip("#"),
            self.font.currentData(),
            self.size.value(),
            self.margin.value(),
            self.alignment.currentData(),
            self.parties.currentData(),
            self.spacing.value(),
            self.footer.text(),
            self.notes.isChecked(),
            self.terms.isChecked(),
            self.signature.isChecked(),
            self.logo,
            tuple(
                self.columns.item(i).data(Qt.ItemDataRole.UserRole)
                for i in range(self.columns.count())
            ),
            tuple(
                self.sections.item(i).data(Qt.ItemDataRole.UserRole)
                for i in range(self.sections.count())
            ),
        )

    def save(self, copy):
        layout = self.data()
        current = self.current
        record_id = "" if copy or current is None else current.id
        version = 0 if copy or current is None else current.version

        def saved(template):
            self.refresh(template.id)

        self.run(lambda: self.templates.save(layout, record_id, version), saved)

    def choose_logo(self):
        path, _ = QFileDialog.getOpenFileName(
            self, "Choose firm logo", "", "Logo (*.png *.jpg *.jpeg)"
        )
        if not path:
            return
        try:
            if Path(path).stat().st_size > 2_000_000:
                raise ValueError("Choose a logo smaller than 2 MB.")
            content = Path(path).read_bytes()
        except (OSError, ValueError) as error:
            self.status.setText(str(error))
            return
        self.run(
            lambda: self.templates.normalize_logo(content),
            lambda logo: (setattr(self, "logo", logo), self.logo_label.setText("Logo attached")),
        )

    def preview(self):
        layout, data = self.data(), self.preview_data

        def show(content):
            self.pdf.close()
            self.buffer.close()
            self.buffer.setData(QByteArray(content))
            self.buffer.open(QIODevice.OpenModeFlag.ReadOnly)
            self.pdf.load(self.buffer)

        self.run(lambda: self.templates.preview(layout, data), show)

    def import_layout(self):
        path, _ = QFileDialog.getOpenFileName(self, "Import layout", "", "Invoice layout (*.json)")
        if not path:
            return
        try:
            if Path(path).stat().st_size > 3_000_000:
                raise ValueError("Layout file is too large.")
            content = Path(path).read_bytes()
        except (OSError, ValueError) as error:
            self.status.setText(str(error))
            return
        self.run(lambda: self.templates.import_layout(content), lambda row: self.refresh(row.id))

    def export_layout(self):
        if self.current and self.data() != self.current.layout:
            self.status.setText("Save the layout before exporting it.")
            return
        if self.current is None:
            return
        path, _ = QFileDialog.getSaveFileName(
            self, "Export saved layout", "invoice-layout.json", "Invoice layout (*.json)"
        )
        if not path:
            return

        def write(content):
            try:
                Path(path).write_bytes(content)
                self.status.setText("Saved layout exported: " + path)
            except OSError:
                self.status.setText("Could not write the selected file.")

        record_id = self.current.id
        self.run(lambda: self.templates.export_layout(record_id), write)
