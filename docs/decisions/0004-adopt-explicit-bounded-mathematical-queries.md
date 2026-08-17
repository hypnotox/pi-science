---
format: current-state-v4
slug: adopt-explicit-bounded-mathematical-queries
status: Implementing
date: 2026-08-17
---
# ADR-0004: Adopt explicit bounded mathematical queries

## Context

The formula analyzer normalizes submitted expressions and equation systems, derives structural and aggregate work, and specializes that work through scenarios. It does not accept an explicit mathematical question about a formula. Agents therefore cannot directly request a domain-aware equivalence check, closed form, property classification, limit, or asymptotic form, even when those results are needed to validate or optimize the represented computation.

ADR-0002 separates abstract formula analysis from evaluation that produces a submitted formula's value. Bounded symbolic questions can cross that line if every derived value is treated as mathematical analysis rather than numerical execution or an inferred implementation. ADR-0001 also requires qualified inspectable results and a shared backend-independent mathematical model, so backend success alone cannot define proof, applicability, or public query semantics.

The query surface must remain explicit and structured. Assumptions are declared knowledge rather than free text, equation names already provide stable analysis units, and scenarios remain explicit specializations rather than an invitation to multiply every question across every parameter regime.

## Decision

1. `decision: explicit-bounded-mathematical-queries` Formula requests may include optional, structured, bounded mathematical queries. A query explicitly names its mathematical question and analyzes either the request expression or one named equation's value as a whole. The analyzer never infers queries from prose or selects arbitrary nested subexpressions. The initial query kinds are exactly `equivalence`, `closed_form`, `properties`, `limit`, and `asymptotic`; later query kinds require a separate decision.
2. `decision: symbolic-query-product-boundary` Query analysis may derive exact symbolic values or forms, including conditional closed forms, limits, and asymptotic forms, without becoming numerical formula evaluation. Derived forms are informational candidates: they neither replace submitted direct-evaluation work nor imply an implementation strategy. General-purpose theorem proving, open-ended derivation, numerical approximation, physical inference, and implementation execution remain outside the analyzer.
3. `decision: assumption-aware-qualified-reasoning` Declared domains and global assumptions actively constrain supported query reasoning. Each answer uses the conservative conclusion set `proved`, `proved_under_assumptions`, `disproved`, `unresolved`, and `inapplicable` as relevant; identifies the assumptions it used; localizes unsupported relevant facts and blockers; and preserves domain, convergence, and applicability conditions. Sampling and an unverified backend transformation are not proof.
4. `decision: exact-query-mathematics` Rational and finite decimal inputs denote exact mathematical values rather than floating-point approximations. Mathematical infinity is represented explicitly for supported query points and bounds and is never treated as finite direct-evaluation work.
5. `decision: explicit-query-contexts` The general formula and each valid scenario are distinct analysis contexts under the same global assumptions. Queries select their context explicitly rather than running implicitly across every scenario. General-context queries form the initial capability; scenario-context queries may extend the same model after the general semantics are established.

## State changes

- update `product/product-boundary:symbolic-analysis-only`
- add `product/mathematical-input-contract:explicit-mathematical-queries`
- add `product/mathematical-analysis-model:assumption-aware-query-reasoning`
- add `product/mathematical-analysis-model:exact-query-values-and-infinity`
- add `product/analysis-report-contract:qualified-query-conclusions`

## Consequences

Agents can ask precise mathematical questions that establish validity, behavior, or candidate equivalence before optimizing a computation. The existing no-query structural and work workflow remains useful, while query results gain stable targets, explicit contexts, conservative qualifications, and local provenance.

The safe internal mathematical model and public contracts must represent the exact values, infinity, semantic operations, conditions, and evidence required by supported query families. Mathematical policy remains in the reusable Python package; Pi and its adapter carry the strict request and result shapes without becoming reasoning authorities. Infinite mathematical operations cannot be misreported as finite direct-evaluation work.

The analyzer must bound query populations, derived expressions, reasoning effort, and serialized results. Some valid questions remain unresolved because conservative public proof policy intentionally rejects unsupported inference. Scenario-specific queries, restricted LaTeX, complex values, dimensions, vector shorthand, and differentiation remain separate extensions rather than implied parts of this decision.

## Alternatives Considered

| Alternative | Why not chosen |
|---|---|
| Infer an analysis goal from free text | Interpretation would be nondeterministic and duplicate the calling agent's responsibility. |
| Always run a standard suite of mathematical analyses | It would spend bounded resources on unrequested work and produce irrelevant or duplicated conclusions. |
| Treat derived forms as replacements for the submitted computation | Mathematical equivalence does not establish that an implementation uses the derived representation or cost model. |
| Expose unrestricted SymPy reasoning | Backend behavior would define public policy and weaken the safe shared-model boundary. |
| Target arbitrary nested subexpressions | Normalization makes nested paths unstable; named equations provide explicit, inspectable analysis units. |
| Run every query across every scenario | Automatic fan-out multiplies bounded work and results while obscuring the caller-selected context. |
| Keep value-oriented symbolic reasoning outside formula analysis | Equivalence, convergence, limits, and behavior are needed to validate and optimize represented computations. |

## Status history

- 2026-08-17: Proposed
- 2026-08-17: Accepted; content-sha256: cd33e6176c48971edd1faaa54db67fcfbcce568e9044ee8a0ea3dfdf9afe99f7
- 2026-08-17: Implementing; content-sha256: cd33e6176c48971edd1faaa54db67fcfbcce568e9044ee8a0ea3dfdf9afe99f7
- 2026-08-17: Applied; operations: update `product/product-boundary:symbolic-analysis-only`, add `product/mathematical-input-contract:explicit-mathematical-queries`, add `product/mathematical-analysis-model:assumption-aware-query-reasoning`, add `product/mathematical-analysis-model:exact-query-values-and-infinity`, add `product/analysis-report-contract:qualified-query-conclusions`
