---
format: current-state-v4
slug: adopt-deterministic-bounded-composed-optimization-search
status: Implementing
date: 2026-08-22
---
# ADR-adopt-deterministic-bounded-composed-optimization-search: Adopt deterministic bounded composed optimization search

## Context

ADR-0018 made every optimization result a complete stateless computation that ordinary analysis can replay, but deliberately left separate plans noncomposable. ADR-0019 added exact objective selection and qualified ranking while retaining that one-step search boundary. The optimizer therefore verifies each generated proposal against the submitted computation and returns independent final candidates; it cannot discover an improvement that requires applying one supported family after another.

Naively feeding accepted candidates back into generation would make results depend on traversal and family registration order. The existing internal candidate key describes one local proposal rather than a canonical complete computation, generated intermediates can change the target set seen by a later step, and equal final computations can arrive through different histories. Fixed resource ceilings would then amplify incidental discovery order into public result differences.

A composed result also does not fit the existing single-family suggestion shape. A final candidate alone is replayable but does not explain its ordered supported transformations, while Pi cannot safely reconstruct intermediate placement or optimizer semantics from target-local edits. The public model needs bounded complete step states without moving mathematical policy out of Python.

The first search tier must remain smaller than a general rewrite system. Existing built-in families, complete-candidate replay, exact equivalence verification, selected-objective projection, and qualified final ordering are sufficient for monotonic depth-two composition. Neutral or temporarily worse setup steps, unrestricted backend rewriting, plugins, new objectives, and global optimality require separate decisions.

## Decision

1. `decision: monotonic-depth-two-composed-search` Optimization will use deterministic breadth-first search rooted at the submitted computation, with at most two accepted transitions. The root is not a result. Every transition must ordinary-replay successfully, be independently exact-symbolically equivalent to its parent under compatible conditions, and strictly reduce the selected objective relative to that parent. Neutral or temporarily worse transitions are not search states.
2. `decision: canonical-complete-search-states` Python will deduplicate and schedule complete computation states through a project-owned canonical semantic key. The key capture-avoidably normalizes lexical, aggregate, and output-index binders and equation order across the full candidate context while preserving outputs, dependencies, domains, constraints, assumptions, definitions, functions, variables, and primitive costs. Analysis-only controls, objective selection, and transformation history are not state semantics.
3. `decision: caller-order-and-state-identity` Canonicalization governs search only. Returned computations preserve caller-facing equation order, and public candidate identity remains a function only of the returned complete candidate. Requests that differ only by equation order must produce equivalent discovery, deduplication, and ranking, but need not produce byte-identical candidates or identities.
4. `decision: deterministic-fair-state-scheduling` Each depth will schedule stable built-in family lanes across canonical parent states in deterministic round-robin order. Family registration order, traversal order, and arrival order will not select the retained population: transitions within each lane and concrete representatives of equal canonical states use stable semantic ordering, and one state retains the shortest then deterministically least trace before expansion.
5. `decision: explicit-composed-search-bounds` Search will enforce fixed per-depth allowances and whole-request ceilings over canonical states, expanded parents, generated transitions, complete reanalyses, proofs, proof nodes, transformation nodes, and work-comparison nodes. Per-depth allocation preserves a bounded opportunity to explore depth two. Exhaustion produces a typed incomplete-search qualification and never proves that no further improvement exists.
6. `decision: output-limit-independent-search` The requested plan count limits only the ranked returned prefix. It does not stop or otherwise change search. Serialized-output enforcement is a post-search projection bound with its own truncation status and bounded diagnostics; it neither changes discovery and ranking nor erases search-exhaustion evidence.
7. `decision: direct-original-to-final-acceptance` A retained final state will reuse its successful transition replay but receive an additional direct original-to-final equivalence proof and selected-objective comparison. Public plan conclusion, conditions, assumptions, and objective before, after, and savings describe that original-to-final result; a chain of parent-relative proofs alone is insufficient.
8. `decision: replayable-composed-transformation-traces` Every public plan will carry an ordered trace of one or two steps. Each step carries its built-in family, target-local transformations, optional intermediate, step-local proof qualification and objective evidence, complete post-step candidate, and candidate identity. The first parent is the submitted computation, each later parent is the preceding step candidate, and the plan final candidate and identity equal the last step state. Equal canonical finals reached by different histories collapse to the deterministic retained trace.
9. `decision: backend-independent-v15-search-transport` Python will own canonicalization, generation, scheduling, replay, proof, objective comparison, deduplication, trace choice, ranking, and search and projection qualifications. Pi will atomically migrate to protocol v15 and strictly correlate and present original, parent, step, final, objective, status, and qualification fields without applying transformations or recomputing mathematical policy. Ordinary advice and direct optimization will expose the same plans, and existing one-step results will use one-step traces.
10. `decision: composed-search-v1-boundary` This decision does not add transformation families, a general rewrite IR, plugins, nonmonotonic setup steps, configurable depth or search budgets, new objective dimensions, approximation, numerical or runtime claims, unrestricted backend rewriting, or local or global optimality. Existing exact-symbolic, finite-precision, passive/direct failure, and ordinary-analysis boundaries remain in force.

## State changes

- update `product/product-boundary:symbolic-analysis-only`
- update `product/mathematical-input-contract:bounded-optimization-advice-requests`
- update `product/mathematical-analysis-model:bounded-optimization-transformation`
- update `product/analysis-report-contract:qualified-optimization-advice`

## Consequences

Agents can receive a directly replayable result that combines two supported improvements and inspect every verified intermediate state. Because each trace state is complete, later steps may target a generated intermediate without hidden placement reconstruction, and Pi can validate parent-child correlation without interpreting an edit language.

Canonical complete-state ownership and fair scheduling make bounded results reproducible across family registration, alpha-renaming, equation traversal, and duplicate histories. That guarantee requires a new whole-computation canonicalization boundary and deterministic transition ordering rather than reuse of the current local-proposal key. Caller order remains stable in returned computations, so semantic invariance deliberately does not imply cross-request byte identity.

Monotonic steps and fixed depth keep the state space and proof obligations bounded and reuse the shipped families' positive-improvement contract. They also miss optimizations that require a neutral or worse intermediate, more than two transformations, or an unsupported family. Search exhaustion remains visible rather than being mistaken for evidence of completeness or optimality.

Complete intermediate candidates increase protocol payload size. The bounded trace depth and separate post-search projection limit contain that cost, while distinct search and projection qualifications prevent byte trimming from obscuring mathematical search exhaustion. Protocol v15 requires an atomic Python, schema, adapter, Pi validation, presentation, test, skill, and documentation migration.

## Alternatives Considered

| Alternative | Why not chosen |
|---|---|
| Keep independent one-step plans | It cannot find improvements that require composing supported families. |
| Return only the final candidate | It hides the supported transformation path and cannot correlate generated intermediate targets without reconstruction. |
| Publish target-local edits without complete step states | Pi or callers would need to apply placement-sensitive edits and recreate optimizer semantics. |
| Include trace or objective in candidate identity | The same final computation would acquire different mathematical identities from search history or analysis policy. |
| Canonicalize caller-facing equation order | It would change the established complete-candidate replay and identity contract solely to obtain search invariance. |
| Stop after filling the requested result count | Discovery order could suppress a better depth-two final and make the request limit alter search policy. |
| Allow neutral or worsening setup transitions | It broadens the initial state space and objective semantics beyond the bounded monotonic tier. |
| Adopt a general rewrite graph or equality-saturation engine | It adds representation, scheduling, and optimality scope not required for depth-two composition of built-in families. |

## Status history

- 2026-08-22: Proposed
- 2026-08-22: Implementing; content-sha256: b2753adb237d28bb70561ef7a093b66262f0e38720834c658dc7f829fffcfce9
- 2026-08-22: Applied; operations: update `product/product-boundary:symbolic-analysis-only`, update `product/mathematical-input-contract:bounded-optimization-advice-requests`, update `product/mathematical-analysis-model:bounded-optimization-transformation`, update `product/analysis-report-contract:qualified-optimization-advice`
