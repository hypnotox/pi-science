---
format: plan-v2
date: 2026-08-18
adrs:
  - adopt-compositional-indexed-equation-analysis
  - adopt-acyclic-dependent-output-domains
status: Implemented
---
# Plan: Repair nested aggregation and add constrained output domains

## Goal

Make aggregate direct-work analysis binder-correct for nested finite sums, then support deterministic acyclic affine dependencies between equation output domains with qualified relationship provenance across general and scenario reports. Nested mathematical closed forms, general polynomial summation, absolute-value semantics, complex scalars, broader exponent normalization, and binder-aware optimization suggestions remain outside this plan.

## Architecture summary

Execution has two independently green transactions. The first repairs ADR-0003 behavior without changing request shape: every expression-valued `WorkAnalysis` field is aggregated through the sum binder, reduction additions remain separate mathematical work, and no completed general or specialized work expression may retain a locally bound index as a free symbol. An exact symbolic `Sum` is a completed binder-owning work expression, not a leaked index and not by itself unresolved. Existing cardinality blockers remain in the flat `unresolved` collection; no field is omitted and no new result sentinel or protocol shape is introduced.

The second transaction introduces one Python-owned constrained-iteration boundary consumed by request validation, work aggregation, relationship reasoning, and scenarios. Output-domain references form an inferred dependency DAG; LHS indices retain mathematical coordinate order and break topological ties only. Aggregation traverses the dependency order from inner to outer. Dependent bounds use the linked ADR's bounded affine-integer grammar, while existing independent bounds retain their current accepted family. The shared bounded reasoner consumes intrinsic domains, supported substitutions and affine relationships, and predecessor-domain facts with provenance under the existing `MAX_REASONING_STEPS = 4096`, `MAX_INTERMEDIATE_NODES = 4096`, and `MAX_WORK_NODES = 4096` limits; it never delegates policy to unrestricted SymPy. The public JSON request shape and protocol-v6 result shape remain unchanged.

The harmonic/M2L workload is an end-to-end acceptance corpus, not a public domain-specific abstraction. Python remains mathematical authority; Pi receives the behavior through the existing adapter while its tool metadata, integration tests, and packaged formula-analysis skill describe and verify the same boundary. Current-state claims, user documentation, and the Python README change with each capability transaction, and schema regeneration must prove that the unchanged structural request shape has not drifted.

## Phase 1: Repair nested direct-work binding

**Execution mode: subagent-driven.**

Completes: ["nested-binder-correctness"]

### Task 1.1: Add failing nested-work regressions
Applying: ["adopt-compositional-indexed-equation-analysis:mathematical-aggregate-work-semantics"]
Paths: ["tests/e2e/test_formula_system_analysis.py", "tests/unit/test_formula_scenarios.py", "packages/pi-science/tests/start.test.ts"]

Add `test_nested_sum_work_keeps_iterators_lexically_bound` around `Sum(Sum(x[j], (j, k, n)), (k, 0, p - 1))`, including a primitive whose declared work depends on `k`, and `test_nested_sum_scenarios_eliminate_free_bound_indices` with a fixed `p`. Assert across aggregate operation categories, total and opaque work, primitive invocation counts, equation/system totals, and scenario work that `k` and `j` are either eliminated or occur only inside a `Sum` that binds them. Assert specifically that no rendered `Max` contains either iterator free. Add a registered-tool round trip in `start.test.ts` with the same fixed-order property. Preserve the existing tested distinction that a `closed_form` query over a nested mathematical sum returns `unresolved` with the nested-sum blocker.

Run the focused tests before production mutation and record in Notes that the new Python and Pi binder assertions fail for the leaked-index reason rather than request construction or transport.

### Task 1.2: Aggregate every work field through finite-sum binders
Applying: ["adopt-compositional-indexed-equation-analysis:mathematical-aggregate-work-semantics"]
Paths: ["packages/py-science-formula/src/py_science/formula/work.py"]

Replace `_analyze_sum`'s unconditional body scaling with binder-aware aggregation. Apply the finite iterator to symbolic operation categories, opaque work, and each primitive invocation count; retain unknown-cost, unresolved, and blocker sets without fabricating work. Charge reduction additions once per nonempty iterator. Use `_free_symbol_names` or an equivalent binder-aware predicate rather than structural `_contains_symbol`, so a nested binder with the same textual name cannot be mistaken for a free dependency.

When a value depends on the iterator, retain `Sum(value, (index, lower, upper))`; this expression itself owns the iterator and remains a populated exact symbolic work field. If cardinality integrality or finiteness is unproved, preserve the existing deterministic cardinality unresolved entry and populated binder-owning expression. Do not add a field-local result type, omit the field, or change protocol v6. Keep mathematical query evaluation in `series.py` unchanged.

### Task 1.3: Synchronize nested-work current state, documentation, and Pi metadata
Kind: batch
Applying: ["adopt-compositional-indexed-equation-analysis:mathematical-aggregate-work-semantics", "adopt-compositional-indexed-equation-analysis:provenance-preserving-system-analysis"]
Paths: [".awf/topics/parts/product/mathematical-analysis-model/current-state.md", ".awf/topics/parts/product/analysis-report-contract/current-state.md", "docs/topics/product/mathematical-analysis-model.md", "docs/topics/product/analysis-report-contract.md", "docs/topics/product/index.md", "docs/analysis-model.md", "packages/py-science-formula/README.md", "packages/pi-science/skills/formula-analysis/SKILL.md", "packages/pi-science/src/index.ts", "packages/pi-science/tests/start.test.ts", ".awf/awf.lock"]
Representative: Clarify `ideal-equation-dependency-work` so nested finite direct work is recursively binder-scoped, and clarify `provenance-preserving-system-work` so unresolved cardinality remains explicit without presenting a local iterator as free.
Edge: Preserve both claims' `Origin: ADR-0003`; this is a current-state correction to already-decided semantics, not an application of the pending dependent-domain ADR and not broader closed-form support.
Post-check: Run `./awf render`; require `./awf check` to exit 0; inspect the two authored claim parts and the two rendered topic pages plus `docs/analysis-model.md` for the nested-direct-work versus mathematical-closed-form distinction; require `git diff --check` to exit 0.

Update the Python README, analysis model, Pi formula-analysis skill, and tool description or prompt snippet to advertise bounded nested finite-work analysis without implying nested closed forms. Keep the registered-tool assertions aligned with the packaged skill.

### Phase close

Authority check: `./awf check staged` must report zero findings. State checks:

```bash
uv run --locked pytest \
  tests/e2e/test_formula_system_analysis.py::test_nested_sum_work_keeps_iterators_lexically_bound \
  tests/unit/test_formula_scenarios.py::test_nested_sum_scenarios_eliminate_free_bound_indices
npx vitest run packages/pi-science/tests/start.test.ts
git diff --check
```

Combined authority-and-state gate: `./scripts/check`. The two focused regressions must have been observed failing before Task 1.2 and must now pass; the targeted Pi file and full project gate must finish with no failures, and `git diff --check` must be empty. Close one transaction:

```commit
fix(formula): preserve nested sum work binders
```

## Phase 2: Implement acyclic affine output domains

**Execution mode: subagent-driven.**

Completes: ["dependent-domain-contract", "bounded-domain-reasoning", "harmonic-acceptance", "synchronized-product-surfaces"]

### Task 2.1: Specify the dependent-domain behavior with failing tests
Applying: ["adopt-compositional-indexed-equation-analysis:compositional-mathematical-requests", "adopt-acyclic-dependent-output-domains:acyclic-dependent-output-domains", "adopt-acyclic-dependent-output-domains:preserve-mathematical-index-order", "adopt-acyclic-dependent-output-domains:bounded-relational-domain-reasoning"]
Paths: ["tests/e2e/test_formula_system_analysis.py", "tests/unit/test_formula_scenarios.py", "packages/pi-science/tests/start.test.ts", "docs/decisions/adopt-acyclic-dependent-output-domains.md", "docs/decisions/INDEX.md", ".awf/awf.lock"]

Before test mutation, transition ADR-adopt-acyclic-dependent-output-domains from Proposed to Accepted through the ADR lifecycle workflow. Its first and only application batch occurs in Task 2.3, which appends Implementing and one Applied event for all three distinct claim operations. Terminal Implemented remains deferred until implementation assurance settles.

Replace the blanket rejection test with these executable seams:

- `Eq(A[n, m], x + 1)` with `n: 0..p`, `m: -n..n` has `(p + 1)**2` output points and aggregate work, specializing to `169` at `p = 12` and `441` at `p = 20` with no free `n`, `m`, or bound-index `Max`.
- `Eq(B[i, j], x + 1)` with LHS order `(i, j)`, `i: 0..j`, `j: 0..N` is accepted and aggregated in dependency order `(j, i)` without changing normalized LHS coordinate order.
- Independent domains use LHS order as their deterministic tie-break. Self-dependence and multi-index cycles fail at the relevant domain path. Calls, indexed values, symbolic products, powers, division, and submitted aggregate operators fail only when they cause a dependent bound; currently valid non-affine independent bounds remain accepted.
- `Eq(C[i], x[i] + 1)` with `i: 0..sigma - h`, nonnegative-integer `h` and `sigma`, and named assumption `h_le_sigma: h <= sigma` produces cardinality `sigma - h + 1`, records `h_le_sigma` in `relationships_used`, and does not retain `Max`. An analogous request without sufficient facts remains valid with a populated symbolic aggregate and deterministic flat unresolved qualification rather than a stronger conclusion.

Assert the same dependent-domain request passes the generated Pi schema structurally and reaches Python policy through the registered tool. In this test-first task, add the exact Python assertions for operation fields, total and opaque work, primitive invocations, scenarios, provenance, and unresolved entries, plus matching Pi assertions for total work and unresolved entries. Run the focused tests before implementation and record the expected dependent-domain rejection and unsupported-inequality failures in Notes.

### Task 2.2: Build the constrained-iteration kernel and connect Python consumers
Applying: ["adopt-compositional-indexed-equation-analysis:ideal-equation-dependency-semantics", "adopt-compositional-indexed-equation-analysis:mathematical-aggregate-work-semantics", "adopt-compositional-indexed-equation-analysis:provenance-preserving-system-analysis", "adopt-acyclic-dependent-output-domains:acyclic-dependent-output-domains", "adopt-acyclic-dependent-output-domains:preserve-mathematical-index-order", "adopt-acyclic-dependent-output-domains:bounded-relational-domain-reasoning"]
Paths: ["packages/py-science-formula/src/py_science/formula/domains.py", "packages/py-science-formula/src/py_science/formula/service.py", "packages/py-science-formula/src/py_science/formula/reasoning.py", "packages/py-science-formula/src/py_science/formula/work.py"]

Introduce a cohesive constrained-domain module owning parsed output-domain entries, free-index dependency extraction, stable topological ordering, affine-dependent-bound validation, and local inclusive-bound facts. Keep request diagnostics and orchestration in `service.py`; keep expression representation independent of service and transport. Infer edges only from free output-index references in each bound, reject self-dependence and cycles, preserve LHS order separately, and aggregate output domains in reverse dependency order so prerequisite indices are outer binders.

Generalize the existing `ReasoningContext` rather than adding a second sign engine. Combine intrinsic integer/sign domains, supported equality and directed-definition substitution, normalized affine equalities and inequalities, and predecessor lower/upper facts under exactly the existing 4096-step, 4096-intermediate-node, and 4096-work-node limits. Feed integral, order, sign, and provenance conclusions into cardinality, direct-work aggregation, `Max` simplification, scenarios, `relationships_used`, and `unused_assumptions`. Add only direct-work affine finite summation sufficient to close triangular cardinalities and their fixed scenarios; do not broaden the public `closed_form` evaluator.

Every exact aggregate field stays populated. An index-dependent value closes as a binder-owning `Sum` when the bounded affine work simplifier does not derive a smaller form; existing flat unresolved entries identify unproved cardinality or finiteness. Implement until all already-failing assertions from Task 2.1 pass. Preserve request/result shapes, independent-domain behavior, equation dependency/reuse semantics, and all named resource limits.

### Task 2.3: Apply the ADR claims and land synchronized harmonic acceptance
Kind: batch
Applying: ["adopt-compositional-indexed-equation-analysis:compositional-mathematical-requests", "adopt-compositional-indexed-equation-analysis:ideal-equation-dependency-semantics", "adopt-compositional-indexed-equation-analysis:explicit-function-cost-knowledge", "adopt-compositional-indexed-equation-analysis:provenance-preserving-system-analysis", "adopt-acyclic-dependent-output-domains:acyclic-dependent-output-domains", "adopt-acyclic-dependent-output-domains:preserve-mathematical-index-order", "adopt-acyclic-dependent-output-domains:bounded-relational-domain-reasoning"]
Paths: ["tests/e2e/test_formula_system_analysis.py", "packages/pi-science/tests/start.test.ts", "packages/pi-science/src/index.ts", "packages/pi-science/skills/formula-analysis/SKILL.md", "packages/py-science-formula/README.md", "docs/analysis-model.md", "docs/decisions/adopt-acyclic-dependent-output-domains.md", "docs/decisions/INDEX.md", ".awf/topics/parts/product/mathematical-input-contract/current-state.md", ".awf/topics/parts/product/mathematical-analysis-model/current-state.md", ".awf/topics/parts/product/analysis-report-contract/current-state.md", "docs/topics/product/mathematical-input-contract.md", "docs/topics/product/mathematical-analysis-model.md", "docs/topics/product/analysis-report-contract.md", "docs/topics/product/index.md", ".awf/awf.lock"]
Representative: In one Applied event, update `compositional-indexed-equation-requests` to admit inferred acyclic affine output-domain dependencies while preserving LHS order; update `ideal-equation-dependency-work` to aggregate in reverse stable dependency order using bounded affine facts; update `provenance-preserving-system-work` to report used submitted and predecessor-domain relationships while retaining binder-owned symbolic work and explicit unresolved qualifications.
Edge: Append Accepted before Phase 2 mutation, then Implementing and `Applied; operations: update product/mathematical-input-contract:compositional-indexed-equation-requests, update product/mathematical-analysis-model:ideal-equation-dependency-work, update product/analysis-report-contract:provenance-preserving-system-work` with exactly matching claim mutations. Do not append Implemented, change protocol v6, change the generated schema, or apply any later-family semantics.
Post-check: Run `./awf render`; require `./awf check` and `./awf check staged` to report zero findings; run `git diff --exit-code HEAD -- packages/pi-science/src/formula-schema.json` after schema generation and require no diff; inspect the ADR history, all three authored claims, their three rendered topic pages, `docs/decisions/INDEX.md`, and `docs/analysis-model.md`; require the Applied operation set to equal the ADR State changes and require `git diff --check` to exit 0.

Add this exact general acceptance system, using restricted syntax and ordinary names rather than public harmonic types:

```text
ratio_t:    Eq(r_t, h_t / sigma)
ratio_s:    Eq(r_s, h_s / sigma)
factor_t:   Eq(a[n], r_t**n),                    n: 0..p
factor_s:   Eq(b[k], r_s**k),                    k: 0..p
scale:      Eq(S[n, k], a[n] * b[k]),            n: 0..p, k: 0..p
translation: Eq(L[n, m],
  a[n] * Sum(
    b[k] * Sum(conjugate(M[k, l]) * harmonic(n + k, m + l), (l, -k, k)),
    (k, 0, p))),                                 n: 0..p, m: -n..n
```

Declare `p` positive integer, `h_t`, `h_s`, and `sigma` positive real, and `M` real until the separate complex feature exists. Declare scalar primitive work `1` for both `conjugate(value)` and `harmonic(degree, order)` so they remain opaque rather than receiving invented mathematics. Expected dependency edges are `ratio_t -> factor_t`, `ratio_s -> factor_s`, `factor_t -> scale`, `factor_s -> scale`, `factor_t -> translation`, and `factor_s -> translation`, each with one ideal-reuse reference. The translation has `(p + 1)**2` output coefficients, per-coefficient work `6*p**2 + 13*p + 7` under the declared primitive costs, total work `(p + 1)**2*(6*p**2 + 13*p + 7)`, and `(p + 1)**4` invocations of each primitive. Its fixed translation work is `173563` at `p = 12` and `1176147` at `p = 20`; primitive invocations are respectively `28561` and `194481` for each primitive. Verify normalized interpretation preserves `L[n, m]`, the triangular `m` domain, and the nested `k`/`l` binders. No test may treat this fixture as physical validation or complex-number semantics.

Update all listed Python, Pi skill/tool, current-state, and rendered documentation surfaces with dependency inference, LHS-order preservation, the affine grammar, invalid cycles/out-of-family dependencies, qualified in-family limits, and provenance. The Pi tool test must round-trip this capability through the real adapter.

### Phase close

Choreography step: run `./awf render` and read back every listed authored and generated target. Authority checks: `./awf check` and `./awf check staged` must report zero findings, and the ADR Applied partition must exactly match all three declared operations. State checks:

```bash
uv run --locked pytest \
  tests/e2e/test_formula_system_analysis.py \
  tests/unit/test_formula_scenarios.py
npx vitest run packages/pi-science/tests/start.test.ts
uv run --locked pyright
git diff --exit-code HEAD -- packages/pi-science/src/formula-schema.json
git diff --check
```

Combined authority-and-state gate: `./scripts/check`. The focused dependent-domain tests must have been observed failing before Task 2.2 and must now pass. The Python files, Pi integration file, type checker, render/drift checks, and full gate must have no failures; the schema comparison and whitespace check must be empty. Inspect and record the exact generated topic, decision-index, analysis-model, skill, and tool-description readings named in Task 2.3. Close one transaction:

```commit
feat(formula): support dependent output domains
```

## Definition of done

- `dod: nested-binder-correctness` Every nested finite-sum work field and fixed scenario either eliminates each local iterator or retains it only under its lexical `Sum`; no iterator leaks free into `Max`, total work, operation counts, opaque work, or primitive invocations, while nested mathematical closed-form queries remain explicitly unsupported.
- `dod: dependent-domain-contract` Equation output bounds accept deterministic acyclic affine dependencies without changing LHS coordinate order, reject self/cyclic/out-of-family dependencies with localized diagnostics, and preserve the existing independent-bound family.
- `dod: bounded-domain-reasoning` Cardinality, aggregate work, scenarios, and reports consume the same bounded intrinsic, substitution, affine-relationship, and predecessor-domain facts with inspectable provenance and qualified unresolved outcomes.
- `dod: harmonic-acceptance` The specified general harmonic/M2L-style system demonstrates triangular counts, nested aggregation, exact dependency/reuse edges, and the stated `p = 12` and `p = 20` work through Python and Pi without domain-specific public semantics.
- `dod: synchronized-product-surfaces` Python tests and README, Pi tool metadata/tests and packaged skill, unchanged generated schema verification, ADR-backed current-state claims, rendered topic pages, and analysis documentation describe and enforce the same boundary, and the full project gate passes.

## Notes

- Plan review disposition: added same-transaction current-state claim and rendered-topic updates to Phase 1 so the binder repair corrects active documentation without implying nested closed-form support.
- Plan review disposition: defined unchanged protocol-v6 behavior explicitly: binder-owned `Sum` fields remain populated and exact; existing flat unresolved entries qualify unproved cardinality, with no new sentinel or field omission.
- Plan review disposition: fixed reasoning and work budgets at the existing named 4096 limits rather than delegating budget tightening.
- Plan review disposition: made both phase gates executable with authority/state classification, pre-fix failure evidence, snapshot-relative schema comparison, and explicit terminal expectations.
- Plan review disposition: fixed the harmonic acceptance system, costs, dependencies, symbolic formula, scenario values, and semantic-rendering expectations so implementation does not choose a new scientific boundary.
- Phase 1 deviation: because ADR-0003 is terminal, current-state claim corrections landed through the narrowly scoped direct-transition ADR `correct-nested-finite-work-current-state-claims`; its two operations exactly match the claim updates and do not authorize Phase 2 semantics.
- Phase 1 deviation: binder-correct retained sums changed existing Pi golden output, so `packages/pi-science/tests/afmm-fixture.ts` and `packages/pi-science/tests/adapter.test.ts` joined the phase transaction as required consumers.
- Phase 1 review: commit `887c33ae5db84088354490a108b8111cae0c5870` received complete phase coverage with no findings. Phase 2 remains fresh but must preserve the existing claim `Revised-by` provenance when applying its pending ADR.
- Phase 2 implementation deviation 1: unary-negative affine terms required admitting `-symbol` in the restricted parser and removing that spelling from the malformed-syntax regression; this is the smallest translation needed to represent the ADR's signed affine coefficients, not broader unary-expression support.
- Phase 2 implementation deviation 2: bounded direct-work polynomial summation required a backend-owned `close_direct_work_sum` seam in `sympy_backend.py`; policy remains in work aggregation, the seam is structurally preflighted, and the public mathematical closed-form evaluator is unchanged.
- Phase 2 implementation deviation 3: the existing scenario expectation changed because proven dependent-domain closure now eliminates a formerly retained binder; the fixture was updated to the exact specialized work rather than weakening its oracle.
- Phase 2 implementation deviation 4: the Pi AFMM golden consumers joined Phase 2 because authorized direct-work sum closure altered their renderings; post-review settlement removed global work factoring, verified unrelated independent-domain rendering remained unchanged, and retained only golden changes caused by the authorized direct-sum seam.
- Phase 2 review finding 1 disposition: unresolved output ordering now uses a zero-clamped inclusive extent and a clamped lexical `Sum` binder, and fixed empty scenarios simplify to zero; the symbolic-then-fixed-empty regression proves no negative work.
- Phase 2 review finding 2 disposition: submitted affine inequality differences are compared structurally up to a common positive rational scalar, so `2*h <= 2*sigma` proves the same ordering as `h <= sigma` while retaining the submitted relationship's name and source.
- Phase 2 review finding 3 disposition: affine candidates are structurally parsed and node-bounded before SymPy, candidate traversal is capped by `MAX_REASONING_STEPS`, and direct-work candidates are checked against `MAX_WORK_NODES`/`MAX_INTERMEDIATE_NODES` before backend expansion.
- Phase 2 review finding 4 disposition: ordinary `render_work` again performs only bounded rendering; polynomial factoring and summation remain confined to the direct-work sum closure seam, whose inputs and output are bounded, and unrelated independent-domain rendering expectations are restored.
- Phase 2 review finding 5 disposition: focused regressions now cover indexed values, calls, symbolic products in both orders, powers, division, submitted sums, accepted nonlinear independent bounds, bound free symbols and shadowing, stable three-index topological ties, coefficient multiplication in both orders, unary-negative affine terms, and endpoint-local diagnostics.
- Phase 2 review finding 6 disposition: the Python and registered-Pi harmonic requests now include `p=12` and `p=20`; tests assert exact normalized translation, operation and aggregate-operation fields, aggregate work, primitive counts, dependency/reuse, provenance, no leaked indices, and exact existing-shape system scenario totals (`173760` and `1176632`). The unchanged result shape has system scenario work but no per-equation scenario invocation fields, so general primitive invocation formulas are specialized and checked in Python without inventing fields.
- Phase 2 review finding 7 disposition: reversible test-first falsifications separately disabled dependent-domain acceptance and submitted affine-inequality use, produced the intended focused failures, and were restored by exact inverse edits without a file reset; commands and observed outputs are recorded below after final green verification.
- Phase 2 settlement falsification evidence: changed exactly `if references and form is None` to `if references` in `domains.py`, ran `uv run --locked pytest tests/e2e/test_formula_system_analysis.py::test_dependent_output_domains_preserve_lhs_order_and_close_triangular_work -q`, and observed exit 1 with `assert triangular.status == "success"` receiving `failure`; restored the exact line. Separately changed exactly `relationship_use = self._submitted_nonnegative_use(value)` to `relationship_use = None  # reversible falsification` in `reasoning.py`, ran `uv run --locked pytest tests/e2e/test_formula_system_analysis.py::test_affine_domain_ordering_uses_named_relationship_provenance -q`, and observed exit 1 with qualified total work `Max(0, -h + sigma + 1)` instead of `-h + sigma + 1`; restored the exact line. The combined focused rerun then reported `2 passed in 0.24s`. No falsification mutation remains.
- Phase 2 renewed-review disposition: direct-work polynomial closure is now disabled whenever cardinality remains a `Max`-clamped unproved ordering. The retained lexical sum specializes through existing constant simplification, and `i: 2..N` with primitive work `i` and fixed `N=0` now reports scenario work `0` instead of `-1`.
- Terminal assurance remediation: index-dependent general work now uses the same `Max`-clamped inclusive upper bound as its cardinality, so later symbolic specialization cannot recover SymPy's negative reversed-sum continuation. System provenance is deduplicated by relationship identity rather than display name, preserving distinct predecessor-domain facts from equations that reuse an index name.
- Terminal assurance falsification evidence: changed exactly `_subtract(_add(lower, count), _ONE) if count_is_clamped else upper` to `upper  # reversible falsification: bypass the Max-clamped bound` in `work.py`, ran `uv run --locked pytest tests/e2e/test_formula_system_analysis.py::test_unproved_independent_domain_closure_clamps_fixed_empty_work -q`, and observed exit 1 with raw general work `Sum(i, (i, 2, N))` instead of the clamped bound; restored the exact line. Separately changed exactly `relationship_uses.update({(item.name, item.relationship): item for item in used})` to `relationship_uses.update({(item.name, ""): item for item in used})` in `service.py`, ran `uv run --locked pytest tests/e2e/test_formula_system_analysis.py::test_same_named_predecessor_domains_keep_equation_specific_provenance -q`, and observed exit 1 with only `("domain:n", "1 <= n <= q")` retained; restored the exact line. The terminal verify review found one mechanical evidence gap in the parallel mathematical `Sum` path. Added a direct-sum regression, changed exactly `if count_is_clamped` to `if False  # reversible falsification: bypass the Sum clamp` in `_analyze_sum`, ran `uv run --locked pytest tests/e2e/test_formula_system_analysis.py::test_unproved_sum_clamps_index_dependent_work_before_specialization -q`, and observed exit 1 with raw general work `Sum(i, (i, 2, N))`; restored the exact line. No falsification mutation remains, and the mechanical-only review disposition requires no further verify pass.
- Later bounded families, including binder-aware invariant/hoisting reports, polynomial mathematical closed forms, exponent/product normalization, complex scalar and conjugation semantics, and absolute-value constraints, remain recorded in effort `bounded-analysis-expansion` and require separately reviewed plans or ADRs when their load-bearing semantics are settled.
