# ADR 0001: Local desktop with independent Python backend

Status: accepted project direction.

The initial user needs an offline Windows desktop application, a single firm's
sales invoices, document exports and local records. The user explicitly requires
loose frontend/backend coupling and SOLID responsibilities.

Use PySide6/Qt Widgets and Qt Designer for presentation. Use pure Python domain
rules and application services behind immutable DTOs and small Protocols.
SQLAlchemy/Alembic adapt SQLite persistence; ReportLab adapts draft PDF output.
Bootstrap constructs implementations. Neither the domain nor application imports Qt.

A Django/HTTP server is not required for this deployment. A later browser or
multi-user application may add transport adapters and a centrally managed database.
The current SQLite file must not be shared directly among computers.

Benefits: one language, local operation, replaceable adapters and tests without GUI.
Costs: we own desktop packaging, background work, recovery and document-template
coordination. Using Python everywhere does not itself guarantee loose coupling;
import contracts and behavioural tests are part of the design.
