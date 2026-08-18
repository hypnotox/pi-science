---
format: plan-v2
date: 2026-08-18
adrs: [require-actionable-bounded-query-blockers]
status: Proposed
---
# Plan: Make bounded query diagnostics actionable

## Goal

Replace every evaluator-level `query family is unsupported` result with safe, reason-specific, actionable guidance for agents probing bounded formula queries. Preserve the public request/result schemas, conservative conclusions, proof policy, resource limits, and supported mathematical families.

## Architecture summary

The reusable Python package remains the sole owner of query applicability and diagnostic policy. A dependency-leaf internal query-diagnostic representation carries stable reason categories, trustworthy bounded observations, configured limits, and non-promissory recovery hints, then renders them into the existing `blockers: tuple[str, ...]` contract; this change adds no public diagnostic-code or transport field. Backend preflight seams return typed bounded failure information instead of raw exceptions or undifferentiated `None`, while evaluator policy maps that information to the currently supported reformulations. Equivalence distinguishes operand rejection from post-reasoning expansion, closed form distinguishes count, bounds, shell, and summand shape, properties and limits distinguish rational bounds, normalization, reasoning, and axis ambiguity, and asymptotics distinguishes rational, linear-exponential, realness, reconstruction, and parameter-dependent-pole failures. Already-specific blockers remain unchanged.

## Phase 1: Diagnose bounded rational equivalence, properties, and limits

**Execution mode: inline.**

Advances: ["reason-specific-query-blockers", "bounded-diagnostic-safety"]

### Task 1.1: Capture rational diagnostic regressions before implementation
Context: ["0004:assumption-aware-qualified-reasoning"]
Paths: ["tests/unit/test_formula_queries.py", "tests/unit/test_formula_properties.py"]

Add failing tests that preserve `conclusion="unresolved"` while requiring distinct actionable blockers for: an equivalence operand outside bounded rational syntax; an assumption or definition expansion that leaves the bounded rational family; a properties target rejected by a measured rational bound; a fixed-`p=12` closed-form target whose `q**12` factor first exceeds the supported degree 8; a limit target rejected by the same measured bound; backend rational normalization refusal; and an ambiguous sign-property axis. The fixed-order regression must use `q**12 * (13 - 12*q) / (1 - q)**2` and assert the trustworthy first observed overflow of degree 12 versus 8 without treating the expression as mathematically invalid or claiming a later aggregate degree that bounded traversal did not compute. Sign-axis recovery must recommend reducing to one unambiguous variable rather than supplying an unsupported `variable` field. Retain existing exact assertions for already-specific reasoning, denominator, substitution, pole, and sign-chart blockers.

### Task 1.2: Add typed bounded failures and consume them in rational evaluators
Context: ["0004:assumption-aware-qualified-reasoning"]
Paths: ["packages/py-science-formula/src/py_science/formula/query_diagnostics.py", "packages/py-science-formula/src/py_science/formula/sympy_backend.py", "packages/py-science-formula/src/py_science/formula/query.py", "packages/py-science-formula/src/py_science/formula/properties.py", "tests/unit/test_formula_queries.py", "tests/unit/test_formula_properties.py"]

Create a dependency-leaf internal diagnostic model that deterministically renders a failed family or precondition, safe observed/configured values when present, and one supported recovery direction into blocker text. Extend rational IR measurement with a typed failure result that distinguishes node, unsupported-form, degree, exponent, coefficient-bit, and expanded-term limits while preserving the existing successful measurement and boolean preflight callers. Traversal must report only facts computed under existing bounded inspection, use stable first-failure ordering, and never include exceptions or backend object representations.

Use the typed result in equivalence before and after reasoning expansion so operand-family rejection and expansion-family rejection remain distinct. Refactor the shared properties/limits shape seam to distinguish reasoning application failure, rational preflight failure, backend translation/cancellation/fraction refusal, and axis ambiguity. Include actual and configured metrics only when the bounded seam measured them; categorical backend refusals stay categorical. Render hints only for supported actions: bounded rational operands for equivalence, smaller univariate rational targets for properties/limits, and one unambiguous variable for sign checks. Preserve all resource constants, conclusions, evidence, assumptions, and already-specific blockers.

### Phase close

Land the failing regressions and rational diagnostic implementation as one green correction. From the phase snapshot, run `uv run --locked pytest tests/unit/test_formula_queries.py tests/unit/test_formula_properties.py` and require exit zero, including the fixed-`p=12` first observed degree-12-versus-8 assertions and the existing properties/limit refusal suite. Then run `./scripts/check` and require exit zero.

```commit
fix(formula): explain bounded rational query refusals
```

## Phase 2: Diagnose closed-form and asymptotic family refusals

**Execution mode: inline.**

Completes: ["reason-specific-query-blockers", "bounded-diagnostic-safety"]

### Task 2.1: Capture series and asymptotic diagnostic regressions before implementation
Context: ["0004:assumption-aware-qualified-reasoning"]
Paths: ["tests/unit/test_formula_queries.py", "tests/unit/test_asymptotics.py"]

Add failing tests for every remaining stable reason category currently collapsed into the generic blocker. Closed-form public-input cases must cover target/shell bounds, zero and more-than-eight sibling sums, negative-infinity bounds, forbidden or index-dependent summand structure, and failure to match `(a*k+b)*r**k`. Asymptotic public-input cases must distinguish a target that is neither bounded rational nor supported linear-exponential syntax, rational degree overflow such as `x**9`, missing realness of non-query parameters, and parameter-dependent denominator paths. Add deterministic backend-seam fault-injection cases for bounded linear-exponential term-count, reconstruction, and rendering refusals so each refusal is asserted without depending on an incidental public expression reaching it. Keep convergence, nested-sum, reasoning-bound, exponential-fact, and existing backend failure diagnostics unchanged.

### Task 2.2: Return bounded failure reasons from series and asymptotic seams
Context: ["0004:assumption-aware-qualified-reasoning"]
Paths: ["packages/py-science-formula/src/py_science/formula/query_diagnostics.py", "packages/py-science-formula/src/py_science/formula/series.py", "packages/py-science-formula/src/py_science/formula/asymptotics.py", "packages/py-science-formula/src/py_science/formula/sympy_backend.py", "tests/unit/test_formula_queries.py", "tests/unit/test_asymptotics.py"]

Replace each remaining exact `query family is unsupported` return with the reason established by its bounded structural check. Closed form must report sum population, upper-bound direction, shell/resource refusal, summand structure, or geometric-linear mismatch and name the supported one-to-eight sibling `(a*k+b)*r**k` form only where relevant. Extend both `bounded_exponential_decomposition` and `bounded_asymptotic_rational` with distinct success, recognized-refusal, and no-match outcomes carrying safe typed failure data for grammar mismatch, resource bounds, reconstruction/refusal, missing real-parameter facts, and parameter-dependent pole paths rather than collapsing those conditions to `None`.

In asymptotic arbitration, exponential success wins. A rational success or recognized rational refusal outranks exponential no-match; a recognized exponential refusal outranks rational no-match; report a neither-family diagnostic only when both seams return no-match. Preserve the current successful-family preference when both could match, and never let an early exponential grammar no-match mask a bounded rational result. Do not expose caught exceptions, claim an algebraic rewrite is equivalent, or convert unsupported questions into request errors.

Preserve all existing successful proof paths and already-specific blockers. Finish with a production-source state search proving the exact literal `query family is unsupported` is absent from `packages/py-science-formula/src/py_science/formula/`; the search must establish successful execution separately from its empty result.

### Phase close

Land the closed-form and asymptotic regressions with their typed failure propagation as one green correction. From the phase snapshot, run `uv run --locked pytest tests/unit/test_formula_queries.py tests/unit/test_asymptotics.py tests/unit/test_formula_properties.py` and require exit zero. Run a checked empty-result search for the removed generic blocker across production formula sources, then run `./scripts/check` and require exit zero.

```commit
fix(formula): localize unsupported query families
```

## Phase 3: Teach agents how to use reason-specific blockers

**Execution mode: inline.**

Completes: ["agent-diagnostic-guidance"]

### Task 3.1: Strengthen current-state blocker guarantees through awf ownership
Kind: batch
Applying: ["require-actionable-bounded-query-blockers:actionable-bounded-query-blockers"]
Context: ["0004:assumption-aware-qualified-reasoning", "0004:explicit-bounded-mathematical-queries"]
Paths: ["docs/decisions/require-actionable-bounded-query-blockers.md", "docs/decisions/INDEX.md", ".awf/topics/parts/product/mathematical-analysis-model/current-state.md", ".awf/topics/parts/product/analysis-report-contract/current-state.md", "docs/topics/product/mathematical-analysis-model.md", "docs/topics/product/analysis-report-contract.md", "docs/analysis-model.md", ".awf/awf.lock"]
Representative: The analysis-model claim owns bounded evaluator refusal policy, including failed supported families, structural/resource bounds, ambiguous axes, and missing preconditions. The report-contract claim owns inspectable reasons, trustworthy bounded observations, and safe reformulation guidance without implying broader mathematical support.
Edge: Keep request-validation diagnostics distinct from query-answer blockers; do not turn implementation-specific constant values into durable product guarantees or alter ADR-0004.
Post-check: Run `./awf render` as choreography, then stage the complete application transaction and run `./awf check staged` and `./awf check` as authority enforcement, all with successful exit status. Inspect the changed authored claims, both rendered topic publications, the generated decision index, and the edit-in-place `docs/analysis-model.md` paragraphs for semantic agreement, conservative wording, contradictory generic guidance, and unintended placeholders. Confirm the ADR history contains Implementing followed by one Applied event naming both updates, both matching claim mutations append this ADR to their existing Revised-by provenance, and the terminal set contains both operations as Applied with no Remaining or Canceled operation. Confirm the generated changed set includes only the pending ADR, authored sources, their rendered publications, generated decision index, intended analysis-model body, and `.awf/awf.lock` as produced by ownership.

Transition the pending ADR from Proposed to Implementing and append one Applied event containing both declared update operations in the same pair-atomic transaction as their matching claim mutations. Update the authored current-state claims and the `docs/analysis-model.md` edit-in-place body to establish reason-specific, bounded, actionable blockers as part of inspectable query results. Describe measured limits as result details rather than promises that every backend refusal has a numeric metric. Preserve unsupported questions as localized `unresolved` or `inapplicable` answers.

### Task 3.2: Update direct-Python and Pi agent guidance
Paths: ["packages/py-science-formula/README.md", "packages/pi-science/skills/formula-analysis/SKILL.md", "packages/pi-science/tests/package.test.ts"]

Explain that query blockers identify a failed family, exceeded bound, ambiguous axis, or missing supported precondition; tell agents to use the stated observation and recovery hint to simplify, reformulate, or select a supported source family. State that hints are conservative and do not certify equivalence or promise wider evaluator support. Add focused packaged-skill assertions for this contract without snapshotting exact prose or duplicating the evaluator's reason vocabulary in TypeScript. Inspect both guidance artifacts for agreement with the applied claims, including actionable observations, conservative hints, no equivalence certification, no expanded-support promise, contradictory generic guidance, and unintended placeholders.

### Phase close

Land the pending ADR's Implementing/Applied history, generated decision index, authored current-state sources, rendered publications, the analysis-model edit-in-place body, Python README, packaged skill, package assertion, and awf lock together. Complete Task 3.1's pair-atomic application, render, authority, and semantic state checks plus Task 3.2's guidance inspection; run `npm run test:pi -- packages/pi-science/tests/package.test.ts`; then run `./scripts/check` and require all commands to exit zero.

```commit
fix: explain (applies require-actionable-bounded-query-blockers batch)
```

## Definition of done

- `dod: reason-specific-query-blockers` No production evaluator returns the generic `query family is unsupported` blocker; each former site reports the bounded family, structure, limit, or precondition that rejected the query and a safe recovery direction where one exists.
- `dod: bounded-diagnostic-safety` Diagnostics preserve existing resource limits and conservative conclusions, include actual/configured values only from bounded trustworthy measurements, expose no raw exceptions or backend representations, and leave public request/result schemas unchanged.
- `dod: agent-diagnostic-guidance` Current-state documentation, the direct-Python guide, and the packaged Pi skill consistently teach agents to act on reason-specific blockers without interpreting a hint as proof or expanded mathematical support.

## Notes

Inline owners immediately correct stale instructions and record reasoned deviations here. Delegated owners may report rather than edit; the parent supplies the report to phase review and reconciles it with findings in one focused post-review settlement commit before checkpointing or later execution. Record deviations, spike answers, follow-ups, and findings surfaced during implementation.

- Plan review: require the fixed-`p=12` regression to report the trustworthy first observed `q**12` degree overflow rather than an aggregate numerator degree that bounded traversal has not safely computed.
- Plan review: distinguish asymptotic no-match from recognized refusal and define arbitration so the evaluator's exponential-first probe cannot mask a supported or specifically refused rational target.
- Linked-authority freshness: the successor ADR affects completed Phase 1 through `32e7f51` and Phase 2 through `3003d7f`. Before Phase 3, renew assurance separately on each final phase snapshot against reason-specific refusal categories, bounded measured details only, safe non-promissory hints, unchanged public schemas and conservative conclusions, and request-validation separation; rerun each phase's focused evidence and settle any findings before continuing from a clean green baseline.
- Renewed Phase 1 assurance found recursive degree, coefficient-bit, and expanded-term upper bounds rendered as observed values. The settled correction preserves conservative preflight refusal but omits the observation when cancellation or arithmetic slack makes the estimate non-exact; exact node, exponent, literal, and structurally noncancelling degree observations remain. Phase 2 renewed assurance found no issues.
