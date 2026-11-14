# Implementation roadmap

## 1. Working foundation — included

- [x] Python package layout, public DTOs and Protocols
- [x] Dependency injection and enforceable package boundaries
- [x] Qt Designer form and asynchronous task bridge
- [x] Decimal draft calculation and INR amount in words
- [x] SQLite draft persistence, Alembic migration, revision checks, audit
- [x] Inclusive date queries and draft PDF export
- [x] Tests, CI definitions and Windows setup instructions

## 1b. Expanded draft workspace — included

- [x] Separate list/editor, search, summary cards and application theme
- [x] Firm/customer detail capture, GSTIN format checks, goods/services and HSN/SAC fields
- [x] Due dates, references, units, notes and payment terms
- [x] Debounced automatic totals, line amounts and stale-result protection
- [x] Unsaved-change guards on navigation and close
- [x] Actual PDF preview and Word draft export with Modern/Classic colour styles
- [x] Inclusive date-range ZIP, invoice/line CSVs and captured-revision manifest
- [x] Old draft payload compatibility and regression coverage

## 2. Complete sales facts and safe issuance

- [ ] Reusable firm/customer/item master profiles (per-draft fields are implemented)
- [ ] Place of supply and explicitly supported GST treatments
- [ ] Agreed discount, rounding and financial-year/closed-period policies
- [ ] Transactional numeric-only counters scoped by firm, FY and document kind
- [ ] Idempotent issue request plus payload hash, immutable financial snapshot
- [ ] Frozen template/branding binding, audit and PDF job in the same transaction
- [ ] Crash/double-click/concurrent-issue/31-March-to-1-April tests
- [ ] Determine e-invoice applicability before enabling production issuance

## 3. Documents and templates

- [ ] Versioned PDF/DOCX template bundles, assets, required-field schema and branding
  (built-in draft renderers and two colour styles are implemented)
- [x] Current draft preview using the real PDF renderer
- [ ] Candidate-template publication preview and approval evidence
- [ ] Validate, visually review, publish, activate and retire template versions
- [ ] Historical template/branding preservation and artifact registry
- [ ] Durable rendering jobs, retries, progress and failure recovery

## 4. Accountant workflow

- [x] Search and all-matching date-range draft selection
- [ ] Paged browsing for large datasets and issued-invoice selection
- [x] Capture one snapshot of all matching draft rows and revisions in a ZIP manifest
- [x] Draft invoice/line CSV registers and ZIP with PDF/Word copies
- [ ] XLSX and GST filing-specific issued-invoice registers
- [ ] Separate cancellation and credit/debit-note registers
- [x] Manual export-folder handoff; no delivery claim

## 5. Operational release

- [ ] Corrections/cancellation policies, payments and adjustment ledger
- [ ] Complete encrypted backups, recovery keys, staged restore and numbering reconciliation
- [ ] Accessibility, larger datasets, Unicode fonts and long/multipage layout QA
- [ ] Windows installer, upgrade backup/migration procedure and dependency licence review
- [ ] Owner-selected project licence and release process

Purchase capture and a shared multi-user server are later extensions. Purchasing
does not inherit the firm's sales-number allocation rules.
