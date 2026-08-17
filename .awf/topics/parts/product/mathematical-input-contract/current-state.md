The input contract governs mathematical syntax and the metadata that qualifies its interpretation.

## Claims

### `rule: safe-familiar-inputs`
Requests use familiar LaTeX or a safely parsed restricted subset of actual SymPy conventions, with relevant metadata for domains, assumptions, scenarios, and opaque primitive costs. Submitted syntax is data and never arbitrary Python; omitted knowledge remains explicit and unresolved.
Origin: ADR-0001

### `rule: compositional-indexed-equation-requests`
Direct Python requests safely accept either an ordinary expression or uniquely named indexed equations, bounded sums, generic calls, local output domains, declared external-variable domains, function definitions, and scalar primitive work. Formula text is bounded data parsed only through the restricted syntax.
Origin: ADR-0003

### `rule: explicit-mathematical-queries`
Formula requests may carry an optional bounded `queries` collection of explicitly named `equivalence`, `closed_form`, `properties`, `limit`, or `asymptotic` questions. A query targets the whole expression or a named equation RHS; it cannot select nested syntax or a scenario context. Exact finite points use canonical rational or decimal scalar syntax and signed infinity is explicit. Restricted LaTeX, complex values, dimensions, vector shorthand, differentiation, and scenario-context queries remain future capabilities.
Origin: ADR-0004
