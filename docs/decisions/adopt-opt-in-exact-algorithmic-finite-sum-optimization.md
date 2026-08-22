---
format: current-state-v4
slug: adopt-opt-in-exact-algorithmic-finite-sum-optimization
status: Implementing
date: 2026-08-22
---
# ADR-adopt-opt-in-exact-algorithmic-finite-sum-optimization: Adopt opt-in exact algorithmic finite-sum optimization

## Context

ADR-0012 established a bounded, independently verified closed-form query for one unique nested finite-polynomial `Sum` tree. Its result is deliberately informational: it does not replace submitted work, claim an implementation, or participate in optimization. ADR-0018 later made optimization results complete stateless computations, ADR-0019 gave them exact objective provenance, and ADR-0020 added deterministic bounded composition. Those records leave algorithm replacement explicitly outside the eight shipped algebraic and reuse families.

A checked finite closed form can nevertheless reduce represented evaluation work. Returning it only as a query candidate makes an agent reconstruct a computation and infer whether replacement is beneficial. Automatically adding it to ordinary advice would instead cross an algorithmic boundary for every caller and could let later families become enabled through a broad tier switch. The product needs a narrow opt-in whose absence preserves the existing algebraic population.

The query envelope itself is not an optimization proof. Its derived candidate lacks the complete replay context and selected-objective comparison, while the ordinary rational-equivalence verifier cannot prove a `Sum` equal to its polynomial closed form. Algorithmic optimization therefore needs to share the checked finite-sum mathematics without treating query output or backend generation as independent evidence. Every published result must still replay as an ordinary complete computation, prove each transition and the original-to-final result, and reduce whole-computation exact symbolic work.

This first algorithmic tier must not become a general aggregate representation. The already bounded ADR-0012 family supplies the needed applicability, antidifference, boundary, range, degree, topology, and resource rules. Infinite series, arbitrary inner-subtree selection, depth-one polynomial widening, approximation, recurrence or stage models, and runtime claims require separate decisions.

## Decision

1. `decision: explicit-exact-transformation-tiers` Optimization transformations will have two explicit provenance tiers: `exact_algebraic_v1` for the existing eight algebraic and reuse families and `exact_algorithmic_v1` for separately approved exact algorithm replacements. Every trace step and the plan's summary suggestion will carry its tier, each family will have one schema-enforced tier, and the summary tier will equal the final trace step tier. Tier is qualification and provenance, not a computation IR, runtime model, or request-wide enablement switch.
2. `decision: family-specific-algorithmic-opt-in` Ordinary optimization configuration and direct optimize requests will accept `enabled_algorithmic_families`, a strictly unique canonically ordered bounded list that defaults to empty and initially accepts only `finite_polynomial_sum_v1`. The existing algebraic families remain enabled as before. Algorithmic families require their own later approval and cannot become active through a broad tier toggle. This analysis-only control will not appear in replay candidates.
3. `decision: bounded-nested-finite-sum-family` The first exact-algorithmic family will replace only the unique maximal nested finite-polynomial `Sum` tree supported by ADR-0012, at its structural location within the preserved expression or equation shell. It will retain ADR-0012's finite-range, affine-integral, rational-polynomial, topology, degree, capture, proof, and resource boundary. It will not select arbitrary inner sums or widen the accepted closed-form family.
4. `decision: independently-verified-algorithmic-identities` Query evaluation and optimization may share one project-owned checked finite-sum derivation boundary, but neither a query answer nor backend-generated candidate will count as optimizer proof. An enabled transition will independently verify the antidifference and inclusive boundaries against its replayed parent and child. Final acceptance will independently verify every retained algorithmic identity from the original computation to the final state before applying the common exact equivalence and objective policy. The resulting proof conditions and assumption uses will qualify the published transition and final result.
5. `decision: complete-positive-algorithmic-plans` A finite-sum replacement will enter optimization only as a complete candidate accepted unchanged by ordinary analysis. It will preserve the computation's mathematical context and output identities, and publish only when Python proves a strictly positive reduction under the selected exact objective over the whole computation, including finite aggregate work, enclosing scope, and output-domain multiplicity. The candidate's computation and context remain usable through the existing explicit candidate-comparison wrapper; this decision adds no comparison shortcut.
6. `decision: composed-opt-in-algorithmic-search` When explicitly enabled, the finite-sum lane will participate in the existing canonical fair depth-two search, state deduplication, fixed resource accounting, original-to-final acceptance, ranking, and output-prefix policy. A trace may mix exact-algebraic and exact-algorithmic steps only when every parent-relative transition and the final result independently satisfy their proof, qualification, and positive-objective contracts. With no enabled algorithmic family, the existing algebraic search population and policy remain unchanged.
7. `decision: silent-ineligibility-and-analysis-separation` Unsupported, infinite, unresolved, incompatible, or nonpositive finite-sum proposals will publish no algorithmic plan and will not add a family-specific refusal diagnostic. Query answers, submitted work, scenarios, comparison, dominance, and ordinary interpretation remain independent and unchanged. A caller may request a closed-form query and algorithmic optimization together, but neither surface supplies or mutates the other's result.
8. `decision: backend-independent-v16-algorithmic-transport` The strict public surface will migrate atomically to protocol v16. Python will own opt-in applicability, tier and family policy, derivation, replay, proof, objective comparison, composition, deduplication, ranking, and qualification. Pi will strictly correlate and present the request, tier, family, trace, candidate, proof, objective, and status fields without applying transformations or recomputing mathematical policy. Exact symbolic replacement will not claim finite-precision equivalence, numerical stability, runtime improvement, or empirical performance.
9. `decision: exact-algorithmic-v1-boundary` This decision does not add infinite-series replacement, depth-one polynomial-sum widening, arbitrary inner-subtree replacement, unapproved aggregate or algorithmic families, approximation, a general map/reduce/stage/recurrence representation, source rewriting, code generation, target-specific costs, scheduling, storage, or runtime claims.

## State changes

- update `product/product-boundary:symbolic-analysis-only`
- update `product/mathematical-input-contract:bounded-optimization-advice-requests`
- update `product/mathematical-analysis-model:bounded-optimization-transformation`
- update `product/analysis-report-contract:qualified-optimization-advice`

## Consequences

Agents can opt into a proved finite-sum algorithm replacement and receive the same complete replay, comparison compatibility, exact objective evidence, and bounded trace structure as existing optimization plans. Explicit family selection prevents a future algorithmic family from silently entering ordinary advice, while explicit per-step tiers make mixed traces understandable without creating a general transformation language.

Sharing the checked derivation boundary avoids duplicating bounded summation mathematics, but makes query and optimizer behavior depend on one internal contract and adds a new optimizer proof mode beyond rational expression equivalence. Query-parity regressions must protect ADR-0012 behavior while optimizer proof remains independently rerun. The final verifier must account for every algorithmic identity in a mixed trace; a parent-relative certificate alone remains insufficient. Preserving the surrounding shell keeps structural paths, later algebraic opportunities, and caller computation shape stable.

Eligible closed forms are not automatically good optimizations. Symbolic range or work comparisons may be unresolved or nonpositive, so opt-in can still yield no algorithmic plan without a new diagnostic. Fixed sufficiently large bounds or adequate assumptions can prove positive savings, while ordinary work and query reports remain descriptions of the submitted computation rather than the replacement.

Protocol v16 changes Python models, generated schema, adapter, strict Pi validation, rendering, tests, skills, and current documentation atomically. Existing requests remain mathematically unchanged when the new list is absent or empty, but strict protocol consumers must migrate to the new version and tier-bearing result shape.

## Alternatives Considered

| Alternative | Why not chosen |
|---|---|
| Keep finite closed forms query-only | Agents would have to reconstruct complete candidates and could not rely on verified whole-computation savings. |
| Enable algorithmic replacement by default | It would change ordinary advice across an intentionally separate algorithmic boundary. |
| Use one broad algorithmic-tier toggle | A later family could become enabled without explicit caller selection or family-specific approval. |
| Infer tier only from family kind | Mixed traces would lack explicit caller-facing tier provenance and require external mapping knowledge. |
| Treat the query candidate as optimizer proof | Query evidence is not a complete replay proof or whole-computation objective comparison. |
| Consume the query-result envelope only as an untrusted proposal generator | It would couple optimization to an informational public envelope instead of the approved shared checked derivation contract, while still requiring an independent optimizer proof. |
| Optimize arbitrary finite `Sum` subtrees | It exceeds ADR-0012's maximal-tree and binder-context contract. |
| Return a family-specific refusal for every rejected proposal | Existing optimization policy silently omits candidate-local failures; a new diagnostic contract is unnecessary for the initial family. |
| Introduce a general aggregate or algorithm IR | The bounded finite-sum replacement needs no map/reduce/stage/recurrence model. |

## Status history

- 2026-08-22: Proposed
- 2026-08-22: Implementing; content-sha256: fe2c328463f1683983dd3fc813172d8c9bff492bf3f05cae6335bddac7e60134
- 2026-08-22: Applied; operations: update `product/product-boundary:symbolic-analysis-only`, update `product/mathematical-input-contract:bounded-optimization-advice-requests`, update `product/mathematical-analysis-model:bounded-optimization-transformation`, update `product/analysis-report-contract:qualified-optimization-advice`
