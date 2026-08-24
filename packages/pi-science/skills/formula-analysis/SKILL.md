---
name: pi-science-formula-analysis
description: Analyze or explicitly optimize one restricted SymPy expression or named equation system with bounded verified replayable plans, compare two mapped candidates, or analyze bounded one-axis aggregate-work term dominance, for normalized interpretation, qualified symbolic work, reuse, provenance, bounded mathematical conclusions, and unresolved costs. Use for formula structure and abstract work, not numeric evaluation, benchmarking, physical validation, or implementation generation.
---

# Formula analysis

Use `analyze_formula` for one bounded restricted-SymPy expression or one nonempty list of uniquely named equations. Choose `expression` for an isolated calculation. Choose `equations` when results have local output domains or later equations reuse named results. Submit a separate explicit `operation: optimize` request only when you want verified transformation plans. Pi supplies `syntax: sympy`; do not include `syntax` in a tool call.

## Request cookbook

Choose one recipe, then add only metadata accepted by that operation. The tool schema is authoritative for mechanical collection, source-size, and numeric bounds; use returned field paths and supported alternatives to repair validation failures.

### Analyze an expression or selected system outputs

Omit `operation` for ordinary analysis. An expression may omit `outputs` or use only `["expression"]`; a system may use a unique list of equation names. Ordinary analysis accepts scenarios and queries but no optimization controls.

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

### Request explicit weighted optimization

Supply every fixed goal, search, and proof literal. A weighted objective requires all five strictly positive exact-rational weights. `projection_limit` controls only the returned ranked prefix.

```json
{
  "operation": "optimize",
  "expression": "(x + 1)**2 + (x + 1)**3",
  "variables": { "x": { "domain": "real" } },
  "goal": {
    "kind": "preserve_all_outputs_v1",
    "semantics": "exact_symbolic_v1",
    "operating_domain": "submitted_domain_v1",
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
  },
  "search": { "kind": "bounded_goal_v1" },
  "proof": { "kind": "verifier_backed_v1" },
  "projection_limit": 5
}
```

Use `{"kind":"unit_work_v1"}` as the goal objective for unit work. Do not add family, depth, budget, selected-output, goal-local-domain, or hard-resource-bound controls.

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
- For optimization, distinguish observed classification, search completion, deterministic selection, and output projection. `incomplete` does not prove that no improvement exists, truncation does not mean search exhaustion, and first position does not prove best or optimal.
- A direct `operation: optimize` failure contains no plans. Ordinary analysis has no optimizer result or passive optimizer failure.

When a request fails, retain the Python-owned message and use any returned field path, source span, or supported alternative to correct it rather than guessing a broader spelling. For query answers, read `conclusion`, conditions, assumptions used, relevant unsupported assumptions, blockers, evidence, and any informational derived candidates. An unresolved query blocker identifies the failed family, exceeded bound, ambiguous axis, or missing supported precondition. Use any measured observation and recovery hint to simplify, reformulate, or select a supported source family. Recovery hints are conservative: they do not certify equivalence or promise wider evaluator support. Treat `proved_under_assumptions`, conservative bounds, `unresolved`, and `inapplicable` as distinct outcomes.

The tool analyzes formulas and directly attached mathematical schema only. It does not accept LaTeX input, infer formulas from source, evaluate represented values numerically, validate physics, profile an implementation, predict runtime or hardware behavior, prove arbitrary theorems, or generate code.

For persistent or one-off direct Python use, depend on `py-science-formula` independently of Pi's isolated backend and import `py_science.formula`. The [`py-science-formula` README](../../../py-science-formula/README.md) contains the matching typed request and PEP 723 guidance.

## Use bounded optimization

Submit `operation: optimize` only for an explicit preserve-all exact-symbolic goal over the computation's submitted mathematical facts. Supply `goal.kind: preserve_all_outputs_v1`, `goal.semantics: exact_symbolic_v1`, `goal.operating_domain: submitted_domain_v1`, a unit-work or exact weighted-operation objective, `search.kind: bounded_goal_v1`, `proof.kind: verifier_backed_v1`, and `projection_limit` from 1 through 16. Ordinary analysis has no optimization controls or plans. Keep scenarios and queries out of optimization requests.

Python searches all shipped exact-algebraic families and the exact-algorithmic `finite_polynomial_sum_v1` family with fixed fair monotonic depth two. Each published plan contains a complete policy-free candidate, one or two replayable parent-relative steps, independent original-to-final evidence, positive selected-objective whole-computation savings, and only a `strict_improvement` claim. The exact-algorithmic lane replaces only ADR-0012's unique maximal supported nested finite-polynomial `Sum` tree inside its existing shell. Query candidates remain informational and never serve as optimizer proof.

Read the canonical result in `details`. `classification` reports only the observed population: `plans_returned`, `no_applicable_candidate`, or `no_verified_improvement`. `search_scope` reports actual families, fixed depth, configured limits, and complete or incomplete bounded search. `selection.kind` is `deterministic_ranked_prefix`; it does not claim superiority or optimality. `projection_status` separately reports whether the output prefix was truncated. A typed failure contains no plan.

A blocker names a family, target, localized reason, and required information already observed during generation or verification. Treat it as missing-information guidance, not a candidate, recommendation, or proof. Blockers may identify a missing primitive cost, unproved domain or cardinality fact, or evaluator limit; unsafe or unlocalized refusals remain absent.

The compact optimization text keeps classification, plans, deterministic selection, search scope, output projection, and blockers visibly separate. Pi correlates and presents protocol-v17 fields but never applies a transformation or recomputes proof, objective, applicability, refusal, scheduling, or ranking policy. Treat aggregate abstract work as a mathematical metric rather than runtime, and do not infer best-candidate status, global optimality, floating-point equivalence, or numerical stability from exact-symbolic reassociation.
