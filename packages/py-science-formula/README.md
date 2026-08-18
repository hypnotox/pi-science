# py-science-formula

`py-science-formula` is the independently importable Python 3.13, AGPL-3.0-only formula-analysis distribution from `pi-science`. It safely parses restricted SymPy expressions and named indexed equation systems, then reports normalized SymPy and LaTeX, symbolic work, dependency reuse, provenance, scenarios, and unresolved costs. It does not evaluate a submitted formula, benchmark application performance, or generate code; formula-to-code remains open but out of scope. Decimal literals are exact reduced rational values (for example `1.50` is `3/2`), not floating-point approximations. The reserved spellings `oo` and `-oo` represent mathematical infinity; an infinite iterator remains structural but has no finite direct-evaluation work.

Pin a compatible repository ref directly in the Python environment (independently of a Pi package pin):

```toml
dependencies = ["py-science-formula @ git+https://github.com/hypnotox/pi-science.git@<full-commit-sha>#subdirectory=packages/py-science-formula"]
```

Use a full SHA for immutable adoption; a readable release tag is convenient but should be locked to its resolved commit.

```python
from py_science.formula import AnalysisRequest, FormulaSyntax, analyze

result = analyze(AnalysisRequest(syntax=FormulaSyntax.SYMPY, expression="x + 1"))
```

Choose one expression for an isolated calculation. Choose named equations when results have local output domains or downstream formulas reuse them. Every free output index needs an `IndexDomain`; every external symbol needs an intrinsic `VariableDeclaration`. Output bounds may reference other output indices when the inferred graph is acyclic and each dependent bound is an affine integer sum; LHS order still defines coordinate order and only breaks dependency-order ties. A named equation-local `DomainConstraint` with `name`, `target`, and `relationship` may tighten a finite base domain through the supported integer-affine and absolute upper-bound family; reports retain submitted constraints, effective domains, and equation-qualified uses. Constraints never define a domain or apply request-wide. Self/cyclic dependencies and dependent calls, indexed values, symbolic products, powers, division, or aggregate operators are rejected. Independent bounds keep their existing accepted family. Represent vectors through indexed scalar components such as `x[i, d]`.

The restricted parser accepts exact integer and decimal literals, ordinary symbols, arithmetic `+`, `-`, `*`, `/`, and `**`, indexed scalars, ordinary positional calls, one-limit inclusive `Sum(body, (index, lower, upper))`, `Eq(lhs, rhs)`, single relationships, and signed infinity `oo` or `-oo`. It rejects unrestricted Python or SymPy, including `Product`, submitted `Max`, attributes, keyword calls, chained relationships, and sums with more than one limit. A generic call can parse while still having no definition, cost, or bounded query semantics; parsing, request-context validation, and evaluator applicability are separate Python-owned checks.

This compact request analyzes a reusable indexed result under a fixed-order scenario:

```python
from py_science.formula import (
    AnalysisRequest, EquationRequest, FormulaSyntax, IndexDomain,
    MathematicalDomain, PrimitiveCost, Scenario, VariableDeclaration, analyze,
)

positive = VariableDeclaration(domain=MathematicalDomain.POSITIVE_INTEGER)
real = VariableDeclaration(domain=MathematicalDomain.REAL)
report = analyze(AnalysisRequest(
    syntax=FormulaSyntax.SYMPY,
    equations=(
        EquationRequest(
            name="samples",
            expression="Eq(S[i], x[i] - center)",
            domains={"i": IndexDomain(lower="0", upper="N - 1")},
        ),
        EquationRequest(
            name="summary",
            expression="Eq(T[k], Sum(basis(S[i], k), (i, 0, N - 1)))",
            domains={"k": IndexDomain(lower="0", upper="p - 1")},
        ),
    ),
    variables={"N": positive, "p": positive, "x": real, "center": real},
    primitive_costs=(
        PrimitiveCost(name="basis", parameters=("value", "k"), work="k + 1"),
    ),
    scenarios=(Scenario(name="fixed_order", fixed={"p": 4}, asymptotic=("N",)),),
))
```

Use `FunctionDefinition` when a function's mathematical body is known. Use `PrimitiveCost` only when the body is intentionally opaque but scalar work is known. Leave both absent to preserve an explicit unknown cost. Nested finite direct work is exact symbolic work: dependent output domains aggregate from inner to outer in reverse dependency order, bounded affine work sums close when proved, and otherwise iterator-dependent fields retain lexical `Sum` binders rather than leaking iterators. Unproved cardinality, ordering, or finiteness remains explicitly unresolved. Submitted affine relationships used for domain ordering appear in provenance. This direct-work behavior is distinct from the partial nested mathematical closed-form family described below and does not itself prove a candidate. Assumptions and directed definitions are explicit mathematical knowledge; scenarios select fixed values, finite choices, bounds, derived values, or asymptotic variables without changing the general report. Scenario scalars accept JavaScript-safe JSON integers or exact scalar strings such as `1/2` and `1.20`; they are reduced and serialized canonically (for example, `1.20` becomes `6/5`). Bounds have finite exact `lower` and `upper` endpoints and optional inclusive flags (both default to closed); open real intervals report conservative infimum/supremum and whether either is attained. Scenario values and intervals must remain consistent with declared domains and applicable global assumptions.

Inspect each normalized SymPy and LaTeX interpretation before using submitted counts, aggregate work, dependency reuse, relationship provenance, scenario qualifications, unknown costs, or unresolved conclusions. The API analyzes formulas and attached mathematical schema only. It does not read source code, validate physical correctness, profile an implementation, predict runtime or hardware behavior, or generate code.

For a one-off PEP 723 probe, put the same Git-subdirectory dependency in script metadata and invoke `uv run probe.py`. Never import from Pi's isolated backend or from `pi_science`.

## Bounded queries

General-context `queries` can compare an expression (or a named equation RHS) with one exact rational-expression candidate. Equivalence answers are conservative: identities retain denominator/domain conditions and use declared equalities; a nonidentity is returned only with an exact counterexample. `closed_form` also derives verified candidates for up to eight sibling, nonnested sums of `(a*k+b)*r**k`, with finite integral bounds or a finite integral lower bound and `oo`. It also partially supports one finite-polynomial nested tree (depth four, eight sums, degree eight), such as `Sum(Sum(1, (l, -k, k)), (k, 0, p))`, only when affine integral ranges are proved ordered or empty; its independently checked candidate is informational and never submitted work. Infinite candidates require a proved `Abs(r) < 1`; proved nonzero divergent series are inapplicable, and unsupported or undecidable cases stay unresolved. Candidates are informational, retain convergence and denominator conditions with assumption provenance, and never replace submitted operation counts or work. Exact univariate `properties` reports denominator exclusions, uncancelled poles, factor-sign charts, and real-derivative or integer-forward-difference monotonicity for the bounded rational family. `limit` supports exact finite substitution, directional poles, and polynomial-degree limits at signed infinity. `asymptotic` returns verified bounded Laurent expansions of rational forms in `t = x-c`, `t = 1/x`, or `t = -1/x`, with a structured exact `O(t**n)` remainder. Unsupported reasoning stays unresolved and missing realness is inapplicable. Queries do not run for scenarios or alter scenario work growth.

A query has a unique `name`. `equivalence` supplies `comparison`; `closed_form` supplies no additional operand; `properties` supplies unique `sign`, `valid_domain(variable)`, `singularities(variable)`, or `monotonicity(variable)` checks; `limit` supplies `variable`, point, and finite-point direction; and `asymptotic` adds an order from 1 through 8. Expression queries omit an equation target and system queries select one named RHS with `EquationTarget(kind="equation", name="...")`. An equivalence or limit may instead use `target={"kind":"derived","query":"earlier_closed_form"}`. The source must be an earlier proved or proved-under-assumptions closed-form query with checked evidence and exactly one candidate; its conditions and provenance are inherited. If unavailable, the dependent remains inapplicable with `normalized_target: null` and a source blocker, never a submitted-target fallback. Finite query points use the same exact scalar grammar as scenarios; `oo` and `-oo` forbid direction. Answers expose one of `proved`, `proved_under_assumptions`, `disproved`, `unresolved`, or `inapplicable`, alongside conditions, participating assumptions, unsupported relevant facts, blockers, evidence, and source-aware diagnostics for request failures.

For an unresolved query, use its blocker to identify the failed family, exceeded bound, ambiguous axis, or missing supported precondition. When the blocker includes a measured observation and recovery hint, simplify the target, reformulate the question, or select the named supported source family. Recovery hints are conservative: they do not certify that a rewrite is equivalent or promise wider evaluator support.

For the AFMM-style omitted tail, `Sum((k + 1) * q**k, (k, p, oo))` with nonnegative integral `p`, real `q`, and global `0 <= q`, `q < 1` assumptions can request `ClosedFormQuery(name="afmm_tail")`. Its qualified candidate is informational: it never changes submitted operation counts or direct work, and the infinite submitted sum still has no finite work count. Scenarios intentionally do not execute queries. Restricted LaTeX input, scenario-context queries, complex values, dimensions, vector shorthand, differentiation, numerical approximation, and general theorem proving remain outside this initial contract.
