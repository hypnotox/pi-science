- `packages/py-science-formula/src/py_science/formula/models.py`: strict Pydantic analysis request, result, and error contracts.
- `packages/py-science-formula/src/py_science/formula/expressions.py`: backend-independent typed expression tree.
- `packages/py-science-formula/src/py_science/formula/parser.py`: allowlisted restricted-SymPy parser built on Python expression AST inspection.
- `packages/py-science-formula/src/py_science/formula/analyzer.py`: submitted-operation counting and abstract-work aggregation.
- `packages/py-science-formula/src/py_science/formula/sympy_backend.py`: validated-tree translation and normalized rendering.
- `packages/py-science-formula/src/py_science/formula/service.py`: public analysis orchestration.
- `tests/e2e/`: public-interface behavior and safety evidence.
- `scripts/check`: application and awf project gate.
- `.awf/` and `docs/`: authored workflow configuration and rendered project documentation.

LaTeX parsing, richer SymPy constructs, symbolic aggregation, scenarios, dependencies, comparisons, rewrites, formula-to-code, and an agent skill remain planned components. See [Roadmap](roadmap.md).
