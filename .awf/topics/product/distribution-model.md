---
paths:
  - 'package.json'
  - 'package-lock.json'
  - 'packages/**'
  - 'pyproject.toml'
  - 'uv.lock'
---

# Distribution model

The repository develops independently importable Python analysis packages alongside its aggregate Pi integration.

## Concern-oriented analysis packages

Reusable mathematical analysis capabilities are distributed as independently importable `py-science-<concern>` Python packages. The first, `py-science-formula`, exposes its typed analysis API through `py_science.formula`; its parser, backend-independent expression tree, analysis policy, and bounded SymPy backend remain cohesive internal components. Pi remains the aggregate discovery surface, and its guidance supports both ordinary tool use and direct-Python spikes; complex probes use normal Python composition rather than being forced through tool-call schemas.

## Pinned public source

A compatible repository release snapshot distributes the Pi bridge, product guidance, and Python packages from public Git source. Pi and Python environments pin that snapshot separately; full commit SHAs and resolved locks are immutable, while tags are readable release identifiers.

## Licensing and runtime

Repository Python and Pi packages are distributed under AGPL-3.0-only. The pre-1.0 Python analysis packages support Python 3.13.

## Fail-closed Pi provisioning

Pi eagerly provisions and validates an isolated uv environment from an immutable source revision. It exposes formula tools only after readiness succeeds; failure emits one actionable diagnostic and retains the diagnostic command without analysis tools. Mutable cache and environment state live outside Pi's managed checkout.
