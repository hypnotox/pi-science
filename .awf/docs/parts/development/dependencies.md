The root `pyproject.toml` defines the uv workspace and development dependencies; `packages/py-science-formula/pyproject.toml` defines the independently buildable formula-analysis distribution and its runtime dependencies. `uv.lock` is the reproducible workspace resolution. Use `uv add` or `uv add --dev` at the applicable workspace member, then stage its manifest and the lockfile together.

The formula runtime uses Pydantic v2 and SymPy. The root development group supplies pytest, Pyright, and Ruff. Python 3.13 is pinned in `.python-version`.
