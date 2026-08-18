---
format: current-state-v4
slug: keep-latex-input-deferred-until-bounded
status: Implemented
date: 2026-08-18
---
# ADR-0007: Keep LaTeX input deferred until bounded

## Context

The shipped formula API accepts safely parsed restricted-SymPy input only. The mathematical input current state still says requests accept LaTeX or restricted SymPy, while its bounded-query claim, the implemented analysis contract, the product skill, and the roadmap identify restricted LaTeX as future work.

Leaving the older claim active makes unsupported input appear available and weakens the rule that a mathematical frontend needs a bounded contract and implementation before callers may rely on it.

## Decision

1. `decision: expose-only-bounded-mathematical-frontends` Describe current requests as restricted-SymPy-only. Keep restricted LaTeX input deferred until it has an explicit safe and bounded contract and implementation.

## State changes

- update `product/mathematical-input-contract:safe-familiar-inputs`

## Consequences

Current authority matches the shipped request contract and no longer routes agents toward unsupported LaTeX input. Normalized LaTeX output remains available and is distinct from accepting LaTeX as input. Callers with LaTeX formulations must translate them into the restricted-SymPy dialect until a bounded LaTeX frontend is implemented.

Restricted LaTeX remains deferred until a bounded contract and implementation exist.

## Alternatives Considered

| Alternative | Why not chosen |
|---|---|
| Retain ADR-0001's complementary LaTeX and SymPy frontend direction as current behavior | The implementation does not accept LaTeX, so the claim would remain false. |
| Implement a bounded restricted-LaTeX frontend now | Designing safe bounded syntax and semantics and delivering the frontend is separate product work; this decision corrects current authority while retaining that work as future direction. |
| Accept arbitrary LaTeX through a general parser | Ambiguity and parser behavior would define an unsafe, unbounded public contract. |
| Remove LaTeX from future direction | A safe restricted frontend remains a valid roadmap option. |

## Status history

- 2026-08-18: Proposed
- 2026-08-18: Implemented; content-sha256: 76ac2e3cf7e82182d4e40083895e641159ba134670fc9bd6d16daec2427e6c5b
