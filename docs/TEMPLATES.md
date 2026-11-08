# Screens and invoice templates

These are separate design surfaces:

| Surface | Current file/tool | Future responsibilities |
| --- | --- | --- |
| Desktop screens | Qt Designer `.ui` form | Navigation, forms, tables, accessibility and themes |
| Draft PDF | ReportLab renderer | A4 layout, fonts, logo, pagination and approved sections |
| Word invoice | Not implemented | docxtpl template with field placeholders and repeated item rows |
| Template catalogue | Not implemented | Versions, validation evidence, publication and retirement |

The draft PDF receives a neutral `DraftPdfModel` with already calculated totals
and amount in words. Template code must never perform financial formulas or change
invoice facts. XML metacharacters in user text are escaped before ReportLab sees
them. The first PDF layout uses built-in Latin fonts; full Indian-script shaping
and embedded fonts are a later template milestone.

The target design freezes a `TemplateVersion`, `BrandingSnapshot` and renderer
version in each issued document's `RenderBinding`. Changing the default template
or logo affects future invoices. Existing documents remain accessible with their
original appearance. The current draft renderer has not yet implemented this
catalogue; it is deliberately a single draft-only adapter.

PDF and Word must match invoice facts. Their pagination is not assumed identical.
Word template publication needs visual review in the intended viewer, because
generating a DOCX file does not prove its page layout. Do not add arbitrary
executable template uploads or hide required fields through appearance settings.
