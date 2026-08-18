---
format: current-state-v4
slug: keep-rewrite-guidance-deferred-until-implemented
status: Implemented
date: 2026-08-18
---
# ADR-0008: Keep rewrite guidance deferred until implemented

## Context

The shipped analyzer reports submitted work, normalized interpretation, named dependencies and ideal reuse, repeated-expression extraction diagnostics, scenario specializations, and qualified bounded mathematical queries. It does not yet suggest local rewrites, estimate invariant-hoisting effects, compare candidate formulations, or claim that one formulation improves another.

Two active claims inherited from the original product direction nevertheless list improvement opportunities and conditional rewrites as current report behavior. The vision now describes shipped MVP behavior accurately, and the roadmap retains rewrite, hoisting-effect, comparison, crossover, and dominance work as uncommitted direction.

## Decision

1. `decision: expose-rewrite-guidance-only-when-implemented` Preserve qualified repeated-expression extraction diagnostics, but describe current reports without local-rewrite, hoisting-effect, candidate-comparison, or improvement-ranking guarantees. Keep those unimplemented capabilities as roadmap work.

## State changes

- update `product/product-boundary:symbolic-analysis-only`
- update `product/analysis-report-contract:qualified-inspectable-results`

## Consequences

Current authority no longer promises results the analyzer does not produce. Agents continue to receive inspectable qualified analysis and may reason about changes themselves without treating absent rewrite guidance as a shipped feature.

Rewrite, hoisting-effect, candidate-comparison, and improvement-ranking support remain roadmap work rather than current guidance.

## Alternatives Considered

| Alternative | Why not chosen |
|---|---|
| Keep the claims aspirational | Current-state documentation must describe available behavior rather than roadmap intent. |
| Implement bounded rewrite or comparison support now | That is separate product work; this decision corrects current authority while retaining implementation as uncommitted roadmap direction. |
| Remove rewrite and comparison from the roadmap | They remain valid future product directions once bounded contracts exist. |

## Status history

- 2026-08-18: Proposed
- 2026-08-18: Implemented; content-sha256: 930685c1eebd6343307678bec22037b6853c512f3208d9072c695d615a03580b
