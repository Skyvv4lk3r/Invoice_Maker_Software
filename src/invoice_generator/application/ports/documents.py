from typing import Protocol

from invoice_generator.application.contracts.dto import ArtifactDTO, DraftPdfModel


class IDraftPdfRenderer(Protocol):
    def render(self, model: DraftPdfModel) -> bytes: ...


class IArtifactStore(Protocol):
    def publish_pdf(self, data: bytes) -> ArtifactDTO: ...
    def reveal(self, artifact_id: str) -> None: ...
