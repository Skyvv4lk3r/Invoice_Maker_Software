# Validation for version 0.3

Local validation: **68 backend/domain/architecture tests and 9 GUI tests passed**;
lint, formatting and all five dependency contracts passed. Checks ran with Python
3.12, Linux and Qt's offscreen platform. The repository's
GitHub workflow separately covers Windows/Linux Python 3.12/3.13 and Windows Qt.

The regression suite covers existing calculations, draft CRUD, revisions, exports,
legacy draft decoding and dependency boundaries, plus:

- anonymous capability rejection, single-owner setup, Argon2 hashes, persisted throttling;
- password/recovery rotation, cross-session invalidation and idle expiration;
- catalogue revisions/deletion and template versions, malformed import fields and logos;
- issuance applicability, required data/tax checks, April financial-year reset;
- immutable issued drafts, concurrent unique numbers and idempotent issue retries;
- stale-revision rollback, frozen layouts, cancellation registers, render failure/retry;
- encrypted backup roundtrip, wrong passwords, tampering and active-data preservation;
- GUI setup/login, automatic firm defaults, unsaved edits through lock/unlock,
  template saving and actual PDF preview.

Run `python scripts/check.py` and `QT_QPA_PLATFORM=offscreen pytest tests/gui`.
Run `python -m build` for the wheel. The Windows CI job builds a PyInstaller portable
folder and smoke-tests the packaged sign-in screen before uploading an artifact.

Visual review used fictional data. Owner setup, sales workspace, firm settings,
layout designer, issued preview, PDF output and LibreOffice-rendered Word output
were inspected. Screenshots are in `docs/screenshots`. Exact Microsoft Word
pagination, a signed Windows installer, assistive-technology support and heavy-data
performance still need validation.

## Scope references

- [CBIC CGST Rule 46](https://taxinformation.cbic.gov.in/content-page/explore-rules/1000136/1000001)
- [GSTN e-invoice overview](https://tutorial.gst.gov.in/downloads/news/e_invoice_overview.pdf)
- [OWASP password storage](https://cheatsheetseries.owasp.org/cheatsheets/Password_Storage_Cheat_Sheet.html)

These informed the supported workflow and security controls. Passing tests does not
certify tax applicability or legal compliance. The firm/accountant must validate
its own treatment and document requirements before using final issuance.
