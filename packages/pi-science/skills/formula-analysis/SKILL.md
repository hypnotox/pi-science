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

## Bounded mathematical queries

Add optional general-context `queries` only when asking one explicit mathematical question. Each query has a unique `name` and one of these strict shapes: `equivalence` has `comparison`; `closed_form` has no extra operand; `properties` has a nonempty unique `checks` list of `sign` or `valid_domain`, `singularities`, or `monotonicity` with `variable`; `limit` has `variable`, an exact finite `point` plus `left`, `right`, or `both` `direction`, or `oo`/`-oo` without direction; `asymptotic` has the same point rule and `order` 1 through 8. An expression query omits `target`; a system query supplies `{ "kind": "equation", "name": "..." }` for one named RHS. Query strings remain restricted SymPy data, and finite scalars use safe JSON integers or exact strings such as `1/2` and `1.20`.

Inspect every answer's `conclusion` (`proved`, `proved_under_assumptions`, `disproved`, `unresolved`, or `inapplicable`), conditions, assumptions used, unsupported relevant assumptions, blockers, and evidence. Read diagnostics with their source path/span and supported alternative. Derived candidates are mathematical information only: they never replace submitted operation counts or work. Infinite mathematics may have a qualified answer but has no finite direct-work count. Scenarios do not run queries, and valid unsupported questions return localized qualified answers rather than an invented result.

For example, this AFMM tail asks for a verified closed form under explicit global assumptions:

```json
{
  "expression": "Sum((k + 1) * q**k, (k, p, oo))",
  "variables": {
    "p": { "domain": "nonnegative_integer" },
    "q": { "domain": "real" }
  },
  "assumptions": [
    { "name": "q_nonnegative", "relationship": "0 <= q" },
    { "name": "tail_ratio", "relationship": "q < 1" }
  ],
  "queries": [{ "name": "afmm_tail", "kind": "closed_form" }]
}
```

The initial families are bounded rational equivalence, geometric-linear finite or convergent infinite closed forms, supported rational properties and limits, and bounded rational or linear-exponential asymptotics. Scenario-context queries, LaTeX input, complex values, dimensions, vector shorthand, differentiation, numerical approximation, and general theorem proving are non-goals.
