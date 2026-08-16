# py-science-formula

`py-science-formula` safely parses a restricted arithmetic syntax and reports normalized SymPy and LaTeX interpretations plus submitted-operation metrics. It does not evaluate a submitted formula to produce the value represented by that formula.

Use the typed public API from `py_science.formula`:

```python
from py_science.formula import AnalysisRequest, FormulaSyntax, analyze

result = analyze(AnalysisRequest(syntax=FormulaSyntax.SYMPY, expression="x + 1"))
```

The package supports Python 3.13 and is licensed under AGPL-3.0-only.
