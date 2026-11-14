import pytest

pytest.importorskip("PySide6")
pytest.importorskip("pytestqt")

from PySide6.QtWidgets import QTableWidgetItem

from invoice_generator.presentation.qt.main_window import MainWindow
from invoice_generator.presentation.view_model import DraftViewModel


def test_desktop_save_and_pdf(qtbot, backend):
    window = MainWindow(
        DraftViewModel(backend.commands, backend.queries, backend.pdfs, backend.artifacts)
    )
    qtbot.addWidget(window)
    window.show()
    qtbot.waitUntil(lambda: not window.bridge.busy)
    window.firm.setText("Example Firm")
    window.customer.setText("Example Customer")
    window.mode.setCurrentIndex(window.mode.findData("IGST"))
    for index, text in enumerate(["Example item", "2", "100", "18"]):
        window.items.setItem(0, index, QTableWidgetItem(text))
    window.save(export_pdf=True)
    qtbot.waitUntil(lambda: not window.bridge.busy, timeout=10000)
    assert window.vm.current is not None
    assert window.vm.current.totals.total_paise == 23600
    assert window.reveal_button.isEnabled()
    assert len(tuple((backend.directory / "exports").glob("*.pdf"))) == 1
    assert window.invoices.rowCount() == 1
    window.close()


def full_window(qtbot, backend):
    window = MainWindow(
        DraftViewModel(
            backend.commands,
            backend.queries,
            backend.pdfs,
            backend.artifacts,
            backend.words,
            backend.previews,
            backend.range_exports,
        )
    )
    qtbot.addWidget(window)
    window.show()
    qtbot.waitUntil(lambda: not window.bridge.busy)
    return window


def fill_form(window):
    window.new_draft()
    window.firm.setText("Example Firm")
    window.customer.setText("Example Customer")
    window.mode.setCurrentIndex(window.mode.findData("IGST"))
    for index, text in enumerate(["Design service", "2", "100", "18"]):
        window.items.setItem(0, index, QTableWidgetItem(text))


def test_automatic_totals_preview_word_and_search(qtbot, backend):
    from PySide6.QtWidgets import QLabel

    window = full_window(qtbot, backend)
    fill_form(window)
    qtbot.waitUntil(lambda: window.total.text() == "INR 236.00", timeout=5000)
    assert window.find(QLabel, "stickyTotal").text() == "Total  INR 236.00"
    window.preview()
    qtbot.waitUntil(lambda: not window.bridge.busy, timeout=10000)
    qtbot.waitUntil(lambda: window.pdf_document.pageCount() == 1, timeout=5000)
    assert window.vm.current is None
    assert window._dirty
    window.save(export_word=True)
    qtbot.waitUntil(lambda: not window.bridge.busy, timeout=10000)
    assert not window._dirty
    assert len(tuple((backend.directory / "exports").glob("*.docx"))) == 1
    window.show_library()
    qtbot.waitUntil(lambda: not window.bridge.busy)
    window.search.setText("not-present")
    assert window.invoices.rowCount() == 0
    window.search.setText("example")
    assert window.invoices.rowCount() == 1
    window.close()


def test_unsaved_navigation_can_cancel_or_save(qtbot, backend, monkeypatch):
    from PySide6.QtWidgets import QMessageBox

    window = full_window(qtbot, backend)
    fill_form(window)
    monkeypatch.setattr(QMessageBox, "question", lambda *a: QMessageBox.StandardButton.Cancel)
    window.new_draft()
    assert window.customer.text() == "Example Customer"
    assert window._dirty
    monkeypatch.setattr(QMessageBox, "question", lambda *a: QMessageBox.StandardButton.Save)
    window.show_library()
    qtbot.waitUntil(lambda: not window.bridge.busy, timeout=10000)
    assert window.pages.currentIndex() == 0
    assert not window._dirty
    assert window.invoices.rowCount() == 1
    window.close()


def test_invalid_edit_clears_stale_totals_and_close_can_discard(qtbot, backend, monkeypatch):
    from PySide6.QtWidgets import QMessageBox

    window = full_window(qtbot, backend)
    fill_form(window)
    qtbot.waitUntil(lambda: window.total.text() == "INR 236.00", timeout=5000)
    window.items.item(0, 2).setText("not money")
    assert window.total.text() == "—"
    qtbot.waitUntil(lambda: not window.auto_timer.isActive() and not window.bridge.busy)
    monkeypatch.setattr(QMessageBox, "question", lambda *a: QMessageBox.StandardButton.Discard)
    window.close()
    qtbot.waitUntil(lambda: not window.isVisible())


def test_range_export_ignores_search_and_uses_date_boundaries(qtbot, backend):
    from dataclasses import replace
    from datetime import date

    from PySide6.QtCore import QDate

    from invoice_generator.application.contracts.dto import DraftInput, LineInput, SaveDraftRequest

    data = DraftInput(
        "Firm",
        "Customer",
        date.today().isoformat(),
        "IGST",
        (LineInput("Goods", "1", "100", "18"),),
    )
    backend.commands.save(SaveDraftRequest(data))
    backend.commands.save(SaveDraftRequest(replace(data, customer_name="Another")))
    window = full_window(qtbot, backend)
    window.start.setDate(QDate.currentDate())
    window.end.setDate(QDate.currentDate())
    window.search.setText("Customer")
    assert window.invoices.rowCount() == 1
    window.export_range()
    qtbot.waitUntil(lambda: not window.bridge.busy, timeout=15000)
    assert "2 drafts" in window.status.text()
    assert window.reveal_button.isEnabled()
    assert len(list((backend.directory / "exports").glob("*.zip"))) == 1
    window.close()
