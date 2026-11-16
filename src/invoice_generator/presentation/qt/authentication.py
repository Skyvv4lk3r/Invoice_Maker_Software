from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QApplication,
    QDialog,
    QFileDialog,
    QFormLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QStackedWidget,
    QVBoxLayout,
    QWidget,
)

from invoice_generator.application.contracts.workspace import OwnerSetup
from invoice_generator.presentation.qt.tasks import QtTaskBridge

AUTH_STYLE = """
QDialog { background: #F5F8F6; }
QWidget { font-family: 'Segoe UI', sans-serif; font-size: 13px; color: #254438; }
QLabel#brand { font-size: 38px; font-weight: 800; color: #1D4D3B; }
QLabel#heading { font-size: 24px; font-weight: 700; margin: 12px 0; }
QLineEdit { background: white; border: 1px solid #CADAD0; border-radius: 6px; padding: 11px; }
QPushButton { background: #28664F; color: white; border: none; border-radius: 6px;
 padding: 12px; font-weight: 600; }
QPushButton:disabled { background: #AEC5B8; }
QPushButton#secondary { background: transparent; color: #527461; }
QLabel#error { color: #A44F42; }
"""


def password_field():
    field = QLineEdit()
    field.setEchoMode(QLineEdit.EchoMode.Password)
    field.setMaxLength(128)
    field.setPlaceholderText("At least 12 characters")
    return field


class RecoveryDialog(QDialog):
    def __init__(self, code, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Save your recovery code")
        self.setStyleSheet(AUTH_STYLE)
        self.resize(540, 270)
        layout = QVBoxLayout(self)
        title = QLabel("Keep this recovery code")
        title.setObjectName("heading")
        layout.addWidget(title)
        label = QLabel(
            "Use it to reset your owner password if you forget it. A password "
            "reset creates a new code and invalidates this one."
        )
        label.setWordWrap(True)
        layout.addWidget(label)
        field = QLineEdit(code)
        field.setReadOnly(True)
        layout.addWidget(field)
        copy = QPushButton("Copy recovery code")
        copy.clicked.connect(lambda: QApplication.clipboard().setText(code))
        layout.addWidget(copy)
        done = QPushButton("I have saved the code · Continue")
        done.clicked.connect(self.accept)
        layout.addWidget(done)


class AuthenticationDialog(QDialog):
    def __init__(self, auth, parent=None, allow_workspace=False):
        super().__init__(parent)
        self.workspace_path = ""
        self.auth = auth
        self.bridge = QtTaskBridge(self)
        self.setWindowTitle("Invoice Workspace · Sign in")
        self.setStyleSheet(AUTH_STYLE)
        self.setMinimumWidth(500)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(38, 28, 38, 30)
        layout.setSpacing(14)
        brand = QLabel("invo.")
        brand.setObjectName("brand")
        layout.addWidget(brand)
        self.heading = QLabel()
        self.heading.setObjectName("heading")
        layout.addWidget(self.heading)
        hint = QLabel("Your firm, invoices and templates in one local workspace.")
        hint.setWordWrap(True)
        layout.addWidget(hint)
        self.pages = QStackedWidget()
        layout.addWidget(self.pages)
        self.setup_page, self.login_page, self.recovery_page = QWidget(), QWidget(), QWidget()
        for page in (self.setup_page, self.login_page, self.recovery_page):
            self.pages.addWidget(page)
        setup = QFormLayout(self.setup_page)
        self.firm, self.owner = QLineEdit(), QLineEdit()
        self.setup_password, self.confirm = password_field(), password_field()
        for label, widget in (
            ("Firm name", self.firm),
            ("Owner username", self.owner),
            ("Password", self.setup_password),
            ("Confirm password", self.confirm),
        ):
            setup.addRow(label, widget)
        login = QFormLayout(self.login_page)
        self.username, self.password = QLineEdit(), password_field()
        self.password.setPlaceholderText("Your owner password")
        login.addRow("Username", self.username)
        login.addRow("Password", self.password)
        recovery = QFormLayout(self.recovery_page)
        self.recovery_user, self.recovery_code = QLineEdit(), password_field()
        self.new_password, self.new_confirm = password_field(), password_field()
        for label, field in (
            ("Username", self.recovery_user),
            ("Recovery code", self.recovery_code),
            ("New password", self.new_password),
            ("Confirm password", self.new_confirm),
        ):
            recovery.addRow(label, field)
        self.error = QLabel()
        self.error.setObjectName("error")
        self.error.setWordWrap(True)
        layout.addWidget(self.error)
        self.submit = QPushButton()
        self.submit.clicked.connect(self.authenticate)
        self.submit.setDefault(True)
        layout.addWidget(self.submit)
        self.switch = QPushButton("Forgot password? Use recovery code")
        self.switch.setObjectName("secondary")
        self.switch.clicked.connect(self.toggle_recovery)
        layout.addWidget(self.switch)
        note = QLabel("Local owner access · Automatic lock after 15 minutes of inactivity")
        note.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(note)
        if allow_workspace:
            opening = QPushButton("Open another workspace folder…")
            opening.setObjectName("secondary")
            opening.clicked.connect(self.choose_workspace)
            layout.addWidget(opening)
        state = self.auth.state()
        self.configured = bool(state.value and state.value.configured)
        self._page(1 if self.configured else 0)
        if state.error:
            self.error.setText(state.error.message)

    def choose_workspace(self):
        if self.bridge.busy:
            return
        path = QFileDialog.getExistingDirectory(self, "Open an existing or restored workspace")
        if path:
            from pathlib import Path

            if not (Path(path) / "invoices.db").is_file():
                self.error.setText("Choose a workspace folder containing invoices.db.")
                return
            self.workspace_path = path
            self.reject()

    def _page(self, page):
        self.pages.setCurrentIndex(page)
        self.heading.setText(["Set up your firm", "Welcome back", "Recover owner access"][page])
        self.submit.setText(["Create firm workspace", "Sign in", "Reset password"][page])
        self.switch.setVisible(page != 0)
        self.switch.setText(
            "Back to sign in" if page == 2 else "Forgot password? Use recovery code"
        )
        self.error.clear()

    def toggle_recovery(self):
        self._page(1 if self.pages.currentIndex() == 2 else 2)

    def authenticate(self):
        page = self.pages.currentIndex()
        if page == 0:
            if self.setup_password.text() != self.confirm.text():
                self.error.setText("The passwords do not match.")
                return
            request = OwnerSetup(self.firm.text(), self.owner.text(), self.setup_password.text())

            def operation():
                return self.auth.setup(request)
        elif page == 1:
            username, password = self.username.text(), self.password.text()

            def operation():
                return self.auth.login(username, password)
        else:
            if self.new_password.text() != self.new_confirm.text():
                self.error.setText("The new passwords do not match.")
                return
            username, code, password = (
                self.recovery_user.text(),
                self.recovery_code.text(),
                self.new_password.text(),
            )

            def operation():
                return self.auth.recover(username, code, password)

        self.submit.setEnabled(False)
        self.pages.setEnabled(False)
        self.switch.setEnabled(False)
        self.error.setText("Checking…")

        def finished(result):
            self.submit.setEnabled(True)
            self.pages.setEnabled(True)
            self.switch.setEnabled(True)
            if result.error:
                self.error.setText(result.error.message)
                return
            for field in (
                self.password,
                self.setup_password,
                self.confirm,
                self.recovery_code,
                self.new_password,
                self.new_confirm,
            ):
                field.clear()
            if page in (0, 2):
                RecoveryDialog(result.value.code, self).exec()
            if page == 2:
                self._page(1)
                self.error.setText("Password updated. Sign in with your new password.")
            else:
                self.accept()

        self.bridge.submit(operation, finished)

    def reject(self):
        if not self.bridge.busy:
            super().reject()
