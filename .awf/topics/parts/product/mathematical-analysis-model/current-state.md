The mathematical analysis model separates public syntax and analysis semantics from backend-specific representation.

## Claims

### `rule: shared-backend-independent-model`
Both mathematical frontends normalize into one internal model. Parsing, cost semantics, and analysis policy remain separable from SymPy-specific representation, which neither defines the public protocol nor inseparably owns every analysis concern.
Origin: ADR-0001

### `rule: ideal-equation-dependency-work`
Direct Python equation systems resolve unique named producers into a deterministic acyclic graph. Each equation is charged once per local output-domain point, downstream references reuse that result, and inclusive bounded sums use nonnegative mathematical cardinality; unresolved primitive costs remain explicit.
Origin: ADR-0003
