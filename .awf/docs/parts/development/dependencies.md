Application and development dependencies live in `pyproject.toml`; `uv.lock` is the reproducible resolution. Use `uv add <package>` or `uv add --dev <package>` to change declared dependencies, then stage the manifest and lockfile together.

The runtime uses Pydantic v2 and SymPy. The development group supplies pytest, Pyright, and Ruff. Python 3.13 is pinned in `.python-version`.
