---
format: plan-v2
date: 2026-08-19
adrs:
  - adopt-bounded-aggregate-work-dominance-analysis
status: Proposed
---
# Plan: Deliver bounded aggregate-work dominance analysis

## Goal

Ship matching Python and Pi support for bounded one-axis dominance analysis over one computation's original reuse-aware aggregate abstract work. Return canonical signed terms, compact exact magnitude-dominance regions, ties, poles, qualifications, and abstention without changing ordinary analysis or candidate-comparison bytes and without adding multivariate ordering, exponentials, opaque aggregate reasoning, rewrites, resource models, or runtime claims.

## Architecture summary

Keep ordinary analysis and candidate comparison unchanged. First extract the existing bounded rational sign chart into a typed internal seam whose caller supplies the axis and whose structural result retains roots, poles, interval signs, admissible point signs, and unresolved facts; existing property queries render their identical public evidence from that seam, and candidate comparison continues to consume bounded sign conclusions without parsing display strings.

Add a separate `DominanceAnalysisRequest` and `analyze_dominance` Python entry point. The request contains `operation: "analyze_dominance"`, `syntax`, exactly one existing expression or nonempty equation system, one declared scaling variable, optional exact fixed substitutions for other declared scalar variables, an optional exact open or closed range, and the existing shared variables, functions, primitive costs, assumptions, and directed definitions. It intentionally omits scenarios, general queries, candidates, and output mappings. The result retains the ordinary analysis and consumes only the private retained original-graph `WorkAnalysis.total_work` plus its unknown, unresolved, and direct-work qualifications.

Python applies checked definitions, assumptions, and exact substitutions, then measures and reduces one bounded univariate rational form. It preserves original denominator exclusions, collects the reduced numerator into stable nonzero power terms over one shared denominator, orders terms by descending power, and verifies exact reconstruction before publishing. Each term id is exactly `power:<p>`, where `<p>` is the canonical unsigned decimal numerator power with no leading zero except `0` (for example `power:2`, `power:1`, `power:0`); Python generates this grammar and TypeScript validates correlation against the reported power. The coefficient and signed expression are bounded canonical renderings, and relevance is determined by absolute magnitude rather than signed value. Non-axis symbols may remain only where bounded reasoning proves every needed coefficient relation and produces axis-only exact boundaries; otherwise the result abstains.

Python admits at most 16 terms and therefore at most 120 pairwise squared-magnitude differences. After exact deduplication it admits at most 256 structural partition points total, counting crossover roots, denominator poles, and finite active-domain endpoints, and at most 513 real or integer result cells before coalescing. Dominance reasoning reuses the existing 4,096-step and 4,096-intermediate-node ceilings. Dominance-owned rendered strings and the serialized dominance supplement excluding the nested ordinary analysis each have a 65,536-byte ceiling; the complete serialized result retains the existing 262,144-byte ceiling. A term, pair, partition, cell, reasoning, node, dominance-rendering, or supplemental overflow returns a request-wide qualified `unresolved` dominance result with null decomposition, empty cells, and a specific blocker; a combined-result overflow returns the existing complexity `AnalysisFailure`, because no conforming success can fit. A near-ceiling nested ordinary analysis is never truncated and must either leave room for the bounded supplement or take that combined-result failure.

Within those ceilings, Python uses the typed sign-chart seam to collect exact crossover roots, denominator poles, and active-domain boundaries. It partitions only within the declared-domain/requested-range intersection, proves the complete tied maximum set for each cell, and coalesces adjacent cells with the same result. Real axes report exact open or closed intervals and admissible points. Integer axes report compact inclusive integer ranges and admissible integer points, omitting noninteger roots. A valid proved-empty intersection returns `empty`; unsupported cells are localized `unresolved` cells, never sampled or guessed rankings. Identically zero work over a nonempty active domain returns `complete` with the active domain retained, an empty term list, no dominance cells, and an explicit zero-work qualification.

The private Pi protocol advances from v9 to v10 and carries an explicit ordinary-analysis, candidate-comparison, or dominance request/result union. The generated provider schema adds the syntax-injected dominance branch. The adapter dispatches on the exact operation, and TypeScript validates shape, bounds, ordering, domain-kind population, and request/result correlation without recomputing decomposition, roots, magnitude comparisons, or dominance. The existing readiness-gated `analyze_formula` tool presents axis and decomposition status before compact regions, exclusions, qualifications, and blockers; canonical complete evidence remains in `details`.

## Phase 1: Extract typed explicit-axis sign charts

**Execution mode: subagent-driven.**

Advances: ["exact-dominance-regions"]
Completes: ["typed-sign-chart-seam"]

### Task 1.1: Characterize and extract the structural sign-chart boundary
Kind: batch
Applying: ["adopt-bounded-aggregate-work-dominance-analysis:exact-domain-aware-dominance-regions", "adopt-bounded-aggregate-work-dominance-analysis:qualified-bounded-dominance-transport"]
Paths: ["docs/decisions/adopt-bounded-aggregate-work-dominance-analysis.md", "docs/decisions/INDEX.md", ".awf/awf.lock", "packages/py-science-formula/src/py_science/formula/properties.py", "packages/py-science-formula/src/py_science/formula/sign_chart.py", "packages/py-science-formula/src/py_science/formula/sympy_backend.py", "packages/py-science-formula/src/py_science/formula/reasoning.py", "packages/py-science-formula/src/py_science/formula/exact_values.py", "packages/py-science-formula/src/py_science/formula/comparison.py", "tests/unit/test_formula_properties.py", "tests/e2e/test_formula_candidate_comparison.py", "tests/unit/test_error_translation.py"]
Representative: An explicit-real-axis structural chart for `(x + 1) / (x - 1)` retains the zero at `-1`, pole at `1`, exact interval signs, point sign at the admissible zero, and consumed assumption provenance, while the existing property query renders byte-identical evidence and candidate-comparison winner/crossover fixtures remain unchanged.
Edge: Cover repeated numerator and denominator roots, canceled but still obligated original denominators, finite domain endpoints, signed infinity, integer witnesses, roots outside the active domain, noninteger roots on integer axes, unsupported factors, ambiguous implicit property axes, resource refusal, and unexpected backend failure. The structural seam accepts checked expression IR and an explicit declared axis; it never parses rendered evidence or turns unrestricted backend roots into public proof.
Post-check: Before mutation, record model dumps for the existing rational sign, singularity, assumption-qualified sign, candidate fixed-winner, and candidate crossover fixtures. Add structural tests and observe failures caused by the absent typed seam, then extract the smallest cohesive policy boundary. Run `tests/unit/test_formula_properties.py`, `tests/e2e/test_formula_candidate_comparison.py`, and `tests/unit/test_error_translation.py`; require the recorded public model dumps to remain byte-for-byte equal, the new structural population to match the representative and edge matrix, and `git diff --check` to exit 0.

Transition ADR-adopt-bounded-aggregate-work-dominance-analysis from Proposed to Accepted through the ADR lifecycle workflow before production mutation, without applying any State change. Define immutable internal chart models for axis, exact boundary, pole, interval classification, point classification, provenance, and localized refusal. Move bounded factor/root/witness policy behind one explicit-axis function, then adapt ordinary property rendering and candidate work-sign consumption to it without changing public results. Backend helpers remain checked algebra providers; project-owned code continues to decide admissibility, domains, evidence, and bounds.

### Phase close

Run:

```bash
uv run --locked pytest \
  tests/unit/test_formula_properties.py \
  tests/e2e/test_formula_candidate_comparison.py \
  tests/unit/test_error_translation.py
uv run --locked pyright
uv run --locked ruff check .
./awf check
./awf check staged
./scripts/check
git diff --check
```

Authority check: the ADR is Accepted with no Applied operations. State check: ordinary property and candidate-comparison public dumps are unchanged, and the new internal seam exposes typed roots, poles, intervals, points, provenance, and refusals for one explicit axis.

```commit
refactor(formula): expose structural sign charts
```

## Phase 2: Ship the direct Python dominance contract

**Execution mode: subagent-driven.**

Advances: ["strict-pi-dominance", "synchronized-dominance-guidance"]
Completes: ["dominance-request-contract", "exact-dominance-regions", "qualified-dominance-report"]

### Task 2.1: Define the strict public request and result through failing tests
Kind: batch
Applying: ["adopt-bounded-aggregate-work-dominance-analysis:single-axis-original-work-dominance", "adopt-bounded-aggregate-work-dominance-analysis:canonical-rational-power-terms", "adopt-bounded-aggregate-work-dominance-analysis:exact-domain-aware-dominance-regions", "adopt-bounded-aggregate-work-dominance-analysis:qualified-bounded-dominance-transport"]
Paths: ["packages/py-science-formula/src/py_science/formula/models.py", "tests/e2e/test_formula_dominance.py", "tests/unit/test_error_translation.py"]
Representative: A positive-integer-axis request whose retained primitive work is `N**2 - N + 1` reports canonical terms `N**2`, `-N`, and `1`; point `N = 1` ties all three magnitudes, and inclusive integer range `N >= 2` has only `N**2` dominant.
Edge: Reject a missing, undeclared, reserved, nonnumeric, or fixed axis; expression/equation dual population; scenarios, queries, candidates, outputs, or surplus keys; foreign or axis fixed substitutions; unsafe integers; invalid exact scalars; conflicting definitions; malformed, reversed, or noncanonical range endpoints; and over-bound names or populations. Characterize strict frozen result truth tables for `complete`, `unresolved`, and `empty`, real and integer cell variants, finite and infinite bounds, nonempty tied sets, excluded poles, exact `power:<p>` term identity/order, nullable decomposition, blockers, provenance, never-dominant terms, and the approved identically-zero `complete` exception.
Post-check: Add model and service-facing tests first and record two failure sets: absent public types/imports, then accepted model shapes reaching the absent service. After implementing only the models, require remaining failures to name the absent dominance service rather than malformed fixtures. Run the dominance and error-translation suites and require localized paths under the computation, `axis`, `fixed`, and `range` fields. Require a focused zero-work regression to retain the nonempty active domain with empty terms and cells plus the explicit qualification.

Add strict frozen models for `DominanceAnalysisRequest`, canonical fixed values and range, `DominanceTerm`, domain-aware real and integer cells, excluded points, structural evidence, and `DominanceAnalysisSuccess | AnalysisFailure`. Success has required `kind: "dominance_analysis"`, `status: "success"`, ordinary analysis, metric `aggregate_abstract_work`, correlated axis/fixed/requested and effective range, nullable shared denominator, bounded ordered terms and cells, exclusions, proved-never-dominant ids, conditions, assumptions, blockers, and `dominance_status` exactly `complete`, `unresolved`, or `empty`. Term models encode the canonical nonnegative integer power explicitly and require id `power:<p>` with the same canonical decimal power.

`complete` requires either a nonempty verified decomposition with no unresolved cells or blockers and exact coverage of the nonexcluded active domain, or the identically-zero exception: a nonempty active domain, empty terms and cells, no blockers, and the explicit zero-work qualification. In the decomposed case, never-dominant ids equal the proved complement of all dominant sets; in the zero-work case they are empty. `unresolved` requires blockers or at least one unresolved cell; it may retain proved complete cells and may name only terms proved never dominant across the entire active domain. An unresolved result before decomposition has null denominator plus empty terms and cells. `empty` requires a proved-empty active domain, no cells or exclusions, no blockers, and no never-dominant claim; it may retain a verified decomposition. Every complete cell has a nonempty ordered unique dominant-id tuple and no blockers; every unresolved cell has an empty dominant tuple and nonempty blockers. Real cells use intervals or points with exact finite or infinite boundaries and inclusivity; integer cells use inclusive ranges or points with integer or infinite boundaries. All ids and populations are exactly correlated and bounded.

### Task 2.2: Implement canonical decomposition and domain-aware dominance regions
Kind: batch
Applying: ["adopt-bounded-aggregate-work-dominance-analysis:single-axis-original-work-dominance", "adopt-bounded-aggregate-work-dominance-analysis:canonical-rational-power-terms", "adopt-bounded-aggregate-work-dominance-analysis:exact-domain-aware-dominance-regions", "adopt-bounded-aggregate-work-dominance-analysis:qualified-bounded-dominance-transport"]
Paths: ["packages/py-science-formula/src/py_science/formula/dominance.py", "packages/py-science-formula/src/py_science/formula/service.py", "packages/py-science-formula/src/py_science/formula/models.py", "packages/py-science-formula/src/py_science/formula/sign_chart.py", "packages/py-science-formula/src/py_science/formula/sympy_backend.py", "packages/py-science-formula/src/py_science/formula/reasoning.py", "packages/py-science-formula/src/py_science/formula/work.py", "tests/e2e/test_formula_dominance.py", "tests/e2e/test_formula_analysis.py", "tests/e2e/test_formula_system_analysis.py", "tests/e2e/test_formula_candidate_comparison.py", "tests/unit/test_formula_properties.py"]
Representative: Equivalent retained work spellings `(N + 1)**2` and `N**2 + 2*N + 1` yield the same descending-power ids, coefficients, signed expressions, denominator, exclusions, and cells. A reduced `(N**2 - 1)/(N - 1)` decomposition retains the original exclusion at `N = 1` even though its shared reduced denominator is `1`.
Edge: Cover negative lower-order corrections, zero coefficients, identically zero aggregate work, equal-magnitude opposite signs, all-term ties, rational poles, canceled denominator obligations, open and closed endpoints, positive/nonnegative/full integer and real domains, noninteger roots on integer axes, exact fixed substitutions, proved coefficient signs, parameter-dependent boundaries, opaque `Sum`/`Max`, exponentials, unknown primitive costs, nonfinite work, retained unresolved work, unsupported coefficients, reconstruction mismatch, unexpected backend failure, the 16-term/120-pair ceilings, 256-partition-point/513-cell ceilings, existing 4,096-step/4,096-node ceilings, 65,536-byte dominance-rendering and supplemental ceilings, and a near-262,144-byte ordinary analysis nested under the combined-result ceiling.
Post-check: Run the dominance suite in focused groups for request binding, decomposition, real regions, integer regions, qualification, and resource ceilings. Require independent ordinary `analyze` results to equal the nested analysis; require original retained `WorkAnalysis.total_work` and system reuse metadata to remain unchanged; require property and candidate-comparison regressions to remain byte-stable; require a reversible falsification of reconstruction equality and one pairwise sign to fail the intended focused tests before restoration.

Implement `analyze_dominance` by invoking `_analyze_computation` once and consuming only immutable retained aggregate work. Validate fixed substitutions and the axis/range intersection against declared domains before algebra. Gate unknown costs, direct-work blockers, and retained unresolved work explicitly. Preserve original denominator obligations, use bounded backend rational reduction and coefficient collection, omit zero coefficients, order by descending power, assign stable power-derived ids, render through existing work budgets, and independently reconstruct the reduced expression before publishing.

Compare magnitudes with checked pairwise squared differences through the Phase-1 structural sign chart. Combine exact boundaries once, classify every active cell against every term, coalesce equal adjacent classifications, translate continuous cells to the admissible integer lattice where required, and keep poles excluded. A cell is complete only when the entire maximal tied set is proved; any missing comparison makes that cell unresolved. Enforce term, pair, root, cell, reasoning, rendering, supplemental-byte, and combined-result ceilings before or during bounded construction, returning qualified unresolved output rather than sampled evidence or a request-wide crash.

### Task 2.3: Export, document, and apply direct Python dominance
Kind: batch
Applying: ["adopt-bounded-aggregate-work-dominance-analysis:single-axis-original-work-dominance", "adopt-bounded-aggregate-work-dominance-analysis:canonical-rational-power-terms", "adopt-bounded-aggregate-work-dominance-analysis:exact-domain-aware-dominance-regions", "adopt-bounded-aggregate-work-dominance-analysis:qualified-bounded-dominance-transport"]
Paths: ["packages/py-science-formula/src/py_science/formula/__init__.py", "packages/py-science-formula/README.md", "docs/decisions/adopt-bounded-aggregate-work-dominance-analysis.md", "docs/decisions/INDEX.md", ".awf/topics/parts/product/product-boundary/current-state.md", ".awf/topics/parts/product/mathematical-input-contract/current-state.md", ".awf/topics/parts/product/mathematical-analysis-model/current-state.md", ".awf/topics/parts/product/analysis-report-contract/current-state.md", "docs/topics/product/product-boundary.md", "docs/topics/product/mathematical-input-contract.md", "docs/topics/product/mathematical-analysis-model.md", "docs/topics/product/analysis-report-contract.md", "docs/topics/product/index.md", "docs/analysis-model.md", ".awf/docs/parts/architecture/data-flow.md", ".awf/docs/parts/testing/tiers.md", ".awf/docs/parts/testing/layout.md", ".awf/docs/glossary.yaml", "docs/architecture.md", "docs/testing.md", "docs/glossary.md", ".awf/awf.lock", "tests/distribution/test_python_package.py"]
Representative: The Python package guide executes one integer correction example and one rational-pole example, explains stable term ids and absolute-magnitude ordering, and reads every result as abstract work rather than runtime.
Edge: State that dominance is a separate direct-Python operation over original submitted-graph work; it does not analyze mathematical-value terms, compare candidates, run scenarios or queries, support several axes, solve exponentials/opaque aggregates, suggest rewrites, or imply speed, memory, scheduling, optimality, or global relevance outside the active domain.
Post-check: Export every public request/result model and `analyze_dominance`; execute both documentation examples through installed public imports. Correct the glossary definition of dominant term to describe absolute-magnitude relevance within an active domain without scenarios or growth control. Run `./awf render`, read every authored and generated document in Paths, and require `./awf check`, `./awf check staged`, distribution tests, the dominance suite, and `git diff --check` to pass. Verify ordinary `AnalysisRequest`, `CandidateComparisonRequest`, `AnalysisSuccess`, and `CandidateComparisonSuccess` model dumps remain unchanged.

Transition the ADR from Accepted to Implementing and append one Applied event containing exactly all four declared State changes with matching authored claim mutations. The product-boundary, analysis-model, and report-contract claims stay transport-neutral. The new input-contract claim describes direct Python support only until Phase 3. Do not append Implemented.

### Phase close

Run:

```bash
uv run --locked pytest \
  tests/e2e/test_formula_dominance.py \
  tests/e2e/test_formula_analysis.py \
  tests/e2e/test_formula_system_analysis.py \
  tests/e2e/test_formula_candidate_comparison.py \
  tests/unit/test_formula_properties.py \
  tests/unit/test_error_translation.py \
  tests/distribution/test_python_package.py
uv run --locked pyright
uv run --locked ruff check .
./awf check
./awf check staged
./scripts/check
git diff --check
```

Authority check: the ADR is Implementing and its Applied partition exactly equals all four State changes. State check: public examples execute, nested ordinary analysis equals independent analysis, existing ordinary/candidate model dumps remain stable, and current-state prose describes direct Python dominance while Pi transport remains pending. Record test-first failures, falsification evidence, result-budget probes, generated-prose review, and reasoned deviations in Notes.

```commit
feat(formula): analyze aggregate-work dominance
```

## Phase 3: Transport dominance through Pi

**Execution mode: subagent-driven.**

Completes: ["strict-pi-dominance", "synchronized-dominance-guidance"]

### Task 3.1: Advance schema, adapter, and strict bridge to protocol v10
Kind: batch
Applying: ["adopt-bounded-aggregate-work-dominance-analysis:single-axis-original-work-dominance", "adopt-bounded-aggregate-work-dominance-analysis:exact-domain-aware-dominance-regions", "adopt-bounded-aggregate-work-dominance-analysis:qualified-bounded-dominance-transport"]
Paths: ["scripts/generate-pi-formula-schema.py", "packages/pi-science/src/formula-schema.json", "packages/pi-science/bridge/formula_adapter.py", "packages/pi-science/src/bridge.ts", "packages/pi-science/src/provision.ts", "tests/test_pi_schema_generation.py", "packages/pi-science/tests/adapter.test.ts", "packages/pi-science/tests/bridge.test.ts", "packages/pi-science/tests/provision.test.ts", "packages/pi-science/tests/start.test.ts", "packages/pi-science/tests/afmm-fixture.ts"]
Representative: The real protocol-v10 adapter and strict bridge round-trip the integer correction fixture with canonical terms, the point tie at `1`, the coalesced integer range from `2`, nested ordinary analysis, conditions, and exact request/result axis correlation.
Edge: Preserve every protocol-v9 ordinary-analysis and candidate-comparison branch and result byte apart from the envelope version. Reject missing, surplus, over-bound, version-mismatched, miscorrelated, out-of-order, overlapping, noncoalesced, wrong-domain-kind, invalid infinity, invalid status/population, fabricated term id, pole-covered, or evidence/blocker-inconsistent results. Accept dominance `AnalysisFailure` responses. TypeScript validates transport truth tables and correlation only; it never recomputes rational reduction, reconstruction, squared differences, roots, integer projection, or dominant sets.
Post-check: Regenerate the schema and run schema, adapter, bridge, provisioning, and registered-tool suites. Require fresh temporary generation to match the committed artifact, real-adapter dominance success and failure round trips, mutation-based strict result rejection, unchanged ordinary/candidate payload fixtures, and `git diff --check`. Run a confined protocol census whose only v9 occurrence is the intentional incompatible-envelope fixture.

Teach the generator to preserve the ordinary expression/system and candidate branches and add one provider-compatible dominance expression/system union with injected `syntax` omitted. Advance live Python and TypeScript protocol constants to 10. Dispatch the adapter and bridge on exact operation values rather than presence of `operation`; preserve explicit required nulls. Add exact TypeScript request/result unions, formula-source accounting, bounds, status truth tables, cell ordering/population checks, and request/result correlation without importing mathematical policy.

### Task 3.2: Expose dominance in the existing tool and synchronize guidance
Kind: batch
Applying: ["adopt-bounded-aggregate-work-dominance-analysis:single-axis-original-work-dominance", "adopt-bounded-aggregate-work-dominance-analysis:canonical-rational-power-terms", "adopt-bounded-aggregate-work-dominance-analysis:exact-domain-aware-dominance-regions", "adopt-bounded-aggregate-work-dominance-analysis:qualified-bounded-dominance-transport"]
Paths: ["packages/pi-science/src/index.ts", "packages/pi-science/skills/formula-analysis/SKILL.md", "packages/pi-science/tests/start.test.ts", "packages/pi-science/tests/package.test.ts", "README.md", ".awf/parts/agents-doc/identity.md", "AGENTS.md", ".awf/docs/parts/architecture/overview.md", ".awf/docs/parts/architecture/data-flow.md", ".awf/docs/parts/testing/tiers.md", ".awf/docs/parts/testing/layout.md", "docs/architecture.md", "docs/vision.md", "docs/analysis-model.md", "docs/testing.md", "packages/py-science-formula/README.md", "docs/decisions/adopt-bounded-aggregate-work-dominance-analysis.md", "docs/decisions/INDEX.md", ".awf/topics/parts/product/product-boundary/current-state.md", ".awf/topics/parts/product/mathematical-input-contract/current-state.md", ".awf/topics/parts/product/mathematical-analysis-model/current-state.md", ".awf/topics/parts/product/analysis-report-contract/current-state.md", "docs/topics/product/product-boundary.md", "docs/topics/product/mathematical-input-contract.md", "docs/topics/product/mathematical-analysis-model.md", "docs/topics/product/analysis-report-contract.md", "docs/topics/product/index.md", ".awf/awf.lock"]
Representative: `analyze_formula` accepts dominance without caller-supplied syntax; compact text lists axis, effective domain, status, canonical signed terms, dominant regions/ties, excluded poles, never-dominant terms, qualifications, and blockers in that order, while `details` retains the complete canonical report.
Edge: Keep one readiness-gated tool and one product skill; preserve ordinary-analysis and candidate-comparison compact text plus health behavior. Guidance must distinguish signed terms from negative work, absolute-magnitude dominance from runtime importance, active-domain relevance from global optimality, and complete cells from unresolved cells. It must name multiple axes, exponentials, opaque sums/Max, rewrites, resource vectors, scheduling, and empirical performance as excluded.
Post-check: Run `./awf render`; read the generated identity, architecture, analysis model, vision, testing guide, package guides, skill, tool description, current-state topics, and representative compact text. Require no stale claim that dominance is direct-Python-only or remains roadmap work. Run focused Pi suites, `./awf check`, `./awf check staged`, the full gate, the protocol census, and `git diff --check`.

Extend the existing `analyze_formula` union and inject syntax for dominance. Compact output is a projection only and never hides canonical details. Update authored guidance and generated outputs from direct-Python delivery to matching Python and Pi support without broadening the mathematical family.

Pair-atomically Reapply `add product/mathematical-input-contract:bounded-dominance-analysis-requests` when its Phase-2 direct-Python wording widens to Python and Pi. Reinspect the transport-neutral product-boundary, analysis-model, and report-contract claims byte-for-byte and classify those three operations as unchanged, with no Reapplied event. If the expected Phase-2 claim snapshot is absent or any supposedly transport-neutral claim would need mutation, stop and replan rather than conditionally changing the declared batch. The ADR remains Implementing; do not append Implemented.

### Phase close

Run:

```bash
uv run --locked pytest tests/test_pi_schema_generation.py
npx vitest run \
  packages/pi-science/tests/adapter.test.ts \
  packages/pi-science/tests/bridge.test.ts \
  packages/pi-science/tests/provision.test.ts \
  packages/pi-science/tests/start.test.ts \
  packages/pi-science/tests/package.test.ts
uv run --locked pyright
npm run check:pi
./awf check
./awf check staged
./scripts/check
git diff --check
python - <<'PY'
import re
import subprocess
from pathlib import Path

tracked = subprocess.check_output(
    ["git", "ls-files", "packages/pi-science", "tests"], text=True
).splitlines()
pattern = re.compile(r"version\s*:\s*9|protocol[- ]?v9|PROTOCOL_VERSION\s*=\s*9")
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
assert re.search(r"version\s*:\s*9", hits[0][2]), hits
PY
```

Authority check: the ADR remains Implementing with all four operations Applied and every materially widened claim carrying one matching Reapplied event. State check: live protocol constants are 10, the census leaves only the deliberate stale-v9 request, ordinary and candidate round trips are unchanged, and dominance round trips preserve exact axis/cell correlation plus decomposition-before-region presentation. Record protocol census, schema/prose meaning review, compact-output inspection, and deviations in Notes.

```commit
feat(pi): expose dominance analysis
```

## Definition of done

- `dod: typed-sign-chart-seam` Python exposes one bounded internal explicit-axis structural sign chart with typed roots, poles, intervals, points, provenance, and refusals, while ordinary property and candidate-comparison public results remain unchanged.
- `dod: dominance-request-contract` Direct Python accepts one strict dominance request over exactly one supported computation, one declared scaling variable, optional exact non-axis substitutions, and an optional exact range, preserving ordinary and candidate contracts and localizing invalid shapes.
- `dod: exact-dominance-regions` Python consumes only original retained aggregate work, publishes a reconstruction-verified reduced-rational power-term decomposition, compares absolute magnitudes, and returns compact exact real intervals or integer ranges with ties, poles, never-dominant terms, empty domains, and localized unresolved cells under strict bounds.
- `dod: qualified-dominance-report` Complete, unresolved, and empty truth tables preserve signed terms, active-domain scope, conditions, provenance, exclusions, unknown or unsupported work, and explicit abstention without runtime, resource, rewrite, multivariate, or global-optimality claims.
- `dod: strict-pi-dominance` Protocol v10, generated provider schema, bounded adapter, exact TypeScript bridge, readiness-gated `analyze_formula`, compact projection, and canonical details transport and correlate dominance while retaining ordinary and candidate behavior.
- `dod: synchronized-dominance-guidance` Applied ADR claims, rendered current state, architecture, analysis model, vision, package guides, agent identity, product skill, and tests consistently describe the shipped bounded dominance family and its exclusions; the full gate passes.

## Notes

Record baseline and test-first evidence, structural-seam compatibility dumps, reconstruction/sign falsification, budget probes, protocol census, generated-prose meaning review, compact-output inspection, follow-ups, and findings surfaced during implementation.

Plan-review dispositions before the initial commit:
- Restored approved D7 zero-work semantics throughout the architecture, Task 2.1 truth table, and Task 2.2 coverage: a nonempty active domain with identically zero work is `complete` with empty terms/cells and an explicit qualification.
- Fixed the delegated stable public term-id detail as `power:<p>` with canonical unsigned-decimal power and required Python/TypeScript correlation, removing cross-language fixture ambiguity.
- Fixed deterministic dominance ceilings and overflow outcomes: 16 terms, 120 pairs, 256 partition points, 513 cells, existing 4,096 reasoning steps and intermediate nodes, 65,536 dominance-rendering and supplemental bytes, and the existing 262,144 combined-result bytes.

Phase 2 recovery follow-up at `3e8acf7`:
- Reproduced the predecessor's primitive-cost `N**2 - N + 1` failure before repair; squared pair differences now use the typed chart's non-real-root-safe path, retain structural pair evidence with a populated sign, and the focused integer correction test exercises the reversible pair-sign assertion.
- Recovered original retained denominator obligations before cancellation, including the reduced `(N**2 - 1)/(N - 1)` exclusion at `N = 1`; poles are partition cuts rather than cells, and integer regions use symbolic infinities rather than finite sentinels.
- Added direct-Python regressions for canonical terms/ties, canceled poles, endpoint/lattice behavior, and nested ordinary-analysis equality. README examples now use primitive-cost-backed work, execute through public imports, and assert canonical terms/regions and poles.
- Focused recovery verification: 173 required Python tests passed; Pyright, Ruff, AWF checks, diff check, and installed README examples passed. Existing property/candidate suites were included in the green run. ADR remained Implementing with its existing four Applied operations; direct-Python wording and Pi-pending state remain unchanged.
- Reversible reconstruction falsification was retained as the independent reconstruction guard in `dominance.py`; pair-sign falsification is covered by the populated-sign assertion. No generated prose was changed.
- A second owner stopped clean at `66add88` after repairing rational pair charts, denominator exclusions, pole partitioning, symbolic integer infinities, and primitive-cost examples, but correctly reported that model truth tables, specialization/provenance, localized cells, remaining ceilings, falsification, and broad coverage were still incomplete.
- Parent completion after `66add88` made the axis domain explicit in results; strengthened fixed-value/domain/definition request validation; enforced canonical cell kinds, ordering, disjointness, exclusions, complete coverage, evidence pairs, never-dominant complements, and complete/unresolved/empty populations; specialized fixed values before algebra; retained supported axis-assumption provenance; and localized an unsupported pair comparison into blocker-bearing cells instead of discarding the decomposition.
- Bounded SymPy dominance helpers now own specialization, rational collection, node counting, reconstruction, pair differences, rendering expressions, and exact magnitude evaluation. Policy enforces pair bounds before construction, 4,096-step/node limits during reasoning, exact rendering and supplement sizes, pre-coalescing cell counts, and the existing combined-result limit. Integer exclusions are lattice-admissible only, real/integer cells preserve exact endpoints without sentinels, and adjacent equal classifications coalesce.
- Focused recovery tests now cover equivalent spellings, zero versus empty, fixed specialization and provenance, invalid requests, unsupported and nonfinite work, strict result truth tables, all eight supplemental ceilings, combined-result failure, localized pair refusal, unexpected backend failure, exact endpoint/lattice behavior, retained canceled poles, independent nested ordinary analysis, and reversible reconstruction/pair-sign falsification.
Phase 1 review settlement:
- The owner landed ADR acceptance at `4870207` and the phase refactor at `56b1cde`, with focused and full gates green, but reported that baseline public dumps and the full edge matrix were omitted. Phase review confirmed the deviation was material: fractional integer-domain witness rounding changed ordinary sign bytes, unsupported canceled denominators were silently discarded, the explicit axis kind was not authoritative, and file-wide lint/type suppressions weakened the new boundary.
- Restored exact ceil/floor witness arithmetic under the approved byte-stability boundary and froze ordinary fractional-integer sign answers plus candidate fixed-winner/crossover work reports as exact JSON regressions. Post-hoc baselines were recovered from `cb8decb` before writing those tests.
- Original denominators are now checked exactly once and unsupported roots produce a typed refusal; the declared axis kind controls integer witnesses and points and is validated against reasoning facts. Added coverage for provenance, repeated roots/poles, canceled obligations, finite active bounds, unbounded sides, out-of-domain boundaries, integer and noninteger roots, ambiguous implicit axes, unsupported factors, resource refusal, and unexpected backend failure.
- Removed the added file-wide Ruff/Pyright suppressions, deleted superseded private witness/sign code, formatted the seam normally, and retained only one narrow SymPy-stub argument-type ignore. Focused tests, project-wide Pyright/Ruff, and the full gate pass after settlement.
- Renewed review found two residual mechanical gaps. Non-rational moving roots now return the caller-specific unsupported numerator or original-denominator refusal rather than falling through Fraction conversion to a backend-failure label, with parameter-dependent regressions. The recovered `cb8decb` exact bytes for the unqualified rational sign and singularity answers are also frozen alongside the other public baselines.

Phase 2 post-review settlement:
- Collected denominator obligations by walking checked retained `Expression` IR before SymPy evaluation, then specialized exact fixed values under the same node cap. Exact cancellation and identically-zero work now retain admissible original poles; zero-work complete reports retain their exclusions and conditions.
- Rejected axis-target definitions, validated fixed values against checked assumption facts/equalities before supplemental algebra, prioritized nonfinite direct-work qualification, and established declared/requested emptiness before assumption reasoning.
- Canonicalized omitted infinite range endpoints as outward-open, strengthened success correlation for axis/fixed/effective range/domain, and added focused regressions for cancellation, zero-work poles, axis definitions, fixed-assumption contradictions, mutation resistance, and range construction.
- Reasoned deviation: no broader solver or transport change was added; the bounded existing `ReasoningContext` and retained-IR/backend seams determine these behaviors. Focused dominance tests passed after the initial failures for canceled poles, axis definitions, and infinity defaults.
