import pytest

pytest.importorskip("PySide6")
pytest.importorskip("pytestqt")

from PySide6.QtWidgets import QDialog, QMessageBox

from invoice_generator.presentation.qt.authentication import AuthenticationDialog, RecoveryDialog
from invoice_generator.presentation.qt.main_window import MainWindow
from invoice_generator.presentation.qt.template_designer import TemplateDesigner
from invoice_generator.presentation.view_model import DraftViewModel


def workspace(qtbot, backend):
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
    qtbot.addWidget(window)
    window.show()
    qtbot.waitUntil(lambda: window._firm_profile is not None and not window.bridge.busy)
    return window


def test_login_rejects_wrong_password_and_accepts_owner(qtbot, backend):
    backend.auth.logout()
    dialog = AuthenticationDialog(backend.auth)
    qtbot.addWidget(dialog)
    dialog.show()
    dialog.username.setText("test-owner")
    dialog.password.setText("wrong")
    dialog.authenticate()
    qtbot.waitUntil(lambda: not dialog.bridge.busy)
    assert dialog.isVisible() and "Incorrect" in dialog.error.text()
    dialog.password.setText("test-password-1234")
    dialog.authenticate()
    qtbot.waitUntil(lambda: not dialog.bridge.busy)
    assert dialog.result() == QDialog.DialogCode.Accepted
    assert dialog.password.text() == ""


def test_profile_prefills_editor_and_lock_preserves_unsaved(qtbot, backend, monkeypatch):
    window = workspace(qtbot, backend)
    window.new_draft()
    assert window.firm.text() == "Demo Firm" and window.firm.isReadOnly()
    window.customer.setText("Unsaved customer")
    qtbot.waitUntil(lambda: not window.bridge.busy and not window.auto_timer.isActive())

    def unlock(dialog):
        assert not window.isVisible()
        assert not backend.auth.state().value.signed_in
        assert backend.auth.login("test-owner", "test-password-1234").error is None
        return QDialog.DialogCode.Accepted

    monkeypatch.setattr(AuthenticationDialog, "exec", unlock)
    window.lock_workspace()
    assert window.isVisible() and window._dirty
    assert window.customer.text() == "Unsaved customer"
    monkeypatch.setattr(QMessageBox, "question", lambda *a: QMessageBox.StandardButton.Discard)
    window.close()
    qtbot.waitUntil(lambda: not window.isVisible())
    assert not backend.auth.state().value.signed_in


def test_template_designer_saves_and_previews_real_pdf(qtbot, backend, sample):
    dialog = TemplateDesigner(backend.templates, sample)
    qtbot.addWidget(dialog)
    dialog.show()
    qtbot.waitUntil(lambda: dialog.current is not None and not dialog.bridge.busy)
    dialog.name.setText("My custom layout")
    dialog.accent.setText("123456")
    dialog.save(True)
    qtbot.waitUntil(lambda: not dialog.bridge.busy)
    assert any(x.layout.name == "My custom layout" for x in backend.templates.list().value)
    dialog.preview()
    qtbot.waitUntil(lambda: not dialog.bridge.busy)
    qtbot.waitUntil(lambda: dialog.pdf.pageCount() == 1)
    assert not dialog.status.text()
    dialog.close()


def test_setup_first_run_displays_recovery_code(qtbot, tmp_path, monkeypatch):
    from invoice_generator.bootstrap import build_backend

    backend = build_backend(tmp_path / "onboarding")
    seen = []
    monkeypatch.setattr(RecoveryDialog, "exec", lambda self: seen.append(True))
    try:
        dialog = AuthenticationDialog(backend.auth)
        qtbot.addWidget(dialog)
        dialog.show()
        assert dialog.pages.currentIndex() == 0
        dialog.firm.setText("My Firm")
        dialog.owner.setText("owner")
        dialog.setup_password.setText("strong-password-123")
        dialog.confirm.setText("strong-password-123")
        dialog.authenticate()
        qtbot.waitUntil(lambda: not dialog.bridge.busy)
        assert seen and dialog.result() == QDialog.DialogCode.Accepted
        assert backend.auth.state().value.signed_in
    finally:
        backend.close()
