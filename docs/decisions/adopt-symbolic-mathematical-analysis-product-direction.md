---
format: current-state-v4
slug: adopt-symbolic-mathematical-analysis-product-direction
status: Implemented
date: 2026-08-16
---
# ADR-adopt-symbolic-mathematical-analysis-product-direction: Adopt symbolic mathematical analysis product direction

## Context

Coding agents can propose plausible algorithms without a deterministic way to inspect their mathematical structure, derive symbolic cost, or understand parameter sensitivity before implementation. The project's previous evidence-workbench direction centered experiment execution, benchmarking, profiling, and verdicts, which does not address that reasoning seam.

Agents already formulate mathematics in LaTeX and SymPy conventions. The product must analyze those formulations without inferring them from source code, executing implementations, or silently inventing missing assumptions and costs.

## Decision

1. `decision: symbolic-analysis-product-boundary` pi-science is an agent-facing deterministic mathematical analysis tool. It accepts agent-formulated symbolic or formula-oriented computations and reports their mathematical cost, structure, scaling, bounds, improvement opportunities, and unresolved quantities. Dataset statistics, source-to-model inference, experiment orchestration, implementation benchmarking, and physical validation are outside the core product boundary. Separate future profiler integrations may consume related outputs, and future formula lowering may produce implementation skeletons without turning the analyzer into an implementation-testing or optimized-code-generation system.
2. `decision: familiar-safe-mathematical-inputs` The agent-facing inputs are familiar LaTeX and a safely parsed restricted subset of actual SymPy conventions. A request may supply relevant metadata for domains, assumptions, scenarios, and opaque primitive costs; omitted knowledge remains explicit and unresolved. Submitted syntax is data and must not permit arbitrary Python evaluation.
3. `decision: shared-mathematical-model` Both frontends normalize into one internal mathematical model. Parsing, cost semantics, and analysis policy remain separable from SymPy-specific representation so that one backend does not define the public protocol or inseparably couple every analysis concern.
4. `decision: inspectable-qualified-analysis` Analysis reports include the normalized interpretation actually analyzed and distinguish exact results, assumption-dependent results, conservative bounds, conditional rewrites, and unresolved quantities. The analyzer must not silently fix a scaling variable, invent an unknown cost, or present sampling as a mathematical bound.

## State changes

- add `product/product-boundary:symbolic-analysis-only`
- add `product/mathematical-input-contract:safe-familiar-inputs`
- add `product/mathematical-analysis-model:shared-backend-independent-model`
- add `product/analysis-report-contract:qualified-inspectable-results`

## Consequences

Agents gain a deterministic feedback loop between mathematical planning and implementation. A common normalized representation can support operation counting, symbolic complexity, scenarios, dependency and reuse analysis, candidate comparison, and qualified rewrite suggestions across both input formats.

The analyzer depends on agents making domains, assumptions, and opaque costs explicit. Incomplete submissions therefore produce symbolic unknowns or qualified bounds rather than fabricated precision. Restricting the frontends reduces language coverage but creates a safe and inspectable protocol.

The former experiment and evidence workbench direction is retired rather than retained as a parallel product surface. Adoption requires replacing the conflicting vision, evidence-model, architecture, roadmap, glossary, and supporting product documentation. No runtime or stored-data migration is required because the repository contains no scientific runtime or stable public API.

## Alternatives Considered

| Alternative | Why not chosen |
|---|---|
| Retain the scientific experiment and evidence workbench | It evaluates implementations and empirical claims rather than strengthening the agent's mathematical formulation before code exists. |
| Infer a mathematical model from source or an algorithm description | Formulation remains the agent's responsibility; inference would add ambiguity outside the intended reasoning seam. |
| Introduce a bespoke mathematical language | LaTeX and SymPy conventions are already familiar to agents and avoid an unnecessary public language. |
| Support only LaTeX or only SymPy | The frontends serve complementary readable and unambiguous submission workflows while sharing one analysis model. |
| Accept unrestricted LaTeX or Python/SymPy syntax | Unrestricted syntax expands ambiguity, arbitrary-evaluation risk, and MVP scope. |

## Status history

- 2026-08-16: Proposed
- 2026-08-16: Implemented; content-sha256: b7b6249f18d5344219a99447143077d4c695855184dbd211e79f86475de42245
