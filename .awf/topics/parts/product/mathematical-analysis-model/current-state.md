The mathematical analysis model separates public syntax and analysis semantics from backend-specific representation.

## Claims

### `rule: shared-backend-independent-model`
Both mathematical frontends normalize into one internal model. Parsing, cost semantics, and analysis policy remain separable from SymPy-specific representation, which neither defines the public protocol nor inseparably owns every analysis concern.
Origin: ADR-0001

### `rule: ideal-equation-dependency-work`
Direct Python equation systems resolve unique named producers into a deterministic acyclic graph. Each equation is charged once per local output-domain point, downstream references reuse that result, and inclusive bounded sums recursively bind each finite direct-work iterator across operation categories, opaque work, and primitive invocations. A populated symbolic `Sum` owns its iterator exactly; unresolved cardinality remains explicit, while unresolved primitive costs remain explicit.
Origin: ADR-0003
Revised-by: ADR-correct-nested-finite-work-current-state-claims

### `rule: assumption-aware-query-reasoning`
The Python query evaluator, not Pi transport, combines declared domains and global assumptions for the supported bounded mathematical families. Answers conservatively identify used assumptions, relevant unsupported assumptions, conditions, blockers, and proof status; localized blockers distinguish failed supported families, structural or resource bounds, ambiguous axes, and missing preconditions. Valid unsupported questions remain unresolved or inapplicable results rather than transport failures or implied broader evaluator support.
Origin: ADR-0004
Revised-by: ADR-0005

### `rule: exact-query-values-and-infinity`
Query and scenario finite scalars are bounded exact rationals, including exact decimal syntax, while `oo` and `-oo` are explicit mathematical infinity. Infinite mathematical expressions remain analyzable but never imply finite direct-evaluation work.
Origin: ADR-0004
