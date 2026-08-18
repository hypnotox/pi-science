---
name: pi-science-formula-analysis
description: Analyze one restricted SymPy expression or named equation system for normalized interpretation, symbolic work, reuse, provenance, scenarios, bounded mathematical queries, and unresolved costs. Use for formula structure and qualified abstract work, not numeric evaluation, benchmarking, physical validation, or implementation generation.
---

# Formula analysis

Use `analyze_formula` for one bounded restricted-SymPy expression or one nonempty list of uniquely named equations. Choose `expression` for an isolated calculation. Choose `equations` when results have local output domains or later equations reuse named results. Pi supplies `syntax: sympy`; do not include `syntax` in a tool call.

## Restricted expression dialect

The parser accepts:

- integer and exact decimal literals, ordinary symbols, and signed infinity `oo` or `-oo`;
- arithmetic `+`, `-`, `*`, `/`, and `**`, including signed integers and negative decimal literals;
- indexed scalars such as `x[i]` and `A[i, j]`;
- ordinary named calls with positional arguments, such as `basis(k, x[i])`;
- one-limit inclusive sums spelled exactly `Sum(body, (index, lower, upper))`;
- equations spelled `Eq(lhs, rhs)`, with a scalar or indexed scalar on the left;
- one unchained relationship using `==`, `<`, `<=`, `>`, or `>=` where that request field permits a relationship.

This is a restricted spelling, not unrestricted SymPy or Python. `Product`, `Piecewise`, attributes, keyword or starred call arguments, chained relationships, implicit vector operations, and multiple limits in one `Sum` are rejected. `Max` is reserved for analyzer output and is not a submitted call. Other ordinary names such as `sqrt(x)`, `exp(x)`, or `f(x)` parse as generic calls; parsing alone does not give them evaluator semantics or a known work cost. `Eq` belongs in an equation request, while relationships belong in assumptions and other relationship-bearing fields. Parser acceptance, request-context validity, and support by a bounded query evaluator are separate checks owned by Python.

A minimal expression call is:

```json
{
  "expression": "Sum((x[i] - center)**2, (i, 0, N - 1))",
  "variables": {
    "N": { "domain": "positive_integer" },
    "x": { "domain": "real" },
    "center": { "domain": "real" }
  }
}
```

## Model an equation system

Represent vectors and tensors as indexed scalar algebra, for example `x[i, d]`. Give every free output index a local equation `domains` entry and every external symbol an intrinsic `variables` domain. A `Sum` iterator is local to its body, and its bounds are inclusive. Use a mathematical `functions` body when a call's formula is known, a scalar `primitive_costs` expression when only its work is known, or neither when its cost must remain unresolved. A function cannot have both. Add only explicit named `assumptions`, acyclic directed `definitions`, and scenario treatments; never ask the tool to infer them.

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

Nested finite sums preserve exact direct work with each iterator lexically bound in symbolic operation counts, opaque work, and primitive invocations; a symbolic `Sum` is an exact populated work value, while an unproved cardinality remains explicitly unresolved. This direct-work behavior does not make nested mathematical closed-form queries supported. Scenarios may select fixed exact values, finite choices, finite bounds, directed definitions, or asymptotic variables without changing the general report. Exact scalars use JavaScript-safe JSON integers or strings such as `1/2` and `1.20`.

## Ask bounded mathematical queries

Optional `queries` ask explicit general-context questions. Each has a unique `name`. `equivalence` adds `comparison`; `closed_form` adds no operand; `properties` has a nonempty unique list of `sign`, `valid_domain`, `singularities`, or `monotonicity` checks; `limit` has a variable and point; `asymptotic` also has `order` from 1 through 8. A finite point requires `left`, `right`, or `both`; `oo` and `-oo` forbid direction. Expression queries omit `target`; system queries select one named RHS with `{"kind":"equation","name":"..."}`.

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
  "queries": [{ "name": "tail", "kind": "closed_form" }]
}
```

Accepted query shape does not promise a proved answer. The shipped evaluators are bounded to rational equivalence; geometric-linear finite or convergent infinite closed forms; supported rational sign, valid-domain, singularity, and monotonicity properties; supported rational limits; and bounded rational or linear-exponential asymptotics. Valid questions outside those families return localized `unresolved` or `inapplicable` answers. Scenarios do not run queries, and derived candidates never replace submitted work.

## Correct and interpret results

First inspect every normalized SymPy and LaTeX interpretation. Then inspect submitted and aggregate work, dependency reuse, relationship provenance, scenario qualifications, unknown costs, unresolved items, and query proof qualifications before drawing a conclusion. A scenario specialization does not replace exact general work.

When a request fails, retain the Python-owned message and use any returned field path, source span, or supported alternative to correct it rather than guessing a broader spelling. For query answers, read `conclusion`, conditions, assumptions used, relevant unsupported assumptions, blockers, evidence, and any informational derived candidates. An unresolved query blocker identifies the failed family, exceeded bound, ambiguous axis, or missing supported precondition. Use any measured observation and recovery hint to simplify, reformulate, or select a supported source family. Recovery hints are conservative: they do not certify equivalence or promise wider evaluator support. Treat `proved_under_assumptions`, conservative bounds, `unresolved`, and `inapplicable` as distinct outcomes.

The tool analyzes formulas and directly attached mathematical schema only. It does not accept LaTeX input, infer formulas from source, evaluate represented values numerically, validate physics, profile an implementation, predict runtime or hardware behavior, prove arbitrary theorems, or generate code.

For persistent or one-off direct Python use, depend on `py-science-formula` independently of Pi's isolated backend and import `py_science.formula`. The [`py-science-formula` README](../../../py-science-formula/README.md) contains the matching typed request and PEP 723 guidance.
