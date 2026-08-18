---
format: current-state-v4
slug: adopt-bounded-nested-finite-polynomial-closed-forms
status: Proposed
date: 2026-08-18
---
# ADR-adopt-bounded-nested-finite-polynomial-closed-forms: Adopt bounded nested finite polynomial closed forms

## Context

The closed-form evaluator supports bounded sibling geometric-linear sums but explicitly rejects every nested mathematical sum. Direct-work aggregation is already binder-correct for nested finite sums, so the analyzer can expose the exact submitted evaluation work while remaining unable to derive the corresponding mathematical count. This blocks direct proof of central translation-count identities such as `Sum(Sum(1, (l, -k, k)), (k, 0, p)) = (p + 1)**2` and leaves their quartic system-level scaling to manual derivation.

ADR-0004 requires explicit bounded query families, checked evidence, conservative qualifications, and strict separation between derived mathematical candidates and submitted work. A nested family therefore cannot be a generic invitation to SymPy summation. Each recursive level needs a project-owned structural contract, bounded candidate generation, independent verification, binder-safe translation, and proof of its finite range.

The motivating workload needs finite polynomial sums with affine dependent bounds, not symbolic rational-function coefficients, mixed infinite/geometric trees, or arbitrary whole-system inlining. Named equation RHS queries already provide stable manageable chunks, while protocol-v7 derived targets allow a proved candidate to feed a later equivalence or limit without silently broadening other query kinds.

## Decision

1. `decision: bounded-nested-polynomial-family` A `closed_form` query may analyze one finite-polynomial `Sum` tree under the existing bounded arithmetic shell. The tree is evaluated innermost-first and is limited per selected expression or equation RHS to nesting depth four, eight total sum nodes, and degree eight in each active binder under the existing target, intermediate, rendering, reasoning, and report bounds. The degree limit is measured in the project-owned restricted expression immediately before deriving each recursive level, after reasoning substitutions and verified inner-candidate replacement, across every binder still active at that level; backend witness representations remain governed by independent verification and the existing resource bounds rather than defining public applicability. A nested target cannot mix this family with infinite or geometric-linear sibling sums, and existing non-nested geometric-linear behavior remains unchanged.
2. `decision: polynomial-coefficient-and-range-contract` At each level the summand is a polynomial over exact rational coefficients, declared symbols, and still-outer binders, with no symbolic rational-function coefficient or denominator depending on the active binder. Bounds are finite affine-integer expressions independent of their own binder and must be proved integral. Each range must then be proved ordered for derivation or proved empty for exact-zero closure; when neither proof succeeds, the query returns `unresolved` rather than a conditional or piecewise candidate.
3. `decision: independently-verified-antidifference-witnesses` Python owns the nested-family policy and admits backend candidate generation only after project-owned topology, coefficient, free-name, degree, affine-bound, and resource preflight. Backend binders are collision-free. Every generated witness is independently checked for the exact one-step antidifference identity and inclusive boundary difference, parsed back into the restricted internal model, checked for escaped temporary names and bounds, and rejected unless every recursive level verifies. Backend generation alone is never proof.
4. `decision: explicit-nested-query-composition` The nested family runs directly only for `closed_form`. Direct properties, limits, and asymptotics over a nested sum remain unsupported; an equivalence or limit may consume a proved nested candidate only through an explicit derived target. Nested candidates never replace submitted operation counts, direct work, scenarios, equation reuse, or output-domain multiplicity.
5. `decision: explicit-partial-family-boundary` User-facing and current-state guidance identifies this as a partial closed-form family and records intentionally excluded extensions as future candidates, including rational-function coefficients, multiple or mixed trees, infinite nesting, higher limits, conditional range forms, direct implicit consumers, staged derived-to-closed-form composition, safe cross-equation inlining, and deeper whole-system optimization analysis.

## State changes

- update `product/mathematical-analysis-model:assumption-aware-query-reasoning`
- update `product/analysis-report-contract:qualified-query-conclusions`

## Consequences

Agents can directly prove bounded nested coefficient counts and combine a per-output candidate with separately reported output-domain multiplicity to establish quartic scaling without conflating that mathematical identity with submitted evaluation work. Equation systems remain manageable through independently queried named RHS chunks, and protocol-v7 explicit derived targets provide controlled downstream composition.

The evaluator gains a separate finite-polynomial route rather than weakening the existing geometric-linear route. The implementation must maintain lexical binder ownership across recursive replacement, use collision-free backend witnesses, prove range semantics before telescoping, and fail closed on topology, degree, coefficient, name, ordering, parse, verification, or resource violations. Verified empty ranges must short-circuit before backend reversed-range conventions can change their meaning.

The family is intentionally partial. It does not solve general nested sums, inline equation dependencies, answer whole-system optimization questions, or authorize direct nested property/asymptotic analysis. Those omissions remain visible in blockers, guidance, and the product roadmap rather than being implied by parser acceptance or backend capability.

## Alternatives Considered

| Alternative | Why not chosen |
|---|---|
| Expose unrestricted SymPy summation for nested targets | Backend success would define public policy without stable family, qualification, or proof guarantees. |
| Allow symbolic rational-function coefficients immediately | Recursive denominator obligations and active-outer-binder transitions widen the initial proof boundary beyond the motivating counts. |
| Support multiple or mixed polynomial/geometric trees | Mixed routing and qualification composition add ambiguity while one finite tree covers the central workload. |
| Return conditional or piecewise candidates when ordering is unknown | The public input and range model does not yet own piecewise semantics; unresolved preserves conservative proof policy. |
| Inline named equations to create deeper trees | It would bypass per-target limits and introduce a separate whole-system substitution and optimization model. |
| Let properties and asymptotics derive nested forms implicitly | Query behavior would broaden silently; explicit closed-form plus derived-target composition remains inspectable. |

## Status history

- 2026-08-18: Proposed
