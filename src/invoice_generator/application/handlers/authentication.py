import secrets
import time
from threading import RLock

from invoice_generator.application.contracts.dto import ApplicationError, Result
from invoice_generator.application.contracts.workspace import (
    AccountState,
    FirmProfile,
    OwnerSetup,
    RecoveryKey,
)
from invoice_generator.application.handlers.drafts import safe_result
from invoice_generator.application.ports.workspace import (
    IIdentityStore,
    IPasswordHasher,
    OwnerCredentials,
)
from invoice_generator.domain.models import ValidationError


class AuthenticationService:
    """One local owner, with an expiring process-local session and persisted throttling."""

    def __init__(self, store: IIdentityStore, hasher: IPasswordHasher, clock=time.time):
        self._store, self._hasher, self._clock = store, hasher, clock
        self._epoch = None
        self._last_activity = 0
        self._lock = RLock()
        self.idle_seconds = 15 * 60
        self._dummy_hash = hasher.hash(secrets.token_urlsafe(32))

    def _valid_session(self):
        owner = self._store.get_owner()
        valid = (
            owner is not None
            and self._epoch == owner.epoch
            and (0 <= self._clock() - self._last_activity < self.idle_seconds)
        )
        if not valid:
            self._epoch = None
        return owner if valid else None

    def authorize(self):
        with self._lock:
            if self._valid_session() is None:
                return ApplicationError("AUTH_REQUIRED", "Sign in to your firm workspace.")
            self._last_activity = self._clock()
        return None

    def protect(self, operation):
        check = safe_result(lambda: self.authorize() or True)
        if check.error:
            return check
        return Result(error=check.value) if check.value is not True else operation()

    def state(self):
        def operation():
            with self._lock:
                owner = self._store.get_owner()
                active = self._valid_session() is not None
                return AccountState(owner is not None, active, owner.username if active else "")

        return safe_result(operation)

    @staticmethod
    def _password(value):
        if not 12 <= len(value) <= 128:
            raise ValidationError("password", "Use a password of 12 to 128 characters.")

    @staticmethod
    def _username(value):
        name = value.strip().casefold()
        if not 3 <= len(name) <= 80 or not all(ch.isalnum() or ch in "._@-" for ch in name):
            raise ValidationError("username", "Use 3 to 80 letters, numbers, dots, @, _ or -.")
        return name

    def setup(self, request: OwnerSetup):
        def operation():
            with self._lock:
                if self._store.get_owner() is not None:
                    raise ValidationError(
                        "account", "This workspace already has an owner. Sign in."
                    )
                self._password(request.password)
                name = self._username(request.username)
                if not 1 <= len(request.firm_name.strip()) <= 200:
                    raise ValidationError(
                        "firm_name", "Enter your firm's name (up to 200 characters)."
                    )
                code = secrets.token_urlsafe(24)
                owner = OwnerCredentials(
                    name, self._hasher.hash(request.password), self._hasher.hash(code)
                )
                self._store.create_owner(owner, FirmProfile(request.firm_name.strip(), revision=1))
                self._epoch, self._last_activity = 1, self._clock()
                return RecoveryKey(code)

        return safe_result(operation)

    def login(self, username, password):
        def operation():
            with self._lock:
                self._epoch = None
                owner = self._store.get_owner()
                now = self._clock()
                if owner and owner.locked_until > now:
                    raise ValidationError(
                        "login", "Too many attempts. Wait five minutes and try again."
                    )
                eligible = owner is not None and username.strip().casefold() == owner.username
                valid = self._hasher.verify(
                    owner.password_hash if eligible else self._dummy_hash, password
                )
                if owner:
                    self._store.record_attempt(owner.epoch, bool(eligible and valid), now)
                if not eligible or not valid:
                    raise ValidationError("login", "Incorrect username or password.")
                self._epoch, self._last_activity = owner.epoch, now
                return True

        return safe_result(operation)

    def logout(self):
        with self._lock:
            self._epoch = None
        return Result(value=True)

    def touch(self):
        return self.protect(lambda: Result(value=True))

    def _rotate(self, owner, new):
        self._password(new)
        code = secrets.token_urlsafe(24)
        self._store.replace_credentials(
            owner.epoch, self._hasher.hash(new), self._hasher.hash(code)
        )
        self._epoch = None
        return RecoveryKey(code)

    def change_password(self, current, new):
        def operation():
            with self._lock:
                owner = self._valid_session()
                now = self._clock()
                if owner and owner.locked_until > now:
                    raise ValidationError("password", "Too many attempts. Wait five minutes.")
                if owner is None or not self._hasher.verify(owner.password_hash, current):
                    if owner:
                        self._store.record_attempt(owner.epoch, False, now)
                    raise ValidationError(
                        "password", "The current password is incorrect or the session expired."
                    )
                return self._rotate(owner, new)

        return safe_result(operation)

    def recover(self, username, recovery_code, new_password):
        def operation():
            with self._lock:
                owner = self._store.get_owner()
                now = self._clock()
                if owner and owner.locked_until > now:
                    raise ValidationError(
                        "login", "Too many attempts. Wait five minutes and try again."
                    )
                eligible = owner is not None and username.strip().casefold() == owner.username
                valid = self._hasher.verify(
                    owner.recovery_hash if eligible else self._dummy_hash, recovery_code
                )
                if owner:
                    self._store.record_attempt(owner.epoch, bool(eligible and valid), now)
                if not eligible or not valid:
                    raise ValidationError("recovery", "Incorrect username or recovery code.")
                return self._rotate(owner, new_password)

        return safe_result(operation)
