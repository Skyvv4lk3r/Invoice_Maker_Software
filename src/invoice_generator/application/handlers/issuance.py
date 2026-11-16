import hashlib
import json
from dataclasses import asdict, replace

from invoice_generator.application.handlers.documents import document_model
from invoice_generator.application.handlers.drafts import _text, parse_date, parse_id, safe_result
from invoice_generator.domain.issuance import STATES, state_code, validate_issuance
from invoice_generator.domain.models import ValidationError, financial_year_start


class IssuanceService:
    def __init__(self, uow_factory, store, firms, templates, pdf, word, bundle, artifacts):
        self._uow, self._store, self._firms, self._templates = uow_factory, store, firms, templates
        self._pdf, self._word, self._bundle, self._artifacts = pdf, word, bundle, artifacts

    def issue(self, request):
        def operation():
            draft_id, request_id = parse_id(request.draft_id), parse_id(request.request_id)
            shipping = _text(request.shipping_address, "shipping_address", 1000)
            existing = self._store.for_draft(draft_id)
            if existing:
                if (
                    existing.model.revision != request.expected_revision
                    or existing.model.shipping_address != shipping
                ):
                    raise ValidationError(
                        "invoice", "This draft is already issued with different details."
                    )
                return existing
            firm = self._firms.get()
            if firm.invoice_mode != "MANUAL_CONFIRMED":
                raise ValidationError(
                    "invoice_mode",
                    (
                        "Review invoice applicability in Firm settings. IRN-required "
                        "invoices cannot be issued by this offline workflow."
                    ),
                )
            with self._uow() as uow:
                draft = uow.drafts.get(draft_id)
            validate_issuance(draft, firm.name, firm.details.gstin, firm.signatory, shipping)
            layout = self._templates.get(draft.template_id).layout
            model = document_model(draft)
            pos = state_code(model.place_of_supply)
            recipient = state_code(model.customer_details.state)
            origin = state_code(model.firm_details.state)
            model = replace(
                model,
                layout=layout,
                signatory=firm.signatory,
                shipping_address=shipping,
                place_of_supply=pos + " " + STATES[pos],
                firm_details=replace(model.firm_details, state=origin + " " + STATES[origin]),
                customer_details=replace(
                    model.customer_details, state=recipient + " " + STATES[recipient]
                ),
            )
            fingerprint = hashlib.sha256(
                json.dumps(asdict(request), sort_keys=True).encode()
            ).hexdigest()
            return self._store.issue(
                draft_id,
                request.expected_revision,
                request_id,
                fingerprint,
                financial_year_start(draft.invoice_date),
                model,
                firm.revision,
            )

        return safe_result(operation)

    def get(self, invoice_id):
        return safe_result(lambda: self._store.get(parse_id(invoice_id)))

    def preview(self, invoice_id):
        return safe_result(lambda: self._pdf.render(self._store.get(parse_id(invoice_id)).model))

    def list(self, dates):
        def operation():
            self._dates(dates)
            return self._store.list(dates.start, dates.end)

        return safe_result(operation)

    @staticmethod
    def _dates(dates):
        if parse_date(dates.start, "start") > parse_date(dates.end, "end"):
            raise ValidationError("date_range", "Start date must not be after end date.")

    def export(self, invoice_id, format="pdf"):
        def operation():
            if format not in ("pdf", "docx"):
                raise ValidationError("format", "Choose PDF or Word.")
            invoice = self._store.get(parse_id(invoice_id))
            renderer = self._pdf if format == "pdf" else self._word
            artifact = self._artifacts.publish(renderer.render(invoice.model), format)
            if format == "pdf":
                self._store.rendered(invoice.id, artifact, invoice.status)
            return artifact

        return safe_result(operation)

    def cancel(self, invoice_id, reason):
        def operation():
            text = _text(reason, "reason", 500)
            if len(text) < 5:
                raise ValidationError(
                    "reason", "Provide a cancellation reason of at least five characters."
                )
            return self._store.cancel(parse_id(invoice_id), text)

        return safe_result(operation)

    def export_range(self, dates):
        def operation():
            self._dates(dates)
            invoices = self._store.list(dates.start, dates.end)
            if not invoices:
                raise ValidationError("date_range", "No issued invoices in this date range.")
            models = tuple(row.model for row in invoices)
            return self._artifacts.publish(self._bundle.render(models, dates), "zip")

        return safe_result(operation)
