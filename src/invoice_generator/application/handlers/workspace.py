import base64
import json
import re
from dataclasses import asdict, replace
from uuid import uuid4

from invoice_generator.application.contracts.dto import LineInput, PartyDetails
from invoice_generator.application.contracts.workspace import InvoiceLayout, TemplateVersion
from invoice_generator.application.handlers.drafts import _line, _party, _text, safe_result
from invoice_generator.domain.models import ValidationError


class FirmService:
    def __init__(self, store, templates):
        self._store, self._templates = store, templates

    def get(self):
        return safe_result(self._store.get)

    def save(self, profile):
        def operation():
            name = _text(profile.name, "name", 200)
            if not name:
                raise ValidationError("name", "Enter the firm name.")
            if profile.invoice_mode not in (
                "REVIEW_REQUIRED",
                "MANUAL_CONFIRMED",
                "EINVOICE_REQUIRED",
            ):
                raise ValidationError("invoice_mode", "Select the firm's invoice applicability.")
            self._templates.get(profile.default_template)
            saved = replace(
                profile,
                name=name,
                details=PartyDetails(**asdict(_party(profile.details, "firm"))),
                bank_details=_text(profile.bank_details, "bank_details", 1000),
                default_terms=_text(profile.default_terms, "default_terms", 2000),
                signatory=_text(profile.signatory, "signatory", 120),
            )
            return self._store.save(saved)

        return safe_result(operation)

    def audit(self):
        return safe_result(self._store.audit)


class TemplateService:
    def __init__(self, store, images, renderer=None):
        self._store, self._images = store, images
        self._renderer = renderer

    def preview(self, layout, data):
        from invoice_generator.application.handlers.documents import document_model
        from invoice_generator.application.handlers.drafts import build_draft

        def operation():
            validated = self._validate(layout)
            draft = build_draft(data, str(uuid4()), 0)
            return self._renderer.render(replace(document_model(draft), layout=validated))

        return safe_result(operation)

    def _validate(self, layout):
        if not isinstance(layout, InvoiceLayout):
            raise ValidationError("layout", "Choose a valid invoice layout.")
        for key in (
            "name",
            "accent",
            "tint",
            "font_family",
            "header_alignment",
            "party_layout",
            "footer_text",
            "logo_png",
        ):
            if not isinstance(getattr(layout, key), str):
                raise ValidationError(key, "This layout field must be text.")
        for key in ("columns", "section_order"):
            value = getattr(layout, key)
            if not isinstance(value, (tuple, list)) or not all(isinstance(x, str) for x in value):
                raise ValidationError(key, "Use an ordered list of field names.")
        for key in ("show_notes", "show_terms", "show_signature"):
            if type(getattr(layout, key)) is not bool:
                raise ValidationError(key, "This layout option must be true or false.")
        if len(layout.logo_png) > 3_000_000:
            raise ValidationError("logo", "The logo is too large.")
        name = _text(layout.name, "template.name", 100)
        if not name:
            raise ValidationError("template.name", "Give this template a name.")
        for key in ("accent", "tint"):
            if not re.fullmatch(r"[0-9a-fA-F]{6}", getattr(layout, key)):
                raise ValidationError(key, "Use a six-digit hex colour, for example 183C39.")
        if (
            layout.font_family not in ("sans", "serif", "mono")
            or layout.header_alignment not in ("left", "center", "right")
            or layout.party_layout not in ("columns", "stacked")
        ):
            raise ValidationError("layout", "Unsupported font, alignment or party arrangement.")
        for key, low, high in (("font_size", 8, 12), ("margin_mm", 10, 25), ("row_spacing", 4, 12)):
            value = getattr(layout, key)
            if type(value) is not int or not low <= value <= high:
                raise ValidationError(key, f"Choose a number from {low} to {high}.")
        required = {"description", "quantity", "unit_price", "gst_rate", "taxable", "total"}
        if set(layout.columns) != required or len(layout.columns) != len(required):
            raise ValidationError(
                "columns", "Keep every required invoice column exactly once; you may reorder them."
            )
        sections = {"parties", "metadata", "items", "totals", "notes", "terms"}
        if set(layout.section_order) != sections or len(layout.section_order) != len(sections):
            raise ValidationError(
                "sections", "Keep every section once; notes and terms can be hidden separately."
            )
        if layout.section_order.index("totals") < layout.section_order.index("items"):
            raise ValidationError("sections", "Place totals after the invoice items.")
        logo = ""
        if layout.logo_png:
            try:
                data = base64.b64decode(layout.logo_png, validate=True)
            except (ValueError, TypeError) as error:
                raise ValidationError("logo", "The logo data is invalid.") from error
            logo = self._images.normalize(data)
        return replace(
            layout,
            name=name,
            accent=layout.accent.upper(),
            tint=layout.tint.upper(),
            footer_text=_text(layout.footer_text, "footer", 180),
            logo_png=logo,
        )

    def list(self):
        return safe_result(self._store.list)

    def save(self, layout, template_id="", expected_version=0):
        def operation():
            validated = self._validate(layout)
            if template_id in ("modern", "classic"):
                raise ValidationError("template", "Save a copy of the built-in template.")
            return self._store.save(
                TemplateVersion(template_id or str(uuid4()), 0, validated), expected_version
            )

        return safe_result(operation)

    def normalize_logo(self, content):
        return safe_result(lambda: self._images.normalize(content))

    def import_layout(self, content):
        def operation():
            if len(content) > 3_000_000:
                raise ValidationError("template", "The layout file is too large.")
            try:
                data = json.loads(content)
                if data.get("format") != "invoice-layout-v1":
                    raise ValueError
                values = data["layout"]
                for key in ("columns", "section_order"):
                    values[key] = tuple(values[key])
                layout = InvoiceLayout(**values)
            except (ValueError, TypeError, KeyError, AttributeError) as error:
                raise ValidationError(
                    "template", "Choose a valid invoice-layout JSON file."
                ) from error
            return self._store.save(TemplateVersion(str(uuid4()), 0, self._validate(layout)), 0)

        return safe_result(operation)

    def export_layout(self, template_id):
        return safe_result(
            lambda: json.dumps(
                {
                    "format": "invoice-layout-v1",
                    "layout": asdict(self._store.get(template_id).layout),
                },
                indent=2,
            ).encode()
        )


class CustomerService:
    def __init__(self, store):
        self._store = store

    def list(self):
        return safe_result(self._store.list)

    def save(self, record):
        def operation():
            name = _text(record.name, "customer.name", 200)
            if not name:
                raise ValidationError("customer.name", "Enter a customer name.")
            return self._store.save(
                replace(
                    record,
                    name=name,
                    details=PartyDetails(**asdict(_party(record.details, "customer"))),
                )
            )

        return safe_result(operation)

    def delete(self, record_id, revision):
        def operation():
            self._store.delete(record_id, revision)
            return True

        return safe_result(operation)


class ItemService:
    def __init__(self, store):
        self._store = store

    def list(self):
        return safe_result(self._store.list)

    def save(self, record):
        def operation():
            line = _line(
                LineInput(
                    record.description,
                    "1",
                    record.unit_price,
                    record.gst_rate,
                    record.item_type,
                    record.hsn_sac,
                    record.unit,
                ),
                1,
            )
            from invoice_generator.domain.calculation import calculate
            from invoice_generator.domain.models import TaxMode

            calculate((line,), TaxMode.IGST)
            return self._store.save(
                replace(
                    record,
                    description=line.description,
                    unit_price=str(line.unit_price),
                    gst_rate=str(line.gst_rate),
                    hsn_sac=line.hsn_sac,
                    unit=line.unit,
                )
            )

        return safe_result(operation)

    def delete(self, record_id, revision):
        def operation():
            self._store.delete(record_id, revision)
            return True

        return safe_result(operation)
