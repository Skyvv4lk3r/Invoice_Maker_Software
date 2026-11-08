# Project instructions

This is the invoice generator software project: offline Windows desktop, sales
invoices first, purchase capture later. Preserve the agreed numeric-only invoice
number and financial-year reset requirements when implementing issuance.

## Boundaries

- Presentation imports public application contracts and its own modules only.
- Domain uses the standard library and never imports application/framework code.
- Contracts contain frozen DTOs, plain values and Protocols; no ORM or Qt objects.
- Handlers depend on domain and outbound ports. Adapters implement those ports.
- Only bootstrap wires concrete adapters and the desktop frontend.
- Workers must not manipulate widgets. Each database operation gets its own session.
- Use Decimal from strings and integer paise. Never calculate money with floats.
- Keep templates separate from calculation logic and application styling.
- No full service locator or all-purpose invoice manager.

## Current milestone

Only draft operations and draft PDF generation exist. Do not introduce a button
that implies legal issuance until the issuance transaction, required fields,
financial-year uniqueness and tested GST treatment policy are implemented together.
Never remove draft watermarks to simulate a finished invoice feature.

## Changes and validation

- Run `.venv`'s Python with `scripts/check.py` for backend changes.
- Run `pytest tests/gui` with `QT_QPA_PLATFORM=offscreen` for screen changes.
- Add meaningful regression tests for financial, persistence and lifecycle changes.
- Schema changes use Alembic migrations; never replace real user databases.
- Prefer explicit constructor injection and cohesive interfaces over extra abstractions.
- Keep the README and roadmap honest about implemented versus planned capabilities.
- Use fictional fixtures. Never commit runtime databases, exports or credentials.

Do not change repository visibility, publish releases, or add a licence without
an explicit project-owner decision.
