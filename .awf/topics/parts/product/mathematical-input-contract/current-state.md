The input contract governs mathematical syntax and the metadata that qualifies its interpretation.

## Claims

### `rule: safe-familiar-inputs`
Requests use a safely parsed restricted subset of actual SymPy conventions, with relevant metadata for domains, assumptions, scenarios, opaque primitive costs, and bounded nonrecursive lexical bindings spelled `Let(name, value, body)`. A `Let` value sees its enclosing scope but not its own name; its name is visible only in the body and the value is charged once at its lexical placement. Submitted syntax is data and never arbitrary Python; omitted knowledge remains explicit and unresolved. Restricted LaTeX input remains deferred until a bounded contract and implementation exist.
Origin: ADR-0001
Revised-by: ADR-0007, ADR-0018

### `rule: compositional-indexed-equation-requests`
Direct Python requests safely accept either an ordinary expression or uniquely named indexed equations, bounded sums, bounded nonrecursive `Let(name, value, body)` bindings, generic calls, local output domains, declared external-variable domains, function definitions, and scalar primitive work. An equation may additionally carry at most 32 uniquely named, explicit-target local constraints; mandatory finite base domains remain authoritative. The partial supported family normalizes integer-affine unit-coefficient equality or inequalities and conjunctive `Abs(E) <= R` forms into acyclic effective bounds; it rejects constraint-only domains, floors/divisibility, chains, disjunctions, disconnected regions, general lattice counting, and nonlinear relations. LHS index order remains mathematical coordinate order and only a stable dependency-order tie-break. Formula text is bounded data parsed only through the restricted syntax.
Origin: ADR-0003
Revised-by: ADR-0010, ADR-0013, ADR-0018

### `rule: bounded-candidate-comparison-requests`
Python and Pi accept exactly two uniquely named expression or acyclic equation-system candidates with explicitly mapped outputs and shared mathematical metadata. Comparison requests contain no scenarios or general queries.
Origin: ADR-0015

### `rule: explicit-mathematical-queries`
Formula requests may carry an optional bounded `queries` collection of explicitly named `equivalence`, `closed_form`, `properties`, `limit`, or `asymptotic` questions. An `equivalence`, `properties`, `limit`, or `asymptotic` query may instead spell `target: {kind: "derived", query: "earlier_name"}` to select exactly one verified candidate from an earlier `closed_form` query. No forward, self, scenario, or closed-form derived target is accepted; derived operands never replace submitted syntax, operation counts, or direct work. Exact finite points use canonical rational or decimal scalar syntax and signed infinity is explicit. Restricted LaTeX, complex values, dimensions, vector shorthand, differentiation, and scenario-context queries remain future capabilities.
Origin: ADR-0004
Revised-by: ADR-0011, ADR-0014

### `rule: bounded-dominance-analysis-requests`
Python and Pi accept one bounded dominance request for one expression or equation system, one declared numeric axis, exact non-axis fixed values, and an optional exact range. Scenarios, queries, candidates, multiple axes, and mathematical-value summands are excluded.
Origin: ADR-0016


### `rule: bounded-optimization-advice-requests`
Ordinary requests carry `optimization.max_suggestions` and an optional exact objective selector; omission is `unit_work_v1`. Direct `optimize` carries `max_plans` and the same selector. `weighted_operations_v1` requires all five strictly positive bounded exact-rational operation weights; opaque work remains coefficient one. Its returned candidates include syntax, transformed expression or equations, required variables/functions/costs/assumptions/definitions, and output identities, but exclude scenarios, queries, and optimization controls. Candidate comparison and dominance requests do not carry optimization configuration.
Origin: ADR-0017
Revised-by: ADR-0018, ADR-0019
