# Architecture

The application is one desktop process with independently testable Python packages.
The frontend is not permitted to import business objects, repositories or document
libraries. It passes immutable request DTOs to small application Protocols.

| Package | Owns | Depends on |
| --- | --- | --- |
| `presentation` | Views, form values, display formatting, Qt worker adapter | `application.contracts`, Qt, standard library |
| `application.contracts` | Requests, results, error values, public interfaces | Standard library |
| `application.handlers` | Validation orchestration, transactions, document mapping | Contracts, ports, domain |
| `application.ports` | Persistence, render and artifact capabilities | Contracts and domain values |
| `domain` | Decimal calculations, Indian words, fiscal-year keys | Standard library |
| `infrastructure` | SQLAlchemy repositories, Alembic, PDF renderer, files | Domain, application ports/contracts, libraries |
| `bootstrap` | Object construction and dependency injection | Concrete implementations |

## Current request path

The view captures form values into a DTO. `QtTaskBridge` schedules a callable on a
worker. The injected use case validates/calculates and uses its persistence ports.
A queued Qt signal delivers a plain result back to the GUI thread. The form is
disabled during operations, so a user cannot edit the submitted form while a save
is pending. No worker receives a QWidget or database session from the screen.

Saving begins a unit-of-work scope. Repository writes use a revision predicate;
stale writes return CONFLICT. Saving and appending an audit event commit together.
Failure or abandonment rolls back. A new Session is created for each scope.
Deletion is a tombstone; original draft rows and audit events remain stored.

Draft export captures one immutable revision, closes its database scope, maps the
values to a neutral PDF model, and invokes a renderer. Rendering does not calculate
tax or mutate an invoice. A unique temporary file is flushed then atomically
renamed. PDF failures do not undo or duplicate a saved draft. Draft exports are
temporary review artifacts; this initial implementation has no issued-artifact
registry or retry queue.

## SOLID in the implementation

| Principle | Concrete decision |
| --- | --- |
| Single responsibility | Calculations, use cases, repositories, renderers and views are separate. |
| Open/closed | Replace an adapter through constructor injection; bootstrap selects implementations. |
| Liskov substitution | Adapter contract tests must preserve amounts, transaction outcomes and declared errors. |
| Interface segregation | Separate commands, queries, draft PDF export, file actions, repositories and audit. |
| Dependency inversion | Handlers depend on Protocols; adapters depend on application-owned contracts. |

The configured import-linter checks catch forbidden imports. Backend tests run in
CI without the desktop extra; a subprocess test also verifies that executing the
backend does not import Qt. Dataclass freezing and typed DTOs keep the boundary
explicit, but Python annotations do not validate every untrusted runtime value.
The current backend is an internal API, not an exposed HTTP endpoint.

## Planned target architecture

The full UML design includes issuance snapshots, versioned template bundles,
branding snapshots, immutable render bindings, idempotent jobs and complete backups.
They are not implemented by this starter. In particular:

- `IDraftPdfCommands` is a milestone-specific interface, not an implementation of
  the target issued-document job interface.
- The current schema only stores draft and audit rows. Number sequences, issued
  snapshots, template versions, export manifests and payments require later migrations.
- Financial-year derivation is implemented as a pure helper. Counter allocation
  and reset are still future transactional behaviour, not a scheduled clock reset.
- SQLite is local to one workstation. Sharing a live database via a network/cloud
  folder is not a planned multi-user architecture.
- An HTTP adapter can be added later without placing web framework imports in domain.

These differences keep the first deliverable executable without claiming that
every box in the target UML has already been built.
