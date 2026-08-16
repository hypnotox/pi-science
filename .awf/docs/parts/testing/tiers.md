- **Focused application tests:** `uv run --locked pytest tests/e2e/test_formula_evaluation.py`.
- **Application suite:** `uv run --locked pytest`.
- **Complete gate:** `./scripts/check`.

There is no separate extended tier. Add one only when an executable workload cannot remain in the deterministic complete gate.
