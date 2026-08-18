---
format: plan-v2
date: 2026-08-18
adrs:
  - adopt-explicit-reusable-verified-query-candidates
status: Proposed
---
# Plan: Implement reusable verified query candidates

## Goal

Let an `equivalence` or `limit` query explicitly analyze the single verified candidate of an earlier named `closed_form` query while preserving bounded qualification, source provenance, request/result correlation, and submitted direct work. Arbitrary query graphs, forward references, derived targets for properties or asymptotics, scenario-context queries, candidate indexing, and broader closed-form families remain outside this plan.

## Architecture summary

Execution is one cross-layer, independently green transaction because the strict Python request/result model, generated provider schema, exact private protocol, TypeScript bridge, and current-state documentation must advance together. Requests add a derived target shaped as `{kind: "derived", query: <earlier query name>}` only to equivalence and limit variants. Python validates dependency-earlier structure before evaluation, retains prior results by query name during sequential evaluation, and resolves a derived operand only from a proved or proved-under-assumptions answer carrying checked closed-form evidence and exactly one candidate.

A resolved derived query reports the candidate interpretation as `normalized_target`. A structurally valid dependency whose source produces no eligible operand remains correlated to the request, reports `inapplicable`, uses `normalized_target: null`, and names the source query and conclusion in its blocker; it never falls back to the submitted expression or equation RHS. Downstream conditions and assumption provenance are deterministically deduplicated under public bounds, source evidence remains on the source result, and a qualified source cannot create an unqualified downstream proof. Qualification overflow returns `unresolved`.

Python owns all dependency, eligibility, evaluation, qualification, and fail-closed policy. Schema generation and Pi transport carry strict shapes and correlation only. The exact private protocol advances from v6 to v7. Derived operands never enter scenarios, operation counts, direct-work aggregation, or equation dependency/reuse analysis. No enabling refactor beyond a cohesive sequential query-resolution seam is authorized.

## Phase 1: Implement explicit sequential derived targets

**Execution mode: subagent-driven.**

Completes: ["derived-target-contract", "verified-query-reuse", "protocol-v7-correlation", "synchronized-query-guidance"]

### Task 1.1: Establish lifecycle authority and failing contract regressions
Applying: ["adopt-explicit-reusable-verified-query-candidates:explicit-derived-query-targets", "adopt-explicit-reusable-verified-query-candidates:dependency-earlier-query-reuse", "adopt-explicit-reusable-verified-query-candidates:verified-candidate-applicability", "adopt-explicit-reusable-verified-query-candidates:composed-query-qualification", "adopt-explicit-reusable-verified-query-candidates:python-owned-derived-target-policy"]
Paths: ["docs/decisions/adopt-explicit-reusable-verified-query-candidates.md", "docs/decisions/INDEX.md", "tests/unit/test_formula_queries.py", "tests/e2e/test_formula_analysis.py", "tests/e2e/test_formula_system_analysis.py", "tests/test_pi_schema_generation.py", "packages/pi-science/tests/adapter.test.ts", "packages/pi-science/tests/bridge.test.ts", "packages/pi-science/tests/start.test.ts", "packages/pi-science/tests/provision.test.ts", ".awf/awf.lock"]

Before production mutation, transition ADR-adopt-explicit-reusable-verified-query-candidates from Proposed to Accepted through the ADR lifecycle workflow. Its three current-state operations apply together in Task 1.4; terminal Implemented remains deferred until implementation assurance settles.

Add focused failing tests for expression and equation-system requests in which a closed-form query is followed by derived-target equivalence and limit queries. Assert that successful dependents expose the candidate interpretation, preserve the derived source target, inherit and deduplicate source conditions and assumption provenance, promote an otherwise unqualified proof when the source is qualified, and leave all submitted direct-work fields unchanged.

Add structural request failures localized to the dependent target for unknown, forward, and self references; a non-closed-form source; and derived targets on closed-form, properties, or asymptotic consumers. Add valid-result cases for unresolved and inapplicable source conclusions, missing verification evidence, zero candidates, and multiple candidates: each dependent remains present, returns `inapplicable`, has `normalized_target: null`, names the source and conclusion in a blocker, and performs no submitted-target fallback. Add deterministic bound tests for qualification deduplication and overflow to `unresolved` without duplicating source evidence as an assumption. Cover generated expression/system schemas, protocol-v7 adapter and bridge round trips, request/result correlation, strict nullability, compact text, and rejection of protocol v6.

Run the focused Python, schema, and Pi tests before implementation and record in Notes that they fail because derived targets and protocol v7 are absent, not because fixtures are malformed.

### Task 1.2: Add Python-owned derived-target resolution and qualification
Applying: ["adopt-explicit-reusable-verified-query-candidates:explicit-derived-query-targets", "adopt-explicit-reusable-verified-query-candidates:dependency-earlier-query-reuse", "adopt-explicit-reusable-verified-query-candidates:verified-candidate-applicability", "adopt-explicit-reusable-verified-query-candidates:composed-query-qualification", "adopt-explicit-reusable-verified-query-candidates:python-owned-derived-target-policy"]
Paths: ["packages/py-science-formula/src/py_science/formula/models.py", "packages/py-science-formula/src/py_science/formula/service.py", "packages/py-science-formula/src/py_science/formula/query.py", "packages/py-science-formula/src/py_science/formula/__init__.py", "tests/unit/test_formula_queries.py", "tests/e2e/test_formula_analysis.py", "tests/e2e/test_formula_system_analysis.py"]

Extend request and resolved-target unions narrowly so only equivalence and limit requests accept a derived target, while existing expression omission and equation-target requirements remain unchanged for submitted operands. Export the derived-target request model from the public Python package alongside peer target models and cover that import surface. Make result `normalized_target` nullable only when an explicit derived operand is unavailable; every other result continues to require an interpretation. Validate references in request order with exact target paths and reject structural dependency mistakes before mathematical evaluation.

Introduce one cohesive sequential resolution seam owned by Python service/query orchestration. Retain evaluated query results by unique name, verify source kind, conclusion, checked closed-form evidence, and single-candidate eligibility, then pass the candidate expression through the existing bounded evaluator seams. Do not reparse rendered user-controlled text through unrestricted SymPy; use the checked internal expression/interpretation translation boundary and preserve existing node, reasoning, rendering, and report bounds.

For eligible operands, compose downstream qualifications by stable deterministic deduplication of conditions and relationship provenance. Preserve source evidence only on the source result, keep unsupported relevant assumptions and downstream blockers semantically distinct, and prevent a proved-under-assumptions source from yielding an unqualified proof. If composition exceeds a public bound, return a correlated `unresolved` answer with a localized blocker. For an ineligible runtime source, synthesize only the approved `inapplicable` result with null normalized target; never call the evaluator on the submitted target. Make all failing Python tests from Task 1.1 pass without changing direct-work, scenario, or closed-form derivation behavior.

### Task 1.3: Advance generated schema and strict Pi transport to protocol v7
Kind: batch
Applying: ["adopt-explicit-reusable-verified-query-candidates:explicit-derived-query-targets", "adopt-explicit-reusable-verified-query-candidates:verified-candidate-applicability", "adopt-explicit-reusable-verified-query-candidates:python-owned-derived-target-policy"]
Paths: ["scripts/generate-pi-formula-schema.py", "packages/pi-science/src/formula-schema.json", "packages/pi-science/bridge/formula_adapter.py", "packages/pi-science/src/bridge.ts", "packages/pi-science/src/index.ts", "tests/test_pi_schema_generation.py", "packages/pi-science/tests/adapter.test.ts", "packages/pi-science/tests/bridge.test.ts", "packages/pi-science/tests/start.test.ts", "packages/pi-science/tests/provision.test.ts"]
Representative: Generate discriminated equivalence and limit variants that accept submitted or derived targets as allowed by expression/system context, carry the same resolved derived target in results, and accept null normalized targets only for unavailable derived operands.
Edge: Keep every other query variant, result field, envelope bound, timeout behavior, and fail-closed exact-key validation unchanged. TypeScript validates shape and correlation but never decides candidate eligibility or qualification.
Post-check: Generate `packages/pi-science/src/formula-schema.json`; require `uv run --locked pytest tests/test_pi_schema_generation.py` and `npx vitest run packages/pi-science/tests/adapter.test.ts packages/pi-science/tests/bridge.test.ts packages/pi-science/tests/start.test.ts packages/pi-science/tests/provision.test.ts` to exit 0. Run `matches=$(rg -n 'protocol-v6|version: 6|PROTOCOL_VERSION = 6' packages/pi-science || true); printf '%s\n' "$matches"; test "$(printf '%s\n' "$matches" | sed '/^$/d' | wc -l)" -eq 1; printf '%s\n' "$matches" | grep -Eq '^packages/pi-science/tests/adapter\.test\.ts:[0-9]+:.*version: 6'`; this must leave exactly the intentional stale-v6 incompatible-protocol request and no other v6 fixture or label. Require `git diff --check` to exit 0.

Advance the adapter and bridge exact protocol version to v7, including the provisioning health fixture. Change the adapter's incompatible-protocol test to submit version 6 so it is the sole intentional stale-version match. Update request/result TypeScript unions and exact validators for derived targets and conditional normalized-target nullability. Preserve result order and correlate each result with the corresponding request target without introducing graph scheduling. Update compact output so a successful derived query displays its candidate and an unavailable operand displays the source-specific blocker without dereferencing a null interpretation. Make the generated-schema, adapter, bridge, provisioning, and registered-tool tests from Task 1.1 pass through the real Python policy boundary.

### Task 1.4: Apply current-state claims and synchronize product guidance
Kind: batch
Applying: ["adopt-explicit-reusable-verified-query-candidates:explicit-derived-query-targets", "adopt-explicit-reusable-verified-query-candidates:dependency-earlier-query-reuse", "adopt-explicit-reusable-verified-query-candidates:verified-candidate-applicability", "adopt-explicit-reusable-verified-query-candidates:composed-query-qualification", "adopt-explicit-reusable-verified-query-candidates:python-owned-derived-target-policy"]
Paths: ["docs/decisions/adopt-explicit-reusable-verified-query-candidates.md", "docs/decisions/INDEX.md", ".awf/topics/parts/product/mathematical-input-contract/current-state.md", ".awf/topics/parts/product/mathematical-analysis-model/current-state.md", ".awf/topics/parts/product/analysis-report-contract/current-state.md", ".awf/docs/parts/architecture/data-flow.md", ".awf/docs/parts/testing/tiers.md", ".awf/docs/parts/testing/layout.md", "docs/topics/product/mathematical-input-contract.md", "docs/topics/product/mathematical-analysis-model.md", "docs/topics/product/analysis-report-contract.md", "docs/topics/product/index.md", "docs/analysis-model.md", "docs/architecture.md", "docs/testing.md", "packages/py-science-formula/README.md", "packages/pi-science/skills/formula-analysis/SKILL.md", "packages/pi-science/src/index.ts", ".awf/awf.lock"]
Representative: Update the explicit-query input claim with dependency-earlier derived targets, the assumption-aware reasoning claim with verified-candidate eligibility and bounded qualification composition, and the qualified-conclusions claim with derived-source provenance plus null normalized targets only for unavailable operands.
Edge: Preserve each claim's Origin and append this ADR to Revised-by. Append Implementing and one Applied event containing exactly all three declared update operations; do not append Implemented. Do not imply broader closed-form families, arbitrary dependency graphs, derived properties/asymptotics, scenario queries, direct-work replacement, or Pi-owned mathematical policy.
Post-check: Run `./awf render`; require `./awf check` and `./awf check staged` to report zero findings; inspect the ADR history, all three authored claims, the architecture and testing source parts, their rendered topic pages, `docs/decisions/INDEX.md`, `docs/analysis-model.md`, `docs/architecture.md`, `docs/testing.md`, the Python README, packaged skill, and Pi routing text; require the Applied operation set to equal the ADR State changes and `git diff --check` to exit 0.

Document the exact request spelling, earlier-only rule, eligible source requirements, qualification inheritance, null unavailable-target result, no-fallback behavior, and separation from submitted work. The generated prose review must confirm that "derived value" never reads as numerical scenario evaluation or an implementation-cost substitution and that compact text remains a projection over full structured details.

### Phase close

Authority checks: `./awf check` and `./awf check staged` must report zero findings, and the ADR Applied partition must exactly match its three State changes. State checks:

```bash
uv run --locked pytest \
  tests/unit/test_formula_queries.py \
  tests/e2e/test_formula_analysis.py \
  tests/e2e/test_formula_system_analysis.py \
  tests/test_pi_schema_generation.py
npx vitest run \
  packages/pi-science/tests/adapter.test.ts \
  packages/pi-science/tests/bridge.test.ts \
  packages/pi-science/tests/start.test.ts
uv run --locked pyright
npm run check:pi
git diff --check
```

Combined authority-and-state gate: `./scripts/check`. The focused derived-target tests must have been observed failing before Task 1.2 and must now pass. Inspect and record the generated current-state, analysis-model, architecture, README, skill, and compact-output readings named in Task 1.4. Close one transaction:

```commit
feat(formula): reuse verified query candidates
```

## Definition of done

- `dod: derived-target-contract` Expression and equation-system requests accept explicit earlier closed-form targets only for equivalence and limit, reject every invalid dependency shape with a localized request error, and preserve request-order result correlation.
- `dod: verified-query-reuse` Eligible verified candidates feed bounded equivalence and limit evaluation with deterministic qualification/provenance composition, while unavailable operands return correlated inapplicable results with null normalized targets and no fallback; submitted work and scenarios remain unchanged.
- `dod: protocol-v7-correlation` The generated schema, adapter, strict TypeScript bridge, provisioning health check, registered Pi tool, and compact projection carry protocol v7 derived targets and conditional nullability while rejecting stale or malformed envelopes.
- `dod: synchronized-query-guidance` The ADR application, current-state claims, rendered topics, analysis and architecture docs, Python README, packaged skill, tests, and Pi routing metadata describe and enforce the same bounded composition contract, and the full project gate passes.

## Notes

- Plan review disposition: expanded protocol-v7 scope to the provisioning health fixture, the public Python target export, and the authored architecture/testing sources so the declared phase can close green and documentation renders from its owners.
- Plan review disposition: replaced the vague protocol-v6 census with an executable exact residual check: only the adapter incompatible-protocol request may retain `version: 6`; all current fixtures, labels, health checks, and constants advance to v7.

Inline owners immediately correct stale instructions and record reasoned deviations here. Delegated owners may report rather than edit; the parent supplies the report to phase review and reconciles it with findings in one focused post-review settlement commit before checkpointing or later execution. Record deviations, test-first failure evidence, generated-prose review evidence, follow-ups, and findings surfaced during implementation.
