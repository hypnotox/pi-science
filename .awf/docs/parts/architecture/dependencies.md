| Dependency | Role |
|---|---|
| Python 3.13 | Formula analysis runtime. |
| uv | Isolated Pi backend provisioning and workspace commands. |
| Pydantic v2 / SymPy | Formula contracts and bounded algebra, rendering, and verification. |
| Pi host API | Aggregate tool and diagnostic-command host (peer dependency). |
| TypeScript / Vitest / ESLint / Prettier | Pi bridge checking and tests. |
| awf | Generates and verifies workflow and documentation state. |

The root manifest resolves Pi production and development dependencies; `packages/py-science-formula/pyproject.toml` retains formula runtime dependencies.
