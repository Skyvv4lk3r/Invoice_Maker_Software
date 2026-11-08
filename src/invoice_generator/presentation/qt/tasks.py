import logging
from uuid import uuid4

from PySide6.QtCore import QObject, QRunnable, QThreadPool, Signal, Slot

from invoice_generator.application.contracts.dto import ApplicationError, Result


class _Signals(QObject):
    completed = Signal(str, object)


class _Task(QRunnable):
    def __init__(self, key, operation):
        super().__init__()
        self.key, self.operation = key, operation
        self.signals = _Signals()

    @Slot()
    def run(self):
        try:
            result = self.operation()
        except Exception as error:
            # Do not include entered invoice data in the generic diagnostic.
            logging.getLogger(__name__).error("Task %s failed (%s)", self.key, type(error).__name__)
            result = Result(
                error=ApplicationError(
                    "INTERNAL", "The operation failed. Please retry.", correlation_id=self.key
                )
            )
        self.signals.completed.emit(self.key, result)


class QtTaskBridge(QObject):
    """All worker calls receive captured requests; callbacks execute on the GUI thread."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self._pool = QThreadPool(self)
        self._pool.setMaxThreadCount(1)
        self._pending = {}

    @property
    def busy(self):
        return bool(self._pending)

    def submit(self, operation, callback):
        key = str(uuid4())
        task = _Task(key, operation)
        self._pending[key] = (task, callback)
        task.signals.completed.connect(self._complete)
        self._pool.start(task)

    @Slot(str, object)
    def _complete(self, key, result):
        _task, callback = self._pending.pop(key)
        callback(result)
