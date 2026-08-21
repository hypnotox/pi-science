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

## Candidate comparison

Direct Python can compare exactly two explicitly mapped candidates. Semantic equivalence is established before the retained ADR-0003 aggregate abstract-work delta (`second - first`) is qualified; this does not compare scenarios, runtime, machine arithmetic, resource vectors, rewrites, or global optimality.

```python
from py_science.formula import CandidateComparisonRequest, CandidateComputation, CandidateOutputMapping, CandidateTargetReference, ExpressionTarget, FormulaSyntax, compare_candidates

result = compare_candidates(CandidateComparisonRequest(
    syntax=FormulaSyntax.SYMPY,
    candidates=(CandidateComputation(name="first", expression="x + 1"), CandidateComputation(name="second", expression="1 + x")),
    outputs=(CandidateOutputMapping(name="value", targets=(CandidateTargetReference(candidate="first", target=ExpressionTarget()), CandidateTargetReference(candidate="second", target=ExpressionTarget()))),),
))
```

Named systems map an `EquationTarget`; comparison-only bounded expansion follows mapped producer references while each candidate's original reuse-aware graph supplies its work:

```python
from py_science.formula import (
    CandidateComparisonRequest, CandidateComputation, CandidateOutputMapping,
    CandidateTargetReference, EquationRequest, EquationTarget, FormulaSyntax,
    MathematicalDomain, VariableDeclaration, compare_candidates,
)

named = compare_candidates(CandidateComparisonRequest(
    syntax=FormulaSyntax.SYMPY,
    variables={
        "x": VariableDeclaration(domain=MathematicalDomain.REAL),
        "d": VariableDeclaration(domain=MathematicalDomain.REAL),
    },
    candidates=(
        CandidateComputation(name="factored", equations=(
            EquationRequest(name="reciprocal", expression="Eq(r, 1 / d)"),
            EquationRequest(name="value", expression="Eq(y, x * r)"),
        )),
        CandidateComputation(name="direct", equations=(
            EquationRequest(name="value", expression="Eq(z, x / d)"),
        )),
    ),
    outputs=(CandidateOutputMapping(name="value", targets=(
        CandidateTargetReference(candidate="factored", target=EquationTarget(name="value")),
        CandidateTargetReference(candidate="direct", target=EquationTarget(name="value")),
    )),),
))
```

Pi exposes the same bounded request through `analyze_formula`, injects `syntax: sympy`, and returns the canonical comparison report in `details`.

## Bounded queries

General-context `queries` can compare an expression (or a named equation RHS) with one exact rational-expression candidate. Equivalence answers are conservative: identities retain denominator/domain conditions and use declared equalities; a nonidentity is returned only with an exact counterexample. `closed_form` also derives verified candidates for up to eight sibling, nonnested sums of `(a*k+b)*r**k`, with finite integral bounds or a finite integral lower bound and `oo`. It also partially supports one finite-polynomial nested tree (depth four, eight sums, degree eight), such as `Sum(Sum(1, (l, -k, k)), (k, 0, p))`, only when affine integral ranges are proved ordered or empty; its independently checked candidate is informational and never submitted work. Infinite candidates require a proved `Abs(r) < 1`; proved nonzero divergent series are inapplicable, and unsupported or undecidable cases stay unresolved. Candidates are informational, retain convergence and denominator conditions with assumption provenance, and never replace submitted operation counts or work. Exact univariate `properties` reports denominator exclusions, uncancelled poles, factor-sign charts, and real-derivative or integer-forward-difference monotonicity for the bounded rational family. `limit` supports exact finite substitution, directional poles, and polynomial-degree limits at signed infinity. `asymptotic` returns verified bounded Laurent expansions of rational forms in `t = x-c`, `t = 1/x`, or `t = -1/x`, with a structured exact `O(t**n)` remainder. Unsupported reasoning stays unresolved and missing realness is inapplicable. Queries do not run for scenarios or alter scenario work growth.

A query has a unique `name`. `equivalence` supplies `comparison`; `closed_form` supplies no additional operand; `properties` supplies unique `sign`, `valid_domain(variable)`, `singularities(variable)`, or `monotonicity(variable)` checks; `limit` supplies `variable`, point, and finite-point direction; and `asymptotic` adds an order from 1 through 8. Expression queries omit an equation target and system queries select one named RHS with `EquationTarget(kind="equation", name="...")`. An equivalence, properties, limit, or asymptotic query may instead use `target={"kind":"derived","query":"earlier_closed_form"}`. The source must be an earlier proved or proved-under-assumptions closed-form query with checked evidence and exactly one candidate; its conditions and provenance are inherited by every dependent answer. Use this explicit route to analyze a checked canonical nested-polynomial candidate without replacing the submitted sum or its work. If unavailable, the dependent remains inapplicable with `normalized_target: null` and a source blocker, never a submitted-target fallback. Finite query points use the same exact scalar grammar as scenarios; `oo` and `-oo` forbid direction. Answers expose one of `proved`, `proved_under_assumptions`, `disproved`, `unresolved`, or `inapplicable`, alongside conditions, participating assumptions, unsupported relevant facts, blockers, evidence, and source-aware diagnostics for request failures.

For an unresolved query, use its blocker to identify the failed family, exceeded bound, ambiguous axis, or missing supported precondition. When the blocker includes a measured observation and recovery hint, simplify the target, reformulate the question, or select the named supported source family. Recovery hints are conservative: they do not certify that a rewrite is equivalent or promise wider evaluator support.

For the AFMM-style omitted tail, `Sum((k + 1) * q**k, (k, p, oo))` with nonnegative integral `p`, real `q`, and global `0 <= q`, `q < 1` assumptions can request `ClosedFormQuery(name="afmm_tail")`. Its qualified candidate is informational: it never changes submitted operation counts or direct work, and the infinite submitted sum still has no finite work count. Scenarios intentionally do not execute queries. Restricted LaTeX input, scenario-context queries, complex values, dimensions, vector shorthand, differentiation, numerical approximation, and general theorem proving remain outside this initial contract.

## Aggregate-work dominance

`analyze_dominance` is a separate Python operation, also available through Pi's `analyze_formula` tool, over original retained aggregate abstract work. It orders canonical signed `power:<p>` terms by absolute magnitude only within its active domain; signed corrections are not negative work, and dominance is neither runtime importance nor a rewrite, candidate-ranking, scenario, or global-relevance claim.

```python
from py_science.formula import DominanceAnalysisRequest, FormulaSyntax, MathematicalDomain, PrimitiveCost, VariableDeclaration, analyze_dominance

correction = analyze_dominance(DominanceAnalysisRequest(
    syntax=FormulaSyntax.SYMPY, expression="work(n)", axis="n",
    variables={"n": VariableDeclaration(domain=MathematicalDomain.POSITIVE_INTEGER)},
    primitive_costs=(PrimitiveCost(name="work", parameters=("n",), work="n**2 - n + 1"),),
))
assert [term.id for term in correction.terms] == ["power:2", "power:1", "power:0"]
assert correction.cells[-1].dominant == ("power:2",)
```

```python
from py_science.formula import DominanceAnalysisRequest, FormulaSyntax, MathematicalDomain, PrimitiveCost, VariableDeclaration, analyze_dominance

pole_scope = analyze_dominance(DominanceAnalysisRequest(
    syntax=FormulaSyntax.SYMPY, expression="work(n)", axis="n",
    variables={"n": VariableDeclaration(domain=MathematicalDomain.REAL)},
    primitive_costs=(PrimitiveCost(name="work", parameters=("n",), work="1 / (n - 1)"),),
))
assert pole_scope.shared_denominator == "n - 1"
assert [pole.value for pole in pole_scope.exclusions] == ["1"]
```

## Bounded local optimization advice

Ordinary `AnalysisRequest` accepts the frozen `OptimizationConfig(max_suggestions=...)` only. The strict range is `0..16`, the default is `3`, and the value is an upper bound; zero returns a disabled empty report. Candidate-comparison and dominance request models have no optimization setting. A `complete` report may contain fewer suggestions than requested, including none. An `incomplete` report identifies bounded search exhaustion, preserves already proved suggestions, and does not establish that no other improvement exists.

The shipped Python generators cover repeated-subexpression extraction, identical-call and reciprocal reuse, bounded checked factoring, redundant-operation removal, iterator-invariant hoisting, compatible sharing across named equation RHSs, and bounded Horner form. Shared producers require one compatible positional free-index interface and acyclic placement. Horner uses fixed target-node, variable, degree, term, and generated-node ceilings. Every generated candidate goes through one verifier: generated intermediates are expanded by checked substitution for output equivalence, every transformed retained output is proved under declared assumptions and domains, and whole-computation aggregate abstract work includes iterator cardinality, output multiplicity, and intermediate scope. Unknown costs, unresolved cardinality or proof, incompatible scopes, capture, nonpositive savings, and incomparable work are omitted.

```python
factored = analyze(AnalysisRequest(
    syntax=FormulaSyntax.SYMPY,
    expression="x*y + x*z",
))
assert factored.status == "success"
assert factored.optimization is not None
assert factored.optimization.suggestions[0].transformations[0].proposed.normalized_sympy == "x*(y + z)"
assert factored.optimization.suggestions[0].savings == "1"
```

Every suggestion has a nonempty tuple of unique target-local transformations. Each transformation owns its target, deterministic child-index occurrence paths, binders and output indices, and normalized original and proposed forms. Atomic cross-equation sharing includes one transformation for every affected equation, including renamed compatible indices. Optional collision-free intermediates, exact identity evidence, conditions and assumptions, before/after work, positive savings, and the `exact_symbolic_only` finite-precision qualification remain suggestion-level. Pi's compact projection presents the best proved suggestion's complete transformation set and names additional suggestions in canonical `details`; it never invents a primary target. Advice is informational and never changes the retained interpretation, counts, work, scenarios, queries, dependencies, reuse, or extraction diagnostics. Exact-symbolic equivalence is not a runtime, numerical-stability, or identical floating-point evaluation claim.
