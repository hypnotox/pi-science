---
format: current-state-v4
slug: adopt-bounded-candidate-comparison
status: Proposed
date: 2026-08-19
---
# ADR-adopt-bounded-candidate-comparison: Adopt bounded candidate comparison

## Context

The analyzer accepts one expression or one named indexed equation system. It can answer a bounded equivalence query for one selected operand and separately report reuse-aware aggregate mathematical work, but an agent must submit alternatives independently, align their intended outputs, and reconstruct the semantic and cost relationship outside the deterministic backend.

ADR-0003 fixes the current abstract-work semantics: named equations are evaluated once per output-domain point, downstream references reuse them, bounded sums include mathematical reduction work, and indexing, storage, scheduling, hardware, and runtime effects are excluded. ADR-0008 keeps candidate comparison as roadmap work until a bounded contract exists. The existing query seam compares a selected equation RHS without expanding differently named producers, so whole-system comparison requires a separate bounded semantic view of the acyclic dependency graph while preserving the submitted graph for work accounting.

Candidate comparison must remain general mathematical tooling. AFMM is a motivating future acceptance case, not a domain model. Resource vectors, generated transformations, parameter search, and configurable machine-arithmetic semantics are independent future decisions rather than prerequisites for comparing candidates under the existing mathematical model.

## Decision

1. `decision: bounded-general-candidate-comparison` Add a domain-neutral operation that compares exactly two supported mathematical candidates under shared request metadata. Each candidate may use the existing restricted expression or acyclic indexed-equation-system language, and explicitly mapped outputs must have compatible mathematical interfaces.
2. `decision: semantic-comparison-precedes-work-preference` Establish the semantic relationship of every mapped output before deriving a work preference. Use bounded acyclic dependency expansion only for semantic comparison, preserve the submitted candidate graphs for reuse-aware work accounting, and abstain when output correspondence or equivalence cannot be established within supported rules and resource limits.
3. `decision: qualified-abstract-work-comparison` Compare each candidate's canonical aggregate abstract mathematical work under ADR-0003, return the symbolic delta, and derive a winner or crossover condition only within a bounded supported sign or inequality family. Unknown costs or unsupported ordering remain explicit unresolved results, and no conclusion claims implementation speed, storage behavior, numerical-machine equivalence, or global optimality.
4. `decision: python-owned-bounded-comparison-policy` Keep candidate validation, semantic expansion, equivalence, work comparison, qualifications, and aggregate resource limits in the transport-free Python package. Pi transports the versioned structured request and evidence without recreating mathematical policy.

## State changes

- update `product/product-boundary:symbolic-analysis-only`
- add `product/mathematical-input-contract:bounded-candidate-comparison-requests`
- add `product/mathematical-analysis-model:bounded-candidate-semantic-and-work-comparison`
- add `product/analysis-report-contract:qualified-candidate-comparison`

## Consequences

Agents can submit two general mathematical formulations once and receive one deterministic semantic-and-work relationship rather than manually correlating independent reports. Named intermediate reuse can participate in cost comparison even when candidates use different internal names, because semantic expansion and work accounting deliberately use different views of the same validated candidate.

The public request, report, generated provider schema, private Pi protocol, compact presentation, and agent guidance all acquire a coordinated comparison variant. Bounds apply across the complete comparison request and combined evidence, not independently per candidate. Unsupported expansion, equivalence, sign reasoning, crossover solving, or opaque cost knowledge produces an inspectable abstention rather than a winner.

The operation retains the existing abstract mathematical-work model. It does not introduce resource vectors, memory or schedule accounting, rewrite generation, parameter optimization, runtime prediction, selectable IEEE 754 semantics, general cross-equation query inlining, or expanded AFMM modeling. Those capabilities require separate decisions if pursued.

## Alternatives Considered

| Alternative | Why not chosen |
|---|---|
| Compare only expressions or self-contained terminal equations | It validates transport and scalar deltas but cannot cover the named reuse patterns that make whole-candidate comparison valuable. |
| Require agents to submit separate semantic expressions alongside cost systems | The duplicated representation could drift, leaving the analyzer to compare semantics that are not tied to the costed computation. |
| Introduce configurable arithmetic profiles and resource vectors first | Those broaden the model substantially and are not required to compare candidates under the already accepted abstract-work semantics. |
| Generate candidate transformations in the same capability | Candidate generation has separate proof, search, numerical-semantics, and resource-model requirements. |

## Status history

- 2026-08-19: Proposed
