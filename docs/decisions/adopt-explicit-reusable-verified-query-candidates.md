---
format: current-state-v4
slug: adopt-explicit-reusable-verified-query-candidates
status: Proposed
date: 2026-08-18
---
# ADR-adopt-explicit-reusable-verified-query-candidates: Adopt explicit reusable verified query candidates

## Context

A closed-form query can produce a bounded, verified derived candidate, but that candidate is informational only: another query cannot select it as the expression to analyze. Callers must therefore copy a rendered candidate into a new request before asking whether it is equivalent to another expression or taking a limit. That breaks the report's provenance chain and makes a proved intermediate result awkward to compose.

ADR-0004 deliberately restricts queries to the submitted expression or one named equation RHS and keeps derived candidates separate from submitted direct work. Reuse must preserve that separation, explicit query selection, conservative qualification, and Python-owned mathematical policy. The current service also evaluates queries sequentially and emits results in request order; arbitrary dependency ordering would introduce graph scheduling and cycle handling without improving the motivating workflow.

A reusable candidate is safe only when its source is unambiguous and verified. A source query can otherwise be unresolved, inapplicable, or yield a shape that the downstream evaluator cannot treat as a single operand. Conditions and assumption provenance must remain inspectable and bounded across the composition rather than being silently dropped, duplicated as proof evidence, or mistaken for direct-work facts.

## Decision

1. `decision: explicit-derived-query-targets` An `equivalence` or `limit` query may explicitly target the single verified candidate of an earlier named `closed_form` query. No other query kind consumes a derived target, and derived candidates never replace the submitted expression, equation RHS, operation counts, direct work, or scenario work.
2. `decision: dependency-earlier-query-reuse` A derived target references only an earlier query in request order. Unknown, forward, or self references, a source that is not a closed-form query, and a derived target on an unsupported consumer are invalid request structure rather than implicit dependencies or fallback behavior.
3. `decision: verified-candidate-applicability` A derived target is usable only when a `proved` or `proved_under_assumptions` source answer carries checked closed-form verification evidence and exactly one candidate. When a structurally valid source runs but does not provide that operand, the dependent query returns `inapplicable` with a blocker naming the source and its conclusion; it never silently analyzes the submitted target instead.
4. `decision: composed-query-qualification` A dependent result identifies its source query and deterministically inherits and deduplicates the source conditions and assumption provenance under public bounds. Source verification evidence remains on the source result rather than being duplicated or represented as an assumption. A qualified source cannot yield an unqualified downstream proof, and qualification overflow fails closed as `unresolved`.
5. `decision: python-owned-derived-target-policy` Python owns derived-target validation, verified-candidate selection, qualification composition, and fail-closed outcomes. Generated schemas and Pi transport carry strict request and result shapes without owning mathematical policy.

## State changes

- update `product/mathematical-input-contract:explicit-mathematical-queries`
- update `product/mathematical-analysis-model:assumption-aware-query-reasoning`
- update `product/analysis-report-contract:qualified-query-conclusions`

## Consequences

Callers can compose a proved closed form directly into a later equivalence or limit query while retaining one bounded, inspectable report. The explicit source name preserves provenance and makes missing operands visible. Sequential dependency rules keep evaluation and output ordering deterministic and avoid a general query scheduler.

The request and result target contracts must distinguish submitted and derived operands. The exact private protocol must advance with the changed wire contract.

Some otherwise meaningful compositions remain intentionally unavailable. Properties and asymptotics cannot consume derived targets under this decision, queries cannot reference later results, and an unresolved source prevents its dependents from running. Callers may still submit an expression directly when they need a workflow outside this bounded composition.

## Alternatives Considered

| Alternative | Why not chosen |
|---|---|
| Implicitly reuse a preceding closed form for later queries | Query behavior would depend on hidden ordering and could silently analyze a different operand. |
| Allow arbitrary forward references and topological scheduling | It adds dependency graphs, cycle diagnostics, and result reordering without serving the motivating sequential workflow. |
| Allow properties and asymptotics to consume derived targets immediately | Their multi-answer and expansion semantics widen the initial composition contract beyond the approved equivalence and limit workflow. |
| Fall back to the submitted target when a candidate is unavailable | The report would conceal that the explicitly selected operand was never produced. |
| Copy source verification evidence into every dependent answer | It duplicates bounded evidence and blurs the distinction between source proof and downstream reasoning. |
| Treat the source query as an assumption | Query provenance is not a mathematical relationship and must not pollute assumption reporting. |

## Status history

- 2026-08-18: Proposed
