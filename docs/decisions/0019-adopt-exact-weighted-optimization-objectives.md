---
format: current-state-v4
slug: adopt-exact-weighted-optimization-objectives
status: Implementing
date: 2026-08-22
---
# ADR-0019: Adopt exact weighted optimization objectives

## Context

ADR-0017 adopted one abstract unit-work objective for bounded optimization: Python sums retained additions, subtractions, multiplications, divisions, powers, and known opaque primitive work, then publishes only candidates with independently proved positive whole-computation savings. ADR-adopt-stateless-replayable-formula-optimization-plans made those candidates complete, stateless computations and exposed the same Python-owned optimizer through ordinary advice and a direct operation. The objective itself remains implicit and fixed.

One fixed profile cannot express an agent's exact symbolic preference between the five already-retained operation dimensions. Existing candidates can differ across those dimensions: for `(x + 1)*(x + 1) + (y*z + y*w)`, unit work ranks factoring `y*z + y*w` ahead of extracting the repeated `x + 1`, while an exact power weight of `5/2` reverses that order and leaves both improvements positive. The retained dimensional tally can support that choice without adding runtime, hardware, storage, scheduling, or numerical policy.

The objective cannot be introduced by changing aggregate work globally. Ordinary reports, scenarios, candidate comparison, dominance, and optimization all currently consume the same unit total, and those non-optimization surfaces are outside this decision. Known primitive costs also contribute opaque work and can change when reuse or hoisting reduces evaluation multiplicity, so omitting opaque work would fail to reproduce the current all-one baseline. Unknown costs and unresolved direct work must remain blockers rather than acquiring invented weights.

Alternative profiles also expose two existing ambiguities. Optimization fields named as work evidence would silently change meaning if they held a selected weighted value, and deterministic fallback ordering between symbolically incomparable savings is not currently distinguished structurally from proved superiority. Stateless callers need explicit objective provenance and qualified ordering, while complete candidates must remain independent of the analysis policy that selected them.

## Decision

1. `decision: exact-optimization-objective-profiles` Optimization will accept an exact-symbolic objective profile. Omission selects the named `unit_work_v1` profile, preserving the existing abstract unit-work objective. The initial custom profile is named `weighted_operations_v1`; callers supply all five retained addition, subtraction, multiplication, division, and power weights through the existing bounded exact-scalar request grammar, and accepted values are canonicalized as exact rationals for objective provenance.
2. `decision: positive-weighted-operation-objective` Every custom weight is strictly positive. The custom objective is known opaque primitive work with fixed coefficient one plus the sum, across the five retained dimensions, of each operation count multiplied by its selected weight. Unknown costs, unresolved direct work, and non-finite work retain their existing blocking semantics. All-one custom weights therefore reproduce the default objective without making opaque work or an operation dimension free.
3. `decision: optimization-only-objective-selection` Objective selection is analysis policy owned only by ordinary optimization configuration and the direct optimize operation. It does not enter complete replayable candidates. Ordinary unit-work reports, scenarios, general candidate comparison, and dominance retain their existing semantics.
4. `decision: explicit-objective-evidence` Candidate eligibility and plan ordering use the selected objective. Public optimization results replace the ambiguous work-before, work-after, and savings evidence with explicit selected-objective before, after, and savings evidence; the default profile yields the existing values. A candidate still publishes only when its complete replay proves exact-symbolic equivalence and strictly positive selected-objective savings.
5. `decision: objective-provenance-with-stable-candidate-identity` Every plan carries separate canonical objective provenance: the default profile identity, or the custom profile identity and all five canonical weights. The plan's existing complete-candidate identity remains independent of objective selection, so the same transformed computation retains the same identity across profiles while its acceptance and ordering remain reproducible.
6. `decision: qualified-deterministic-objective-ordering` A proved exact-symbolic savings-superiority relation determines the affected relative plan order. When retained plans have equal or incomparable savings, or bounded reasoning cannot prove superiority, their order remains deterministic but is structurally qualified as a non-superiority tie-break. Presentation must preserve that distinction and must not turn deterministic position into a superiority claim.
7. `decision: backend-independent-v14-objective-transport` Python continues to own objective construction, candidate verification, eligibility, ordering, and qualification. Pi will strictly validate, transport, and present objective controls, provenance, evidence, and ordering qualification without recomputing policy. Their exact public request and result shapes migrate atomically to protocol v14.
8. `decision: exact-objective-v1-boundary` This decision does not add objective controls to comparison or dominance, unchanged-opaque-cost cancellation, workload roots, scenario regions, Pareto reporting, storage, critical path, temporary count, code size, empirical costs, runtime or hardware prediction, composed search, numerical optimization, or global optimality. Existing resource bounds, common candidate verification, exact-symbolic finite-precision qualification, passive/direct policy sharing, and failure semantics remain in force.

## State changes

- update `product/product-boundary:symbolic-analysis-only`
- update `product/mathematical-input-contract:bounded-optimization-advice-requests`
- update `product/mathematical-analysis-model:bounded-optimization-transformation`
- update `product/analysis-report-contract:qualified-optimization-advice`

## Consequences

Agents can state an exact symbolic operation preference while retaining today's behavior by default. Because plans identify the profile and canonical weights that accepted and ordered them, passive and direct results remain inspectable and reproducible without embedding policy into the returned computation. The same candidate can be reanalysed ordinarily or selected under another objective without changing its mathematical identity.

A separate objective projection prevents custom weights from changing ordinary unit-work analysis, comparison, dominance, or scenarios. Keeping opaque work at fixed coefficient one preserves known primitive-cost reductions and baseline compatibility, but intentionally does not let callers tune primitive cost relative to operations beyond the primitive costs already declared in formula context. Strictly positive weights keep every retained dimension meaningful and objective totals nonnegative; callers cannot model free or rewarded operations in v1.

Alternative objectives can admit a candidate whose ordinary unit-work delta is not positive. Explicit selected-objective evidence makes that policy visible rather than mislabeling it as unit-work savings. Structured non-superiority qualification makes deterministic output stable without claiming a total mathematical ranking. These additions enlarge strict request and result shapes and require an atomic protocol migration, but Pi remains a transport and presentation boundary rather than a second cost-policy implementation.

The profile is still an abstract symbolic objective, not time, resource use, numerical stability, or global optimization. Bounded generation may miss improvements, and separate accepted plans remain noncomposable unless a later decision adds search semantics.

## Alternatives Considered

| Alternative | Why not chosen |
|---|---|
| Keep only implicit unit work | Agents could not express exact preferences among operation dimensions, and returned plans could not identify the policy that ranked them. |
| Replace the global aggregate-work total with a weighted total | It would silently change ordinary reports, scenarios, comparison, and dominance outside the optimization boundary. |
| Weight only the five operation dimensions and omit opaque work | All-one weights would not reproduce current results, and reuse of known primitive calls could lose its existing benefit. |
| Make opaque work a sixth configurable weight | It broadens v1 beyond the approved five retained operation controls and into a separately deferred cost-policy choice. |
| Allow zero or negative weights | Zero silently makes a retained dimension free; negative values reward added work and undermine nonnegative objective invariants. |
| Keep `work_*` result names for the selected objective | Alternative profiles would silently reinterpret fields understood as unit-work evidence. |
| Publish both unit and selected-objective evidence in every plan | It increases payload and validation complexity without being required to explain selected-objective eligibility; ordinary replay remains available for unit-work analysis. |
| Qualify plan identity by objective | The same complete transformed computation would acquire different mathematical identities solely because analysis policy changed. |
| Use deterministic fallback order without structured qualification | Stable position could still be mistaken for proved objective superiority. |

## Status history

- 2026-08-22: Proposed
- 2026-08-22: Implementing; content-sha256: 75478b0028e071657d552403bc6bc4a0639dfb375922062dadcb1c54d423778a
- 2026-08-22: Applied; operations: update `product/product-boundary:symbolic-analysis-only`, update `product/mathematical-input-contract:bounded-optimization-advice-requests`, update `product/mathematical-analysis-model:bounded-optimization-transformation`, update `product/analysis-report-contract:qualified-optimization-advice`
