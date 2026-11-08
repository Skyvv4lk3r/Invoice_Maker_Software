import os
import subprocess
import sys
from pathlib import Path
from uuid import UUID, uuid4

from invoice_generator.application.contracts.dto import ArtifactDTO
from invoice_generator.application.ports.persistence import MissingError


class LocalArtifactStore:
    def __init__(self, directory: Path):
        self._directory = directory.resolve()
        self._directory.mkdir(parents=True, exist_ok=True)

    def publish_pdf(self, data: bytes) -> ArtifactDTO:
        artifact_id = str(uuid4())
        path = self._directory / f"draft-{artifact_id}.pdf"
        temporary = path.with_suffix(".tmp")
        try:
            with temporary.open("xb") as file:
                file.write(data)
                file.flush()
                os.fsync(file.fileno())
            os.replace(temporary, path)
        finally:
            temporary.unlink(missing_ok=True)
        return ArtifactDTO(artifact_id, path.name)

    def reveal(self, artifact_id: str) -> None:
        path = self._directory / f"draft-{UUID(artifact_id)}.pdf"
        if not path.is_file():
            raise MissingError
        if sys.platform == "win32":
            subprocess.Popen(["explorer.exe", "/select,", str(path)])
        elif sys.platform == "darwin":
            subprocess.Popen(["open", "-R", str(path)])
        else:
            subprocess.Popen(["xdg-open", str(self._directory)])
