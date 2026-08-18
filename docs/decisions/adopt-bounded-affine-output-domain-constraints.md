---
format: current-state-v4
slug: adopt-bounded-affine-output-domain-constraints
status: Proposed
date: 2026-08-18
---
# ADR-adopt-bounded-affine-output-domain-constraints: Adopt bounded affine output-domain constraints

## Context

ADR-0010 admits acyclic affine dependencies between an equation's finite output-domain bounds, but it has no first-class way to intersect that base domain with additional named relations. Callers can express one triangular orientation directly as a lower or upper bound, yet cannot retain several coupled constraints as submitted knowledge, see their combined effective domain, or use the same local context consistently across equation work, scenarios, and targeted mathematical queries. Encoding a rectangular superset and correcting its cardinality externally loses both exact work and reasoning provenance.

A constrained domain must remain subordinate to global assumptions rather than redefine them. A provable contradiction such as a local range outside the assumed parameter context is a caller error, while an admissible parameterized domain may become empty only after specialization and then has exact zero work. When several valid bounds have assumption-dependent dominance, lack of a total ordering does not erase known information: their conjunction has an exact `Min`/`Max` representation.

General integer-polyhedron counting and nonlinear constraints require floor, divisibility, union, piecewise, or solver semantics beyond the existing bounded affine dependency model. The initial family therefore needs an explicit orientation, finite base domain, restricted normalization boundary, deterministic dependency direction, local scope, and inspectable report contract without delegating public policy to backend symbolic behavior.

## Decision

1. `decision: named-targeted-local-constraints` An indexed equation may declare named local `DomainConstraint` relationships, each explicitly identifying the output-index target it tightens. Every LHS output index still has a mandatory finite base `IndexDomain`; constraints intersect that base domain and never define or override global assumptions. Exact request paths localize diagnostics, while unchanged submitted structures and equation-qualified stable constraint names remain available for report provenance.
2. `decision: order-decomposable-affine-family` The initial family accepts conjunctions of integer-affine equality and strict or non-strict inequalities whose target coefficient is `+1` or `-1`. Strict inequalities normalize exactly over integers, equality supplies coincident bounds, and conjunctive `Abs(E) <= R` or `Abs(E) < R` forms and their reversed equivalents normalize into two supported affine bounds. All affine operands must be proved integral. Chained or disjunctive relations, non-unit target coefficients, absolute lower bounds `Abs(E) >= R` and `Abs(E) > R`, general absolute equalities `Abs(E) = R`, their reversed forms, and nonlinear products, powers, variable division, or functions are invalid request structure rather than implicit solver input.
3. `decision: constrained-domain-dependency-and-intersection` A normalized constraint creates dependencies from every referenced output index to its explicit target and composes with base-domain dependencies in one acyclic graph; LHS order remains coordinate order and only breaks dependency-order ties. Multiple valid lower and upper bounds combine exactly through bounded analyzer-owned `Max` and `Min` semantics, preserving parameter-dependent intersections rather than requiring one bound to dominate globally.
4. `decision: global-compatibility-and-specialized-emptiness` Global declarations, definitions, and assumptions govern local-constraint validity. A local/global conjunction proved incompatible before specialization is a localized request error, while compatibility that bounded reasoning cannot decide remains explicit and unresolved. A valid parameterized domain may specialize to an empty intersection in a scenario, in which case its effective cardinality and work are exactly zero. Local output binders may not shadow declared global variables.
5. `decision: whole-equation-local-reasoning` Local constraints govern both sides of their equation: output-coordinate existence, RHS interpretation and direct work, and mathematical queries explicitly targeting that equation. They do not leak to another equation or a top-level expression query. Scenario specialization recomputes effective domains and work; fixed scenarios expose one specialized effective domain, and finite-choice scenarios key effective domains by the same canonical combinations as choice work.
6. `decision: inspectable-constrained-domain-reports` Per-equation reports separately expose unchanged submitted constraints, normalized effective bounds, equation-qualified constraint provenance, and global assumptions used. Query and scenario reports expose the corresponding consumed or specialized constraint context. Public request, report, and transport resources remain strictly bounded, and Python retains all normalization, compatibility, cardinality, and query-policy ownership.
7. `decision: explicit-deferred-constraint-families` Constraint-only domain definitions, non-unit coefficients with floor or divisibility semantics, chained relations, general disjunctions, disconnected absolute-value regions, general bounded affine integer-polyhedron lattice counting, and nonlinear products, powers, variable division, and function constraints remain unsupported and are recorded as future candidates.

## State changes

- update `product/mathematical-input-contract:compositional-indexed-equation-requests`
- update `product/mathematical-analysis-model:ideal-equation-dependency-work`
- update `product/mathematical-analysis-model:assumption-aware-query-reasoning`
- update `product/analysis-report-contract:provenance-preserving-system-work`
- update `product/analysis-report-contract:qualified-query-conclusions`

## Consequences

Callers can state finite simplex-like and other order-decomposable intersections without flattening several relations into one opaque bound or correcting a rectangular overcount externally. Named constraints remain traceable from submitted input through effective domains, exact work, specialization, and equation-targeted queries. Parameter-dependent dominance remains exact through bounded `Min`/`Max` forms, and specialized empty regions close to zero without turning caller contradictions into silent computations.

The public model and private protocol must carry new request and report structures, and the exact private protocol must advance with the changed wire contract. Domain normalization, dependency construction, compatibility classification, aggregation, scenario evaluation, query context, rendering, and provenance must share one bounded interpretation. Existing reports that identify relationships only by unqualified names are insufficient for local names reused across equations, so constraint provenance must retain equation identity, stable constraint names, and unchanged submitted structures.

This decision intentionally does not create a general constraint solver. Unsupported grammar is rejected at the named relationship path, while valid in-family uncertainty stays qualified. Existing unconstrained and acyclic dependent domains retain their behavior, and Pi transports strict shapes and opaque qualified results without interpreting mathematics.

## Alternatives Considered

The chosen approach accepts coordination cost across validation, aggregation, scenarios, queries, reports, and transport so every consumer shares one normalization and effective-domain interpretation.

| Alternative | Why not chosen |
|---|---|
| Keep encoding every relation as a base lower or upper bound | It cannot preserve several named submitted constraints, their exact intersection, or their provenance across consumers. |
| Apply constraints request-wide | A relation defining one equation's coordinates could incorrectly affect unrelated equations and top-level queries. |
| Infer which output index a relation should tighten | Relations such as `i + j <= N` have several valid orientations; an explicit target avoids hidden choices and graph drift. |
| Let constraints define domains without base bounds | Completeness and finiteness would need a separate proof boundary before safe aggregation. |
| Require one bound to dominate under global assumptions | It discards an exact parameter-dependent intersection that bounded `Min`/`Max` can preserve. |
| Admit arbitrary affine or nonlinear constraint solving | Lattice counting, disconnected regions, floors, and nonlinear solvers exceed the approved deterministic family. |

## Status history

- 2026-08-18: Proposed
