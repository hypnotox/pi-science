---
format: current-state-v4
slug: keep-rewrite-guidance-deferred-until-implemented
status: Proposed
date: 2026-08-18
---
# ADR-0008: Keep rewrite guidance deferred until implemented

## Context

The shipped analyzer reports submitted work, normalized interpretation, named dependencies and ideal reuse, scenario specializations, and qualified bounded mathematical queries. It does not yet suggest local rewrites, compare candidate formulations, identify common-subexpression extraction or invariant-hoisting opportunities, or claim that one formulation improves another.

Two active claims inherited from the original product direction nevertheless list improvement opportunities and conditional rewrites as current report behavior. The vision now describes shipped MVP behavior accurately, and the roadmap retains rewrite, extraction, comparison, crossover, and dominance work as uncommitted direction.

## Decision

1. `decision: expose-rewrite-guidance-only-when-implemented` Describe current reports without rewrite or improvement-opportunity guarantees. Keep local rewrites, extraction suggestions, candidate comparison, and related improvement guidance deferred until they have explicit bounded semantics, qualification rules, tests, and documentation.

## State changes

- update `product/product-boundary:symbolic-analysis-only`
- update `product/analysis-report-contract:qualified-inspectable-results`

## Consequences

Current authority no longer promises results the analyzer does not produce. Agents continue to receive inspectable qualified analysis and may reason about changes themselves without treating absent rewrite guidance as a shipped feature.

Future rewrite or comparison support must define how candidates are generated, qualified, bounded, and separated from submitted work before current guidance advertises it.

## Alternatives Considered

| Alternative | Why not chosen |
|---|---|
| Keep the claims aspirational | Current-state documentation must describe available behavior rather than roadmap intent. |
| Add unbounded SymPy rewrite suggestions immediately | General CAS output would not provide the required resource, qualification, or submitted-work guarantees. |
| Remove rewrite and comparison from the roadmap | They remain valid future product directions once bounded contracts exist. |

## Status history

- 2026-08-18: Proposed
