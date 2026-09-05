---
format: 1
---

# pi-science project guidance

`pi-science` is an active AGPL-3.0 analysis API and Pi package for developers and Pi users who need bounded, qualified reports over strict restricted-SymPy expressions, equation systems, candidate comparisons, dominance, and explicit-goal optimization. The transport-free typed Python implementation lives under `packages/py-science-formula`; the aggregate Pi integration under `packages/pi-science` validates an isolated uv backend from the same pinned public snapshot, exposes the protocol-v17 formula tool and product skill only while ready, and retains diagnostics when provisioning fails.

## Invariants

- Keep public models and mathematical policy backend-independent. Python owns resource-checked algebra and verification; Pi validates and presents the contract without recomputing it.
- Keep current behavior and durable rationale in the matching `.awf/topics/` source and project documentation. Treat decision records as temporary implementation artifacts: after verifying the result and incorporating their durable substance, remove them while preserving their Git history.
- Update documentation with behavior and contract changes.
- Preserve unrelated work and repair defects introduced by the current transaction.
- Use Conventional Commits and keep each commit to one concern.

## Workflow

Use the narrowest relevant test, build, or lint command while editing. Before committing, stage the complete transaction and run `./awf check` and `./scripts/check` manually; this repository does not rely on installed Git hooks. Run the slower release check after AWF render settlement or release-flow changes.

After editing `.awf/project.md` or `.awf/topics/`, run `./awf render`, inspect the generated diff, and run `./awf check`. Generated files carry an AWF ownership marker; edit their source rather than the projection.

## Commands

- `uv run --locked pytest`: Python test suite.
- `./awf render`: regenerate AWF projections.
- `./awf check`: verify AWF projection state.
- `./scripts/check`: combined Python, schema, type, lint, format, Pi, and AWF gate.
- `./scripts/check-release`: clean-snapshot installation and Pi readiness verification.

## Documentation

- `docs/vision.md`: product purpose, scope, and principles.
- `docs/analysis-model.md`: mathematical requests, analysis results, and qualification semantics.
- `docs/architecture.md`: package boundaries, components, dependencies, and data flow.
- `docs/development.md`: local setup and command usage.
- `docs/testing.md`: verification tiers and coverage.
- `docs/debugging.md`: diagnosis and recovery.
- `docs/releasing.md`: release procedure.
- `docs/roadmap.md`: uncommitted future work.
- `docs/glossary.md`: project terminology.
- `docs/pitfalls.md`: durable implementation hazards.
