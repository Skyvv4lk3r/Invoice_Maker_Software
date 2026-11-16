import hashlib
import json
import os
import sqlite3
import tempfile
from contextlib import closing
from io import BytesIO
from pathlib import Path
from uuid import uuid4
from zipfile import ZIP_DEFLATED, BadZipFile, ZipFile

from cryptography.exceptions import InvalidTag
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from cryptography.hazmat.primitives.kdf.scrypt import Scrypt

from invoice_generator.application.contracts.dto import ArtifactDTO
from invoice_generator.domain.models import ValidationError

# Limited, bounded archives keep verification and memory use predictable on a desktop.
MAX_BYTES = 128 * 1024 * 1024
MAGIC = b"INVO-BACKUP-1\x00"


def _key(passphrase, salt):
    if not 12 <= len(passphrase) <= 128:
        raise ValidationError("passphrase", "Use a backup passphrase of 12 to 128 characters.")
    return Scrypt(salt=salt, length=32, n=32768, r=8, p=1).derive(passphrase.encode())


class EncryptedBackupStore:
    def __init__(self, directory):
        self._directory = Path(directory)

    def create(self, destination, passphrase):
        def operation():
            target = Path(destination).expanduser().resolve()
            if target.exists():
                raise ValidationError(
                    "destination",
                    "Choose a new backup filename; existing files are never overwritten.",
                )
            salt, nonce = os.urandom(16), os.urandom(12)
            key = _key(passphrase, salt)
            with tempfile.TemporaryDirectory() as temporary:
                snapshot = Path(temporary) / "invoices.db"
                with (
                    closing(sqlite3.connect(self._directory / "invoices.db")) as source,
                    closing(sqlite3.connect(snapshot)) as db,
                ):
                    source.backup(db)
                if snapshot.stat().st_size > MAX_BYTES:
                    raise ValidationError("backup", "Database exceeds the 128 MB backup limit.")
                members = {"invoices.db": snapshot.read_bytes()}
                for path in sorted((self._directory / "exports").glob("*")):
                    if (
                        path.is_file()
                        and not path.is_symlink()
                        and path.suffix in (".pdf", ".docx", ".zip")
                    ):
                        if sum(map(len, members.values())) + path.stat().st_size > MAX_BYTES:
                            raise ValidationError(
                                "backup", "This workspace exceeds the 128 MB backup limit."
                            )
                        members["exports/" + path.name] = path.read_bytes()
                if sum(map(len, members.values())) > MAX_BYTES:
                    raise ValidationError(
                        "backup", "This workspace exceeds the 128 MB backup limit."
                    )
                manifest = {
                    name: hashlib.sha256(data).hexdigest() for name, data in members.items()
                }
                if len(members) >= 10000:
                    raise ValidationError("backup", "Backup supports up to 9,999 stored files.")
                buffer = BytesIO()
                with ZipFile(buffer, "w", ZIP_DEFLATED) as archive:
                    for name, data in members.items():
                        archive.writestr(name, data)
                    archive.writestr("manifest.json", json.dumps(manifest))
                content = (
                    MAGIC + salt + nonce + AESGCM(key).encrypt(nonce, buffer.getvalue(), MAGIC)
                )
                target.parent.mkdir(parents=True, exist_ok=True)
                temporary_file = target.with_name(target.name + "." + str(uuid4()) + ".tmp")
                try:
                    with temporary_file.open("xb") as file:
                        file.write(content)
                        file.flush()
                        os.fsync(file.fileno())
                    os.link(temporary_file, target)
                finally:
                    temporary_file.unlink(missing_ok=True)
                return ArtifactDTO(str(uuid4()), str(target))

        return operation()

    def restore_copy(self, source, passphrase, destination):
        def operation():
            path, target = Path(source).resolve(), Path(destination).resolve()
            if target.exists() and any(target.iterdir()):
                raise ValidationError(
                    "destination", "Choose an empty folder for the restored workspace."
                )
            if path.stat().st_size > MAX_BYTES + 2_000_000:
                raise ValidationError("backup", "Backup exceeds the supported size.")
            content = path.read_bytes()
            if not content.startswith(MAGIC) or len(content) < len(MAGIC) + 44:
                raise ValidationError(
                    "backup", "This is not an Invoice Workspace encrypted backup."
                )
            offset = len(MAGIC)
            salt, nonce = content[offset : offset + 16], content[offset + 16 : offset + 28]
            try:
                raw = AESGCM(_key(passphrase, salt)).decrypt(nonce, content[offset + 28 :], MAGIC)
            except InvalidTag as error:
                raise ValidationError(
                    "backup", "Incorrect passphrase or damaged backup."
                ) from error
            try:
                with ZipFile(BytesIO(raw)) as archive:
                    infos = archive.infolist()
                    if (
                        len(infos) > 10000
                        or sum(x.file_size for x in infos) > MAX_BYTES + 2_000_000
                    ):
                        raise ValueError
                    names = [x.filename for x in infos]
                    if (
                        len(names) != len(set(names))
                        or "manifest.json" not in names
                        or "invoices.db" not in names
                    ):
                        raise ValueError
                    manifest = json.loads(archive.read("manifest.json"))
                    if set(names) != set(manifest) | {"manifest.json"}:
                        raise ValueError
                    members = {}
                    for name in manifest:
                        parts = name.split("/")
                        if name != "invoices.db" and not (
                            len(parts) == 2
                            and parts[0] == "exports"
                            and parts[1] not in ("", ".", "..")
                            and "\\" not in name
                            and ":" not in name
                            and Path(parts[1]).suffix in (".pdf", ".docx", ".zip")
                        ):
                            raise ValueError
                        data = archive.read(name)
                        if hashlib.sha256(data).hexdigest() != manifest[name]:
                            raise ValueError
                        members[name] = data
            except (BadZipFile, ValueError, KeyError, TypeError) as error:
                raise ValidationError(
                    "backup", "The backup contents failed integrity verification."
                ) from error
            target.parent.mkdir(parents=True, exist_ok=True)
            with tempfile.TemporaryDirectory(dir=target.parent) as temporary:
                stage = Path(temporary) / "workspace"
                stage.mkdir()
                for name, data in members.items():
                    dest = stage / name
                    dest.parent.mkdir(parents=True, exist_ok=True)
                    dest.write_bytes(data)
                try:
                    with closing(sqlite3.connect(stage / "invoices.db")) as db:
                        if db.execute("PRAGMA integrity_check").fetchone()[0] != "ok":
                            raise ValueError
                        tables = {
                            x[0]
                            for x in db.execute("SELECT name FROM sqlite_master WHERE type='table'")
                        }
                        if (
                            not {
                                "workspace_owner",
                                "invoice_draft",
                                "template_version",
                                "alembic_version",
                            }
                            <= tables
                        ):
                            raise ValueError
                        if db.execute("SELECT version_num FROM alembic_version").fetchall() != [
                            ("0003_issuance",)
                        ]:
                            raise ValueError
                except (sqlite3.Error, ValueError) as error:
                    raise ValidationError(
                        "backup", "The restored database failed verification."
                    ) from error
                if target.exists():
                    target.rmdir()
                stage.rename(target)
            return str(target)

        return operation()
