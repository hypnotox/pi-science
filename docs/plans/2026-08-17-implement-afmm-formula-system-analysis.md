---
format: plan-v2
date: 2026-08-17
adrs: [adopt-compositional-indexed-equation-analysis]
status: Proposed
---
# Plan: Implement AFMM Formula System Analysis

## Goal

Deliver a restricted-SymPy mathematical request and report path that can represent, compose, and analyze an AFMM-like indexed equation system through both the public Python API and Pi, including symbolic work, ideal named-result reuse, explicit assumptions, variable scenarios, opaque primitive costs, and qualified complexity. LaTeX input, source-code inference, physical validation, empirical timing, hardware modeling, recurrences, and code generation are non-goals.

## Architecture summary

Extend the existing strict Python request boundary and backend-independent immutable expression tree rather than making SymPy the protocol or analysis model. The restricted parser will build typed nodes for indexed values, generic calls, bounded sums, and equations from Python expression AST data; all formula-bearing metadata uses the same safe parser and one request-wide complexity policy. A symbolic work layer preserves submitted operation structure, derives bounded-sum and function-call work, and renders only validated mathematical nodes through the SymPy backend. A system layer validates local index scopes and output domains, builds an acyclic named-equation dependency graph, charges each equation once per output-domain point, and reuses producer results downstream.

Assumptions and directed definitions pass through constrained deterministic transformations with provenance. Variable declarations own intrinsic mathematical domains, while scenarios own fixed, bounded, choice, derived, and asymptotic treatments; exact symbolic work remains available when a tighter conclusion is unsupported. Generic functions prefer mathematical definitions, accept one scalar symbolic work expression only when intentionally opaque, and otherwise retain an unresolved cost. The private versioned adapter and Pi schema translate the public Python contracts without becoming analysis authority. The implementation preserves the approved formula-only boundary and reports optimization opportunities without silently changing the submitted computation.

## Phase 1: Deliver compositional indexed equation work

**Execution mode: subagent-driven.**

Completes: ["safe-mathematical-systems", "ideal-symbolic-work"]

### Task 1.1: Extend strict requests, the typed IR, and safe parsing
Applying: ["adopt-compositional-indexed-equation-analysis:compositional-mathematical-requests"]
Paths: ["packages/py-science-formula/src/py_science/formula/", "tests/e2e/test_formula_analysis.py", "tests/e2e/test_formula_system_analysis.py", "tests/unit/"]

Start from the review-settled `ADR-adopt-compositional-indexed-equation-analysis` and the green single-expression analyzer on the effort branch; establish the complete equation-system and ideal-reuse core before assumption or scenario specialization. Drive strict public-contract and parser behavior through failing tests before production changes. Add request models for named equations, per-equation output domains, external variable declarations, mathematical function definitions, and scalar primitive work declarations while retaining the ordinary one-expression request. Require exactly one expression or a nonempty uniquely named equation list, strict frozen data, and explicit mathematical domains for external variables used by a system. Extend the backend-independent immutable IR and allowlisted Python-AST conversion for indexed values such as `x[i, d]`, ordinary named generic calls, `Sum(body, (index, lower, upper))`, and `Eq(lhs, rhs)`. Restrict an equation left side to one scalar or indexed result; reject attributes, dynamic call targets, keywords, unpacking, executable constructs, duplicate definitions, invalid arity, malformed index tuples, and unsupported special forms.

Give bound indices lexical scope, forbid ambiguous shadowing within one formula, and validate that every free right-side index is either a declared output index or a bound iterator. Apply existing byte, depth, integer, and node protections to every mathematical string; add public-Python limits for total request bytes, equations, function definitions, domains, primitive costs, and aggregate expression nodes so splitting input across fields cannot bypass safety limits. Bound normalized rendering and report construction before allocating an unbounded public result. Submitted text must never reach Python evaluation or a SymPy string parser. Extend the one-way SymPy adapter only for validated nodes and return normalized SymPy and LaTeX for each accepted expression and equation without eager evaluation of powers.

### Task 1.2: Derive bounded-sum and generic-function work
Applying: ["adopt-compositional-indexed-equation-analysis:mathematical-aggregate-work-semantics", "adopt-compositional-indexed-equation-analysis:explicit-function-cost-knowledge"]
Paths: ["packages/py-science-formula/src/py_science/formula/", "tests/e2e/test_formula_analysis.py", "tests/e2e/test_formula_system_analysis.py", "tests/unit/"]

Introduce a typed symbolic work representation separate from SymPy objects. Preserve integer submitted counts for literal operator occurrences and add symbolic aggregate counts and work renderings for executed mathematical structure. For an inclusive bounded sum, derive `max(upper - lower + 1, 0)` when integral ordering facts are available, multiply body work by that cardinality, and add `max(cardinality - 1, 0)` reduction additions; apply the rule recursively to nested sums and return qualified or unresolved work when cardinality cannot be established. Do not charge index access, loop control, bound evaluation, storage, or hardware effects.

Analyze a generic function definition by safely substituting actual arguments into its validated mathematical body. Otherwise substitute its validated scalar primitive `work` expression per invocation, or retain a stable unresolved symbolic cost and list the unknown. Reject definition/work conflicts, arity mismatches, and recursive function definitions. Count argument-expression work normally, aggregate calls across surrounding domains, and report primitive invocation counts separately. Repeated unnamed subexpressions and calls remain charged as submitted; detection may report an extraction opportunity but must not modify the baseline total.

### Task 1.3: Build the ideal named-equation dependency analysis
Applying: ["adopt-compositional-indexed-equation-analysis:ideal-equation-dependency-semantics", "adopt-compositional-indexed-equation-analysis:provenance-preserving-system-analysis"]
Paths: ["packages/py-science-formula/src/py_science/formula/", "packages/pi-science/src/bridge.ts", "packages/pi-science/tests/bridge.test.ts", "tests/e2e/test_formula_system_analysis.py", "tests/unit/"]

Resolve indexed references to unique equation producers, construct deterministic dependency edges, reject self-reference and cycles, and validate local output-domain bindings independently for each equation. Calculate each equation's work once across its own output domain and sum those equation totals once for system work; a downstream reference contributes access to an already-defined mathematical value, never recursive producer construction. Report per-equation submitted counts, symbolic aggregate counts and work, the total system work, dependency edges, reuse/reference information, extraction opportunities, unknown primitive costs, and unresolved conclusions in strict discriminated public models.

Preserve the existing one-expression behavior while evolving its result into the same inspectable report family. Update the private TypeScript response validator and regression fixtures in the same task so the already-advertised simple Pi tool remains compatible and fail-closed with the richer public result. Cover empty domains, one-term sums, nested sums, symbolic domain sizes, duplicate left sides, out-of-scope indices, distinct local uses of the same index name, repeated producer references, unnamed repetition, and deterministic topological ordering.

### Task 1.4: Apply the input and analysis-model claims
Kind: batch
Applying: ["adopt-compositional-indexed-equation-analysis:compositional-mathematical-requests", "adopt-compositional-indexed-equation-analysis:ideal-equation-dependency-semantics", "adopt-compositional-indexed-equation-analysis:mathematical-aggregate-work-semantics", "adopt-compositional-indexed-equation-analysis:explicit-function-cost-knowledge"]
Paths: ["docs/decisions/adopt-compositional-indexed-equation-analysis.md", ".awf/topics/parts/product/mathematical-input-contract/current-state.md", ".awf/topics/parts/product/mathematical-analysis-model/current-state.md", "docs/topics/product/mathematical-input-contract.md", "docs/topics/product/mathematical-analysis-model.md", "docs/domains/product.md", "docs/decisions/INDEX.md", "docs/analysis-model.md", ".awf/awf.lock"]
Representative: Apply `product/mathematical-input-contract:compositional-indexed-equation-requests` and `product/mathematical-analysis-model:ideal-equation-dependency-work` with the first Implementing/Applied lifecycle events when the Phase 1 runtime makes those claims true.
Edge: Claim prose and the Analysis Model's implemented-slice section must describe the shipped direct-Python equation-system capability without implying that assumptions, scenarios, or the expanded Pi request are already implemented; Remaining ADR operations stay visibly pending.
Post-check: Choreography check: render from the completed Phase 1 tree. Authority checks: require `./awf check` success and verify that both claim origins and the Applied/Remaining partition satisfy the ADR lifecycle. State checks: inspect both generated topic pages, the product-domain page, decision index, and implemented-slice section of `docs/analysis-model.md`. Expected terminal set: the two named claims have this ADR as Origin, their matching Applied event is present, the report-contract operation remains unapplied, and no generated drift, stale indexed-equation exclusion, or premature assumption/scenario/Pi-tool claim remains.

Use the ADR lifecycle workflow to land exactly the two matching claim additions and their generated outputs with the Phase 1 implementation transaction.

### Phase close

Land the safe indexed equation-system parser, symbolic work engine, ideal dependency reuse, public report contracts, compatibility evidence, and first two claim applications as one independently green core transaction.

```commit
feat(formula): add compositional equation work analysis
```

## Phase 2: Add qualified assumptions, scenarios, and AFMM evidence

**Execution mode: subagent-driven.**

Completes: ["qualified-scenario-analysis", "afmm-python-acceptance"]

### Task 2.1: Apply constrained assumptions and directed definitions
Applying: ["adopt-compositional-indexed-equation-analysis:provenance-preserving-system-analysis"]
Paths: ["packages/py-science-formula/src/py_science/formula/", "tests/e2e/test_formula_system_analysis.py", "tests/unit/"]

Start from the green Phase 1 public equation-system analyzer with the input and analysis-model claims applied; specialize exact system work only through explicit mathematical knowledge and prove the direct Python acceptance case. Add safely parsed equality and inequality assumptions plus directed variable definitions without passing strings to SymPy parsing. Reject directed-definition cycles and directly detectable contradictions. Support deterministic algebraic factoring and exact normalized-subexpression replacement sufficient to transform a term such as `K(p) * Sum(n[b], (b, 0, B_leaf - 1))` under `Sum(n[b], (b, 0, B_leaf - 1)) == N`; record the exact relationship used in every derived result. Unsupported matching, proof, ordering, or contradiction cases remain explicit unresolved items instead of invoking an unrestricted solver or silently trusting a transformation.

Use declared integer and sign domains to discharge bounded-sum cardinality facts where supported. Tests must distinguish exact results, assumption-dependent results, rejected direct contradictions, unsupported inference, and unused assumptions, and must prove that assumption and definition strings share the parser and request-wide complexity limits.

### Task 2.2: Evaluate explicit variable scenarios
Applying: ["adopt-compositional-indexed-equation-analysis:compositional-mathematical-requests", "adopt-compositional-indexed-equation-analysis:provenance-preserving-system-analysis"]
Paths: ["packages/py-science-formula/src/py_science/formula/", "tests/e2e/test_formula_system_analysis.py", "tests/unit/"]

Keep intrinsic variable domains separate from scenario treatment. Implement fixed substitution, finite choices, directed definitions, retained asymptotic variables, and interval bounds in strict scenario models. Bound public-Python assumption, scenario, per-scenario treatment, finite-choice, and generated scenario-result populations as part of the request/result policy established in Phase 1. Always preserve the exact general symbolic work. Return concrete or finite-choice work by exact substitution; derive asymptotic classifications only for variables explicitly marked asymptotic and under sufficient declared sign/domain facts; produce conservative interval results only when supported monotonic or endpoint reasoning is proven. An untreated symbol, unsupported multivariate dominance, or unproved interval relationship must prevent a stronger claim and appear in unresolved output.

Cover the same work expression under fixed expansion order, jointly scaling particle count and expansion order, finite parameter choices, derived dimensions, and bounded ranges. Every scenario result lists substitutions, relationships, and qualifications used, and no scenario mutates the general report.

### Task 2.3: Prove the AFMM-like direct Python acceptance case
Applying: ["adopt-compositional-indexed-equation-analysis:ideal-equation-dependency-semantics", "adopt-compositional-indexed-equation-analysis:mathematical-aggregate-work-semantics", "adopt-compositional-indexed-equation-analysis:explicit-function-cost-knowledge", "adopt-compositional-indexed-equation-analysis:provenance-preserving-system-analysis"]
Paths: ["tests/e2e/test_formula_system_analysis.py", "packages/py-science-formula/README.md"]

Add one readable end-to-end request containing component-indexed particle displacement mathematics, leaf multipole construction, and a translation equation that references `M[neighbor[b, c], k]` rather than treating an interaction ordinal as a box. Declare particle, component, box, coefficient, occupancy, and interaction domains. Exercise all three knowledge paths deterministically: one generic function has a mathematical definition, `basis` has a scalar declared work expression, and a distinct opaque translation function has neither definition nor work so its cost remains unresolved. Include `Sum(n[b], (b, 0, B_leaf - 1)) == N` and scenarios where `N`, `p`, or both scale.

Assert normalized SymPy and LaTeX readings equation by equation, local and total symbolic work, dependency order, once-per-output-domain construction of `M`, repeated downstream reuse, primitive invocation totals, assumption provenance, fixed and asymptotic scenario differences, and unresolved-cost behavior. The fixture demonstrates structural and complexity analysis only; its names are representative and make no physical-correctness claim. Add a compact direct-Python example to the package README matching the tested public schema.

### Task 2.4: Apply the qualified report claim and current analysis model
Kind: batch
Applying: ["adopt-compositional-indexed-equation-analysis:provenance-preserving-system-analysis"]
Paths: ["docs/decisions/adopt-compositional-indexed-equation-analysis.md", ".awf/topics/parts/product/analysis-report-contract/current-state.md", "docs/topics/product/analysis-report-contract.md", "docs/domains/product.md", "docs/decisions/INDEX.md", "docs/analysis-model.md", ".awf/awf.lock"]
Representative: Apply `product/analysis-report-contract:provenance-preserving-system-work` when the assumption, scenario, AFMM, uncertainty, and provenance evidence is green; update the implemented-slice section of the Analysis Model without rewriting its broader future contract.
Edge: This is the final explicit Applied batch, but the ADR remains Implementing until implementation assurance and effort integration settle; documentation must distinguish the direct Python capability from the not-yet-expanded Pi tool.
Post-check: Choreography check: render from the completed Phase 2 tree. Authority checks: require `./awf check` success and validate that all declared operations are Applied while the ADR remains Implementing. State checks: inspect the report-contract topic, product-domain page, decision index, and implemented-slice boundaries in `docs/analysis-model.md`. Expected terminal set: provenance and unresolved-result rules match runtime evidence, Pi exposure is still described as pending, and no generated drift remains.

Use the ADR lifecycle workflow to land the final claim addition and its generated outputs with the Phase 2 implementation transaction.

### Phase close

Land constrained relationship reasoning, explicit scenario treatments, the direct-Python AFMM acceptance fixture, package example, and final claim application as one independently green transaction.

```commit
feat(formula): analyze qualified AFMM scenarios
```

## Phase 3: Expose equation-system analysis through Pi

**Execution mode: subagent-driven.**

Completes: ["bounded-pi-transport", "afmm-pi-acceptance", "current-project-documentation"]

### Task 3.1: Version and bound the private full-request adapter
Applying: ["adopt-compositional-indexed-equation-analysis:compositional-mathematical-requests", "adopt-compositional-indexed-equation-analysis:provenance-preserving-system-analysis"]
Context: ["0002:aggregate-pi-integration", "0002:eager-fail-closed-provisioning"]
Paths: ["packages/pi-science/bridge/formula_adapter.py", "packages/pi-science/src/bridge.ts", "packages/pi-science/tests/adapter.test.ts", "packages/pi-science/tests/bridge.test.ts"]

Start from the green Phase 2 Python request/result contract and AFMM fixture; translate that complete contract through the private bounded adapter and agent-facing tool without moving analysis policy into TypeScript. Advance the private protocol version for the expanded request/result contract. Let strict Python public models validate the decoded request after the adapter enforces exact envelope shape and a documented whole-envelope byte bound. Add bounded policies for equation count, metadata collection sizes, aggregate mathematical nodes, and serialized output so many individually valid fields cannot exhaust the subprocess or overflow Pi; preserve actionable public input-size errors while keeping internal structural exhaustion generic.

Update TypeScript request types and exact response validation for per-equation/system reports, symbolic renderings, scenarios, qualifications, and structured failures. Preserve timeout, cancellation, process-tree cleanup, stderr sanitization, malformed-output handling, health checks, and fail-closed protocol mismatch behavior. Tests cover old-version rejection, extra keys, oversized aggregate requests, oversized output, malformed rich results, and a real-adapter system round trip.

### Task 3.2: Register the complete strict Pi request schema
Applying: ["adopt-compositional-indexed-equation-analysis:compositional-mathematical-requests"]
Context: ["0002:aggregate-pi-integration"]
Paths: ["packages/pi-science/src/index.ts", "packages/pi-science/src/bridge.ts", "packages/pi-science/tests/start.test.ts", "packages/pi-science/tests/bridge.test.ts"]

Replace the expression-only tool parameters with a strict TypeBox schema for exactly one expression or a nonempty named-equation system plus relevant variables, domains, function definitions, primitive work, assumptions, and scenarios. Keep `syntax: sympy` injected by the Pi integration rather than advertising unsupported LaTeX input. Reject surplus fields and structurally invalid unions before subprocess launch while leaving mathematical validation and analysis to Python.

Retain eager readiness gating: `analyze_formula` and its product skill appear only together after successful provisioning, while `/pi-science-doctor` remains available on failure. Tool results expose the validated Python report unchanged in `details` and deterministic JSON text in content.

### Task 3.3: Prove AFMM analysis across the real Pi boundary
Applying: ["adopt-compositional-indexed-equation-analysis:provenance-preserving-system-analysis"]
Context: ["0002:aggregate-pi-integration"]
Paths: ["packages/pi-science/tests/adapter.test.ts", "packages/pi-science/tests/bridge.test.ts", "packages/pi-science/tests/start.test.ts", "packages/pi-science/tests/package.test.ts"]

Round-trip a compact form of the Phase 2 AFMM request through the actual Python adapter and through the registered tool execute callback. Assert normalized equations, dependency reuse, symbolic system work, assumption provenance, scenario qualification, and unresolved primitive cost survive JSON translation exactly. Keep separate regressions for request validation failures, analysis failures, response overflow, timeout, cancellation, and unavailable-backend surface withholding. Verify the packed Pi package still contains the adapter and product skill and production-installs without reaching into the repository checkout.

### Task 3.4: Correct Pi-facing guidance and current-state documentation
Kind: batch
Applying: ["adopt-compositional-indexed-equation-analysis:provenance-preserving-system-analysis"]
Context: ["0001:symbolic-analysis-product-boundary", "0002:aggregate-pi-integration"]
Paths: ["packages/pi-science/skills/formula-analysis/SKILL.md", ".awf/parts/agents-doc/identity.md", "glob:.awf/docs/parts/architecture/*.md", "glob:.awf/docs/parts/testing/*.md", ".awf/docs/parts/debugging/surfaces.md", "docs/analysis-model.md", "docs/architecture.md", "docs/testing.md", "docs/debugging.md", "AGENTS.md", "CLAUDE.md", "glob:.claude/**", "glob:.pi/**", ".awf/awf.lock"]
Representative: Replace expression-only Pi skill and current-state claims with the newly shipped strict system request, bounded bridge, result surfaces, and AFMM integration evidence, then regenerate consumers.
Edge: Make only the minimum corrections required for Phase 3 currency; extended formulation examples remain Phase 4. Preserve LaTeX input, physical validation, source inference, empirical timing, hardware modeling, and code generation as exclusions.
Post-check: Choreography checks: capture the managed-output population and hashes, render, and read every changed target. Authority check: require `./awf check` success. State checks: run the complete project gate and semantically inspect the skill, identity, architecture, testing, debugging, agent-guide, and implemented-slice prose. Expected terminal set: no expression-only Pi claims, every advertised Pi surface has Phase 3 evidence, exclusions remain accurate, and no generated drift remains.

Update the authored awf sources, preserved Analysis Model section, product skill, and generated consumers in the same Phase 3 transaction that invalidates their prior claims.

### Phase close

Land the expanded private protocol, strict Pi schema, readiness-preserving registration, real AFMM bridge evidence, and minimally current Pi documentation as one independently green integration transaction.

```commit
feat(pi): expose formula system analysis
```

## Phase 4: Publish extended formulation guidance

**Execution mode: inline.**

Completes: ["agent-formulation-guidance"]

### Task 4.1: Teach agents to formulate and inspect equation systems
Applying: ["adopt-compositional-indexed-equation-analysis:compositional-mathematical-requests", "adopt-compositional-indexed-equation-analysis:ideal-equation-dependency-semantics", "adopt-compositional-indexed-equation-analysis:provenance-preserving-system-analysis"]
Paths: ["packages/pi-science/skills/formula-analysis/SKILL.md", "packages/py-science-formula/README.md", "README.md"]

Start from the complete green and currently documented Python and Pi AFMM path from Phase 3; this documentation-only phase adds fuller guidance without repairing deferred stale state. Expand the minimally current Phase 3 guidance with concise examples for choosing one expression versus named equations, declaring every free output domain and external variable nature, representing vectors through indexed scalar algebra, separating function definitions from scalar opaque work, supplying assumptions and scenarios, and inspecting normalized interpretation, provenance, qualifications, and unresolved quantities before relying on complexity. State the hard formula-only input boundary and distinguish mathematical work from physical validation, source inference, profiling, or runtime prediction. Include one compact tool request and one direct-Python request that match tested schemas rather than copying the entire AFMM fixture. Run the complete project gate and read all three rendered Markdown files to confirm examples match the tested contract and preserve every deferred boundary.

### Phase close

Land the extended agent guidance and package examples as one independently green documentation transaction.

```commit
docs(formula): document equation system analysis
```

## Definition of done

- `dod: safe-mathematical-systems` Strict direct-Python requests safely parse one expression or named indexed equations with bounded sums, generic functions, local domains, and request-wide complexity enforcement; arbitrary Python and SymPy string evaluation remain impossible.
- `dod: ideal-symbolic-work` Reports preserve submitted counts, derive symbolic aggregate work with nonnegative bounded-sum semantics, charge every named equation once per output-domain point, reuse dependencies downstream, and leave unnamed repetition in the baseline.
- `dod: qualified-scenario-analysis` Explicit assumptions, directed definitions, variable domains, and scenarios produce provenance-bearing exact, fixed, choice, bounded, asymptotic, or unresolved results without guessed scaling variables or unrestricted theorem proving.
- `dod: afmm-python-acceptance` A direct Python request representing component-indexed particle mathematics, leaf multipoles, interaction-neighbor translation, and parameter scenarios returns inspectable per-equation and total work with dependency reuse and explicit unknowns.
- `dod: bounded-pi-transport` The private versioned adapter and strict Pi schema carry the complete request and report under whole-request and bounded-output policies while preserving readiness gating, cancellation, timeout, cleanup, and malformed-protocol diagnostics.
- `dod: afmm-pi-acceptance` The registered `analyze_formula` tool round-trips a representative AFMM system and returns the same normalized equations, work, reuse, provenance, scenario qualifications, and unresolved quantities as the public Python API.
- `dod: current-project-documentation` At the Phase 3 capability boundary, the product skill and generated current-state documentation describe the implemented Python and Pi system surfaces, verification, and exclusions without stale expression-only claims.
- `dod: agent-formulation-guidance` Package guidance accurately teaches formula-only system formulation without presenting future LaTeX input, physical validation, source inference, empirical timing, or code generation as current.

## Notes

Inline owners immediately correct stale instructions and record reasoned deviations here. Delegated owners may report rather than edit; the parent supplies the report to phase review and reconciles it with findings in one focused post-review settlement commit before checkpointing or later execution. Record deviations, spike answers, follow-ups, and findings surfaced during implementation.

- Plan review: moved the minimum invalidated Pi skill and generated current-state documentation into Phase 3 so the expanded tool lands independently current; Phase 4 now adds only extended formulation guidance.
- Plan review: made the AFMM fixture exercise one mathematically defined function, one declared-work opaque function, and one unresolved opaque function so all approved knowledge paths have deterministic acceptance evidence.
- Phase 1 settlement: the phase-closing commit exposed unsafe and incomplete parser, request-bound, work-analysis, index-validation, and report behavior. The review settlement replaced those internals within the approved IR and contract boundary, kept the Pi request expression-only, expanded its response validator for the richer optional report, exported every public Phase 1 model, and added exact regressions for sum cardinality, function knowledge, reuse, local indices, validation, and advisory extraction. This authority-preserving completion adds the private Pi bridge paths required by Task 1.3 compatibility; `./scripts/check` is green.
- Phase 1 renewed review: rejected dependent output domains rather than silently multiplying free-index cardinalities; made local output indices integral in their lexical scope; enforced generic arity and iterator shadowing request-wide; reserved `Max` for analyzer-generated nonnegative cardinalities; and added pre-SymPy structural/render budgets plus malformed-rich-response and exhaustion regressions. These reasoned corrections preserve the ADR's strict local-domain and bounded-result rules without introducing ordered dependent domains or expanding the Pi request, and the full gate remains green.
- Phase 1 verify pass: mechanically closed residual formula-bearing-bound and budget paths by rejecting named-result references in output domains, validating bound-call arities, bounding primitive substitution and definition-expansion depth, and making the render estimate conservative for iterator names and signed integers. Focused regressions cover each residual; no approved boundary changed.
- Phase 2 implementation: added the omitted private TypeScript response-validator plus bridge and readiness fixture paths because frozen Python Phase 2 result defaults are serialized even for the still-expression-only Pi request. The compatibility-only change accepts empty scenario output and the new provenance fields without expanding the Pi request schema or protocol, as permitted by Task 2.2's explicit compatibility boundary; focused bridge tests and the full gate verify fail-closed behavior remains intact.
- Phase 2 review settlement: preserved the Applied provenance-report claim by rejecting decidably false relationships and domain-invalid directed definitions before analysis, making equality replacement literal-safe and strictly canonical, qualifying unproved definition-domain preservation, emitting finite-choice work only for actual choices, and claiming scenario-definition provenance only when analyzed work changes. Focused regressions cover both equality spellings, ambiguous/unused knowledge, integer-empty assumptions, global and scenario domains, all non-choice scenario forms, and used versus unused scenario definitions. No approved boundary changed and there were no deviations.
- Phase 2 renewed-review residuals: generalized contradiction bounds to exact rational arithmetic and validates definition domains after topological dependency plus scenario fixed/choice substitution. This closes arithmetic-constant integer intervals and prevents a declared positive variable from specializing through another definition or scenario value to a negative result; unresolved qualifications remain only for genuinely unproved preservation. No approved boundary changed.
