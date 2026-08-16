The repository develops independently importable Python analysis packages alongside its future Pi integration.

## Claims

### `rule: concern-oriented-analysis-packages`
Reusable mathematical analysis capabilities are distributed as independently importable `py-science-<concern>` Python packages. The first, `py-science-formula`, exposes its typed analysis API through `py_science.formula`; its parser, backend-independent expression tree, analysis policy, and SymPy renderer remain cohesive internal components.
Origin: ADR-separate-reusable-analysis-packages-from-pi-integration

### `rule: agpl-only`
Repository Python and Pi packages are distributed under AGPL-3.0-only.
Origin: ADR-separate-reusable-analysis-packages-from-pi-integration

### `rule: python-313-runtime`
The pre-1.0 Python analysis packages support Python 3.13.
Origin: ADR-separate-reusable-analysis-packages-from-pi-integration
