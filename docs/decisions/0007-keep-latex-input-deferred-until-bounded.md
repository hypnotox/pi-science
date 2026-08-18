---
format: current-state-v4
slug: keep-latex-input-deferred-until-bounded
status: Proposed
date: 2026-08-18
---
# ADR-0007: Keep LaTeX input deferred until bounded

## Context

The shipped formula API accepts safely parsed restricted-SymPy input only. The mathematical input current state still says requests accept LaTeX or restricted SymPy, while its bounded-query claim, the implemented analysis contract, the product skill, and the roadmap identify restricted LaTeX as future work.

Leaving the older claim active makes unsupported input appear available and weakens the rule that a mathematical frontend needs an explicit safe grammar, bounded semantics, qualification behavior, tests, and documentation before callers may rely on it.

## Decision

1. `decision: expose-only-bounded-mathematical-frontends` Describe current requests as restricted-SymPy-only. Keep restricted LaTeX input deferred until it has an explicit safe and bounded contract and implementation.

## State changes

- update `product/mathematical-input-contract:safe-familiar-inputs`

## Consequences

Current authority matches the shipped request contract and no longer routes agents toward unsupported LaTeX input. Normalized LaTeX output remains available and is distinct from accepting LaTeX as input.

A future LaTeX frontend requires a successor decision and complete bounded product contract before it becomes current guidance.

## Alternatives Considered

| Alternative | Why not chosen |
|---|---|
| Retain LaTeX as a current frontend claim | The implementation does not accept it, so the claim would remain false. |
| Accept arbitrary LaTeX through a general parser | Ambiguity and parser behavior would define an unsafe, unbounded public contract. |
| Remove LaTeX from future direction | A safe restricted frontend remains a valid roadmap option. |

## Status history

- 2026-08-18: Proposed
