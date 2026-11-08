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
