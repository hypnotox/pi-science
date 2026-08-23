---
format: plan-v2
date: 2026-08-23
adrs: [separate-formula-responsibilities-behind-compatibility-facades]
status: Proposed
---
# Plan: Implement Formula Responsibility Boundaries

## Goal

Replace the central formula and Pi monoliths with cohesive internal owners behind stable compatibility surfaces while preserving protocol v16, generated schema bytes, public exports, model objects, candidate and plan identities, search, proof, objective, and transport behavior. Do not add GoalSpec, PlanIR, transformation families, protocol fields, or new mathematical claims.

## Architecture summary

Define transport-free Python contracts once under `contracts/`, with `models.py` and the package root forwarding the same objects. Put retained-computation construction and bounded structural-occurrence facts in neutral `_analysis` modules consumed by service, optimizer, and comparison. Keep optimizer generation, objectives, replay, verification, canonical state, search, and plan projection under `_optimization`; keep request orchestration, queries, scenarios, dominance dispatch, and result bounds under `_service`. Preserve `optimization.py` and `service.py` as thin compatibility facades where existing imports require them, and remove every optimizer dependency on service orchestration.

Split Pi protocol, request and result shapes, diagnostics, strict correlation, and the per-call client state machine under `src/bridge/`; keep `bridge.ts` as the outward compatibility barrel and `process.ts` as the process-tree mechanism. Provisioning and registration consume owning modules directly, presentation leaves `index.ts`, and no TypeScript module derives mathematical policy. The test-layout split precedes production extraction, the Python cycle is removed before optimizer and service decomposition, and current-state claims land only after every owner is real. Each phase closes independently green. Delegation uses one sequential worker or up to three parallel workers from `pi-science#2` through `pi-science#4`; path-disjoint foundation work may be prepared in parallel, but the orchestrator integrates it in the declared order and retains root exports, generated schema, `bridge.ts`, `index.ts`, lifecycle, closing commits for inline phases, and semantic conflict resolution. Every assignment requires DONE or BLOCKED reporting and carries this orchestrator contract through handoffs.

## Phase 1: Split the optimization characterization corpus

**Execution mode: subagent-driven.**

Completes: ["optimization-test-ownership"]

### Task 1.1: Move tests by responsibility without changing assertions
Kind: batch
Paths: ["tests/unit/test_formula_optimization.py", "tests/unit/optimization/test_occurrences.py", "tests/unit/optimization/test_families.py", "tests/unit/optimization/test_verifier.py", "tests/unit/optimization/test_objectives.py", "tests/unit/optimization/test_canonical_states.py", "tests/unit/optimization/test_search.py", "tests/unit/optimization/test_replay.py", "tests/unit/optimization/test_budgets.py", "tests/unit/optimization/test_algorithmic_sum.py", ".awf/docs/parts/testing/layout.md", "docs/testing.md", ".awf/awf.lock"]
Representative: Move occurrence discovery and scope diagnostics to `test_occurrences.py` and full candidate replay to `test_replay.py` without changing their assertions.
Edge: Keep a cross-cutting case with the subsystem whose behavior its terminal assertion proves, and preserve shared helper semantics locally rather than creating a new production seam.
Post-check: State check: compare the parent and result with a successful Python AST inventory of test-function names, parameter markers, and assertion counts; require equal inventories, require the old monolithic file to be absent, collect every new module, run the complete moved population, and require every capability-evidence link to resolve. Choreography check: render after updating the authored testing source.

Move existing tests and their narrow helpers into the named responsibility modules. Preserve each test's inputs, assertions, parameterization, monkeypatch target meaning, and real-adapter coverage; change imports only as needed for the new locations. Keep cross-cutting replay cases with replay, search-budget cases with search or budgets according to the behavior asserted, and the opt-in finite-sum family in its dedicated file. Do not add snapshots, production helpers, or behavior expectations. Update the authored testing layout and its generated publication in the same transaction so every family-level capability-evidence link names the new owning test module; change no testing-policy claim beyond the real layout.

### Phase close

Close only the test-layout and matching evidence-link transaction after the state checks for moved tests and live links, the render choreography check, and the full gate pass.

```commit
test(formula): split optimization characterization by responsibility
```

## Phase 2: Establish transport-free contract homes

**Execution mode: subagent-driven.**

Advances: ["frozen-foundation-behavior"]
Completes: ["python-contract-identity"]

### Task 2.1: Extract the contract dependency DAG behind `models.py`
Kind: batch
Applying: ["separate-formula-responsibilities-behind-compatibility-facades:assign-single-responsibility-owners", "separate-formula-responsibilities-behind-compatibility-facades:preserve-python-compatibility-surfaces", "separate-formula-responsibilities-behind-compatibility-facades:preserve-foundation-compatibility"]
Paths: ["packages/py-science-formula/src/py_science/formula/contracts/__init__.py", "packages/py-science-formula/src/py_science/formula/contracts/_base.py", "packages/py-science-formula/src/py_science/formula/contracts/common.py", "packages/py-science-formula/src/py_science/formula/contracts/evidence.py", "packages/py-science-formula/src/py_science/formula/contracts/queries.py", "packages/py-science-formula/src/py_science/formula/contracts/optimization.py", "packages/py-science-formula/src/py_science/formula/contracts/requests.py", "packages/py-science-formula/src/py_science/formula/contracts/reports.py", "packages/py-science-formula/src/py_science/formula/contracts/comparison.py", "packages/py-science-formula/src/py_science/formula/contracts/dominance.py", "packages/py-science-formula/src/py_science/formula/models.py", "tests/unit/test_public_exports.py", "tests/test_pi_schema_generation.py", "tests/distribution/test_python_package.py"]
Representative: Define `AnalysisRequest` in `contracts/requests.py` while `models.AnalysisRequest` and root `AnalysisRequest` remain that exact object and emit the same schema.
Edge: Preserve comparison and dominance delegation into `AnalysisRequest` without introducing a reverse request-to-comparison or request-to-dominance import.
Post-check: State check: import every former `models.py` name from its defining module, `models.py`, and the package root where public; require object identity, the exact pinned root export set, unchanged representative JSON and validation errors, byte-identical `formula-schema.json`, and an installed wheel that imports every contract module.

Move class bodies without reordering fields, unions, validators, defaults, docstrings, or helpers. Preserve strict frozen Pydantic configuration and every direct `py_science.formula.models` import by explicit alias, never subclassing or duplicating a model. Use the acyclic direction `_base -> common -> evidence -> queries and optimization -> requests and reports -> comparison and dominance`; no contract module imports the package root, `models.py`, parser, SymPy, optimizer implementation, service, or Pi. Keep the generator and package-root export list orchestrator-owned and unchanged.

### Phase close

Close after state checks for schema bytes, class-object aliases, direct model imports, package installation, and the full gate prove compatibility.

```commit
refactor(formula): split typed contracts behind the models facade
```

## Phase 3: Split the strict Pi bridge core

**Execution mode: inline.**

Advances: ["pi-transport-boundaries", "frozen-foundation-behavior"]

### Task 3.1: Extract protocol, validation, correlation, and the client state machine
Kind: batch
Applying: ["separate-formula-responsibilities-behind-compatibility-facades:assign-single-responsibility-owners", "separate-formula-responsibilities-behind-compatibility-facades:direct-pi-dependencies", "separate-formula-responsibilities-behind-compatibility-facades:preserve-foundation-compatibility"]
Paths: ["packages/pi-science/src/bridge/protocol.ts", "packages/pi-science/src/bridge/requests.ts", "packages/pi-science/src/bridge/results.ts", "packages/pi-science/src/bridge/diagnostics.ts", "packages/pi-science/src/bridge/correlation.ts", "packages/pi-science/src/bridge/client.ts", "packages/pi-science/src/bridge.ts", "packages/pi-science/tests/bridge.test.ts", "packages/pi-science/tests/adapter.test.ts", "packages/pi-science/tests/package.test.ts", ".awf/docs/parts/architecture/components.md", ".awf/docs/parts/architecture/data-flow.md", "docs/architecture.md", ".awf/awf.lock"]
Representative: Route a real protocol-v16 optimization response through request-independent shape validation, request-aware trace correlation, and the unchanged client result.
Edge: Preserve pre-abort, timeout, cleanup-induced stdin error, resistant-descendant termination, and close-after-terminate settlement as one client state machine.
Post-check: State check: require the barrel to expose the previous exported symbol set, require no new bridge module to import the barrel or `index.ts`, run the real adapter and strict bridge suites, require the packed package to contain and import the new modules with unchanged schema bytes and protocol constant, and inspect the rendered intermediate component and data-flow passages for truth. Choreography check: render after updating the authored architecture sources.

Give protocol constants and byte/JSON primitives one home; separate request types, result types and request-independent shape checks, bounded diagnostics, and request-aware correlation. Keep one strict response-correlation entry point. Move `invokeAdapter` as one intact per-call state machine that owns payload writing, stdout and stderr bounds, timeout, abort, settlement, and cleanup while depending on the existing `process.ts` spawn and tree-termination seam. Preserve exact-key rejection, diagnostic envelopes, operation-specific failure variants, all correlation checks, protocol v16, and every limit. Do not move presentation, `index.ts`, provisioning policy, process lifecycle, or generated schema in this phase. The inline orchestrator owns `bridge.ts`, authored and generated architecture, and semantic integration. A commit-disabled delegated helper may own only the six new `src/bridge/` modules and the three named Pi test files; it must not edit shared or generated paths. Update architecture source and generated output to describe the truthful intermediate barrel, child-module, client, and retained-presentation boundary.

### Phase close

Close after state checks for TypeScript type, lint, format, strict bridge, adapter, packaging, and rendered prose, the render choreography check, and the full repository gate pass.

```commit
refactor(pi): split strict bridge behind compatibility barrel
```

## Phase 4: Remove the Python orchestration cycle through neutral analysis

**Execution mode: subagent-driven.**

Advances: ["optimizer-responsibility-boundary", "service-responsibility-boundary", "frozen-foundation-behavior"]
Completes: ["acyclic-python-analysis"]

### Task 4.1: Extract retained computation and occurrence facts
Kind: batch
Applying: ["separate-formula-responsibilities-behind-compatibility-facades:assign-single-responsibility-owners", "separate-formula-responsibilities-behind-compatibility-facades:direct-python-dependencies", "separate-formula-responsibilities-behind-compatibility-facades:preserve-foundation-compatibility"]
Paths: ["packages/py-science-formula/src/py_science/formula/_analysis/__init__.py", "packages/py-science-formula/src/py_science/formula/_analysis/retained.py", "packages/py-science-formula/src/py_science/formula/_analysis/occurrences.py", "packages/py-science-formula/src/py_science/formula/computation.py", "packages/py-science-formula/src/py_science/formula/service.py", "packages/py-science-formula/src/py_science/formula/optimization.py", "packages/py-science-formula/src/py_science/formula/comparison.py", "tests/unit/optimization/test_occurrences.py", "tests/unit/optimization/test_replay.py", "tests/e2e/test_formula_analysis.py", "tests/e2e/test_formula_system_analysis.py", "tests/e2e/test_formula_candidate_comparison.py"]
Representative: Replay one complete candidate through the neutral retained analyzer passed into the optimizer and compare its retained aggregate work exactly as before.
Edge: Preserve equation-system occurrence scope and extraction diagnostics while preventing ordinary analysis from importing optimizer candidate policy.
Post-check: State check: require a successful import-graph probe to show no optimization-to-service edge, require service, optimizer, and comparison to consume the neutral retained seam, require one bounded occurrence implementation, and run all analysis, comparison, occurrence, and replay characterizations.

Move the sole retained-computation construction path, including its immutable work snapshot, into neutral analysis without changing its one-pass parsing, validation, scenario prevalidation, producer ordering, knowledge, context, base success, or budgets. Move bounded structural occurrence traversal and legacy extraction-diagnostic projection together, but leave optimizer applicability, candidate construction, proof, objective, and ranking above that seam. Preserve `RetainedComputation` and `RetainedWorkAnalysis` meaning and keep temporary private compatibility aliases only where characterized callers still require them.

Replace optimizer local imports of `service._analyze_computation` with an explicit analyzer callable supplied by service orchestration; comparison imports neutral retained analysis directly. Preserve complete ordinary replay for every child and original-to-final check. Service may still invoke the monolithic optimizer report during this phase, but optimizer must not import service.

### Phase close

Close after state checks for the dependency cycle, focused replay and comparison behavior, package imports, and the full gate pass.

```commit
refactor(formula): extract neutral retained analysis and occurrences
```

## Phase 5: Separate optimizer generation, search, and verification

**Execution mode: subagent-driven.**

Advances: ["frozen-foundation-behavior"]
Completes: ["optimizer-responsibility-boundary"]

### Task 5.1: Extract optimizer owners behind `optimization.py`
Kind: batch
Applying: ["separate-formula-responsibilities-behind-compatibility-facades:assign-single-responsibility-owners", "separate-formula-responsibilities-behind-compatibility-facades:direct-python-dependencies", "separate-formula-responsibilities-behind-compatibility-facades:preserve-foundation-compatibility"]
Paths: ["packages/py-science-formula/src/py_science/formula/_optimization/__init__.py", "packages/py-science-formula/src/py_science/formula/_optimization/budgets.py", "packages/py-science-formula/src/py_science/formula/_optimization/candidates.py", "packages/py-science-formula/src/py_science/formula/_optimization/objectives.py", "packages/py-science-formula/src/py_science/formula/_optimization/replay.py", "packages/py-science-formula/src/py_science/formula/_optimization/verifier.py", "packages/py-science-formula/src/py_science/formula/_optimization/canonical.py", "packages/py-science-formula/src/py_science/formula/_optimization/search.py", "packages/py-science-formula/src/py_science/formula/_optimization/plans.py", "packages/py-science-formula/src/py_science/formula/_optimization/families/__init__.py", "packages/py-science-formula/src/py_science/formula/_optimization/families/repeated_structure.py", "packages/py-science-formula/src/py_science/formula/_optimization/families/call_reuse.py", "packages/py-science-formula/src/py_science/formula/_optimization/families/factoring.py", "packages/py-science-formula/src/py_science/formula/_optimization/families/redundant_operations.py", "packages/py-science-formula/src/py_science/formula/_optimization/families/invariant_hoisting.py", "packages/py-science-formula/src/py_science/formula/_optimization/families/cross_equation_sharing.py", "packages/py-science-formula/src/py_science/formula/_optimization/families/horner.py", "packages/py-science-formula/src/py_science/formula/_optimization/families/finite_polynomial_sum.py", "packages/py-science-formula/src/py_science/formula/optimization.py", "tests/unit/optimization/test_families.py", "tests/unit/optimization/test_verifier.py", "tests/unit/optimization/test_objectives.py", "tests/unit/optimization/test_canonical_states.py", "tests/unit/optimization/test_search.py", "tests/unit/optimization/test_replay.py", "tests/unit/optimization/test_budgets.py", "tests/unit/optimization/test_algorithmic_sum.py", "tests/distribution/test_python_package.py"]
Representative: Generate, replay, verify, rank, and project one repeated-structure candidate through distinct owners while retaining its exact candidate and plan identities.
Edge: Keep the opt-in finite-polynomial Sum lane and mixed two-step traces under independent algorithmic verification without letting the family publish or bypass replay.
Post-check: State check: require an import-graph probe with families depending only on neutral facts and candidate types, replay depending on the analyzer seam and candidate types, verifier depending on replay but independent of search, search depending on families, verifier, canonical state, and objectives, and no `_optimization` import of service; run the complete optimization population and installed-package import probe.

Move code mechanically into the named single homes. Families return untrusted proposals and never publish plans or bypass replay. Replay owns construction and ordinary reanalysis of complete parent, child, and final states through the supplied analyzer seam. Verifier consumes replayed states, owns transition and direct-final acceptance, and does not own traversal or search. Objectives own optimizer projection and comparison policy but not work primitives; canonical state owns deduplication and trace keys but not ranking; search owns fair scheduling and bounded admission; plans own final model projection. Keep all budgets, family order, candidates, canonical keys, proof retries, objective comparisons, qualifications, identities, and ranked prefixes unchanged. Make `optimization.py` a thin explicit compatibility facade for characterized internal imports; do not introduce a common catch-all module.

### Phase close

Close after state checks for dependency direction, split optimizer tests, deterministic replay, package installation, and the full gate pass.

```commit
refactor(formula): separate optimizer generation search and verification
```

## Phase 6: Separate service orchestration responsibilities

**Execution mode: subagent-driven.**

Advances: ["frozen-foundation-behavior"]
Completes: ["service-responsibility-boundary"]

### Task 6.1: Extract orchestration owners behind `service.py`
Kind: batch
Applying: ["separate-formula-responsibilities-behind-compatibility-facades:assign-single-responsibility-owners", "separate-formula-responsibilities-behind-compatibility-facades:direct-python-dependencies", "separate-formula-responsibilities-behind-compatibility-facades:preserve-foundation-compatibility"]
Paths: ["packages/py-science-formula/src/py_science/formula/_service/__init__.py", "packages/py-science-formula/src/py_science/formula/_service/orchestration.py", "packages/py-science-formula/src/py_science/formula/_service/optimization.py", "packages/py-science-formula/src/py_science/formula/_service/query_execution.py", "packages/py-science-formula/src/py_science/formula/_service/scenario_execution.py", "packages/py-science-formula/src/py_science/formula/_service/result_bounds.py", "packages/py-science-formula/src/py_science/formula/service.py", "tests/e2e/test_formula_analysis.py", "tests/e2e/test_formula_system_analysis.py", "tests/e2e/test_formula_candidate_comparison.py", "tests/e2e/test_formula_dominance.py", "tests/unit/test_formula_queries.py", "tests/unit/test_formula_scenarios.py", "tests/unit/optimization/test_replay.py", "tests/distribution/test_python_package.py"]
Representative: Route one ordinary request through retained analysis, queries, scenarios, passive optimization, and result bounding while preserving its exact report.
Edge: Preserve direct optimization failure typing and dominance dispatch without feeding either through ordinary advice attachment or changing null and byte-bound policy.
Post-check: State check: require the unchanged package root and `service.py` to expose the pinned public callables, require `_service` modules to import neutral analysis and `_optimization` owners rather than compatibility facades, require no reverse optimizer edge, and run ordinary, query, scenario, dominance, comparison, replay, and installed-package evidence.

The delegated owner must not edit package-root `__init__.py`; the orchestrator verifies its export identity and resolves any semantic conflict outside this phase rather than broadening the phase. Move entry-point orchestration, ordinary and direct optimization dispatch, query attachment and derived-target correlation, scenario specialization, dominance dispatch, and result byte bounding into their named owners. Keep neutral retained analysis outside `_service`. Preserve a top-to-bottom orchestration path and make `service.py` a thin explicit facade for `analyze`, `optimize`, `analyze_dominance`, and characterized compatibility aliases. Do not change request loading, passive versus direct failures, result null policy, report attachment order, optimization disablement during replay, or output allowances.

### Phase close

Close after state checks for public-callable identity, service dependency direction, the full analysis surface, packaging, and repository gates pass.

```commit
refactor(formula): separate service orchestration responsibilities
```

## Phase 7: Complete Pi presentation and internal dependency direction

**Execution mode: inline.**

Advances: ["frozen-foundation-behavior"]
Completes: ["pi-transport-boundaries"]

### Task 7.1: Extract presentation and redirect integration imports
Applying: ["separate-formula-responsibilities-behind-compatibility-facades:direct-pi-dependencies", "separate-formula-responsibilities-behind-compatibility-facades:preserve-foundation-compatibility"]
Paths: ["packages/pi-science/src/bridge/presentation.ts", "packages/pi-science/src/index.ts", "packages/pi-science/src/provision.ts", "packages/pi-science/src/bridge.ts", "packages/pi-science/tests/start.test.ts", "packages/pi-science/tests/provision.test.ts", "packages/pi-science/tests/bridge.test.ts", "packages/pi-science/tests/package.test.ts"]

Move compact result rendering and tool-result projection out of `index.ts` into presentation that depends only on result types and the host context it needs. Keep registration, schema import, readiness composition, public exports, and default extension in `index.ts`. Redirect provisioning to the owning protocol and diagnostic primitives while preserving its distinct bounded health-process and readiness policy. Internal production modules must not import `bridge.ts`; the barrel remains for compatibility and tests. Preserve every rendered phrase, details payload, readiness diagnostic, cancellation and timeout outcome, formula schema, and protocol value.

### Phase close

Close after state checks for direct imports, TypeScript, all Pi behavior, package installation and startup, and schema identity, plus the full repository gate pass.

```commit
refactor(pi): separate presentation and integration dependencies
```

## Phase 8: Apply and document the implemented component boundary

**Execution mode: inline.**

Completes: ["current-component-documentation", "frozen-foundation-behavior"]

### Task 8.1: Apply the current-state claim and update component guidance
Kind: batch
Applying: ["separate-formula-responsibilities-behind-compatibility-facades:assign-single-responsibility-owners", "separate-formula-responsibilities-behind-compatibility-facades:direct-python-dependencies", "separate-formula-responsibilities-behind-compatibility-facades:preserve-python-compatibility-surfaces", "separate-formula-responsibilities-behind-compatibility-facades:direct-pi-dependencies", "separate-formula-responsibilities-behind-compatibility-facades:preserve-foundation-compatibility"]
Paths: ["docs/decisions/separate-formula-responsibilities-behind-compatibility-facades.md", ".awf/topics/parts/product/formula-component-boundaries/current-state.md", ".awf/docs/parts/architecture/components.md", ".awf/docs/parts/architecture/data-flow.md", ".awf/docs/parts/testing/layout.md", "packages/py-science-formula/README.md", "docs/decisions/INDEX.md", "docs/topics/product/formula-component-boundaries.md", "docs/architecture.md", "docs/testing.md", ".awf/awf.lock"]
Representative: Apply the responsibility-directed-components claim and render the architecture component map from the actual extracted module boundaries.
Edge: Keep protocol, analysis-model, and vision semantics unchanged while removing stale central-file ownership wording from active guidance.
Post-check: Authority checks: run the destination topic inspection and staged AWF validation. Choreography check: render from the authored sources. State checks: inspect each generated component, dependency, extension, and test-ownership passage for semantic agreement, and require a successful active-document census to find no remaining claim that the central files own extracted policy.

Use the ADR lifecycle to enter Implementing and apply the single add `product/formula-component-boundaries:responsibility-directed-components` in the same transaction as its claim. State the single owners, dependency direction, compatibility surfaces, Pi no-mathematics boundary, and retained process lifecycle, with the pending ADR slug as Origin. Keep the ADR and plan nonterminal through implementation assurance.

Update architecture source with the real component map and data flow, testing source with subsystem ownership, and the Python package README with the extension seams for a transformation family and proof semantics. Reference the current-state topic for the durable rule rather than repeating rationale. Render generated outputs and review their meaning. Do not change product semantics, protocol documentation, the analysis model, or vision claims.

### Phase close

Close only after state checks for package and Pi release installation, byte-identical schema, public exports, candidate and plan identities, search, replay, and generated prose; authority check `./awf check staged`; and the full `./scripts/check` and `./scripts/check-release` gates pass.

```commit
refactor(architecture): apply formula responsibility boundaries
```

## Definition of done

- `dod: optimization-test-ownership` The former monolithic optimization tests are organized by responsibility with the same test-function and assertion inventory and all moved nodes passing.
- `dod: python-contract-identity` Every contract has one transport-free defining home; `models.py` and the package root forward identical objects; direct imports, strict validation, schema bytes, exports, and installed-package behavior remain stable.
- `dod: acyclic-python-analysis` Retained-computation construction and structural-occurrence facts have neutral owners consumed by service, optimizer, and comparison, with no optimizer-to-service dependency and no duplicated occurrence walker.
- `dod: optimizer-responsibility-boundary` Candidate families, objectives, replay and verification, canonical state, search, budgets, and plan projection have cohesive owners without changing families, states, ordering, proofs, objectives, qualifications, or identities.
- `dod: service-responsibility-boundary` Request orchestration, optimization dispatch, queries, scenarios, dominance dispatch, and result bounds have cohesive owners behind stable public service entry points.
- `dod: pi-transport-boundaries` Protocol, shapes, diagnostics, strict correlation, client invocation, and presentation have separate owners; `bridge.ts` is an outward barrel, `process.ts` retains process-tree lifecycle, and Pi behavior and wording remain stable.
- `dod: current-component-documentation` The ADR operation is applied, current architecture and package guidance name the real owners and extension seams, test guidance names subsystem ownership, and generated prose is semantically reviewed.
- `dod: frozen-foundation-behavior` Protocol v16, generated schema bytes, public exports and objects, request and result serialization and validation, candidate and plan identities, search population and ordering, proofs, objectives, budgets, Pi correlation, presentation, provisioning, and release installation match the R0 baseline, with no GoalSpec or PlanIR added.

## Notes

Inline owners immediately correct stale instructions and record reasoned deviations here. Delegation uses one sequential worker or up to three parallel workers from `pi-science#2` through `pi-science#4`. Delegated owners report DONE or BLOCKED to the goal-driven-optimizer orchestrator, preserve that assignment through handoffs, and do not change contracts, reserved integration files, protocol, schema, or semantics outside their phase. The orchestrator supplies each report to phase review, resolves semantic conflicts, and records focused evidence, generated-prose review, deviations, and review settlements here before the next integration.

Precommit review disposition: D6 moves capability-evidence links with Phase 1 so the committed index never points at the deleted monolith. Phase 3 is inline because the compatibility barrel and architecture publications are orchestrator-owned; a path-disjoint commit-disabled helper may prepare only the new bridge modules and tests. Architecture source travels in Phase 3 so the intermediate boundary is truthful. `_optimization/replay.py` is the cohesive owner of complete-state construction and ordinary reanalysis; verifier consumes replayed states rather than combining those responsibilities. Phase 6 leaves the package root unchanged and delegated work excludes it. Material probes are labeled by state, authority, or choreography purpose.

Phase 1 close: commit `ab4aa2b` preserves the complete 88-test and 372-assert AST inventory across the nine responsibility modules; the moved population passes 119 cases, all capability links resolve, render output is current, and the full gate passes 515 Python and 126 Pi tests. Phase review found no issue or deviation.
