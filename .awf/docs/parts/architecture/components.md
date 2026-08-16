- `src/pi_science/models.py`: strict Pydantic request, result, and error contracts.
- `src/pi_science/expressions.py`: backend-independent typed expression tree.
- `src/pi_science/parser.py`: allowlisted restricted-SymPy parser built on Python expression AST inspection.
- `src/pi_science/analyzer.py`: submitted-operation counting and unit-work aggregation.
- `src/pi_science/sympy_backend.py`: validated-tree translation and normalized rendering.
- `src/pi_science/service.py`: public evaluation orchestration.
- `tests/e2e/`: public-interface behavior and safety evidence.
- `scripts/check`: application and awf project gate.
- `.awf/` and `docs/`: authored workflow configuration and rendered project documentation.

LaTeX parsing, richer SymPy constructs, symbolic aggregation, scenarios, dependencies, comparisons, rewrites, and an agent skill remain planned components. See [Roadmap](roadmap.md).
