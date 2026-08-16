# py-science-formula

`py-science-formula` is the independently importable Python 3.13, AGPL-3.0-only formula-analysis distribution from `pi-science`. It safely parses restricted arithmetic syntax and reports normalized SymPy and LaTeX interpretations plus submitted-operation metrics. It does not evaluate a submitted formula, benchmark application performance, or generate code; formula-to-code remains open but out of scope.

Pin a compatible repository ref directly in the Python environment (independently of a Pi package pin):

```toml
dependencies = ["py-science-formula @ git+https://github.com/hypnotox/pi-science.git@<full-commit-sha>#subdirectory=packages/py-science-formula"]
```

Use a full SHA for immutable adoption; a readable release tag is convenient but should be locked to its resolved commit.

```python
from py_science.formula import AnalysisRequest, FormulaSyntax, analyze

result = analyze(AnalysisRequest(syntax=FormulaSyntax.SYMPY, expression="x + 1"))
```

For a one-off PEP 723 probe, put the same Git-subdirectory dependency in script metadata and invoke `uv run probe.py`. Never import from Pi's isolated backend or from `pi_science`.
