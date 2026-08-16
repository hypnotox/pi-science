The mathematical analysis model separates public syntax and analysis semantics from backend-specific representation.

## Claims

### `rule: shared-backend-independent-model`
Both mathematical frontends normalize into one internal model. Parsing, cost semantics, and analysis policy remain separable from SymPy-specific representation, which neither defines the public protocol nor inseparably owns every analysis concern.
Origin: ADR-0001
