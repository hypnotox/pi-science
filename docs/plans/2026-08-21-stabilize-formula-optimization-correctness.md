---
format: plan-v2
date: 2026-08-21
adrs: [0017]
status: Implemented
---
# Plan: Stabilize Formula Optimization Correctness

## Goal

Correct the bounded optimization contract so valid exact-symbolic transformations may reduce aggregate work to zero, every retained analysis that did not execute optimization reports it as disabled, and agent-facing guidance describes deterministic presentation without claiming unproved superiority. Preserve protocol v12, default-on ordinary advice, the existing generator families and proof policy, and all exclusions around runtime, numerical behavior, unrestricted search, and algorithm replacement; do not begin the proposed first-class optimization operation or later upgrade phases.

## Architecture summary

Keep Python as the mathematical-policy owner and Pi as a strict transport and presentation layer. First, add failing regressions for neutral rewrites and then change the common Python verifier plus the public Python and TypeScript correlations from blanket positive work to `work_before > work_after >= 0` with positive, exactly correlated savings. Second, add failing retained-analysis, ordinary-analysis, candidate-comparison, dominance, adapter, and bridge regressions, then make the base `AnalysisSuccess.optimization` value disabled while leaving ordinary `analyze()` as the sole path that attaches an executed report; comparison and dominance continue to analyze retained work without running optimization, and their nested TypeScript correlation explicitly expects disabled reports. Third, update tool routing, compact presentation, the packaged product skill, and authoritative documentation sources so ordinary advice is discoverable, separately proved suggestions are not combined, and the first deterministically presented candidate is never described as mathematically best unless superiority is proved.

The three phases are independently green transactions. No request/result field, protocol version, generator family, proof rule, search bound, or module layout changes. Generated documentation changes originate in `.awf/` and travel with rendered outputs.

## Phase 1: Accept proved zero-post-work candidates

**Execution mode: subagent-driven.**

Completes: ["zero-post-work-candidates"]

### Task 1.1: Add failing zero-work contract regressions
Kind: batch
Applying: ["0017:initial-proved-families", "0017:python-owned-proof-and-ranking", "0017:backend-independent-policy"]
Paths: ["tests/unit/test_formula_optimization.py", "packages/pi-science/tests/adapter.test.ts", "packages/pi-science/tests/bridge.test.ts"]
Representative: Ordinary analysis of each of `x + 0`, `x * 1`, `x / 1`, and `x**1` publishes a `redundant_operation_removal` suggestion with work `1 -> 0`, savings `1`, a reparsable proposed candidate, proved equivalence, and a successful JSON model round trip.
Edge: Cover an equation-system form whose output multiplicity scales work before and savings while work after remains zero; reject negative `work_after`; reject a zero `work_before` candidate; preserve rejection of zero or negative savings and inconsistent numeric deltas. The real adapter and strict bridge must accept a Python-owned valid suggestion with `work_after: "0"` without adding transport-owned algebraic reasoning.
Post-check: State check on the regression-only snapshot, before production changes: run `uv run --locked pytest tests/unit/test_formula_optimization.py -k 'neutral_redundant_operations_can_reduce_work_to_zero or zero_work_optimization_scales_equation_output_multiplicity or optimization_suggestion_rejects_invalid_zero_or_negative_work'` and `npx vitest run packages/pi-science/tests/adapter.test.ts packages/pi-science/tests/bridge.test.ts -t 'zero-post-work'`. Require only the new neutral-publication, zero-valued model/round-trip, real-adapter, and strict-bridge assertions to fail for omission or rejection; the new negative/zero-before rejection assertions and every selected pre-existing test must pass. Record the exact failing test identities and messages.

This phase starts from the clean baseline at `79b605a97a011914da95700651c7e526b415551f` recorded in Notes, before any production or regression mutation. Add regressions before production changes. Build expected suggestion data through the public analysis/model seams rather than bypassing validation, and use exact aggregate values for the multiplicity fixture instead of assuming every system remains `1 -> 0`.

### Task 1.2: Correct Python verification and strict transport correlation
Kind: batch
Applying: ["0017:initial-proved-families", "0017:python-owned-proof-and-ranking", "0017:backend-independent-policy"]
Paths: ["packages/py-science-formula/src/py_science/formula/optimization.py", "packages/py-science-formula/src/py_science/formula/models.py", "packages/pi-science/src/bridge.ts", "tests/unit/test_formula_optimization.py", "packages/pi-science/tests/adapter.test.ts", "packages/pi-science/tests/bridge.test.ts"]
Representative: `_verify_candidate` retains a proved candidate when aggregate work is `1 -> 0`; `OptimizationSuggestion` and the TypeScript bridge accept the correlated strings `("1", "0", "1")`.
Edge: Require numeric `work_before > 0`, `work_after >= 0`, `savings > 0`, and exact `work_before - work_after == savings`. Preserve the existing proof-based symbolic correlation, equivalence evidence, conditions, positive-savings proof, negative-work rejection, and TypeScript's role as shape/correlation validation rather than mathematical policy.
Post-check: State check: rerun the exact Task 1.1 commands plus the complete optimization, adapter, and bridge files. Require every new regression to pass, all four public proposals to reparse and revalidate, the multiplicity values to equal direct aggregate analysis, and every malformed bridge fixture to remain rejected.

Change only the blanket positivity checks that incorrectly cover post-transformation work. Preserve the existing redundant-operation-removal generator and every family boundary; do not special-case neutral syntax in a generator, weaken the common verifier, or alter public request/result shape.

### Phase close

Confirm all four neutral forms and the equation-system multiplicity form publish independently proved positive reductions ending at zero, while negative or inconsistent work remains invalid and Pi accepts the valid Python-owned result.

```commit
fix(formula): permit zero-work optimized results
```

## Phase 2: Mark every unexecuted optimization report disabled

**Execution mode: subagent-driven.**

Completes: ["disabled-retained-optimization"]

### Task 2.1: Add failing optimization-ownership regressions
Kind: batch
Applying: ["0017:default-bounded-advice", "0017:qualified-informational-results", "0017:backend-independent-policy"]
Paths: ["tests/unit/test_formula_optimization.py", "tests/e2e/test_formula_candidate_comparison.py", "tests/e2e/test_formula_dominance.py", "packages/pi-science/tests/adapter.test.ts", "packages/pi-science/tests/bridge.test.ts"]
Representative: Direct retained analysis of `x + 0` reports `{requested_limit: 0, status: disabled, suggestions: [], qualifications: []}`; ordinary `analyze()` still executes the default limit-three search and publishes the Phase 1 suggestion; every nested comparison and dominance analysis reports disabled optimization even for an obviously optimizable computation.
Edge: Preserve ordinary `optimization.max_suggestions=0` disabled behavior, ordinary default complete/incomplete execution, comparison and dominance work/semantic conclusions, Python JSON round trips, real-adapter results, explicit nulls, and strict malformed-result rejection. Do not add optimization controls to comparison or dominance requests.
Post-check: State check on the regression-only snapshot, before production changes: run `uv run --locked pytest tests/unit/test_formula_optimization.py tests/e2e/test_formula_candidate_comparison.py tests/e2e/test_formula_dominance.py -k 'retained_analysis_disables_optimization or ordinary_analysis_optimization_ownership or nested_analysis_disables_optimization'` and `npx vitest run packages/pi-science/tests/adapter.test.ts packages/pi-science/tests/bridge.test.ts -t 'nested retained optimization disabled'`. Require only the new retained, comparison, dominance, real-adapter, and strict-bridge disabled-state assertions to fail because they observe limit-three `complete`; require the ordinary default-on and explicit-zero controls plus every selected pre-existing test to pass. Record the exact failing test identities and messages.

This phase starts from the reviewed Phase 1 close commit, with zero-post-work publication and transport green. Add regressions before changing construction defaults or bridge correlation. Replace any existing expectation that nested retained analysis equals ordinary default-on `analyze()` where that expectation conflates base analysis with executed advice.

### Task 2.2: Make retained analysis disabled and correlate nested transport explicitly
Kind: batch
Applying: ["0017:default-bounded-advice", "0017:qualified-informational-results", "0017:backend-independent-policy"]
Paths: ["packages/py-science-formula/src/py_science/formula/models.py", "packages/pi-science/src/bridge.ts", "tests/unit/test_formula_optimization.py", "tests/e2e/test_formula_candidate_comparison.py", "tests/e2e/test_formula_dominance.py", "packages/pi-science/tests/adapter.test.ts", "packages/pi-science/tests/bridge.test.ts"]
Representative: `AnalysisSuccess` construction without an attached executed report defaults to disabled; `analyze()` replaces it with the requested executed report; comparison and dominance preserve the disabled nested value through protocol-v12 validation.
Edge: Keep `_analyze_computation()` free of optimization execution, keep query attachment and ordinary result bounding unchanged, and keep comparison/dominance mathematics unchanged. TypeScript may validate nested reports against an explicit disabled expectation or an equivalent synthetic zero-limit retained request, but it must not silently treat them as ordinary default-on analyses or recreate optimization policy.
Post-check: State check: rerun the exact Task 2.1 commands plus the complete optimization, candidate-comparison, dominance, adapter, and bridge files. Require retained, comparison, and dominance nested reports to be disabled; ordinary omitted configuration to execute at limit three; ordinary explicit zero to remain disabled; and all semantic/work results to remain byte-for-byte unchanged apart from the corrected nested optimization fields.

Implement the narrow disabled `AnalysisSuccess.optimization` default and explicit nested transport correlation. Treat the existing `analyze()` attachment and `_analyze_computation()` comparison/dominance flow as invariants; do not modify service/comparison orchestration or execute optimization from either retained-analysis consumer. If implementation evidence contradicts that grounded premise, stop this phase and return for a separately sequenced spike rather than broadening the task.

### Phase close

Confirm no retained analysis claims a search ran, ordinary analysis remains default-on, comparison and dominance remain optimization-free, and Python plus Pi agree on every correlated state.

```commit
fix(formula): mark retained optimization disabled
```

## Phase 3: Make optimization routing and ranking language truthful

**Execution mode: subagent-driven.**

Completes: ["truthful-optimization-guidance"]

### Task 3.1: Add failing routing and compact-ranking regressions
Kind: batch
Applying: ["0017:python-owned-proof-and-ranking", "0017:qualified-informational-results", "0017:backend-independent-policy"]
Paths: ["packages/pi-science/tests/start.test.ts"]
Representative: Registered-tool assertions require routing metadata to mention bounded exact-symbolic optimization advice and compact output to label the displayed item first-ranked or first-presented rather than imply an unqualified mathematical best.
Edge: Cover populated, symbolic/incomparable deterministic ordering, disabled, multi-target atomic, and incomplete-search fixtures while preserving canonical `details` and finite-precision qualifications.
Post-check: State check on the regression-only snapshot, before `index.ts` changes: run `npx vitest run packages/pi-science/tests/start.test.ts -t 'advertises bounded optimization advice|presents first-ranked optimization advice'`. Require only those new routing and first-ranked terminology assertions to fail against the old metadata/unqualified projection, while every selected pre-existing assertion passes; record the exact failures.

This phase starts from the reviewed Phase 2 close commit, with retained-analysis ownership and nested protocol correlation green.

### Task 3.2: Correct tool routing and compact presentation
Kind: batch
Applying: ["0017:python-owned-proof-and-ranking", "0017:qualified-informational-results", "0017:backend-independent-policy"]
Paths: ["packages/pi-science/src/index.ts", "packages/pi-science/tests/start.test.ts"]
Representative: Registered-tool routing mentions bounded exact-symbolic optimization advice, and compact output identifies the displayed suggestion as first-ranked or first-presented rather than an unqualified mathematical best.
Edge: Keep the complete canonical report in `details`, preserve additional-suggestion counts and incomplete-search guidance, keep disabled advice quiet, retain exact-symbolic finite-precision qualification, and do not introduce runtime, numerical-stability, hardware, or global-optimality claims.
Post-check: State check: rerun the exact Task 3.1 command and the complete registered-tool test file against default, disabled, populated, multi-target, symbolic-ranking, and incomplete fixtures. Inspect the compact output boundary and require it to distinguish deterministic presentation from proved superiority without any Pi-owned savings comparison.

Update only routing metadata and presentation terminology. Pi must not compare savings or decide superiority.

### Task 3.3: Synchronize the packaged skill and authoritative documentation
Kind: batch
Applying: ["0017:default-bounded-advice", "0017:python-owned-proof-and-ranking", "0017:qualified-informational-results", "0017:independently-bounded-search", "0017:backend-independent-policy"]
Paths: ["packages/pi-science/skills/formula-analysis/SKILL.md", "packages/pi-science/tests/package.test.ts", "README.md", "packages/py-science-formula/README.md", "docs/analysis-model.md", ".awf/docs/parts/architecture/overview.md", ".awf/docs/parts/architecture/data-flow.md", ".awf/docs/parts/testing/tiers.md", ".awf/docs/parts/testing/layout.md", "docs/architecture.md", "docs/testing.md", ".awf/awf.lock"]
Representative: The skill introduces ordinary verified local advice early, calls the compact item first-ranked/first-presented, and tells agents not to combine separate independently proved suggestions unless Python returns them as one atomic transformation set.
Edge: Preserve the exact aggregate-work objective, independent proof against the original retained computation, conditional/incomparable ranking qualification, request bounds, incomplete-search meaning, finite-precision caveat, and exclusions. Change generated architecture/testing publications only through their `.awf/` authorities; keep the editable body of `docs/analysis-model.md` within its owned in-place region.
Post-check: Authority check: run `./awf render` and read back every authored and rendered path. State check: run a literal `rg -n -F 'best proved'` census over exactly `README.md`, `packages/py-science-formula/README.md`, `packages/pi-science/skills/formula-analysis/SKILL.md`, `docs/analysis-model.md`, `.awf/docs/parts/architecture/overview.md`, `.awf/docs/parts/architecture/data-flow.md`, `docs/architecture.md`, and `docs/testing.md`; capture its status, print `GUIDANCE_CENSUS_OK` only when the command ran and returned the expected no-match status, and require that sentinel with zero matches. Historical plans and ADR wording are outside this current-guidance population. Leave semantic equivalents to a recorded focused prose review. Run `npx vitest run packages/pi-science/tests/package.test.ts` and `./awf check` after rendering; require both to pass, existing independent search bounds and incomplete-search meaning to remain explicit, and rendered prose to preserve meaning across the named boundaries.

Keep one canonical explanation per document owner and reference existing policy rather than adding a second optimization specification. Record the generated-prose and compact-output inspection boundaries and result in Notes.

### Phase close

Confirm routing advertises the shipped advice, compact and durable guidance distinguish deterministic ordering from proved superiority, atomicity guidance forbids combining separate suggestions, and all AWF outputs are synchronized.

```commit
docs(formula): clarify optimization advice ranking
```

## Definition of done

- `dod: zero-post-work-candidates` All four supported neutral forms and an output-multiplied equation-system form publish independently verified exact-symbolic reductions with nonnegative post-work and positive exactly correlated savings; negative, zero-before, zero-saving, and inconsistent work claims remain invalid in Python and strict Pi transport.
- `dod: disabled-retained-optimization` `_analyze_computation()` and every nested candidate-comparison and dominance analysis report disabled optimization without executing search, while ordinary `analyze()` still executes default limit-three advice and honors explicit zero; Python, adapter, bridge, and JSON round trips agree.
- `dod: truthful-optimization-guidance` Tool routing, compact output, packaged skill, current documentation, generated publications, and tests describe bounded exact-symbolic advice, atomic independently proved suggestions, deterministic non-superiority ordering, incomplete search, and finite-precision/runtime exclusions without stale unqualified `best` language.

## Notes

Inline owners immediately correct stale instructions and record reasoned deviations here. Delegated owners report rather than edit; the parent supplies their report to phase review and reconciles it with findings in one focused settlement commit before checkpointing or later execution.

- Approved boundary: Phase 0 only; no protocol bump, successor ADR, first-class optimize operation, plan IR, cost profile, composed search, algorithmic transformation, numerical lane, or speculative optimizer module split.
- Baseline at `79b605a97a011914da95700651c7e526b415551f`: managed worktree clean; focused optimization/comparison/dominance population `92 passed`; full Python population `392 passed`; `./scripts/check` passed with schema determinism, Pyright, Ruff, TypeScript lint/type/format, `112` Vitest tests, and AWF checks green.
- Revalidated audit divergences: candidate-comparison coverage is under `tests/e2e/`; dominance shares the retained-analysis consequence; TypeScript needs both zero-post-work and nested-disabled correlation changes; the adapter owns serialization rather than independent work mathematics; current compact rendering does not literally print `best`, while the skill and current guides use that unsupported term.
- Initial plan-review reasoned disposition: remove conditional authority to edit service/comparison orchestration because current source proves the disabled model default plus nested bridge correlation is the narrow complete fix; any contradictory implementation evidence must stop for a separately sequenced spike. Make both regression-only snapshots reproducible with exact commands, named new-test selectors, expected failure sets, and pre-existing-green requirements. Confine the stale-wording census to an exact current-guidance population with a checked sentinel, leaving semantic-equivalent review to focused human inspection.
- Phase 2 reasoned deviation: add `tests/e2e/test_formula_analysis.py` to the implementation transaction because changing the retained-model default invalidated ordinary-analysis expected reports; updating that test preserves the approved invariant that ordinary `analyze()` replaces the retained default with an executed limit-three report. The full gate passed with no service/comparison orchestration change.
- Phase 2 review settlement: report-only review accepted the omitted-path deviation and found two mechanical coverage regressions where prior full nested-versus-ordinary analysis equality had been narrowed to optimization-only assertions. Restore equality after normalizing only the optimization field for both candidate comparison and dominance, while retaining exact disabled/default-on assertions.
- Phase 3 semantic inspection: inspected `packages/pi-science/src/index.ts` compact advice and routing boundaries; the packaged skill; current root and Python package guides; editable analysis-model body; authored and rendered architecture/testing boundaries. All retain canonical `details`, disabled quietness, finite-precision and runtime exclusions, independent bounds and incomplete-search meaning, and state first-ranked deterministic presentation without an unproved superiority claim. The skill introduces ordinary verified local advice early and prohibits combining separate suggestions unless Python returns one atomic transformation set.
- Phase 3 review settlement: report-only review accepted the plan-Notes path deviation and found one mechanical coverage gap: the compact-ranking regression used only one numeric suggestion. Add a registered-tool fixture with two Python-ordered suggestions carrying incomparable symbolic savings, then assert compact text presents only the first array entry as first-ranked, retains the second in canonical details, and makes no best/superiority claim.
