---
paths:
  - 'docs/analysis-model.md'
  - 'packages/py-science-formula/src/py_science/formula/contracts/**'
  - 'packages/py-science-formula/src/py_science/formula/domains.py'
  - 'packages/py-science-formula/src/py_science/formula/expressions.py'
  - 'packages/py-science-formula/src/py_science/formula/parser.py'
  - 'packages/pi-science/src/bridge/protocol.ts'
  - 'packages/pi-science/src/bridge/requests.ts'
  - 'packages/pi-science/src/formula-schema.json'
  - 'packages/pi-science/skills/formula-analysis/SKILL.md'
---

# Mathematical input contract

The input contract governs mathematical syntax and the metadata that qualifies its interpretation.

## Safe familiar inputs

Requests use a safely parsed restricted subset of actual SymPy conventions, with relevant metadata for domains, assumptions, scenarios, opaque primitive costs, and bounded nonrecursive lexical bindings spelled `Let(name, value, body)`. A `Let` value sees its enclosing scope but not its own name; its name is visible only in the body and the value is charged once at its lexical placement. Submitted syntax is data and never arbitrary Python; omitted knowledge remains explicit and unresolved. Restricted LaTeX input remains deferred until a bounded contract and implementation exist.

## Indexed equation requests

Direct Python requests safely accept either an ordinary expression or uniquely named indexed equations, bounded sums, bounded nonrecursive `Let(name, value, body)` bindings, generic calls, local output domains, declared external-variable domains, function definitions, and scalar primitive work. A generic function has one nonrecursive definition, one scalar primitive cost, or neither—never both—and callers do not separately supply operation tallies derivable from a definition. Directed definitions are acyclic, and directly detectable contradictory assumptions are invalid. An equation may additionally carry at most 32 uniquely named, explicit-target local constraints; mandatory finite base domains remain authoritative, and local output binders may not shadow declared global variables because coordinate scope must not silently replace request-wide knowledge. The partial supported family requires proved-integral affine operands and normalizes integer-affine unit-coefficient equalities, strict or non-strict inequalities, and conjunctive `Abs(E) <= R` or `Abs(E) < R` forms, including reversed equivalents, into acyclic effective bounds. Strict inequalities normalize exactly on the integer lattice. The family rejects constraint-only domains, floors/divisibility, chains, disjunctions, disconnected regions, general lattice counting, and nonlinear relations. LHS index order remains mathematical coordinate order and only a stable dependency-order tie-break: dependency order is inferred separately because reordering coordinates to bind a domain would transpose the stated result. Formula text is bounded data parsed only through the restricted syntax.

## Candidate comparison requests

Python and Pi accept exactly two uniquely named expression or acyclic equation-system candidates with explicitly mapped outputs and shared mathematical metadata. Comparison requests contain no scenarios or general queries.

## Mathematical queries

Formula requests may carry an optional bounded `queries` collection of explicitly named `equivalence`, `closed_form`, `properties`, `limit`, or `asymptotic` questions. Queries are caller-explicit and target the whole expression, one named equation RHS, or an eligible derived result; normalized nested paths are unstable, and implicit scenario fan-out would multiply bounded work while obscuring the selected context. An `equivalence`, `properties`, `limit`, or `asymptotic` query may instead spell `target: {kind: "derived", query: "earlier_name"}` to select exactly one verified candidate from an earlier `closed_form` query. No forward, self, scenario, or closed-form derived target is accepted; derived operands never replace submitted syntax, operation counts, or direct work. Exact finite points use canonical rational or decimal scalar syntax and signed infinity is explicit. Restricted LaTeX, complex values, dimensions, vector shorthand, differentiation, and scenario-context queries remain future capabilities.

## Dominance requests

Python and Pi accept one bounded dominance request for one expression or equation system, one declared numeric axis, exact non-axis fixed values, and an optional exact range. Scenarios, queries, candidates, multiple axes, and mathematical-value summands are excluded.

## Optimization requests

Optimization is available only through an explicit `optimize` request. It requires one expression or equation system, a `preserve_all_outputs_v1` exact-symbolic goal using `submitted_domain_v1`, one unit-work or strictly positive exact weighted-operation objective, the fixed `bounded_goal_v1` search policy, the fixed `verifier_backed_v1` proof policy, and a `projection_limit` from 1 through 16. `weighted_operations_v1` requires canonical strictly positive exact-rational weights for additions, subtractions, multiplications, divisions, and powers. The submitted domain includes the computation's variable and output domains, constraints, and assumptions; definitions, functions, and primitive costs remain part of the submitted computation context. Requests expose no family, depth, search-budget, selected-output, goal-local-domain, hard-resource-bound, scenario, or query control. Ordinary analysis, candidate comparison, and dominance requests carry no optimization configuration. Returned candidates preserve every submitted output and carry the complete replayable computation without goal, search, proof, or projection policy in candidate identity.
