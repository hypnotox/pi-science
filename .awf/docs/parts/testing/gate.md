Run `./scripts/check` before every commit. It runs, in order:

1. pytest formula-analysis end-to-end behavior and safety checks;
2. Pyright strict static type checking;
3. Ruff source linting;
4. `./awf check` for repository authority and generated-output drift.

The script uses the locked uv environment and stops at the first failure.
