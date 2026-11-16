from invoice_generator.application.handlers.drafts import safe_result


class BackupService:
    def __init__(self, store):
        self._store = store

    def create(self, destination, passphrase):
        return safe_result(lambda: self._store.create(destination, passphrase))

    def restore_copy(self, source, passphrase, destination):
        return safe_result(lambda: self._store.restore_copy(source, passphrase, destination))
