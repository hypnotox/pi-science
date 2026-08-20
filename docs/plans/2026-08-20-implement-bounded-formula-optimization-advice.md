---
format: plan-v2
date: 2026-08-20
adrs:
  - adopt-bounded-formula-optimization-advice
status: Proposed
---
# Plan: Implement bounded formula optimization advice

## Goal

Ship default-on, bounded, proved lower-work formula suggestions for ordinary expression and equation-system analysis in direct Python and Pi, including the approved local, hoisting, sharing, and Horner families. Preserve submitted analysis and return qualified partial advice rather than adding arbitrary rewrite search, approximation, numerical-stability claims, runtime prediction, hardware modeling, or algorithm replacement.

## Architecture summary

Keep the retained submitted computation authoritative. Add `optimization.max_suggestions` only to `AnalysisRequest`, default it to 3, accept 0 through 16, and put one typed `OptimizationReport` on `AnalysisSuccess` so expressions and systems share the contract. Each suggestion carries a typed family, expression or equation target, normalized original and proposed forms, deterministic child-index occurrence paths with active binders or output indices, optional generated intermediate, checked exact-symbolic evidence and assumptions, whole-computation aggregate work before and after, positive savings, and the finite-precision reassociation qualification. A report separately states whether bounded search completed.

Refactor the existing system-local string diagnostic into one private bounded occurrence-and-scope detector that continues to feed `SystemReport.extraction_opportunities`. Build private capture-safe optimization candidates from retained parsed computations. A candidate may contain generated intermediates with explicit evaluation scope; semantic verification expands those intermediates only through checked substitution, while work analysis charges each intermediate at its actual binder or output-domain multiplicity. Extract the needed bounded mapped-output equivalence and aggregate-work ordering seams from comparison rather than reparsing renderings or duplicating policy.

Run a deterministic Python pipeline after ordinary analysis and before result bounding: detect, generate, capture-check, analyze transformed work, verify every retained output, prove positive savings over declared domains, deduplicate, rank unconditional suggestions before conditional suggestions, truncate to the request limit, and render. Unknown or unavailable costs, nonpositive or incomparable savings, unresolved equivalence, and exhausted candidates do not publish. Independent inspection, candidate, transformation, proof, work, and advice-byte budgets preserve the original result and produce an explicit incomplete-search qualification. The prior 262,144-byte base-result allowance remains intact; a separate 65,536-byte optimization allowance raises the combined Python and framed Pi ceilings without allowing advice to consume base-report capacity.

Implement bounded family generators directly over the internal expression model. Repeated extraction, repeated-call and reciprocal reuse, factoring, redundant-operation removal, and invariant hoisting use the shared occurrence and scope model. Cross-equation sharing requires compatible free-index interfaces and an acyclic generated producer. Horner generation uses a checked bounded polynomial backend seam, deterministic variable selection, explicit degree, term, and node ceilings, and an independent equivalence proof; sparse or other forms that do not lower the adopted work metric are filtered out.

Python remains the sole mathematical-policy owner. Advance the private protocol, generated schema, strict TypeScript request/result validation, compact rendering, package skill, examples, and current-state documentation without recomputing applicability, proof, work, or ranking in Pi.

## Phase 1: Establish reusable occurrence and comparison foundations

**Execution mode: subagent-driven.**

Completes: ["preserved-optimization-foundation"]

### Task 1.1: Freeze existing behavior and introduce typed occurrence and scope detection
Kind: batch
Applying: ["adopt-bounded-formula-optimization-advice:python-owned-proof-and-ranking", "adopt-bounded-formula-optimization-advice:backend-independent-policy"]
Paths: ["docs/decisions/adopt-bounded-formula-optimization-advice.md", "docs/decisions/INDEX.md", ".awf/awf.lock", "packages/py-science-formula/src/py_science/formula/expressions.py", "packages/py-science-formula/src/py_science/formula/service.py", "packages/py-science-formula/src/py_science/formula/optimization.py", "tests/unit/test_formula_optimization.py", "tests/e2e/test_formula_analysis.py", "tests/e2e/test_formula_system_analysis.py"]
Representative: The new detector reports two identical `x[i] + 1` occurrences with stable equation and child-index paths plus active output and `Sum` binders, while the existing extraction diagnostic renders exactly the same public string as before.
Edge: Cover expression and system roots, deterministic equation order, binary children, call arguments, sum bounds versus body scope, nested and shadowed binders, indexed values, named producer references, structurally equal nodes in incompatible scopes, capture collisions, traversal exhaustion, and inputs with no repeated nodes. Do not add optimization fields or suggestions in this task.
Post-check: Run the new optimization unit suite and existing expression/system suites. Require pre-refactor and post-refactor model dumps to match for representative expression, repeated-expression system, nested-sum, dependency, scenario, and query requests; require the detector's bounded-exhaustion tests to terminate with no public analysis change and `git diff --check` to exit 0.

Transition ADR-adopt-bounded-formula-optimization-advice from Proposed to Accepted through the ADR lifecycle workflow without applying any State change. Add characterization tests before changing the detector. Introduce a private immutable occurrence record with target identity, tuple child path, normalized structural expression, free symbols, active binders or output indices, and compatible evaluation scope. Move repeated-node traversal out of `_extraction_opportunities`; keep that function as the compatibility renderer over the typed detector until the new report lands. Centralize scope traversal with the existing sum-binding rule: bounds are outside the new binder and only the body owns it.

### Task 1.2: Extract reusable semantic and aggregate-work comparison seams
Kind: batch
Applying: ["adopt-bounded-formula-optimization-advice:python-owned-proof-and-ranking", "adopt-bounded-formula-optimization-advice:independently-bounded-search", "adopt-bounded-formula-optimization-advice:backend-independent-policy"]
Paths: ["packages/py-science-formula/src/py_science/formula/comparison.py", "packages/py-science-formula/src/py_science/formula/equivalence.py", "packages/py-science-formula/src/py_science/formula/reasoning.py", "packages/py-science-formula/src/py_science/formula/work.py", "packages/py-science-formula/src/py_science/formula/service.py", "tests/e2e/test_formula_candidate_comparison.py", "tests/unit/test_formula_queries.py", "tests/e2e/test_formula_analysis.py", "tests/e2e/test_formula_system_analysis.py"]
Representative: Existing candidate comparison proves mapped rational outputs equal under the required denominator condition and orders their retained aggregate work through extracted internal functions, with its public result unchanged.
Edge: Cover scalar expressions, indexed equations, positional binder alignment, lexical sums, denominator conditions, assumption-qualified identity, semantic disproof, unresolved equivalence, unknown primitive costs, non-finite work, multivariate or otherwise incomparable work, and expansion or reasoning overflow. Do not add optimization-specific candidate or outcome types in this phase.
Post-check: Run comparison, query, expression, and system suites. Compare all existing candidate-comparison and equivalence-query serialized results before and after extraction; require each new seam to have an existing production caller and `git diff --check` to exit 0.

Extract bounded mapped-output expansion and equivalence plus aggregate-work sign reasoning from comparison into internal reusable functions. Keep comparison as their first production consumer, preserve its public truth tables and error handling, and keep backend proof and ordering policy behind Python-owned typed inputs rather than rendered strings. Optimization-specific transformed computations, generated intermediates, and accepted, rejected, or exhausted outcomes land only with their first ordinary-analysis consumer in Phase 2.

### Phase close

Run focused Python suites, pyright, ruff, the full project gate, and `git diff --check`. Authority check: the ADR is Accepted with no Applied operations. State check: public request and report dumps remain unchanged, existing extraction strings remain unchanged, and existing comparison and query production flows consume the extracted proof and work seams.

```commit
refactor(formula): establish optimization analysis seams
```

## Phase 2: Ship the direct Python optimization contract and local families

**Execution mode: subagent-driven.**

Advances: ["complete-initial-optimization-families", "synchronized-optimization-guidance"]
Completes: ["python-optimization-contract", "strict-pi-optimization"]

### Task 2.1: Define the strict request and qualified report through failing tests
Kind: batch
Applying: ["adopt-bounded-formula-optimization-advice:default-bounded-advice", "adopt-bounded-formula-optimization-advice:qualified-informational-results", "adopt-bounded-formula-optimization-advice:independently-bounded-search", "adopt-bounded-formula-optimization-advice:backend-independent-policy"]
Paths: ["packages/py-science-formula/src/py_science/formula/models.py", "packages/py-science-formula/src/py_science/formula/__init__.py", "packages/py-science-formula/src/py_science/formula/service.py", "tests/unit/test_formula_optimization.py", "tests/e2e/test_formula_analysis.py", "tests/e2e/test_formula_system_analysis.py", "tests/unit/test_error_translation.py", "tests/distribution/test_python_package.py"]
Representative: An omitted optimization setting yields a top-level completed report requesting at most three suggestions; `{max_suggestions: 0}` yields a disabled empty report; 16 is accepted; negative, noninteger, 17, and surplus configuration keys fail at `optimization.max_suggestions`.
Edge: Fix the complete public truth table for disabled, complete with no opportunity, complete with suggestions, and incomplete search. Require every suggestion to have one supported kind, target, nonempty occurrences, original and proposed normalized forms, optional intermediate with invariant nullability, exact proof conclusion, evidence, conditions and used assumptions, work-before, work-after, positive savings, and reassociation qualification. Prohibit unresolved proof, unknown work, zero or negative savings, blockers on completed proof, and contradictory completion metadata.
Post-check: Add tests first and record the absent-model failures. Implement only models and orchestration skeleton, then require remaining failures to identify absent generators rather than invalid fixtures. Run the named suites, inspect Pydantic error locations and JSON schema defaults/minimum/maximum, and assert candidate-comparison and dominance request schemas contain no optimization field.

Add strict frozen `OptimizationConfig`, target, occurrence, intermediate, suggestion, and report models. Put `optimization` only on `AnalysisRequest` and the report only on `AnalysisSuccess`; export the public types. Structural paths are tuples of nonnegative child indices rooted at the expression or named equation RHS. A report records requested limit, status `disabled`, `complete`, or `incomplete`, ordered suggestions, and bounded qualifications; disabled requires limit zero, while incomplete requires a search-exhaustion qualification. Make fewer suggestions than requested valid in every status. Attach optimization only after the retained ordinary analysis and query results exist, and keep result bounding aware that advice can be discarded or shortened without replacing the base success.

### Task 2.2: Implement repeated extraction, reuse, factoring, and invariant hoisting
Kind: batch
Applying: ["adopt-bounded-formula-optimization-advice:initial-proved-families", "adopt-bounded-formula-optimization-advice:python-owned-proof-and-ranking", "adopt-bounded-formula-optimization-advice:qualified-informational-results", "adopt-bounded-formula-optimization-advice:independently-bounded-search"]
Paths: ["packages/py-science-formula/src/py_science/formula/optimization.py", "packages/py-science-formula/src/py_science/formula/expressions.py", "packages/py-science-formula/src/py_science/formula/sympy_backend.py", "packages/py-science-formula/src/py_science/formula/service.py", "packages/py-science-formula/src/py_science/formula/work.py", "tests/unit/test_formula_optimization.py", "tests/e2e/test_formula_analysis.py", "tests/e2e/test_formula_system_analysis.py"]
Representative: Analyze an expression with a repeated iterator-invariant rational call and return a proved suggestion that introduces one intermediate at the narrowest legal outer scope, preserves denominator conditions, and reports lower whole-expression aggregate work after sum cardinality is included.
Edge: Cover repeated binary forms, calls with definitions, scalar primitive costs, unknown generic calls, reciprocal reuse with nonzero conditions, local common-factor extraction, neutral-operation elimination accepted by the submitted dialect, invariant and variant sum bodies, nested sums, output-domain multiplicity, same syntax in incompatible scopes, reassociation qualification, already-minimal forms, and transformations whose local node count falls but aggregate work does not. Unknown calls, unresolved cardinality, unproved equivalence, and nonpositive savings publish nothing.
Post-check: Run optimization plus expression/system suites. For every family, assert the normalized replacement reparses through project-owned restricted syntax where it is publicly rendered, independent equivalence evidence succeeds, and the reported aggregate-work values match direct internal analysis of original and candidate. Assert ordinary interpretations, operation counts, work, scenarios, queries, dependencies, reuse, and extraction diagnostics are unchanged when suggestions are enabled or disabled.

Define the private optimization candidate computation with retained output mappings, transformed expressions or equations, and generated intermediates with collision-free names and explicit evaluation scope. Semantic verification expands intermediates for proof only; work evaluation charges them at their actual scope multiplicity. Typed accepted, rejected, and exhausted outcomes keep unsupported proof distinct from absence. Implement bounded family-specific generators, not a generic rewrite registry or unrestricted backend simplifier. Use the typed detector for repeated expressions and identical calls; recognize reciprocal structure only through the internal binary model and preserve nonzero obligations. Use checked backend factoring only after a bounded rational preflight and independently verify the generated candidate. Hoist only across binders absent from the candidate's free-symbol set and place the generated intermediate at the narrowest compatible scope. Every generator returns candidates to the common verifier and cannot publish directly.

### Task 2.3: Regenerate the schema and transport the public contract atomically
Kind: batch
Applying: ["adopt-bounded-formula-optimization-advice:default-bounded-advice", "adopt-bounded-formula-optimization-advice:qualified-informational-results", "adopt-bounded-formula-optimization-advice:independently-bounded-search", "adopt-bounded-formula-optimization-advice:backend-independent-policy"]
Paths: ["packages/py-science-formula/src/py_science/formula/models.py", "packages/py-science-formula/src/py_science/formula/service.py", "scripts/generate-pi-formula-schema.py", "packages/pi-science/src/formula-schema.json", "packages/pi-science/bridge/formula_adapter.py", "packages/pi-science/src/bridge.ts", "packages/pi-science/src/provision.ts", "tests/e2e/test_formula_analysis.py", "tests/e2e/test_formula_system_analysis.py", "tests/test_pi_schema_generation.py", "packages/pi-science/tests/adapter.test.ts", "packages/pi-science/tests/bridge.test.ts", "packages/pi-science/tests/provision.test.ts", "packages/pi-science/tests/start.test.ts"]
Representative: The real adapter and strict bridge round-trip an omitted optimization config as default three, a disabled request, and a populated local-family expression and system report with structural occurrences, conditions, exact-symbolic evidence, aggregate-work savings, reassociation qualification, and completion status.
Edge: Preserve candidate-comparison and dominance schema branches without optimization. Reject missing, surplus, over-bound, miscorrelated, contradictory, or invalid optimization result fields; preserve explicit nulls; accept fewer suggestions than requested and qualified incomplete results; and never recompute proof, work deltas, ordering, or applicability in TypeScript. Preserve a base analysis valid at the prior 262,144-byte maximum while fitting the mandatory minimum optimization report.
Post-check: Regenerate the schema and run schema, adapter, bridge, provisioning, registered-tool, and prior-maximum-base regression suites. Require fresh generation to match the committed artifact, assert the request schema default/minimum/maximum and strict ordinary-only placement, prove the separate advice allowance preserves the prior base population, and run a protocol-version census whose only prior-version occurrence is the intentional incompatible-envelope fixture.

Advance live Python and TypeScript protocol constants together. Extend strict TypeScript request/result types, validators, source accounting, and request/result correlation. Preserve the prior 262,144-byte base-result allowance, add a separate 65,536-byte optimization allowance, set the combined Python ceiling to 327,680 bytes, and set the framed Pi response ceiling to 327,936 bytes. The minimum valid optimization report always fits the separate allowance; suggestions truncate within it. TypeScript validates transport shape and ordered population bounds but does not parse algebra or decide that a suggestion is beneficial. The model, generated schema, adapter, strict bridge, and coupled result ceilings land in this same phase transaction so no checked-in schema drift or base-result regression exists at phase close.

### Task 2.4: Apply the live contract and update invalidated documentation
Kind: batch
Applying: ["adopt-bounded-formula-optimization-advice:default-bounded-advice", "adopt-bounded-formula-optimization-advice:initial-proved-families", "adopt-bounded-formula-optimization-advice:python-owned-proof-and-ranking", "adopt-bounded-formula-optimization-advice:qualified-informational-results", "adopt-bounded-formula-optimization-advice:independently-bounded-search", "adopt-bounded-formula-optimization-advice:backend-independent-policy"]
Paths: ["docs/decisions/adopt-bounded-formula-optimization-advice.md", "docs/decisions/INDEX.md", ".awf/topics/parts/product/product-boundary/current-state.md", ".awf/topics/parts/product/mathematical-input-contract/current-state.md", ".awf/topics/parts/product/analysis-report-contract/current-state.md", ".awf/topics/parts/product/mathematical-analysis-model/current-state.md", "docs/topics/product/product-boundary.md", "docs/topics/product/mathematical-input-contract.md", "docs/topics/product/analysis-report-contract.md", "docs/topics/product/mathematical-analysis-model.md", ".awf/parts/agents-doc/identity.md", "AGENTS.md", ".awf/docs/parts/architecture/overview.md", ".awf/docs/parts/architecture/data-flow.md", ".awf/docs/parts/testing/tiers.md", ".awf/docs/parts/testing/layout.md", "docs/architecture.md", "docs/testing.md", "docs/analysis-model.md", "docs/vision.md", "README.md", "packages/py-science-formula/README.md", "packages/pi-science/skills/formula-analysis/SKILL.md", ".awf/awf.lock"]
Representative: Current-state authority and public guidance describe the shipped default-on Python/Pi contract, the delivered local extraction, reuse, factoring, and hoisting families, proof-positive abstract-work semantics, incomplete-search behavior, and the still-pending cross-equation and Horner family completion.
Edge: Remove stale statements that all rewrites, hoisting effects, or improvement ranking remain future work; preserve broader rewrite search, resource models, empirical performance, and code generation as deferred. Correct the pre-existing false claim that dominance Pi transport is pending. Do not describe Phase 3 families as shipped before they land.
Post-check: Run `./awf render`; read back every authored and rendered path; execute documented local-family examples; require current protocol and product statements to agree; require no stale dominance-transport-pending wording; and require `./awf check`, `./awf check staged`, the focused documentation tests, and `git diff --check` to pass.

Transition the ADR from Accepted to Implementing and append one Applied event containing exactly all four declared State changes alongside their pair-atomic claim mutations. Keep the new claims family-neutral where their durable rule is generic; enumerate only the Phase 2 delivered families in current capability prose that is updated again in Phase 3. Synchronize the generated agent identity, architecture, testing guide, analysis model, vision, root and package guides, and product skill with the live protocol and contract. No terminal lifecycle flip occurs.

### Phase close

Run focused optimization, expression, system, error, distribution, schema, adapter, bridge, provisioning, registered-tool, documentation, and example tests; pyright; ruff; TypeScript checking and formatting; `./awf check`; `./awf check staged`; the protocol and stale-language censuses; the full gate; and `git diff --check`. State check: direct Python and Pi default to three, zero disables, local-family suggestions are proved lower over declared domains, the prior base-result population remains valid, enabling advice changes no submitted analysis field, fresh schema generation matches the committed artifact, and all invalidated documentation is current. Authority check: the ADR is Implementing and its Applied partition exactly equals all four State changes.

```commit
feat(formula): add optimization advice contract
```

## Phase 3: Complete system sharing, Horner reformulation, ranking, and resilience

**Execution mode: subagent-driven.**

Completes: ["complete-initial-optimization-families"]

### Task 3.1: Add compatible cross-equation sharing and bounded Horner generation
Kind: batch
Applying: ["adopt-bounded-formula-optimization-advice:initial-proved-families", "adopt-bounded-formula-optimization-advice:python-owned-proof-and-ranking", "adopt-bounded-formula-optimization-advice:qualified-informational-results", "adopt-bounded-formula-optimization-advice:independently-bounded-search"]
Paths: ["packages/py-science-formula/src/py_science/formula/optimization.py", "packages/py-science-formula/src/py_science/formula/sympy_backend.py", "packages/py-science-formula/src/py_science/formula/service.py", "packages/py-science-formula/src/py_science/formula/work.py", "tests/unit/test_formula_optimization.py", "tests/e2e/test_formula_analysis.py", "tests/e2e/test_formula_system_analysis.py", "docs/analysis-model.md", "docs/vision.md", "README.md", "packages/py-science-formula/README.md", "packages/pi-science/skills/formula-analysis/SKILL.md"]
Representative: A system with the same indexed computation in two compatible equation RHSs receives one acyclic generated producer at the shared free-index domain; a dense polynomial receives a deterministic Horner candidate only when its verified whole-computation work is lower.
Edge: For sharing, cover scalar and indexed common forms, equal and unequal arity, renamed positional indices, incompatible output bounds, predecessor-dependent domains, equation-local constraints, existing producer dependencies, cycles, lexical sums, and generated-name collisions. For Horner, cover deterministic variable choice, coefficient symbols, exact rational coefficients, dense and sparse polynomials, powers counted under the adopted metric, bounded degree and terms, multivariate forms outside the supported family, backend or node overflow, already-Horner forms, and finite-precision qualification.
Post-check: Run optimization and system suites. Assert generated shared producers preserve every original output under mapped-output proof and are charged once per compatible domain point. Assert every Horner fixture has independent exact-symbolic evidence and positive reported savings, while sparse, over-bound, ambiguous-variable, or higher-work candidates produce no suggestion or a bounded incomplete-search qualification as appropriate.

Generate a cross-equation intermediate only when all occurrences admit one compatible free-index interface and inserting its producer preserves the validated acyclic graph. Do not inline unrelated equations or rewrite submitted dependency reports. Add a checked backend Horner seam with explicit public-diagnostic limits for target nodes, polynomial variable count, degree, terms, and intermediate nodes. Deterministically inspect eligible variables and candidates, but let the common work proof decide publication. In the same phase transaction, update every guide that enumerates supported families so cross-equation sharing and Horner become current only when their implementation lands; the already Applied family-neutral claims need no lifecycle event unless their prose materially changes.

### Task 3.2: Finalize deterministic selection and search budgets
Kind: batch
Applying: ["adopt-bounded-formula-optimization-advice:default-bounded-advice", "adopt-bounded-formula-optimization-advice:python-owned-proof-and-ranking", "adopt-bounded-formula-optimization-advice:qualified-informational-results", "adopt-bounded-formula-optimization-advice:independently-bounded-search"]
Paths: ["packages/py-science-formula/src/py_science/formula/optimization.py", "packages/py-science-formula/src/py_science/formula/models.py", "packages/py-science-formula/src/py_science/formula/service.py", "packages/py-science-formula/src/py_science/formula/work.py", "tests/unit/test_formula_optimization.py", "tests/e2e/test_formula_analysis.py", "tests/e2e/test_formula_system_analysis.py", "tests/distribution/test_python_package.py"]
Representative: A request with overlapping unconditional and assumption-dependent opportunities returns at most three deduplicated suggestions, unconditional first, descending only where savings are provably comparable, then stable family, target, and structural-path tie-breaks without claiming superiority for incomparable deltas.
Edge: Cover duplicate candidates from several families, identical replacements at overlapping scopes, exact equal savings, conditionally comparable and incomparable symbolic savings, max values 0, 1, 3, and 16, candidate-pool exhaustion, traversal exhaustion, proof-step exhaustion, transformation-node exhaustion, work-node exhaustion, and multibyte rendering near the separate advice limit. Recover only typed exhausted, unsupported, backend-refusal, and advice-size outcomes; unexpected exceptions remain observable and test-failing.
Post-check: Run deterministic repeated-process probes over the full suggestion population, request-limit property tests, and each independent search-budget fixture. Require identical ordered JSON across runs; require every `incomplete` result to name measured and configured bounds; require `complete` with no suggestions to avoid any global-optimality claim; and require unexpected injected defects to propagate to the test harness.

Set fixed independent constants for inspected nodes, generated candidates, per-candidate and aggregate transformation nodes, proof steps and nodes, and work-comparison nodes within the Phase 2 advice allowance. Deduplicate by semantic target, placement, and normalized transformation rather than display text. Use proved work relations for ordering when available; otherwise use stable non-superiority tie-breaks. Catch only the typed expected optimization outcomes named above.

### Phase close

Run all Python formula suites, schema determinism, adapter and bridge tests, documentation examples, pyright, ruff, TypeScript checking, the full gate, and `git diff --check`. State check: all six approved families are present, enumerative guidance is current, ordering is deterministic, every publication is proved lower whole-computation work, and every expected search budget preserves the base result. Authority check: the ADR remains Implementing with all four State changes Applied; append a Reapplied event only if an already Applied claim materially changes in this phase.

```commit
feat(formula): complete optimization advice
```

## Phase 4: Present, document, and apply the capability

**Execution mode: subagent-driven.**

Completes: ["synchronized-optimization-guidance"]

### Task 4.1: Render compact advice and synchronize product guidance
Kind: batch
Applying: ["adopt-bounded-formula-optimization-advice:default-bounded-advice", "adopt-bounded-formula-optimization-advice:initial-proved-families", "adopt-bounded-formula-optimization-advice:python-owned-proof-and-ranking", "adopt-bounded-formula-optimization-advice:qualified-informational-results", "adopt-bounded-formula-optimization-advice:independently-bounded-search", "adopt-bounded-formula-optimization-advice:backend-independent-policy"]
Paths: ["packages/pi-science/src/index.ts", "packages/pi-science/skills/formula-analysis/SKILL.md", "packages/pi-science/tests/start.test.ts", "packages/pi-science/tests/package.test.ts", "README.md", "packages/py-science-formula/README.md", "docs/analysis-model.md", "docs/architecture.md", "docs/testing.md"]
Representative: Compact tool text shows the best proved suggestion with target, replacement or intermediate, work savings, conditions, and finite-precision qualification, shows how many additional suggestions remain in canonical `details`, and distinguishes no opportunity from incomplete search.
Edge: Preserve ordinary interpretation and work ordering in compact text, never hide qualifications, never call abstract work speed or optimality, keep disabled output quiet, localize incomplete-search guidance, and document unknown-cost omission, conditional ordering, Horner filtering, the 0 through 16 control, structured details, and excluded runtime, numerical, approximate, and arbitrary algorithm claims.
Post-check: Run `./awf render`; read back every authored and rendered topic/document in `Paths`; execute all documented Python examples and representative Pi callback fixtures; require no stale statement that local rewrites, hoisting effects, or improvement ranking remain future work. Run a checked search proving the only remaining optimization roadmap language is intentionally broader future work, and prove no stale dominance-transport-pending wording remains in tracked current-state documentation.

Add compact optimization presentation without changing canonical details or Python-owned policy. Finalize guidance around the complete family set, requested-versus-returned counts, incomplete search, exact-symbolic finite-precision qualification, and abstract-work meaning. Keep deeper whole-system optimization, stage and resource models, arbitrary rewrites, empirical performance, and formula-to-code deferred. The ADR remains Implementing with its Phase 2 Applied partition; mutate a claim and append a matching Reapplied event only if compact presentation exposes a material current-state correction rather than merely changing guidance.

### Phase close

Run all Python and Pi suites, schema determinism, pyright, ruff, TypeScript checking and formatting, `./awf check`, `./awf check staged`, the full project gate, stale-language censuses, documented examples, and `git diff --check`. Perform focused semantic review of generated current-state prose and compact output, recording inspected boundaries and results in Notes. Authority check: the ADR remains Implementing and its Applied partition exactly equals the four State changes, with any Phase 4 Reapplied event pair-atomic with a material claim correction. State check: Python, Pi, schema, protocol, compact text, canonical details, package skill, examples, current-state topics, architecture, testing guide, and product documentation agree on the shipped bounded capability and exclusions.

```commit
feat(pi): present formula optimization advice
```

## Definition of done

- `dod: preserved-optimization-foundation` One bounded typed occurrence and scope detector plus reusable semantic-proof and aggregate-work comparison seams preserve every existing ordinary analysis, query, comparison, dominance, and extraction-diagnostic behavior.
- `dod: python-optimization-contract` Direct Python ordinary requests default to at most three suggestions, accept `optimization.max_suggestions` from 0 through 16, and return one strict top-level qualified report for expressions and systems without exposing the field on comparison or dominance requests.
- `dod: complete-initial-optimization-families` Repeated extraction, iterator-invariant hoisting, repeated-call and reciprocal reuse, safe factoring and redundant-operation removal, compatible cross-equation sharing, and bounded Horner generation publish only independently proved exact-symbolic candidates with positive whole-computation aggregate-work savings, deterministic ranking, conditions, and finite-precision qualifications.
- `dod: strict-pi-optimization` The generated provider schema, bounded versioned adapter, exact TypeScript bridge, and readiness-gated tool transport and correlate the request and report while preserving all existing request variants and leaving mathematical policy in Python.
- `dod: synchronized-optimization-guidance` Compact output, canonical details, package skill, public guides, examples, Applied current-state claims, architecture, testing documentation, and ADR history consistently describe default bounded advice, partial-search semantics, abstract-work meaning, and exclusions; the full gate passes.

## Notes

Inline owners immediately correct stale instructions and record reasoned deviations here. Delegated owners may report rather than edit; the parent supplies the report to phase review and reconciles it with findings in one focused post-review settlement commit before checkpointing or later execution. Record characterization baselines, test-first failures, configured optimization budgets, family-specific proof fixtures, deterministic-ranking evidence, protocol census, documented-example execution, generated-prose meaning review, compact-output inspection, review findings, and deviations surfaced during implementation.

- Plan-review reasoned disposition: land the public Python request/report model, generated schema, protocol advance, and strict Pi transport in one Phase 2 transaction so every phase closes without schema drift. Preserve the prior 262,144-byte base-result allowance, add a separately bounded 65,536-byte optimization allowance, and raise the combined Python and framed Pi ceilings in that same transaction so the mandatory minimum report cannot invalidate an old maximum-size success. Recover only typed bounded or unsupported optimization outcomes; unexpected defects remain observable.
- Phase 1 evidence: characterization and focused occurrence, expression, system, query, and candidate-comparison suites preserve the existing extraction text and public comparison behavior; typed occurrence traversal exhaustion remains diagnostic-only.
- Phase 1 review settlement: bind output indices when computing occurrence free symbols; retain lexical binder identity, paths, and bounds plus output-domain interfaces so shadowed or incompatible scopes remain distinct; skip named-producer subtrees deterministically. Replace the expression-equivalence alias with one typed mapped-output expansion, interface-alignment, and proof seam consumed by comparison. Move full zero, constant-sign, sign-chart, crossover, condition, and unresolved aggregate-work policy behind a typed relation that uses bounded rational normalization rather than rendered text. Expanded focused coverage includes output bindings, call paths, shadowing, domain incompatibility, producer references, no-repeat input, mapped outputs, unknown and non-finite work, and crossover behavior.
- Plan-review verify-pass residual disposition: apply all four family-neutral current-state operations and update every contract, protocol, architecture, testing, identity, package, and skill document invalidated by Phase 2 in that phase's atomic commit. Later phases update enumerative guidance with newly delivered families and use Reapplied history only for a material correction to already Applied claim prose.
