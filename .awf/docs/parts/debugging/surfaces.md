Reproduce formula-analysis behavior through the public end-to-end suite:

```bash
uv run --locked pytest tests/e2e/test_formula_analysis.py -q
```

A submitted formula returns a typed `AnalysisFailure` for malformed, unsupported, or resource-limited syntax; it does not raise a parser exception through the public boundary. Complexity messages name public byte, nesting, or integer limits when actionable and keep internal structural exhaustion generic. Inspect `packages/py-science-formula/src/py_science/formula/parser.py` for grammar decisions, `packages/py-science-formula/src/py_science/formula/sympy_backend.py` for normalized rendering, and `packages/py-science-formula/src/py_science/formula/service.py` for boundary translation.

Run `./scripts/check` for application, typing, lint, and awf failures. Use `./awf check` alone for generated drift or repository-rule diagnosis and follow its emitted repair hint.
