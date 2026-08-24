---
format: plan-v2
date: 2026-08-23
adrs: [adopt-declarative-optimization-goals-and-explicit-claim-scope]
status: Proposed
---
# Plan: Implement Declarative Optimization Goals and Explicit Claims

## Goal

Replace passive and implementation-selected optimization with one explicit goal-driven operation whose replayable plans and empty outcomes state exactly what bounded exact-symbolic search proved. Preserve the existing mathematical verifier and candidate replay boundary; do not introduce hard resource ceilings, selectable output subsets, goal-local domains, configurable depth, PlanIR, new resources, runtime claims, or numerical claims.

## Architecture summary

The public Python contract has one explicit optimize request containing the submitted computation, required `GoalSpec`, required `bounded_goal_v1` search policy, required `verifier_backed_v1` proof policy, and a separate result projection limit. `GoalSpec` preserves every submitted output, consumes the submitted domains, constraints, and assumptions, and selects the existing unit-work or exact weighted-operation aggregate abstract-work objective. Ordinary analysis no longer invokes optimization or carries optimization results.

Optimizer-owned generation and verification capture bounded typed outcome facts during existing work, then search owns result classification and scope. Accepted-plan projection owns `strict_improvement` claim construction without changing complete candidate identity or replay. Service owns request orchestration and result byte bounds. Python alone derives goals, claims, selection, completion, and blockers. Pi protocol v17 strictly validates and correlates the Python result, then presentation renders it without deriving mathematics. The public cutover is one atomic Python-schema-adapter-Pi phase so no committed protocol combination is internally inconsistent.

Execution follows the `goal-driven-optimizer` orchestrator contract: one sequential owner or at most three path-disjoint helpers from `pi-science#2` through `pi-science#4`, each reporting DONE or BLOCKED and carrying the orchestrator assignment through handoffs. The orchestrator retains the ADR and plan, public root exports, generated schema, protocol version, shared bridge surfaces, generated documentation, semantic integration, final gates, closing commits, and conflict resolution. R3 remains dependency-gated and does not begin here.

## Phase 1: Capture bounded search outcomes without changing the public contract

**Execution mode: subagent-driven.**

Advances: ["truthful-result-accounting", "actionable-blockers"]

### Task 1.1: Introduce private typed search accounting
Kind: batch
Applying: ["adopt-declarative-optimization-goals-and-explicit-claim-scope:explicit-truthful-claims", "adopt-declarative-optimization-goals-and-explicit-claim-scope:bounded-actionable-blockers"]
Paths: ["packages/py-science-formula/src/py_science/formula/_optimization/diagnostics.py", "packages/py-science-formula/src/py_science/formula/_optimization/search.py", "packages/py-science-formula/src/py_science/formula/_optimization/verifier.py", "packages/py-science-formula/src/py_science/formula/_optimization/families/horner.py", "packages/py-science-formula/src/py_science/formula/_optimization/families/finite_polynomial_sum.py", "tests/unit/optimization/test_search.py", "tests/unit/optimization/test_verifier.py", "tests/unit/optimization/test_families.py", "tests/unit/optimization/test_algorithmic_sum.py", "tests/unit/optimization/test_budgets.py"]
Representative: Record that an observed repeated-call proposal reached verification but lacked a declared primitive cost, without retaining the speculative candidate or changing its rejection.
Edge: A family that returns no proposal and no localized typed refusal still contributes no blocker. Nonpositive savings remain an observed nonverification outcome, not missing-information guidance. Resource exhaustion continues to control search incompleteness rather than blocker classification.
Post-check: State check: run the focused optimizer population and require unchanged public model dumps, candidate identities, ordering, search and projection statuses, budgets, and plan population while private counters distinguish zero applicable proposals from proposals rejected before final acceptance. Falsify the no-extra-work rule with call counters around generation and verification, and require blocker records to contain no candidate syntax or raw exception/rejection strings.

Add a private bounded accounting model consumed by the existing search. Count only events already observed during proposal generation, transition verification, and final original-relative acceptance. Give missing primitive cost, unproved domain or cardinality, and already-localized evaluator limits stable internal reason codes with family and target provenance when those facts are available. Deduplicate deterministically under a fixed internal cap. Do not traverse again, call an evaluator for diagnostics, publish the records yet, or change current silent behavior.

### Phase close

Close after the private accounting is a production-consumed search seam, its falsification tests prove no additional generation or proof work, the current public characterization is unchanged, and the full gate passes.

```commit
refactor(formula): capture bounded optimization outcomes
```

## Phase 2: Cut over the explicit goal contract and protocol v17

**Execution mode: inline.**

Completes: ["explicit-goal-operation", "goal-policy", "truthful-result-accounting", "actionable-blockers", "protocol-v17"]

### Task 2.1: Replace the Python request and result contracts
Kind: batch
Applying: ["adopt-declarative-optimization-goals-and-explicit-claim-scope:explicit-goal-operation", "adopt-declarative-optimization-goals-and-explicit-claim-scope:initial-goal-semantics", "adopt-declarative-optimization-goals-and-explicit-claim-scope:fixed-bounded-search-and-proof", "adopt-declarative-optimization-goals-and-explicit-claim-scope:explicit-truthful-claims", "adopt-declarative-optimization-goals-and-explicit-claim-scope:bounded-actionable-blockers"]
Paths: ["packages/py-science-formula/src/py_science/formula/contracts/goals.py", "packages/py-science-formula/src/py_science/formula/contracts/optimization.py", "packages/py-science-formula/src/py_science/formula/contracts/requests.py", "packages/py-science-formula/src/py_science/formula/contracts/reports.py", "packages/py-science-formula/src/py_science/formula/contracts/__init__.py", "packages/py-science-formula/src/py_science/formula/models.py", "packages/py-science-formula/src/py_science/formula/__init__.py", "packages/py-science-formula/src/py_science/formula/_optimization/diagnostics.py", "packages/py-science-formula/src/py_science/formula/_optimization/search.py", "packages/py-science-formula/src/py_science/formula/_optimization/plans.py", "packages/py-science-formula/src/py_science/formula/_optimization/objectives.py", "packages/py-science-formula/src/py_science/formula/_service/orchestration.py", "packages/py-science-formula/src/py_science/formula/_service/optimization.py", "packages/py-science-formula/src/py_science/formula/_service/result_bounds.py", "packages/py-science-formula/src/py_science/formula/service.py", "packages/py-science-formula/src/py_science/formula/optimization.py", "tests/unit/optimization/test_goals.py", "tests/unit/optimization/test_search.py", "tests/unit/optimization/test_replay.py", "tests/unit/optimization/test_objectives.py", "tests/unit/optimization/test_budgets.py", "tests/unit/test_public_exports.py", "tests/e2e/test_formula_analysis.py", "tests/e2e/test_formula_system_analysis.py", "tests/distribution/test_python_package.py"]
Representative: Validate a required exact-symbolic, preserve-all, submitted-domain goal with a weighted objective; search every supported exact lane under fixed monotonic depth two; return an independently replayable plan carrying `strict_improvement` and a self-contained scope record.
Edge: Ordinary analysis has neither optimization controls nor an optimization result. Old objective/family request keys fail strict validation. Candidate identity remains the complete candidate JSON and excludes goal, claim, search, proof, and engine metadata. An incomplete empty result retains its observed classification but cannot imply absence beyond completed work.
Post-check: Authority check: assert defining-module, `models.py`, and package-root object identity for every new public contract and the absence of removed optimization objects. State check: cover expression and system requests, every fixed GoalSpec literal, both objectives, qualified proofs, all exact lanes, each result classification, incomplete search with and without plans, projection truncation, stable replay identity, strict rejection of former request keys, and installed-wheel imports. Require ordinary analysis to execute no optimizer call and serialize no optimization field.

Define the goal, search, proof, search-scope, claim, blocker, selection, and result-classification contracts once behind the existing compatibility facades. Replace, rather than layer beside, the old public optimization request/result types. The search profile enables every current exact lane, including finite-polynomial-sum optimization, without accepting family or depth controls. Project only `strict_improvement`; report `deterministic_ranked_prefix`; keep search completion, observed result classification, and output projection independent. Bound and deduplicate public blockers within the existing optimization output allowance. Preserve replay verification and complete candidate identity as correctness properties, not wire-compatibility promises.

### Task 2.2: Migrate the schema, adapter, and strict Pi bridge together
Kind: batch
Applying: ["adopt-declarative-optimization-goals-and-explicit-claim-scope:python-policy-pi-transport"]
Paths: ["scripts/generate-pi-formula-schema.py", "packages/pi-science/src/formula-schema.json", "packages/pi-science/bridge/formula_adapter.py", "packages/pi-science/src/bridge/protocol.ts", "packages/pi-science/src/bridge/requests.ts", "packages/pi-science/src/bridge/results.ts", "packages/pi-science/src/bridge/correlation.ts", "packages/pi-science/src/bridge/client.ts", "packages/pi-science/src/bridge/presentation.ts", "packages/pi-science/src/bridge.ts", "packages/pi-science/src/index.ts", "packages/pi-science/src/provision.ts", "packages/pi-science/tests/adapter.test.ts", "packages/pi-science/tests/bridge.test.ts", "packages/pi-science/tests/start.test.ts", "packages/pi-science/tests/provision.test.ts", "packages/pi-science/tests/package.test.ts", "tests/test_pi_schema_generation.py"]
Representative: Round trip a real protocol-v17 goal request through Python, reject a fabricated best/optimal claim and mismatched search scope, and present Python's strict-improvement or empty classification without deriving either in TypeScript.
Edge: Retain one intentional stale-version rejection fixture. Exact-key validation rejects v16/new-shape hybrids, former request controls, surplus claim values, inconsistent plan/classification populations, blocker/candidate confusion, and search/projection contradictions. TypeScript may check correlation and arithmetic integrity but never chooses a claim, reason, or objective relation.
Post-check: State check: regenerate the provider-compatible schema from the new Python authority, require all removed passive/legacy branches to be absent and all new required branches strict, then run real-adapter, strict-bridge, readiness, provisioning, packed-package, type, lint, and format populations. Falsify request-aware correlation by mutating every claim/scope/classification/blocker field independently. Require protocol constants to agree at every producer and consumer and the framed output limit to remain sufficient under maximal bounded diagnostics.

Advance the adapter and Pi to protocol v17 in the same transaction as the Python public cutover. Replace manual TypeScript request and result shapes, strict validators, request-aware correlation, and fixtures. Presentation may be minimally truthful in this phase; its complete agent guidance lands next. Do not introduce protocol negotiation or preserve v16 acceptance.

### Phase close

Close only when Python and Pi expose one explicit goal-driven operation, ordinary analysis is optimization-free, every result shape is strictly correlated under protocol v17, generated schema and package probes are current, the full gate passes, and the release gate passes because protocol, distribution, and provisioning changed.

```commit
feat(formula): adopt explicit optimization goals and claims
```

## Phase 3: Apply product claims and agent guidance

**Execution mode: inline.**

Completes: ["product-guidance"]

### Task 3.1: Publish the implemented request, result, and product boundaries
Kind: batch
Applying: ["adopt-declarative-optimization-goals-and-explicit-claim-scope:explicit-goal-operation", "adopt-declarative-optimization-goals-and-explicit-claim-scope:initial-goal-semantics", "adopt-declarative-optimization-goals-and-explicit-claim-scope:fixed-bounded-search-and-proof", "adopt-declarative-optimization-goals-and-explicit-claim-scope:explicit-truthful-claims", "adopt-declarative-optimization-goals-and-explicit-claim-scope:bounded-actionable-blockers", "adopt-declarative-optimization-goals-and-explicit-claim-scope:python-policy-pi-transport"]
Paths: ["docs/decisions/adopt-declarative-optimization-goals-and-explicit-claim-scope.md", ".awf/topics/parts/product/mathematical-input-contract/current-state.md", ".awf/topics/parts/product/analysis-report-contract/current-state.md", ".awf/topics/parts/product/mathematical-analysis-model/current-state.md", ".awf/topics/parts/product/product-boundary/current-state.md", ".awf/parts/agents-doc/identity.md", ".awf/docs/parts/architecture/overview.md", ".awf/docs/parts/architecture/components.md", ".awf/docs/parts/architecture/data-flow.md", ".awf/docs/parts/testing/tiers.md", ".awf/docs/parts/testing/layout.md", "docs/analysis-model.md", "docs/vision.md", "README.md", "packages/py-science-formula/README.md", "packages/pi-science/skills/formula-analysis/SKILL.md", "AGENTS.md", "docs/architecture.md", "docs/testing.md", "docs/topics/product/mathematical-input-contract.md", "docs/topics/product/analysis-report-contract.md", "docs/topics/product/mathematical-analysis-model.md", "docs/topics/product/product-boundary.md", "docs/decisions/INDEX.md", ".awf/awf.lock"]
Representative: Replace guidance that asks agents to choose an algorithmic family with a complete explicit goal request and show how to distinguish strict improvement, deterministic selection, incomplete search, projection truncation, and a blocker that is not a candidate.
Edge: Remove every current-state statement that ordinary analysis defaults to optimization or that protocol v16 carries optimizer results. Keep informational queries, scenarios, comparison, and dominance separate. Do not describe blockers as recommendations or any abstract-work result as runtime, finite-precision, best-candidate, or optimality evidence.
Post-check: Authority check: append `Implementing` and one Applied event containing all four declared claim updates, mutate exactly those four claim bodies with preserved Origin and appended Revised-by, and require `./awf context --show pending` to report no Remaining operation. Choreography check: render all managed outputs after source edits. State check: inspect the rendered analysis-model optimization request/result passages, architecture component and data-flow passages, capability evidence links, root and package examples, Pi skill request recipe, and compact presentation fixtures; require no active prose or fixture outside decision history to advertise passive optimization, former request controls, protocol v16 optimization, configurable depth, or unsupported optimality.

Update current-state authority only after the behavior exists. Enter the ADR into Implementing and apply its four claim updates in this same transaction. Refresh generated and hand-authored product guidance, package examples, agent identity, test evidence, and the product skill. Keep the plan mutable; terminal ADR and plan closure remains deferred until implementation assurance settles.

### Phase close

Close after claim replay, render, semantic prose review, live-link checks, the full gate, and the release gate pass over the documented protocol-v17 product.

```commit
feat(product): apply declarative optimization boundaries
```

## Definition of done

- `dod: explicit-goal-operation` Python and Pi accept optimization only through one strict explicit request with required goal, search, and proof policies plus an independent projection limit; ordinary analysis has no optimization control or result.
- `dod: goal-policy` The initial goal preserves all submitted outputs, uses submitted mathematical facts, supports only the existing unit or exact weighted aggregate abstract-work objective, and exposes none of the deferred R3, resource, numerical, runtime, hard-bound, or depth controls.
- `dod: truthful-result-accounting` Every plan reports only strict improvement with exact proof, cost, objective, search-scope, and engine semantics; every report separately identifies deterministic selection, observed population classification, search completion or incompleteness, and projection truncation without implying best or optimal.
- `dod: actionable-blockers` Bounded deduplicated blockers expose only localized missing cost, domain/cardinality, or evaluator-limit facts observed during existing work; they never carry speculative candidates, raw rejection text, or recommendation/proof status.
- `dod: protocol-v17` Generated schema, Python adapter, strict Pi validation and correlation, presentation, provisioning, package contents, and stale-version rejection agree on protocol v17 without moving mathematical policy into TypeScript.
- `dod: product-guidance` Current-state claims, analysis and architecture docs, package guidance, agent skill, identity, and capability evidence describe the implemented explicit goal contract and its exclusions; full and release gates pass and fresh implementation assurance finds no unresolved issue.

## Notes

Inline owners immediately correct stale instructions and record reasoned deviations here. Delegated owners report rather than edit; the orchestrator supplies each report to phase review and reconciles it with findings in one focused settlement commit before checkpointing or later execution. Every `pi-science#2` through `pi-science#4` assignment names exact path ownership, requires DONE or BLOCKED reporting, and carries the orchestrator contract through handoffs. The orchestrator records phase evidence, protocol/schema hashes, generated-prose review, deviations, and review settlements here before progression.

Phase 1 owner commit `5114bc2` added private bounded search accounting with no reported deviation; its focused optimizer population passed 87 tests and the full gate passed 540 Python and 131 Pi tests. Independent review found that generic unresolved facts and aggregate-wide missing costs were reported with unjustified domain/target confidence. The settlement restricts both blocker kinds to already-retained target-local evidence and recognizes only stable domain/cardinality facts; regressions cover a genuine target-local cardinality fact, unrelated assumptions, and missing costs in another system output.

Phase 2 expands its test paths to the existing optimizer, candidate comparison, dominance, scenario, schema, public-export, and package characterization populations required by the clean-break request/result migration, plus `_optimization/verifier.py` for the typed objective verification seam. This preserves the approved explicit-only boundary and existing mathematical invariants rather than restoring compatibility. The cutover removes passive optimization and migrates Python and Pi together to protocol v17. Phase review found five contract gaps: defaulted wire literals, an implicit submitted-domain policy, unreported ranked-prefix truncation, under-correlated blockers, and plan claims without configured limits. The settlement requires every request literal, exposes only `submitted_domain_v1`, reports projection truncation independently, correlates blocker reason, target, and uniqueness, and carries limits on each strict-improvement claim. Final schema SHA-256 is `9ad6f4169e6c30c3e9da78052a6c46c1fc1208225a947f2114e12acf3e19b0fb`. The verify pass found one mechanical residual: byte-bound truncation replaced an existing projection-limit qualification. The residual preserves and deduplicates both reasons with a bounded fallback. The full gate passes 546 Python and 122 Pi tests; the release gate passes source-pin installation, packaged startup, readiness, and diagnostics.

Phase 3 expands its paths to `packages/pi-science/tests/package.test.ts` because the shipped-skill package characterization asserted removed passive-advice wording and must track the explicit goal guidance in the same documentation transaction. The four declared claim updates are Applied with no remaining operation, every generated surface is current, active guidance removes the legacy optimization controls, and capability-evidence links resolve. The focused package population passes 7 tests, the full gate passes 546 Python and 122 Pi tests, and the release gate passes source-pin installation, packaged startup, readiness, and diagnostics.
