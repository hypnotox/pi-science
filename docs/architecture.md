# Architecture
## Overview
The repository contains the independently importable `py-science-formula` Python 3.13 distribution and the aggregate `pi-science` Pi package. Formula parsing, expression representation, mathematical policy, and bounded SymPy algebra, rendering, and verification remain transport-free behind `py_science.formula`. Pi carries the same strict analysis, comparison, dominance, or explicit optimization request and qualified report through a private bounded JSON subprocess adapter.

At extension startup Pi provisions an isolated, immutable-revision uv environment outside its checkout. It registers formula analysis and its product skill only after that readiness check; otherwise only its diagnostic command remains available. [Vision](vision.md) owns the product boundary, [Analysis Model](analysis-model.md) owns request and report semantics, and [Roadmap](roadmap.md) owns uncommitted expansion work.


Bounded aggregate-work dominance is available in Python and Pi protocol v17. Python owns its canonical rational decomposition and exact one-axis regions; Pi validates and presents the report without recomputing mathematical policy. It excludes multiple axes, exponentials, opaque aggregates, rewrites, resource vectors, scheduling, and empirical performance.


Optimization is a separate explicit goal operation; ordinary analysis carries no optimization control or result. Its strict request preserves all submitted outputs, uses submitted mathematical facts, selects unit or exact weighted aggregate abstract work, and requires fixed `bounded_goal_v1` search, `verifier_backed_v1` proof, and an independent projection limit. Python generates, reparses, verifies, costs, deduplicates, and ranks complete candidates through fixed fair breadth-first monotonic depth-two search over every shipped exact-algebraic and exact-algorithmic lane. Query and optimizer share checked finite-sum derivation infrastructure, but optimizer transition and final proofs independently rerun it against replayed states and compare positive whole-computation selected-objective savings. Canonical states deduplicate only search, so returned candidates preserve caller order and policy-free identity. Protocol v17 transports complete one- or two-step traces, per-plan `strict_improvement` claims, actual scope and limits, observed result classification, deterministic ranked-prefix selection, separate search/projection states, bounded blockers, and typed failures. Pi strictly correlates and presents them without deriving mathematics or policy. Exact-symbolic replacement makes no best-candidate, global-optimality, runtime, numerical, or finite-precision claim.


## Components
- `packages/py-science-formula/src/py_science/formula/contracts/`: canonical request, explicit goal/search/proof, evidence, result, and report definitions; `models.py` and the package root are forwarding compatibility surfaces.
- `packages/py-science-formula/src/py_science/formula/_analysis/`: neutral retained-computation construction and structural-occurrence facts.
- `packages/py-science-formula/src/py_science/formula/_optimization/`: candidate families, replay, verification, objectives, canonical state, search, and plan projection; `optimization.py` is its compatibility facade.
- `packages/py-science-formula/src/py_science/formula/_service/`: request orchestration, queries, scenarios, dominance and optimization dispatch, and result bounds; `service.py` is its compatibility facade.
- `packages/pi-science/bridge/formula_adapter.py`: private, versioned, whole-request and output-bounded JSON adapter.
- `packages/pi-science/src/provision.ts`: eager isolated-uv readiness gate.
- `scripts/generate-pi-formula-schema.py` and `packages/pi-science/src/formula-schema.json`: deterministic Python-model-to-provider-schema generation and its checked-in Pi artifact.
- `packages/pi-science/src/bridge/`: protocol primitives, request and result shapes, bounded diagnostics, request-aware correlation, the per-call adapter client state machine, and compact result presentation.
- `packages/pi-science/src/bridge.ts`: outward compatibility barrel; internal production modules consume owning bridge modules directly.
- `packages/pi-science/src/process.ts`: adapter process spawning and process-tree termination mechanisms.
- `packages/pi-science/src/index.ts`: generated-schema tool registration, routing metadata, readiness composition, and always-available doctor.
- `packages/pi-science/tests/`: schema, bridge, AFMM round-trip, package, routing, and readiness-gate regression evidence.
- `packages/pi-science/skills/formula-analysis/`: restricted-dialect, modeling, bounded-query, diagnostic-recovery, and qualified-result guidance.


## Data flow
The formula-analysis flow is:

```text
strict Pi analysis/comparison/dominance/optimization request -> readiness gate -> bounded versioned JSON adapter -> py_science.formula -> validated qualified report
```

Python publishes the request model from which the repository generates Pi's checked-in provider-compatible structural schema. The gate rejects schema drift. Pi imports that artifact, injects restricted-SymPy syntax, and translates the public formula contract without owning mathematical policy. Active-tool routing metadata points agents to the packaged operational skill rather than duplicating its grammar.

The adapter owns whole-envelope and serialized-output bounds. Pi's bridge protocol module owns JSON, framing, and byte primitives; its request module owns transport shapes and source enumeration; its result module owns result shapes and request-independent checks; its correlation module owns request-aware matching; its client owns each call's timeout, cancellation, stream bounds, settlement, and cleanup state; presentation projects validated results; and `process.ts` owns process spawning and tree termination. Internal production modules consume these owners directly, while `bridge.ts` is outward-only. On the intentional request-error exit the client preserves only an exact bounded current-version Python error envelope; malformed, incompatible, surplus, wrong-status, or unbounded output still fails closed. The Python API remains transport-free and owns request validation, parsing, mathematical applicability, and analysis. Startup uses `uv run --isolated --no-project` with the immutable repository revision and a user cache, so mutable environments never enter the managed Pi checkout. Failed provisioning withholds the tool and product skill together rather than advertising a later-failing capability.

Within Python, service orchestration calls optimizer policy and both consume neutral retained analysis; comparison consumes the same neutral owner, and optimizer never calls service. Canonical contracts and compatibility facades preserve public object identity while internal owners remain direct. The [formula component boundaries topic](../.awf/topics/product/formula-component-boundaries.md) owns this dependency rule.

Optional general-context query requests and their exact discriminated qualified results cross the protocol-v17 boundary. TypeScript and the adapter enforce only strict shape and bounds; target resolution, assumption use, mathematical applicability, constraint normalization, compatibility, cardinality, and proof policy remain Python-owned. The partial bounded affine constraint family crosses as submitted named relationships, analyzer-owned effective domains, and equation-qualified provenance; Pi never interprets its mathematics. Scenarios specialize submitted work and effective domains but do not execute queries.

Derived query targets cross protocol v17 as strict correlation data only; Python owns earlier-only validation, verified-candidate eligibility, bounded qualification composition, and unavailable-target results. Direct `closed_form` may additionally evaluate one partial finite-polynomial nested Sum tree in Python; the bridge transports its checked candidate and never classifies or verifies it.

Direct Python and Pi dominance requests analyze retained original aggregate work once, and use the typed explicit-axis sign-chart seam for bounded canonical regions.


Bounded aggregate-work dominance is available in Python and Pi protocol v17. Python owns its canonical rational decomposition and exact one-axis regions; Pi validates and presents the report without recomputing mathematical policy. It excludes multiple axes, exponentials, opaque aggregates, rewrites, resource vectors, scheduling, and empirical performance.


An explicit optimize request carries one computation, a preserve-all exact-symbolic goal over its submitted domain, one abstract-work objective, fixed search and proof policy literals, and an independent projection limit. Ordinary analysis never dispatches optimizer policy. Python constructs each complete candidate with `Let` or a complete named system and reanalyses it through ordinary parsing and producer/dependency checks. Every shipped lane participates in fair depth-two scheduling; the exact-algorithmic finite-sum lane asks the shared checked derivation for one maximal tree location and proposal. The transition verifier treats that proposal as untrusted, independently rederives its antidifference and boundaries against the replayed parent, checks the structural path and child, and applies the common positive whole-computation objective policy. Final acceptance independently rederives every retained algorithmic identity from its owning pre-step state before direct original-to-final proof.

Generation and verification capture only bounded localized missing-cost, domain/cardinality, and evaluator-limit facts already observed; they perform no extra diagnostic traversal or proof. Search owns actual scope, limits, completion, observed population classification, and deterministic ranked-prefix selection, while result bounding owns independent projection truncation. Protocol v17 strictly correlates the required goal literals, scope, per-plan `strict_improvement` claim, complete one- or two-step traces, candidate context and output identities, classification, blockers, selection, and projection limit. Presentation exposes those transported distinctions without deriving mathematics, ranking, or refusal policy. A direct failure is typed and contains no plan. Independent resource budgets preserve the 262,144-byte ordinary-result allowance and bound optimization output to 262,144 bytes; the framed Pi limit remains 524,544 bytes. Exact-symbolic replacement carries no best-candidate, global-optimality, runtime, numerical, or finite-precision claim.


## Key dependencies
| Dependency | Role |
|---|---|
| Python 3.13 | Formula analysis runtime. |
| uv | Isolated Pi backend provisioning and workspace commands. |
| Pydantic v2 / SymPy | Formula contracts and bounded algebra, rendering, and verification. |
| Pi host API | Aggregate tool and diagnostic-command host (peer dependency). |
| TypeScript / Vitest / ESLint / Prettier | Pi bridge checking and tests. |
| awf | Projects repository guidance, lexical topics, and effort entrypoints. |

The root manifest resolves Pi production and development dependencies; `packages/py-science-formula/pyproject.toml` retains formula runtime dependencies.
