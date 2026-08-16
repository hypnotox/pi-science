| Dependency | Role |
|---|---|
| Python 3.13 | Application runtime. |
| Pydantic v2 | Strict typed request and result validation. |
| SymPy | Normalized symbolic and LaTeX rendering after validation. |
| uv | Python provisioning, dependency locking, and command execution. |
| pytest | End-to-end application tests. |
| Pyright | Strict static type checking. |
| Ruff | Python linting. |
| awf | Generates and verifies workflow and documentation state. |
| Git | Versions authoritative project state. |

The root `pyproject.toml` declares workspace development dependencies; `packages/py-science-formula/pyproject.toml` declares the package runtime dependencies; `uv.lock` pins the workspace resolution. Frontend safety and the internal expression model do not depend on evaluating submitted text or exposing SymPy as the public protocol.
