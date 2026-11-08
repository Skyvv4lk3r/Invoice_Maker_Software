# Contributing

Use Python 3.12 for the initial development environment and follow the README setup.
Create a feature branch, make one coherent change, and update relevant documentation.

Run `python scripts/check.py`. Screen changes also require `pytest tests/gui` with
`QT_QPA_PLATFORM=offscreen`. Domain/application code should remain testable without
installing the desktop extra. Use `python -m build` to verify packaged resources.

Use `python -m ruff format .` to format and `python -m ruff check .` to lint. Financial
and transaction changes require tests for invalid inputs, exact amounts, stale
versions and rollback behaviour. Rendering changes need a representative multipage
PDF review in addition to automated checks.

Use fictional firm/customer data in tests and examples. Describe the concrete
problem, resulting behaviour and checks in pull requests. Never edit an applied
database migration to change existing installations; add a new revision with a
documented backup/recovery plan.
