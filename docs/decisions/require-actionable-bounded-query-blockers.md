---
format: current-state-v4
slug: require-actionable-bounded-query-blockers
status: Proposed
date: 2026-08-18
---
# ADR-require-actionable-bounded-query-blockers: Require actionable bounded query blockers

## Context

ADR-0004 requires supported query answers to localize unsupported facts and blockers while preserving conservative proof status. It does not establish what a blocker must reveal or how a caller can recover. Generic family refusals therefore satisfy the older conclusion contract while leaving agents unable to distinguish unsupported syntax, a measured resource limit, an ambiguous axis, or a missing proof precondition.

The public query result already carries blockers as strings. Adding public diagnostic codes or transport fields would widen the result schema without being necessary for safe recovery. Numeric details are trustworthy only when bounded inspection actually measured them; backend refusal alone cannot justify an observed value.

ADR-0004 is Implemented, so its current-state claims are terminal history. Strengthening those claims requires this successor decision rather than a correction to the frozen record.

## Decision

1. `decision: actionable-bounded-query-blockers` Within the existing query-answer blocker contract, an unresolved supported query identifies the failed supported family, structural or resource bound, ambiguous axis, or missing precondition and gives a safe reformulation direction when one exists. A blocker includes observed and configured values only when bounded inspection measured them. Recovery guidance neither certifies equivalence nor promises broader evaluator support, and unsupported questions remain localized `unresolved` or `inapplicable` answers rather than request failures.

## State changes

- update `product/mathematical-analysis-model:assumption-aware-query-reasoning`
- update `product/analysis-report-contract:qualified-query-conclusions`

## Consequences

Agents can distinguish why a bounded evaluator refused a query and can choose a supported next action without treating the hint as proof. The public request and result schemas remain unchanged, and categorical backend refusals need not invent numeric details.

Diagnostic wording becomes part of inspectable product behavior even though exact prose remains internal policy. New query families and refusal modes must preserve conservative conclusions, bounded evidence, and non-promissory recovery guidance.

## Alternatives Considered

| Alternative | Why not chosen |
|---|---|
| Keep one generic unsupported-family blocker | It does not tell an agent which bounded reformulation is relevant. |
| Add public diagnostic codes and fields | The existing blocker contract can carry the required guidance without widening the schema. |
| Change ADR-0004 and its claims in place | Implemented ADR content and terminal claim history are frozen. |

## Status history

- 2026-08-18: Proposed
