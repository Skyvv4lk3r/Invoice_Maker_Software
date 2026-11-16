# Invoice layouts

The application theme and invoice documents are separate. Qt QSS changes the
application's screens; an InvoiceLayout changes the PDF and Word output.

In **Invoice designer**, start with Modern or Classic. Choose **Save as new** to
create a named template. Built-ins are immutable. Further changes use **Save new
version** with optimistic version checking. Firm settings select the default.

| Setting | Supported values |
| --- | --- |
| Logo | PNG/JPEG input, up to 2 MB and 4000×4000; re-encoded as PNG, at most 800×250 |
| Colours | Six-digit accent and alternate-row tint |
| Font | Sans serif, serif or monospace |
| Body size / margin | 8–12 pt setting, 10–25 mm margins |
| Header | Left, centre or right alignment |
| Parties | Side by side or stacked |
| Rows | 4–12 spacing setting |
| Columns | Reorder item, quantity/unit, price, GST rate, taxable amount, line total |
| Sections | Reorder parties, details, items, totals, notes and terms; totals follow items |
| Optional display | Notes, payment terms, signature area and footer message |

Required facts cannot be removed. Issued documents always include the signatory
area. The preview renders a real PDF from the current invoice or fictional sample
data. Layout JSON import/export makes designs reusable. It is a declarative file
format, not executable code; arbitrary Word/PDF template import and a free-form
page canvas are not implemented.

Issued invoices capture the full layout/logo; later template updates do not alter
stored facts. Drafts use the newest version. PDF and Word use the same financial
facts, but pagination differs. Font support is currently Latin text; Indian scripts
need appropriate fonts and shaping. Exact Microsoft Word rendering has not been
validated; a sample was rendered and checked using LibreOffice.

PDF sans uses bundled embedded Vera fonts; serif/mono use standard PDF fonts.
Renderer code and font binaries are not archived per invoice. Preserve original
PDF exports when byte-identical historical documents are required.
