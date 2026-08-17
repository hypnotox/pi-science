---
name: pi-science-formula-analysis
description: Analyze one restricted SymPy expression or named equation system for normalized interpretation, symbolic work, reuse, provenance, scenarios, and unresolved costs. Use for formula structure and qualified abstract work, not numeric evaluation, benchmarking, physical validation, or implementation generation.
---

# Formula analysis

Use the `analyze_formula` Pi tool for one bounded restricted-SymPy expression or one nonempty list of uniquely named equations. System requests may include per-equation output domains, variable domains, mathematical function definitions, scalar primitive costs, named assumptions, directed definitions, and scenarios. Pi supplies `syntax: sympy`; LaTeX input is not supported.

Inspect the returned normalized SymPy and LaTeX equations, symbolic total work, dependency reuse, relationship provenance, scenario qualifications, unknown costs, and unresolved items before relying on a conclusion. The tool analyzes submitted formula structure; it does not infer formulas from source, evaluate represented values, validate physics, measure implementation performance, model hardware, or generate code.

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
