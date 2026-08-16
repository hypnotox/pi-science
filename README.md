# pi-science

`pi-science` is an AGPL-3.0-only formula-analysis package for [Pi](https://github.com/badlogic/pi-mono). It pairs the Pi bridge with the independently importable Python 3.13 distribution `py-science-formula`. Formula analysis reports normalized interpretations and abstract operation metrics; it does not evaluate represented values, benchmark an implementation, or generate code. Formula-to-code is an open, out-of-scope roadmap direction.

## Install one compatible source snapshot

Choose one release ref for both independently owned dependencies. A full 40-character commit SHA is immutable; a readable tag is useful for release communication but must resolve to the intended SHA. Python lock resolution records the resolved immutable commit.

In a project-local `.pi/settings.json`, pin Pi:

```json
{"packages":["git+https://github.com/hypnotox/pi-science.git#<release-ref>"]}
```

For a persistent Python project dependency, pin the same ref separately:

```toml
[project]
requires-python = ">=3.13,<3.14"
dependencies = ["py-science-formula @ git+https://github.com/hypnotox/pi-science.git@<release-ref>#subdirectory=packages/py-science-formula"]
```

Compose the public Python API directly, never through Pi's managed environment:

```python
from py_science.formula import AnalysisRequest, FormulaSyntax, analyze
result = analyze(AnalysisRequest(syntax=FormulaSyntax.SYMPY, expression="x * (y + 1)"))
```

For a one-off PEP 723 probe, save this as `probe.py` and run `uv run probe.py`:

```python
# /// script
# requires-python = ">=3.13,<3.14"
# dependencies = ["py-science-formula @ git+https://github.com/hypnotox/pi-science.git@<release-ref>#subdirectory=packages/py-science-formula"]
# ///
from py_science.formula import AnalysisRequest, FormulaSyntax, analyze
print(analyze(AnalysisRequest(syntax=FormulaSyntax.SYMPY, expression="n + 1")))
```

Pi eagerly provisions its isolated backend on first startup. Install `uv`, Git, Python 3.13, and allow network access for an uncached pin. When readiness succeeds, `analyze_formula` and its matching `pi-science-formula-analysis` skill appear together. If prerequisites fail, they are withheld and `/pi-science-doctor` reports the diagnosis; repair it, then reload or restart Pi. Upgrade by changing both declarations to a newly tested compatible ref and refreshing the Python lock.

## Verification and releases

`./scripts/check` is the fast development gate. `./scripts/check-release` builds a temporary clean Git snapshot from the current working tree and checks local source pins without publishing. Before a real release, run it after render settlement, tag and push the immutable commit, then repeat the checks against the public remote tag.
