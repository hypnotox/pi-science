The mathematical analysis model separates public syntax and analysis semantics from backend-specific representation.

## Claims

### `rule: shared-backend-independent-model`
Accepted mathematical syntax normalizes into one internal model. Parsing, cost semantics, and analysis policy remain separable from SymPy-specific representation, which neither defines the public protocol nor owns product policy. SymPy is the established algebra, rendering, and verification backend behind checked, resource-bounded seams; prefer extending these seams over recreating backend algebra, and never treat a general or unverified CAS result as supported behavior, proof, or qualification.
Origin: ADR-0001
Revised-by: ADR-0006

### `rule: ideal-equation-dependency-work`
Direct Python equation systems resolve unique named producers into a deterministic acyclic graph. Each equation is charged once per local output-domain point, downstream references reuse that result, and inclusive bounded sums recursively bind each finite direct-work iterator across operation categories, opaque work, and primitive invocations. Acyclic affine output domains aggregate in reverse stable dependency order while preserving LHS coordinate order; bounded intrinsic, submitted, and predecessor-domain facts close supported affine direct-work sums under the existing 4096 reasoning and work budgets. A populated symbolic `Sum` owns its iterator exactly when closure is unavailable; unresolved cardinality, ordering, or finiteness remains explicit, while unresolved primitive costs remain explicit.
Origin: ADR-0003
Revised-by: ADR-0009, ADR-0010

### `rule: assumption-aware-query-reasoning`
The Python query evaluator, not Pi transport, combines declared domains and global assumptions for the supported bounded mathematical families. Answers conservatively identify used assumptions, relevant unsupported assumptions, conditions, blockers, and proof status; localized blockers distinguish failed supported families, structural or resource bounds, ambiguous axes, and missing preconditions. Valid unsupported questions remain unresolved or inapplicable results rather than transport failures or implied broader evaluator support. Python sequentially resolves a derived target only from a proved or proved-under-assumptions closed-form answer with checked evidence and exactly one candidate, inheriting deduplicated conditions and relationship provenance under public bounds. Missing eligibility is an inapplicable result, never submitted-target fallback.
Origin: ADR-0004
Revised-by: ADR-0005, ADR-adopt-explicit-reusable-verified-query-candidates

### `rule: exact-query-values-and-infinity`
Query and scenario finite scalars are bounded exact rationals, including exact decimal syntax, while `oo` and `-oo` are explicit mathematical infinity. Infinite mathematical expressions remain analyzable but never imply finite direct-evaluation work.
Origin: ADR-0004
