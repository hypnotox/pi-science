---
format: plan-v2
date: 2026-08-18
adrs:
  - adopt-bounded-nested-finite-polynomial-closed-forms
status: Proposed
---
# Plan: Implement bounded nested finite polynomial closed forms

## Goal

Let direct `closed_form` queries derive and independently verify one bounded nested finite-polynomial `Sum` tree, including the motivating `(p + 1)**2` coefficient count, while preserving existing geometric closed forms, explicit derived-query composition, and submitted direct work. General nested summation, mixed or multiple trees, rational-function coefficients, conditional ranges, implicit property/limit/asymptotic consumers, cross-equation inlining, and whole-system optimization remain outside this plan.

## Architecture summary

Execution is one independently green Python-owned transaction because the recursive family, checked SymPy seams, cross-layer evidence, current-state claims, partial-support guidance, and future inventory describe one shipped applicability boundary. `derive_closed_form()` classifies a target before the existing geometric-linear route: exactly one nested finite-polynomial tree under the bounded arithmetic shell enters a separate innermost-first evaluator, while nonnested geometric behavior remains unchanged and mixed topologies fail closed.

At each recursive level, project-owned policy applies bounded reasoning substitutions and already verified inner-candidate replacement, then checks finite affine-integral bounds, ordered-or-empty range proof, allowed names and coefficients, and degree at most eight in every still-active binder. The depth-four, eight-sum-node, target, intermediate, rendering, reasoning, and report limits remain per selected expression or equation RHS. A proved-empty range becomes exact zero; unproved ordering is unresolved. Backend code generates collision-free polynomial antidifference witnesses behind bounded translation, but Python independently checks the one-step identity and inclusive boundary difference, parses the candidate back through the restricted model, rejects escaped temporary names, and reapplies resource bounds before recursion continues. Backend representation never defines the public degree limit.

Only a direct `closed_form` query invokes this family. Direct properties, limits, and asymptotics over a nested sum remain unsupported; later equivalence or limit queries may consume the proved candidate only through the existing explicit derived-target path. Candidates remain informational and never replace submitted operation counts, aggregate work, scenarios, equation reuse, or output-domain multiplicity. The request/result schema and private protocol stay at v7 because no public shape changes.

## Phase 1: Ship the bounded nested finite-polynomial family

**Execution mode: subagent-driven.**

Completes: ["bounded-nested-closure", "verified-recursive-policy", "preserved-query-and-work-boundaries", "honest-partial-guidance"]

### Task 1.1: Establish lifecycle authority and failing family regressions
Applying: ["adopt-bounded-nested-finite-polynomial-closed-forms:bounded-nested-polynomial-family", "adopt-bounded-nested-finite-polynomial-closed-forms:polynomial-coefficient-and-range-contract", "adopt-bounded-nested-finite-polynomial-closed-forms:independently-verified-antidifference-witnesses", "adopt-bounded-nested-finite-polynomial-closed-forms:explicit-nested-query-composition"]
Paths: ["docs/decisions/adopt-bounded-nested-finite-polynomial-closed-forms.md", "docs/decisions/INDEX.md", "tests/unit/test_formula_queries.py", "tests/e2e/test_formula_analysis.py", "tests/e2e/test_formula_system_analysis.py"]

Before lifecycle or test mutation, run the existing focused Python and Pi suites named in the Phase close and require a green baseline. Then transition ADR-adopt-bounded-nested-finite-polynomial-closed-forms from Proposed to Accepted through the ADR lifecycle workflow. Its two declared current-state updates apply together in Task 1.4; terminal Implemented remains deferred until implementation assurance settles.

Add focused failing tests for direct expression and named-equation-RHS `closed_form` requests. The acceptance matrix must include `Sum(Sum(1, (l, -k, k)), (k, 0, p)) = (p + 1)**2`, polynomial coefficients containing declared symbols and still-outer binders, affine dependent bounds, collision-prone distinct binder names, and exact boundary cases for depth four, eight total sum nodes, and degree eight. Assert the degree rule after reasoning substitutions and after verified inner replacement, including rejection when either transformation raises a still-active binder above degree eight.

Add refusal and qualification cases for depth five, nine sum nodes, degree nine, rational-function coefficients, forbidden or undeclared names, a bound depending on its own binder, non-affine or non-integral bounds, mixed nested/geometric or multiple-tree topology, infinite nesting, and target/intermediate/rendering overflow. Cover proved ordered ranges, proved-empty ranges closing to zero before backend reversed-range semantics, and unknown ordering returning `unresolved` with a localized family/precondition blocker. Preserve existing geometric-linear conclusions and diagnostics.

Add falsification seams for backend candidate absence, antidifference-identity failure, inclusive-boundary failure, restricted-candidate parse failure, escaped temporary names, and resource overflow. Assert that no generated candidate becomes proof without checked `ClosedFormEvidence`. Run the focused Python tests before implementation and record in Notes that they fail because nested mathematical closed forms are still rejected, not because fixtures are malformed.

### Task 1.2: Implement project-owned recursive policy and checked backend witnesses
Applying: ["adopt-bounded-nested-finite-polynomial-closed-forms:bounded-nested-polynomial-family", "adopt-bounded-nested-finite-polynomial-closed-forms:polynomial-coefficient-and-range-contract", "adopt-bounded-nested-finite-polynomial-closed-forms:independently-verified-antidifference-witnesses"]
Paths: ["packages/py-science-formula/src/py_science/formula/series.py", "packages/py-science-formula/src/py_science/formula/sympy_backend.py", "packages/py-science-formula/src/py_science/formula/query.py", "tests/unit/test_formula_queries.py", "tests/e2e/test_formula_analysis.py", "tests/e2e/test_formula_system_analysis.py"]

Add a cohesive nested-family classification and recursive evaluator beside the existing sibling geometric-linear route in `series.py`; do not weaken or reinterpret the geometric recognizer. In `query.py`, gate this new route to direct `ClosedFormQuery` evaluation so `_property_expression()` preserves its existing geometric replacement behavior but does not implicitly derive a nested candidate for direct properties, limit, or asymptotic queries. Preflight the single-tree topology, total descendant sum count, maximum depth, bounded shell, lexical binder ownership, declared/free-name set, exact-rational polynomial coefficient grammar, and affine bounds before backend generation. Evaluate innermost-first. At each level apply the existing bounded reasoning context, replace only already verified inner candidates through binder-safe expression traversal, measure polynomial degree in every binder still active at that point, prove integral bounds, and require ordered or proved-empty range semantics. Accumulate bounded, stable assumption provenance and conditions without treating backend evidence as an assumption.

Extend `sympy_backend.py` with bounded polynomial-antidifference generation and an independently callable verifier. Translate active and outer binders to collision-free private backend symbols, bound input and every intermediate, and return only a candidate/witness representation that the caller can verify without trusting generation. Verify the exact one-step identity and inclusive boundary difference independently, then translate through bounded rendering and restricted `parse_expression`; reject parse failures, temporary-name escape, unsupported internal nodes, or exceeded node/render limits. A proved-empty range must short-circuit to internal zero without asking SymPy to interpret reversed finite bounds.

After every recursive replacement, rerun intermediate and result preflight. Produce exactly one informational candidate with finite-antidifference checked evidence only after every level succeeds; retain ordered-range conditions and assumption provenance, use `proved_under_assumptions` when qualifications require it, and otherwise fail closed with the localized blockers exercised in Task 1.1. Do not call the direct-work closure helper as mathematical proof and do not introduce unrestricted backend summation as public applicability policy.

### Task 1.3: Prove explicit composition and transport-neutral work preservation
Kind: batch
Applying: ["adopt-bounded-nested-finite-polynomial-closed-forms:explicit-nested-query-composition", "adopt-bounded-nested-finite-polynomial-closed-forms:bounded-nested-polynomial-family", "adopt-bounded-nested-finite-polynomial-closed-forms:independently-verified-antidifference-witnesses"]
Paths: ["tests/unit/test_formula_queries.py", "tests/e2e/test_formula_analysis.py", "tests/e2e/test_formula_system_analysis.py", "tests/test_pi_schema_generation.py", "packages/pi-science/tests/adapter.test.ts", "packages/pi-science/tests/bridge.test.ts", "packages/pi-science/tests/start.test.ts"]
Representative: Round-trip the motivating nested count through the public Python API, real protocol-v7 adapter, strict bridge, and registered Pi tool; assert the proved candidate and checked evidence while the canonical submitted work remains byte-for-byte or mathematically unchanged as appropriate.
Edge: Direct nested properties, limits, and asymptotics remain unsupported. A later explicit derived equivalence or limit may consume the proved nested candidate through existing source eligibility and qualification composition; no direct implicit consumer, schema variant, protocol version, TypeScript mathematical policy, or submitted-work substitution is added.
Post-check: Require `uv run --locked pytest tests/unit/test_formula_queries.py tests/e2e/test_formula_analysis.py tests/e2e/test_formula_system_analysis.py tests/test_pi_schema_generation.py` and `npx vitest run packages/pi-science/tests/adapter.test.ts packages/pi-science/tests/bridge.test.ts packages/pi-science/tests/start.test.ts` to exit 0. Regenerate the Pi schema to a temporary file or use the deterministic schema test and require no diff in `packages/pi-science/src/formula-schema.json`; require the protocol to remain v7 and `git diff --check` to exit 0.

Extend Python regressions so direct `properties`, `limit`, and `asymptotic` requests over nested sums retain their established unsupported outcome, while a proved nested `closed_form` followed by an explicit derived equivalence and limit succeeds with source qualifications preserved. Reuse the harmonic-style system fixture to query manageable named RHS chunks and prove the per-output nested coefficient count without inlining named equations or bypassing per-target limits. Assert that operation counts, aggregate work, scenarios, dependency reuse, primitive invocations, and the separately reported output-domain multiplicity remain unchanged, including the existing quartic invocation result.

Add real adapter, bridge, and registered-tool success plus unresolved-range cases. Assert full structured details retain evidence, conditions, blockers, and candidate interpretation. Transport tests must demonstrate that the unchanged protocol-v7 result shape already carries the new Python-owned conclusion; TypeScript must not classify nested families or verify mathematics.

### Task 1.4: Apply current-state claims and synchronize partial-family guidance
Kind: batch
Applying: ["adopt-bounded-nested-finite-polynomial-closed-forms:bounded-nested-polynomial-family", "adopt-bounded-nested-finite-polynomial-closed-forms:polynomial-coefficient-and-range-contract", "adopt-bounded-nested-finite-polynomial-closed-forms:independently-verified-antidifference-witnesses", "adopt-bounded-nested-finite-polynomial-closed-forms:explicit-nested-query-composition", "adopt-bounded-nested-finite-polynomial-closed-forms:explicit-partial-family-boundary"]
Paths: ["docs/decisions/adopt-bounded-nested-finite-polynomial-closed-forms.md", "docs/decisions/INDEX.md", ".awf/topics/parts/product/mathematical-analysis-model/current-state.md", ".awf/topics/parts/product/analysis-report-contract/current-state.md", ".awf/docs/parts/architecture/data-flow.md", ".awf/docs/parts/testing/layout.md", ".awf/docs/parts/testing/tiers.md", ".awf/docs/parts/roadmap/ideas.md", "docs/topics/product/mathematical-analysis-model.md", "docs/topics/product/analysis-report-contract.md", "docs/topics/product/index.md", "docs/analysis-model.md", "docs/architecture.md", "docs/testing.md", "docs/roadmap.md", "packages/py-science-formula/README.md", "packages/pi-science/skills/formula-analysis/SKILL.md", "packages/pi-science/src/index.ts", "packages/pi-science/tests/package.test.ts", ".awf/awf.lock"]
Representative: Replace the obsolete blanket statement that nested mathematical closed forms are unsupported with an explicit partial-family description, exact motivating syntax, limits, ordered-or-empty qualification, direct-query boundary, verified derived reuse, and separation from submitted evaluation work.
Edge: Preserve the mathematical-input claim because request syntax and protocol shape do not change. Preserve each updated claim's Origin and append this ADR to Revised-by. Do not imply rational-function coefficients, multiple or mixed trees, infinite nesting, higher limits, conditional or piecewise ranges, implicit consumers, staged derived-to-closed-form composition, cross-equation inlining, or whole-system optimization.
Post-check: Run `./awf render` and `./awf check`; stage the complete pair-atomic application snapshot, verify that the staged diff contains the Implementing/Applied history, both authored claim mutations, and their rendered outputs, then require `./awf check staged` to report zero findings. Inspect the ADR history and Applied partition, both authored claims, authored architecture/testing/roadmap parts, every rendered path listed above, the Python README, packaged skill, Pi routing metadata, and packed-skill test; require the Applied operation set to equal the ADR State changes, all shipped descriptions to label the capability partial, every ADR-listed excluded extension to appear in the future-candidate inventory, and `git diff --check` to exit 0.

Append Implementing and one Applied event containing exactly the two declared update operations, without appending another Accepted event or appending Implemented. Update `assumption-aware-query-reasoning` with the bounded recursive policy, degree-measurement point, qualification, and independently verified backend boundary. Update `qualified-query-conclusions` with nested candidate evidence, localized unresolved/empty-range behavior, and preservation of submitted work. Do not revise the mathematical-input claim because accepted syntax is unchanged.

Update architecture and testing sources, the edit-in-place analysis model, Python README, packaged product skill, and concise Pi routing metadata so they describe the same partial family without duplicating full grammar in routing text. Add all intentionally excluded extensions from the ADR to `.awf/docs/parts/roadmap/ideas.md`, including rational-function coefficients, multiple or mixed trees, infinite nesting, higher limits, conditional range forms, direct implicit consumers, staged derived-to-closed-form composition, safe cross-equation inlining, and deeper whole-system optimization analysis. Render owned outputs and add a package regression proving the updated partial-support guidance ships. The semantic rendering review must confirm that the new closed form reads as an informational mathematical candidate, not submitted evaluation work or a whole-system optimization result.

### Phase close

Authority checks: `./awf check` must report zero findings. Stage the complete transaction, verify that the staged diff contains the ADR Implementing/Applied history, both matching claim mutations, and rendered outputs, then require `./awf check staged` to report zero findings and the ADR Applied partition to exactly match its two State changes. State checks:

```bash
uv run --locked pytest \
  tests/unit/test_formula_queries.py \
  tests/e2e/test_formula_analysis.py \
  tests/e2e/test_formula_system_analysis.py \
  tests/test_pi_schema_generation.py
npx vitest run \
  packages/pi-science/tests/adapter.test.ts \
  packages/pi-science/tests/bridge.test.ts \
  packages/pi-science/tests/start.test.ts \
  packages/pi-science/tests/package.test.ts
uv run --locked pyright
npm run check:pi
git diff --check
```

Combined authority-and-state gate: `./scripts/check`. The focused nested-family tests must have been observed failing before Task 1.2 and must now pass. Confirm the generated schema has no diff and the protocol remains v7. Inspect and record the partial-family, submitted-work separation, and future-candidate readings named in Task 1.4. Close one transaction:

```commit
feat(formula): derive bounded nested polynomial sums
```

## Definition of done

- `dod: bounded-nested-closure` Direct expression and named-equation `closed_form` queries derive the motivating nested count and the complete accepted finite-polynomial matrix within depth four, eight sum nodes, degree eight, affine-integral ordered-or-empty ranges, and existing resource bounds; excluded topologies fail closed with localized blockers.
- `dod: verified-recursive-policy` Python owns innermost-first family checks and degree measurement after reasoning and inner replacement, while collision-free backend witnesses are independently checked for antidifference and inclusive boundaries, parsed through the restricted model, and rejected on escaped names, failed verification, or resource overflow.
- `dod: preserved-query-and-work-boundaries` Existing geometric closed forms remain unchanged; nested forms run directly only for `closed_form`; explicit derived equivalence and limit reuse remains qualified; direct implicit consumers stay unsupported; submitted operation counts, work, scenarios, equation reuse, output multiplicity, schema, and protocol remain unchanged.
- `dod: honest-partial-guidance` The Applied ADR claims, rendered current state, architecture, analysis model, testing docs, Python README, packaged skill, Pi routing metadata, and package tests consistently label the family partial, distinguish candidates from evaluation work, and inventory every intentionally excluded extension as a future candidate; the full project gate passes.

## Notes

Inline owners immediately correct stale instructions and record reasoned deviations here. Delegated owners may report rather than edit; the parent supplies the report to phase review and reconciles it with findings in one focused post-review settlement commit before checkpointing or later execution. Record deviations, test-first failure evidence, generated-prose review evidence, follow-ups, and findings surfaced during implementation.
