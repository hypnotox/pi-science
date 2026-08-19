---
format: plan-v2
date: 2026-08-19
adrs:
  - adopt-bounded-candidate-comparison
status: Proposed
---
# Plan: Deliver bounded candidate comparison

## Goal

Ship a general-purpose Python and Pi operation that compares exactly two supported mathematical candidates, proves or qualifies mapped-output equivalence before work preference, and reports reuse-aware aggregate-work deltas, bounded winner or crossover evidence, and explicit abstention. Do not add resource vectors, memory or schedule costs, generated rewrites, parameter search, selectable machine-arithmetic semantics, scenario comparison, general query inlining, or expanded AFMM modeling.

## Architecture summary

Keep the existing analysis path behavior and public models intact. First refactor Python service orchestration to retain one private analyzed-computation bundle containing parsed operands, validated producers and dependency order, original `WorkAnalysis`, knowledge, and the rendered `AnalysisSuccess`; extract the existing bounded rational equivalence proof into one internal expression-to-expression seam used by ordinary equivalence queries and comparison. No rendered report string is reparsed into mathematical policy.

Add a separate `CandidateComparisonRequest` and `compare_candidates` Python entry point. The request has `operation: "compare_candidates"`, `syntax`, exactly two uniquely named candidate computations, at least one logical output mapping, and shared variables, function definitions, scalar primitive costs, assumptions, and directed definitions. Each candidate contains exactly one expression or one nonempty existing equation list. Each output mapping has a unique logical name and exactly two `{candidate, target}` entries, one for each candidate; a target is `{kind: "expression"}` or `{kind: "equation", name: ...}`. Comparison requests intentionally omit scenarios and general-context queries in this milestone; callers may analyze either computation separately for those operations.

For each mapped output, Python validates the target and mathematical interface. Expressions and arity-zero equations are scalar; indexed equations must have equal arity and proved-equal effective output domains after positional binder alignment. Python recursively expands only mapped-output producer references over the already validated acyclic graph, with capture-avoiding positional index substitution and a separate aggregate expansion-node bound. It never changes the original candidate graph or its work analysis. The shared bounded equivalence seam compares aligned expanded operands under global knowledge and proved common output-domain facts. Unsupported interface proof, expansion, equivalence, or resource limits produce a correlated unresolved or inapplicable output result.

The comparison result retains both ordinary candidate analysis reports and one structured result per mapped output. It derives overall semantic status from the weakest required output. Only when every output is proved equal or proved under assumptions may it derive work preference. Candidate work uses each retained original `WorkAnalysis.total_work`, not top-level submitted `abstract_work` and not expanded operands. Define the rendered delta as `second_candidate - first_candidate`; positive means the first candidate has lower modeled work, negative means the second does, and zero is equal. Reuse the bounded exact univariate rational sign-chart family for winner and crossover intervals, and otherwise return the rendered delta and unresolved condition. Non-finite direct work, unknown costs, unsupported multivariate ordering, or unresolved semantics never become a winner. Every result names the `aggregate_abstract_work` metric and retains the existing no-runtime qualification.

The private Pi protocol advances from v8 to v9 and carries an analysis-or-comparison request/result union through the existing adapter. Extend the single `analyze_formula` tool schema with the comparison variant, keep `syntax: sympy` injected by Pi, and preserve exact TypeScript shape, bound, and request/result correlation checks without moving mathematical policy out of Python. Compact output presents semantic status before work relation; canonical structured evidence remains in `details`.

## Phase 1: Retain internal mathematical analysis state

**Execution mode: subagent-driven.**

Advances: ["semantic-candidate-comparison"]

### Task 1.1: Establish authority and introduce the internal comparison seams
Kind: batch
Applying: ["adopt-bounded-candidate-comparison:bounded-general-candidate-comparison", "adopt-bounded-candidate-comparison:semantic-comparison-precedes-work-preference", "adopt-bounded-candidate-comparison:qualified-abstract-work-comparison"]
Paths: ["docs/decisions/adopt-bounded-candidate-comparison.md", "docs/decisions/INDEX.md", ".awf/awf.lock", "packages/py-science-formula/src/py_science/formula/service.py", "packages/py-science-formula/src/py_science/formula/query.py", "packages/py-science-formula/src/py_science/formula/equivalence.py", "packages/py-science-formula/src/py_science/formula/work.py", "tests/unit/test_formula_queries.py", "tests/e2e/test_formula_analysis.py", "tests/e2e/test_formula_system_analysis.py"]
Representative: Ordinary analysis returns the same `AnalysisSuccess`, while internal orchestration also retains the parsed expression or equations, producer map, dependency order, per-equation and combined `WorkAnalysis`, and knowledge needed by a later comparison consumer.
Edge: Preserve every existing public request/result byte, direct-work nullability rule, query conclusion, scenario result, normalized rendering, dependency/reuse edge, qualification, and error path. The new bundle is private, immutable, and consumed by existing analysis/query flow so it is not dead speculative structure.
Post-check: Run the three focused suites in `Paths`, compare representative pre-refactor and post-refactor model dumps for expression, system, equivalence, unknown primitive, and non-finite cases, and require `git diff --check` to exit 0.

Transition ADR-adopt-bounded-candidate-comparison from Proposed to Accepted through the ADR lifecycle workflow without applying any claim. Add or tighten characterization coverage only where needed to freeze ordinary expression, equation-system, query-equivalence, primitive-cost, unknown-cost, non-finite-work, dependency, and reuse results, and record the focused green baseline in Notes before production mutation.

Refactor `_analyze_single` and `_analyze_system` behind one internal analyzed-computation result without making the private bundle public or reparsing normalized renderings. Move the mathematical core of `query._equivalence` into `equivalence.py` as a bounded two-`Expression` comparison that accepts `ReasoningContext` and returns the existing qualified `QueryAnswer`; retain query-source parsing and diagnostic paths in `query.py`. Existing equivalence queries must delegate to the new seam with unchanged evidence and qualification.

### Phase close

Run:

```bash
uv run --locked pytest \
  tests/unit/test_formula_queries.py \
  tests/e2e/test_formula_analysis.py \
  tests/e2e/test_formula_system_analysis.py
uv run --locked pyright
uv run --locked ruff check .
./scripts/check
git diff --check
```

State check: ordinary public model dumps and error locations remain unchanged for the characterization population. Authority check: the ADR is Accepted with no Applied operations.

```commit
refactor(formula): retain internal analysis state
```

## Phase 2: Ship the direct Python comparison contract

**Execution mode: subagent-driven.**

Advances: ["strict-pi-comparison", "synchronized-comparison-guidance"]
Completes: ["candidate-comparison-contract", "semantic-candidate-comparison", "qualified-work-comparison"]

### Task 2.1: Define the bounded public contract through failing tests
Kind: batch
Applying: ["adopt-bounded-candidate-comparison:bounded-general-candidate-comparison", "adopt-bounded-candidate-comparison:semantic-comparison-precedes-work-preference", "adopt-bounded-candidate-comparison:qualified-abstract-work-comparison"]
Paths: ["packages/py-science-formula/src/py_science/formula/models.py", "tests/e2e/test_formula_candidate_comparison.py", "tests/unit/test_error_translation.py"]
Representative: Two candidates with different internal producer names map one indexed output, prove the same expanded value, retain distinct original reuse-aware work, and return a delta oriented as second minus first.
Edge: Cover duplicate or invalid candidate names, not-exactly-two candidates, missing or duplicate logical outputs, missing/duplicate/foreign mapping entries, expression targets on systems, equation targets on expressions, unknown equations, scalar/indexed mismatch, arity mismatch, unequal or unproved output domains, cycles through existing validation, aggregate source/node overflow, and forbidden surplus scenarios or queries.
Post-check: Run the new comparison and error-translation tests in two recorded steps. First add the tests and observe model-import or validation failures caused by the absent contract. Then implement only the request/result models and require the remaining terminal failures to come from the absent comparison service or behavior rather than malformed fixtures; record both failure sets in Notes before Tasks 2.2 and 2.3.

Add failing contract and outcome tests for the exact request and result shape in the Architecture summary, then implement the models only after preserving the initial failures. Bound candidate count to exactly two, output mappings to 32, names with the existing identifier/name limits, all submitted mathematical text under the existing aggregate request-byte and parser-node budgets, and semantic expansion under a separate aggregate 16,384-node ceiling. Keep the existing serialized result ceiling. Require strict frozen models and localized paths under `candidates[i]` and `outputs[i]`.

Define `CandidateComparisonOutcome` as `CandidateComparisonSuccess | AnalysisFailure`; failures retain the existing exact `status: "failure"` model. `CandidateComparisonSuccess` has required `kind: "candidate_comparison"`, `status: "success"`, exactly two ordered `CandidateAnalysisReport` entries, a nonempty output-comparison tuple, `semantic_status`, and `work_comparison`. Each candidate report has the submitted name, ordinary `AnalysisSuccess`, and `aggregate_work: str | null`; finite direct work requires aggregate work, while non-finite work requires null plus the candidate analysis blockers.

Each mapped-output result retains the submitted logical name and exactly two target references. `interface_status` is exactly `compatible`, `incompatible`, or `unresolved`; `expanded_interpretations` is either an ordered pair or null; and `answer` is one existing unchecked `QueryAnswer` with `check: null`, no derived candidates, and no constraint-use leakage. `incompatible` requires null expanded interpretations plus an `inapplicable` answer with nonempty blockers and null evidence. Interface `unresolved` requires null expanded interpretations plus an `unresolved` answer with nonempty blockers and null evidence. A compatible interface permits null expanded interpretations only when expansion itself is unresolved, with an unresolved blocker and null evidence. Successful expansion requires both interpretations and permits only `proved`, `proved_under_assumptions`, `disproved`, or `unresolved`: proved conclusions require identity evidence, disproved requires counterexample evidence, and unresolved requires nonempty blockers with null evidence.

Overall `semantic_status` is exactly `proved_equal`, `proved_equal_under_assumptions`, `disproved`, or `unresolved`. Any disproved mapped output wins precedence; otherwise any unresolved or inapplicable output produces unresolved; otherwise any assumption-qualified equality produces proved-equal-under-assumptions; otherwise all outputs are proved equal.

`CandidateWorkComparison` always names metric `aggregate_abstract_work`, repeats the two candidate names and nullable rendered works in request order, and carries nullable second-minus-first `delta`, status `not_comparable`, `equal`, `first_lower`, `second_lower`, `crossover`, or `unresolved`, conditions, assumptions used, unsupported assumptions, blockers, and `IdentityEvidence | PropertyEvidence | null`. Semantic disproof or unresolved status requires `not_comparable`, nonempty blockers, and null evidence; it may retain a delta only when both candidate works are finite. Established semantics with unavailable direct work requires `unresolved`, null delta, nonempty blockers, and null evidence. With established semantics and finite work, delta is required: `equal` requires identity evidence, fixed winners and `crossover` require property evidence, and unsupported sign reasoning requires `unresolved`, nonempty blockers, and null evidence. No other status, nullability, blocker, or evidence combination validates.

### Task 2.2: Implement bounded mapped-output expansion and interface comparison
Kind: batch
Applying: ["adopt-bounded-candidate-comparison:bounded-general-candidate-comparison", "adopt-bounded-candidate-comparison:semantic-comparison-precedes-work-preference"]
Paths: ["packages/py-science-formula/src/py_science/formula/comparison.py", "packages/py-science-formula/src/py_science/formula/equivalence.py", "packages/py-science-formula/src/py_science/formula/expressions.py", "packages/py-science-formula/src/py_science/formula/reasoning.py", "packages/py-science-formula/src/py_science/formula/service.py", "tests/e2e/test_formula_candidate_comparison.py"]
Representative: Compare `r = 1 / d; y[i] = x[i] * r` with `z[j] = x[j] / d`, align `i` and `j` positionally, prove equal effective domains and values under `d != 0`, and leave both submitted graphs untouched for cost accounting.
Edge: Include scalar expression versus scalar equation, indexed binder renaming, nested acyclic producers, repeated producer references, producer indices that differ from consumer indices, lexical `Sum` binders, equation-local effective output domains, exact denominator conditions, semantic disproof with a bounded counterexample, unsupported rational forms, capture risk, and expansion overflow. Never expose this expansion through ordinary equation-targeted queries.
Post-check: Run the new comparison suite and existing system/query suites. Require mapped expansion to change neither candidate `SystemReport` nor retained `WorkAnalysis`; compare those objects with independent ordinary `analyze` results. Require every unsupported interface or expansion case to return a correlated qualified result rather than a false equality or request-wide crash.

Implement comparison-only capture-avoiding producer substitution over the validated acyclic producer graph. Align mapped output binders by position, prove effective lower and upper bounds equal through the shared bounded equivalence seam, and construct comparison-scoped reasoning from shared global knowledge plus proved common output-domain facts. Preserve candidate-local equation constraints as interface/domain evidence without leaking one candidate's unrelated facts into the other. Use the shared equivalence seam for the expanded values and aggregate results with the exact precedence defined in Task 2.1: any disproof, then any unresolved or inapplicable result, then any assumption-qualified equality, otherwise proved equality. Test every mixed-result pair so tuple order cannot change the overall status.

### Task 2.3: Compare retained aggregate work and derive bounded crossovers
Kind: batch
Applying: ["adopt-bounded-candidate-comparison:semantic-comparison-precedes-work-preference", "adopt-bounded-candidate-comparison:qualified-abstract-work-comparison"]
Paths: ["packages/py-science-formula/src/py_science/formula/comparison.py", "packages/py-science-formula/src/py_science/formula/properties.py", "packages/py-science-formula/src/py_science/formula/reasoning.py", "packages/py-science-formula/src/py_science/formula/work.py", "packages/py-science-formula/src/py_science/formula/service.py", "tests/e2e/test_formula_candidate_comparison.py"]
Representative: A proved-equivalent pair whose second-minus-first work delta changes sign at one supported exact univariate threshold reports `crossover` and the exact sign intervals; a fixed-sign delta reports the corresponding lower-work candidate.
Edge: Cover equal work, positive and negative constant deltas, assumption-qualified sign, exact univariate crossover, several exact roots, multivariate unsupported sign, opaque unknown primitive costs, finite versus non-finite direct work, and semantic `disproved` or `unresolved`. Work strings come only from retained submitted-graph `WorkAnalysis.total_work`; top-level `abstract_work`, expanded operands, operation vectors, and runtime language never decide preference.
Post-check: Run the comparison, property, scenario, and system suites. Assert delta orientation directly, assert no preference whenever any mapped semantic result is disproved/unresolved or either direct work is unavailable, and require unknown costs and unsupported sign families to remain named blockers with the symbolic delta retained when finite.

Reuse the existing bounded rational property/sign-chart machinery rather than adding a general inequality solver. Convert exact all-positive/all-negative/zero sign evidence into first/second/equal status and mixed sign intervals into `crossover`; preserve exact conditions and provenance. A valid unsupported sign chart returns `unresolved` with the rendered comparison condition, never sampled evidence or a guessed threshold.

### Task 2.4: Export, document, and apply the direct Python capability
Kind: batch
Applying: ["adopt-bounded-candidate-comparison:bounded-general-candidate-comparison", "adopt-bounded-candidate-comparison:semantic-comparison-precedes-work-preference", "adopt-bounded-candidate-comparison:qualified-abstract-work-comparison"]
Paths: ["packages/py-science-formula/src/py_science/formula/models.py", "packages/py-science-formula/src/py_science/formula/service.py", "packages/py-science-formula/src/py_science/formula/__init__.py", "packages/py-science-formula/README.md", "docs/decisions/adopt-bounded-candidate-comparison.md", "docs/decisions/INDEX.md", ".awf/topics/parts/product/product-boundary/current-state.md", ".awf/topics/parts/product/mathematical-input-contract/current-state.md", ".awf/topics/parts/product/mathematical-analysis-model/current-state.md", ".awf/topics/parts/product/analysis-report-contract/current-state.md", ".awf/docs/glossary.yaml", "docs/topics/product/product-boundary.md", "docs/topics/product/mathematical-input-contract.md", "docs/topics/product/mathematical-analysis-model.md", "docs/topics/product/analysis-report-contract.md", "docs/topics/product/index.md", "docs/analysis-model.md", "docs/glossary.md", ".awf/awf.lock"]
Representative: The Python package guide shows one expression comparison and one named-reuse comparison, and the current-state report contract requires semantic qualification before aggregate-work preference and prohibits runtime interpretation.
Edge: State explicitly that the direct Python comparison request has no scenarios or general queries, uses the fixed ADR-0003 abstract-work semantics, and does not imply resource vectors, machine arithmetic, transformations, parameter search, AFMM completeness, or global optimality.
Post-check: Run `./awf render`, read back every authored and rendered topic/document in `Paths`, and require `./awf check`, `./awf check staged`, package import tests, the comparison suite, and `git diff --check` to pass. Inspect examples by executing them against the public imports.

Export the new request, mapping, result models, and `compare_candidates` without changing `AnalysisRequest`, `AnalysisOutcome`, or `analyze`. Correct the glossary's authority-free future description: candidate comparison uses shared mathematical metadata but this milestone does not compare scenarios. Transition the ADR from Accepted to Implementing and append one Applied event containing exactly its four State changes alongside the matching claim mutations. Update the product-boundary claim to remove only candidate comparison from future work; keep local rewrites, hoisting effects, and improvement ranking deferred. Do not append Implemented.

### Phase close

Run:

```bash
uv run --locked pytest \
  tests/e2e/test_formula_candidate_comparison.py \
  tests/e2e/test_formula_analysis.py \
  tests/e2e/test_formula_system_analysis.py \
  tests/unit/test_formula_queries.py \
  tests/unit/test_formula_properties.py \
  tests/unit/test_formula_scenarios.py \
  tests/unit/test_error_translation.py \
  tests/distribution/test_python_package.py
uv run --locked pyright
uv run --locked ruff check .
./awf check
./awf check staged
./scripts/check
git diff --check
```

Authority check: the ADR is Implementing and its Applied partition exactly equals all four State changes. State check: the public examples execute, existing `AnalysisRequest` model dumps remain stable, and the decision corpus and current-state topics consistently describe direct Python support and Pi transport as not yet widened. Record test-first failures, sign/crossover evidence, generated-prose review, and any reasoned deviations in Notes.

```commit
feat(formula): compare mathematical candidates
```

## Phase 3: Transport comparison through Pi

**Execution mode: subagent-driven.**

Completes: ["strict-pi-comparison", "synchronized-comparison-guidance"]

### Task 3.1: Advance the generated schema and private protocol to v9
Kind: batch
Applying: ["adopt-bounded-candidate-comparison:bounded-general-candidate-comparison", "adopt-bounded-candidate-comparison:semantic-comparison-precedes-work-preference", "adopt-bounded-candidate-comparison:qualified-abstract-work-comparison"]
Paths: ["scripts/generate-pi-formula-schema.py", "packages/pi-science/src/formula-schema.json", "packages/pi-science/bridge/formula_adapter.py", "packages/pi-science/src/bridge.ts", "packages/pi-science/src/provision.ts", "tests/test_pi_schema_generation.py", "packages/pi-science/tests/adapter.test.ts", "packages/pi-science/tests/bridge.test.ts", "packages/pi-science/tests/provision.test.ts", "packages/pi-science/tests/start.test.ts"]
Representative: The real protocol-v9 adapter and strict bridge round-trip two differently named equivalent systems, mapped outputs, both candidate reports, semantic evidence, original aggregate works, second-minus-first delta, and a qualified work relation.
Edge: Preserve every analysis expression/system schema branch and protocol result unchanged; reject missing, surplus, over-bound, version-mismatched, miscorrelated candidate names/order, output mappings/results, semantic populations, work entries, nullable direct-work fields, or invalid status/evidence combinations. TypeScript validates transport shape and correlation only; it never recomputes or judges delta arithmetic.
Post-check: Regenerate the schema, run the schema, adapter, bridge, provisioning, and registered-tool suites, require a fresh temporary schema generation to match the committed artifact, and require `git diff --check` to pass. Assert second-minus-first orientation in the Python comparison suite and preserve that exact value through the real-adapter round trip; bridge-only fixtures assert candidate-name and positional correlation without mathematical recomputation. Run a confined protocol census whose only v8 occurrence is the intentional incompatible-envelope fixture.

Teach the generator to retain its existing expression/system branches and add the provider-compatible comparison branch from `CandidateComparisonRequest`, omitting injected `syntax`. Advance live Python and TypeScript protocol constants to 9 and preserve protocol envelope and response bounds. The adapter validates an analysis-or-comparison request union and dispatches only to `analyze` or `compare_candidates`; it must serialize explicit nulls required by either strict result variant. Add exact TypeScript request/result unions, validators, source-population accounting, and correlation without interpreting equivalence, domain compatibility, delta sign, or crossover mathematics.

### Task 3.2: Expose comparison in the existing tool and synchronize guidance
Kind: batch
Applying: ["adopt-bounded-candidate-comparison:bounded-general-candidate-comparison", "adopt-bounded-candidate-comparison:semantic-comparison-precedes-work-preference", "adopt-bounded-candidate-comparison:qualified-abstract-work-comparison"]
Paths: ["packages/pi-science/src/index.ts", "packages/pi-science/skills/formula-analysis/SKILL.md", "packages/pi-science/tests/start.test.ts", "packages/pi-science/tests/package.test.ts", "README.md", ".awf/parts/agents-doc/identity.md", "AGENTS.md", ".awf/docs/parts/architecture/overview.md", ".awf/docs/parts/architecture/data-flow.md", ".awf/docs/parts/testing/tiers.md", ".awf/docs/parts/testing/layout.md", "docs/architecture.md", "docs/vision.md", "docs/analysis-model.md", "docs/testing.md", "packages/py-science-formula/README.md", "docs/decisions/adopt-bounded-candidate-comparison.md", "docs/decisions/INDEX.md", ".awf/topics/parts/product/product-boundary/current-state.md", ".awf/topics/parts/product/mathematical-input-contract/current-state.md", ".awf/topics/parts/product/mathematical-analysis-model/current-state.md", ".awf/topics/parts/product/analysis-report-contract/current-state.md", "docs/topics/product/product-boundary.md", "docs/topics/product/mathematical-input-contract.md", "docs/topics/product/mathematical-analysis-model.md", "docs/topics/product/analysis-report-contract.md", "docs/topics/product/index.md", ".awf/awf.lock"]
Representative: `analyze_formula` accepts the comparison variant without caller-supplied syntax; compact text lists mapped-output semantic status before the aggregate-work relation and directs the agent to blockers when no preference is justified, while `details` retains the canonical complete result.
Edge: Keep one readiness-gated tool and one product skill; preserve ordinary analysis text and health behavior. Guidance must prohibit interpreting abstract work as speed, preferring semantically unresolved candidates, hiding unknown costs, or treating exact/real symbolic equivalence as IEEE 754 equivalence. It must identify scenarios, transformations, resource vectors, parameter search, and AFMM expansion as outside this comparison request.
Post-check: Run `./awf render`; read the generated identity, architecture, analysis-model, vision, testing guide, package guides, skill, tool description, and representative compact text. Require no stale claim that Python and Pi accept only one expression/system request or that candidate comparison remains future work. Run the focused Pi suites, `./awf check`, `./awf check staged`, the full gate, and `git diff --check`.

Extend the existing `analyze_formula` parameter and bridge request union rather than registering a second tool. Inject `syntax` into either request variant. Compact comparison output reports candidate names and interpretations, overall semantic status, per-output blockers, the named aggregate-work metric, candidate works, delta orientation, decision status/conditions, and unresolved costs in that order. Update the skill with the exact request spelling and compare-revise workflow, and update current product/architecture prose from direct-Python-only delivery to matching Python and Pi support without strengthening later-roadmap promises.

For every already Applied State-change claim whose prose materially changes to describe Pi transport, mutate the authored claim with its rendered outputs and append the matching ADR `Reapplied` event in this transaction. The expected reapplication is add `product/mathematical-input-contract:bounded-candidate-comparison-requests`, widening its direct-Python request statement to matching Python and Pi transport. Reinspect the product-boundary, analysis-model, and report-contract claims: leave a transport-neutral claim byte-for-byte unchanged and append no event for it; if any still states a direct-Python-only boundary, update it and include its exact operation in the same transaction. Do not append Implemented.

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
pattern = re.compile(r"version\s*:\s*8|protocol[- ]?v8|PROTOCOL_VERSION\s*=\s*8")
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
assert re.search(r"version\s*:\s*8", hits[0][2]), hits
PY
```

Authority check: the ADR remains Implementing with all operations Applied, every materially widened claim has one matching Reapplied event and pair-atomic mutation, transport-neutral claims remain unchanged, and no terminal flip occurs. State checks: live protocol constants are 9, the census leaves only the deliberate stale-v8 request, ordinary analysis round trips are unchanged, and comparison round trips preserve semantic-before-work ordering and exact correlation. Record protocol census, generated-prose meaning review, compact-output inspection, and deviations in Notes.

```commit
feat(pi): expose candidate comparison
```

## Definition of done

- `dod: candidate-comparison-contract` Direct Python accepts one strict bounded request containing exactly two general mathematical candidate computations and explicit mapped outputs, validates compatible interfaces, preserves existing analysis requests, and rejects unsupported or surplus shapes with localized diagnostics.
- `dod: semantic-candidate-comparison` Python expands only mapped acyclic dependencies under an aggregate resource bound, aligns compatible output domains and binders, and returns conservative per-output plus overall equality, conditional equality, disproof, or unresolved evidence without altering submitted graphs or general queries.
- `dod: qualified-work-comparison` Only semantically established candidates receive an aggregate abstract-work preference; results preserve both reuse-aware original works, second-minus-first delta, bounded exact winner/crossover evidence, unknown costs, assumptions, conditions, and explicit abstention without runtime or global-optimality claims.
- `dod: strict-pi-comparison` Protocol v9, generated provider schema, bounded adapter, exact TypeScript bridge, readiness-gated `analyze_formula` tool, compact projection, and canonical details transport and correlate the comparison contract while retaining all existing analysis behavior.
- `dod: synchronized-comparison-guidance` Applied ADR claims, rendered current state, vision, analysis model, architecture, package guides, agent identity, product skill, routing text, examples, tests, and roadmap boundaries consistently describe the shipped general-purpose comparison capability and its exclusions; the full gate passes.

## Notes

- Plan-review mechanical disposition: merged the lifecycle-only task into the enabling refactor so every Applying assignment implements part of the linked nonterminal ADR; staged Task 2.1 model failures before service failures; and added the protocol-v9 testing documentation owners.
- Plan-review reasoned disposition: fixed the complete comparison outcome, interface, semantic aggregation, work-status, nullability, blocker, and evidence truth tables; mixed mapped-output precedence is order-independent. Added the glossary owner and removed its unsupported shared-scenario implication while leaving scenario comparison excluded.
- Plan-review verify-pass residual disposition: Phase 3 now owns pair-atomic Reapplied events for claims materially widened from direct Python to Python and Pi, while leaving transport-neutral claims unchanged. TypeScript correlates candidate order and fields but never validates delta arithmetic; Python and the real-adapter round trip prove second-minus-first orientation.
- Phase 1 baseline: before phase-owner mutation, the parent ran the three focused suites (166 passed), pyright, ruff, `./scripts/check` (286 Python and 94 Pi tests), and `git diff --check`; all passed. This evidence was recorded after the phase-closing commit during review settlement because the phase owner omitted the required Notes entry.
- Phase 1 review settlement: made retained parsed-equation and work-analysis state deeply read-only, added parser-call characterization proving expression and system queries reuse validated operands, restored the `_attach_queries` docstring, and reformatted the introduced retained-state paths. Renewed review found the shallowly frozen submitted `EquationRequest` still exposed its mutable domain mapping, so retained equations now keep only frozen private metadata plus parsed state. The late baseline record is a reasoned process deviation; no approved design boundary changed.

Inline owners immediately correct stale instructions and record reasoned deviations here. Delegated owners may report rather than edit; the parent supplies the report to phase review and reconciles it with findings in one focused post-review settlement commit before checkpointing or later execution. Record baseline and test-first evidence, public-shape deviations, protocol census, generated-prose meaning review, compact-output inspection, follow-ups, and findings surfaced during implementation.
