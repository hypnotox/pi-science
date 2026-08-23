---
format: current-state-v4
slug: adopt-declarative-optimization-goals-and-explicit-claim-scope
status: Proposed
date: 2026-08-23
---
# ADR-adopt-declarative-optimization-goals-and-explicit-claim-scope: Adopt Declarative Optimization Goals and Explicit Claim Scope

## Context

The optimizer currently mixes optimization intent with ordinary analysis advice. Ordinary requests
default to a bounded suggestion count, while direct optimization exposes output projection,
objective selection, and an internal algorithmic-family opt-in as sibling controls. A caller must
therefore know implementation lanes rather than state the mathematical outcome it wants.
Informational queries remain separate, but optimization has no typed goal, search policy, or proof
policy.

Published plans already replay completely, prove exact-symbolic equivalence, and prove a positive
whole-computation reduction under the selected objective. Their reports do not state this claim in a
single machine-readable contract. `complete` means only that the configured monotonic depth-two
procedure accumulated no exhaustion qualification. Ranking may use deterministic tie-breaking and
adjacent comparison, so neither completion nor first position proves a best candidate or finite,
global, runtime, or numerical optimality.

Several rejection causes are also lost. The search preserves resource exhaustion but silently drops
candidate-local proof and work refusals, while most families return no localized reason when they
produce no proposal. Useful blockers must therefore come only from facts captured during existing
bounded generation and verification. They cannot be reconstructed later by Pi or presented as safe
transformations.

The current request and result shapes are used for spikes rather than as a persisted compatibility
boundary. The next contract can replace them directly, but it must preserve the mathematical trust
boundary: Python owns goal interpretation, search, proof, cost policy, classification, and blockers;
Pi validates, correlates, and presents bounded transport without recomputing those decisions.

## Decision

1. `decision: explicit-goal-operation` Optimization is an explicit operation with separate required contracts for declarative mathematical intent, bounded search policy, verifier policy, and result projection. Ordinary analysis no longer performs passive or default optimization, and informational mathematical queries do not act as optimization goals. The new contract replaces the current optimization request and result shapes without a backward-compatibility layer.
2. `decision: initial-goal-semantics` The initial goal requires exact-symbolic semantics, preserves all submitted expression or system outputs, uses the computation's submitted domains, constraints, and assumptions, and minimizes the selected aggregate abstract-work objective. The objective is either unit work or the existing strictly positive exact operation weighting, including its existing opaque-work semantics. Goal-local domain restrictions, selected-output subsets, hard resource ceilings, additional resources, runtime, numerical behavior, and operational plan representation are excluded.
3. `decision: fixed-bounded-search-and-proof` The initial public search policy is `bounded_goal_v1`: it enables every currently supported exact lane, uses fixed monotonic breadth-first composition to depth two, and reports the actual families, bounds, and completion state without exposing family-selection or depth controls. The required `verifier_backed_v1` policy accepts only independently verified exact-symbolic plans, including plans whose submitted assumptions or derived conditions are reported explicitly.
4. `decision: explicit-truthful-claims` Every published plan reports only `strict_improvement`, together with its objective, exact proof semantics, objective-selected aggregate abstract-work semantics, bounded search scope, and optimizer semantic version. Reports identify selection as `deterministic_ranked_prefix`, classify the observed result as `plans_returned`, `no_applicable_candidate`, or `no_verified_improvement`, and keep search completion separate from output projection. They do not expose best-candidate, finite-space, unrestricted, runtime, or numerical optimality claims.
5. `decision: bounded-actionable-blockers` Optimization may publish bounded, deduplicated blockers only when existing generation or verification work confidently identifies a family, target, stable reason, and required information. The initial reasons cover missing primitive costs, unproved domain or cardinality facts, and localized evaluator limits. Blockers are not candidates, recommendations, or proof; they contain no speculative candidate or raw internal rejection text, require no extra analysis, and remain absent when a useful localized statement is unsafe.
6. `decision: python-policy-pi-transport` Python is the sole owner of goal normalization, search and proof policy, objective comparison, claim and result classification, and blockers. Pi advances atomically to protocol v17 to validate, correlate, and present the Python-owned contract without deriving mathematical policy.

## State changes

- update `product/mathematical-input-contract:bounded-optimization-advice-requests`
- update `product/analysis-report-contract:qualified-optimization-advice`
- update `product/mathematical-analysis-model:bounded-optimization-transformation`
- update `product/product-boundary:symbolic-analysis-only`

## Consequences

Agents state desired mathematical optimization rather than choosing implementation families. Every
plan and empty result becomes inspectable without strengthening the proof currently available.
Removing passive advice also makes ordinary analysis cheaper and keeps optimization intent explicit.

The replacement breaks existing request and result wire shapes and requires one coordinated Python,
schema, adapter, Pi, documentation, and skill migration. It retains exact candidate replay and
mathematical verification as correctness properties, but not serialized compatibility. Fixed depth
and one resource objective keep R2 bounded while leaving configurable depth, operational plans,
resource vectors, and stronger selection claims to later decisions.

Blocker coverage is intentionally incomplete. Capturing only facts already observed avoids changing
search population or budgets and prevents speculative rejection details from becoming public
advice. The result classification describes the work actually observed; an incomplete search still
does not prove candidate absence.

## Alternatives Considered

| Alternative | Why not chosen |
|---|---|
| Add nullable goals beside the existing optimization controls | It creates precedence and normalization rules for a compatibility boundary the product does not need. |
| Retain passive advice and add goals only to direct optimization | It preserves two public optimization modes and keeps ordinary analysis coupled to unstated optimization intent. |
| Expose family selection and configurable depth in the initial search policy | It makes callers choose implementation mechanics and pulls broader-search work forward from its later dependency gate. |
| Report the first plan as best or optimal within the completed search | Current ranking and completion do not prove all relevant pairwise comparisons or a declared exhaustive finite space. |
| Publish every internal proposal rejection as a blocker | Raw rejections are unstable, noisy, potentially speculative, and may misrepresent an unsafe candidate as guidance. |

## Status history

- 2026-08-23: Proposed
