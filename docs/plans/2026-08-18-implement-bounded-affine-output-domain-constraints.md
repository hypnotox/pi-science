---
format: plan-v2
date: 2026-08-18
adrs:
  - adopt-bounded-affine-output-domain-constraints
status: Proposed
---
# Plan: Implement bounded affine output-domain constraints

## Goal

Ship the reviewed bounded equation-local affine constraint family with exact effective domains, qualified work, scenario and targeted-query semantics, inspectable provenance, and strict protocol transport. Do not add constraint-only domains, disconnected or general polyhedral regions, non-unit floor semantics, or nonlinear solving.

## Architecture summary

Python remains the sole mathematical-policy owner. A named `DomainConstraint` identifies one equation output-index target; a project-owned normalizer validates the approved affine or conjunctive absolute grammar, isolates that target, and contributes dependencies and candidate bounds to the existing acyclic output-domain graph. Mandatory finite base domains and normalized constraints produce analyzer-owned bounded `Min`/`Max` effective-domain expressions, which feed one compatibility classifier, reverse aggregation, scenario recomputation, equation-local query reasoning, and structured report provenance. Generic formula calls and SymPy never define constraint acceptance or intersection semantics.

The public request and result shapes advance the private protocol atomically. Pi validates and transports the strict wire contract without reimplementing normalization, compatibility, cardinality, or proof policy. Existing unconstrained and ADR-0010 dependent-domain requests preserve their results. The implementation closes as one independently green cross-layer transaction because strict exact-key reports and equation-local semantics cannot safely expose a partially wired public constraint shape.

## Phase 1: Ship bounded affine constraint intersections end to end

**Execution mode: subagent-driven.**

Completes: ["bounded-constraint-contract", "exact-constrained-analysis", "isolated-constraint-reasoning", "strict-cross-layer-delivery", "synchronized-constraint-guidance"]

### Task 1.1: Establish the lifecycle and test-first acceptance matrix
Kind: batch
Applying: ["adopt-bounded-affine-output-domain-constraints:named-targeted-local-constraints", "adopt-bounded-affine-output-domain-constraints:order-decomposable-affine-family", "adopt-bounded-affine-output-domain-constraints:constrained-domain-dependency-and-intersection", "adopt-bounded-affine-output-domain-constraints:global-compatibility-and-specialized-emptiness", "adopt-bounded-affine-output-domain-constraints:whole-equation-local-reasoning", "adopt-bounded-affine-output-domain-constraints:inspectable-constrained-domain-reports"]
Paths: ["docs/decisions/0013-adopt-bounded-affine-output-domain-constraints.md", "docs/decisions/INDEX.md", "tests/e2e/test_formula_system_analysis.py", "tests/unit/test_formula_scenarios.py", "tests/unit/test_formula_queries.py", "tests/unit/test_error_translation.py", "tests/test_pi_schema_generation.py", "packages/pi-science/tests/adapter.test.ts", "packages/pi-science/tests/bridge.test.ts", "packages/pi-science/tests/start.test.ts", "packages/pi-science/tests/provision.test.ts"]
Representative: A two-index equation with finite rectangular base domains and named target-`j` constraints `i + j <= N` and `j <= K` reports `j <= Min(N - i, K)`, exact clamped cardinality and work, equation-qualified provenance, specialized fixed and choice domains, and constraint-qualified equation-targeted queries.
Edge: Cover strict integer normalization, equality, supported `Abs` upper forms, reverse-LHS dependencies, multiple bounds, parameter-dependent dominance, globally proved contradiction, unresolved compatibility, specialization-empty zero, binder/global shadowing, duplicate names, missing or wrong targets, cycles, real operands, non-unit coefficients, chained/disjunctive relationships, rejected absolute lower/equality forms, nonlinear grammar, and unchanged unconstrained/dependent requests.
Post-check: First require the existing focused Python, schema, and Pi suites named in `Paths` to pass before lifecycle or test mutation. Then transition the ADR from Proposed to Accepted without applying claims, add the public acceptance and refusal matrix, and observe focused failures attributable to the absent constraint model, effective-domain analysis, scenario/query context, or protocol-v8 transport rather than malformed fixtures. Preserve those red results in Notes; do not weaken existing oracles.

### Task 1.2: Build the bounded constraint model, normalization, graph, and effective-domain work
Kind: batch
Applying: ["adopt-bounded-affine-output-domain-constraints:named-targeted-local-constraints", "adopt-bounded-affine-output-domain-constraints:order-decomposable-affine-family", "adopt-bounded-affine-output-domain-constraints:constrained-domain-dependency-and-intersection", "adopt-bounded-affine-output-domain-constraints:global-compatibility-and-specialized-emptiness", "adopt-bounded-affine-output-domain-constraints:inspectable-constrained-domain-reports"]
Paths: ["packages/py-science-formula/src/py_science/formula/models.py", "packages/py-science-formula/src/py_science/formula/expressions.py", "packages/py-science-formula/src/py_science/formula/parser.py", "packages/py-science-formula/src/py_science/formula/domains.py", "packages/py-science-formula/src/py_science/formula/reasoning.py", "packages/py-science-formula/src/py_science/formula/work.py", "packages/py-science-formula/src/py_science/formula/sympy_backend.py", "packages/py-science-formula/src/py_science/formula/service.py", "packages/py-science-formula/src/py_science/formula/__init__.py", "tests/e2e/test_formula_system_analysis.py", "tests/unit/test_error_translation.py"]
Representative: Preserve the submitted constraints separately from an effective per-index domain whose lower bound is the bounded maximum of all normalized lowers and whose upper bound is the bounded minimum of all normalized uppers; use the effective domains in dependency ordering, inclusive extents, operation categories, opaque work, and primitive invocations.
Edge: Add explicit analyzer-generated minimum and maximum expression semantics across traversal, substitution, rendering, integrality, node accounting, and work preflight; ordinary submitted formulas must not acquire a new generic `Min`/`Max` or `Abs` policy. Interpret only exact restricted-SymPy `Abs` spelling and arity inside constraint normalization. Bound each equation to at most 32 constraints, include every relationship in the existing request-byte budget, retain the 4096 reasoning/work ceilings, and keep repeated result growth within existing report and scenario populations.
Post-check: Run the focused system and diagnostic tests from this task. Inspect every accepted normalized relationship and effective bound, require all emitted expressions to remain within node/render budgets, require exact diagnostic paths under `equations[i].constraints[j]`, and compare representative unconstrained and ADR-0010 reports byte-for-byte or model-for-model as appropriate.

Implement a dedicated triangular compatibility classifier rather than treating failure to prove nonnegative as contradiction. Prove a request-invalid intersection only from bounded evidence that it is uniformly empty under global facts and predecessor extrema; retain parameter-dependent or undecidable intersections with exact clamped work and explicit unresolved qualification. Reject any LHS output binder that shadows a declared global variable before domain construction.

### Task 1.3: Recompute scenarios and isolate whole-equation query reasoning
Kind: batch
Applying: ["adopt-bounded-affine-output-domain-constraints:global-compatibility-and-specialized-emptiness", "adopt-bounded-affine-output-domain-constraints:whole-equation-local-reasoning", "adopt-bounded-affine-output-domain-constraints:inspectable-constrained-domain-reports"]
Paths: ["packages/py-science-formula/src/py_science/formula/models.py", "packages/py-science-formula/src/py_science/formula/reasoning.py", "packages/py-science-formula/src/py_science/formula/query.py", "packages/py-science-formula/src/py_science/formula/service.py", "packages/py-science-formula/src/py_science/formula/work.py", "tests/unit/test_formula_scenarios.py", "tests/unit/test_formula_queries.py", "tests/e2e/test_formula_system_analysis.py"]
Representative: A fixed scenario substitutes global parameters into normalized constraints, recomputes effective domains and work, and closes a specialized empty region to zero; a finite-choice scenario emits effective-domain maps under exactly the canonical keys used by `choice_work`. A query targeting the constrained equation may consume its effective bounds and named constraints, while the same query against another equation or a top-level expression cannot.
Edge: Remove only stale general domain-order qualifications superseded by scenario recomputation, preserve unrelated blockers, and bound recomputation by the existing maximum of 256 generated choice results. Constraint context applies to both sides of the owning equation but enters a query answer's provenance only when consumed; local names reused by different equations remain unambiguous.
Post-check: Run the scenario, query, and system suites in `Paths`. Require fixed and every generated choice result to pair work with the matching specialized effective domain; assert exact zero and no stale ordering blocker for proved-specialized emptiness; assert global assumptions and equation-qualified constraint uses separately; and prove isolation with negative controls for unrelated equation and expression targets.

Use this exact public shape. `DomainConstraint` has required `name`, `target`, and `relationship`; `EquationRequest.constraints` is a required-shape tuple with default empty, maximum 32, and names unique within the equation. `EffectiveIndexDomain` has `index`, rendered `lower`, and rendered `upper`. `ConstraintUse` has `equation`, `name`, `target`, and unchanged `relationship`. `EquationEffectiveDomains` has `equation` and an LHS-ordered tuple of `EffectiveIndexDomain`.

`EquationReport` adds required `constraints`, `effective_domains`, and `constraint_uses` tuples, empty for unconstrained equations. `QueryAnswer` adds a required `constraint_uses` tuple, populated only by consumed local facts. `ScenarioResult` adds required `effective_domains` and `choice_effective_domains`: a scenario without choices uses the former and an empty map; a scenario with choices uses an empty former tuple and a map whose keys exactly equal `choice_work`, with each value an equation-ordered tuple of `EquationEffectiveDomains`. Existing `relationships_used` continues to carry global assumptions and domain facts rather than local constraints. These fields are non-null and bounded by 32 indices/constraints per equation, 128 equations, 256 generated choice combinations, 4096 characters per rendered effective bound, and the existing serialized-response ceiling. Preserve unchanged submitted relationship text and stable constraint names; exact request paths remain diagnostic-only.

### Task 1.4: Advance and strictly transport the cross-layer contract
Kind: batch
Applying: ["adopt-bounded-affine-output-domain-constraints:named-targeted-local-constraints", "adopt-bounded-affine-output-domain-constraints:inspectable-constrained-domain-reports"]
Paths: ["scripts/generate-pi-formula-schema.py", "packages/pi-science/src/formula-schema.json", "packages/pi-science/bridge/formula_adapter.py", "packages/pi-science/src/bridge.ts", "packages/pi-science/src/provision.ts", "packages/pi-science/src/index.ts", "tests/test_pi_schema_generation.py", "packages/pi-science/tests/adapter.test.ts", "packages/pi-science/tests/bridge.test.ts", "packages/pi-science/tests/start.test.ts", "packages/pi-science/tests/provision.test.ts", "packages/pi-science/tests/package.test.ts"]
Representative: A real protocol-v8 adapter, strict bridge, provisioning health request, and registered tool round-trip the named simplex constraint and its full submitted/effective/provenance and scenario result shapes without TypeScript interpreting the relation.
Edge: Advance every live version constant and fixture from v7 to v8; retain only the deliberate incompatible-protocol negative fixture at v7. Exact-key validators reject missing, extra, malformed, cross-equation, over-budget, or version-mismatched constraint fields. The generated provider schema is regenerated only from the Python model and generator.
Post-check: State checks: run `uv run --locked pytest tests/test_pi_schema_generation.py` and `npx vitest run packages/pi-science/tests/adapter.test.ts packages/pi-science/tests/bridge.test.ts packages/pi-science/tests/start.test.ts packages/pi-science/tests/provision.test.ts packages/pi-science/tests/package.test.ts`; require the generated schema to match a fresh temporary generation; require both live constants to equal 8; and run the Phase-close confined census, whose sole stale-v7 match is the incompatible request in `packages/pi-science/tests/adapter.test.ts`. Exercise malformed and successful requests through the real adapter, strict bridge, readiness gate, and registered callback. Authority check: inspect Pi source and require no affine normalization, compatibility, or cardinality policy.

### Task 1.5: Apply current-state claims and synchronize bounded-family guidance
Kind: batch
Applying: ["adopt-bounded-affine-output-domain-constraints:named-targeted-local-constraints", "adopt-bounded-affine-output-domain-constraints:order-decomposable-affine-family", "adopt-bounded-affine-output-domain-constraints:constrained-domain-dependency-and-intersection", "adopt-bounded-affine-output-domain-constraints:global-compatibility-and-specialized-emptiness", "adopt-bounded-affine-output-domain-constraints:whole-equation-local-reasoning", "adopt-bounded-affine-output-domain-constraints:inspectable-constrained-domain-reports", "adopt-bounded-affine-output-domain-constraints:explicit-deferred-constraint-families"]
Paths: ["docs/decisions/0013-adopt-bounded-affine-output-domain-constraints.md", "docs/decisions/INDEX.md", ".awf/topics/parts/product/mathematical-input-contract/current-state.md", ".awf/topics/parts/product/mathematical-analysis-model/current-state.md", ".awf/topics/parts/product/analysis-report-contract/current-state.md", ".awf/docs/parts/architecture/data-flow.md", ".awf/docs/parts/testing/layout.md", ".awf/docs/parts/testing/tiers.md", ".awf/docs/parts/roadmap/ideas.md", "docs/topics/product/mathematical-input-contract.md", "docs/topics/product/mathematical-analysis-model.md", "docs/topics/product/analysis-report-contract.md", "docs/topics/product/index.md", "docs/analysis-model.md", "docs/architecture.md", "docs/testing.md", "docs/roadmap.md", "packages/py-science-formula/README.md", "packages/pi-science/skills/formula-analysis/SKILL.md", "packages/pi-science/src/index.ts", "packages/pi-science/tests/package.test.ts", ".awf/awf.lock"]
Representative: Current-state and shipped guidance describe one partial bounded equation-local family with mandatory base domains, named explicit targets, exact intersections, whole-equation/query scope, qualified emptiness, Python ownership, and protocol-v8 transport, while the roadmap retains every excluded family from the ADR.
Edge: Preserve each updated claim's Origin and prior Revised-by sequence before appending this ADR. Do not imply constraint-only completeness, general polyhedral counting, non-unit floors, disconnected regions, nonlinear solving, request-wide scope, or TypeScript mathematical policy.
Post-check: Choreography check: run `./awf render` and read back every authored source and generated target in `Paths`. Authority checks: stage the complete pair-atomic snapshot, run `./awf check` and `./awf check staged`, and prove that the five updated claim operations exactly equal the ADR State changes. State checks: verify the roadmap inventory contains constraint-only domains, non-unit floor/divisibility, chained relations, disjunctions, disconnected absolute regions, general affine lattice counting, and nonlinear products, powers, variable division, and functions; require every shipped description to call the supported family partial and preserve the submitted/effective/provenance distinction.

Task 1.1 is the sole Accepted transition. Append only Implementing, then one Applied event containing exactly the five declared update operations in this transaction; apply the matching authored claim mutations and rendered outputs. Do not append Implemented: terminal ADR and plan closure remains deferred until implementation assurance settles.

### Phase close

State checks:

```bash
uv run --locked pytest \
  tests/e2e/test_formula_system_analysis.py \
  tests/unit/test_formula_scenarios.py \
  tests/unit/test_formula_queries.py \
  tests/unit/test_error_translation.py \
  tests/test_pi_schema_generation.py
npx vitest run \
  packages/pi-science/tests/adapter.test.ts \
  packages/pi-science/tests/bridge.test.ts \
  packages/pi-science/tests/start.test.ts \
  packages/pi-science/tests/provision.test.ts \
  packages/pi-science/tests/package.test.ts
uv run --locked pyright
npm run check:pi
./scripts/check
git diff --check
python - <<'PY'
import re
import subprocess
from pathlib import Path

tracked = subprocess.check_output(
    ["git", "ls-files", "packages/pi-science", "tests"], text=True
).splitlines()
pattern = re.compile(r"version\s*:\s*7|protocol[- ]?v7|PROTOCOL_VERSION\s*=\s*7")
hits = []
for name in tracked:
    path = Path(name)
    if path.suffix not in {".py", ".ts"}:
        continue
    for number, line in enumerate(path.read_text().splitlines(), 1):
        if pattern.search(line):
            hits.append((name, number, line.strip()))
assert len(hits) == 1, hits
assert hits[0][0] == "packages/pi-science/tests/adapter.test.ts", hits
assert re.search(r"version\s*:\s*7", hits[0][2]), hits
PY
```

Authority checks: run `./awf check` and inspect the ADR history, requiring its Applied partition to equal State changes with no Remaining or Canceled operations. State checks: inspect every Definition-of-done outcome against the complete result, confirm both live protocol constants are 8, and require the census above to terminate with exactly the sole incompatible-v7 fixture. Choreography check: stage the complete transaction before `./awf check staged`. Record test-first evidence, semantic rendered-prose review, protocol census, and any reasoned deviations in Notes.

```commit
feat(formula): add bounded affine domain constraints
```

## Definition of done

- `dod: bounded-constraint-contract` Public Python accepts bounded named targeted equation-local constraints only inside the approved integer-affine and conjunctive absolute family, rejects every excluded structure with precise field paths, preserves mandatory finite base domains and existing requests, and enforces all population, source, reasoning, rendering, and report bounds.
- `dod: exact-constrained-analysis` One acyclic effective-domain interpretation combines base and normalized constraint bounds with analyzer-owned `Min`/`Max`, distinguishes proved global contradiction from unresolved compatibility and specialization emptiness, and drives exact cardinality, operation work, opaque costs, primitive invocations, fixed scenarios, and finite-choice scenarios.
- `dod: isolated-constraint-reasoning` Submitted constraints, effective domains, global assumptions, and equation-qualified constraint uses remain separately inspectable; constraints govern both sides and targeted queries of only their owning equation, with no cross-equation or top-level leakage.
- `dod: strict-cross-layer-delivery` Protocol v8, generated schema, real adapter, strict bridge, provisioning, registered tool, response bounds, and installed package transport the complete contract while all mathematical policy remains Python-owned.
- `dod: synchronized-constraint-guidance` The ADR's five Applied claim updates, rendered current state, analysis and architecture docs, testing guidance, Python README, packaged skill, Pi routing text, and roadmap describe the same partial supported family and complete deferred inventory; the full gate passes.

## Notes

Inline owners immediately correct stale instructions and record reasoned deviations here. Delegated owners may report rather than edit; the parent supplies the report to phase review and reconciles it with findings in one focused post-review settlement commit before checkpointing or later execution. Record deviations, test-first evidence, protocol census, semantic generated-prose review, follow-ups, and findings surfaced during implementation.

- Plan-review disposition: fixed lifecycle ownership so Task 1.1 alone accepts the ADR and Task 1.5 appends only Implementing and Applied; added the backend rendering and authored architecture/testing sources; made focused/full commands, protocol census, and authority/state/choreography checks executable.
- Plan-review reasoned disposition: fixed the public shape inside the approved transparency boundary with `DomainConstraint`, `EffectiveIndexDomain`, `ConstraintUse`, and `EquationEffectiveDomains`; non-null equation, query, fixed-scenario, and choice-scenario fields preserve submitted/effective/provenance separation under explicit bounds without adding a new durable semantic choice.
- Implementation evidence: baseline focused Python suite passed 147 tests and focused Pi suite passed 90 tests before mutation. The added constrained-domain regression initially red because the public model had no constraint shape; after implementation it passes and the focused Python suite passes 148 tests.
- Protocol census: live Python adapter and TypeScript bridge constants are 8; the confined census found exactly one stale v7 spelling, the intentional incompatible-envelope fixture in `packages/pi-science/tests/adapter.test.ts`.
- Generated-prose meaning review: inspected the rendered product input, analysis-model, and report-contract topic boundaries plus architecture/testing output; each preserves the partial-family, Python-policy, submitted/effective/provenance distinctions and no contradictory broader solver claim was found.
- Deviations: none.
- Post-review settlement: added bounded uniform-empty compatibility rejection, analyzer-owned integral `Min`/`Max` cardinality and specialized-empty zero work, equation-targeted consumed-local-constraint provenance, strict bridge report/scenario correlation and source-population validation, and a precise duplicate-constraint-name field diagnostic. Focused acceptance/refusal regressions cover equality, strict inequalities, negative target coefficient, reversed and strict `Abs` upper forms, and the excluded non-unit, chained/disjunctive, absolute lower/equality, product, power, division families. The query current-state claim now states consumed local facts rather than implying every selected constraint is used. Authority: approved ADR decisions 2-6. Verification: focused matrix and diagnostic tests, then full gate.
- Renewed-review settlement: corrected inclusive global-emptiness proof, counts every constraint source field in the direct-Python request budget, supplies isolated equation-local scalar reasoning to targeted queries and reports only actually consumed constraints, and correlates strict bridge system, scenario, and query populations with submitted request objects. Added singleton/nonempty, request-budget, outcome-changing query-isolation, and forged bridge regressions. Authority: approved ADR decisions 3-6. Verification: focused suites, then full gate.
- Verify-pass residual settlement: targeted query reasoning now consumes normalized effective bounds while retaining submitted local provenance, keeps local uses out of global-assumption provenance, and bridge correlation accepts LHS order while requiring exact unique domain populations and per-answer local-use uniqueness. Added absolute-bound, provenance separation, reversed-key, and repeated-property-use regressions. Authority: approved ADR decisions 3, 5, and 6. Verification: focused suites, then full gate; no further review loop under the review protocol.
