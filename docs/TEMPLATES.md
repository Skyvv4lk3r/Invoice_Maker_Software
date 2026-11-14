# Screens and invoice documents

These are separate design surfaces:

| Surface | Current implementation | Remaining work |
| --- | --- | --- |
| Desktop screens | Qt Designer form and a packaged QSS application theme | Accessibility and larger-data usability testing |
| Draft PDF | ReportLab, A4, embedded bundled Latin fonts, repeated table headers | Indian-script fonts/shaping, logo and production sections |
| Word draft | python-docx, A4, editable fields and repeated table header | Published docxtpl bundles and Microsoft Word layout QA |
| Document styles | Modern/Classic palettes saved with each draft | User-designed, versioned and validated templates |
| Preview | Actual PDF bytes shown through Qt PDF, without saving | Candidate-template publication previews |
| Template catalogue | Not implemented | Versions, assets, branding snapshots, publication and retirement |

The renderers receive a neutral `DraftPdfModel` shared by both document formats,
with already calculated amounts. They do not perform financial formulas or change
invoice facts. ReportLab text is escaped. PDF fonts are embedded from ReportLab's
bundled Vera font files; this is not full Indian-script support.

Modern and Classic are built-in colour variants of the same draft layout. They do
not represent the versioned template catalogue in the target UML. Future issued
documents must freeze template, branding and renderer versions so later changes do
not silently alter historical documents.

PDF and Word match invoice facts; their pagination need not match. Word copies are
editable, and later manual edits do not change the database. A fictional sample was
rendered through LibreOffice for visual review; exact Microsoft Word pagination
still needs validation. Both formats retain explicit DRAFT labels.
