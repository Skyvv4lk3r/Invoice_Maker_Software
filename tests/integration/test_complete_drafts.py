import csv
import json
from dataclasses import replace
from io import BytesIO, StringIO
from zipfile import ZipFile

import pytest
from docx import Document

from invoice_generator.application.contracts.dto import (
    DateRange,
    DraftReference,
    PartyDetails,
    SaveDraftRequest,
)
from invoice_generator.application.handlers.drafts import build_draft
from invoice_generator.infrastructure.persistence.repositories import decode, encode


@pytest.fixture
def complete(sample):
    return replace(
        sample,
        firm_details=PartyDetails(
            "12 Example Road\nAhmedabad 380001",
            "24ABCDE1234F1Z5",
            "Gujarat",
            "firm@example.invalid",
            "0000000000",
        ),
        customer_details=PartyDetails("45 Sample Lane", "", "Gujarat"),
        place_of_supply="Gujarat",
        reference="PO-DEMO-001",
        due_date="2026-04-30",
        notes="Fictional draft for testing.",
        terms="Payment in 30 days.",
        template_id="classic",
        lines=(replace(sample.lines[0], item_type="SERVICES", hsn_sac="998314", unit="Hours"),),
    )


def test_extended_fields_and_line_totals_survive_save_reload(backend, complete):
    saved = backend.commands.save(SaveDraftRequest(complete)).value
    assert saved.data == complete
    assert backend.queries.get(saved.id).value == saved
    assert saved.totals.lines[0].total_paise == 23600
    assert saved.totals.lines[0].cgst_paise == 1800
    assert saved.totals.lines[0].sgst_paise == 1800


def test_previous_payload_remains_readable(sample):
    original = build_draft(sample, "12345678-1234-1234-1234-123456789abc", 1)
    legacy = json.loads(encode(original))
    for field in (
        "firm_details",
        "customer_details",
        "place_of_supply",
        "reference",
        "due_date",
        "notes",
        "terms",
        "template_id",
    ):
        legacy.pop(field)
    for line in legacy["lines"]:
        for field in ("item_type", "hsn_sac", "unit"):
            line.pop(field)
    restored = decode(json.dumps(legacy))
    assert restored == original


@pytest.mark.parametrize(
    "change,field",
    [
        ({"firm_details": PartyDetails(gstin="invalid")}, "firm_details.gstin"),
        ({"due_date": "2026-03-31"}, "due_date"),
        ({"template_id": "missing"}, "id"),
        ({"notes": "bad\x00text"}, "notes"),
    ],
)
def test_new_fields_are_validated(backend, complete, change, field):
    result = backend.commands.save(SaveDraftRequest(replace(complete, **change)))
    assert result.error.code == "VALIDATION"
    assert result.error.field == field


def test_preview_is_pdf_and_does_not_save(backend, complete):
    result = backend.previews.preview(complete)
    assert result.value.startswith(b"%PDF-")
    assert backend.queries.list(DateRange("2026-01-01", "2026-12-31")).value == ()
    assert not list((backend.directory / "exports").iterdir())


def test_word_contains_details_and_same_totals_as_saved_draft(backend, complete):
    saved = backend.commands.save(SaveDraftRequest(complete)).value
    artifact = backend.words.export(DraftReference(saved.id, saved.revision)).value
    document = Document(backend.directory / "exports" / artifact.display_name)
    text = "\n".join(p.text for p in document.paragraphs)
    tables = "\n".join(
        cell.text for table in document.tables for row in table.rows for cell in row.cells
    )
    assert "DRAFT INVOICE" in text
    assert "TOTAL: INR 236.00" in text
    assert "Rupees Two Hundred Thirty Six Only" in text
    assert "PO-DEMO-001" in text
    assert "24ABCDE1234F1Z5" in tables
    assert "998314" in tables
    assert "Hours" in tables
    backend.commands.save(SaveDraftRequest(complete, saved.id, saved.revision))
    assert backend.words.export(DraftReference(saved.id, saved.revision)).error.code == "CONFLICT"


def test_date_range_bundle_contains_all_and_only_matching_revisions(backend, complete):
    included = []
    for day in ("2026-03-31", "2026-04-01", "2026-04-30", "2026-05-01"):
        data = replace(complete, invoice_date=day, due_date="", customer_name="=SUM(1,2)")
        saved = backend.commands.save(SaveDraftRequest(data)).value
        if day.startswith("2026-04"):
            included.append(saved)
    deleted = backend.commands.save(SaveDraftRequest(complete)).value
    backend.commands.delete(DraftReference(deleted.id, deleted.revision))
    receipt = backend.range_exports.export_range(DateRange("2026-04-01", "2026-04-30")).value
    assert receipt.invoice_count == 2
    path = backend.directory / "exports" / receipt.artifact.display_name
    with ZipFile(path) as archive:
        manifest = json.loads(archive.read("manifest.json"))
        assert {x["id"] for x in manifest["invoices"]} == {x.id for x in included}
        assert all(x["revision"] == 1 for x in manifest["invoices"])
        register = list(csv.DictReader(StringIO(archive.read("invoices.csv").decode("utf-8-sig"))))
        assert len(register) == 2
        assert all(x["Customer"] == "'=SUM(1,2)" for x in register)
        assert all(x["Total INR"] == "236.00" for x in register)
        for item in manifest["invoices"]:
            assert archive.read(item["pdf"]).startswith(b"%PDF-")
            document = Document(BytesIO(archive.read(item["word"])))
            assert "TOTAL: INR 236.00" in "\n".join(p.text for p in document.paragraphs)
    assert not list(path.parent.glob("*.tmp"))


def test_empty_or_reversed_date_range_produces_no_export(backend):
    for dates in (DateRange("2026-04-01", "2026-04-30"), DateRange("2026-05-01", "2026-04-30")):
        assert backend.range_exports.export_range(dates).error.code == "VALIDATION"
    assert not list((backend.directory / "exports").iterdir())
