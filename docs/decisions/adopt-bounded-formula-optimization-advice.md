---
format: current-state-v4
slug: adopt-bounded-formula-optimization-advice
status: Implementing
date: 2026-08-20
---
# ADR-adopt-bounded-formula-optimization-advice: Adopt bounded formula optimization advice

## Context

pi-science reports retained-formula work, dependencies, ideal reuse, repeated-expression extraction diagnostics, bounded mathematical queries, candidate comparison, and one-axis aggregate-work dominance. These results help an agent understand a formula, but ordinary analysis does not yet turn detected structure into a proved lower-work reformulation. Agents must independently discover, validate, and assess improvements even when the analyzer already owns the relevant mathematical model.

The existing extraction diagnostic is system-local and does not claim a rewrite, equivalence, or improvement. Candidate comparison and query evaluation already establish the required policy boundaries: Python owns bounded mathematical verification, assumptions, and aggregate abstract work, while Pi strictly transports and presents qualified results. Generated advice must reuse those boundaries without changing the submitted interpretation, work, scenarios, or query conclusions.

A useful optimization claim must mean lower whole-computation aggregate abstract work over the declared domains, not fewer local syntax nodes or predicted runtime. Iterator cardinality, equation output multiplicity, named-result reuse, primitive costs, assumptions, and unknown costs can all change that conclusion. Algebraic reassociation can also change finite-precision evaluation even when exact-symbolic equivalence is proved.

Default advice introduces search and output costs. Independent bounds and qualified truncation are required so optimization cannot make an otherwise valid analysis fail or imply that a bounded search established global optimality.

## Decision

1. `decision: default-bounded-advice` Ordinary expression and equation-system analysis includes informational optimization advice by default. The strict request field `optimization.max_suggestions` defaults to 3, accepts 0 to disable advice, accepts positive integers through 16, and requests an upper bound rather than a guaranteed count. Candidate-comparison and dominance requests remain unchanged.
2. `decision: initial-proved-families` The initial bounded families are repeated-subexpression extraction, iterator-invariant hoisting, repeated-call and reciprocal reuse, safe factoring and redundant-operation removal, compatible sharing across named equations, and Horner-form polynomial reformulation. Horner and every other family publishes only candidates that reduce the adopted work metric; no family implies exhaustive rewrite search.
3. `decision: python-owned-proof-and-ranking` Python owns candidate generation, exact-symbolic equivalence verification, assumption qualification, whole-computation aggregate-work comparison, deduplication, and ranking. A suggestion publishes only when equivalence and positive aggregate-work reduction are proved over the declared domains. Unknown-cost candidates do not qualify. Unconditional suggestions precede assumption-dependent suggestions; incomparable savings use deterministic ordering without a superiority claim.
4. `decision: qualified-informational-results` Each suggestion identifies its expression or equation target, normalized subexpression, deterministic structural occurrence paths, crossed binders or output domains, proposed replacement or named intermediate, checked evidence, conditions, aggregate work before and after, and the delta. Reassociation carries an exact-symbolic-only finite-precision qualification. Suggestions never replace or feed the submitted interpretation, ordinary work, scenarios, or query results.
5. `decision: independently-bounded-search` Inspection, candidate generation, transformation size, proof work, work comparison, and rendered advice have independent deterministic bounds. Exhaustion preserves the base analysis, returns any already-proved suggestions that fit, and explicitly states that optimization search was incomplete. It never means that no improvement exists.
6. `decision: backend-independent-policy` Optimization policy and typed results remain transport-free in `py-science-formula`. Pi carries the strict request and report, renders compact advice, and does not recompute equivalence, assumptions, work, ranking, or applicability.

## State changes

- update `product/product-boundary:symbolic-analysis-only`
- add `product/mathematical-input-contract:bounded-optimization-advice-requests`
- add `product/analysis-report-contract:qualified-optimization-advice`
- add `product/mathematical-analysis-model:bounded-optimization-transformation`

## Consequences

Agents receive a small set of actionable, verified improvements without having to request a separate comparison or infer that a structural diagnostic is beneficial. Expressions and systems share one qualified advice contract, while equation domains and lexical sum scope remain part of the work proof.

The analyzer becomes more expensive and its report surface grows. Independent budgets, deterministic truncation, and the request-level disable control confine that cost. The base analysis remains valid when advice is partial or absent.

A typed occurrence and scope model, capture-safe generated-candidate evaluation, and reusable equivalence and aggregate-work comparison seams become necessary. Existing repeated-expression diagnostics must derive from the shared detector or otherwise remain explicitly compatible so two policies cannot contradict each other.

The decision does not add arbitrary rewrite search, approximation, numerical-stability analysis, runtime prediction, hardware modeling, formula execution, global optimality, or algorithm replacement. Exact-symbolic proof does not establish identical finite-precision evaluation.

## Alternatives Considered

| Alternative | Why not chosen |
|---|---|
| Keep diagnostics only | It identifies possible repetition but leaves equivalence, placement, and work improvement unproved. |
| Require an explicit optimization query | Agents could miss a proven better variant, contrary to the default feedback goal. |
| Generate unrestricted backend rewrites | Backend search is difficult to bound and cannot define project proof, qualification, or ranking policy. |
| Rank local node-count reductions | Local syntax size ignores iterator cardinality, equation multiplicity, reuse, and opaque work. |
| Include algorithmic or approximate reformulations | They require numerical, semantic, or performance contracts outside the approved exact-symbolic slice. |

## Status history

- 2026-08-20: Proposed
- 2026-08-20: Accepted; content-sha256: 16e353a8fc2ec9b1ed92af5ce4c00fd4c0c46fa176db4fc633773d87a9a63c71
- 2026-08-20: Implementing; content-sha256: 16e353a8fc2ec9b1ed92af5ce4c00fd4c0c46fa176db4fc633773d87a9a63c71
- 2026-08-20: Applied; operations: update `product/product-boundary:symbolic-analysis-only`, add `product/mathematical-input-contract:bounded-optimization-advice-requests`, add `product/analysis-report-contract:qualified-optimization-advice`, add `product/mathematical-analysis-model:bounded-optimization-transformation`
