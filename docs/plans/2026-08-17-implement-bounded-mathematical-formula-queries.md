---
format: plan-v2
date: 2026-08-17
adrs:
  - adopt-explicit-bounded-mathematical-queries
status: Proposed
---
# Plan: Implement bounded mathematical formula queries

## Goal

Expose safe, exact, assumption-aware mathematical queries for formula requests through both the reusable Python API and Pi while preserving no-query structural and direct-work analysis. Scenario-scoped queries, LaTeX, complex values, dimensions, vector shorthand, differentiation, numerical approximation, and general theorem proving are not implemented by this plan.

## Architecture summary

The backend-independent expression model gains canonical `RationalLiteral(numerator, positive_denominator)` and `InfinityLiteral(sign)` values before query execution is introduced. Formula decimal tokens use the same bounded exact rational semantics; `oo` and `-oo` are reserved infinity spellings. Cross-language scalar inputs accept a JavaScript-safe JSON integer or a no-whitespace string matching `-?(0|[1-9][0-9]*)(/[1-9][0-9]*|\.[0-9]+)?`. A leading plus, leading zero on a nonzero integer part, exponent notation, signed or zero denominator, bare decimal point, and surrounding whitespace are invalid. Values reduce by greatest common divisor, keep a positive denominator, normalize every zero spelling to `0`, and serialize as a base-10 integer string when integral or `numerator/denominator` otherwise. Digit and bit limits apply before and after reduction.

Submitted structure stays in the existing operation fields. The exact direct-work union uses `DirectWorkApplicability = finite | not_finite` and bounded `direct_work_blockers: tuple[str, ...]`. `AnalysisSuccess` adds those two keys and changes only `abstract_work` to `int | null`. `EquationReport` adds those keys and changes `aggregate_operation_counts`, `aggregate_work`, and `primitive_invocations` to their existing type or null. `SystemReport` adds those keys and changes `aggregate_operation_counts`, `total_work`, and `primitive_invocations` to their existing type or null. In every finite variant all work/count/invocation fields are nonnull and blockers is empty. An equation containing an infinite iterator is `not_finite`, all three equation aggregate fields are null, and blockers contains `infinite iterator has no finite direct-evaluation work`. A system is `not_finite` when any equation is, its three aggregate fields are null, and its blockers name the affected equations; unaffected equation reports remain finite. A single-expression success with an infinite iterator is `not_finite`, `abstract_work` is null, and the same blocker is present. Structural `operation_counts`, normalized interpretation, dependencies, unknown costs, and query results remain populated in either variant. No null or empty aggregate value is presented as zero work.

The diagnostic schema is exact. `SourceLocation` remains `{line: int >= 1, column: int >= 0}`. `SourceSpan` is `{start: SourceLocation, end: SourceLocation}` with an end-exclusive end not preceding start. `SourceReference` is `{path: str, span: SourceSpan | null, excerpt: str | null}`; path is a bounded request path such as `expression`, `equations[1].expression`, or `queries[0].comparison`, and excerpt is at most 160 Unicode code points. `AnalysisError` serializes exactly `{code, message, location, source, supported_alternative}`: the final three keys are always present and contain null when unavailable, `location` equals `source.span.start` when a span exists, and `supported_alternative` is a bounded string or null. A source path may exist with null span/excerpt for model-level failures. Missing precision uses null, never a synthetic coordinate. Phase 1 advances the private protocol from version 2 to 3 and updates the minimum adapter and TypeScript validators atomically for these populated fields.

The general request is the only query context in this plan. The request union uses `EquationTarget = {kind: "equation", name: identifier}` and the exact scalar-or-infinity `Point` defined above. Its strict variants are: `EquivalenceQuery = {name, kind: "equivalence", target?, comparison: formula}`; `ClosedFormQuery = {name, kind: "closed_form", target?}`; `PropertiesQuery = {name, kind: "properties", target?, checks}`; `LimitQuery = {name, kind: "limit", target?, variable: identifier, point, direction?}`; and `AsymptoticQuery = {name, kind: "asymptotic", target?, variable: identifier, point, direction?, order: int[1,8]}`. `checks` is a nonempty bounded tuple of unique strict variants `{kind: "valid_domain", variable}`, `{kind: "singularities", variable}`, `{kind: "sign"}`, or `{kind: "monotonicity", variable}`. A single-expression query must omit `target`; a system query must supply it. A finite point requires `direction: left | right | both`; `oo` and `-oo` forbid direction. Every unlisted key, nested selector, scenario context, empty check list, duplicate check, or incompatible point/direction pair is invalid.

The result union is also exact. `ResolvedTarget` is `{kind: "expression"}` or `{kind: "equation", name}`. `DerivedCandidate` is `{interpretation: Interpretation, operation_counts: OperationCounts}` and never carries direct work. Every `QueryAnswer` serializes `{check, conclusion, conditions, assumptions_used, relevant_unsupported_assumptions, blockers, evidence, derived_candidates}`. `check` is null for non-property answers and the exact submitted property-check object otherwise. `conclusion` is one of `proved`, `proved_under_assumptions`, `disproved`, `unresolved`, or `inapplicable`; `conditions`, `relevant_unsupported_assumptions`, and `blockers` are bounded tuples of normalized strings; `assumptions_used` is a bounded tuple of existing `RelationshipUse`; `derived_candidates` is always a bounded tuple; and `evidence` is always present with one strict variant or null. Evidence variants are `{kind: "identity", statement}`, `{kind: "counterexample", substitutions, target_value, comparison_value}`, `{kind: "closed_form", verification: "finite_antidifference" | "infinite_partial_sum", statement}`, `{kind: "property", value, intervals}`, `{kind: "limit", exists, value, left, right}`, and `{kind: "asymptotic", statement, remainder}`. Every expression/value/interval/statement is a normalized bounded string; substitutions map identifiers to canonical exact-scalar strings; nullable limit values are present as null; and `remainder` is `{local_parameter, exponent: int, normalized_big_o}` or null for an exact exhausted expansion.

Each strict result variant is `{name, kind, target: ResolvedTarget, normalized_target: Interpretation, summary, answers}` with the same discriminant as its request. Equivalence, closed-form, limit, and asymptotic results contain exactly one answer and permit only their matching evidence kinds; properties contains exactly one answer per check in request order and permits only property evidence. An unresolved or inapplicable answer has null evidence unless exact divergence/inapplicability evidence exists, and an empty candidate tuple. `AnalysisSuccess.queries` is always serialized as a tuple, empty when omitted and otherwise in request order. Request syntax or target errors fail the request with source identity; a valid but unsupported mathematical question succeeds with a localized unresolved answer.

A cohesive Python query evaluator owns target resolution, assumption relevance, proof qualification, and resource budgets. Before any backend call it accepts only an allowlisted family, at most 512 query-target nodes, eight sibling nonnested sums, polynomial degree at most 8, absolute literal exponent at most 32, 1024-bit exact coefficients, and asymptotic order at most 8. Every candidate-producing step validates at most 4096 intermediate nodes, coefficient and rendering bounds, and the existing serialized-result limit before continuing. Generic `summation`, `simplify`, `limit`, `diff`, or `series` calls on unchecked expressions are prohibited. SymPy may perform only the family-specific normalization, cancellation, differentiation, or rendering named by a task; deterministic precondition failure returns `unresolved` in the direct Python API rather than relying on Pi's process timeout.

Existing scenarios remain work specializations under global assumptions; their scalar values and finite intervals become exact, but they do not execute queries. The private adapter and TypeScript layers translate and strictly validate the same contract without acquiring mathematical policy. Protocol version 4 in Phase 2 carries the empty/general query result envelope needed for no-query Pi compatibility, version 5 in Phase 6 exposes exact real scenarios, and version 6 in Phase 7 exposes query requests and the complete query result contract.

## Phase 1: Establish exact values, infinity, and diagnostics

**Execution mode: subagent-driven.**

Completes: ["exact-foundation"]

### Task 1.1: Specify exact parsing and non-finite work behavior in tests
Applying: ["adopt-explicit-bounded-mathematical-queries:exact-query-mathematics", "adopt-explicit-bounded-mathematical-queries:symbolic-query-product-boundary"]
Paths: ["tests/e2e/test_formula_analysis.py", "tests/e2e/test_formula_system_analysis.py", "tests/unit/test_error_translation.py", "tests/unit/test_exact_values.py"]

Start from the reviewed ADR and the current integer-only expression model without adding the public query collection. Drive the Architecture summary's exact-scalar grammar, canonical output, infinity spellings, direct-work applicability union, and diagnostic coordinate conventions through focused failing evidence. Cover exact finite decimal parsing and rendering, canonical rational arithmetic, bounded literal sizes, positive and negative mathematical infinity in supported positions, and rejection of infinity where a finite computational bound is required. Prove that an infinite `Sum` remains a mathematical expression but cannot produce finite direct-evaluation work. Extend diagnostic evidence to cover source field identity, query-ready source spans, excerpts, and supported-alternative hints without weakening existing error codes.

### Task 1.2: Add shared exact-value and infinity semantics
Applying: ["adopt-explicit-bounded-mathematical-queries:exact-query-mathematics", "adopt-explicit-bounded-mathematical-queries:symbolic-query-product-boundary"]
Paths: ["packages/py-science-formula/src/py_science/formula/expressions.py", "packages/py-science-formula/src/py_science/formula/parser.py", "packages/py-science-formula/src/py_science/formula/exact_values.py", "packages/py-science-formula/src/py_science/formula/sympy_backend.py", "packages/py-science-formula/src/py_science/formula/work.py", "packages/py-science-formula/src/py_science/formula/service.py"]

Represent finite decimals as exact rational values and represent signed infinity as a distinct IR value rather than an ordinary symbol. Route traversal, substitution, node counting, exact arithmetic, relationship evaluation, rendering, and domain predicates through the shared exact-value module. Classify sum bounds before work cardinality: finite integral bounds retain ADR-0003 semantics, while infinite bounds produce an explicit non-finite direct-work qualification and never a symbolic finite cardinality. Preserve parser safety, input depth, node, digit, and rendering budgets.

### Task 1.3: Publish structured source diagnostics and exact-value models
Applying: ["adopt-explicit-bounded-mathematical-queries:exact-query-mathematics", "adopt-explicit-bounded-mathematical-queries:assumption-aware-qualified-reasoning"]
Paths: ["packages/py-science-formula/src/py_science/formula/models.py", "packages/py-science-formula/src/py_science/formula/__init__.py", "packages/py-science-formula/src/py_science/formula/parser.py", "packages/py-science-formula/src/py_science/formula/service.py", "packages/py-science-formula/README.md", "packages/pi-science/bridge/formula_adapter.py", "packages/pi-science/src/bridge.ts", "packages/pi-science/src/provision.ts", "packages/pi-science/tests/adapter.test.ts", "packages/pi-science/tests/bridge.test.ts", "packages/pi-science/tests/provision.test.ts", "packages/pi-science/tests/start.test.ts"]

Implement the exact optional diagnostic fields and nullable non-finite work representation specified in the Architecture summary. Syntactically invalid input remains a request failure; mathematically unsupported but valid input remains eligible for later qualified query results. Remove synthetic locations that imply unavailable precision. Export the exact public types and document exact decimal and infinity behavior without advertising queries yet. Advance the private protocol to version 3 in the adapter, bridge, and readiness probe; teach TypeScript's exact-key validators the diagnostic and direct-work variants, and add accepted, missing, surplus, and malformed nested-field fixtures. This is shape compatibility only: Python retains all diagnostic and mathematical policy.

### Phase close

Focused evidence: run `uv run --locked pytest tests/unit/test_exact_values.py tests/unit/test_error_translation.py tests/e2e/test_formula_analysis.py tests/e2e/test_formula_system_analysis.py` and `./node_modules/.bin/vitest run packages/pi-science/tests/adapter.test.ts packages/pi-science/tests/bridge.test.ts packages/pi-science/tests/provision.test.ts packages/pi-science/tests/start.test.ts`. Close only when existing finite Sum and no-query work values remain unchanged except for the specified shape additions and `./scripts/check` passes.

```commit
feat(formula): add exact mathematical values and diagnostics
```

## Phase 2: Add query contracts and equivalence reasoning

**Execution mode: subagent-driven.**

Completes: ["equivalence-queries"]

### Task 2.1: Specify the bounded general-query contract
Applying: ["adopt-explicit-bounded-mathematical-queries:explicit-bounded-mathematical-queries", "adopt-explicit-bounded-mathematical-queries:explicit-query-contexts", "adopt-explicit-bounded-mathematical-queries:assumption-aware-qualified-reasoning"]
Paths: ["tests/e2e/test_formula_analysis.py", "tests/e2e/test_formula_system_analysis.py", "tests/unit/test_formula_queries.py", "tests/unit/test_formula_scenarios.py"]

Start from the exact-value foundation commit and keep scenario execution unchanged. Turn every request, target, point, direction, order, check, result, answer, conclusion, evidence, condition, blocker, candidate, default, and omission rule in the Architecture summary into failing strict-model and serialization evidence. Cover unique named queries, bounded populations and aggregate source bytes, all five discriminated kinds, the implicit main-expression target, the required named-equation target for systems, missing and unknown equation targets, and rejection of nested selectors or scenario contexts. Verify that omitted `queries` serializes as an empty result collection, preserves all prior finite analysis values, and causes no scenario fan-out.

### Task 2.2: Introduce query models, target resolution, and qualification ownership
Applying: ["adopt-explicit-bounded-mathematical-queries:explicit-bounded-mathematical-queries", "adopt-explicit-bounded-mathematical-queries:explicit-query-contexts", "adopt-explicit-bounded-mathematical-queries:assumption-aware-qualified-reasoning"]
Paths: ["packages/py-science-formula/src/py_science/formula/models.py", "packages/py-science-formula/src/py_science/formula/__init__.py", "packages/py-science-formula/src/py_science/formula/query.py", "packages/py-science-formula/src/py_science/formula/reasoning.py", "packages/py-science-formula/src/py_science/formula/service.py", "packages/pi-science/bridge/formula_adapter.py", "packages/pi-science/src/bridge.ts", "packages/pi-science/src/provision.ts", "packages/pi-science/tests/adapter.test.ts", "packages/pi-science/tests/bridge.test.ts", "packages/pi-science/tests/provision.test.ts", "packages/pi-science/tests/start.test.ts"]

Implement the strict frozen request and result unions exactly as specified in the Architecture summary. Resolve targets after ordinary formula/system validation and pass parsed RHS values into a separate evaluator; do not embed query branches into work analysis or mutate system reports. The initial reasoning context consumes declared integer/real/sign domains, exact directed-definition substitution, exact equality replacement, and conjunctions of single-symbol affine rational inequalities. It may derive closed interval endpoints, strictness, zero exclusions, signs of bounded products and integer powers, and `Abs(r) < 1` from proved `-1 < r < 1`; multivariate solving, nonlinear inequality solving, and facts not derivable by this rule set remain relevant unsupported assumptions. Apply the pre-call and intermediate backend limits before any candidate operation, plus independent query-count, aggregate-source, reasoning-step, derived-node, rendering, and serialized-result budgets. In this phase `closed_form`, `properties`, `limit`, and `asymptotic` are real production consumers that deterministically return one localized `unresolved` answer with blocker `query kind is not implemented in this release slice`; Phases 3 through 5 replace that terminal behavior kind by kind without changing the public union. Advance the private protocol from version 3 to version 4 and update the adapter, readiness probe, and TypeScript result validator for the serialized empty/general query result envelope so existing no-query Pi calls remain green. Do not add query request fields to the Pi tool schema yet.

### Task 2.3: Implement conservative domain-aware equivalence
Applying: ["adopt-explicit-bounded-mathematical-queries:assumption-aware-qualified-reasoning", "adopt-explicit-bounded-mathematical-queries:symbolic-query-product-boundary"]
Paths: ["packages/py-science-formula/src/py_science/formula/query.py", "packages/py-science-formula/src/py_science/formula/reasoning.py", "packages/py-science-formula/src/py_science/formula/sympy_backend.py", "packages/py-science-formula/src/py_science/formula/service.py", "tests/unit/test_formula_queries.py", "tests/e2e/test_formula_analysis.py", "tests/e2e/test_formula_system_analysis.py", "packages/py-science-formula/README.md"]

Compare one explicit candidate against the selected target under declared domains and global assumptions. The initial equivalence family accepts exact rational expressions whose query-relevant numerator and denominator polynomials meet the Architecture summary caps and whose coefficients are exact or parameter expressions with resolved equalities. Cancel and cross-multiply only after recording every original denominator as a nonzero domain obligation; prove equality when the bounded normalized numerator difference is the zero polynomial on that domain. Prove nonidentity immediately for a nonzero exact constant difference, or with a reported exact rational assignment found by bounded deterministic enumeration that satisfies every domain and assumption; failure to find such an assignment is not evidence. Later supported closed forms enter the same verifier. Qualify used assumptions, excluded points, and any conditional equality. Keep comparison and normalized candidate structure outside submitted operation and direct-work fields. Valid family mismatches, unresolved coefficients, and undischarged obligations return `unresolved` locally.

### Phase close

Focused evidence: run `uv run --locked pytest tests/unit/test_formula_queries.py tests/e2e/test_formula_analysis.py tests/e2e/test_formula_system_analysis.py tests/unit/test_formula_scenarios.py` and `./node_modules/.bin/vitest run packages/pi-science/tests/adapter.test.ts packages/pi-science/tests/bridge.test.ts packages/pi-science/tests/provision.test.ts packages/pi-science/tests/start.test.ts`. Close with expression and named-RHS equivalence evidence for proved, assumption-qualified, disproved, domain-restricted, unresolved, and malformed cases, deterministic unresolved consumers for later kinds, a green no-query regression suite, and `./scripts/check` success.

```commit
feat(formula): add bounded equivalence queries
```

## Phase 3: Derive qualified closed forms

**Execution mode: subagent-driven.**

Completes: ["closed-form-queries"]

### Task 3.1: Specify supported finite and infinite series families
Applying: ["adopt-explicit-bounded-mathematical-queries:explicit-bounded-mathematical-queries", "adopt-explicit-bounded-mathematical-queries:assumption-aware-qualified-reasoning", "adopt-explicit-bounded-mathematical-queries:exact-query-mathematics"]
Paths: ["tests/unit/test_formula_queries.py", "tests/e2e/test_formula_analysis.py", "tests/e2e/test_formula_system_analysis.py"]

Start from the equivalence query engine and reuse its target, exact-value, condition, provenance, and candidate boundaries. The initial rule matrix accepts at most eight sibling, nonnested sums whose normalized summand is `(a*k + b) * r**k`: `a`, `b`, and `r` are independent of the bound index `k`, contain no indexed values, opaque calls, or further sums, and satisfy the Architecture summary's node, exponent, coefficient, and polynomial caps. Bounds are finite integer-valued expressions independent of `k`, or a finite lower bound with upper `oo`; their ordering and integrality must follow from declared domains and global assumptions.

Drive these exact rules through failing examples. For finite bounds `m..n`, define `G = (r**m - r**(n + 1)) / (1 - r)` when `r != 1` and `G = n - m + 1` when `r == 1`; the candidate for `(a*k+b)*r**k` is the fully expanded exact form of `a*r*dG/dr + b*G`. For `m..oo`, use `G = r**m/(1-r)` and the same derivative identity only when `Abs(r) < 1` is proved. A proved nonzero summand with `Abs(r) >= 1` yields `inapplicable` with a divergence condition; undecidable convergence or a matrix mismatch yields `unresolved`; nested sums yield `unresolved`. Multiple accepted siblings are replaced independently and composed through the enclosing supported arithmetic. Include the AFMM identity `Sum((k + 1) * q**k, (k, p, oo)) = q**p * (p + 1 - p*q) / (1 - q)**2` under nonnegative integral `p` and `0 <= q < 1`. Require exact convergence and denominator conditions, named assumption provenance, and separate derived-candidate structure.

### Task 3.2: Implement a bounded closed-form rule library
Applying: ["adopt-explicit-bounded-mathematical-queries:symbolic-query-product-boundary", "adopt-explicit-bounded-mathematical-queries:assumption-aware-qualified-reasoning"]
Paths: ["packages/py-science-formula/src/py_science/formula/query.py", "packages/py-science-formula/src/py_science/formula/reasoning.py", "packages/py-science-formula/src/py_science/formula/series.py", "packages/py-science-formula/src/py_science/formula/sympy_backend.py", "packages/py-science-formula/src/py_science/formula/service.py", "tests/unit/test_formula_queries.py", "tests/e2e/test_formula_analysis.py", "tests/e2e/test_formula_system_analysis.py", "packages/py-science-formula/README.md"]

Implement only the Task 3.1 rule matrix. Construct candidates from the explicit `G` and derivative identities rather than calling generic SymPy summation. Family-checked polynomial differentiation and cancellation may normalize the candidate, but the evaluator must revalidate intermediate bounds and verify the finite antidifference or infinite partial-sum limit identity before assigning a proved status. Discharge convergence, integer-bound, ordering, empty-range, `r == 1`, and denominator obligations explicitly. Preserve the specified divergence and mismatch outcomes and never pass infinite sums into finite work aggregation.

### Phase close

Focused evidence: run `uv run --locked pytest tests/unit/test_formula_queries.py tests/e2e/test_formula_analysis.py tests/e2e/test_formula_system_analysis.py`. Close when the AFMM omitted-tail identity is proved through the direct Python API, every Task 3.1 rule-matrix terminal outcome is covered, convergence failures remain conservative, all earlier query and work results remain green, and `./scripts/check` passes.

```commit
feat(formula): derive qualified series closed forms
```

## Phase 4: Analyze properties and limits

**Execution mode: subagent-driven.**

Completes: ["property-limit-queries"]

### Task 4.1: Specify property applicability and directional limits
Applying: ["adopt-explicit-bounded-mathematical-queries:explicit-bounded-mathematical-queries", "adopt-explicit-bounded-mathematical-queries:assumption-aware-qualified-reasoning"]
Paths: ["tests/unit/test_formula_queries.py", "tests/e2e/test_formula_analysis.py", "tests/e2e/test_formula_system_analysis.py"]

Start from the shared reasoning context and closed-form rules, retaining an exact univariate boundary. After replacing Task 3.1 sums, the initial property matrix accepts exact rational combinations of the query variable, bounded integer powers, and symbolic parameter factors whose realness and sign are established by declared domains or global assumptions. Denominators must factor into supported linear factors in the query variable; opaque calls, indexed values, unfactored parameter-dependent roots, and multivariate ordering remain unsupported. `valid_domain` reports excluded denominator roots; `singularities` reports uncanceled roots and pole order; `sign` uses an exact factor sign chart; real-variable `monotonicity` differentiates then requires the same sign grammar; integer-variable monotonicity uses an exact forward difference and the same grammar. `limit` supports exact substitution away from excluded roots, leading-factor one-sided pole limits, polynomial-degree limits at signed infinity, and Task 3 closed forms. Other valid forms return `unresolved`; sign or monotonicity returns `inapplicable` when realness is unproved. A proved nonexistent two-sided limit is a `proved` answer whose kind-specific evidence records distinct one-sided results.

Turn every matrix row and terminal outcome into failing evidence. Treat other symbols as parameters under global domains and assumptions, report singularities even when assumptions exclude them, and identify each singularity's relation to the active domain. Exercise exact finite points, left, right, and two-sided limits, signed infinity, and resource refusals.

### Task 4.2: Implement localized property and limit evaluators
Applying: ["adopt-explicit-bounded-mathematical-queries:assumption-aware-qualified-reasoning", "adopt-explicit-bounded-mathematical-queries:symbolic-query-product-boundary"]
Paths: ["packages/py-science-formula/src/py_science/formula/query.py", "packages/py-science-formula/src/py_science/formula/reasoning.py", "packages/py-science-formula/src/py_science/formula/properties.py", "packages/py-science-formula/src/py_science/formula/sympy_backend.py", "packages/py-science-formula/src/py_science/formula/service.py", "tests/unit/test_formula_queries.py", "tests/e2e/test_formula_analysis.py", "tests/e2e/test_formula_system_analysis.py", "packages/py-science-formula/README.md"]

Implement only the Task 4.1 property matrix with allowlisted factorization, cancellation, differentiation, and forward-difference operations guarded by the Architecture summary's pre-call and intermediate bounds. Attach only facts that participate in each conclusion and distinguish proved nonexistence, unsupported reasoning, and mathematical inapplicability. Demonstrate that the AFMM tail is nonnegative for integral `p >= 0` and `0 <= q < 1`; prove strict positivity only with `q > 0` or `p == 0`; characterize supported nonincreasing or nondecreasing behavior in `p` and `q`; and report the `q = 1` singularity and its relation to the assumed open domain. None of these facts changes implementation-cost claims.

### Phase close

Focused evidence: run `uv run --locked pytest tests/unit/test_formula_queries.py tests/e2e/test_formula_analysis.py tests/e2e/test_formula_system_analysis.py`. Close with every Task 4.1 property-matrix outcome qualified under global assumptions, no unrelated assumption duplication, green prior query, scenario, and work suites, and `./scripts/check` success.

```commit
feat(formula): analyze formula properties and limits
```

## Phase 5: Add mathematical asymptotic queries

**Execution mode: subagent-driven.**

Completes: ["asymptotic-queries"]

### Task 5.1: Specify bounded expression expansions
Applying: ["adopt-explicit-bounded-mathematical-queries:explicit-bounded-mathematical-queries", "adopt-explicit-bounded-mathematical-queries:symbolic-query-product-boundary"]
Paths: ["tests/unit/test_formula_queries.py", "tests/e2e/test_formula_analysis.py", "tests/e2e/test_formula_system_analysis.py"]

Start from exact limits and qualification without reusing scenario work-growth classification as expression semantics. The initial matrix accepts Task 4 rational expressions and Task 3 closed forms that become rational in a local parameter, plus a finite sum of `(a*x+b)*r**x` terms at signed infinity when coefficient and base facts meet the common bounds. At a finite point `c`, the local parameter is `t = x-c`; at `oo` it is `t = 1/x`; at `-oo` it is `t = -1/x`. For rational forms, `order = n` retains every Laurent term with local exponent below `n` and returns the exact structured remainder `O(t**n)`; negative pole exponents are allowed within the exponent cap. For the exponential-linear family, `order` is the maximum retained nonzero polynomial-times-exponential terms, ordered by decreasing polynomial degree, with an exact zero remainder when the accepted expression is exhausted. Finite points require a direction and signed infinity forbids one; multivariate or path-dependent requests are invalid or unresolved according to the request/result boundary.

Add failing cases for every accepted family, point grammar, order meaning, one-sided condition, exact structured remainder, unsupported family, intermediate bound, and result-size limit. Assert that an expression asymptotic answer is distinct from scenario direct-work growth and cannot mutate submitted work.

### Task 5.2: Implement qualified asymptotic forms
Applying: ["adopt-explicit-bounded-mathematical-queries:assumption-aware-qualified-reasoning", "adopt-explicit-bounded-mathematical-queries:symbolic-query-product-boundary"]
Paths: ["packages/py-science-formula/src/py_science/formula/query.py", "packages/py-science-formula/src/py_science/formula/reasoning.py", "packages/py-science-formula/src/py_science/formula/asymptotics.py", "packages/py-science-formula/src/py_science/formula/sympy_backend.py", "packages/py-science-formula/src/py_science/formula/service.py", "tests/unit/test_formula_queries.py", "tests/e2e/test_formula_analysis.py", "tests/e2e/test_formula_system_analysis.py", "packages/py-science-formula/README.md"]

Implement only the Task 5.1 matrix with exact polynomial division, truncated rational arithmetic, and explicit exponential-linear ordering. Do not call generic SymPy `series` on submitted expressions. Verify every coefficient, approach condition, and structured remainder against the accepted rational identity or exact exponential decomposition before assigning a proved status. Rename report prose for existing scenario complexity to `work growth` where needed while preserving its request compatibility. Return `unresolved` for unsupported expansion families or any pre-call/intermediate bound refusal.

### Phase close

Focused evidence: run `uv run --locked pytest tests/unit/test_formula_queries.py tests/e2e/test_formula_analysis.py tests/e2e/test_formula_system_analysis.py`. Close when every Task 5.1 family and terminal outcome is covered, all five general query kinds share one qualification and target contract, asymptotic outputs remain bounded and separate from work growth, and `./scripts/check` passes.

```commit
feat(formula): add qualified asymptotic queries
```

## Phase 6: Extend scenarios with exact real values

**Execution mode: subagent-driven.**

Completes: ["exact-real-scenarios"]

### Task 6.1: Specify exact scenario scalars and intervals
Applying: ["adopt-explicit-bounded-mathematical-queries:exact-query-mathematics", "adopt-explicit-bounded-mathematical-queries:explicit-query-contexts"]
Paths: ["tests/unit/test_formula_scenarios.py", "tests/e2e/test_formula_analysis.py", "tests/e2e/test_formula_system_analysis.py"]

Start from the shared exact-value module and keep scenario-context queries disabled. Apply the Architecture summary's exact-scalar grammar to fixed values, choices, and interval endpoints. Explicitly accept `0`, `-0`, `1/2`, `-3/4`, `1.20`, and safe JSON integers; canonicalize them to `0`, `1/2`, `-3/4`, and `6/5` as applicable. Reject whitespace, `+1`, `01`, `.5`, `1.`, `1e-3`, `1/-2`, `1/0`, over-limit digits, and duplicate values after canonicalization. Add `nonnegative_real`.

An interval has finite `lower` and `upper` exact scalars plus optional `lower_inclusive` and `upper_inclusive` booleans that default to true for existing closed bounds. Reject lower greater than upper; reject equal endpoints unless both are inclusive; preserve an inclusive singleton. Require a nonempty intersection with the declared domain and global assumptions. Results carry canonical endpoints, both inclusion flags, conservative infimum/supremum, and whether either extremum is attained. Keep symbolic limit approaches in queries and prove that scenarios never execute queries in this plan.

### Task 6.2: Apply exact values throughout scenario specialization
Applying: ["adopt-explicit-bounded-mathematical-queries:exact-query-mathematics", "adopt-explicit-bounded-mathematical-queries:explicit-query-contexts"]
Paths: ["packages/py-science-formula/src/py_science/formula/models.py", "packages/py-science-formula/src/py_science/formula/exact_values.py", "packages/py-science-formula/src/py_science/formula/service.py", "packages/py-science-formula/src/py_science/formula/work.py", "packages/py-science-formula/src/py_science/formula/__init__.py", "tests/unit/test_formula_scenarios.py", "tests/e2e/test_formula_analysis.py", "tests/e2e/test_formula_system_analysis.py", "packages/py-science-formula/README.md", "packages/pi-science/bridge/formula_adapter.py", "packages/pi-science/src/bridge.ts", "packages/pi-science/src/index.ts", "packages/pi-science/src/provision.ts", "packages/pi-science/tests/adapter.test.ts", "packages/pi-science/tests/bridge.test.ts", "packages/pi-science/tests/provision.test.ts", "packages/pi-science/tests/start.test.ts"]

Use the Architecture summary's one bounded exact-scalar type and Task 6.1 interval shape across fixed values, choices, interval endpoints, substitution records, domain checks, assumption consistency, definitions, and rendering. Reject duplicate canonical choices rather than silently deduplicating them. Continuous open intervals report conservative infimum/supremum and attained flags rather than claiming unattained extrema. Preserve current integer scenario behavior, closed-bound defaults, and generated-result bounds. Advance the private protocol from version 4 to version 5 and carry the exact-scalar scenario request/result shapes through the adapter, readiness probe, TypeScript validators, and TypeBox schema in this same phase; keep Pi query request fields absent.

### Phase close

Focused evidence: run `uv run --locked pytest tests/unit/test_formula_scenarios.py tests/e2e/test_formula_analysis.py tests/e2e/test_formula_system_analysis.py tests/unit/test_formula_queries.py` and `./node_modules/.bin/vitest run packages/pi-science/tests/adapter.test.ts packages/pi-science/tests/bridge.test.ts packages/pi-science/tests/provision.test.ts packages/pi-science/tests/start.test.ts`. Close when the accepted/rejected scalar table and interval terminal set are covered, exact real substitutions remain consistent with global assumptions, query execution remains general-only, all prior formula behavior is green, and `./scripts/check` passes.

```commit
feat(formula): support exact real scenarios
```

## Phase 7: Carry the complete contract through Pi and current-state authority

**Execution mode: subagent-driven.**

Completes: ["pi-query-product"]

### Task 7.1: Translate and strictly validate queries across the private protocol
Kind: batch
Applying: ["adopt-explicit-bounded-mathematical-queries:explicit-bounded-mathematical-queries", "adopt-explicit-bounded-mathematical-queries:exact-query-mathematics", "adopt-explicit-bounded-mathematical-queries:assumption-aware-qualified-reasoning"]
Paths: ["packages/pi-science/bridge/formula_adapter.py", "packages/pi-science/src/bridge.ts", "packages/pi-science/src/index.ts", "packages/pi-science/src/provision.ts", "packages/pi-science/tests/adapter.test.ts", "packages/pi-science/tests/bridge.test.ts", "packages/pi-science/tests/start.test.ts", "packages/pi-science/tests/provision.test.ts", "packages/pi-science/tests/afmm-fixture.ts"]
Representative: Carry each Python discriminated query and result variant through TypeScript exact-key validators and the TypeBox tool schema without translating mathematical meaning.
Edge: Reject surplus keys, invalid scalar strings, invalid targets, invalid result conclusions, oversized query operands, malformed candidates, and protocol-version mismatches before the Pi tool returns them.
Post-check: Run `npm run test:pi`; expect every test under `packages/pi-science/tests` to pass and no validator fixture without an explicit accepted or rejected terminal assertion.

Start from the settled Python request and result contract and propagate query requests atomically through strict transport. Advance the private protocol from version 5 to version 6 in the adapter, bridge, and readiness probe because the Pi request now exposes queries and the validator accepts populated query answers and derived candidates. Include query operand strings in whole-request byte accounting and preserve adapter/output bounds. Keep mathematical applicability and proof status opaque to TypeScript: it validates shape and transports Python's qualified result only. Preserve the existing no-query AFMM fixture and add a separate query-bearing AFMM round trip.

### Task 7.2: Teach callers the exact query and result contract
Applying: ["adopt-explicit-bounded-mathematical-queries:explicit-bounded-mathematical-queries", "adopt-explicit-bounded-mathematical-queries:symbolic-query-product-boundary", "adopt-explicit-bounded-mathematical-queries:explicit-query-contexts"]
Paths: ["packages/pi-science/skills/formula-analysis/SKILL.md", "packages/py-science-formula/README.md", "README.md"]

Document each query's fields, supported initial mathematical families, whole-expression or named-RHS targeting, global-assumption behavior, exact values, conclusion statuses, and diagnostic inspection. State that derived candidates do not replace submitted work, infinite mathematics has no finite work count, scenarios do not run queries, and unsupported valid questions remain localized and qualified. Include one AFMM tail example and retain explicit non-goals.

### Task 7.3: Apply current-state claims and rephase future capabilities
Kind: batch
Applying: ["adopt-explicit-bounded-mathematical-queries:explicit-bounded-mathematical-queries", "adopt-explicit-bounded-mathematical-queries:symbolic-query-product-boundary", "adopt-explicit-bounded-mathematical-queries:assumption-aware-qualified-reasoning", "adopt-explicit-bounded-mathematical-queries:exact-query-mathematics", "adopt-explicit-bounded-mathematical-queries:explicit-query-contexts"]
Paths: ["docs/decisions/adopt-explicit-bounded-mathematical-queries.md", ".awf/topics/parts/product/product-boundary/current-state.md", ".awf/topics/parts/product/mathematical-input-contract/current-state.md", ".awf/topics/parts/product/mathematical-analysis-model/current-state.md", ".awf/topics/parts/product/analysis-report-contract/current-state.md", "docs/topics/product/product-boundary.md", "docs/topics/product/mathematical-input-contract.md", "docs/topics/product/mathematical-analysis-model.md", "docs/topics/product/analysis-report-contract.md", "docs/domains/product.md", "docs/vision.md", "docs/analysis-model.md", ".awf/docs/parts/architecture/components.md", ".awf/docs/parts/architecture/data-flow.md", ".awf/docs/parts/testing/layout.md", ".awf/docs/parts/testing/tiers.md", ".awf/docs/parts/roadmap/ideas.md", "docs/architecture.md", "docs/testing.md", "docs/roadmap.md", "docs/decisions/INDEX.md", ".awf/awf.lock"]
Representative: Update the single owning claim or current-state section for each implemented contract, then render generated outputs.
Edge: Keep restricted LaTeX, scenario-context queries, complex values, dimensions, vector shorthand, and differentiation explicitly future; do not describe them as shipped or retain contradictory MVP wording.
Post-check: Capture pre-render hashes, run `./awf render`, and require the render-owned changed set to be exactly `.awf/awf.lock`, `docs/architecture.md`, `docs/testing.md`, `docs/roadmap.md`, the four named `docs/topics/product/*.md` pages, `docs/domains/product.md`, and `docs/decisions/INDEX.md`; a clean-snapshot render may prove an expected member unchanged but may not introduce an unlisted path. Inspect the query, scenario, product-boundary, and future-capability paragraphs in every changed rendered document for consistent meaning, then run `./awf check`; expect zero drift and zero findings.

Transition the ADR to Implementing and apply one intentional atomic batch containing: update `product/product-boundary:symbolic-analysis-only`; add `product/mathematical-input-contract:explicit-mathematical-queries`; add `product/mathematical-analysis-model:assumption-aware-query-reasoning`; add `product/mathematical-analysis-model:exact-query-values-and-infinity`; and add `product/analysis-report-contract:qualified-query-conclusions`. The claims become current together only after Python and Pi expose the coordinated product contract. Preserve the later terminal `Implemented` status-only transition for post-implementation assurance.

### Phase close

Focused evidence: run `npm run test:pi`, `uv run --locked pytest tests/unit/test_formula_queries.py tests/unit/test_formula_scenarios.py tests/e2e/test_formula_analysis.py tests/e2e/test_formula_system_analysis.py`, and the Task 7.3 render checks. Close when the registered Pi tool proves the AFMM tail identity and its qualified behavior without changing submitted work, the strict Python/adapter/TypeScript schemas agree, current-state claims are Applied, generated prose is semantically consistent, and `./scripts/check` passes.

```commit
feat(pi): expose bounded mathematical formula queries
```

## Definition of done

- `dod: exact-foundation` Exact decimals, rationals, signed infinity, finite/infinite work separation, and source-aware diagnostics are bounded, safe, and covered without regressing finite formula analysis.
- `dod: equivalence-queries` Optional general-context queries target the main expression or one named equation RHS, and domain-aware equivalence returns only conservatively qualified conclusions with local provenance.
- `dod: closed-form-queries` Supported finite and infinite sums produce verified conditional closed forms, including the AFMM omitted-tail identity, while divergent or unsupported sums remain qualified.
- `dod: property-limit-queries` Valid domain, singularities, sign, real and integer monotonicity, and directional limits use global assumptions and distinguish proved, disproved, unresolved, and inapplicable cases.
- `dod: asymptotic-queries` Bounded univariate mathematical asymptotic forms are verified and remain distinct from scenario direct-work growth.
- `dod: exact-real-scenarios` Fixed values, finite choices, and finite open or closed intervals support bounded exact real values, obey global assumptions, and do not execute queries.
- `dod: pi-query-product` The Python API and registered Pi tool expose one strict matching query contract, preserve no-query behavior and submitted work, pass AFMM-like acceptance, and ship synchronized guidance and current-state authority.

## Notes

Read-only continuity context: `.awf/efforts/<slug>/memory.md` for the active owning effort.

The ADR's state operations are intentionally deferred to the coordinated product phase because their claims describe the complete Python and Pi contract. Earlier independently green commits remain implementation preparation under the reviewed Proposed ADR; Phase 7 performs the first Implementing and Applied lifecycle transaction. Record implementation deviations, review findings, and any narrowed supported mathematical family here without strengthening the approved public boundary.

- Plan review, user-approved sequencing: move protocol-version-3 adapter, bridge, readiness, and validator compatibility for populated diagnostic and non-finite-work fields into Phase 1 so that phase stays independently green. The same atomicity rule places empty query-result compatibility in protocol version 4 during Phase 2 and exact-scenario transport in version 5 during Phase 6; Phase 7 exposes Pi query requests and populated answers as version 6.
- Plan review, reasoned specification: made exact scalar, infinity, work applicability, diagnostic spans, query unions/results, temporary consumers, backend-call bounds, equivalence rules, series rules, property/limit rules, asymptotic rules, and exact interval semantics executable in the Architecture summary and owning tasks.
- Plan review, mathematical correction: the AFMM tail is nonnegative on `p >= 0` and `0 <= q < 1`; strict positivity requires `q > 0` or `p == 0`.
- Plan review, mechanical settlement: added generated topic/domain paths, focused commands plus the project gate to each phase close, status-accurate ADR wording, and this effort-memory citation.
- Verify-pass residual settlement: enumerated the exact finite/non-finite variants at `AnalysisSuccess`, `EquationReport`, and `SystemReport`; fixed diagnostic null/serialization rules; specified strict request, target, property-check, answer, evidence, and derived-candidate unions; and added the protocol-sensitive registered-tool fixture to Phases 1, 2, and 6. These corrections close the residual reasoned and mechanical findings without changing the approved boundary; the governed workflow permits no second same-artifact review.
- Phase 1 settlement: scenarios over non-finite direct work fail with source identity and the supported alternative to remove scenarios, because the existing scenario result contract represents only work specializations and cannot report a null work value. Regression fixtures in `tests/unit/test_formula_scenarios.py` are a necessary added path. Review fixes also preserve Unicode-safe decimal source lexemes and maximum-size scalar fractions, enforce pre- and post-reduction exact-value bounds and nested direct-work invariants, reserve `oo` across mathematical identifiers, classify direct and every definition-substituted infinity as non-finite work, reject infinity recursively in finite output domains, primitive work, and scenario work definitions, preserve required protocol nulls, retain actual end-exclusive diagnostic spans in UTF-8 byte columns while leaving unavailable precision null, and correlate the protocol-v3 validators through the report hierarchy.
