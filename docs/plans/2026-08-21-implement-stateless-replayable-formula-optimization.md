---
format: plan-v2
date: 2026-08-21
adrs: [adopt-stateless-replayable-formula-optimization-plans]
status: Proposed
---
# Plan: Implement stateless replayable formula optimization

## Goal

Let agents explicitly request bounded optimization and receive independently verified, complete stateless candidates that can be submitted again to ordinary analysis or candidate comparison. Preserve ordinary default-on advice, the existing abstract unit-work objective, exact-symbolic qualifications, and Python ownership of mathematical policy; do not add source edits, configurable families, composed search, new cost objectives, algorithm replacement, or numerical optimization.

## Architecture summary

Implement the reviewed ADR through three independently green transactions. First, extend the restricted project-owned expression model and ordinary analysis with bounded nonrecursive `Let(name, value, body)` semantics, including capture-free parsing, preserved rendering, mathematical lowering, work-once accounting, lexical traversal, resource bounds, and the first two current-state claim updates. Second, make the existing Python optimizer construct and reanalyse complete candidates internally for every shipped family while retaining the protocol-v12 advice projection; this removes hidden intermediate placement from the verification seam before any public transport shape changes. Third, atomically expose those candidates through `operation: optimize`, project the same plans through ordinary advice, add operation-specific failures, and migrate Python, generated schema, adapter, TypeScript validation, registered-tool presentation, guidance, current-state claims, and protocol version to v13.

A complete candidate carries a transformed expression or equation system, the formula context required to interpret it, and output identities. Direct Python candidates include the required syntax discriminator; Pi candidates use the established syntax-injected projection. Candidate context excludes scenarios, queries, and optimization controls. Pi validates shape and request/result correlation but never evaluates binding scope, equivalence, cost, applicability, ranking, or failure policy.

## Phase 1: Add bounded lexical binding to ordinary analysis

**Execution mode: subagent-driven.**

Completes: ["lexical-binding-analysis"]

### Task 1.1: Add failing lexical-binding contract regressions
Kind: batch
Applying: ["adopt-stateless-replayable-formula-optimization-plans:minimal-lexical-binding", "adopt-stateless-replayable-formula-optimization-plans:exact-symbolic-boundary"]
Paths: ["tests/unit/test_exact_values.py", "tests/unit/test_formula_queries.py", "tests/unit/test_formula_properties.py", "tests/unit/test_asymptotics.py", "tests/unit/test_formula_scenarios.py", "tests/unit/test_formula_optimization.py", "tests/e2e/test_formula_system_analysis.py", "packages/pi-science/tests/adapter.test.ts", "packages/pi-science/tests/bridge.test.ts"]
Representative: Parse and analyse `Let(t, x*x, t + t)` as one evaluation of `x*x` plus two reuse accesses, preserving the binding in normalized output while lowering it only for mathematical proof and query evaluation.
Edge: Cover malformed arity, a non-symbol name, self-reference, nested bindings, an enclosing `Sum` iterator visible in the value, the bound name visible only in the body, collision with a submitted symbol or iterator, a binding inside versus outside a `Sum`, output-index-dependent values, definitions and scenarios, property/query/asymptotic consumers, deep nesting, node ceilings, unknown primitive work, and nonfinite aggregate work. Add protocol-v12 real-adapter and strict-bridge round trips plus malformed-input transport behavior without moving lexical or mathematical validation into TypeScript. Existing expressions and `Sum` shadowing must remain unchanged.
Post-check: State check on the regression-only snapshot: run `uv run --locked pytest tests/unit/test_exact_values.py tests/unit/test_formula_queries.py tests/unit/test_formula_properties.py tests/unit/test_asymptotics.py tests/unit/test_formula_scenarios.py tests/unit/test_formula_optimization.py tests/e2e/test_formula_system_analysis.py -k 'let_binding or lexical_binding'` and `npx vitest run packages/pi-science/tests/adapter.test.ts packages/pi-science/tests/bridge.test.ts -t 'lexical Let|Let binding'`. Require only the new supported-binding and real-adapter round-trip assertions to fail because `Let` is still parsed as an ordinary call or rejected; malformed/capture/resource and transport-rejection controls plus all selected pre-existing tests must pass. Record exact failing identities and messages before production mutation.

### Task 1.2: Implement the typed binding, parser, renderer, and work semantics
Kind: batch
Applying: ["adopt-stateless-replayable-formula-optimization-plans:minimal-lexical-binding", "adopt-stateless-replayable-formula-optimization-plans:complete-candidate-verification"]
Paths: ["packages/py-science-formula/src/py_science/formula/expressions.py", "packages/py-science-formula/src/py_science/formula/parser.py", "packages/py-science-formula/src/py_science/formula/sympy_backend.py", "packages/py-science-formula/src/py_science/formula/analyzer.py", "packages/py-science-formula/src/py_science/formula/work.py", "packages/py-science-formula/src/py_science/formula/domains.py", "packages/py-science-formula/src/py_science/formula/service.py", "packages/py-science-formula/src/py_science/formula/models.py", "packages/py-science-formula/src/py_science/formula/__init__.py", "tests/unit/test_exact_values.py", "tests/unit/test_formula_scenarios.py", "tests/e2e/test_formula_system_analysis.py"]
Representative: Add one typed nonrecursive value/body node and recognize only `Let(<bare symbol>, <value>, <body>)`; render it canonically as `Let`, lower it capture-safely for represented-value mathematics, and charge the value once per evaluation of its lexical placement while references are reuse accesses.
Edge: The value sees enclosing iterators and equation-output indices but never its own name; the body sees the name; nested bindings compose; request-wide depth/node/source/name limits remain authoritative. Reserve `Let` in request-model callable validation so function definitions and primitive costs cannot assign it a competing meaning, with direct rejection coverage. Mathematical lowering must never replace binding-aware direct work. Moving the same binding across a `Sum` or output scope must observably change multiplicity. Keep arbitrary generic calls named `Let` unavailable so there is one meaning.
Post-check: State check: rerun the exact Task 1.1 population, then run `uv run --locked pytest tests/unit/test_exact_values.py tests/unit/test_formula_scenarios.py tests/e2e/test_formula_system_analysis.py`. Require canonical parse/render round trips, exact work-once results, lexical rejection cases, and every selected pre-existing test to pass.

### Task 1.3: Make every expression consumer binding-safe
Kind: batch
Applying: ["adopt-stateless-replayable-formula-optimization-plans:minimal-lexical-binding", "adopt-stateless-replayable-formula-optimization-plans:complete-candidate-verification"]
Paths: ["packages/py-science-formula/src/py_science/formula/optimization.py", "packages/py-science-formula/src/py_science/formula/mapped_outputs.py", "packages/py-science-formula/src/py_science/formula/series.py", "packages/py-science-formula/src/py_science/formula/reasoning.py", "packages/py-science-formula/src/py_science/formula/query.py", "packages/py-science-formula/src/py_science/formula/asymptotics.py", "packages/py-science-formula/src/py_science/formula/comparison.py", "packages/py-science-formula/src/py_science/formula/equivalence.py", "tests/unit/test_formula_queries.py", "tests/unit/test_formula_properties.py", "tests/unit/test_asymptotics.py", "tests/unit/test_formula_optimization.py", "tests/e2e/test_formula_candidate_comparison.py", "packages/pi-science/tests/adapter.test.ts", "packages/pi-science/tests/bridge.test.ts"]
Representative: Route occurrence discovery, producer expansion, renaming, reasoning substitution, series/query walks, equivalence, and comparison through binding-aware traversal so no union dispatcher falls through to binary-expression assumptions or captures the bound name.
Edge: Query families may return their existing qualified unsupported result when a binding cannot be lowered within their bounds, but must not crash, erase lexical work, or reinterpret `Let` as a generic mathematical call. Candidate comparison expands bindings for represented-value equivalence while retaining binding-aware work. Protocol-v12 adapter and bridge tests must transport the Python-owned valid result and bounded malformed-input diagnostic without interpreting lexical scope.
Post-check: State check: run `uv run --locked pytest tests/unit/test_formula_queries.py tests/unit/test_formula_properties.py tests/unit/test_asymptotics.py tests/unit/test_formula_optimization.py tests/e2e/test_formula_candidate_comparison.py -k 'let_binding or lexical_binding'`, then the complete five files and `npx vitest run packages/pi-science/tests/adapter.test.ts packages/pi-science/tests/bridge.test.ts -t 'lexical Let|Let binding'`. Require all new lexical consumers, real-adapter and strict-bridge cases, and all pre-existing query, property, asymptotic, optimization, and comparison behavior to pass.

### Task 1.4: Apply the lexical-input claims and document the restricted form
Kind: batch
Applying: ["adopt-stateless-replayable-formula-optimization-plans:minimal-lexical-binding", "adopt-stateless-replayable-formula-optimization-plans:exact-symbolic-boundary"]
Paths: ["docs/decisions/adopt-stateless-replayable-formula-optimization-plans.md", ".awf/topics/parts/product/mathematical-input-contract/current-state.md", "docs/topics/product/mathematical-input-contract.md", "docs/analysis-model.md", "README.md", "packages/py-science-formula/README.md", "packages/pi-science/skills/formula-analysis/SKILL.md", "packages/pi-science/tests/package.test.ts", "docs/decisions/INDEX.md", ".awf/awf.lock"]
Representative: Transition the ADR to Implementing and apply exactly `product/mathematical-input-contract:safe-familiar-inputs` and `product/mathematical-input-contract:compositional-indexed-equation-requests` with prose that names bounded `Let`, its lexical/work semantics, and its exclusions; keep the four operation/report/model claims pending.
Edge: Edit AWF topic sources rather than generated topic output, preserve the familiar restricted-SymPy boundary for every existing construct, and do not advertise the not-yet-public explicit optimize operation. Guidance must distinguish represented-value lowering from work-once evaluation and must not imply runtime, scheduling, mutation, or code generation.
Post-check: Authority check: run `./awf render`, `./awf topic product/mathematical-input-contract`, and `./awf check`; read back the ADR history, authored claim source, rendered topic, analysis model, both READMEs, and packaged skill. Require one Implementing event paired with one Applied event containing exactly the two named claim IDs, no remaining claim presented as applied, canonical `Let(name, value, body)` guidance, and no generated drift. Run `npx vitest run packages/pi-science/tests/package.test.ts`.

### Phase close

Land ordinary-analysis lexical binding, its capture-safe semantics, and the matching first ADR application batch as one green transaction.

```commit
feat(formula): add lexical binding computations
```

## Phase 2: Verify authoritative complete candidates internally

**Execution mode: subagent-driven.**

Completes: ["complete-candidate-verification"]

### Task 2.1: Add failing complete-candidate replay regressions
Kind: batch
Applying: ["adopt-stateless-replayable-formula-optimization-plans:complete-replayable-plans", "adopt-stateless-replayable-formula-optimization-plans:complete-candidate-verification", "adopt-stateless-replayable-formula-optimization-plans:shared-optimization-policy"]
Paths: ["tests/unit/test_formula_optimization.py", "tests/e2e/test_formula_analysis.py", "tests/e2e/test_formula_system_analysis.py", "tests/e2e/test_formula_candidate_comparison.py"]
Representative: For every retained private candidate, construct one complete computation and reanalyse it through the ordinary retained-computation seam before projecting the existing protocol-v12 suggestion.
Edge: Cover factoring, neutral removal, Horner, expression-local repetition, `Sum`-local and iterator-dependent repetition, iterator-invariant hoisting, output-index-dependent sharing, reciprocal/call reuse, and cross-equation sharing. Assert preserved output names/indices, domains, assumptions, definitions, primitive costs, generated-name freshness, equation acyclicity, work delta, and exact-symbolic conditions. Separate candidates remain noncomposable.
Post-check: State check on the regression-only snapshot: run `uv run --locked pytest tests/unit/test_formula_optimization.py tests/e2e/test_formula_analysis.py tests/e2e/test_formula_system_analysis.py tests/e2e/test_formula_candidate_comparison.py -k 'complete_candidate or replayable_candidate'`. Require the new authoritative replay assertions to fail because candidates still retain hidden intermediate placement, while selected pre-existing family, work, and comparison tests pass. Record exact failures.

### Task 2.2: Refactor ordinary advice through one complete-candidate policy seam
Kind: batch
Applying: ["adopt-stateless-replayable-formula-optimization-plans:shared-optimization-policy", "adopt-stateless-replayable-formula-optimization-plans:complete-replayable-plans", "adopt-stateless-replayable-formula-optimization-plans:complete-candidate-verification"]
Paths: ["packages/py-science-formula/src/py_science/formula/computation.py", "packages/py-science-formula/src/py_science/formula/optimization.py", "packages/py-science-formula/src/py_science/formula/service.py", "packages/py-science-formula/src/py_science/formula/comparison.py", "packages/py-science-formula/src/py_science/formula/mapped_outputs.py", "tests/unit/test_formula_optimization.py", "tests/e2e/test_formula_analysis.py", "tests/e2e/test_formula_system_analysis.py", "tests/e2e/test_formula_candidate_comparison.py", "tests/e2e/test_formula_dominance.py"]
Representative: Replace the private reference-plus-hidden-intermediate verification path with one complete candidate value that uses `Let` for lexical sharing and complete named systems where their scope is sufficient; validate it through normal parsing, producer/dependency checks, retained-output proof, and binding-aware aggregate work before deriving the unchanged public suggestion projection.
Edge: Proof expansion may lower `Let` only after candidate validation and never for candidate work. Reuse the retained-computation, output mapping, equivalence, and aggregate-work seams rather than duplicating them. Preserve zero post-work, assumption qualification, unknown-cost omission, incomplete bounds, ranking, deduplication, base-result independence, nested comparison/dominance optimization-disabled reports, and current protocol-v12 bytes.
Post-check: State check: rerun the exact Task 2.1 population, then the complete optimization, analysis, system, comparison, and dominance files. Require every shipped family to reanalyse and compare from its complete internal candidate, all work/proof correlations to match the published projection, and every existing report to remain protocol-v12 compatible.

### Task 2.3: Synchronize the internal architecture description
Kind: batch
Applying: ["adopt-stateless-replayable-formula-optimization-plans:complete-candidate-verification", "adopt-stateless-replayable-formula-optimization-plans:backend-independent-transport"]
Paths: [".awf/docs/parts/architecture/overview.md", ".awf/docs/parts/architecture/data-flow.md", "docs/architecture.md", ".awf/awf.lock"]
Representative: Describe Python's complete-candidate validation and the temporary protocol-v12 target-local projection without claiming the explicit operation or protocol v13 has landed.
Edge: Keep current authority truthful during the staged migration: complete candidate construction is internal in this phase, ordinary advice remains the only public optimizer surface, and Pi still transports v12 without mathematical policy.
Post-check: Authority check: run `./awf render` and `./awf check`; inspect authored and rendered architecture boundaries and require the internal complete-candidate seam, current v12 projection, base independence, proof/work ownership, and deferred public operation to be unambiguous.

### Phase close

Land one Python optimizer policy that verifies complete replayable candidates internally while preserving the existing public protocol.

```commit
refactor(formula): verify complete optimization candidates
```

## Phase 3: Publish the stateless optimize operation in protocol v13

**Execution mode: subagent-driven.**

Completes: ["stateless-optimize-protocol"]

### Task 3.1: Add failing Python operation, plan, and failure regressions
Kind: batch
Applying: ["adopt-stateless-replayable-formula-optimization-plans:explicit-stateless-optimization-operation", "adopt-stateless-replayable-formula-optimization-plans:shared-optimization-policy", "adopt-stateless-replayable-formula-optimization-plans:complete-replayable-plans", "adopt-stateless-replayable-formula-optimization-plans:operation-specific-failure"]
Paths: ["tests/unit/test_formula_optimization.py", "tests/e2e/test_formula_analysis.py", "tests/e2e/test_formula_system_analysis.py", "tests/e2e/test_formula_candidate_comparison.py"]
Representative: Direct Python accepts `operation: optimize` with `max_plans` default 3 or strict 1..16 and returns plans whose candidates include syntax, transformed computation, semantic formula context, and output identities but exclude scenarios, queries, and optimization controls.
Edge: Reject zero, booleans, values above 16, surplus fields, and comparison/dominance-only shapes. Cover empty complete search, bounded incomplete search, passive internal failure preserving byte-for-byte base analysis with `status: failed`, direct typed operation failure, no unverified candidates on failure, assumption-dependent plans, expression/system output identities, JSON round trips, and ordinary advice projecting the same plan identities and ordering.
Post-check: State check on the regression-only snapshot: run `uv run --locked pytest tests/unit/test_formula_optimization.py tests/e2e/test_formula_analysis.py tests/e2e/test_formula_system_analysis.py tests/e2e/test_formula_candidate_comparison.py -k 'optimize_operation or replayable_plan or optimization_failed'`. Require only the new operation/model/failure assertions to fail because the public Python models are absent; all malformed controls that existing validation already rejects and selected pre-existing tests must pass. Record exact failures.

### Task 3.2: Expose the Python operation and shared public plans
Kind: batch
Applying: ["adopt-stateless-replayable-formula-optimization-plans:explicit-stateless-optimization-operation", "adopt-stateless-replayable-formula-optimization-plans:shared-optimization-policy", "adopt-stateless-replayable-formula-optimization-plans:complete-replayable-plans", "adopt-stateless-replayable-formula-optimization-plans:complete-candidate-verification", "adopt-stateless-replayable-formula-optimization-plans:operation-specific-failure"]
Paths: ["packages/py-science-formula/src/py_science/formula/models.py", "packages/py-science-formula/src/py_science/formula/optimization.py", "packages/py-science-formula/src/py_science/formula/service.py", "packages/py-science-formula/src/py_science/formula/__init__.py", "tests/unit/test_formula_optimization.py", "tests/e2e/test_formula_analysis.py", "tests/e2e/test_formula_system_analysis.py", "tests/e2e/test_formula_candidate_comparison.py"]
Representative: Add strict typed optimize request/success/failure models and one service entry point over the Phase 2 policy; make ordinary advice and direct optimization serialize the same bounded plan model and candidate identity.
Edge: Preserve retained base analysis before optional advice, isolate only unexpected optimizer defects at the passive boundary, keep direct failures bounded and typed, distinguish incomplete resource exhaustion, and account for duplicated candidate context inside independent plan and combined-result byte limits. Candidate validation must prove syntax/context/output correlation without allowing Pi to infer it.
Post-check: State check: rerun the exact Task 3.1 population and the complete four files. Require strict request validation, complete candidate replay, identical direct/passive plan identity and ordering, bounded failures, incomplete distinction, and all prior ordinary-analysis/comparison behavior to pass.

### Task 3.3: Add failing protocol-v13 transport and presentation regressions
Kind: batch
Applying: ["adopt-stateless-replayable-formula-optimization-plans:backend-independent-transport", "adopt-stateless-replayable-formula-optimization-plans:explicit-stateless-optimization-operation", "adopt-stateless-replayable-formula-optimization-plans:complete-replayable-plans", "adopt-stateless-replayable-formula-optimization-plans:operation-specific-failure"]
Paths: ["tests/test_pi_schema_generation.py", "packages/pi-science/tests/adapter.test.ts", "packages/pi-science/tests/bridge.test.ts", "packages/pi-science/tests/start.test.ts", "packages/pi-science/tests/package.test.ts"]
Representative: The generated provider schema accepts the Pi optimize projection without `syntax`; the real adapter and strict bridge round-trip protocol-v13 expression and system plans containing `Let`; the registered tool presents a complete candidate and output identities without recomputing mathematics.
Edge: Cover max-plans correlation, default omission, direct typed failure, passive failed advice, incomplete search, exact nulls, missing/surplus/malformed candidate context, output-identity mismatch, invalid Let shape, protocol mismatch, UTF-8 and total-output bounds, disabled nested comparison/dominance reports, canonical details, first-ranked non-superiority wording, finite-precision qualification, and readiness/package behavior.
Post-check: State check on the regression-only snapshot: run `uv run --locked pytest tests/test_pi_schema_generation.py -k 'optimize or protocol_v13 or replayable'` and `npx vitest run packages/pi-science/tests/adapter.test.ts packages/pi-science/tests/bridge.test.ts packages/pi-science/tests/start.test.ts packages/pi-science/tests/package.test.ts -t 'protocol v13|explicit optimize|replayable plan|optimization failed'`. Require the new schema, adapter, bridge, presentation, and package assertions to fail only because transport remains v12; all selected v12 controls must pass. Record exact failures.

### Task 3.4: Migrate schema, adapter, bridge, and registered tool atomically
Kind: batch
Applying: ["adopt-stateless-replayable-formula-optimization-plans:backend-independent-transport", "adopt-stateless-replayable-formula-optimization-plans:explicit-stateless-optimization-operation", "adopt-stateless-replayable-formula-optimization-plans:complete-replayable-plans", "adopt-stateless-replayable-formula-optimization-plans:operation-specific-failure"]
Paths: ["scripts/generate-pi-formula-schema.py", "packages/pi-science/src/formula-schema.json", "packages/pi-science/bridge/formula_adapter.py", "packages/pi-science/src/bridge.ts", "packages/pi-science/src/index.ts", "tests/test_pi_schema_generation.py", "packages/pi-science/tests/adapter.test.ts", "packages/pi-science/tests/bridge.test.ts", "packages/pi-science/tests/start.test.ts", "packages/pi-science/tests/package.test.ts"]
Representative: Advance both protocol owners to v13, add operation dispatch and strict result correlation, project direct-Python candidate syntax to Pi's syntax-injected request shape, and render plans and failures from Python-owned fields only.
Edge: Recalculate bounded serialized-result and framed-output allowances from the complete-plan population rather than weakening limits ad hoc. Reject mixed v12/v13 envelopes, wrong operation variants, unbounded diagnostics, malformed bindings, context drift, output mismatches, and any attempt by TypeScript to derive equivalence, scope, work, or ranking. Preserve provisioning and the always-available doctor.
Post-check: State check: rerun the exact Task 3.3 commands, then the complete schema, adapter, bridge, start, and package files. Require real-adapter and registered-tool round trips for every operation/result/failure variant, strict malformed-result rejection, deterministic schema generation, bounded output, and no remaining active v12 fixture.

### Task 3.5: Apply the remaining claims and synchronize product guidance
Kind: batch
Applying: ["adopt-stateless-replayable-formula-optimization-plans:explicit-stateless-optimization-operation", "adopt-stateless-replayable-formula-optimization-plans:shared-optimization-policy", "adopt-stateless-replayable-formula-optimization-plans:complete-replayable-plans", "adopt-stateless-replayable-formula-optimization-plans:complete-candidate-verification", "adopt-stateless-replayable-formula-optimization-plans:operation-specific-failure", "adopt-stateless-replayable-formula-optimization-plans:backend-independent-transport", "adopt-stateless-replayable-formula-optimization-plans:exact-symbolic-boundary"]
Paths: ["docs/decisions/adopt-stateless-replayable-formula-optimization-plans.md", ".awf/topics/parts/product/product-boundary/current-state.md", ".awf/topics/parts/product/mathematical-input-contract/current-state.md", ".awf/topics/parts/product/analysis-report-contract/current-state.md", ".awf/topics/parts/product/mathematical-analysis-model/current-state.md", "docs/topics/product/product-boundary.md", "docs/topics/product/mathematical-input-contract.md", "docs/topics/product/analysis-report-contract.md", "docs/topics/product/mathematical-analysis-model.md", "docs/vision.md", "docs/analysis-model.md", ".awf/docs/parts/architecture/overview.md", ".awf/docs/parts/architecture/data-flow.md", ".awf/docs/parts/testing/tiers.md", ".awf/docs/parts/testing/layout.md", ".awf/parts/agents-doc/identity.md", "docs/architecture.md", "docs/testing.md", "README.md", "packages/py-science-formula/README.md", "packages/pi-science/skills/formula-analysis/SKILL.md", "AGENTS.md", "docs/decisions/INDEX.md", ".awf/awf.lock"]
Representative: Apply exactly the remaining updates to `product/product-boundary:symbolic-analysis-only`, `product/mathematical-input-contract:bounded-optimization-advice-requests`, `product/analysis-report-contract:qualified-optimization-advice`, and `product/mathematical-analysis-model:bounded-optimization-transformation`, documenting direct optimize, replay, failures, v13, and preserved exclusions.
Edge: Keep the ADR Implementing after this final explicit batch; terminal Implemented closure belongs after implementation assurance. Teach agents to submit the returned candidate directly, inspect normalized interpretation and qualifications, keep plans atomic, and distinguish failed from incomplete. Update generated outputs only through AWF authorities. Historical ADRs and implemented plans retain v12 references; active current-state and operational guidance must use v13.
Post-check: Authority check: run `./awf render`, `./awf topic product/product-boundary`, `./awf topic product/mathematical-input-contract`, `./awf topic product/analysis-report-contract`, `./awf topic product/mathematical-analysis-model`, and `./awf check`. Inspect every authored/rendered path. Run a checked current-guidance census that excludes `docs/decisions/**` and `docs/plans/**`, prints `CURRENT_PROTOCOL_CENSUS_OK` only after a successful search, and require no active `protocol v12`, `protocol-v12`, or `PROTOCOL_VERSION = 12` matches. Require the ADR history to show the earlier two-claim Applied batch plus one final Applied batch containing exactly the four remaining operations, with no duplicate or missing operation.

### Phase close

Land the complete Python/Pi protocol-v13 operation, plan projection, failure contract, current-state claims, and agent guidance as one atomic green transaction.

```commit
feat(formula): add stateless optimize operation
```

## Definition of done

- `dod: lexical-binding-analysis` Ordinary Python and Pi analysis safely accept bounded `Let(name, value, body)`, preserve its normalized lexical structure, lower it only for represented-value mathematics, charge its value once per enclosing evaluation, and reject recursion, capture, malformed names, and resource overflow; the two lexical-input claim updates are applied.
- `dod: complete-candidate-verification` Every shipped optimizer family constructs a complete internal expression or equation-system candidate, reanalyses it through ordinary validation, proves retained outputs, and compares binding-aware whole work before the existing public projection can publish it.
- `dod: stateless-optimize-protocol` Direct Python and Pi protocol v13 accept `operation: optimize` with `max_plans` default 3 and range 1..16; direct optimization and ordinary advice return the same bounded replayable plans, complete candidates and output identities round-trip through analysis and comparison, passive failure preserves base analysis, direct failure is typed, exhaustion remains incomplete, Pi owns no mathematical policy, and all remaining ADR claim updates are applied.

## Notes

- Approved public shape: `Let(name, value, body)`; `operation: optimize`; `max_plans` default 3 and strict range 1..16; complete caller-facing candidate plus semantic context and output identities; scenarios, queries, and optimization controls excluded from candidate context; protocol v13.
- ADR operation allocation: Phase 1 applies `safe-familiar-inputs` and `compositional-indexed-equation-requests`. Phase 2 is an internal enabling transaction and applies no current-state operation. Phase 3 applies `symbolic-analysis-only`, `bounded-optimization-advice-requests`, `qualified-optimization-advice`, and `bounded-optimization-transformation` atomically with the public migration.
- The atomic Phase 3 boundary is intentional: Python public models, generated provider schema, adapter dispatch, TypeScript unions/correlation, registered-tool rendering, protocol version, and current-state claims cannot independently expose incompatible partial shapes.
- Inline owners immediately correct stale instructions and record reasoned deviations here. Delegated owners report rather than edit; the parent supplies their report to phase review and reconciles it with findings in one focused settlement commit before checkpointing or later execution.
- Phase 1 review settlement adds precedence-safe lexical rendering, bounded capture-avoiding represented-value lowering, fresh binding-name validation, binding-aware optimizer and mapped-output traversal, preserved system rendering, and the omitted consumer and protocol-v12 regressions. It preserves the approved phase boundary with no reasoned deviation.
- Renewed Phase 1 assurance found six consumer gaps. The settlement resolves lexical values in aggregate bounds and primitive costs without double-charging evaluation, carries inferred binding integrality into index qualification, lowers bindings for dependent-domain and post-substitution reasoning mathematics, validates comparison bindings against request names, and preserves lexical placement for reuse candidates. These are authority-determined corrections inside the approved complete-consumer boundary; no design or material-scope deviation was required.
- Phase 2 review settlement keeps mixed output-index and local-binder reuse lexical, preserves applicable output constraints on generated producers, validates reconstructed requests against public population bounds, and replaces an unapproved prefix cap with a deterministic family- and population-spanning schedule that preserves bounded later-candidate coverage. Renewed assurance derives proof from the replayed retained outputs themselves, allocates capture-free canonical binder identities, keeps every represented family plus the population tail when the schedule is full, and aligns architecture prose with bounded selection. Planned computation, service, comparison, mapped-output, and dominance paths remain unchanged because the optimizer reuses their existing retained seams and established nested-disable coverage without modification; this path omission is reconciled rather than padded with no-op edits. The corrections preserve the approved boundary with no material-scope deviation.
