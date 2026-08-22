---
format: current-state-v4
slug: preserve-separate-future-optimization-lanes
status: Implemented
date: 2026-08-22
---
# ADR-preserve-separate-future-optimization-lanes: Preserve separate future optimization lanes

## Context

The exact optimizer now returns replayable exact-symbolic plans under explicit abstract objectives. Its reports deliberately do not claim finite-precision behavior, runtime, hardware performance, or empirical validation. The roadmap separately defers richer resource models and profiler or benchmark integration.

Future optimization work could cross several different evidence boundaries. Target-aware abstract costs predict under a declared symbolic model. Approximate numerical transformations require finite-precision semantics and evidence. Profiling observes an implementation in an execution environment. Treating these as one progression would let a symbolic prediction appear empirical, an exact identity appear numerically safe, or a benchmark appear to prove mathematical correctness.

This record settles only their separation. It does not choose detailed cost dimensions, numerical semantics, package or protocol shapes, execution infrastructure, or measurement representations.

## Decision

1. `decision: three-separate-future-lanes` Future target-aware exact symbolic costs, approximate numerical optimization, and empirical profiling will remain three separate architectural lanes.
2. `decision: evidence-boundaries-remain-distinct` Target-aware exact symbolic costs will remain predictions under an explicit abstract model; approximate numerical results will require lane-specific qualification and will not be qualified by exact-symbolic proof; empirical results will remain observations of identified implementations and environments. Evidence from one lane will not stand in for another lane's proof or qualification.
3. `decision: later-lane-specific-authorization` This decision changes no current request, result, protocol, package, optimizer, or execution behavior. Each lane will require its own later decision before implementation.

## State changes

- update `product/product-boundary:symbolic-analysis-only`

## Consequences

The project has a durable guardrail against collapsing symbolic prediction, numerical behavior, and measured performance into one claim. Exact-symbolic optimization keeps its current proof and qualification boundary.

Future work must make lane-specific choices before implementation. Those choices may proceed independently, but integration across lanes must preserve their distinct evidence. Maintaining that separation adds coordination and qualification work when results cross lane boundaries. Detailed representations and mechanisms remain deliberately unsettled.

## Alternatives Considered

| Alternative | Why not chosen |
|---|---|
| Treat the lanes as one general performance optimizer | It would conflate different semantics, evidence, and qualification. |
| Decide detailed models for all three lanes now | The project has not selected implementations or gathered the lane-specific evidence needed for those choices. |
| Leave the separation only as roadmap prose | A future implementation could rediscover and blur the evidence boundary without a durable decision. |

## Status history

- 2026-08-22: Proposed
- 2026-08-22: Implemented; content-sha256: 781520b26fd2e8f88b9da8d913a32e6ef04d6804dedb4cc34fae3470679a3afd
