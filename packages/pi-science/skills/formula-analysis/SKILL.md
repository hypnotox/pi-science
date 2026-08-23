---
name: pi-science-formula-analysis
description: Analyze or explicitly optimize one restricted SymPy expression or named equation system with bounded verified replayable plans, compare two mapped candidates, or analyze bounded one-axis aggregate-work term dominance, for normalized interpretation, qualified symbolic work, reuse, provenance, bounded mathematical conclusions, and unresolved costs. Use for formula structure and abstract work, not numeric evaluation, benchmarking, physical validation, or implementation generation.
---

# Formula analysis

Use ordinary `analyze_formula` expression or equation-system analysis for bounded verified local optimization advice. Use `analyze_formula` for one bounded restricted-SymPy expression or one nonempty list of uniquely named equations. Choose `expression` for an isolated calculation. Choose `equations` when results have local output domains or later equations reuse named results. Pi supplies `syntax: sympy`; do not include `syntax` in a tool call.

## Request cookbook

Choose one recipe, then add only metadata accepted by that operation. The tool schema is authoritative for mechanical collection, source-size, and numeric bounds; use returned field paths and supported alternatives to repair validation failures.

### Analyze an expression or selected system outputs

Omit `operation` for ordinary analysis. An expression may omit `outputs` or use only `["expression"]`; a system may use a unique list of equation names. Ordinary analysis alone accepts scenarios, queries, and `optimization`.

```json
{
  "expression": "N * p + m + 1 / (1 - q)",
  "outputs": ["expression"],
  "variables": {
    "N": { "domain": "positive_integer" },
    "p": { "domain": "positive_integer" },
    "m": { "domain": "positive_integer" },
    "q": { "domain": "real" }
  },
  "scenarios": [
    {
      "name": "bounded_sweep",
      "choices": { "p": [2, 4, 8] },
      "bounds": {
        "q": {
          "lower": 0,
          "upper": 1,
          "upper_inclusive": false
        }
      },
      "definitions": [{ "variable": "m", "expression": "2 * N" }],
      "asymptotic": ["N"]
    }
  ]
}
```

A scenario variable has exactly one treatment: `fixed`, nonempty unique `choices`, one finite nonempty `bounds` interval, one directed `definitions` target, or `asymptotic`. Interval endpoints are exact scalars and default to inclusive. Choices form a bounded Cartesian expansion; scenarios specialize the general report and do not run queries.

### Compare two mapped candidates

Map every logical output to exactly one target in each candidate. Candidate order matters: `details.work_comparison.delta` is the second candidate minus the first.

```json
{
  "operation": "compare_candidates",
  "variables": { "x": { "domain": "real" } },
  "candidates": [
    { "name": "first", "expression": "x + x" },
    { "name": "second", "expression": "2 * x" }
  ],
  "outputs": [
    {
      "name": "value",
      "targets": [
        { "candidate": "first", "target": { "kind": "expression" } },
        { "candidate": "second", "target": { "kind": "expression" } }
      ]
    }
  ]
}
```

### Analyze one-axis dominance

Declare the numeric axis, fix every required non-axis value exactly, and optionally restrict the active interval. Omitted endpoints are outward-open infinities; explicit `-oo` and `oo` endpoints are also open. Finite endpoint inclusivity defaults to true.

```json
{
  "operation": "analyze_dominance",
  "expression": "N**3 - C * N**2",
  "variables": {
    "N": { "domain": "positive_integer" },
    "C": { "domain": "positive_real" }
  },
  "axis": "N",
  "fixed": { "C": 4 },
  "range": { "lower": 1, "upper": 100 }
}
```

### Request weighted direct optimization

Omit `objective` for unit work. A weighted objective requires all five strictly positive exact-rational weights inside `weights`.

```json
{
  "operation": "optimize",
  "expression": "(x + 1)**2 + (x + 1)**3",
  "variables": { "x": { "domain": "real" } },
  "max_plans": 5,
  "objective": {
    "kind": "weighted_operations_v1",
    "weights": {
      "additions": 1,
      "subtractions": 1,
      "multiplications": 2,
      "divisions": 3,
      "powers": 4
    }
  }
}
```

Use the same objective under `optimization.objective` for ordinary advice. `max_plans` and `max_suggestions` select only the ranked output prefix after the fixed search; they do not deepen the search or raise its budgets.

## Compare two candidates

`analyze_formula` also accepts `{ "operation": "compare_candidates", "candidates": [first, second], "outputs": [...] }`; Pi supplies `syntax`. Map every logical output once to each candidate with an expression target or named equation target. Inspect semantic status and mapped-output blockers before any work preference. `aggregate_abstract_work` is mathematical work, never speed, runtime, storage, or IEEE-754 behavior; unknown costs and unresolved semantics forbid a preference. Scenarios, transformations, resource vectors, parameter search, and AFMM expansion are excluded from comparison requests.

## Analyze aggregate-work term dominance

Use `{ "operation": "analyze_dominance", "expression" | "equations", "axis": "N", ... }` to inspect one retained aggregate-work expression on one declared numeric axis; Pi supplies `syntax`. `fixed` supplies exact values for other declared variables and `range` may restrict the active interval. Terms retain their signs, but relevance compares absolute magnitude: a negative term is not negative work, and a dominant term is not a runtime or global-optimality claim. Read `details` for canonical cells, ties, poles, conditions, and blockers. `complete` cells are proved; unresolved cells are not guesses. Multiple axes, exponentials, opaque `Sum`/`Max`, rewrites, resource vectors, scheduling, and empirical performance are excluded.

## Restricted expression dialect

The parser accepts:

- integer and exact decimal literals, ordinary symbols, and signed infinity `oo` or `-oo`;
- arithmetic `+`, `-`, `*`, `/`, and `**`, including signed integers and negative decimal literals;
- indexed scalars such as `x[i]` and `A[i, j]`;
- ordinary named calls with positional arguments, such as `basis(k, x[i])`;
- bounded nonrecursive lexical bindings spelled exactly `Let(name, value, body)`; the value does not see its own name, the body does, and value work is charged once at lexical placement;
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

Represent vectors and tensors as indexed scalar algebra, for example `x[i, d]`. Give every free output index a local equation `domains` entry and every external symbol an intrinsic `variables` domain. Output bounds may reference other output indices when the inferred dependency graph is acyclic and each dependent bound is an affine integer sum; LHS order remains coordinate order and only breaks topological ties. Reject self/cyclic dependencies and dependent calls, indexed values, symbolic products, powers, division, or aggregate operators; independent bounds retain their established family. A `Sum` iterator is local to its body, and its bounds are inclusive. Use a mathematical `functions` body when a call's formula is known, a scalar `primitive_costs` expression when only its work is known, or neither when its cost must remain unresolved. A function cannot have both. Add only explicit named `assumptions`, acyclic directed `definitions`, and scenario treatments; never ask the tool to infer them.

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

Named equation-local constraints may tighten a required finite base domain with the supported integer-affine or absolute upper-bound family; use `constraints: [{name, target, relationship}]`, inspect submitted constraints, effective domains, and equation-qualified constraint uses, and expect scenario domains to specialize per choice. Constraints govern only their owning equation and targeted queries, never other equations or expression queries. Constraint-only domains, floors or divisibility, chains, disjunctions, disconnected regions, general lattice counting, and nonlinear relationships are outside the supported family.

Nested finite sums and dependent output domains preserve exact direct work with each iterator lexically bound in symbolic operation counts, opaque work, and primitive invocations. Domains aggregate in reverse stable dependency order; bounded affine sums close from intrinsic, submitted, and predecessor-domain facts with relationship provenance. A symbolic `Sum` remains an exact populated fallback, while unproved cardinality, ordering, or finiteness stays explicitly unresolved. This direct-work behavior is distinct from the partial nested mathematical closed-form family described below and does not itself prove a candidate. Scenarios may select fixed exact values, finite choices, finite bounds, directed definitions, or asymptotic variables without changing the general report. Exact scalars use JavaScript-safe JSON integers or strings such as `1/2` and `1.20`.

## Ask bounded mathematical queries

Optional `queries` ask explicit general-context questions. Each has a unique `name`. `equivalence` adds `comparison`; `closed_form` adds no operand; `properties` has a nonempty unique list of `sign`, `valid_domain`, `singularities`, or `monotonicity` checks; `limit` has a variable and point; `asymptotic` also has `order` from 1 through 8. A finite point requires `left`, `right`, or `both`; `oo` and `-oo` forbid direction. Expression queries omit an equation target; system queries select one named RHS with `{"kind":"equation","name":"..."}`. An `equivalence`, `properties`, `limit`, or `asymptotic` query may use `{"kind":"derived","query":"earlier_closed_form"}` in either context. The source is earlier-only and must be a verified single closed-form candidate. Use this explicit two-query route for downstream analysis of a nested finite sum; direct consumers do not silently replace the sum. Python owns this policy; unavailable operands stay correlated as inapplicable with `normalized_target: null` and never fall back to submitted work.

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

Accepted query shape does not promise a proved answer. The shipped evaluators are bounded to rational equivalence; partial direct `closed_form` support for one ordered-or-empty finite-polynomial nested Sum tree (including `Sum(Sum(1, (l, -k, k)), (k, 0, p))`) with at most four nested levels, eight total `Sum` nodes, degree eight in each active binder, and a checked canonical factored candidate; geometric-linear finite or convergent infinite closed forms; supported rational sign, valid-domain, singularity, and monotonicity properties; supported rational limits; and bounded rational or linear-exponential asymptotics. Valid questions outside those families return localized `unresolved` or `inapplicable` answers. Scenarios do not run queries, and derived candidates never replace submitted work.

## Correct and interpret results

The tool text is a compact human-readable projection organized around interpretation, query conclusions, work, and blockers. It is not the report contract: use the complete canonical report in `details` whenever you need provenance, evidence, qualifications, or other structured fields. First inspect every normalized SymPy and LaTeX interpretation. Then inspect submitted and aggregate work, dependency reuse, relationship provenance, scenario qualifications, unknown costs, unresolved items, and query proof qualifications before drawing a conclusion. A scenario specialization does not replace exact general work; its `substituted_work` is specialized evaluation work, not represented mathematical value.

Use this interpretation checklist:

- Ordinary direct work is either `finite` or `not_finite`. A non-finite computation has null aggregate counts, work, and primitive totals plus explicit blockers; a mathematical query may still have a qualified conclusion.
- For comparison, read mapped semantic and interface status before work status. The reuse-aware delta is second minus first; `not_comparable`, `unresolved`, and a proved preference are distinct outcomes.
- For dominance, distinguish the requested range from the effective active domain. Read top-level `dominance_status`, then inspect `cells` and blockers for `complete` or `unresolved`; `empty` means the effective active domain is empty.
- For optimization, distinguish search status from output-projection status. `incomplete` does not prove that no improvement exists, and truncation does not mean search exhaustion.
- In ordinary analysis, a passive optimizer failure preserves the base analysis and appears only as failed advice. Direct `operation: optimize` failure contains no plans.

When a request fails, retain the Python-owned message and use any returned field path, source span, or supported alternative to correct it rather than guessing a broader spelling. For query answers, read `conclusion`, conditions, assumptions used, relevant unsupported assumptions, blockers, evidence, and any informational derived candidates. An unresolved query blocker identifies the failed family, exceeded bound, ambiguous axis, or missing supported precondition. Use any measured observation and recovery hint to simplify, reformulate, or select a supported source family. Recovery hints are conservative: they do not certify equivalence or promise wider evaluator support. Treat `proved_under_assumptions`, conservative bounds, `unresolved`, and `inapplicable` as distinct outcomes.

The tool analyzes formulas and directly attached mathematical schema only. It does not accept LaTeX input, infer formulas from source, evaluate represented values numerically, validate physics, profile an implementation, predict runtime or hardware behavior, prove arbitrary theorems, or generate code.

For persistent or one-off direct Python use, depend on `py-science-formula` independently of Pi's isolated backend and import `py_science.formula`. The [`py-science-formula` README](../../../py-science-formula/README.md) contains the matching typed request and PEP 723 guidance.

## Use bounded optimization

Submit `operation: optimize` for complete replayable plans. Set `max_plans` to a strict integer from `1` through `16`; omission defaults to three. Omit `objective` for `unit_work_v1`, or submit `weighted_operations_v1` with all five strictly positive bounded exact-rational `additions`, `subtractions`, `multiplications`, `divisions`, and `powers` weights; known opaque work keeps coefficient one. Ordinary advice accepts the same selector under `optimization.objective`. To enable the narrow checked nested finite-polynomial `Sum` replacement, submit `enabled_algorithmic_families: ["finite_polynomial_sum_v1"]` at the direct top level or under `optimization`; omission or `[]` preserves default algebraic advice. Each plan contains canonical objective provenance, one complete policy-free candidate, its caller-output identities, the same verified diagnostic suggestion used by ordinary advice, and a stable objective-independent identity. Submit the candidate's expression or equations and mathematical context directly to ordinary analysis or candidate comparison without changing its mathematical content; Pi supplies the restricted-SymPy syntax. Keep plans atomic and do not combine separate candidates. Inspect normalized replay, output identities, conditions, assumptions, work, and `exact_symbolic_only` qualification before using a plan.

A direct `failed` result is a bounded operation failure and contains no unverified plan. `incomplete` means a search or output budget was exhausted, may still contain proved plans, and never means no improvement exists. `complete` with no plans means no candidate qualified within the bounded search. A passive optimizer failure leaves ordinary analysis successful and reports failed advice separately. Ordinary expression and equation-system analysis remains default-on advice over the same plans. Set `optimization.max_suggestions` to a strict integer from `0` through `16`; `0` disables advice.

The compact ordinary-analysis text shows the selected one- or two-step optimization plan: every ordered family step, `exact_algebraic_v1` or `exact_algorithmic_v1` tier, affected target, original-to-final selected-objective saving, conditions, and exact-symbolic qualification. This deterministic presentation is not a superiority claim. Canonical `details` contains every complete replayable trace candidate and identity; search-incomplete and output-truncation qualifications remain separate. Pi correlates and presents protocol-v16 fields but never applies a transformation or recomputes proof, objective, scheduling, or ranking policy.

The eight default exact-algebraic families are repeated-subexpression extraction, identical-call and reciprocal reuse, checked factoring, redundant-operation removal, iterator-invariant hoisting, compatible sharing across named equation RHSs, and bounded Horner reformulation. The separately enabled exact-algorithmic family replaces only ADR-0012's unique maximal supported nested finite-polynomial `Sum` tree inside its existing shell; ineligible or nonpositive proposals stay silent and query candidates remain informational. Sharing requires one compatible positional free-index interface and acyclic producer placement; Horner stays within fixed variable, degree, term, and node ceilings. Python publishes only independently proved positive selected-objective reductions; it omits unknown-cost, unresolved-cardinality, unproved, capture-prone, incompatible-scope, or nonpositive candidates. Position one is neutral; each later position records either proved superiority of the preceding plan or a deterministic non-superiority tie-break. Python independently rederives every algorithmic identity against replayed parents and the original-to-final proof. Pi validates shape, canonical provenance, and correlation only and never derives a sum or recomputes algebra, objective values, applicability, or ranking.

Advice never changes submitted interpretation, ordinary work, scenarios, queries, dependencies, reuse, or extraction diagnostics. Treat aggregate abstract work as a mathematical metric rather than runtime, and do not infer floating-point equivalence or numerical stability from exact-symbolic reassociation.
