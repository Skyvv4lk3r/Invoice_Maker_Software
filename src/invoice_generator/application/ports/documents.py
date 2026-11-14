from typing import Protocol

from invoice_generator.application.contracts.dto import ArtifactDTO, DateRange, DraftPdfModel


class IDraftPdfRenderer(Protocol):
    def render(self, model: DraftPdfModel) -> bytes: ...


class IArtifactStore(Protocol):
    def publish_pdf(self, data: bytes) -> ArtifactDTO: ...
    def publish(self, data: bytes, extension: str) -> ArtifactDTO: ...
    def reveal(self, artifact_id: str) -> None: ...


class IDraftBundleRenderer(Protocol):
    def render(self, models: tuple[DraftPdfModel, ...], dates: DateRange) -> bytes: ...
