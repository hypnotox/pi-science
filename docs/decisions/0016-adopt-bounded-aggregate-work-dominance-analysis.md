---
format: current-state-v4
slug: adopt-bounded-aggregate-work-dominance-analysis
status: Implemented
date: 2026-08-19
---
# ADR-0016: Adopt bounded aggregate-work dominance analysis

## Context

The analyzer reports one canonical reuse-aware aggregate abstract-work expression for a submitted expression or acyclic equation system. It can qualify the sign of a bounded rational expression and compare two whole candidates, but it does not identify which terms of one work expression matter over different parameter ranges. Agents must inspect rendered algebra, choose a scaling variable, infer crossovers, and decide whether apparent terms are stable across equivalent spellings.

ADR-0003 fixes the aggregate-work meaning: named equations are charged once per output-domain point, downstream references reuse them, and storage, scheduling, hardware, and runtime effects are excluded. ADR-0015 establishes Python-owned bounded sign reasoning and abstention for unsupported work ordering, but its two-candidate semantic gate does not define term decomposition. ADR-0008 therefore left dominance as roadmap work until a bounded contract existed.

Equivalent forms such as `(N + 1)**2` and `N**2 + 2*N + 1` must not yield different public term identities. Signed algebraic corrections such as `-N` can remain relevant to the exact work expression even though negative work is not a physical interpretation. Rational denominators introduce excluded poles, integer variables admit only lattice points, and pairwise term comparisons can grow quadratically. A useful capability consequently needs a canonical term model, domain-aware exact regions, strict resource bounds, and qualified abstention rather than display-string parsing, sampling, or a general inequality solver.

## Decision

1. `decision: single-axis-original-work-dominance` Add a separate domain-neutral `analyze_dominance` operation that analyzes terms within one computation's original reuse-aware aggregate abstract-work expression. The request selects exactly one declared scaling variable, may fix other scalar variables exactly, and may restrict the axis to an exact open or closed interval; omission uses the declared domain. It does not compare whole candidates, and ordinary analysis plus candidate-comparison request and result bytes remain unchanged.
2. `decision: canonical-rational-power-terms` For the bounded supported family, reduce work to one checked univariate rational form and define stable signed terms as the collected nonzero numerator power terms over its shared reduced denominator. Require exact reconstruction before publishing the decomposition, compare term relevance by absolute magnitude while retaining signed renderings, and abstain for unsupported coefficients, opaque aggregates, exponentials, unknown costs, or unresolved work. Identically zero aggregate work over a nonempty active domain is `complete` with no terms or regions, the active domain retained, and an explicit zero-work qualification; `empty` remains reserved for an active domain with no admissible points.
3. `decision: exact-domain-aware-dominance-regions` Derive piecewise dominance through a bounded typed sign-chart seam with an explicit selected axis, so policy consumes structural roots, poles, intervals, and point classifications rather than rendered evidence. Partition from proved roots of pairwise squared-magnitude differences, denominator poles, and active-domain boundaries; report complete tied maximum sets, excluded points, never-dominant terms, and localized unresolved regions. Coalesce adjacent regions with the same dominant set. Real axes use exact intervals and admissible points, while integer axes use coalesced admissible integer ranges and points. The dominance status is exactly `complete`, `unresolved`, or `empty`; a proved-empty active domain returns `empty` with no regions.
4. `decision: qualified-bounded-dominance-transport` Bound term population, pairwise comparisons, structural reasoning, partition growth, rendering, and the supplemental plus combined report before quadratic or serialized growth escapes existing ceilings. Python owns decomposition and mathematical conclusions. Python and Pi expose matching strict requests and reports by advancing the private protocol to v10 and routing the new operation through the existing readiness-gated `analyze_formula` tool. No result claims runtime, storage, scheduling, hardware behavior, rewrite safety, optimization, or multivariate dominance.

## State changes

- update `product/product-boundary:symbolic-analysis-only`
- add `product/mathematical-input-contract:bounded-dominance-analysis-requests`
- add `product/mathematical-analysis-model:canonical-aggregate-work-term-dominance`
- add `product/analysis-report-contract:qualified-dominance-regions`

## Consequences

Agents can ask which exact aggregate-work terms dominate on a declared domain or concrete range and receive stable term identities, exact tied regions, poles, qualifications, and compact integer-domain results. Equivalent supported spellings produce the same decomposition, while the ordinary analysis remains the authoritative source of submitted-graph work.

The checked sign-chart boundary must gain a typed explicit-axis structural result rather than forcing dominance to parse existing rendered property evidence. The public model, result budget, schema, private protocol, TypeScript correlation, compact presentation, and guidance acquire a coordinated operation. Quadratic pairwise reasoning is accepted only behind strict early bounds.

The operation remains intentionally partial. It does not analyze mathematical-value summands, compare candidates, infer several scaling axes, expand opaque sums or `Max`, solve exponential dominance, invent unknown costs, suggest transformations, or interpret symbolic work as observed performance. Unsupported algebra or ordering remains an inspectable unresolved region or result.

## Alternatives Considered

| Alternative | Why not chosen |
|---|---|
| Preserve submitted top-level summands as term identities | Equivalent algebraic spellings would produce different public dominance reports. |
| Compare signed term values | Negative lower-order corrections would be misclassified as irrelevant or as negative work rather than retained by magnitude. |
| Support multivariate or sampled ordering | It would require a broader solver or empirical evidence and could overstate unsupported regions. |
| Reuse rendered property interval strings | Display text does not carry typed roots, poles, axis identity, or domain intersections and is not a safe policy boundary. |
| Add dominance to candidate comparison | Candidate comparison first proves mapped mathematical equivalence; term dominance concerns one already established aggregate-work expression. |

## Status history

- 2026-08-19: Proposed
- 2026-08-19: Accepted; content-sha256: ba0de47644df26bb7f7c6cf554d0bfe918eac5fbdfc0782e442cbbe3cdfc3023

- 2026-08-19: Implementing; content-sha256: ba0de47644df26bb7f7c6cf554d0bfe918eac5fbdfc0782e442cbbe3cdfc3023
- 2026-08-19: Applied; operations: update `product/product-boundary:symbolic-analysis-only`, add `product/mathematical-input-contract:bounded-dominance-analysis-requests`, add `product/mathematical-analysis-model:canonical-aggregate-work-term-dominance`, add `product/analysis-report-contract:qualified-dominance-regions`
- 2026-08-19: Reapplied; operations: add `product/mathematical-input-contract:bounded-dominance-analysis-requests`
- 2026-08-19: Implemented; content-sha256: ba0de47644df26bb7f7c6cf554d0bfe918eac5fbdfc0782e442cbbe3cdfc3023
