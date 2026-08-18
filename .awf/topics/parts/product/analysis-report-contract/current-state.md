The report contract governs inspectability, qualification, and unresolved analysis results.

## Claims

### `rule: qualified-inspectable-results`
Every analysis reports the normalized interpretation actually analyzed and distinguishes exact results, assumption-dependent results, conservative bounds, conditional rewrites, and unresolved quantities. It never silently fixes a scaling variable, invents an unknown cost, or presents sampling as a mathematical bound.
Origin: ADR-0001

### `rule: provenance-preserving-system-work`
Direct Python system reports preserve exact general symbolic work and identify every supported equality or directed definition used in a deterministic specialization. Finite direct-work `Sum` expressions retain lexical ownership of local iterators, and unresolved cardinality remains a flat explicit qualification rather than a free local symbol. Bounded explicit scenarios report their substitutions, provenance, qualifications, and unresolved blockers; unsupported inference, ordering, multivariate dominance, monotonicity, and opaque costs remain explicit rather than becoming stronger claims. These reports analyze submitted mathematical structure and complexity, not physical correctness, implementation timing, or global optimality.
Origin: ADR-0003
Revised-by: ADR-correct-nested-finite-work-current-state-claims

### `rule: qualified-query-conclusions`
Each query result preserves its submitted target and normalized interpretation and returns only `proved`, `proved_under_assumptions`, `disproved`, `unresolved`, or `inapplicable` conclusions with inspectable evidence and qualifications. Unresolved blockers identify the failed supported family, structural or resource bound, ambiguous axis, or missing precondition and provide safe reformulation guidance when one exists; observed and configured values appear only when bounded inspection measured them, and guidance neither proves equivalence nor promises broader evaluator support. Derived candidates are informational and never replace submitted operation counts or direct work; no-query reports remain valid with an empty query collection.
Origin: ADR-0004
Revised-by: ADR-0005
