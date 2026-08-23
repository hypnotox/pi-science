Formula analysis responsibilities have one internal owner and explicit dependency direction behind stable compatibility surfaces.

## Claims

### `rule: responsibility-directed-components`
Python contract classes are defined once under `py_science.formula.contracts`; `models.py` and the package root forward the same objects. Neutral `_analysis` owns retained-computation construction and structural-occurrence facts below comparison, optimizer, and service consumers. `_optimization` owns candidate families, replay, proof, objectives, canonical state, search, and plan projection without depending on `_service`; `_service` owns request orchestration, queries, scenarios, dominance dispatch, optimization dispatch, and result bounds. `optimization.py` and `service.py` remain compatibility facades. Pi bridge modules separately own protocol primitives, request and result shapes, diagnostics, correlation, client invocation, and compact presentation; internal production modules import these owners directly through an acyclic graph, while `bridge.ts` remains an outward compatibility barrel and `process.ts` retains subprocess-tree lifecycle. Python alone owns mathematical policy.
Origin: ADR-separate-formula-responsibilities-behind-compatibility-facades
