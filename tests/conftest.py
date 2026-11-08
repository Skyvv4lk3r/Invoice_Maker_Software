import pytest

from invoice_generator.application.contracts.dto import DraftInput, LineInput
from invoice_generator.bootstrap import build_backend


@pytest.fixture
def sample():
    return DraftInput(
        "Demo Firm",
        "Example Customer",
        "2026-04-01",
        "CGST_SGST",
        (LineInput("Example goods", "2", "100.00", "18"),),
    )


@pytest.fixture
def backend(tmp_path):
    app = build_backend(tmp_path / "app-data")
    yield app
    app.close()
