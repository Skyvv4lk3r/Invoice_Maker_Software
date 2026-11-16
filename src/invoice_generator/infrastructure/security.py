from argon2 import PasswordHasher
from argon2.exceptions import InvalidHashError, VerificationError
from argon2.low_level import Type


class ArgonPasswordHasher:
    def __init__(self):
        self._hasher = PasswordHasher(time_cost=2, memory_cost=19456, parallelism=1, type=Type.ID)

    def hash(self, password: str) -> str:
        return self._hasher.hash(password)

    def verify(self, encoded: str, password: str) -> bool:
        if not 1 <= len(password) <= 128:
            return False
        try:
            return self._hasher.verify(encoded, password)
        except (VerificationError, InvalidHashError):
            return False
