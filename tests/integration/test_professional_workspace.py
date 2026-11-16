"""Regressions for identity, versioned branding, issuance and disaster recovery."""

import base64
import csv
import json
import sqlite3
from concurrent.futures import ThreadPoolExecutor
from dataclasses import asdict, replace
from io import BytesIO, StringIO
from uuid import uuid4
from zipfile import ZipFile

import pytest
from PIL import Image

from invoice_generator.application.contracts.dto import (
    DateRange,
    DraftInput,
    DraftReference,
    LineInput,
    PartyDetails,
    SaveDraftRequest,
)
from invoice_generator.application.contracts.issuance import IssueRequest
from invoice_generator.application.contracts.workspace import (
    CustomerRecord,
    InvoiceLayout,
    ItemRecord,
    OwnerSetup,
)
from invoice_generator.bootstrap import build_backend

PASSWORD = "test-password-1234"
DATES = DateRange("2025-01-01", "2026-11-16")


def value(result):
    assert result.error is None, result.error
    return result.value


def ready_firm(backend):
    # Fictional PAN and checksum, never a real firm's details.
    alphabet = "0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZ"
    body = "24AAAAA0000A1Z"
    factor, total = 2, 0
    for char in reversed(body):
        product = alphabet.index(char) * factor
        total += product // 36 + product % 36
        factor = 3 - factor
    gstin = body + alphabet[(36 - total % 36) % 36]
    return value(
        backend.firm.save(
            replace(
                value(backend.firm.get()),
                name="Demo Firm",
                details=PartyDetails("12 Sample Road, Ahmedabad 380001", gstin, "24"),
                signatory="Example Owner",
                invoice_mode="MANUAL_CONFIRMED",
            )
        )
    )


def saved_draft(backend, firm, day="2026-04-01", template="modern"):
    return value(
        backend.commands.save(
            SaveDraftRequest(
                DraftInput(
                    firm.name,
                    "Example Customer",
                    day,
                    "CGST_SGST",
                    (
                        LineInput(
                            "Design service", "2", "1500", "18", "SERVICES", "998314", "Hours"
                        ),
                    ),
                    firm.details,
                    PartyDetails("7 Sample Lane, Ahmedabad 380002", "", "24"),
                    "24",
                    template_id=template,
                )
            )
        )
    )


def issue(backend, draft, request_id=None):
    return backend.issued.issue(
        IssueRequest(
            draft.id,
            draft.revision,
            request_id or str(uuid4()),
            draft.data.customer_details.address,
        )
    )


def test_anonymous_capabilities_and_one_owner(backend, sample, tmp_path):
    backend.auth.logout()
    calls = [
        lambda: backend.commands.save(SaveDraftRequest(sample)),
        lambda: backend.queries.list(DATES),
        backend.firm.get,
        backend.templates.list,
        backend.customers.list,
        backend.items.list,
        lambda: backend.issued.list(DATES),
        lambda: backend.backups.create(str(tmp_path / "private.invobak"), PASSWORD),
        lambda: backend.previews.preview(sample),
    ]
    for call in calls:
        assert call().error.code == "AUTH_REQUIRED"
    assert backend.auth.setup(OwnerSetup("Replacement", "attacker", PASSWORD)).error
    value(backend.auth.login("TEST-OWNER", PASSWORD))
    assert value(backend.firm.get()).name == "Demo Firm"


def test_password_hash_and_persisted_throttle(backend):
    with sqlite3.connect(backend.directory / "invoices.db") as db:
        row = db.execute("SELECT password_hash, recovery_hash FROM workspace_owner").fetchone()
    assert all(x.startswith("$argon2id$") and PASSWORD not in x for x in row)
    backend.auth.logout()
    for _ in range(5):
        assert backend.auth.login("test-owner", "wrong").error
    another = build_backend(backend.directory)
    try:
        assert "five minutes" in another.auth.login("test-owner", PASSWORD).error.message
        assert another.queries.list(DATES).error.code == "AUTH_REQUIRED"
    finally:
        another.close()


def test_password_rotation_invalidates_all_sessions_and_old_recovery(tmp_path):
    app = build_backend(tmp_path / "identity")
    other = None
    try:
        key = value(app.auth.setup(OwnerSetup("Example", "owner", PASSWORD)))
        other = build_backend(app.directory)
        value(other.auth.login("owner", PASSWORD))
        replacement = value(app.auth.change_password(PASSWORD, "replacement-password-5678"))
        assert not value(other.auth.state()).signed_in
        assert app.auth.recover("owner", key.code, PASSWORD).error
        rotated = value(app.auth.recover("owner", replacement.code, PASSWORD))
        assert rotated.code != replacement.code
        value(app.auth.login("owner", PASSWORD))
    finally:
        if other:
            other.close()
        app.close()


def test_idle_lock_does_not_get_extended_by_state_checks(backend):
    now = [1000.0]
    backend.auth._clock = lambda: now[0]
    value(backend.auth.login("test-owner", PASSWORD))
    now[0] += 899
    assert value(backend.auth.state()).signed_in
    now[0] += 2
    assert not value(backend.auth.state()).signed_in
    assert backend.templates.list().error.code == "AUTH_REQUIRED"


def test_master_records_revision_conflicts_and_soft_delete(backend):
    customer = value(backend.customers.save(CustomerRecord("Example", PartyDetails("Address"))))
    changed = value(backend.customers.save(replace(customer, name="Changed")))
    assert backend.customers.save(customer).error.code == "CONFLICT"
    value(backend.customers.delete(changed.id, changed.revision))
    assert not value(backend.customers.list())
    item = value(backend.items.save(ItemRecord("Service", "100.25", "18", "SERVICES", "998314")))
    assert item.unit_price == "100.25"
    assert backend.items.save(replace(item, unit_price="-1")).error


def test_template_versions_and_import_export(backend, sample):
    first = value(backend.templates.save(InvoiceLayout(name="My firm", accent="112233")))
    second = value(backend.templates.save(replace(first.layout, name="Brand two"), first.id, 1))
    assert second.version == 2
    assert backend.templates.save(first.layout, first.id, 1).error.code == "CONFLICT"
    assert backend.templates.save(first.layout, "modern", 1).error
    assert value(backend.templates.preview(second.layout, sample)).startswith(b"%PDF")
    copied = value(
        backend.templates.import_layout(value(backend.templates.export_layout(first.id)))
    )
    assert copied.id != first.id and copied.layout == second.layout


@pytest.mark.parametrize(
    "change",
    [
        {"accent": "not-a-colour"},
        {"accent": None},
        {"columns": None},
        {"columns": (["bad"],)},
        {"section_order": ("items", "items")},
        {"font_size": True},
        {"show_notes": "false"},
        {"logo_png": "not base64"},
    ],
)
def test_untrusted_template_fields_are_validation_errors(backend, change):
    layout = replace(InvoiceLayout(), **change)
    result = backend.templates.save(layout)
    assert result.error and result.error.code == "VALIDATION"
    data = {"format": "invoice-layout-v1", "layout": asdict(layout)}
    result = backend.templates.import_layout(json.dumps(data).encode())
    assert result.error and result.error.code == "VALIDATION"


def test_logo_reencodes_and_rejects_non_images(backend):
    stream = BytesIO()
    Image.new("RGB", (1000, 300), "navy").save(stream, format="PNG")
    encoded = value(backend.templates.normalize_logo(stream.getvalue()))
    with Image.open(BytesIO(base64.b64decode(encoded))) as image:
        assert image.format == "PNG" and image.width <= 800 and image.height <= 250
    assert backend.templates.normalize_logo(b"<svg onload='bad()'/>").error
    assert backend.templates.normalize_logo(b"X" * 2_000_001).error


def test_issuance_gate_and_required_fields(backend, sample):
    draft = value(backend.commands.save(SaveDraftRequest(sample)))
    assert issue(backend, draft).error.field == "invoice_mode"
    firm = ready_firm(backend)
    assert issue(backend, draft).error
    draft = saved_draft(backend, firm)
    value(backend.firm.save(replace(firm, invoice_mode="EINVOICE_REQUIRED")))
    assert issue(backend, draft).error.field == "invoice_mode"


def test_numeric_sequence_resets_by_invoice_financial_year_and_is_immutable(backend):
    firm = ready_firm(backend)
    first_draft = saved_draft(backend, firm, "2026-03-31")
    first = value(issue(backend, first_draft))
    retry = value(issue(backend, first_draft))
    assert first.id == retry.id
    second = value(issue(backend, saved_draft(backend, firm, "2026-04-01")))
    third = value(issue(backend, saved_draft(backend, firm, "2026-04-02")))
    assert (first.financial_year, first.number) == (2025, 1)
    assert (second.financial_year, second.number) == (2026, 1)
    assert third.number == 2
    assert backend.commands.delete(DraftReference(first_draft.id, first_draft.revision)).error
    assert backend.commands.save(
        SaveDraftRequest(
            first_draft.data,
            first_draft.id,
            first_draft.revision,
        )
    ).error
    assert not value(backend.queries.list(DATES))
    assert len(value(backend.issued.list(DATES))) == 3


def test_parallel_issuance_allocates_unique_numbers_and_retry_is_idempotent(backend):
    firm = ready_firm(backend)
    drafts = [saved_draft(backend, firm) for _ in range(5)]
    with ThreadPoolExecutor(max_workers=5) as pool:
        invoices = [value(x) for x in pool.map(lambda d: issue(backend, d), drafts)]
    assert sorted(x.number for x in invoices) == [1, 2, 3, 4, 5]
    extra = saved_draft(backend, firm)
    request_id = str(uuid4())
    with ThreadPoolExecutor(max_workers=3) as pool:
        retries = [
            value(x) for x in pool.map(lambda _: issue(backend, extra, request_id), range(3))
        ]
    assert len({x.id for x in retries}) == 1 and retries[0].number == 6


def test_captured_template_cancelled_register_and_export_retry(backend):
    firm = ready_firm(backend)
    custom = value(backend.templates.save(InvoiceLayout(name="Captured", accent="123456")))
    invoice = value(issue(backend, saved_draft(backend, firm, template=custom.id)))
    value(backend.templates.save(replace(custom.layout, accent="654321"), custom.id, 1))
    assert value(backend.issued.get(invoice.id)).model.layout.accent == "123456"
    assert backend.firm.save(replace(firm, details=replace(firm.details, gstin=""))).error
    assert value(backend.issued.preview(invoice.id)).startswith(b"%PDF")
    pdf = value(backend.issued.export(invoice.id))
    assert (backend.directory / "exports" / pdf.display_name).is_file()
    value(backend.issued.export(invoice.id, "docx"))
    cancelled = value(backend.issued.cancel(invoice.id, "Created in error"))
    assert cancelled.status == "CANCELLED" and cancelled.number == invoice.number
    bundle = value(backend.issued.export_range(DateRange("2026-04-01", "2026-04-01")))
    with ZipFile(backend.directory / "exports" / bundle.display_name) as archive:
        rows = list(csv.reader(StringIO(archive.read("invoices.csv").decode("utf-8-sig"))))
        assert len(rows) == 2 and len(rows[0]) == len(rows[1])
        assert rows[1][0] == "CANCELLED"
        manifest = json.loads(archive.read("manifest.json"))
        assert manifest["invoices"][0]["number"] == 1
        assert b"CANCELLED" in archive.read("README.txt")
    assert value(issue(backend, saved_draft(backend, firm))).number == 2


def test_failed_revision_does_not_consume_number(backend):
    firm = ready_firm(backend)
    draft = saved_draft(backend, firm)
    updated = value(backend.commands.save(SaveDraftRequest(draft.data, draft.id, draft.revision)))
    assert issue(backend, draft).error
    assert value(issue(backend, updated)).number == 1


def test_encrypted_backup_roundtrip_and_tampering(backend, tmp_path):
    firm = ready_firm(backend)
    invoice = value(issue(backend, saved_draft(backend, firm)))
    value(backend.issued.export(invoice.id))
    target = tmp_path / "safe.invobak"
    value(backend.backups.create(str(target), PASSWORD))
    raw = target.read_bytes()
    assert b"SQLite format" not in raw and b"Example Customer" not in raw
    assert backend.backups.create(str(target), PASSWORD).error
    restored = tmp_path / "restored"
    assert backend.backups.restore_copy(str(target), "wrong-password-123", str(restored)).error
    assert not restored.exists()
    value(backend.backups.restore_copy(str(target), PASSWORD, str(restored)))
    copy = build_backend(restored)
    try:
        assert copy.issued.list(DATES).error.code == "AUTH_REQUIRED"
        value(copy.auth.login("test-owner", PASSWORD))
        assert value(copy.issued.get(invoice.id)) == invoice
        assert value(issue(copy, saved_draft(copy, firm))).number == 2
    finally:
        copy.close()
    assert len(value(backend.issued.list(DATES))) == 1
    assert backend.backups.restore_copy(str(target), PASSWORD, str(restored)).error
    target.write_bytes(raw[:-1] + bytes([raw[-1] ^ 1]))
    assert backend.backups.restore_copy(str(target), PASSWORD, str(tmp_path / "tampered")).error


@pytest.mark.parametrize(
    "change",
    [
        {"tax_mode": "IGST"},
        {"place_of_supply": "27"},
        {"invoice_date": "2099-01-01"},
        {"customer_details": PartyDetails("", "", "24")},
        {"customer_details": PartyDetails("Address", "24AAAAA0000A1Z1", "24")},
        {"lines": (LineInput("Goods", "1", "100", "0", "GOODS", "4820"),)},
        {"lines": (LineInput("Service", "1", "100", "18", "SERVICES", "123456"),)},
    ],
)
def test_issuance_rejects_invalid_tax_and_required_data(backend, change):
    firm = ready_firm(backend)
    draft = saved_draft(backend, firm)
    changed = value(
        backend.commands.save(
            SaveDraftRequest(
                replace(draft.data, **change),
                draft.id,
                draft.revision,
            )
        )
    )
    assert issue(backend, changed).error
    assert not value(backend.issued.list(DATES))


def test_failed_pdf_can_retry_without_number_or_snapshot_change(backend, monkeypatch):
    from invoice_generator.infrastructure.documents.pdf import ReportLabDraftRenderer

    firm = ready_firm(backend)
    invoice = value(issue(backend, saved_draft(backend, firm)))
    renderer = ReportLabDraftRenderer.render

    def fail(*args):
        raise OSError("Simulated full disk")

    monkeypatch.setattr(ReportLabDraftRenderer, "render", fail)
    assert backend.issued.export(invoice.id).error.code == "STORAGE_FAILURE"
    assert value(backend.issued.get(invoice.id)) == invoice
    monkeypatch.setattr(ReportLabDraftRenderer, "render", renderer)
    value(backend.issued.export(invoice.id))
    assert value(backend.issued.get(invoice.id)).number == 1
