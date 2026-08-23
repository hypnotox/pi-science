---
format: current-state-v4
slug: separate-formula-responsibilities-behind-compatibility-facades
status: Implementing
date: 2026-08-23
---
# ADR-separate-formula-responsibilities-behind-compatibility-facades: Separate Formula Responsibilities Behind Compatibility Facades

## Context

The formula implementation concentrates unrelated responsibilities in four central files. At the
reviewed baseline, `models.py` contains 2,233 lines of interleaved request, evidence, result, and
report contracts; `optimization.py` contains 3,009 lines of candidate generation, search, proof,
objective, and publication policy; `service.py` contains 3,145 lines of retained analysis and
request orchestration; and `bridge.ts` contains 4,469 lines of protocol types, validation,
correlation, and subprocess-client behavior.

The concentration also obscures dependency direction. Service imports optimizer-private occurrence
diagnostics, while optimizer replay and candidate comparison import service-private retained
analysis. The resulting service-to-optimizer-to-service cycle is deferred through local imports
rather than removed. In Pi, provisioning and integration consume protocol utilities through the same
bridge module that owns the client state machine. Contract extraction additionally risks changing
Pydantic class identity, validator order, schema structure, or the broad package-root export surface.

The refactor must establish cohesive owners without changing the shipped analysis product. Python
continues to own mathematical policy and Pi continues to own strict bounded transport, correlation,
and presentation. Protocol v16, generated schema bytes, public imports, candidate and plan identities,
search population and ordering, proof and objective policy, and transport behavior form the
compatibility baseline. Declarative goals and specification/plan IR remain later decisions.

## Decision

1. `decision: assign-single-responsibility-owners` Formula contracts, neutral retained-computation and structural-occurrence analysis, optimizer policy, service orchestration, and Pi transport concerns each have one internal owner. Retained-computation and structural-occurrence facts live below their consumers rather than being recreated by those consumers.
2. `decision: direct-python-dependencies` Service orchestration may invoke optimizer policy; service, optimizer, and comparison consume neutral retained analysis; and optimizer policy never depends on service orchestration. Optimizer-owned modules own candidate generation, search, objectives, replay, and verification. Service-owned modules own request orchestration, queries, scenarios, dominance dispatch, and result bounding.
3. `decision: preserve-python-compatibility-surfaces` Python contract classes are defined once. `models.py` and the package root remain forwarding compatibility surfaces that expose the same class objects rather than subclasses or duplicate definitions.
4. `decision: direct-pi-dependencies` Pi protocol, validation and correlation, client invocation, diagnostics, and presentation have separate internal owners behind an outward-only `bridge.ts` compatibility barrel. Internal modules consume the owning modules directly, mathematical policy remains in Python, and `process.ts` retains subprocess-tree lifecycle mechanisms.
5. `decision: preserve-foundation-compatibility` The structural foundation preserves protocol v16, generated schema bytes, public exports, candidate and plan identities, search, proof, and objective behavior, and Pi transport semantics.

## State changes

- add `product/formula-component-boundaries:responsibility-directed-components`

## Consequences

The implementation gains acyclic, testable seams for later goal, plan, resource, and proof work
without making those future contracts part of this decision. Contract and transport changes can be
reviewed at their actual owners, while compatibility facades isolate existing callers from internal
movement.

The extraction is constrained work rather than a cleanup license. Moving a definition can alter
Pydantic schema, validation, import initialization, or TypeScript correlation even when its body is
unchanged. Each coherent move therefore preserves exact objects and behavior. Compatibility facades
add forwarding indirection, but they avoid a simultaneous public migration and may remain as stable
boundaries.

## Alternatives Considered

| Alternative | Why not chosen |
|---|---|
| Retain the central modules and deferred local-import cycle | It preserves concentrated responsibilities, private coupling, and circular ownership. |
| Remove the central modules in a big-bang rename | It couples internal cleanup to a public import and transport migration. |
| Split files while retaining current private cross-imports | It redistributes the monolith without establishing ownership or removing cycles. |
| Duplicate retained analysis or occurrence traversal for each consumer | It creates competing sources of mathematical and scope policy. |

## Status history

- 2026-08-23: Proposed
- 2026-08-23: Implementing; content-sha256: 020fb52fda4e42d856cf6a4f584c0710d1c03f662d5f9be93dbb5b0ca2033f2e
- 2026-08-23: Applied; operations: add `product/formula-component-boundaries:responsibility-directed-components`
