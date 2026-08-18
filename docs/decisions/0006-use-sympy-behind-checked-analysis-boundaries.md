---
format: current-state-v4
slug: use-sympy-behind-checked-analysis-boundaries
status: Implemented
date: 2026-08-18
---
# ADR-0006: Use SymPy behind checked analysis boundaries

## Context

`py-science-formula` uses a project-owned restricted parser and typed expression model so submitted syntax remains data and the public contract does not inherit unrestricted Python or CAS behavior. The project also owns mathematical applicability, resource policy, assumptions and provenance, work and reuse semantics, qualification, and fail-closed outcomes.

The implementation already delegates normalized rendering, rational algebra, polynomial mechanics, factorization, differentiation, closed-form construction and verification, and asymptotic mechanics to bounded SymPy adapters. Current architecture guidance describes SymPy mainly as a renderer, which understates that role and can lead maintainers to recreate algebra that the established backend already supplies. Backend independence is a boundary around public semantics and policy, not a direction to avoid SymPy internally.

## Decision

1. `decision: preserve-project-owned-analysis-policy` Keep the restricted parser, input-interpretation semantics, typed mathematical model, resource gates, assumptions and provenance, work and reuse semantics, supported-query policy, qualification, and fail-closed outcomes authoritative in `py-science-formula`; no unrestricted or unverified CAS result defines public support or constitutes proof.
2. `decision: prefer-checked-sympy-mechanics` Use SymPy as the preferred algebra, rendering, and verification engine behind checked, resource-bounded seams rather than recreating backend mathematics.

## State changes

- update `product/mathematical-analysis-model:shared-backend-independent-model`
- update `product/distribution-model:concern-oriented-analysis-packages`

## Consequences

Maintainers may expand symbolic capability by extending checked SymPy seams while preserving stable project-owned semantics and conservative qualifications. SymPy algorithms remain implementation mechanisms rather than public protocol commitments. Each new family still needs bounded applicability, resource behavior, result qualification, and verification appropriate to its claim.

The project retains adapter and verification code around SymPy and may expose less functionality than SymPy can compute generally. This cost buys predictable resource use, inspectable evidence, and freedom to change backend mechanisms without changing the analysis contract. SymPy upgrades require compatibility, security, algorithm-behavior, and bounded-resource regression validation.

## Alternatives Considered

| Alternative | Why not chosen |
|---|---|
| Treat SymPy only as a renderer | This encourages duplicate algebra and does not describe the implemented backend. |
| Select SymPy or project-owned mechanics independently for each checked family without a preferred backend | This reduces default SymPy coupling and upgrade exposure, but forgoes consistent reuse of mature SymPy mechanics behind replaceable seams and project-owned semantics. |
| Expose unrestricted SymPy behavior as the analysis contract | General CAS behavior does not supply the project's resource, work, provenance, qualification, or stability guarantees. |
| Reimplement supported symbolic mechanics in project-owned code | This duplicates mature backend functionality without improving the public policy boundary. |

## Status history

- 2026-08-18: Proposed
- 2026-08-18: Implemented; content-sha256: a542195bb5d4d927a8e3522d0bcddc6c437cf9109073e9aef31a80be05d404a9
