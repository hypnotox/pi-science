---
format: plan-v2
date: 2026-08-16
adrs: [separate-reusable-analysis-packages-from-pi-integration]
status: Proposed
---
# Plan: Distribute formula analysis and Pi integration

## Goal

Deliver `py-science-formula` as an independently importable Python 3.13 analysis distribution and `pi-science` as a project-pinnable Pi package that eagerly provisions the formula backend, exposes it only when healthy, and teaches both tool and direct-import use. Publishing to npm or PyPI, numerical evaluation of represented formula results, formula-to-code generation, benchmarking, and compatibility shims are non-goals.

## Architecture summary

Use a root development workspace with a self-contained `py-science-formula` member whose public boundary is `py_science.formula`, and remove the old `pi_science` import atomically. Keep parsing, the backend-independent expression tree, analysis policy, and SymPy rendering cohesive behind that typed in-process API. The aggregate `pi-science` Pi package depends one way on the Python API through a private machine-readable subprocess adapter; transport and provisioning failures never enter the Python analysis contract. At startup the extension validates an isolated uv environment from its pinned checkout before registering analysis tools or returning availability-dependent skill paths, while an always-available diagnostic command explains recovery. Each repository release is one compatible source snapshot, but adopter Python environments declare their Git-subdirectory dependency separately from Pi's project package pin.

Implementation proceeds in three independently green transactions: migrate and package the Python concern with its current-state claims; add and verify the Pi protocol, eager provisioning, tool, and fail-closed state; then add conditional skills, adopter/release documentation, and clean-source installation evidence. The exact uv cache invocation is settled by a confined spike before the bridge phase; it must keep mutable environments outside Pi's managed checkout and tolerate concurrent sessions.

## Phase 1: Establish the reusable formula-analysis distribution

**Execution mode: subagent-driven.**

Advances: ["current-authority"]
Completes: ["python-distribution"]

### Task 1.1: Migrate the Python package and public analysis contract atomically
Kind: batch
Applying: ["separate-reusable-analysis-packages-from-pi-integration:concern-oriented-python-distributions", "separate-reusable-analysis-packages-from-pi-integration:agpl-only-distribution", "separate-reusable-analysis-packages-from-pi-integration:analysis-not-formula-evaluation", "separate-reusable-analysis-packages-from-pi-integration:python-313-runtime"]
Paths: ["pyproject.toml", "uv.lock", ".python-version", "LICENSE", ".gitignore", "glob:src/pi_science/**", "glob:packages/py-science-formula/**", "glob:tests/**", "scripts/check"]
Representative: Replace the root `pi-science` distribution and `pi_science` imports with the self-contained `py-science-formula` member and `py_science.formula` public API while preserving the implemented safe parsing, normalization, structured failures, and operation metrics.
Edge: Provide no old namespace package or re-export shim; package metadata and user-facing types must describe analysis rather than imply calculation of the formula's represented result.
Post-check: As choreography, run `uv build --package py-science-formula --wheel --out-dir <new-temp-dir>` and require exactly one selected wheel. As state checks, census that wheel and tracked paths for absence of `pi_science`, create a new Python 3.13 environment under the temporary directory, install only the selected wheel, change to a second temporary directory outside the repository, and run checked success-sentinel probes for `py_science.formula`, a representative analysis, and rejection of `pi_science`; also run the migrated behavioral suite, strict type checking, Ruff, and root locked gate. As authority checks, run `./awf check`. Expected terminal set at the Task 1.1 snapshot: one independently built and installable `py-science-formula` distribution, no tracked old namespace, no source-tree or editable-environment import leakage, and no behavioral regression.

This phase starts from the review-settled Proposed ADR and current green restricted-formula evaluator. Create a root uv workspace that can admit later concern packages while keeping the formula member installable through a Git subdirectory. Move the implementation into the implicit `py_science` namespace with `formula` as the concrete package, deliberately configure Hatch wheel inclusion, and retain Python `>=3.13,<3.14`. Rename the typed public facade and request/result vocabulary around analysis, then update all internal imports and tests in the same transaction. Add package-local metadata and README content needed for a standalone build, repository AGPL-3.0-only text and manifest metadata, a lock consistent with the workspace, and gate commands that address the new source and test populations. Protect implicit-namespace coexistence and built-artifact contents with packaging tests instead of relying only on source-tree imports.

### Task 1.2: Determine the concurrency-safe uv bridge environment
Kind: spike
Applying: ["separate-reusable-analysis-packages-from-pi-integration:eager-fail-closed-provisioning", "separate-reusable-analysis-packages-from-pi-integration:pinned-public-source-distribution"]
Question: Which supported uv invocation can eagerly validate and reuse the local pinned `py-science-formula` source while keeping mutable environment state outside Pi's managed Git checkout, keying reuse to immutable source identity, and remaining safe when multiple Pi sessions start concurrently? Record the checked command, cache/environment location, invalidation behavior, first-run network behavior, and failure signals in Notes for Phase 2.

### Task 1.3: Apply the package, license, runtime, and product-boundary claims
Kind: batch
Applying: ["separate-reusable-analysis-packages-from-pi-integration:concern-oriented-python-distributions", "separate-reusable-analysis-packages-from-pi-integration:agpl-only-distribution", "separate-reusable-analysis-packages-from-pi-integration:analysis-not-formula-evaluation", "separate-reusable-analysis-packages-from-pi-integration:python-313-runtime"]
Paths: ["docs/decisions/separate-reusable-analysis-packages-from-pi-integration.md", ".awf/topics/metadata/product/distribution-model.yaml", ".awf/topics/parts/product/distribution-model/current-state.md", ".awf/topics/parts/product/product-boundary/current-state.md", ".awf/parts/agents-doc/identity.md", "glob:.awf/docs/parts/architecture/*.md", "glob:.awf/docs/parts/development/*.md", "glob:.awf/docs/parts/testing/*.md", ".awf/docs/parts/debugging/surfaces.md", "docs/analysis-model.md", "docs/architecture.md", "docs/development.md", "docs/testing.md", "docs/debugging.md", "docs/topics/product/distribution-model.md", "docs/topics/product/product-boundary.md", "docs/topics/product/index.md", "docs/domains/product.md", "AGENTS.md", "CLAUDE.md", ".awf/awf.lock"]
Representative: Make current-state authority and generated architecture describe the independent formula-analysis distribution and analysis-only semantics that Phase 1 actually delivers.
Edge: Keep formula-to-code as an open, out-of-scope future direction; do not present the Pi bridge or Git adopter flow as implemented before their later phases; exclude ADR-0001, retained plan history, and unrelated documentation.
Post-check: As choreography, run `./awf render`. As state checks, read the changed claims and generated identity, architecture, development, testing, debugging, analysis-model, domain, and topic outputs and run the full project gate. As authority checks, run `./awf check` and verify the rendered population against `.awf/awf.lock`. Expected terminal set: the ADR is Implementing with exactly the concern-oriented package, AGPL, Python 3.13, and updated product-boundary operations Applied; fail-closed provisioning and pinned-source operations remain unapplied; no generated drift or stale `pi_science` current-state claim remains.

Use the ADR lifecycle to enter Implementing and apply the first batch: `product/distribution-model:concern-oriented-analysis-packages`, `product/distribution-model:agpl-only`, `product/distribution-model:python-313-runtime`, and the update to `product/product-boundary:symbolic-analysis-only`, in the same phase transaction as their matching claim prose. Update the existing distribution-topic selector to own `pyproject.toml`, `uv.lock`, and `packages/**`, removing the retired `src/pi_science/**` selector; introduce no broader product-domain ownership.

### Phase close

Land the independently installable formula-analysis distribution, atomic import migration, package verification, applicable current-state claims, and uv bridge-spike evidence.

```commit
refactor(core): separate formula analysis package
```

## Phase 2: Add the eager fail-closed Pi bridge

**Execution mode: subagent-driven.**

Advances: ["current-authority"]
Completes: ["pi-bridge"]

### Task 2.1: Implement the aggregate package and machine-readable formula adapter
Kind: batch
Applying: ["separate-reusable-analysis-packages-from-pi-integration:aggregate-pi-integration", "separate-reusable-analysis-packages-from-pi-integration:eager-fail-closed-provisioning", "separate-reusable-analysis-packages-from-pi-integration:agpl-only-distribution"]
Paths: ["package.json", "package-lock.json", "glob:packages/pi-science/src/**", "glob:packages/pi-science/bridge/**", "glob:packages/pi-science/tests/**", "scripts/check"]
Representative: A bounded Pi tool request crosses a private versioned JSON subprocess envelope, calls the public `py_science.formula` API, and returns the same structured interpretation and metrics without moving transport policy into the Python core.
Edge: Distinguish analysis failures from environment, process, timeout, malformed-output, and protocol failures; reserve stdout for one deterministic response envelope and keep diagnostics on stderr or in typed bridge errors.
Post-check: As state checks, exercise successful and analysis-failure round trips plus malformed request, incompatible protocol, nonzero process, malformed response, timeout/cancellation, bounded output, and an exact `AGPL-3.0-only` root-manifest assertion; run TypeScript formatting/lint/type checks and tests, Python tests, and the combined root gate. As authority checks, run `./awf check`. Expected terminal set: the independently importable Python API remains transport-free, one aggregate Pi package manifest resolves production dependencies and carries the repository license, and every bridge failure becomes a bounded actionable diagnostic rather than an advertised successful analysis.

This phase starts from Phase 1's installable Python distribution and recorded uv environment-spike answer. Add the root Pi-package manifest and a product-owned extension implementation outside generated `.pi` workflow resources. Keep Pi host types as peer dependencies and runtime dependencies available under Pi's production install. Put the Python-side serialization adapter with the Pi bridge, not in the public formula-analysis API, and make its schema/protocol version explicit enough to reject incompatible or malformed messages. Register a clearly named formula-analysis tool only through a readiness-controlled helper so later concern tools can follow the same aggregate pattern.

### Task 2.2: Provision immediately and disable analysis surfaces on failure
Kind: batch
Applying: ["separate-reusable-analysis-packages-from-pi-integration:eager-fail-closed-provisioning"]
Paths: ["glob:packages/pi-science/src/**", "glob:packages/pi-science/tests/**", "package.json", "package-lock.json"]
Representative: Successful startup validates the Phase 1 spike-selected isolated uv environment before analysis-tool registration; failed startup emits one actionable warning and retains only `/pi-science-doctor` for diagnosis and recheck guidance.
Edge: Missing `uv`, Python provisioning failure, dependency/install failure, import validation failure, and concurrent startup must all fail closed without repeated session noise; print/JSON modes cannot depend on interactive UI.
Post-check: As state checks with controlled executable paths and temporary caches, prove success registers the formula tool, each prerequisite/provisioning failure registers no analysis tool, warnings are emitted at most once through supported mode-aware channels, diagnostics remain available, and a repaired environment is recognized on recheck/reload. In the healthy concurrency case, use a barrier-controlled two-process test that proves both processes overlap while contending for the same source identity and require both to become ready through one uncorrupted reusable environment with no checkout mutation. Separately inject a provisioning failure and require both processes to return the same fail-closed diagnosis. As authority checks, run the full gate including `./awf check`. Expected terminal set: no unavailable analysis surface is advertised and no mutable environment is created inside the managed package checkout.

Use the uv invocation and invalidation contract recorded by Task 1.2 rather than choosing a different cache model during implementation. Keep the diagnostic command available in both ready and disabled states, report the concrete failed prerequisite and recovery command, and make reload/restart the explicit point at which newly available skills and tools become authoritative.

### Task 2.3: Apply bridge provisioning authority and document the live failure surfaces
Kind: batch
Applying: ["separate-reusable-analysis-packages-from-pi-integration:aggregate-pi-integration", "separate-reusable-analysis-packages-from-pi-integration:eager-fail-closed-provisioning"]
Paths: ["docs/decisions/separate-reusable-analysis-packages-from-pi-integration.md", ".awf/topics/metadata/product/distribution-model.yaml", ".awf/topics/parts/product/distribution-model/current-state.md", ".awf/parts/agents-doc/identity.md", "glob:.awf/docs/parts/architecture/*.md", "glob:.awf/docs/parts/development/*.md", "glob:.awf/docs/parts/testing/*.md", "glob:.awf/docs/parts/debugging/*.md", "docs/architecture.md", "docs/development.md", "docs/testing.md", "docs/debugging.md", "docs/topics/product/distribution-model.md", "docs/topics/product/index.md", "docs/domains/product.md", "AGENTS.md", "CLAUDE.md", ".awf/awf.lock"]
Representative: Document the implemented Python-to-Pi dependency direction, eager readiness gate, isolated environment, protocol diagnostics, and combined Python/TypeScript development gate.
Edge: Do not claim availability-dependent skills or public Git installation evidence until Phase 3 lands; exclude retained decisions, plans, and Phase 3 adopter/release documents.
Post-check: Apply the middle batch containing only `product/distribution-model:fail-closed-pi-provisioning`; add `package.json` and `package-lock.json` to the distribution-topic selector in the same Phase 2 snapshot; as choreography, render. As state checks, semantically inspect changed architecture, development, testing, debugging, identity, domain, and topic outputs and run the full combined gate. As authority checks, run `./awf check` and verify managed-output drift. Expected terminal set: the claim and matching Applied event land atomically, both Pi manifest files are topic-owned, `product/distribution-model:pinned-public-source` remains the sole unapplied operation, and generated outputs contain no contradictory eager/lazy or enabled/disabled behavior.

### Phase close

Land the functional aggregate Pi package, private protocol adapter, eager isolated provisioning, diagnostic-only disabled mode, regression evidence, and matching current-state claim.

```commit
feat(pi): add eager formula analysis bridge
```

## Phase 3: Complete adopter guidance and pinned-source verification

**Execution mode: subagent-driven.**

Completes: ["adopter-experience", "current-authority"]

### Task 3.1: Load formula skills only when their tools are available
Kind: batch
Applying: ["separate-reusable-analysis-packages-from-pi-integration:aggregate-pi-integration", "separate-reusable-analysis-packages-from-pi-integration:eager-fail-closed-provisioning"]
Paths: ["glob:packages/pi-science/skills/**", "glob:packages/pi-science/src/**", "glob:packages/pi-science/tests/**", "package.json", "package-lock.json"]
Representative: A healthy extension contributes a formula-analysis skill that teaches the ordinary tool path and direct `py_science.formula` composition for complex probes; a disabled extension contributes neither the tool nor availability-dependent skill paths.
Edge: Keep product skills in the source-distributed Pi package rather than generated workflow `.pi/skills`; examples must pin Python independently and must not import from Pi's managed clone.
Post-check: As state checks, inspect resource discovery in ready and disabled states, require the returned skill to be complete, uniquely named, and absent on failure, and execute every checked command/import example against the package snapshot. As authority checks, run the full gate including `./awf check`. Expected terminal set: ready projects discover the tool and its matching guidance together, disabled projects see only diagnostics, and direct-import examples use the public Python boundary.

This phase starts from Phase 2's readiness-gated Pi package and machine-readable formula tool. Write one focused formula-analysis skill with selection guidance, tool examples, and pointers for persistent project dependencies and PEP 723/`uv run` probes. Register skill paths dynamically through Pi's resource-discovery event only after readiness succeeds; do not statically list availability-dependent skills in the root package manifest.

### Task 3.2: Document and verify the public Git adopter flow
Kind: batch
Applying: ["separate-reusable-analysis-packages-from-pi-integration:pinned-public-source-distribution", "separate-reusable-analysis-packages-from-pi-integration:agpl-only-distribution", "separate-reusable-analysis-packages-from-pi-integration:python-313-runtime"]
Paths: ["README.md", "packages/py-science-formula/README.md", "scripts/check-release", "glob:tests/distribution/**", ".github/workflows/ci.yml", ".awf/docs/parts/releasing/content.md", "glob:.awf/docs/parts/development/*.md", "glob:.awf/docs/parts/testing/*.md", "glob:.awf/docs/parts/debugging/*.md", ".awf/docs/parts/roadmap/deferred.md"]
Representative: The root README gives copyable project-local `.pi/settings.json`, persistent Python Git-subdirectory, and one-off PEP 723 examples using one release ref, followed by prerequisites, eager first-run behavior, diagnostics, upgrades, license, and the analysis-versus-performance boundary.
Edge: Tags are readable release identifiers but full commit SHAs and Python lock resolution provide immutable pins; the release lane must not depend on an editable source tree or silently reuse developer environments; generated documentation remains Task 3.3-owned.
Post-check: As choreography, have `scripts/check-release` materialize a temporary Git commit from the exact selected Phase 3 working-tree snapshot, including intended untracked files, and assert that both tested source pins resolve to that commit. From that clean snapshot and empty caches, use state checks to exercise production dependency installation, built Python import and representative analysis, Pi package discovery/startup in a supported noninteractive harness, ready tool/skill visibility, a forced missing-prerequisite disabled state, and every README command. Run focused documentation/example checks that tolerate the intentionally pending render; reserve `./awf check` and the ordinary full gate for Task 3.3. Expected terminal set: `scripts/check-release` reports explicit success for separate Pi and Python pins at the temporary commit, ordinary `scripts/check` remains unchanged and fast, CI is configured to run the authoritative gates after render settlement, and authored release guidance distinguishes local, clean-source, and remote-tag verification.

Add an explicit slower release/distribution lane rather than burdening every commit with clean-clone provisioning. Make it reproduce Git-subdirectory Python installation and project-local Pi loading from a source ref without relying on network publication during normal development; releasing guidance adds the real public-ref check after a tag exists. Preserve formula-to-code as an open but currently out-of-scope roadmap direction.

### Task 3.3: Apply the pinned-source claim and settle generated documentation
Kind: batch
Applying: ["separate-reusable-analysis-packages-from-pi-integration:pinned-public-source-distribution", "separate-reusable-analysis-packages-from-pi-integration:aggregate-pi-integration"]
Paths: ["docs/decisions/separate-reusable-analysis-packages-from-pi-integration.md", ".awf/topics/parts/product/distribution-model/current-state.md", ".awf/parts/agents-doc/identity.md", "docs/vision.md", "docs/analysis-model.md", "docs/architecture.md", "docs/development.md", "docs/testing.md", "docs/debugging.md", "docs/releasing.md", "docs/roadmap.md", "docs/topics/product/distribution-model.md", "docs/topics/product/index.md", "docs/domains/product.md", "AGENTS.md", "CLAUDE.md", ".awf/awf.lock"]
Representative: Current-state and generated documentation describe the complete source-distributed Python-and-Pi system, while generated workflow resources remain distinct from product-owned Pi skills.
Edge: Keep the ADR and plan nonterminal until implementation assurance settles; this phase applies the final remaining claim but does not perform their deferred `Implemented` flips; exclude retained decisions, retained plans, generated workflow skills, and product-owned Pi skill sources from render ownership.
Post-check: Apply the final batch containing only `product/distribution-model:pinned-public-source`; as choreography, render. As state checks, inspect every changed output in the `.awf/awf.lock` managed population for accurate names, commands, package boundaries, prerequisites, release pins, disabled behavior, license, and deferred formula-to-code scope, then run `./scripts/check` and `./scripts/check-release`. As authority checks, run `./awf check` and verify no unmanaged or unrelated generated file changed. Expected terminal set: every ADR operation is Applied while status remains Implementing, every DoD outcome is evidenced, no generated drift remains, and no document tells adopters to install `pi-science` as the Python library or import `pi_science`.

### Phase close

Land conditional product skills, adopter and release guidance, clean-source distribution checks, CI coverage, the final current-state claim, and all rendered documentation.

```commit
feat(distribution): complete pinned-source adopter flow
```

## Definition of done

- `dod: python-distribution` A clean Python 3.13 environment outside the source tree can install a built `py-science-formula` artifact, import `py_science.formula`, and perform the implemented abstract analysis; built artifacts contain no `pi_science` compatibility package.
- `dod: pi-bridge` Pi eagerly validates an isolated uv environment from its pinned checkout and exposes the bounded formula-analysis tool only when a version-compatible subprocess round trip succeeds; otherwise it warns once and leaves actionable diagnostics without analysis tools.
- `dod: adopter-experience` A project can pin one compatible repository ref separately for Pi and Python, discover matching tool guidance when healthy, and follow checked README examples for ordinary tool calls, persistent imports, and one-off probes.
- `dod: current-authority` All declared ADR operations are Applied with matching current-state claims; generated architecture, development, testing, debugging, releasing, roadmap, product, and agent guidance accurately describe the delivered package boundaries, AGPL-3.0-only license, Python 3.13 runtime, source distribution, and fail-closed behavior.

## Notes

Inline owners immediately correct stale instructions and record reasoned deviations here. Delegated owners may report rather than edit; the parent supplies the report to phase review and reconciles it with findings in one focused post-review settlement commit before checkpointing or later execution. Record deviations, spike answers, follow-ups, and findings surfaced during implementation.

- Plan review: redefined the Phase 1 Python outcome around a clean built-artifact install; Phase 3 owns Git-subdirectory adopter evidence.
- Plan review: confined topic ownership to the existing distribution topic and replaced broad documentation globs with affected authored sources and generated consumers, excluding retained ADR and plan history.
- Plan review: made first, middle, and final ADR application batches explicit and carried AGPL metadata into the later-created Pi manifest.
- Plan review: classified material evidence as state or authority checks, isolated wheel probes outside the source tree, and required barrier-controlled concurrency evidence for provisioning.
- Plan verify pass: separated Phase 3 authored-source checks from its render-and-authority close, tied clean-source verification to an exact temporary commit of the working-tree snapshot, required healthy concurrent provisioning to make both callers ready, and moved Pi manifest selector ownership into Phase 2.
- Task 1.2 checked uv answer: from outside the Pi checkout, set `UV_CACHE_DIR="${XDG_CACHE_HOME:-$HOME/.cache}/pi-science/uv"` and run `uv run --isolated --no-project --python 3.13 --with "py-science-formula @ git+https://github.com/hypnotox/pi-science.git@<immutable-commit>#subdirectory=packages/py-science-formula" python -c '<health probe>'`. The immutable Git commit and package subdirectory key uv's cached environment; the cache and all mutable environment state live under the user cache, not the managed checkout. A first run needs Git access plus network access for uncached Python and package dependencies; subsequent identical probes reused the cache in the checked spike. uv serializes cache writes for concurrent callers. Missing `uv` or Python, an unreachable or invalid revision, Git/network failure on a cold cache, resolution/build failure, or a nonzero health probe are provisioning failures for Phase 2 to report and fail closed.
- Phase 1 review settlement: added a gate-owned distribution regression that inspects wheel namespace and license contents, installs and probes outside the repository, rejects `pi_science`, and composes another implicit `py_science` member; included the AGPL text in the wheel. A reversible import-order mutation under the migrated source path passed pytest and Pyright, failed the complete gate at Ruff with `I001`, and was restored by exact edit. A separate exact mutation made the package-local AGPL text differ from the repository license; the focused distribution suite failed both its built-wheel and source-license assertions, after which that mutation was restored by exact edit and the final gate returned green.
- Phase 2 implementation deviation: replaced the root `packages/*` uv workspace glob with the explicit Python member because the new TypeScript Pi package is not a Python uv member; the combined gate verifies the narrower workspace.
- Phase 2 review settlement: derived the full commit SHA from the installed repository checkout and removed mutable revision fallbacks; adopted the real Pi API and valid command/tool contracts; bounded requests, stdout, and continuously drained stderr; made cancellation and timeout cleanup terminate resistant children; strictly validated adapter and health protocols; added external-cache and prerequisite diagnostics; expanded actual-adapter, lifecycle, failure, bound, and real-uv concurrency tests; included the private adapter in Pyright/Ruff; configured meaningful ESLint rules; and narrowed npm pack contents. `.gitignore` gained `node_modules/` because the production-install verification introduced the first repository-local Node dependency tree. Reversible adapter import-order and TypeScript explicit-`any` mutations proved the complete Ruff path and ESLint rule fail before exact restoration and a final green gate.
- Phase 2 renewed-review settlement: centralized detached subprocess-group TERM/KILL escalation for bridge and provisioning, bounded serialized request envelopes and spawn diagnostics, rejected direct and symlink-resolved checkout caches, and added real adapter, resistant-descendant, escape-boundary, and npm-pack/production-install regressions; focused Pi tests and the combined gate verify the fixes.
- Phase 2 residual settlement: Windows cleanup explicitly uses error-tolerant `taskkill /PID <pid> /T /F`; non-cleanup bridge-stdin errors now terminate and diagnose the process tree; and cache canonicalization races fail closed with bounded actionable cache detail. Bridge timeout/cancellation and provisioning-timeout tests record resistant descendant PIDs and prove their bounded disappearance with leak-killing teardown. A reversible child-only termination mutation made all three descendant assertions fail, then was exactly restored before the focused suite and combined gate returned green.
