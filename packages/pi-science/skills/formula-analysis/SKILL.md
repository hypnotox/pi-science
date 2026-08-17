---
name: pi-science-formula-analysis
description: Analyze one restricted SymPy expression or named equation system for normalized interpretation, symbolic work, reuse, provenance, scenarios, and unresolved costs. Use for formula structure and qualified abstract work, not numeric evaluation, benchmarking, physical validation, or implementation generation.
---

# Formula analysis

Use the `analyze_formula` Pi tool for one bounded restricted-SymPy expression or one nonempty list of uniquely named equations. Choose an expression for an isolated calculation. Choose equations when named results have distinct output domains or downstream formulas reuse them.

Formulate systems as indexed scalar algebra. Represent a vector component as `x[i, d]`, not as an implicit vector object. Give every free output index a local `domains` entry and every external symbol an intrinsic `variables` domain. A bound `Sum` iterator is local to its body. Use a mathematical `functions` body when its formula is known, a scalar `primitive_costs` expression when only its work is known, or neither when its cost must remain unresolved. Add only explicit `assumptions`, directed `definitions`, and scenario treatments; never ask the tool to guess them.

Pi supplies `syntax: sympy`; LaTeX input is not supported. A compact system request is:

```json
{
  "equations": [
    {
      "name": "samples",
      "expression": "Eq(S[i], x[i] - center)",
      "domains": { "i": { "lower": "0", "upper": "N - 1" } }
    },
    {
      "name": "summary",
      "expression": "Eq(T[k], Sum(basis(S[i], k), (i, 0, N - 1)))",
      "domains": { "k": { "lower": "0", "upper": "p - 1" } }
    }
  ],
  "variables": {
    "N": { "domain": "positive_integer" },
    "p": { "domain": "positive_integer" },
    "x": { "domain": "real" },
    "center": { "domain": "real" }
  },
  "primitive_costs": [
    { "name": "basis", "parameters": ["value", "k"], "work": "k + 1" }
  ],
  "scenarios": [
    { "name": "fixed_order", "fixed": { "p": 4 }, "asymptotic": ["N"] }
  ]
}
```

Inspect every normalized SymPy and LaTeX equation before accepting the interpretation. Then inspect submitted and aggregate work, dependency reuse, relationship provenance, scenario qualifications, unknown costs, and unresolved items before relying on a complexity conclusion. Exact general work remains authoritative when a scenario cannot support a stronger result.

The tool accepts formulas and directly attached mathematical schema only. It does not infer formulas from source, evaluate represented values, validate physics, profile an implementation, predict runtime or hardware behavior, or generate code.

For a persistent project dependency, declare the Python package independently of Pi's managed environment. Replace `<release-ref>` with the same compatible full commit SHA (preferred) or readable release tag used for the project Pi package:

```toml
[project]
requires-python = ">=3.13,<3.14"
dependencies = [
  "py-science-formula @ git+https://github.com/hypnotox/pi-science.git@<release-ref>#subdirectory=packages/py-science-formula",
]
```

Compose the public API directly for a complex probe, importing it from `py_science.formula`. The [`py-science-formula` README](../../../py-science-formula/README.md) contains a matching equation-system request.

For a one-off PEP 723 probe, put that dependency in the script metadata and run `uv run probe.py`; do not import from Pi's isolated backend or its managed checkout.
