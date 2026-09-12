---
paths:
  - 'docs/analysis-model.md'
  - 'packages/py-science-formula/src/py_science/formula/contracts/**'
  - 'packages/py-science-formula/src/py_science/formula/_service/result_bounds.py'
  - 'packages/pi-science/src/bridge/correlation.ts'
  - 'packages/pi-science/src/bridge/presentation.ts'
  - 'packages/pi-science/src/bridge/protocol.ts'
  - 'packages/pi-science/src/bridge/results.ts'
  - 'packages/pi-science/src/formula-schema.json'
  - 'packages/pi-science/skills/formula-analysis/SKILL.md'
---

# Analysis report contract

Every analysis reports the normalized interpretation actually analyzed and distinguishes exact results, assumption-dependent results, conservative bounds, and unresolved quantities. System reports may identify repeated-expression extraction diagnostics without claiming a rewrite or improvement. The analyzer never silently fixes a scaling variable, invents an unknown cost, or presents sampling as a mathematical bound.

## System work provenance

Direct Python system reports preserve exact general symbolic work and identify every supported equality, directed definition, submitted affine relationship, predecessor-domain fact, and equation-qualified local constraint used in deterministic specialization and dependent-domain aggregation. Submitted constraints, normalized effective domains, and constraint uses remain separate inspectable fields. Fixed scenarios expose their specialized effective domains; finite-choice scenarios key them by the same canonical combinations as choice work. Finite direct-work `Sum` expressions retain lexical ownership of local iterators, and unresolved cardinality, ordering, or finiteness remains a flat explicit qualification rather than a free local symbol. Bounded explicit scenarios report their substitutions, provenance, qualifications, and unresolved blockers; unsupported inference, ordering, multivariate dominance, monotonicity, and opaque costs remain explicit rather than becoming stronger claims. These reports analyze submitted mathematical structure and complexity, not physical correctness, implementation timing, or global optimality.

## Candidate comparison

Candidate comparison reports ordered ordinary analyses, mapped semantic evidence, and only then a second-minus-first reuse-aware aggregate abstract-work delta. After mapped semantics are established, bounded sign evidence classifies the delta as `equal`, `first_lower`, `second_lower`, or `crossover`. Any unresolved or disproved mapping prevents preference; unsupported sign ordering remains explicit abstention rather than a runtime or optimality claim.

## Query conclusions

Each query result preserves its submitted target and normalized interpretation and returns only `proved`, `proved_under_assumptions`, `disproved`, `unresolved`, or `inapplicable` conclusions with inspectable evidence and qualifications. Unresolved blockers identify the failed supported family, structural or resource bound, ambiguous axis, or missing precondition and provide safe reformulation guidance when one exists; observed and configured values appear only when bounded inspection measured them, and guidance neither proves equivalence nor promises broader evaluator support. Derived candidates are informational and never replace submitted operation counts or direct work; no-query reports remain valid with an empty query collection. A partial nested finite-polynomial candidate carries checked finite-antidifference evidence and an independently identity-verified bounded canonical factorization; proved-empty ranges close to zero, unknown ordering is a localized unresolved precondition, and failed canonicalization publishes no candidate. A dependent equivalence, properties, limit, or asymptotic result preserves its derived source target and reports that candidate as `normalized_target`; only an unavailable derived operand uses `normalized_target: null`, with a source-specific inapplicable blocker. Query constraint uses are equation-qualified and present only when the selected equation-local facts are consumed. Symbolic reports do not claim runtime, cache behaviour, numerical quality, or optimal tuning.

## Dominance regions

Dominance reports canonical terms, active-domain cells, poles, ties, provenance, and bounded unresolved blockers. Status is exactly `complete`, `unresolved`, or `empty`: complete zero work has no terms or cells and an explicit zero-work qualification, while `empty` means no admissible active-domain points. Only complete results claim never-dominant terms. They state relevance only within the active domain and never imply speed, ranking, or optimality.

## Optimization advice

An explicit optimization success classifies its observed population as `plans_returned`, `no_applicable_candidate`, or `no_verified_improvement`. It separately reports `bounded_goal_v1` search scope and completion, `deterministic_ranked_prefix` selection, output-projection completion or truncation, and bounded localized blockers. Search incompleteness names exhausted bounds and never proves that no further improvement exists; projection truncation does not imply search exhaustion. Blockers identify only an observed family, target, stable missing-cost, domain/cardinality, or evaluator-limit reason, and required information. They are not candidates, recommendations, or proof and contain no speculative transformation or raw rejection text.

Every published plan carries only a `strict_improvement` claim under `verifier_backed_v1`, with the selected objective, exact-symbolic and aggregate-abstract-work semantics, actual families, fixed monotonic depth two, configured limits, and optimizer engine. Its one- or two-step replay retains schema-correlated `exact_algebraic_v1` or `exact_algorithmic_v1` provenance, complete candidates, parent-relative evidence, and independent original-to-final proof and positive whole-computation savings. Each step has unique target-local transformations; cross-equation sharing carries every affected equation, including positional-index renaming, as one atomic transformation set whose occurrences retain binder and output-index scope. Candidate identity remains policy-free, and each plan repeats canonical objective provenance. Unconditional proofs rank before assumption-dependent proofs; adjacent order is `previous_proved_superior` only when exact reasoning proves it, while equality, incomparability, or bounded uncertainty is `deterministic_non_superiority`. Deterministic ordering and a completed search do not claim a best candidate, finite-space exhaustion, unrestricted optimality, runtime improvement, finite-precision equivalence, numerical stability, or empirical performance. A typed operation failure contains no plan; ordinary analysis has no optimization report or passive optimizer failure.
