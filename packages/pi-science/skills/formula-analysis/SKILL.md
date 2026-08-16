---
name: pi-science-formula-analysis
description: Analyze a restricted SymPy arithmetic formula for its normalized interpretation and abstract operation metrics. Use when you need formula structure or abstract work, not a numeric result, benchmark, or generated implementation.
---

# Formula analysis

Use the `analyze_formula` Pi tool for an ordinary, bounded formula-analysis request:

```json
{ "expression": "x * (y + 1)" }
```

Inspect the returned normalized SymPy and LaTeX interpretations before relying on its operation counts or abstract work. The tool analyzes submitted syntax; it does not evaluate the formula's represented value, measure implementation performance, or generate code.

For a persistent project dependency, declare the Python package independently of Pi's managed environment. Replace `<release-ref>` with the same compatible full commit SHA (preferred) or readable release tag used for the project Pi package:

```toml
[project]
requires-python = ">=3.13,<3.14"
dependencies = [
  "py-science-formula @ git+https://github.com/hypnotox/pi-science.git@<release-ref>#subdirectory=packages/py-science-formula",
]
```

Compose the public API directly for a complex probe:

```python
from py_science.formula import AnalysisRequest, FormulaSyntax, analyze

result = analyze(AnalysisRequest(syntax=FormulaSyntax.SYMPY, expression="x * (y + 1)"))
```

For a one-off PEP 723 probe, put that dependency in the script metadata and run `uv run probe.py`; do not import from Pi's isolated backend or its managed checkout.
