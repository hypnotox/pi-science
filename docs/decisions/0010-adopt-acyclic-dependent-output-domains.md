---
format: current-state-v4
slug: adopt-acyclic-dependent-output-domains
status: Implemented
date: 2026-08-18
---
# ADR-0010: Adopt acyclic dependent output domains

## Context

ADR-0003 introduced equation-local output domains but deliberately required their bounds to be independent of every output index. That rule admits rectangular grids but rejects common finite scientific iteration spaces such as triangular coefficients, simplex traversals, and ragged tensor regions. Callers must currently split one indexed equation into many scalar requests or submit a rectangular superset and correct its work externally. Both approaches obscure the computation that the analyzer is meant to inspect.

Dependent bounds introduce scope and reasoning questions that independent mappings avoid. LHS index order is part of the mathematical identity of an indexed result, so requiring users to reorder it merely to satisfy iteration dependencies can transpose the stated quantity. Treating every bound as mutually visible instead permits cycles and leaves evaluation order ambiguous. General constraint solving or unrestricted SymPy delegation would also violate the product's deterministic bounded-analysis policy.

The implementation already separates safely parsed expressions, free-symbol validation, work aggregation, relationship reasoning, scenario substitution, and rendering. A dependent-domain model must give those consumers one deterministic dependency meaning, preserve exact qualification and provenance, and remain general rather than embedding harmonic or FMM concepts. Nested mathematical closed forms, polynomial summation, absolute-value semantics, complex scalars, exponent normalization, and loop-invariant transformation analysis are separate bounded capability families. The confirmed nested direct-work binder leak is likewise a correctness repair under ADR-0003, not a reason for this decision.

## Decision

1. `decision: acyclic-dependent-output-domains` An equation's local output-domain bounds may reference other output indices. The analyzer infers directed dependencies from those references, rejects cycles and self-dependence, and evaluates the resulting finite domain in a deterministic topological order. Independent output domains remain valid.
2. `decision: preserve-mathematical-index-order` LHS index order continues to define the indexed result's mathematical coordinate order and is not changed to satisfy domain dependencies. When several output indices are simultaneously eligible in the dependency order, their LHS order is the deterministic tie-break.
3. `decision: bounded-relational-domain-reasoning` Dependent-domain acceptance, cardinality, aggregate direct work, and scenario specialization use one bounded affine-integer reasoning family. A dependent bound may contain integer constants and finite sums of integer multiples of declared integer variables or output indices, but not calls, indexed values, powers, products between symbolic terms, division, or submitted aggregate operators. Reasoning may use intrinsic integer and sign domains, supported equality or directed-definition substitution, normalized submitted affine equalities and inequalities, and the inclusive lower/upper facts of output indices already available in dependency order. It may normalize and compare affine differences only within explicit request and reasoning budgets, and every relationship used retains provenance. A cycle, self-dependence, or dependent bound outside this grammar is a request error; a valid in-family analysis whose finiteness, ordering, sign, or bound-index elimination cannot be proved remains qualified or unresolved. Independent bounds retain their existing accepted expression family. No case is delegated to unrestricted symbolic reasoning.

## State changes

- update `product/mathematical-input-contract:compositional-indexed-equation-requests`
- update `product/mathematical-analysis-model:ideal-equation-dependency-work`
- update `product/analysis-report-contract:provenance-preserving-system-work`

## Consequences

Agents can state triangular, simplex-like, and other acyclic affine finite output spaces directly without transposing indexed results or padding them into rectangular supersets. Domain validation, cardinality, work aggregation, and scenario results share one dependency interpretation, and harmonic/M2L formulas become a demanding acceptance case for general scientific semantics rather than a special API.

Requests become stricter in a different dimension: dependency cycles, self-reference, and dependent bounds outside the affine grammar are invalid. Accepted affine requests can still yield qualified or unresolved analysis when the bounded reasoner cannot establish finiteness, ordering, sign, or complete aggregation. Topological evaluation and relational provenance add implementation complexity across validation, work, scenarios, and reports, but deterministic ordering and explicit qualification keep that complexity inspectable. Supporting dependent output domains does not imply general polyhedral analysis, arbitrary constraint solving, nested closed forms, absolute-value reasoning, complex mathematics, or automatic loop transformation.

The Python contract remains the owner of mathematical policy. Pi must carry any affected strict schema and qualified report shape without independently interpreting dependency or constraint semantics, and its formula-analysis skill and current-state documentation must describe the same supported boundary.

## Alternatives Considered

Inferring a bounded dependency graph costs more cross-cutting validation, aggregation, provenance, and reporting work than preserving independent domains, while intentionally covering less than a nonlinear or general polyhedral solver. That cost is accepted to keep natural affine scientific domains both reusable and deterministic.

| Alternative | Why not chosen |
|---|---|
| Keep output domains independent | Callers must fragment natural equations or overcount rectangular supersets. |
| Use LHS order as mandatory lexical binding order | It forces some callers to transpose the mathematical indexing convention merely to express an acyclic dependency. |
| Require explicit dependency or binding-order metadata | It duplicates relationships already present in the bounds, burdens callers, and can drift from the submitted mathematics. |
| Make all output-domain indices mutually visible | Cycles and evaluation order become ambiguous, weakening deterministic validation. |
| Delegate arbitrary constraints to SymPy | Backend behavior and resource use would define public policy instead of an auditable bounded family. |
| Add harmonic- or FMM-specific triangular domains | It would solve one workload by narrowing a deliberately reusable scientific tool. |

## Status history

- 2026-08-18: Proposed
- 2026-08-18: Accepted; content-sha256: 06938c0953bf78f9def41acfb21d4a86891c35dba07ec24c802e05e94c053fd9
- 2026-08-18: Implementing; content-sha256: 06938c0953bf78f9def41acfb21d4a86891c35dba07ec24c802e05e94c053fd9
- 2026-08-18: Applied; operations: update `product/mathematical-input-contract:compositional-indexed-equation-requests`, update `product/mathematical-analysis-model:ideal-equation-dependency-work`, update `product/analysis-report-contract:provenance-preserving-system-work`
- 2026-08-18: Implemented; content-sha256: 06938c0953bf78f9def41acfb21d4a86891c35dba07ec24c802e05e94c053fd9
