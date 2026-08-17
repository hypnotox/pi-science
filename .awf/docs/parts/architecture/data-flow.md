The formula-analysis flow is:

```text
strict Pi expression/system request -> readiness gate -> bounded versioned JSON adapter -> py_science.formula -> validated qualified report
```

Pi injects restricted-SymPy syntax and translates the public formula contract without owning mathematical policy. The adapter owns whole-envelope and serialized-output bounds; the TypeScript bridge owns process, timeout, cancellation, cleanup, malformed-message, response-shape, and protocol diagnostics. The Python API remains transport-free and owns mathematical validation and analysis. Startup uses `uv run --isolated --no-project` with the immutable repository revision and a user cache, so mutable environments never enter the managed Pi checkout. Failed provisioning withholds the tool and product skill together rather than advertising a later-failing capability.
