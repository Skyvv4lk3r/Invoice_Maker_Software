# Implementation roadmap

## 1. Working foundation — included

- [x] Python package layout, public DTOs and Protocols
- [x] Dependency injection and enforceable package boundaries
- [x] Qt Designer form and asynchronous task bridge
- [x] Decimal draft calculation and INR amount in words
- [x] SQLite draft persistence, Alembic migration, revision checks, audit
- [x] Inclusive date queries and draft PDF export
- [x] Tests, CI definitions and Windows setup instructions

## 2. Complete sales facts and safe issuance

- [ ] Firm/customer profiles, addresses, GSTIN, goods/services, HSN/SAC, units
- [ ] Place of supply and explicitly supported GST treatments
- [ ] Agreed discount, rounding and financial-year/closed-period policies
- [ ] Transactional numeric-only counters scoped by firm, FY and document kind
- [ ] Idempotent issue request plus payload hash, immutable financial snapshot
- [ ] Frozen template/branding binding, audit and PDF job in the same transaction
- [ ] Crash/double-click/concurrent-issue/31-March-to-1-April tests
- [ ] Determine e-invoice applicability before enabling production issuance

## 3. Documents and templates

- [ ] Paired PDF and DOCX templates, assets, required-field schema and branding
- [ ] Draft/candidate preview with real document renderers
- [ ] Validate, visually review, publish, activate and retire template versions
- [ ] Historical template/branding preservation and artifact registry
- [ ] Durable rendering jobs, retries, progress and failure recovery

## 4. Accountant workflow

- [ ] Search, paged browsing and all-matching date-range selection
- [ ] Capture a stable export manifest across every result page
- [ ] Excel/CSV invoice/line/GST registers and a complete ZIP package
- [ ] Separate cancellation and credit/debit-note registers
- [ ] Manual file handoff with an honest distinction from delivery confirmation

## 5. Operational release

- [ ] Corrections/cancellation policies, payments and adjustment ledger
- [ ] Complete encrypted backups, recovery keys, staged restore and numbering reconciliation
- [ ] Accessibility, larger datasets, Unicode fonts and long/multipage layout QA
- [ ] Windows installer, upgrade backup/migration procedure and dependency licence review
- [ ] Owner-selected project licence and release process

Purchase capture and a shared multi-user server are later extensions. Purchasing
does not inherit the firm's sales-number allocation rules.
