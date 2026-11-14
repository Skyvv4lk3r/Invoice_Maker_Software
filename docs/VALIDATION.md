# Validation performed on 14 November 2026

The expanded draft workspace was checked locally on Linux with Python 3.12.14.
These results describe a draft application, not a production accounting release.

| Check | Observed result |
| --- | --- |
| Domain, integration and architecture tests | 39 passed |
| Qt desktop workflow tests | 5 passed using Qt's offscreen platform |
| Import-linter contracts | 5 kept, 0 broken |
| Ruff lint and formatting | Passed |
| Python wheel/source distribution | Built successfully using isolated build dependencies |
| Desktop visual review | List, editor, collapsible details, persistent total and actual PDF preview reviewed |
| Draft PDF visual review | A4, embedded Latin fonts, parties, item amounts, tax summary and DRAFT labels reviewed |
| Word visual review | Fictional sample rendered through LibreOffice and inspected; no clipped tables or text |
| Multipage PDF case | 80 items including XML-sensitive text exported successfully |
| Backward compatibility | Payloads without the new fields decode without data replacement |
| Git whitespace check | Passed |

New tests exercise extended-field persistence, per-line totals, malformed fields,
old JSON payloads, PDF preview without saving, Word content/revision conflicts,
inclusive package boundaries, deleted-row exclusion, CSV formula escaping,
consistent Word/register totals and revision manifests. Desktop tests cover
automatic totals, PDF preview, Word export, search, save/cancel/discard navigation,
stale-total removal and date-range export unaffected by search text.

The earlier 8 November starter passed its five GitHub Actions jobs. The new branch's
Windows/Linux and Python 3.12/3.13 results are reported by its own Actions run; local
Linux checks do not substitute for those results.

Not validated as production features: GST classification, registered GSTIN status,
GSTIN checksum, issued numbering, financial-year counter reset, immutable issued
invoices, special GST treatments, reusable master profiles, GST return submission,
XLSX exports, published template versions, full Indian-script rendering, encrypted
recovery and Windows installer behavior. Word was inspected through LibreOffice;
Microsoft Word pagination still needs review. ZIP generation currently runs in
memory and has not been benchmarked for large accounting datasets.

Dependencies are bounded compatibility ranges, not a full release lock. A tested
Windows dependency lock and installer remain necessary before distribution.
