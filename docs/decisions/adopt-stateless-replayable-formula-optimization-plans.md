---
format: current-state-v4
slug: adopt-stateless-replayable-formula-optimization-plans
status: Proposed
date: 2026-08-21
---
# ADR-adopt-stateless-replayable-formula-optimization-plans: Adopt stateless replayable formula optimization plans

## Context

ADR-0017 added default-on bounded optimization advice to ordinary analysis. Python independently verifies exact-symbolic equivalence and positive whole-computation aggregate-work savings, while Pi strictly transports a qualified report. The advice deliberately remains separate from submitted interpretation, work, scenarios, and queries.

The current public suggestion is inspectable but not a complete transformed computation. It reports target-local normalized forms, structural occurrence paths, and an optional intermediate expression with binder and output-index names. The verifier retains additional placement and scope information internally when it expands an intermediate for proof and charges its evaluation multiplicity. An agent therefore cannot always take a suggestion unchanged, submit it for ordinary analysis, and compare it with the original. Reconstructing hidden lexical placement from display strings and paths would make the agent reproduce analyzer policy and would violate the desired stateless request-to-result contract.

Self-contained local rewrites such as factoring, redundant-operation removal, and Horner reformulation fit an ordinary expression. Compatible cross-equation or output-index sharing can fit a complete named equation system. Expression-local, `Sum`-local, and inter-iterator reuse or hoisting cannot always be represented faithfully by either form: expanding the intermediate removes the reuse whose saving was proved, while moving it to a global named equation can change scope or evaluation multiplicity. The restricted computation model therefore needs one minimal lexical binding construct, not a general scheduling or source-edit representation.

Agents also need to request optimization explicitly when they want complete candidates, while ordinary analysis must retain ADR-0017's default feedback. Those entry points must share one Python-owned optimizer rather than evolve separate generation, proof, cost, or ranking policies. Their failure semantics differ: optional advice must not destroy an otherwise valid ordinary analysis, whereas failure of a directly requested optimization must be explicit.

## Decision

1. `decision: explicit-stateless-optimization-operation` Python and Pi will accept an explicit bounded optimization operation alongside ADR-0017 ordinary default-on advice.
2. `decision: shared-optimization-policy` The explicit operation and ordinary advice will use the same Python-owned retained computation, candidate generation, verification, cost, deduplication, and ranking policy. Ordinary advice is a compatibility projection of that policy rather than an independent optimizer.
3. `decision: complete-replayable-plans` Every public optimization plan will contain one authoritative complete candidate: the transformed expression or equation system, the declared formula context required to interpret it, and its output identities. This computation-and-context value uses the same public mathematical input contract consumed by ordinary analysis and candidate comparison, so an agent can resubmit it without reconstructing hidden placement, consulting server state, or modifying the candidate. Target-local descriptions may remain only as bounded diagnostics.
4. `decision: minimal-lexical-binding` The restricted project-owned expression model will add one bounded, nonrecursive lexical binding construct with a value expression and a body expression. The value is interpreted in the enclosing lexical and equation-output environment; the fresh binding name is visible only in the body, and generated names and substitutions are capture-avoiding. The value is evaluated once for each evaluation of the construct in that enclosing environment, while references in the body are reuse accesses. Nesting expresses additional bindings, and moving a binding across an aggregate or output scope changes its evaluation multiplicity. The construct is valid both as analyzer input and optimizer output and supports expression-local, aggregate-local, iterator-dependent, output-dependent, and hoisted intermediates without adding a general scheduling IR.
5. `decision: complete-candidate-verification` A generator remains untrusted. Python will verify each complete candidate against the original retained outputs under the declared domains and assumptions and will compare whole-computation aggregate abstract work with binding scope and evaluation multiplicity included. A plan publishes only with qualified proof and positive savings under the selected existing objective; separate plans are not implicitly composable.
6. `decision: operation-specific-failure` Unexpected passive-optimization failure will preserve the valid ordinary base analysis and return a bounded failed optimization diagnostic with no unverified candidate. Failure of the explicit optimization operation will be an explicit typed operation failure. Resource exhaustion remains an incomplete bounded search rather than a failure or evidence that no improvement exists.
7. `decision: backend-independent-transport` Optimization semantics and typed results remain transport-free and Python-owned. Pi will strictly validate, transport, and present the versioned contract without recomputing binding scope, equivalence, work, applicability, ranking, or failure policy.
8. `decision: exact-symbolic-boundary` This decision does not add source spans, stable edit identifiers, patch application, stored optimizer state, code generation, arbitrary rewrite search, composed search, new cost objectives, algorithm replacement, numerical optimization, runtime prediction, hardware modeling, or global optimality. Exact-symbolic equivalence continues not to claim identical finite-precision evaluation or numerical stability.

## State changes

- update `product/product-boundary:symbolic-analysis-only`
- update `product/mathematical-input-contract:safe-familiar-inputs`
- update `product/mathematical-input-contract:compositional-indexed-equation-requests`
- update `product/mathematical-input-contract:bounded-optimization-advice-requests`
- update `product/analysis-report-contract:qualified-optimization-advice`
- update `product/mathematical-analysis-model:bounded-optimization-transformation`

## Consequences

Agents can request optimization when it is their concrete task and receive complete candidates that flow back through the same stateless mathematical interface. Ordinary analysis still supplies bounded advice automatically, so existing agent feedback does not depend on discovering a new operation. One Python policy prevents the passive and explicit surfaces from disagreeing about equivalence, aggregate work, applicability, or ranking.

The lexical binding becomes part of the public restricted computation language and therefore requires explicit parsing, scoping, alpha-renaming, resource bounds, work semantics, rendering, proof expansion, and transport validation. It increases the input and result surface, but confines that growth to the missing semantic concept instead of introducing source-edit or scheduling machinery. Ordinary expressions and equation systems remain the simpler representations whenever they are sufficient.

Complete plans and repeated mathematical context increase report size. Existing whole-request, proof, transformation, and output bounds must be extended deliberately so a valid base analysis remains bounded. Returning a candidate that can be reanalysed does not mean it can be pasted into arbitrary source code, and the operation still promises only independently proved improvements found within its configured search bounds.

The public union and computation language require a new versioned protocol contract. Its implementation and rollout belong to the implementation plan. Later objective models, composed search, and exact algorithmic transformations gain a stable complete-state boundary, but remain separate decisions and are not authorized here.

## Alternatives Considered

| Alternative | Why not chosen |
|---|---|
| Keep display-oriented ordinary advice only | Agents would still have to reconstruct complete computations and could not reliably replay plans. |
| Replace ordinary advice with a required explicit operation | This reverses ADR-0017's default-feedback goal and would make agents miss available proved improvements. |
| Return the intermediate expanded into an ordinary expression | Expansion is semantically replayable but erases the retained reuse and its proved work saving. |
| Materialize every intermediate as a named equation | It works for global and output-index sharing but cannot preserve every lexical or iterator-local placement and multiplicity. |
| Return source spans, structural edit identities, or stateful plan handles | These solve source application rather than mathematical replay, couple plans to stored or submitted representation identity, and are unnecessary when the complete candidate is returned. |
| Adopt a general computation or scheduling IR | Map, reduce, stage, recurrence, materialization, and scheduling semantics are broader than the single missing lexical-binding concept. |
| Implement a separate optimizer for the explicit operation | Duplicate policies could disagree about proof, cost, ranking, bounds, and qualifications. |

## Status history

- 2026-08-21: Proposed
