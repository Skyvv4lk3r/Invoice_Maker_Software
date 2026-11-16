# Requirements and implementation status

| Requirement | Version 0.3 status |
| --- | --- |
| Offline Windows desktop | PySide6 application, portable Windows build job; signed installer pending |
| Firm authentication | One owner, first-run setup, sign-in, recovery, password change, throttling and idle lock |
| Firm defaults | Persistent legal/address/GST/contact/bank/signatory/terms/template settings |
| Goods and services | Separate item types, HSN/SAC and units; reusable item catalogue |
| Automatic calculations | Decimal totals, component taxes and Indian amount in words |
| GST validation | Narrow ordinary domestic taxable scope; explicit applicability gate; further cases blocked |
| Create, store, view, update, delete | Draft operations with revisions, soft deletion and audit |
| Numeric-only final numbers | Atomic allocation; unique within each April–March financial year |
| Financial-year reset | Separate counter selected by invoice date; display remains simple integer |
| Final invoice lifecycle | Immutable captured facts/layout; cancellation retains number and reason |
| PDF and Word | Both implemented for drafts and issued records; editable Word copies |
| View/share start–end range | Inclusive date filter; ZIP of PDF/Word/CSV/manifest; manual file sharing |
| Custom layout | Logo/colours/fonts/margins/sections/columns, named versions and JSON import/export |
| Existing Word/PDF as template | Pending; current designer uses structured configuration |
| Customer catalogue | Create, search, edit and soft-delete |
| Backup/recovery | Encrypted archive, verified restore copy, workspace-folder selection |
| Staff roles/multiple devices | Pending; single owner and one live workstation |
| Payment tracking/credit notes | Pending |
| GST portal/e-invoice integration | Pending; IRN-required final issuance blocked |
| Purchase invoices | Future separate module; sales-only initial scope retained |

Non-functional priorities: exact arithmetic, short transactions, explicit errors,
concurrent-write protection, background UI work, independently testable layers,
document readability and recoverability. The live database and exports are not
encrypted. Backups have a documented 128 MB limit. No complete GST-compliance
claim is made. Read README for the supported scope and operational limits.
