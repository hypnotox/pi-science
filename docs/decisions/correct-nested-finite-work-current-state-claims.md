---
format: current-state-v4
slug: correct-nested-finite-work-current-state-claims
status: Implemented
date: 2026-08-18
---
# ADR-correct-nested-finite-work-current-state-claims: Correct nested finite-work current-state claims

## Context

ADR-0003 already decides that nested bounded sums apply aggregate-work semantics recursively. The prior current-state claims described cardinality scaling but did not state the binder ownership required to prevent a nested direct-work iterator from escaping into aggregate operation counts, opaque work, primitive invocations, totals, or fixed scenarios.

## Decision

1. `decision: binder-correct-nested-direct-work-claims` Correct the ADR-0003-backed current-state claims to state that every finite direct-work field is aggregated through its lexical `Sum` binder, a retained symbolic `Sum` is exact populated work, and unproved cardinality remains a flat explicit qualification. This clarification preserves ADR-0003 claim origins and does not broaden mathematical closed-form evaluation or apply dependent output-domain policy.

## State changes

- update `product/mathematical-analysis-model:ideal-equation-dependency-work`
- update `product/analysis-report-contract:provenance-preserving-system-work`

## Consequences

Current-state documentation and reports distinguish binder-correct finite direct work from unsupported nested mathematical closed forms without changing protocol shape, output-domain policy, or unresolved-cardinality semantics.

## Alternatives Considered

| Alternative | Why not chosen |
|---|---|
| Amend ADR-0003 | ADR-0003 is terminal and its body is frozen. |
| Leave the claims unchanged | It would retain an incorrect current-state description of already-decided recursive sum semantics. |

## Status history

- 2026-08-18: Proposed
- 2026-08-18: Implemented; content-sha256: 6976c5bc2bdd9e32506ddf354e457db17127a7f62645310eb23efa395d7144d9
