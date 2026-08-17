---
format: plan-v2
date: 2026-08-17
adrs: []
status: Proposed
---
# Plan: Align the Pi formula tool contract and guidance

## Goal

Make the user-facing `analyze_formula` tool a thin, reliable Pi bridge to the authoritative Python formula-analysis API: generate its provider-compatible structural schema from `AnalysisRequest`, preserve Python request diagnostics, and teach agents the shipped restricted-SymPy contract through explicit routing and the product skill. Do not expand the parser language, mathematical evaluator, query families, or internal development workflow skills.

## Architecture summary

Python remains the sole authority for request validation, restricted-expression parsing, and mathematical policy. A deterministic repository generator derives a checked-in, provider-compatible public Pi JSON Schema from `AnalysisRequest`; the gate rejects drift, while the TypeScript extension imports that artifact, removes no semantic restrictions of its own, injects `syntax: "sympy"`, and translates bounded adapter results into Pi tool results. Pi prompt metadata directs agents to read the progressively disclosed `pi-science-formula-analysis` skill, whose compact operational guide owns the expression dialect, modeling recipes, examples, qualifications, and recovery guidance. The bridge recognizes the adapter's bounded request-error envelope even on its intentional nonzero exit, but continues to reject malformed, incompatible, or unbounded subprocess output.

## Phase 1: Generate and consume the Pi request schema

**Execution mode: inline.**

Advances: ["agent-first-call"]
Completes: ["generated-schema"]

### Task 1.1: Add deterministic Python-to-Pi schema generation
Paths: ["scripts/generate-pi-formula-schema.py", "packages/pi-science/src/formula-schema.json", "tests/test_pi_schema_generation.py", "scripts/check", ".awf/docs/parts/testing/gate.md", "docs/testing.md", ".awf/awf.lock"]

Create a repository generator that starts from `py_science.formula.AnalysisRequest.model_json_schema()` and deterministically writes the checked-in Pi-facing artifact. Target the tool-parameter JSON Schema subset documented and exercised by the repository's pinned `@earendil-works/pi-coding-agent` and `typebox` versions: recursive schemas may use `type`, `enum`, `properties`, `required`, `additionalProperties`, `items`, `minItems`, `maxItems`, `uniqueItems`, `minimum`, `maximum`, `minLength`, `maxLength`, `pattern`, `description`, and object/scalar `anyOf`; every finite string choice must use `{ "type": "string", "enum": [...] }`, matching Pi's Google-compatible `StringEnum`, rather than `const` or an `anyOf` of literals. The normalization must remove the injected `syntax` field, expose mutually exclusive expression and equation-system request variants, inline local references, remove discriminators and definition tables, and retain structural required fields, closed-object behavior, patterns, population limits, and scalar bounds that Pydantic publishes. It must not translate model validators, parser behavior, graph checks, or mathematical applicability into a second semantic implementation.

Provide write and check behavior suitable for local regeneration and CI. The check must compare canonical bytes, fail with an actionable regeneration command when the committed artifact differs, recursively reject keywords outside the named subset, and reject unresolved references, definitions, discriminators, `const`, and literal unions. Add focused Python tests for deterministic output, public removal of `syntax`, representative expression/system/query branches, and preservation of key bounds. Add a TypeScript assertion that the artifact passes the pinned TypeBox `Value.Check` cases and can be retained by a Pi `registerTool` host; these are the deterministic compatibility checks for the pinned harness contract, not a claim about arbitrary future providers. Wire the check and generator lint coverage into `scripts/check` without requiring an installed Python environment beyond the existing locked workspace. Update the authored testing gate source, render `docs/testing.md`, and include the resulting awf lock mutation in this phase.

### Task 1.2: Register the generated schema through the thin TypeScript bridge
Paths: ["packages/pi-science/src/index.ts", "packages/pi-science/src/bridge.ts", "packages/pi-science/tests/start.test.ts", "packages/pi-science/tests/package.test.ts", "tsconfig.json", ".prettierignore"]

Enable TypeScript's `resolveJsonModule`, import `formula-schema.json` from `index.ts` with the NodeNext JSON import attribute, and cast the immutable imported value only to the `TSchema` boundary required by Pi. Replace the hand-maintained TypeBox schema construction with that artifact. Keep the existing TypeScript request types only where the bridge needs compile-time transport access; they are not an executable validation authority. Preserve `syntax: "sympy"` injection and the expression/system query-target typing used by bridge code. No dependency, package manifest, or lockfile change is part of this task because the npm `files` entry already ships the entire `packages/pi-science/src` directory.

Update schema tests to exercise representative accepted and rejected expression, system, scenario, and query requests against the imported artifact, and verify that the npm package contains the generated schema. Preserve the existing readiness rule: the product tool and skill remain jointly absent when Python provisioning is not ready.

### Phase close

Land the generated contract, its gate, gate documentation, and its first production consumer together. From the Phase 1 snapshot, run the state checks `uv run --locked pytest tests/test_pi_schema_generation.py`, `uv run --locked python scripts/generate-pi-formula-schema.py --check`, and `npm run test:pi -- packages/pi-science/tests/start.test.ts packages/pi-science/tests/package.test.ts`; each must exit zero and establish deterministic generation, current artifact bytes, TypeBox/Pi consumption, and package inclusion. Then run the authority-enforcement gate `./scripts/check` and require exit zero.

```commit
feat(pi): generate formula tool schema from Python
```

## Phase 2: Preserve Python request diagnostics through Pi

**Execution mode: inline.**

Completes: ["diagnostic-recovery"]

### Task 2.1: Capture the lost-validation-message regression
Paths: ["packages/pi-science/tests/bridge.test.ts", "packages/pi-science/tests/start.test.ts"]

Add failing regressions in which a request passes the public structural schema but the real or protocol-faithful adapter rejects a Python-owned cross-field rule, exits with its documented request-error status, and emits the bounded `{ version, error: { kind: "request", message } }` envelope. The bridge test must assert that `invokeAdapter` receives the Python validation path and message rather than the generic `formula adapter exited unsuccessfully` text. The registered-tool test must independently assert that the same exact bounded path/message reaches the agent-facing `analyze_formula` tool error.

### Task 2.2: Parse bounded request-error envelopes before generic process failure
Paths: ["packages/pi-science/src/bridge.ts", "packages/pi-science/tests/bridge.test.ts"]

Teach `invokeAdapter` to recognize only the exact current-protocol request-error envelope on the adapter's intentional request-error exit, bound and strictly decode it using the existing response limits, and surface it as a distinguishable bridge error with the adapter's message intact. Do not accept success envelopes on nonzero exits, error envelopes on arbitrary exit statuses, surplus keys, malformed UTF-8/JSON, incompatible versions, oversized messages, or stderr-only process failures; those retain their existing fail-safe classifications and diagnostics.

### Phase close

Land the regression and the minimal bridge correction as one bug-fix transaction. From the Phase 2 snapshot, run the state check `npm run test:pi -- packages/pi-science/tests/bridge.test.ts packages/pi-science/tests/start.test.ts` and require exit zero, establishing the actionable request-error cases and the malformed JSON/UTF-8, wrong-status, incompatible-version, oversized-output/message, surplus-key, and stderr-only nonzero-exit terminal assertions. Then run the authority-enforcement gate `./scripts/check` and require exit zero.

```commit
fix(pi): preserve formula request diagnostics
```

## Phase 3: Teach agents discovery, formulation, and interpretation

**Execution mode: inline.**

Completes: ["agent-first-call", "guidance-current"]

### Task 3.1: Add explicit Pi routing metadata
Paths: ["packages/pi-science/src/index.ts", "packages/pi-science/tests/start.test.ts"]

Add a concise `promptSnippet` describing the formula-analysis capability and active-tool `promptGuidelines` that name `analyze_formula`, direct the agent to read the available `pi-science-formula-analysis` skill before first use, and identify Python as the authority for rejected requests. Do not instruct the agent to invoke `/skill:...`, imply that skill loading is enforceable state, or duplicate the restricted grammar in static system-prompt metadata. Extend the test host to retain and assert tool description and prompt metadata so later routing drift is visible.

### Task 3.2: Refocus the packaged skill on the shipped operational contract
Paths: ["packages/pi-science/skills/formula-analysis/SKILL.md", "packages/pi-science/tests/package.test.ts"]

Keep the essential first-use contract directly in `SKILL.md`: selection between expression and system requests; the accepted literal, symbol, arithmetic, indexed-scalar, positional-call, one-limit inclusive `Sum`, `Eq`, relationship, and signed-infinity forms; important rejected or merely generic-call spellings; and the distinction between parser acceptance, request-context validity, and bounded query applicability. Retain the Python-owned rules for domains, definitions, assumptions, scenarios, queries, qualifications, and non-goals, but reorganize them into compact modeling guidance with minimal expression, system, and query examples rather than relying on one large request.

Tell agents to inspect normalized interpretations before conclusions and to use returned paths, spans, supported alternatives, blockers, and proof qualifications when correcting or interpreting a request. Avoid claiming support for LaTeX, vector shorthand, numerical evaluation, unrestricted SymPy, general theorem proving, or evaluator families beyond the shipped bounded implementations. Strengthen package tests around a few stable routing, dialect, and result-interpretation statements without snapshotting the prose wholesale.

### Task 3.3: Synchronize current user-facing documentation
Kind: batch
Paths: ["README.md", "packages/py-science-formula/README.md", "docs/analysis-model.md", ".awf/docs/parts/architecture/components.md", ".awf/docs/parts/architecture/data-flow.md", "docs/architecture.md", ".awf/awf.lock"]
Representative: Pi tool-call examples omit user-supplied `syntax`, direct-Python examples retain `FormulaSyntax.SYMPY`, all current examples use only shipped restricted-SymPy forms, and accepted query shapes remain distinct from bounded evaluator support.
Edge: Broader future-product material must live after the exact heading `## Broader product direction (not implemented)` and must not instruct agents to submit unsupported LaTeX, `Product`, `Max`, multi-limit sums, or other unimplemented constructs to the current tool.
Post-check: From the Phase 3 pre-close snapshot, run the choreography step `./awf render`, then the authority check `./awf check`; require both to exit zero. Perform a state check by inspecting all of `docs/analysis-model.md` and the changed Architecture paragraphs for contradictory current guidance, concept drift, or unintentional placeholders. Print `CURRENT_GUIDANCE_SEARCH_OK` only after two state searches exit successfully with an empty residual set: (1) `rg -n '"syntax"\s*:\s*"latex|Product\(|Max\(|multi-limit' README.md packages/py-science-formula/README.md packages/pi-science/skills/formula-analysis/SKILL.md`; and (2) extract only the prefix of `docs/analysis-model.md` before the exact future heading, then search that prefix with the same expression. The future-heading suffix is the sole exclusion. As a final state check, require the post-render changed managed set to be exactly the authored Architecture sources, `docs/architecture.md`, the preserved edit-in-place `docs/analysis-model.md` body when changed, and `.awf/awf.lock`.

Update user-facing examples and the `docs/analysis-model.md` edit-in-place body to state the exact shipped expression/query limits and to separate operational current guidance from broader direction. Route generated-schema, bridge, skill-routing, and diagnostic-flow facts through the authored Architecture component/data-flow sources and rendered `docs/architecture.md`; do not mutate ADR-origin mathematical-analysis topic claims unless their Python-owned mathematical meaning actually changes. Make generated-tree changes through their awf-owned sources or edit-in-place surface, render them, and commit sources with outputs.

### Phase close

Land routing metadata, the operational product skill, and synchronized user-facing documentation together. From the Phase 3 snapshot, run the state check `npm run test:pi -- packages/pi-science/tests/start.test.ts packages/pi-science/tests/package.test.ts` and require exit zero for all metadata and packaged-skill assertions; complete Task 3.3's classified render, authority, and semantic state checks; then run the authority-enforcement gate `./scripts/check` and require exit zero.

```commit
feat(pi): route agents to formula guidance
```

## Definition of done

- `dod: generated-schema` The committed Pi parameter schema is deterministically derived from `AnalysisRequest`, provider-compatible, shipped in the npm package, consumed by `analyze_formula`, and rejected by the gate when stale.
- `dod: diagnostic-recovery` A Python-owned request-validation failure reaches the agent with its bounded actionable path/message, while malformed or incompatible subprocess responses still fail closed.
- `dod: agent-first-call` An agent can discover `analyze_formula`, is directed to the product skill, and has enough structural schema plus skill guidance to formulate a valid first expression, system, or bounded query request.
- `dod: guidance-current` The packaged skill and current user-facing documentation agree with the shipped parser, request rules, evaluator limits, readiness behavior, and Python-owned semantic boundary.

## Notes

Inline owners immediately correct stale instructions and record reasoned deviations here. Delegated owners may report rather than edit; the parent supplies the report to phase review and reconciles it with findings in one focused post-review settlement commit before checkpointing or later execution. Record deviations, spike answers, follow-ups, and findings surfaced during implementation.

- Plan review: confined schema compatibility to a named JSON Schema subset backed by the repository's pinned Pi/TypeBox contract and deterministic registration/validation tests, rather than claiming compatibility with unspecified future providers.
- Plan review: fixed the JSON consumer to TypeScript `resolveJsonModule` plus a NodeNext import attribute and removed an unsupported manifest mutation; the generated artifact remains shipped by the existing `files` boundary.
- Plan review: routed transport and routing documentation to Architecture ownership, preserved ADR-origin mathematical topic claims, and made future-scope exclusion deterministic through one exact heading.
- Verify review: classified focused tests, drift comparisons, residual searches, and semantic inspection as state checks; rendering as choreography; and `./awf check` plus `./scripts/check` as authority enforcement, so each check is no stricter than its named durable obligation.
- Phase 1: added `enum` to the plan's allowed schema-keyword list because its immediately following provider-safe string-choice requirement already mandates `enum`; this corrects an internal omission without changing the approved schema boundary.
- Phase 1: added `.prettierignore` so the deterministic Python generator, rather than a second formatter, exclusively owns `formula-schema.json` bytes; the schema drift check and JSON parser tests verify the artifact.
- Phase 1 review: required every Pydantic `const` discriminator after converting it to an enum, added schema-aware allowed-key validation and stale-artifact falsification, derived query membership and its shared target from Pydantic's emitted union, and added an installed-package Pi loader probe. These corrections preserve the Python-owned contract while closing structural and verification gaps identified at `349125e`.
