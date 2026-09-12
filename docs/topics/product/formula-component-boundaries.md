---
paths:
  - 'packages/py-science-formula/src/py_science/formula/**'
  - 'packages/pi-science/src/**'
---

# Formula component boundaries

Formula analysis responsibilities have one internal owner and explicit dependency direction behind stable compatibility surfaces.

Python contract classes are defined once under `py_science.formula.contracts`; `models.py` and the package root forward the same objects. Neutral `_analysis` owns retained-computation construction and structural-occurrence facts below comparison, optimizer, and service consumers so mathematical and scope policy cannot diverge or recreate a service-to-optimizer cycle. `_optimization` owns candidate families, replay, proof, objectives, canonical state, search, and plan projection without depending on `_service`; `_service` owns request orchestration, queries, scenarios, dominance dispatch, optimization dispatch, and result bounds. `optimization.py` and `service.py` remain compatibility facades because forwarding the same objects preserves class identity, schema, and transport behavior while internals move. Pi bridge modules separately own protocol primitives, request and result shapes, diagnostics, correlation, client invocation, and compact presentation; internal production modules import these owners directly through an acyclic graph, while `bridge.ts` remains an outward compatibility barrel and `process.ts` retains subprocess-tree lifecycle. Python alone owns mathematical policy.
