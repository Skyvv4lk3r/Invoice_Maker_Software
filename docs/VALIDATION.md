# Validation performed on 8 November 2026

The delivered source was checked in a Linux development environment with Python
3.12.14. These results describe this starter, not a production accounting release.

| Check | Observed result |
| --- | --- |
| Domain, integration and architecture tests | 29 passed |
| Qt desktop save-and-PDF workflow | 1 passed using Qt's offscreen platform |
| Import-linter contracts | 5 kept, 0 broken |
| Ruff lint and formatting | Passed |
| Python wheel build | Passed; Qt `.ui` form and Alembic migration included |
| Desktop visual review | Saved draft, totals, date-filtered list and export action visible |
| Draft PDF visual review | A4 layout, calculated amounts and DRAFT labels readable |
| Multipage PDF case | Export of 80 items with XML-sensitive text completed |
| Git whitespace check | Passed |

Representative scenarios cover half-paise component rounding, Indian amount words,
invalid/non-finite decimal input, fiscal-year boundary derivation, reopening data
through a second backend, conflicting revisions, rollback, tombstones, audit count,
inclusive date ranges, stale PDF requests, storage failure and backend execution
without importing Qt.

Windows and Python 3.13 checks are configured in `.github/workflows/ci.yml` but have
not been run on GitHub before publication. Windows installer behaviour, complete
GST compliance, issued numbering, Word templates, bulk export and encrypted
recovery are not implemented or validated in this milestone.

The dependency bounds in `pyproject.toml` are compatibility ranges, not a full
reproducible lock. Once Windows CI passes, select and maintain a tested release
lock for distribution. The local run used SQLAlchemy 2.1.8, Alembic 1.20.1,
ReportLab 5.1.0 and PySide6 6.12.0.
