The formula-analysis flow is:

```text
Pi tool -> readiness gate -> versioned JSON adapter -> py_science.formula -> typed analysis outcome
```

The adapter owns process, timeout, bounded-output, malformed-message, and protocol diagnostics; the Python API remains transport-free. Startup uses `uv run --isolated --no-project` with the immutable repository revision and a user cache, so mutable environments never enter the managed Pi checkout. Failed provisioning withholds analysis surfaces rather than advertising a later-failing capability.
