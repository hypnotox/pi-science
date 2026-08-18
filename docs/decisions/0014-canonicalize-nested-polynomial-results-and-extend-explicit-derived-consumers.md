---
format: current-state-v4
slug: canonicalize-nested-polynomial-results-and-extend-explicit-derived-consumers
status: Implementing
date: 2026-08-18
---
# ADR-0014: Canonicalize Nested Polynomial Results and Extend Explicit Derived Consumers

## Context

ADR-0012 introduced checked closed forms for one bounded nested finite-polynomial `Sum` tree while deliberately keeping the result informational: only an explicit derived equivalence or limit could consume the candidate. This preserved submitted work and proof provenance, but real coefficient-count formulas expose two related usability gaps.

For example, the packed interaction count
`Sum(Sum(Sum(2*k + 1, (k, 0, p - n)), (m, 0, n)), (n, 0, p))`
is proved, yet its candidate renders as a long algebraically equivalent accumulation rather than the compact polynomial `(p + 1)*(p + 2)**2*(p + 3)/12`. The rational evaluator can prove equivalence and a fixed `p = 12` value after explicit derived reuse, but the presentation obscures that route, while properties and asymptotics cannot select the proved candidate as an explicit derived operand.

The existing safety boundary remains necessary. SymPy may construct an algebraic candidate only behind project-owned structural and resource checks, and a backend transformation does not establish the submitted sum's domain obligations or proof provenance. Canonicalization therefore must be bounded and independently checked, the original sum must remain visible in evidence and work accounting, and downstream analysis must remain explicit rather than silently replacing direct `Sum` queries.

## Decision

1. `decision: canonical-explicit-nested-polynomial-operands` A proved bounded nested-polynomial closed form exposes a resource-checked canonical factored-polynomial candidate while preserving the submitted sum as its proof source and direct-work subject. Canonicalization separates exact rational content and sign, collects factor multiplicities, and orders factors through the restricted canonical renderer; it publishes no candidate unless the result stays within the polynomial, resource, parse, name, and rendering bounds and an independent exact polynomial-identity check verifies it against the proved candidate. That checked candidate may be selected explicitly as a derived operand by equivalence, properties, limit, and asymptotic queries, with its source qualifications and normalized interpretation retained. Direct equivalence, properties, limits, and asymptotics over the nested `Sum` remain unsupported, and no symbolic result claims runtime, cache behaviour, numerical quality, or an optimal implementation parameter.

## State changes

- update `product/mathematical-input-contract:explicit-mathematical-queries`
- update `product/mathematical-analysis-model:assumption-aware-query-reasoning`
- update `product/analysis-report-contract:qualified-query-conclusions`

## Consequences

Nested polynomial identities can be presented in a compact stable form and then reused for exact values, sign analysis, limits, and asymptotics without resubmitting or concealing the operand that was proved. The candidate remains distinct from submitted operation counts, direct work, scenarios, equation reuse, and output multiplicity, and every dependent conclusion carries the closed-form source's conditions and provenance.

Canonical factoring adds another guarded backend transformation and verification step. A candidate that exceeds its polynomial, resource, rendering, parsing, or identity checks is rejected rather than published. Explicit derived targeting costs one named query step, but keeps transformation visible and avoids promising general analysis of `Sum` expressions.

Performance and numerical trade-offs remain empirical questions. The symbolic API may report exact mathematical counts and asymptotic structure, but benchmark evidence remains necessary for wall-clock, cache, accuracy, and tuning conclusions.

## Alternatives Considered

| Alternative | Why not chosen |
|---|---|
| Publish the existing verified but uncanonicalized candidate | It preserves correctness but leaves central polynomial identities unnecessarily opaque. |
| Implicitly replace nested sums for every downstream query | It makes query behaviour less inspectable and silently broadens direct `Sum` support. |
| Permit unrestricted SymPy simplification and downstream evaluation | Backend heuristics and resource use would define public policy without stable preflight, verification, or domain qualification. |
| Add only presentation normalization | It would not let sign or asymptotic queries reuse the already-proved operand. |
| Expand explicit consumers without canonicalizing the candidate | It improves reuse but leaves deterministic compact presentation, the other observed usability gap, unsolved. |

## Status history

- 2026-08-18: Proposed
- 2026-08-18: Accepted; content-sha256: cb69cfdb87684c778657de0f44693bf7239d7c6c57f6481e46775d3f96ca2eda
- 2026-08-18: Amended; content-sha256: b0b3a288afd80c8f4b800d637bb2f385c416959304a98fcbb7171d53e179028d
- 2026-08-18: Implementing; content-sha256: b0b3a288afd80c8f4b800d637bb2f385c416959304a98fcbb7171d53e179028d
- 2026-08-18: Applied; operations: update `product/mathematical-input-contract:explicit-mathematical-queries`, update `product/mathematical-analysis-model:assumption-aware-query-reasoning`, update `product/analysis-report-contract:qualified-query-conclusions`
