---
format: plan-v2
date: 2026-08-16
adrs: [0001]
status: Proposed
---
# Plan: Implement First Formula Evaluation MVP Slice

## Goal

Deliver the first executable, safely parsed restricted-SymPy formula evaluator through a typed in-process API, with normalized interpretation, submitted-operation counts, structured failures, and a reproducible strict Python gate. LaTeX, CLI transport, substitutions, functions, indexed constructs, equation systems, scenarios, dependencies, comparisons, and rewrites are non-goals.

## Architecture summary

Expose `evaluate(request: EvaluationRequest) -> EvaluationOutcome` as the public in-process boundary. Strict frozen Pydantic v2 models own request validation and the discriminated success/failure result contract; a small backend-independent typed expression tree owns integer literals, symbols, and submitted `+`, `-`, `*`, `/`, and `**` operators. An allowlisted parser builds that tree from Python expression syntax without evaluating submitted text, an analyzer counts the preserved operators and unit work, and a one-way SymPy adapter translates only validated tree nodes for normalized SymPy and LaTeX rendering. Transport semantics remain outside the evaluator. Each behavior begins as a failing end-to-end test through `evaluate()` and turns green before the next behavior is introduced. Python 3.13, uv, pytest, Pyright strict, Ruff, Pydantic v2, and SymPy form the initial toolchain; the project gate runs application checks and the awf authority check.

## Phase 1: Deliver the typed evaluator vertical slice

**Execution mode: inline.**

Completes: ["typed-evaluation", "safe-restricted-parser", "operation-accounting", "reproducible-gate", "current-documentation"]

### Task 1.1: Establish the typed package and first normalized evaluation path
Applying: ["0001:familiar-safe-mathematical-inputs", "0001:shared-mathematical-model", "0001:inspectable-qualified-analysis"]
Paths: ["pyproject.toml", ".python-version", "uv.lock", "src/pi_science/", "tests/e2e/test_formula_evaluation.py"]

Pin Python 3.13 and configure a uv-managed package with strict Pyright, Ruff, pytest, Pydantic v2, and SymPy. Before implementing model configuration, witness public-contract tests fail for an extra request field, representative string-to-enum and string-to-number coercions, frozen-model mutation, and success/failure discriminator narrowing; the checked test code must exercise both runtime discrimination and Pyright's branch narrowing. Add strict frozen Pydantic request, interpretation, success, failure, error, and discriminated-outcome models to turn those tests green. Add a typed immutable internal expression union that has no Pydantic or SymPy dependency. Through the public `evaluate()` entry point, then witness an end-to-end test fail for a simple integer-and-symbol arithmetic expression and implement only the allowlisted parsing and validated-tree-to-SymPy rendering needed to return deterministic normalized SymPy and LaTeX interpretations. The parser may inspect Python's expression AST but must never pass submitted text to `eval`, `exec`, `compile` for execution, `sympify`, `parse_expr`, or another evaluator. Generate the lockfile with uv and read back `pyproject.toml`, `.python-version`, and `uv.lock` before relying on the environment.

### Task 1.2: Count submitted arithmetic operations and unit work
Applying: ["0001:shared-mathematical-model", "0001:inspectable-qualified-analysis"]
Paths: ["src/pi_science/", "tests/e2e/test_formula_evaluation.py"]

Add end-to-end examples one at a time for nested addition, subtraction, multiplication, division, and exponentiation, witnessing each new expectation fail before extending the analyzer. Return a fully typed count object and total abstract unit work. Count binary operator occurrences in the validated internal tree, so subtraction and division remain distinct even when the SymPy adapter renders them canonically as addition of a negative or multiplication by a reciprocal. Parentheses add no work. Accept exactly one Python AST `UnaryOp` using unary plus or minus whose operand is an integer `Constant` (excluding `bool`) as a signed integer literal with no operation cost; because whitespace and parentheses are absent from the AST, `-1`, `+1`, `- 1`, and `-(1)` are equivalent accepted forms, while a nested unary node such as `--1` is rejected. Cover those boundaries end to end. Keep weighting, symbolic loop aggregation, function costs, and algebraic simplification outside this slice.

### Task 1.3: Close the restricted grammar with structured failures
Applying: ["0001:familiar-safe-mathematical-inputs", "0001:inspectable-qualified-analysis"]
Paths: ["src/pi_science/", "tests/e2e/test_formula_evaluation.py"]

Drive malformed syntax and each unsupported category through separate failing end-to-end cases before implementing the corresponding rejection: calls, attributes, indexing, containers, comprehensions, non-integer constants, boolean operators and comparisons, unsupported unary expressions, and unsupported binary operators. Accept only integer literals, ordinary named symbols, parentheses, the five approved binary operators, and signed integer literals. Return a discriminated `EvaluationFailure` with a stable typed error code, human-readable message, and source location when the parser supplies one; do not leak raw parser or SymPy exceptions through the public boundary. Add a repeated-request assertion proving deterministic typed results.

### Task 1.4: Make application verification authoritative and document the runtime
Kind: batch
Applying: ["0001:symbolic-analysis-product-boundary"]
Paths: ["scripts/check", ".awf/config.yaml", ".awf/parts/agents-doc/identity.md", "glob:.awf/docs/parts/architecture/*.md", "glob:.awf/docs/parts/development/*.md", "glob:.awf/docs/parts/testing/*.md", "docs/analysis-model.md", "glob:docs/architecture.md", "glob:docs/development.md", "glob:docs/testing.md", "docs/config-reference.md", "docs/workflow.md", ".awf/hooks/pre-commit.sh", ".awf/hooks/pre-push.sh", ".awf/awf.lock", "AGENTS.md", "CLAUDE.md", "glob:.claude/**", "glob:.pi/**"]
Representative: Replace the docs-only setup and `./awf check` gate claims with the uv-provisioned evaluator runtime and `scripts/check` application-plus-awf gate, then regenerate consumers from those authored sources.
Edge: Preserve broader MVP capabilities as future contract while naming the exact arithmetic grammar currently implemented; generated skills and hooks must call `scripts/check` without causing that script to invoke itself.
Post-check: From the completed Phase 1 worktree, allocate a new temporary `UV_PROJECT_ENVIRONMENT`, run `uv sync --locked` into it, and invoke `scripts/check` through that isolated locked environment; require checked successful pytest, Pyright strict, Ruff, and `./awf check` sentinels. Before `./awf render`, capture a tracked-and-untracked `git status --short` census and existence/content hashes for `.awf/awf.lock` plus every managed-output path listed in its `files` map. After rendering, capture the same evidence for the union of pre-render and post-render lock populations; compare hashes and existence rather than status alone, and read every changed or newly created target before the phase gate. Expected terminal set: no generated drift, no test/type/lint failures, and no stale documentation claiming that the repository lacks an analyzer runtime; exclude only ignored uv caches, the ordinary worktree environment, and the explicitly temporary verification environment.

Add an executable project gate that runs pytest, Pyright strict, Ruff, and `./awf check`, then make the awf `gateCmd` and `gateCmdFull` point to it and expose the focused pytest command through `testCmd`. Treat the approved typing/toolchain decisions, ADR-0001, and repository invariants as authority: pytest is a state check for observable evaluator behavior and safety failures, Pyright strict is a state check for the accepted static-typing property, Ruff is a state check for configured source-quality rules, and `./awf check` is the authority/drift check for repository and generated-state rules; introduce no choreography-only check. Update the authored awf sources and the preserved Analysis Model body so current architecture, setup, dependencies, test layout, implemented restricted grammar, and deferred capabilities match the delivered runtime. Render all managed outputs. Semantically inspect the generated command guidance, hooks, architecture, development, testing, configuration reference, workflow, and identity prose for recursion, contradictory old claims, and accurate separation between the implemented slice and the broader MVP target.

### Phase close

Land the complete independently green evaluator slice, its end-to-end evidence, toolchain, lockfile, authoritative gate, and current documentation together.

```commit
feat(evaluator): add first formula evaluation slice
```

## Definition of done

- `dod: typed-evaluation` A caller can construct a strict typed restricted-SymPy request, invoke `evaluate()`, and receive deterministic typed normalized SymPy and LaTeX interpretation without a CLI or serialization adapter.
- `dod: safe-restricted-parser` Malformed or out-of-grammar submitted text returns a structured typed failure, and submitted text never reaches an arbitrary Python or SymPy string evaluator.
- `dod: operation-accounting` End-to-end tests prove distinct submitted counts for addition, subtraction, multiplication, division, and exponentiation plus total unit work, including cases whose normalized SymPy form differs.
- `dod: reproducible-gate` A clean checkout can use uv to provision the pinned environment, and the authoritative project gate passes pytest, Pyright strict, Ruff, and awf checks.
- `dod: current-documentation` Generated and preserved project documentation describes the executable slice, its commands and dependencies, and its boundaries without presenting deferred MVP capabilities as implemented.

## Notes

Inline owners immediately correct stale instructions and record reasoned deviations here. Delegated owners may report rather than edit; the parent supplies the report to phase review and reconciles it with findings in one focused post-review settlement commit before checkpointing or later execution. Record deviations, spike answers, follow-ups, and findings surfaced during implementation.

- Plan review: added explicit red-green coverage for strict Pydantic behavior and discriminated outcome narrowing so accepted public-contract invariants have regression evidence.
- Plan review: defined signed integer literals by exact Python AST shape and boundary examples so whitespace, parentheses, unary plus, and repeated signs have executable semantics.
- Plan review: classified each gate lane by its durable state property and strengthened reproducibility evidence with an isolated locked uv environment.
- Plan review: expanded generated-output scope and replaced a non-isolating `git diff` probe with pre/post tracked-and-untracked censuses plus existence/content hashes across the union of pre/post awf-managed populations.
- Plan review: declined to add generic clean/green baseline choreography to the plan because the executing-plans workflow explicitly owns that protocol.
