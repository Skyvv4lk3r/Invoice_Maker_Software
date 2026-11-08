# Requirements and implementation status

| Requirement | Current status |
| --- | --- |
| Windows desktop and offline use | Source-run PySide6 application implemented; installer pending |
| Sales invoices for goods and services | Draft item descriptions implemented; formal item type/HSN/SAC pending |
| Automatic total and amount in words | Implemented on Calculate, Save and Save + PDF |
| GST calculation | Arithmetic for manually selected split/rates only; production treatment validation pending |
| Create, store, view and update | Implemented for drafts |
| Delete with traceability | Soft deletion and audit events for drafts implemented |
| Numeric-only invoice numbers | Issuance pending; drafts receive UUIDs only |
| Reset invoice sequence each financial year | FY helper implemented; atomic counter allocation pending |
| Inclusive start/end date range | Implemented for draft listing |
| PDF export | Draft-only A4 layout implemented |
| Word export | Planned with docxtpl/python-docx |
| Whole-range accountant package | Planned: immutable selection, Excel/CSV registers, ZIP, PDFs/DOCX |
| Sharing | Generated draft PDFs can be revealed for manual attachment; no automatic sending |
| Template configuration and version history | Planned; Qt screen design and invoice design remain separate |
| Firm/customer/item masters | Planned; names currently entered directly into each draft |
| Issued invoice corrections/cancellation | Planned with policies, audit and immutable originals |
| Payment tracking | Planned |
| Encrypted complete backup/restore | Planned |
| Purchase invoices | Future separate module; retain supplier-issued number |

Quality priorities: exact monetary arithmetic, explicit errors, optimistic
concurrency, short transactions, responsive background work, package independence,
document readability and recoverability. No claim of complete GST compliance is
made for this draft-only development milestone.
