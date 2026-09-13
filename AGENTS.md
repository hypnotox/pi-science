# pi-science project guidance

`pi-science` is an active AGPL-3.0 analysis API and Pi package for developers and Pi users who need bounded, qualified symbolic-mathematical reports. The transport-free typed Python implementation lives in `packages/py-science-formula`; `packages/pi-science` integrates it with Pi through an isolated, pinned uv backend. Own the requested change and the repository's ongoing correctness and maintainability.

## Global rules

- Keep public models and mathematical policy backend-independent. Python owns resource-checked algebra and verification; Pi validates and presents the contract without recomputing it. Expose analysis tools and their product skill only when backend readiness succeeds; retain diagnostics on failure.
- Keep current behavior in the matching `docs/topics/` source and project documentation; update them with behavior and contract changes. Preserve enduring decisions and rationale under the ADR workflow, retiring records only after their still-binding substance has a surviving authoritative home, with Git history retained.
- Preserve unrelated work and repair defects introduced by the current transaction.
- Use Conventional Commits and keep each commit to one concern.

## Workflow

Use `./awf resolve` for global topics, adding repository-relative paths for matching knowledge. Read every returned source and keep affected topics current; `./awf docs topics` owns the detailed workflow.

Use `./awf docs changes` when brainstorming material choices or defining a change's outcome or route, even without a change document. Use `./awf docs adr` when recording or changing enduring decisions.

Use an effort for continuity across stages, sessions, or handoffs and for implementation worktrees; check `./awf effort list` for a matching active effort first. Follow `./awf docs effort`. Read `./awf docs completion` during implementation for verification and commit cadence and before final completion or integration, even without an effort. Native AWF skills provide the same workflows; keep shared methods there rather than duplicating them here.

Use the narrowest relevant test, build, or lint command while editing. Before committing, stage the complete transaction and run `./awf check` and `./scripts/check` manually; this repository does not rely on installed Git hooks. Run the slower release check after AWF render settlement or release-flow changes. Commit completed, verified changes before reporting completion unless instructed otherwise.

`AGENTS.md`, `CLAUDE.md`, and topics are author-owned; edit them directly. After topic or AWF integration changes, run `./awf render`, inspect the diff, and run `./awf check`. AWF generates only its fixed skills and launch infrastructure; use `./awf docs integration` for ownership, CI, and pinned-version updates.

## Commands and references

- `uv run --locked pytest`: Python test suite.
- `./awf render && ./awf check`: refresh and verify fixed AWF outputs and topic validity.
- `./scripts/check`: combined Python, schema, type, lint, format, Pi, and AWF gate.
- `./scripts/check-release`: clean-snapshot installation and Pi readiness verification.
- `docs/vision.md`, `docs/analysis-model.md`, `docs/architecture.md`: purpose, mathematical contract, and component boundaries.
- `docs/development.md`, `docs/testing.md`, `docs/debugging.md`, `docs/releasing.md`: setup, verification, recovery, and release workflow.
- `docs/roadmap.md`, `docs/glossary.md`, `docs/pitfalls.md`: uncommitted future work, terminology, and durable implementation hazards.
