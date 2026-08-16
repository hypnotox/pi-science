---
format: current-state-v4
slug: separate-reusable-analysis-packages-from-pi-integration
status: Proposed
date: 2026-08-16
---
# ADR-separate-reusable-analysis-packages-from-pi-integration: Separate reusable analysis packages from Pi integration

## Context

The implemented slice is one Python distribution named `pi-science`, with its public imports under
`pi_science`. That identity conflates the reusable mathematical analysis capability with the Pi
integration through which agents will ordinarily discover it. More complex formulation work also
needs a direct Python interface so an agent can derive inputs algorithmically in a spike or probe
instead of guessing values through a sequence of tool calls.

The project is pre-1.0 and has no compatibility obligation to preserve the current import. Adopters
will pin public GitHub source rather than depend on an external package registry. Pi can load a
project-scoped package from such a pin, while Python environments must continue to own their direct
dependencies independently of Pi's managed checkout.

The product boundary remains abstract mathematical analysis. It may calculate metrics about a
formula, but it does not evaluate the formula to produce the value the formula represents, translate
it into an implementation in the current scope, or claim measured application performance.

## Decision

1. `decision: concern-oriented-python-distributions` Reusable mathematical analysis capabilities are packaged as independently importable `py-science-<concern>` Python distributions. The first is `py-science-formula`, imported through `py_science.formula`; its parser, mathematical model, analyzers, and backend adapters remain cohesive internal components rather than separate distributions.
2. `decision: aggregate-pi-integration` `pi-science` remains the aggregate Pi integration package. It exposes compatible analysis capabilities as agent tools and supplies guidance for both ordinary tool use and direct Python spikes or probes, without making Pi the core analysis boundary.
3. `decision: pinned-public-source-distribution` The public GitHub repository is the distribution source. A repository release identifies a compatible snapshot of the Pi integration, its guidance, and the Python distributions; Pi and direct Python environments declare their own pinned source dependencies rather than importing through one another's managed environments.
4. `decision: eager-fail-closed-provisioning` The Pi integration eagerly provisions and validates an isolated Python analysis environment through `uv`. If its prerequisites or analysis environment are unavailable, it warns clearly and withholds analysis tools and availability-dependent guidance while retaining a diagnostic recovery path.
5. `decision: agpl-only-distribution` The repository's Pi and Python packages are distributed under AGPL-3.0-only.
6. `decision: analysis-not-formula-evaluation` Formula analysis may calculate abstract analysis metrics but does not evaluate a submitted formula to produce the value it represents. Formula-to-pseudocode or implementation lowering remains a possible future concern outside the current formula package scope.

## State changes

- add `product/distribution-model:concern-oriented-analysis-packages`
- add `product/distribution-model:pinned-public-source`
- add `product/distribution-model:fail-closed-pi-provisioning`
- add `product/distribution-model:agpl-only`
- update `product/product-boundary:symbolic-analysis-only`

## Consequences

Python spikes and probes gain a normal import boundary, while Pi remains the convenient agent-facing
catalogue. A concern can evolve and be consumed without requiring Pi, and one repository pin keeps
the bridge, guidance, and analysis implementations compatible.

Adopters who use both surfaces repeat the source pin in Pi and Python configuration because each
environment owns its dependencies. The Pi integration also gains an eager startup cost and an
explicit dependency on `uv`, but it fails before advertising unavailable tools rather than producing
partial results later. Supporting multiple distributions adds packaging, compatibility, and
clean-install verification work.

The current Python import is replaced without a compatibility shim. Concrete layouts, subprocess
protocol details, cache placement, and migration order remain implementation choices rather than
permanent architecture.

## Alternatives Considered

| Alternative | Why not chosen |
|---|---|
| Expose the analysis only as Pi tools | Complex probes need ordinary Python composition and should not be forced through tool-call schemas. |
| Keep one Python distribution named `pi-science` | It preserves the integration/core conflation and gives future independent concerns no clear package boundary. |
| Split every parser, model, and backend into its own distribution | Those components evolve together as one formula-analysis concern and would create tightly coupled micro-packages. |
| Publish first through PyPI or npm | Public pinned Git source already serves the expected adopters without additional registry operations. |
| Provision on the first tool call | Lazy failure would advertise capabilities whose prerequisites have not been validated. |

## Status history

- 2026-08-16: Proposed
