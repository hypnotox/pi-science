---
format: current-state-v4
slug: adopt-bounded-formula-optimization-advice
status: Implementing
date: 2026-08-20
---
# ADR-0017: Adopt bounded formula optimization advice

## Context

pi-science reports retained-formula work, dependencies, ideal reuse, repeated-expression extraction diagnostics, bounded mathematical queries, candidate comparison, and one-axis aggregate-work dominance. These results help an agent understand a formula, but ordinary analysis does not yet turn detected structure into a proved lower-work reformulation. Agents must independently discover, validate, and assess improvements even when the analyzer already owns the relevant mathematical model.

The existing extraction diagnostic is system-local and does not claim a rewrite, equivalence, or improvement. Candidate comparison and query evaluation already establish the required policy boundaries: Python owns bounded mathematical verification, assumptions, and aggregate abstract work, while Pi strictly transports and presents qualified results. Generated advice must reuse those boundaries without changing the submitted interpretation, work, scenarios, or query conclusions.

A useful optimization claim must mean lower whole-computation aggregate abstract work over the declared domains, not fewer local syntax nodes or predicted runtime. Iterator cardinality, equation output multiplicity, named-result reuse, primitive costs, assumptions, and unknown costs can all change that conclusion. Algebraic reassociation can also change finite-precision evaluation even when exact-symbolic equivalence is proved.

Default advice introduces search and output costs. Independent bounds and qualified truncation are required so optimization cannot make an otherwise valid analysis fail or imply that a bounded search established global optimality.

Cross-equation sharing is one atomic suggestion with changes in several equation right-hand sides. A singular suggestion target and target-less occurrence paths cannot identify every affected equation, and positional interfaces may use different local index names. The public report therefore needs target-local transformations rather than a primary-target convention.

## Decision

1. `decision: default-bounded-advice` Ordinary expression and equation-system analysis includes informational optimization advice by default. The strict request field `optimization.max_suggestions` defaults to 3, accepts 0 to disable advice, accepts positive integers through 16, and requests an upper bound rather than a guaranteed count. Candidate-comparison and dominance requests remain unchanged.
2. `decision: initial-proved-families` The initial bounded families are repeated-subexpression extraction, iterator-invariant hoisting, repeated-call and reciprocal reuse, safe factoring and redundant-operation removal, compatible sharing across named equations, and Horner-form polynomial reformulation. Horner and every other family publishes only candidates that reduce the adopted work metric; no family implies exhaustive rewrite search.
3. `decision: python-owned-proof-and-ranking` Python owns candidate generation, exact-symbolic equivalence verification, assumption qualification, whole-computation aggregate-work comparison, deduplication, and ranking. A suggestion publishes only when equivalence and positive aggregate-work reduction are proved over the declared domains. Unknown-cost candidates do not qualify. Unconditional suggestions precede assumption-dependent suggestions; incomparable savings use deterministic ordering without a superiority claim.
4. `decision: qualified-informational-results` Each suggestion contains one or more target-local transformations. Every transformation identifies its expression or named-equation target, normalized original and proposed forms, and deterministic structural occurrence paths with crossed binders or output domains. Targets are unique within a suggestion; single-target families carry one transformation, while cross-equation sharing carries one for every affected equation, including renamed positional interfaces. A generated intermediate, checked evidence, conditions, whole-computation aggregate work before and after, and the delta remain suggestion-level because they qualify the transformation set atomically. Protocol v12 carries this strict shape. Reassociation carries an exact-symbolic-only finite-precision qualification. Suggestions never replace or feed the submitted interpretation, ordinary work, scenarios, or query results.
5. `decision: independently-bounded-search` Inspection, candidate generation, transformation size, proof work, work comparison, and rendered advice have independent deterministic bounds. Exhaustion preserves the base analysis, returns any already-proved suggestions that fit, and explicitly states that optimization search was incomplete. It never means that no improvement exists.
6. `decision: backend-independent-policy` Optimization policy and typed results remain transport-free in `py-science-formula`. Pi carries the strict request and report, renders compact advice, and does not recompute equivalence, assumptions, work, ranking, or applicability.

## State changes

- update `product/product-boundary:symbolic-analysis-only`
- add `product/mathematical-input-contract:bounded-optimization-advice-requests`
- add `product/analysis-report-contract:qualified-optimization-advice`
- add `product/mathematical-analysis-model:bounded-optimization-transformation`

## Consequences

Agents receive a small set of actionable, verified improvements without having to request a separate comparison or infer that a structural diagnostic is beneficial. Expressions and systems share one qualified advice contract, while equation domains and lexical sum scope remain part of the work proof. Multi-equation suggestions identify every target-local change without weakening their atomic proof or work claim.

Protocol v12 is an incompatible report-shape migration: Python and Pi models, generated schema, strict validation, rendering, fixtures, and consumers must move atomically to target-local transformations, and protocol v11 optimization payloads are not valid protocol v12 payloads.

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
| Keep a singular primary target and add target identities only to occurrences | Other equations would still lack explicit original and proposed forms, leaving cross-equation advice less actionable and preserving a misleading primary-target convention. |
| Publish each affected equation edit as a separate suggestion | The edits are not independently applicable or independently proved improvements; splitting them would lose the atomic equivalence and whole-computation work claim. |
| Restrict sharing to identical index names or one equation | This would exclude compatible positional interfaces and contradict the approved cross-equation family. |

## Status history

- 2026-08-20: Proposed
- 2026-08-20: Accepted; content-sha256: 16e353a8fc2ec9b1ed92af5ce4c00fd4c0c46fa176db4fc633773d87a9a63c71
- 2026-08-20: Implementing; content-sha256: 16e353a8fc2ec9b1ed92af5ce4c00fd4c0c46fa176db4fc633773d87a9a63c71
- 2026-08-20: Applied; operations: update `product/product-boundary:symbolic-analysis-only`, add `product/mathematical-input-contract:bounded-optimization-advice-requests`, add `product/analysis-report-contract:qualified-optimization-advice`, add `product/mathematical-analysis-model:bounded-optimization-transformation`
- 2026-08-20: Reapplied; operations: update `product/product-boundary:symbolic-analysis-only`, add `product/mathematical-analysis-model:bounded-optimization-transformation`
- 2026-08-21: Amended; content-sha256: 5ada01f2f781a9ea5d49331da7b42e5443c85adc7ed43913cc148bb9dcd15e9f
- 2026-08-21: Amended; content-sha256: 8614abf356beff2fd1024c27d0c6474eda9564e8d4629c17b6210a1d72d6749a
- 2026-08-21: Reapplied; operations: add `product/analysis-report-contract:qualified-optimization-advice`, add `product/mathematical-analysis-model:bounded-optimization-transformation`
