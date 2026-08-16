---
format: current-state-v4
slug: adopt-compositional-indexed-equation-analysis
status: Proposed
date: 2026-08-17
---
# ADR-adopt-compositional-indexed-equation-analysis: Adopt compositional indexed equation analysis

## Context

The implemented formula analyzer accepts one scalar arithmetic expression and reports its normalized rendering and submitted operation tally. The motivating AFMM use case instead requires agents to state indexed computations across particle, box, coefficient, component, and interaction domains; split those computations into reusable named results; and derive system work under explicit mathematical relationships. The same capability must serve both pre-implementation reasoning and agent-formulated analysis of an existing algorithm without reading or inferring from source code.

A formula alone distinguishes mathematical application from implementation only when its computation and reuse boundaries are explicit. Treating every downstream reference as a recursive re-evaluation would model an avoidably poor implementation, while silently eliminating every repeated expression would replace the submitted computation. The analysis therefore needs durable semantics for named results, bound iteration, opaque functions, assumptions, and parameter treatment.

ADR-0001 already requires safe familiar frontends, a backend-independent mathematical model, and qualified inspectable results. This decision specializes that direction for compositional indexed equation systems without introducing AFMM- or physics-specific semantics. SymPy may normalize and render validated expressions, but it cannot become the parser, public contract, or source of analysis policy.

## Decision

1. `decision: compositional-mathematical-requests` Formula requests may describe named equations over indexed scalar algebra, generic mathematical calls, bounded sums, and explicitly declared local output domains. External variables declare their mathematical domains, while scenarios separately declare fixed, bounded, finite-choice, derived, and asymptotic treatments. These constructs enter the shared typed mathematical model only through safely parsed restricted mathematical syntax; arbitrary Python and source-code inference remain forbidden.
2. `decision: ideal-equation-dependency-semantics` Named equations form an acyclic dependency graph. Each equation defines one unique result, is evaluated once per point in its local output domain, and is reused by downstream references without recursively charging its construction cost. Bound indices are locally scoped, every free index must be declared or bound, and duplicate definitions, unbound indices, self-reference, and dependency cycles are invalid. Repeated unnamed expressions remain part of the submitted work and may be reported as extraction opportunities rather than silently cached.
3. `decision: mathematical-aggregate-work-semantics` A bounded sum has inclusive bounds and, when integral ordering facts are provable, cardinality `max(upper - lower + 1, 0)`. It multiplies body work by that cardinality and adds `max(cardinality - 1, 0)` mathematical reduction additions. Nested sums apply the same rule recursively. Aggregate work excludes loop control, indexing, bound evaluation, storage, and hardware effects, and remains qualified or unresolved when the required cardinality facts cannot be established. Reports distinguish submitted structural operations from aggregate executed mathematical work.
4. `decision: explicit-function-cost-knowledge` A generic function's mathematical definition is the authoritative source for derived work. When no definition is supplied, a request may attach one scalar symbolic per-call work expression; without either, the function retains an explicit unresolved symbolic cost. A request cannot provide both a definition and primitive work for one function, recursive definitions are invalid, and manual operation-category metadata does not duplicate information derivable from a definition.
5. `decision: provenance-preserving-system-analysis` Assumptions and directed definitions are safely parsed mathematical relationships applied only through supported deterministic transformations. Directed definitions must be acyclic, and directly detectable contradictory assumptions are invalid. Every simplification identifies the relationships it used; unsupported inference and untreated scaling variables remain unresolved. Results expose normalized SymPy and LaTeX interpretations, per-equation and system work, dependencies and reuse, primitive invocation counts, assumptions used, unknown costs, and qualified conclusions without claiming physical correctness, implementation timing, or global algorithmic optimality.

## State changes

- add `product/mathematical-input-contract:compositional-indexed-equation-requests`
- add `product/mathematical-analysis-model:ideal-equation-dependency-work`
- add `product/analysis-report-contract:provenance-preserving-system-work`

## Consequences

Agents can represent an AFMM-like calculation as a mathematical system, inspect each named computation independently, compose its work into later equations, and see when a value can be computed once and reused. The same request can preserve exact symbolic work while scenarios distinguish fixed parameters from scaling dimensions. Indexed scalar algebra and generic functions also cover vector mathematics without embedding physics-specific types or operations.

The analyzer acquires stricter validation and a symbolic cost algebra rather than relying on SymPy's expression behavior. Requests must supply domains, relationships, and opaque costs needed for strong conclusions; incomplete knowledge intentionally produces unresolved results. The once-per-domain-point rule describes ideal reuse explicit in the submitted equation graph, not the behavior of an implementation and not proof that no different mathematical formulation is cheaper.

The public Python request and result contracts must gain whole-request complexity and bounded-output policies. Pi's private versioned adapter must remain compatible with those evolving contracts without becoming public analysis authority. LaTeX parsing, cyclic recurrences, physical validation, source analysis, empirical performance, hardware cost models, and code generation remain outside this decision.

## Alternatives Considered

| Alternative | Why not chosen |
|---|---|
| Continue with independent scalar expressions | It cannot represent aggregate indexed work, dependencies, or reusable AFMM stages. |
| Make SymPy expressions the analysis model | It would couple public semantics and safety policy to one backend and conflict with ADR-0001. |
| Recursively charge every referenced equation | It models unnecessary recomputation instead of the ideal reuse made explicit by named results. |
| Silently deduplicate every repeated expression | It changes the submitted computation rather than reporting a possible extraction. |
| Add AFMM, vector, or particle-specific primitives | Indexed scalar algebra and generic functions provide the required mathematics without narrowing a general analysis product. |
| Require manual operation categories for opaque functions | Exact definitions already expose those operations; one scalar work expression is sufficient when internals remain intentionally opaque. |

## Status history

- 2026-08-17: Proposed
