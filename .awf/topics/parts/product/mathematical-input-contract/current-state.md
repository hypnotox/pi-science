The input contract governs mathematical syntax and the metadata that qualifies its interpretation.

## Claims

### `rule: safe-familiar-inputs`
Requests use familiar LaTeX or a safely parsed restricted subset of actual SymPy conventions, with relevant metadata for domains, assumptions, scenarios, and opaque primitive costs. Submitted syntax is data and never arbitrary Python; omitted knowledge remains explicit and unresolved.
Origin: ADR-0001

### `rule: compositional-indexed-equation-requests`
Direct Python requests safely accept either an ordinary expression or uniquely named indexed equations, bounded sums, generic calls, local output domains, declared external-variable domains, function definitions, and scalar primitive work. Formula text is bounded data parsed only through the restricted syntax.
Origin: ADR-0003
