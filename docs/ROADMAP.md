# Roadmap

## Implemented in 0.3

Owner setup/sign-in/recovery/locking; firm defaults; customer and item catalogues;
draft editing/calculation/preview; versioned layout designer and logo; PDF/Word and
date-range ZIP exports; restricted domestic taxable issuance with atomic fiscal-year
numbering and immutable facts; cancellation and audit history; encrypted backups
and verified restore copies; Windows portable build configuration.

## Before routine use by the firm

- Accountant review of applicability, HSN/SAC/rates, rounding and document particulars.
- Test representative goods/services and long invoices with the firm's real layout.
- Establish the numbering starting point; current implementation starts at 1 and
  does not import an existing register or opening counter.
- Validate recovery/backup procedures on the target Windows PC.
- Sign/distribute Windows builds and validate actual Microsoft Word rendering.

## Further features

1. Opening balances/number migration and restore reconciliation; avoid issuing from
   an old restored counter or multiple independent copies.
2. Credit/debit notes, payments and overdue tracking, discounts and round-off policy.
3. Appropriate e-invoice/IRN and GST return adapters, additional tax treatments,
   HSN/SAC/rate reference validation and accountant-compatible import formats.
4. Staff roles, multi-computer sync, application-level encrypted live storage.
5. Streaming large exports, durable background retries, scheduled backups and updates.
6. Arbitrary document-template import, renderer/font archival and Indian-script support.
7. Purchase invoice capture using separate use cases and models.

Purchase capture remains outside the first sales-only release. Do not add runtime
network sharing or live SQLite sync as a shortcut to multi-user support.
