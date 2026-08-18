The input contract governs mathematical syntax and the metadata that qualifies its interpretation.

## Claims

### `rule: safe-familiar-inputs`
Requests use a safely parsed restricted subset of actual SymPy conventions, with relevant metadata for domains, assumptions, scenarios, and opaque primitive costs. Submitted syntax is data and never arbitrary Python; omitted knowledge remains explicit and unresolved. Restricted LaTeX input remains deferred until a bounded contract and implementation exist.
Origin: ADR-0001
Revised-by: ADR-0007

### `rule: compositional-indexed-equation-requests`
Direct Python requests safely accept either an ordinary expression or uniquely named indexed equations, bounded sums, generic calls, local output domains, declared external-variable domains, function definitions, and scalar primitive work. Local output-domain bounds may infer acyclic dependencies through the bounded affine-integer grammar; LHS index order remains the mathematical coordinate order and is only a stable dependency-order tie-break. Self-dependence, cycles, and dependent calls, indexed values, symbolic products, powers, division, or aggregate operators are rejected, while independent bounds retain their established family. Formula text is bounded data parsed only through the restricted syntax.
Origin: ADR-0003
Revised-by: ADR-0010

### `rule: explicit-mathematical-queries`
Formula requests may carry an optional bounded `queries` collection of explicitly named `equivalence`, `closed_form`, `properties`, `limit`, or `asymptotic` questions. A query targets the whole expression or a named equation RHS; it cannot select nested syntax or a scenario context. Exact finite points use canonical rational or decimal scalar syntax and signed infinity is explicit. Restricted LaTeX, complex values, dimensions, vector shorthand, differentiation, and scenario-context queries remain future capabilities.
Origin: ADR-0004
