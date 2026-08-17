# pi-science

`pi-science` is an AGPL-3.0-only formula-analysis package for [Pi](https://github.com/badlogic/pi-mono). It pairs the Pi bridge with the independently importable Python 3.13 distribution `py-science-formula`. Formula analysis reports normalized interpretations and abstract operation metrics; it does not evaluate represented values, benchmark an implementation, or generate code. Formula-to-code is an open, out-of-scope roadmap direction.

## Install one compatible source snapshot

Choose one release ref for both independently owned dependencies. A full 40-character commit SHA is immutable; a readable tag is useful for release communication but must resolve to the intended SHA. Python lock resolution records the resolved immutable commit.

In a project-local `.pi/settings.json`, pin Pi:

```json
{"packages":["https://github.com/hypnotox/pi-science.git@<release-ref>"]}
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

## Formulate an analysis

Use one expression for an isolated calculation. Use named equations when results have separate output domains or downstream formulas reuse them. Express vector and tensor components through indexed scalar algebra, declare every free output index and external variable domain, and attach only explicit mathematical knowledge:

- a function body when the mathematical definition is known;
- scalar primitive work when the body is opaque but its work is known;
- assumptions and directed definitions for relationships the analyzer may use;
- scenarios for fixed values, choices, bounds, derived values, or selected asymptotic variables.

The installed `pi-science-formula-analysis` skill contains a compact `analyze_formula` system request. The [`py-science-formula` package guide](packages/py-science-formula/README.md) contains the matching direct-Python pattern. In either interface, inspect normalized SymPy and LaTeX, dependency reuse, provenance, qualifications, unknown costs, and unresolved items before relying on the work report.

Only formulas and directly attached mathematical schema are inputs. Analysis does not infer from source code, validate physics, profile implementations, predict runtime or hardware behavior, or generate code. LaTeX is an output representation, not an input syntax.

## Verification and releases

`./scripts/check` is the fast development gate. `./scripts/check-release` builds a temporary clean Git snapshot from the current working tree and drives Pi's real Git-package startup plus both Python dependency forms without publishing. Before a real release, run it after render settlement, tag and push the immutable commit, then verify the public tag and its intended commit:

```bash
./scripts/check-release --public-ref v0.2.0 --expected-sha <full-40-character-sha>
```
