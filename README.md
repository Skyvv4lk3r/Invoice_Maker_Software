# Invoice Generator

An offline desktop application for an Indian firm's sales invoices, built with
**PySide6, a separate Python backend, and SQLite**.

**Status: milestone 1 — a working draft workflow.** This repository is a starter
implementation of the agreed architecture, not the completed GST invoice product.
It does not issue legal invoices or allocate invoice numbers yet. Every generated
PDF is marked **DRAFT**. See [the roadmap](docs/ROADMAP.md) for the remaining work.

## What works now

- Open the desktop application and enter multiple draft items.
- Choose an explicit draft tax split and enter rates; calculate with `Decimal`.
- Convert the final rounded amount to Indian-numbering words.
- Save, reload, update and soft-delete drafts in a local SQLite database.
- Reject stale updates using a revision number; record save/delete audit events.
- Find drafts using inclusive start and end dates.
- Generate a paginated draft PDF with escaped user-entered text.
- Run the same backend without importing Qt.
- Check package boundaries automatically with import-linter.

## Windows setup

Install **64-bit Python 3.12** and Git. In PowerShell, clone the repository:

```powershell
git clone https://github.com/Skyvv4lk3r/Invoice_Maker_Software.git
cd Invoice_Maker_Software
```

From the repository directory, create the environment and start the application:

```powershell
py -3.12 -m venv .venv
.\.venv\Scripts\python.exe -m pip install --upgrade pip
.\.venv\Scripts\python.exe -m pip install -e ".[desktop,dev,gui-test]"
.\.venv\Scripts\python.exe -m invoice_generator
```

Activation is optional. Calling the virtual environment's Python directly avoids
PowerShell activation-policy issues. Alternatively run `scripts/setup.ps1`.

For a backend-only demonstration:

```powershell
.\.venv\Scripts\python.exe -m invoice_generator --demo --data-dir .\data\demo
```

This creates fictional sample data and a draft PDF, then prints the PDF location.
Repeated demo runs create separate drafts. The `data` directory is ignored by Git.

## Using the draft workspace

1. Enter firm/customer names and an invoice date.
2. Select a draft tax split and add descriptions, quantities, prices and tax rates.
3. Choose **Calculate** or **Save draft**; saving always recalculates in the backend.
4. Double-click a saved draft to reopen it. Use **Save + draft PDF** to export.
5. Choose **Show generated PDF in folder** to locate the exported document.

Rates and the split are manually supplied draft inputs. This version does not
determine GST applicability, place of supply, exemptions or special treatments.
The draft calculation policy rounds each line's taxable amount and each tax
component to paise using `ROUND_HALF_UP`; totals sum those displayed components.
Production policy and examples must be agreed before issuance is implemented.

## Where the files belong

| Path | Responsibility |
| --- | --- |
| `src/invoice_generator/presentation/` | Qt views, task bridge and presentation state |
| `src/invoice_generator/application/contracts/` | Public immutable DTOs and narrow interfaces |
| `src/invoice_generator/application/handlers/` | Use cases and orchestration |
| `src/invoice_generator/application/ports/` | Storage, rendering and file-operation interfaces |
| `src/invoice_generator/domain/` | Pure calculations and business values |
| `src/invoice_generator/infrastructure/` | SQLAlchemy, Alembic, ReportLab and filesystem adapters |
| `src/invoice_generator/bootstrap.py` | Constructs concrete implementations and injects them |
| `tests/` | Domain, storage, export, architecture and GUI checks |
| `docs/` | Decisions, requirements, template plan and implementation milestones |
| `.github/` | CI workflow, issue/PR templates and dependency-update configuration |
| `scripts/` | Windows setup and portable quality checks |

The editable Qt Designer form is
`src/invoice_generator/presentation/qt/forms/main_window.ui`. Open it with
`.\.venv\Scripts\pyside6-designer.exe`. Runtime loading means there is no generated
UI Python file to edit or regenerate.

## Local data

Normal startup uses the platform's per-user application-data directory. On Windows,
this is normally `%LOCALAPPDATA%\InvoiceGenerator`. It contains `invoices.db` and
an `exports` folder. Pass `--data-dir PATH` or set `INVOICE_GENERATOR_DATA_DIR` to
choose another local directory. Nothing is uploaded by the application.

Do not commit databases, customer records, invoice exports or credentials. SQLite
and draft exports are not encrypted by this starter. Encrypted full backups and
controlled restore are planned. Use fictional data while developing.

## Checks

```powershell
.\.venv\Scripts\python.exe scripts\check.py
```

This runs formatting, linting, dependency-boundary checks and backend tests. To
also test the GUI:

```powershell
$env:QT_QPA_PLATFORM = "offscreen"
.\.venv\Scripts\python.exe -m pytest tests\gui
```

GitHub Actions is configured to test the backend on Windows and Linux with Python
3.12/3.13, plus a Windows GUI job. These remote jobs run after the repository is
pushed; a workflow file alone does not mean a GitHub run has passed.

Build a Python wheel with `python -m build`. A Windows `.exe`/installer is a later
packaging milestone. Source installs currently require Python.

## GitHub development

The repository is [Skyvv4lk3r/Invoice_Maker_Software](https://github.com/Skyvv4lk3r/Invoice_Maker_Software).
Use feature branches and pull requests for subsequent changes. See
[CONTRIBUTING.md](CONTRIBUTING.md) for the checks to run before submitting a change.
Authenticate with your normal GitHub sign-in workflow; never put a token into source files.

## Architecture and scope

Read [architecture](docs/ARCHITECTURE.md), [requirements](docs/REQUIREMENTS.md),
[template design](docs/TEMPLATES.md), [roadmap](docs/ROADMAP.md), and
[contribution instructions](CONTRIBUTING.md). These explain why no Django or web
server is needed and how future adapters can be added without changing the UI.

The included [41-page UML specification](docs/design/UML_System_Design.pdf) and
[offline diagram gallery](docs/design/gallery.html) describe the **target** architecture.
This starter implements its draft slice. Durable issued-document jobs, immutable
issued snapshots, template publication and annual issuance counters are explicitly
future work; this repository does not pretend to implement those contracts yet.

No open-source licence has been selected. Choose a licence before distributing the
project as open source. Third-party dependencies retain their own licence terms.
