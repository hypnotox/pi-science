The report contract governs inspectability, qualification, and unresolved analysis results.

## Claims

### `rule: qualified-inspectable-results`
Every analysis reports the normalized interpretation actually analyzed and distinguishes exact results, assumption-dependent results, conservative bounds, and unresolved quantities. System reports may identify repeated-expression extraction diagnostics without claiming a rewrite or improvement. The analyzer never silently fixes a scaling variable, invents an unknown cost, or presents sampling as a mathematical bound.
Origin: ADR-0001
Revised-by: ADR-0008

### `rule: provenance-preserving-system-work`
Direct Python system reports preserve exact general symbolic work and identify every supported equality, directed definition, submitted affine relationship, predecessor-domain fact, and equation-qualified local constraint used in deterministic specialization and dependent-domain aggregation. Submitted constraints, normalized effective domains, and constraint uses remain separate inspectable fields. Finite direct-work `Sum` expressions retain lexical ownership of local iterators, and unresolved cardinality, ordering, or finiteness remains a flat explicit qualification rather than a free local symbol. Bounded explicit scenarios report their substitutions, provenance, qualifications, and unresolved blockers; unsupported inference, ordering, multivariate dominance, monotonicity, and opaque costs remain explicit rather than becoming stronger claims. These reports analyze submitted mathematical structure and complexity, not physical correctness, implementation timing, or global optimality.
Origin: ADR-0003
Revised-by: ADR-0009, ADR-0010, ADR-0013

### `rule: qualified-candidate-comparison`
Candidate comparison reports ordered ordinary analyses, mapped semantic evidence, and only then a second-minus-first reuse-aware aggregate abstract-work delta. Any unresolved or disproved mapping prevents preference; unsupported sign ordering remains explicit abstention rather than a runtime or optimality claim.
Origin: ADR-0015

### `rule: qualified-query-conclusions`
Each query result preserves its submitted target and normalized interpretation and returns only `proved`, `proved_under_assumptions`, `disproved`, `unresolved`, or `inapplicable` conclusions with inspectable evidence and qualifications. Unresolved blockers identify the failed supported family, structural or resource bound, ambiguous axis, or missing precondition and provide safe reformulation guidance when one exists; observed and configured values appear only when bounded inspection measured them, and guidance neither proves equivalence nor promises broader evaluator support. Derived candidates are informational and never replace submitted operation counts or direct work; no-query reports remain valid with an empty query collection. A partial nested finite-polynomial candidate carries checked finite-antidifference evidence and an independently identity-verified bounded canonical factorization; proved-empty ranges close to zero, unknown ordering is a localized unresolved precondition, and failed canonicalization publishes no candidate. A dependent equivalence, properties, limit, or asymptotic result preserves its derived source target and reports that candidate as `normalized_target`; only an unavailable derived operand uses `normalized_target: null`, with a source-specific inapplicable blocker. Query constraint uses are equation-qualified and present only when the selected equation-local facts are consumed. Symbolic reports do not claim runtime, cache behaviour, numerical quality, or optimal tuning.
Origin: ADR-0004
Revised-by: ADR-0005, ADR-0011, ADR-0012, ADR-0013, ADR-0014

### `rule: qualified-dominance-regions`
Dominance reports canonical terms, active-domain cells, poles, ties, provenance, and bounded unresolved blockers. They state relevance only within the active domain and never imply speed, ranking, or optimality.
Origin: ADR-0016


### `rule: qualified-optimization-advice`
Ordinary successful analysis reports bounded optimization advice separately from submitted interpretation, submitted work, scenarios, and informational queries. Every published suggestion carries a nonempty tuple of unique target-local transformations with target, normalized original and proposed forms, and structural occurrences. Every trace step and final suggestion carries schema-correlated `exact_algebraic_v1` or `exact_algorithmic_v1` tier provenance. Plans carry canonical objective provenance separate from objective-independent candidate identity and report selected-objective before, after, positive whole-computation savings, and one-based qualified adjacent ordering; deterministic non-superiority never claims proved superiority. Ordinary advice and direct optimization expose the same ordered replayable plans; absent, empty, ineligible, or nonpositive algorithmic selection adds no family-specific diagnostic and leaves other analysis independent. Each plan has one or two complete parent-relative trace states, may mix tiers when explicitly enabled, and carries independently checked original-to-final evidence. Passive optimizer faults preserve base analysis with a bounded failed diagnostic; direct optimization returns a typed failure without plans. Search incompleteness names a bounded resource and does not imply no improvement exists. Post-search serialized-output truncation is a separate projection status and qualification. Exact-symbolic plans do not claim runtime improvement, finite-precision equivalence, numerical stability, or empirical performance.
Origin: ADR-0017
Revised-by: ADR-0018, ADR-0019, ADR-0020, ADR-adopt-opt-in-exact-algorithmic-finite-sum-optimization