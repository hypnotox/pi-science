Use these repository commands:

- `./scripts/check`: run the complete application and repository gate.
- `uv run --locked pytest`: run the application test suite.
- `uv run --locked pyright`: run strict static type checking.
- `uv run --locked ruff check packages/py-science-formula/src tests`: run Python linting.
- `./awf render`: regenerate managed workflow and documentation artifacts.
- `./awf check`: verify awf-managed repository authority and drift.
- `./awf version`: report the resolved awf version.
