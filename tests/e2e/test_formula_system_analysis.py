# ruff: noqa: E501
# pyright: basic, reportArgumentType=false, reportOptionalMemberAccess=false, reportOptionalSubscript=false, reportAttributeAccessIssue=false, reportOperatorIssue=false, reportCallIssue=false, reportUnknownMemberType=false, reportUnknownVariableType=false
from types import SimpleNamespace
from typing import Any, cast

import py_science.formula.reasoning as formula_reasoning
import py_science.formula.service as formula_service
import py_science.formula.work as formula_work
import pytest
from py_science.formula import (
    AnalysisRequest,
    AnalysisSuccess,
    Assumption,
    ClosedFormQuery,
    EquationRequest,
    EquationTarget,
    EquivalenceQuery,
    FormulaSyntax,
    FunctionDefinition,
    IndexDomain,
    MathematicalDomain,
    PrimitiveCost,
    Scenario,
    VariableDeclaration,
    analyze,
)
from py_science.formula.domains import build_output_domains
from py_science.formula.expressions import IntegerLiteral, Relationship, Sum, Symbol
from py_science.formula.parser import parse_expression
from pydantic import ValidationError
from sympy import Max, simplify, sympify  # type: ignore[import-untyped]
from sympy import Sum as SympySum  # type: ignore[import-untyped]


def variables(*names: str) -> dict[str, VariableDeclaration]:
    return {
        name: VariableDeclaration(domain=MathematicalDomain.NONNEGATIVE_INTEGER) for name in names
    }


def test_named_rhs_query_is_local_and_preserves_system_work() -> None:
    base = AnalysisRequest(
        syntax=FormulaSyntax.SYMPY,
        equations=(EquationRequest(name="value", expression="Eq(y, x + 1)"),),
        variables=variables("x", "y"),
    )
    baseline = analyze(base)
    queried = analyze(
        AnalysisRequest(
            syntax=FormulaSyntax.SYMPY,
            equations=base.equations,
            variables=base.variables,
            queries=(
                EquivalenceQuery(
                    name="same",
                    target=EquationTarget(name="value"),
                    comparison="1 + x",
                ),
            ),
        )
    )
    assert isinstance(baseline, AnalysisSuccess)
    assert isinstance(queried, AnalysisSuccess)
    assert baseline.system is not None and queried.system is not None
    assert queried.system.total_work == baseline.system.total_work
    assert queried.system.equations == baseline.system.equations
    assert queried.queries[0].answers[0].conclusion == "proved"


def test_named_rhs_asymptotic_query_is_local_and_preserves_system_work() -> None:
    base = AnalysisRequest(
        syntax=FormulaSyntax.SYMPY,
        equations=(EquationRequest(name="value", expression="Eq(y, (x + 1)/(x - 1))"),),
        variables={"x": VariableDeclaration(domain=MathematicalDomain.REAL)},
    )
    baseline = analyze(base)
    queried = analyze(AnalysisRequest(
        syntax=FormulaSyntax.SYMPY,
        equations=base.equations,
        variables=base.variables,
        queries=({"name": "tail", "kind": "asymptotic", "target": {"kind": "equation", "name": "value"}, "variable": "x", "point": "oo", "order": 2},),
    ))
    assert isinstance(baseline, AnalysisSuccess) and isinstance(queried, AnalysisSuccess)
    assert baseline.system is not None and queried.system is not None
    assert queried.system.total_work == baseline.system.total_work
    evidence = queried.queries[0].answers[0].evidence
    assert evidence is not None and evidence.kind == "asymptotic"


def test_named_rhs_property_query_is_local_to_the_selected_equation() -> None:
    outcome = analyze(AnalysisRequest(
        syntax=FormulaSyntax.SYMPY,
        equations=(EquationRequest(name="value", expression="Eq(y, 1/(x - 1))"),),
        variables={"x": VariableDeclaration(domain=MathematicalDomain.REAL)},
        queries=({"name": "properties", "kind": "properties", "target": {"kind": "equation", "name": "value"}, "checks": ({"kind": "singularities", "variable": "x"},)},),
    ))
    assert isinstance(outcome, AnalysisSuccess)
    assert outcome.system is not None and outcome.queries[0].target.name == "value"
    assert "pole of order 1" in outcome.queries[0].answers[0].evidence.value


def test_named_rhs_closed_form_query_is_local_to_the_selected_equation() -> None:
    outcome = analyze(AnalysisRequest(
        syntax=FormulaSyntax.SYMPY,
        equations=(EquationRequest(name="tail", expression="Eq(y, Sum(k * 2**k, (k, 0, 3)))"),),
        queries=(ClosedFormQuery(name="closed", target=EquationTarget(name="tail")),),
    ))
    assert isinstance(outcome, AnalysisSuccess)
    assert outcome.queries[0].answers[0].conclusion == "proved_under_assumptions"
    assert outcome.system is not None and outcome.system.equations[0].aggregate_work is not None


def test_system_derived_target_reuses_named_closed_form_without_changing_work() -> None:
    base = AnalysisRequest(
        syntax=FormulaSyntax.SYMPY,
        equations=(EquationRequest(name="tail", expression="Eq(y, Sum(k * 2**k, (k, 0, 3)))"),),
    )
    baseline = analyze(base)
    outcome = analyze(AnalysisRequest(
        syntax=FormulaSyntax.SYMPY, equations=base.equations,
        queries=(
            {"name": "closed", "kind": "closed_form", "target": {"kind": "equation", "name": "tail"}},
            {"name": "same", "kind": "equivalence", "target": {"kind": "derived", "query": "closed"}, "comparison": "34"},
            {"name": "limit", "kind": "limit", "target": {"kind": "derived", "query": "closed"}, "variable": "x", "point": "oo"},
        ),
    ))
    assert isinstance(baseline, AnalysisSuccess) and isinstance(outcome, AnalysisSuccess)
    assert baseline.system == outcome.system
    assert outcome.queries[1].normalized_target is not None
    assert outcome.queries[1].answers[0].conclusion == "proved_under_assumptions"
    assert outcome.queries[2].normalized_target is not None


def test_named_rhs_nested_closed_form_preserves_system_work_and_reuses_candidate() -> None:
    equations = (
        EquationRequest(
            name="coefficient",
            expression="Eq(c, Sum(Sum(1, (l, -k, k)), (k, 0, p)))",
        ),
    )
    declared = {"p": VariableDeclaration(domain=MathematicalDomain.NONNEGATIVE_INTEGER)}
    baseline = analyze(AnalysisRequest(
        syntax=FormulaSyntax.SYMPY, equations=equations, variables=declared
    ))
    outcome = analyze(AnalysisRequest(
        syntax=FormulaSyntax.SYMPY,
        equations=equations,
        variables=declared,
        queries=(
            {"name": "closed", "kind": "closed_form", "target": {"kind": "equation", "name": "coefficient"}},
            {"name": "same", "kind": "equivalence", "target": {"kind": "derived", "query": "closed"}, "comparison": "(p + 1)**2"},
        ),
    ))
    assert isinstance(baseline, AnalysisSuccess) and isinstance(outcome, AnalysisSuccess)
    assert outcome.system == baseline.system
    assert outcome.queries[0].answers[0].conclusion == "proved"
    assert outcome.queries[1].answers[0].conclusion == "proved"
    assert outcome.queries[1].normalized_target is not None
    assert outcome.queries[1].normalized_target.normalized_sympy == "2*p + 1 + p**2"


def test_named_indexed_equations_reuse_producer_and_sum_work() -> None:
    outcome = analyze(
        AnalysisRequest(
            syntax=FormulaSyntax.SYMPY,
            equations=(
                EquationRequest(
                    name="m",
                    expression="Eq(M[b], Sum(x[i] * y[i], (i, 0, n - 1)))",
                    domains={"b": IndexDomain(lower="0", upper="B - 1")},
                ),
                EquationRequest(
                    name="l",
                    expression="Eq(L[b], M[b] + M[b])",
                    domains={"b": IndexDomain(lower="0", upper="B - 1")},
                ),
            ),
            variables=variables("B", "n", "x", "y"),
        )
    )
    assert outcome.status == "success"
    assert outcome.system is not None
    assert [equation.name for equation in outcome.system.equations] == ["m", "l"]
    assert outcome.system.dependency_edges == (("m", "l"),)
    assert outcome.system.reuse[0].model_dump() == {
        "producer": "m",
        "consumer": "l",
        "references": 2,
    }
    assert outcome.system.equations[0].aggregate_work is not None
    assert "Max" in outcome.system.equations[0].aggregate_work
    assert outcome.system.extraction_opportunities == ()


def assert_iterators_are_lexically_bound(rendered: str) -> None:
    parsed = cast(Any, sympify(rendered))
    assert {symbol.name for symbol in parsed.free_symbols}.isdisjoint({"j", "k"})

    def visit(node: Any, bound: frozenset[str] = frozenset()) -> None:
        if node.func is Max:
            assert {symbol.name for symbol in node.free_symbols}.isdisjoint({"j", "k"} - bound)
        if isinstance(node, SympySum):
            body, *limits = cast(tuple[Any, ...], node.args)
            iterators = frozenset(str(limit[0]) for limit in limits)
            visit(body, bound | iterators)
            for limit in limits:
                for endpoint in limit[1:]:
                    visit(endpoint, bound)
            return
        for child in cast(tuple[Any, ...], node.args):
            visit(child, bound)

    visit(parsed)


def test_nested_sum_work_keeps_iterators_lexically_bound() -> None:
    outcome = analyze(
        AnalysisRequest(
            syntax=FormulaSyntax.SYMPY,
            expression="Sum(Sum(x[j] + primitive(k), (j, k, n)), (k, 0, p - 1))",
            variables=variables("n", "p", "x"),
            primitive_costs=(PrimitiveCost(name="primitive", parameters=("value",), work="value"),),
            queries=(ClosedFormQuery(name="nested"),),
        )
    )

    assert isinstance(outcome, AnalysisSuccess)
    assert outcome.system is not None
    assert outcome.queries[0].answers[0].conclusion == "unresolved"
    assert "nested" in " ".join(outcome.queries[0].answers[0].blockers)
    values = (
        *outcome.system.aggregate_operation_counts.model_dump().values(),
        outcome.system.total_work,
        outcome.system.equations[0].aggregate_work,
        *outcome.system.primitive_invocations.values(),
    )
    for rendered in values:
        assert rendered is not None
        assert_iterators_are_lexically_bound(rendered)


def test_sum_work_handles_empty_one_term_nested_and_symbolic_domains() -> None:
    empty = analyze(AnalysisRequest(syntax=FormulaSyntax.SYMPY, expression="Sum(x[i], (i, 2, 1))"))
    one = analyze(AnalysisRequest(syntax=FormulaSyntax.SYMPY, expression="Sum(x[i], (i, 2, 2))"))
    nested = analyze(
        AnalysisRequest(
            syntax=FormulaSyntax.SYMPY,
            expression="Sum(Sum(x[i, j] + 1, (j, 0, m - 1)), (i, 0, n - 1))",
            variables=variables("m", "n", "x"),
        )
    )
    assert empty.status == "success"
    assert empty.system is not None
    assert one.status == "success"
    assert one.system is not None
    assert nested.status == "success"
    assert nested.system is not None
    assert empty.system.total_work == "0"
    assert one.system.total_work == "0"
    assert nested.system.total_work is not None
    assert "Max" in nested.system.total_work


def test_nonintegral_sum_bounds_remain_explicitly_unresolved() -> None:
    outcome = analyze(
        AnalysisRequest(
            syntax=FormulaSyntax.SYMPY,
            expression="Sum(x[i] + 1, (i, a, b))",
            variables={
                "a": VariableDeclaration(domain=MathematicalDomain.REAL),
                "b": VariableDeclaration(domain=MathematicalDomain.REAL),
                "x": VariableDeclaration(domain=MathematicalDomain.REAL),
            },
        )
    )
    assert outcome.status == "success"
    assert outcome.system is not None
    assert outcome.system.total_work is not None
    assert "cardinality" in outcome.system.total_work
    assert outcome.system.unresolved == ("sum index i cardinality requires integral bounds",)


def test_function_definitions_primitive_work_and_unknown_costs_are_distinct() -> None:
    outcome = analyze(
        AnalysisRequest(
            syntax=FormulaSyntax.SYMPY,
            expression="defined(x) + primitive(n) + opaque(x)",
            variables=variables("n", "x"),
            functions=(FunctionDefinition(name="defined", parameters=("z",), body="z * z"),),
            primitive_costs=(PrimitiveCost(name="primitive", parameters=("k",), work="2 * k + 1"),),
        )
    )
    assert outcome.status == "success"
    assert outcome.system is not None
    assert outcome.system.primitive_invocations == {"primitive": "1"}
    assert outcome.system.unknown_costs == ("C_opaque",)
    assert outcome.system.unresolved == ("unknown cost for opaque",)
    assert outcome.system.total_work == "2*n + C_opaque(x) + 4"


def test_function_contract_rejects_arity_conflicts_and_recursion() -> None:
    arity = analyze(
        AnalysisRequest(
            syntax=FormulaSyntax.SYMPY,
            expression="f(x, y)",
            functions=(FunctionDefinition(name="f", parameters=("z",), body="z + 1"),),
        )
    )
    recursive = analyze(
        AnalysisRequest(
            syntax=FormulaSyntax.SYMPY,
            expression="f(x)",
            functions=(FunctionDefinition(name="f", parameters=("z",), body="f(z)"),),
        )
    )
    assert arity.status == "failure"
    assert arity.error.message == "function f requires 1 arguments"
    assert recursive.status == "failure"
    assert recursive.error.message == "function definitions contain a cycle"
    with pytest.raises(ValidationError):
        AnalysisRequest(
            syntax=FormulaSyntax.SYMPY,
            expression="f(x)",
            functions=(FunctionDefinition(name="f", parameters=("z",), body="z"),),
            primitive_costs=(PrimitiveCost(name="f", parameters=("z",), work="1"),),
        )


def test_system_validation_rejects_duplicate_results_cycles_and_bad_indices() -> None:
    duplicate = analyze(
        AnalysisRequest(
            syntax=FormulaSyntax.SYMPY,
            equations=(
                EquationRequest(name="a", expression="Eq(X, 1)"),
                EquationRequest(name="b", expression="Eq(X, 2)"),
            ),
        )
    )
    cycle = analyze(
        AnalysisRequest(
            syntax=FormulaSyntax.SYMPY,
            equations=(
                EquationRequest(
                    name="a",
                    expression="Eq(A[i], B[i])",
                    domains={"i": IndexDomain(lower="0", upper="N")},
                ),
                EquationRequest(
                    name="b",
                    expression="Eq(B[i], A[i])",
                    domains={"i": IndexDomain(lower="0", upper="N")},
                ),
            ),
            variables=variables("N"),
        )
    )
    unbound = analyze(
        AnalysisRequest(
            syntax=FormulaSyntax.SYMPY,
            equations=(
                EquationRequest(
                    name="a",
                    expression="Eq(A[i], x[j])",
                    domains={"i": IndexDomain(lower="0", upper="N")},
                ),
            ),
            variables=variables("N", "x"),
        )
    )
    shadowed = analyze(
        AnalysisRequest(
            syntax=FormulaSyntax.SYMPY,
            equations=(
                EquationRequest(
                    name="a",
                    expression="Eq(A[i], Sum(x[i], (i, 0, N)))",
                    domains={"i": IndexDomain(lower="0", upper="N")},
                ),
            ),
            variables=variables("N", "x"),
        )
    )
    for outcome in (duplicate, cycle, unbound, shadowed):
        assert outcome.status == "failure"


def test_dependent_output_domains_preserve_lhs_order_and_close_triangular_work() -> None:
    triangular = analyze(
        AnalysisRequest(
            syntax=FormulaSyntax.SYMPY,
            equations=(
                EquationRequest(
                    name="a",
                    expression="Eq(A[n, m], x + 1)",
                    domains={
                        "n": IndexDomain(lower="0", upper="p"),
                        "m": IndexDomain(lower="-n", upper="n"),
                    },
                ),
            ),
            variables=variables("p", "x"),
            scenarios=(Scenario(name="p12", fixed={"p": 12}), Scenario(name="p20", fixed={"p": 20})),
        )
    )
    reversed_order = analyze(
        AnalysisRequest(
            syntax=FormulaSyntax.SYMPY,
            equations=(
                EquationRequest(
                    name="b",
                    expression="Eq(B[i, j], x + 1)",
                    domains={
                        "i": IndexDomain(lower="0", upper="j"),
                        "j": IndexDomain(lower="0", upper="N"),
                    },
                ),
            ),
            variables=variables("N", "x"),
        )
    )
    assert triangular.status == "success"
    assert triangular.system is not None
    report = triangular.system.equations[0]
    assert report.interpretation.normalized_sympy.startswith("Eq(A[n, m]")
    assert report.aggregate_work == "(p + 1)**2"
    assert triangular.system.total_work == "(p + 1)**2"
    assert [item.substituted_work for item in triangular.scenarios] == ["169", "441"]
    assert all(name not in triangular.system.total_work for name in ("Max", "Sum"))
    assert reversed_order.status == "success"
    assert reversed_order.system is not None
    assert reversed_order.system.equations[0].interpretation.normalized_sympy.startswith("Eq(B[i, j]")
    assert reversed_order.system.total_work == "(N + 1)*(N + 2)/2"


def test_dependent_output_domain_cycles_and_non_affine_bounds_are_local_errors() -> None:
    requests = (
        ({"i": IndexDomain(lower="0", upper="i")}, "domains.i.upper"),
        ({"i": IndexDomain(lower="0", upper="j"), "j": IndexDomain(lower="0", upper="i")}, "domains"),
        ({"i": IndexDomain(lower="0", upper="f(j)"), "j": IndexDomain(lower="0", upper="N")}, "domains.i.upper"),
        ({"i": IndexDomain(lower="0", upper="j**2"), "j": IndexDomain(lower="0", upper="N")}, "domains.i.upper"),
    )
    for domains, path in requests:
        indices = ", ".join(domains)
        outcome = analyze(AnalysisRequest(
            syntax=FormulaSyntax.SYMPY,
            equations=(EquationRequest(name="bad", expression=f"Eq(A[{indices}], x)", domains=domains),),
            variables=variables("N", "x"),
        ))
        assert outcome.status == "failure"
        location = outcome.error.source.path if outcome.error.source is not None else outcome.error.message
        assert path in location or "output-domain bounds cannot depend" in outcome.error.message


def test_unsupported_inequality_is_preflighted_before_sympy_conversion(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    relationship = parse_expression("h**2 <= sigma**2")
    assert isinstance(relationship, Relationship)
    item = SimpleNamespace(
        name="nonlinear",
        source="h**2 <= sigma**2",
        value=relationship,
    )

    def forbidden_conversion(_expression: object) -> object:
        raise AssertionError("unsupported inequality reached SymPy conversion")

    monkeypatch.setattr(formula_reasoning, "_to_sympy", forbidden_conversion)
    context = formula_reasoning.ReasoningContext.build({}, (), (item,))
    assert context.unsupported == (("nonlinear", frozenset({"h", "sigma"})),)


def test_affine_domain_ordering_uses_named_relationship_provenance() -> None:
    qualified = analyze(AnalysisRequest(
        syntax=FormulaSyntax.SYMPY,
        equations=(EquationRequest(
            name="c",
            expression="Eq(C[i], x[i] + 1)",
            domains={"i": IndexDomain(lower="0", upper="sigma - h")},
        ),),
        variables={
            "h": VariableDeclaration(domain=MathematicalDomain.NONNEGATIVE_INTEGER),
            "sigma": VariableDeclaration(domain=MathematicalDomain.NONNEGATIVE_INTEGER),
            "x": VariableDeclaration(domain=MathematicalDomain.REAL),
        },
        assumptions=(Assumption(name="h_le_sigma", relationship="2*h <= 2*sigma"),),
    ))
    unresolved = analyze(AnalysisRequest(
        syntax=FormulaSyntax.SYMPY,
        equations=(EquationRequest(
            name="c",
            expression="Eq(C[i], x[i] + 1)",
            domains={"i": IndexDomain(lower="0", upper="sigma - h")},
        ),),
        variables={
            "h": VariableDeclaration(domain=MathematicalDomain.NONNEGATIVE_INTEGER),
            "sigma": VariableDeclaration(domain=MathematicalDomain.NONNEGATIVE_INTEGER),
            "x": VariableDeclaration(domain=MathematicalDomain.REAL),
        },
    ))
    assert qualified.status == "success" and qualified.system is not None
    assert qualified.system.total_work == "-h + sigma + 1"
    assert [item.name for item in qualified.system.relationships_used] == ["h_le_sigma"]
    assert qualified.system.unresolved == ()
    assert unresolved.status == "success" and unresolved.system is not None
    assert unresolved.system.total_work == "Max(0, -h + sigma + 1)"
    assert "ordering or finiteness is unproved" in " ".join(unresolved.system.unresolved)


def test_unproved_symbolic_then_fixed_empty_domain_never_reports_negative_work() -> None:
    outcome = analyze(AnalysisRequest(
        syntax=FormulaSyntax.SYMPY,
        equations=(EquationRequest(
            name="empty",
            expression="Eq(A[i, j], primitive(i))",
            domains={
                "i": IndexDomain(lower="0", upper="sigma - h"),
                "j": IndexDomain(lower="0", upper="i"),
            },
        ),),
        variables={
            "h": VariableDeclaration(domain=MathematicalDomain.NONNEGATIVE_INTEGER),
            "sigma": VariableDeclaration(domain=MathematicalDomain.NONNEGATIVE_INTEGER),
        },
        primitive_costs=(PrimitiveCost(name="primitive", parameters=("z",), work="z"),),
        scenarios=(Scenario(name="empty", fixed={"h": 2, "sigma": 0}),),
    ))
    assert outcome.status == "success" and outcome.system is not None
    assert "Max(0, -h + sigma + 1)" in outcome.system.total_work
    assert "Sum" in outcome.system.total_work
    assert outcome.scenarios[0].substituted_work == "0"
    assert outcome.scenarios[0].unresolved


def test_dependent_bound_family_and_topological_ties_follow_the_adr_boundary() -> None:
    rejected = (
        "value[j]", "f(j)", "j*N", "N*j", "j**2", "j/2",
        "Sum(j, (q, 0, N))",
    )
    for upper in rejected:
        outcome = analyze(AnalysisRequest(
            syntax=FormulaSyntax.SYMPY,
            equations=(EquationRequest(
                name="bad", expression="Eq(A[i, j], x)",
                domains={"i": IndexDomain(lower="0", upper=upper), "j": IndexDomain(lower="0", upper="N")},
            ),),
            variables=variables("N", "x", "value"),
        ))
        assert outcome.status == "failure"
        assert outcome.error.source is not None
        assert outcome.error.source.path == "equations[0].domains.i.upper"

    for upper in ("2*j", "j*2", "-j + 3*N"):
        outcome = analyze(AnalysisRequest(
            syntax=FormulaSyntax.SYMPY,
            equations=(EquationRequest(
                name="ok", expression="Eq(A[i, j], x)",
                domains={"i": IndexDomain(lower="-j", upper=upper), "j": IndexDomain(lower="0", upper="N")},
            ),),
            variables=variables("N", "x"),
        ))
        assert outcome.status == "success"

    independent_nonlinear = analyze(AnalysisRequest(
        syntax=FormulaSyntax.SYMPY,
        equations=(EquationRequest(
            name="independent", expression="Eq(A[i], x)",
            domains={"i": IndexDomain(lower="0", upper="N**2")},
        ),),
        variables=variables("N", "x"),
    ))
    assert independent_nonlinear.status == "success"

    parsed_bounds = {
        "i": (parse_expression("0"), parse_expression("k")),
        "j": (parse_expression("0"), parse_expression("N")),
        "k": (parse_expression("0"), parse_expression("N")),
    }
    assert all(not hasattr(value, "message") for pair in parsed_bounds.values() for value in pair)
    built = build_output_domains(parsed_bounds, ("i", "j", "k"), 0, frozenset({"N"}))  # type: ignore[arg-type]
    assert not hasattr(built, "message")
    assert built[1] == ("j", "k", "i")  # type: ignore[index]


def test_domain_bounds_localize_free_symbol_and_shadowing_diagnostics() -> None:
    free = analyze(AnalysisRequest(
        syntax=FormulaSyntax.SYMPY,
        equations=(EquationRequest(name="bad", expression="Eq(A[i], x)", domains={"i": IndexDomain(lower="0", upper="missing")}),),
        variables=variables("x"),
    ))
    shadowed = analyze(AnalysisRequest(
        syntax=FormulaSyntax.SYMPY,
        equations=(EquationRequest(name="bad", expression="Eq(A[i, j], x)", domains={
            "i": IndexDomain(lower="0", upper="Sum(j, (j, 0, N))"),
            "j": IndexDomain(lower="0", upper="N"),
        }),),
        variables=variables("N", "x"),
    ))
    assert free.status == "failure" and free.error.source is not None
    assert free.error.source.path == "equations[0].domains.i.upper"
    assert shadowed.status == "failure"
    assert "shadows an existing index" in shadowed.error.message


def test_same_named_predecessor_domains_keep_equation_specific_provenance() -> None:
    outcome = analyze(AnalysisRequest(
        syntax=FormulaSyntax.SYMPY,
        equations=(
            EquationRequest(
                name="a",
                expression="Eq(A[n, m], x)",
                domains={
                    "n": IndexDomain(lower="0", upper="p"),
                    "m": IndexDomain(lower="-n", upper="n"),
                },
            ),
            EquationRequest(
                name="b",
                expression="Eq(B[n, m], x)",
                domains={
                    "n": IndexDomain(lower="1", upper="q"),
                    "m": IndexDomain(lower="-n", upper="n"),
                },
            ),
        ),
        variables=variables("p", "q", "x"),
    ))

    assert outcome.status == "success" and outcome.system is not None
    assert [(item.name, item.relationship) for item in outcome.system.relationships_used] == [
        ("domain:n", "0 <= n <= p"),
        ("domain:n", "1 <= n <= q"),
    ]
    assert [
        [(item.name, item.relationship) for item in report.relationships_used]
        for report in outcome.system.equations
    ] == [
        [("domain:n", "0 <= n <= p")],
        [("domain:n", "1 <= n <= q")],
    ]


def test_unproved_independent_domain_closure_clamps_fixed_empty_work() -> None:
    outcome = analyze(
        AnalysisRequest(
            syntax=FormulaSyntax.SYMPY,
            equations=(
                EquationRequest(
                    name="empty_after_substitution",
                    expression="Eq(A[i], primitive(i))",
                    domains={"i": IndexDomain(lower="2", upper="N")},
                ),
            ),
            variables={
                "N": VariableDeclaration(domain=MathematicalDomain.INTEGER),
            },
            primitive_costs=(
                PrimitiveCost(name="primitive", parameters=("value",), work="value"),
            ),
            scenarios=(Scenario(name="empty", fixed={"N": 0}),),
        )
    )

    assert outcome.status == "success" and outcome.system is not None
    assert "Sum(i, (i, 2, Max(0, N - 1) + 1))" in outcome.system.total_work
    n_value = sympify("n_value")
    assert sympify(outcome.system.total_work, locals={"N": n_value}).subs(n_value, 0).doit() == 0
    assert outcome.scenarios[0].substituted_work == "0"
    assert all("-1" not in value for value in outcome.scenarios[0].choice_work.values())


def test_unproved_sum_clamps_index_dependent_work_before_specialization() -> None:
    outcome = analyze(AnalysisRequest(
        syntax=FormulaSyntax.SYMPY,
        equations=(EquationRequest(
            name="sum_after_substitution",
            expression="Eq(y, Sum(primitive(i), (i, 2, N)))",
        ),),
        variables={
            "N": VariableDeclaration(domain=MathematicalDomain.INTEGER),
        },
        primitive_costs=(
            PrimitiveCost(name="primitive", parameters=("value",), work="value"),
        ),
        scenarios=(Scenario(name="empty", fixed={"N": 0}),),
    ))

    assert outcome.status == "success" and outcome.system is not None
    assert "Sum(i, (i, 2, Max(0, N - 1) + 1))" in outcome.system.total_work
    n_value = sympify("n_value")
    assert sympify(outcome.system.total_work, locals={"N": n_value}).subs(n_value, 0).doit() == 0
    assert outcome.scenarios[0].substituted_work == "0"


def test_harmonic_style_system_closes_dependent_domain_work_without_special_semantics() -> None:
    positive_real = VariableDeclaration(domain=MathematicalDomain.POSITIVE_REAL)
    request = AnalysisRequest(
        syntax=FormulaSyntax.SYMPY,
        equations=(
            EquationRequest(name="ratio_t", expression="Eq(r_t, h_t / sigma)"),
            EquationRequest(name="ratio_s", expression="Eq(r_s, h_s / sigma)"),
            EquationRequest(name="factor_t", expression="Eq(a[n], r_t**n)", domains={"n": IndexDomain(lower="0", upper="p")}),
            EquationRequest(name="factor_s", expression="Eq(b[k], r_s**k)", domains={"k": IndexDomain(lower="0", upper="p")}),
            EquationRequest(name="scale", expression="Eq(S[n, k], a[n] * b[k])", domains={"n": IndexDomain(lower="0", upper="p"), "k": IndexDomain(lower="0", upper="p")}),
            EquationRequest(
                name="translation",
                expression="Eq(L[n, m], a[n] * Sum(b[k] * Sum(conjugate(M[k, l]) * harmonic(n + k, m + l), (l, -k, k)), (k, 0, p)))",
                domains={"n": IndexDomain(lower="0", upper="p"), "m": IndexDomain(lower="-n", upper="n")},
            ),
        ),
        variables={
            "p": VariableDeclaration(domain=MathematicalDomain.POSITIVE_INTEGER),
            "h_t": positive_real,
            "h_s": positive_real,
            "sigma": positive_real,
            "M": VariableDeclaration(domain=MathematicalDomain.REAL),
        },
        primitive_costs=(
            PrimitiveCost(name="conjugate", parameters=("value",), work="1"),
            PrimitiveCost(name="harmonic", parameters=("degree", "order"), work="1"),
        ),
        scenarios=(Scenario(name="p12", fixed={"p": 12}), Scenario(name="p20", fixed={"p": 20})),
    )
    outcome = analyze(request)
    assert outcome.status == "success" and outcome.system is not None
    system = outcome.system
    assert system.dependency_edges == (
        ("ratio_s", "factor_s"), ("ratio_t", "factor_t"),
        ("factor_s", "scale"), ("factor_t", "scale"),
        ("factor_s", "translation"), ("factor_t", "translation"),
    )
    assert [(item.producer, item.consumer, item.references) for item in system.reuse] == [
        ("ratio_s", "factor_s", 1),
        ("ratio_t", "factor_t", 1),
        ("factor_s", "scale", 1),
        ("factor_t", "scale", 1),
        ("factor_s", "translation", 1),
        ("factor_t", "translation", 1),
    ]
    translation = next(item for item in system.equations if item.name == "translation")
    assert translation.interpretation.normalized_sympy == "Eq(L[n, m], a[n]*Sum(b[k]*Sum(harmonic(k + n, l + m)*conjugate(M[k, l]), (l, -k, k)), (k, 0, p)))"
    assert translation.operation_counts.model_dump() == {
        "additions": 2, "subtractions": 0, "multiplications": 4,
        "divisions": 0, "powers": 0,
    }
    expected = sympify("(p + 1)**2*(6*p**2 + 13*p + 7)")
    assert translation.aggregate_work == (
        "(p + (p + 1)*(3*p + 2))*(p + 1)**2 + "
        "((p + 1)*(p + 2) + 1)*(p + 1)**2 + 2*((p + 1)**2)**2"
    )
    assert simplify(sympify(translation.aggregate_work) - expected) == 0
    assert translation.aggregate_operation_counts.model_dump() == {
        "additions": "(p + (p + 1)*(3*p + 2))*(p + 1)**2",
        "subtractions": "0",
        "multiplications": "((p + 1)*(p + 2) + 1)*(p + 1)**2",
        "divisions": "0",
        "powers": "0",
    }
    assert translation.direct_work_applicability == "finite"
    assert translation.direct_work_blockers == ()
    assert translation.unknown_costs == () and translation.unresolved == ()
    assert set(translation.dependencies) == {"factor_s", "factor_t"}
    assert [(item.name, item.relationship) for item in translation.relationships_used] == [
        ("domain:n", "0 <= n <= p")
    ]
    assert [(item.name, item.relationship) for item in system.relationships_used] == [
        ("domain:n", "0 <= n <= p")
    ]
    assert system.unused_assumptions == ()
    for rendered in (translation.aggregate_work, *translation.primitive_invocations.values()):
        assert not ({"n", "m", "k", "l"} & {str(item) for item in sympify(rendered).free_symbols})
    for primitive in ("conjugate", "harmonic"):
        assert translation.primitive_invocations[primitive] == "((p + 1)**2)**2"
        assert simplify(sympify(translation.primitive_invocations[primitive]) - sympify("(p + 1)**4")) == 0
    operation_work = sum(
        sympify(value)
        for value in translation.aggregate_operation_counts.model_dump().values()
    )
    assert simplify(sympify(translation.aggregate_work) - operation_work) == 2 * sympify(
        "(p + 1)**4"
    )
    for scenario, work in zip(outcome.scenarios, (173760, 1176632), strict=True):
        assert scenario.substituted_work == str(work)
        assert scenario.unresolved == ()
    for value, work, invocations in ((12, 173563, 28561), (20, 1176147, 194481)):
        assert int(expected.subs({"p": value})) == work
        assert int(sympify(translation.primitive_invocations["harmonic"]).subs({"p": value})) == invocations


def test_request_wide_generic_arities_and_parameter_scopes_are_validated() -> None:
    cross_definition = analyze(
        AnalysisRequest(
            syntax=FormulaSyntax.SYMPY,
            expression="opaque(x, y)",
            functions=(FunctionDefinition(name="f", parameters=("z",), body="opaque(z)"),),
        )
    )
    cross_equation = analyze(
        AnalysisRequest(
            syntax=FormulaSyntax.SYMPY,
            equations=(
                EquationRequest(name="a", expression="Eq(A, opaque(x))"),
                EquationRequest(name="b", expression="Eq(B, opaque(x, y))"),
            ),
            variables=variables("x", "y"),
        )
    )
    parameter_shadow = analyze(
        AnalysisRequest(
            syntax=FormulaSyntax.SYMPY,
            expression="f(x)",
            functions=(FunctionDefinition(name="f", parameters=("i",), body="Sum(i, (i, 0, N))"),),
        )
    )
    nested_shadow = analyze(
        AnalysisRequest(
            syntax=FormulaSyntax.SYMPY,
            expression="Sum(Sum(x[i], (i, 0, N)), (i, 0, N))",
            variables=variables("N", "x"),
        )
    )
    primitive_shadow = analyze(
        AnalysisRequest(
            syntax=FormulaSyntax.SYMPY,
            expression="p(x)",
            primitive_costs=(PrimitiveCost(name="p", parameters=("i",), work="Sum(i, (i, 0, N))"),),
        )
    )
    assert cross_definition.status == "failure"
    assert cross_equation.status == "failure"
    assert parameter_shadow.status == "failure"
    assert nested_shadow.status == "failure"
    assert primitive_shadow.status == "failure"
    assert "function opaque requires 1 arguments" in cross_definition.error.message
    assert "function opaque requires 1 arguments" in cross_equation.error.message
    assert "shadows an existing index" in parameter_shadow.error.message
    assert "shadows an existing index" in nested_shadow.error.message
    assert "shadows an existing index" in primitive_shadow.error.message


def test_domain_bounds_reject_producers_and_share_request_wide_call_arities() -> None:
    producer_bound = analyze(
        AnalysisRequest(
            syntax=FormulaSyntax.SYMPY,
            equations=(
                EquationRequest(
                    name="a",
                    expression="Eq(A[i], x)",
                    domains={"i": IndexDomain(lower="0", upper="B")},
                ),
                EquationRequest(name="b", expression="Eq(B, y)"),
            ),
            variables=variables("x", "y"),
        )
    )
    known_arity = analyze(
        AnalysisRequest(
            syntax=FormulaSyntax.SYMPY,
            equations=(
                EquationRequest(
                    name="a",
                    expression="Eq(A[i], x)",
                    domains={"i": IndexDomain(lower="0", upper="f(N, N)")},
                ),
            ),
            variables=variables("N", "x"),
            functions=(FunctionDefinition(name="f", parameters=("z",), body="z"),),
        )
    )
    generic_arity = analyze(
        AnalysisRequest(
            syntax=FormulaSyntax.SYMPY,
            equations=(
                EquationRequest(
                    name="a",
                    expression="Eq(A[i], opaque(x))",
                    domains={"i": IndexDomain(lower="0", upper="opaque(N, N)")},
                ),
            ),
            variables=variables("N", "x"),
        )
    )
    assert producer_bound.status == "failure"
    assert "cannot reference named results: B" in producer_bound.error.message
    assert known_arity.status == "failure"
    assert known_arity.error.message == "function f requires 1 arguments"
    assert generic_arity.status == "failure"
    assert generic_arity.error.message == "function opaque requires 2 arguments"


def test_primitive_substitution_and_definition_depth_fail_structurally() -> None:
    repeated_argument = " + ".join("x" for _ in range(70))
    repeated_parameter = " + ".join("z" for _ in range(70))
    primitive = analyze(
        AnalysisRequest(
            syntax=FormulaSyntax.SYMPY,
            expression=f"p({repeated_argument})",
            primitive_costs=(PrimitiveCost(name="p", parameters=("z",), work=repeated_parameter),),
        )
    )
    definitions = tuple(
        FunctionDefinition(
            name=f"f{index}",
            parameters=("z",),
            body=(
                " + ".join([f"f{index + 1}(z)", *("1" for _ in range(10))])
                if index < 39
                else "z + 1"
            ),
        )
        for index in range(40)
    )
    deep = analyze(
        AnalysisRequest(
            syntax=FormulaSyntax.SYMPY,
            expression="f0(x)",
            functions=definitions,
        )
    )
    assert primitive.status == "failure"
    assert primitive.error.code.value == "expression_too_complex"
    assert deep.status == "failure"
    assert deep.error.code.value == "expression_too_complex"


def test_work_render_estimates_cover_signed_integers_and_sum_indices(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    expressions = (
        IntegerLiteral(-123456789),
        Sum(Symbol("x"), "a_very_long_iterator_name", IntegerLiteral(-3), IntegerLiteral(8)),
    )
    for expression in expressions:
        rendering = formula_work.render_work(expression, formula_work.WorkRenderBudget())
        assert formula_work._rendered_size_upper_bound(expression) >= len(  # pyright: ignore[reportPrivateUsage]
            rendering.encode("utf-8")
        )

    monkeypatch.setattr(formula_work, "MAX_WORK_RENDER_BYTES", 1)
    bounded = analyze(
        AnalysisRequest(syntax=FormulaSyntax.SYMPY, expression="Sum(x[i] + 1, (i, 0, N))")
    )
    assert bounded.status == "failure"
    assert bounded.error.code.value == "expression_too_complex"


def test_work_expansion_and_rendered_results_fail_with_structured_complexity(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    doubled = "p(" * 14 + "x" + ")" * 14
    expanded = analyze(
        AnalysisRequest(
            syntax=FormulaSyntax.SYMPY,
            expression=doubled,
            functions=(FunctionDefinition(name="p", parameters=("z",), body="z + z"),),
        )
    )
    assert expanded.status == "failure"
    assert expanded.error.code.value == "expression_too_complex"

    monkeypatch.setattr(formula_service, "MAX_RENDERED_BYTES", 1)
    rendering = analyze(AnalysisRequest(syntax=FormulaSyntax.SYMPY, expression="x + 1"))
    assert rendering.status == "failure"
    assert rendering.error.code.value == "expression_too_complex"

    monkeypatch.setattr(formula_service, "MAX_RESULT_BYTES", 1)
    result = analyze(AnalysisRequest(syntax=FormulaSyntax.SYMPY, expression="x"))
    assert result.status == "failure"
    assert result.error.code.value == "expression_too_complex"


def test_request_wide_split_field_bounds_apply_before_analysis() -> None:
    # Each field is individually valid; the aggregate must still be bounded.
    oversized_bytes = analyze(
        AnalysisRequest(
            syntax=FormulaSyntax.SYMPY,
            expression="x",
            functions=tuple(
                FunctionDefinition(name=f"f{index}", parameters=(), body="x" * 60_000)
                for index in range(5)
            ),
        )
    )
    terms = " + ".join("x" for _ in range(2_000))
    oversized_nodes = analyze(
        AnalysisRequest(
            syntax=FormulaSyntax.SYMPY,
            expression="x",
            functions=tuple(
                FunctionDefinition(name=f"g{index}", parameters=(), body=terms)
                for index in range(5)
            ),
        )
    )
    assert oversized_bytes.status == "failure"
    assert oversized_bytes.error.code.value == "expression_too_complex"
    assert oversized_nodes.status == "failure"
    assert oversized_nodes.error.code.value == "expression_too_complex"


def test_max_is_reserved_for_aggregate_work_semantics() -> None:
    with pytest.raises(ValidationError, match="Max"):
        AnalysisRequest(
            syntax=FormulaSyntax.SYMPY,
            expression="x",
            functions=(FunctionDefinition(name="Max", parameters=("x",), body="x"),),
        )
    parsed = analyze(AnalysisRequest(syntax=FormulaSyntax.SYMPY, expression="Max(x, 0)"))
    assert parsed.status == "failure"
    assert parsed.error.code.value == "unsupported_construct"


def test_equation_index_names_are_local_and_unnamed_repetition_is_not_removed() -> None:
    outcome = analyze(
        AnalysisRequest(
            syntax=FormulaSyntax.SYMPY,
            equations=(
                EquationRequest(
                    name="a",
                    expression="Eq(A[i], (x[i] + 1) * (x[i] + 1))",
                    domains={"i": IndexDomain(lower="0", upper="N")},
                ),
                EquationRequest(
                    name="b",
                    expression="Eq(B[i], y[i] + 1)",
                    domains={"i": IndexDomain(lower="1", upper="M")},
                ),
            ),
            variables=variables("M", "N", "x", "y"),
        )
    )
    assert outcome.status == "success"
    assert outcome.system is not None
    assert outcome.system.equations[0].operation_counts.additions == 2
    assert outcome.system.equations[0].operation_counts.multiplications == 1
    assert outcome.system.extraction_opportunities == (
        "equation a: extract repeated `x[i] + 1` (2 occurrences)",
    )


def test_afmm_like_request_reports_structural_work_scenarios_and_uncertainty() -> None:
    # Representative structure for complexity analysis; this is not a physical-validation oracle.
    request = AnalysisRequest(
        syntax=FormulaSyntax.SYMPY,
        equations=(
            EquationRequest(
                name="displacement",
                expression="Eq(D[i, d], x[i, d] - center[leaf[i], d])",
                domains={
                    "i": IndexDomain(lower="0", upper="N - 1"),
                    "d": IndexDomain(lower="0", upper="D_dim - 1"),
                },
            ),
            EquationRequest(
                name="multipoles",
                expression="Eq(M[b, a], Sum(q[i] * basis(a, D[i, 0]), (i, 0, n[b] - 1)))",
                domains={
                    "b": IndexDomain(lower="0", upper="B_leaf - 1"),
                    "a": IndexDomain(lower="0", upper="K(p) - 1"),
                },
            ),
            EquationRequest(
                name="translation",
                expression=(
                    "Eq(L[b, a], Sum(Sum(translate(a, k, M[neighbor[b, c], k]) + "
                    "M[neighbor[b, c], k], (k, 0, K(p) - 1)), "
                    "(c, 0, interaction_count[b] - 1)))"
                ),
                domains={
                    "b": IndexDomain(lower="0", upper="B_leaf - 1"),
                    "a": IndexDomain(lower="0", upper="K(p) - 1"),
                },
            ),
        ),
        variables={
            name: VariableDeclaration(domain=domain)
            for name, domain in {
                "N": MathematicalDomain.POSITIVE_INTEGER,
                "D_dim": MathematicalDomain.POSITIVE_INTEGER,
                "B_leaf": MathematicalDomain.POSITIVE_INTEGER,
                "p": MathematicalDomain.POSITIVE_INTEGER,
                "x": MathematicalDomain.REAL,
                "center": MathematicalDomain.REAL,
                "leaf": MathematicalDomain.NONNEGATIVE_INTEGER,
                "q": MathematicalDomain.REAL,
                "n": MathematicalDomain.NONNEGATIVE_INTEGER,
                "neighbor": MathematicalDomain.NONNEGATIVE_INTEGER,
                "interaction_count": MathematicalDomain.NONNEGATIVE_INTEGER,
            }.items()
        },
        functions=(FunctionDefinition(name="K", parameters=("z",), body="z**2"),),
        primitive_costs=(PrimitiveCost(name="basis", parameters=("a", "r"), work="2*a + 1"),),
        assumptions=(
            Assumption(
                name="particle_partition",
                relationship="Sum(n[b], (b, 0, B_leaf - 1)) == N",
            ),
        ),
        scenarios=(
            Scenario(
                name="particles_scale", fixed={"p": 8, "D_dim": 3, "B_leaf": 64}, asymptotic=("N",)
            ),
            Scenario(
                name="order_scales", fixed={"N": 1000, "D_dim": 3, "B_leaf": 64}, asymptotic=("p",)
            ),
            Scenario(name="joint_scale", fixed={"D_dim": 3, "B_leaf": 64}, asymptotic=("N", "p")),
        ),
    )

    outcome = analyze(request)

    assert outcome.status == "success"
    assert outcome.system is not None
    system = outcome.system
    assert [equation.name for equation in system.equations] == [
        "displacement",
        "multipoles",
        "translation",
    ]
    assert system.dependency_edges == (
        ("displacement", "multipoles"),
        ("multipoles", "translation"),
    )
    assert [(item.producer, item.consumer, item.references) for item in system.reuse] == [
        ("displacement", "multipoles", 1),
        ("multipoles", "translation", 2),
    ]
    assert [item.interpretation.normalized_sympy for item in system.equations] == [
        "Eq(D[i, d], -center[leaf[i], d] + x[i, d])",
        "Eq(M[b, a], Sum(basis(a, D[i, 0])*q[i], (i, 0, n[b] - 1)))",
        (
            "Eq(L[b, a], Sum(translate(a, k, M[neighbor[b, c], k]) + "
            "M[neighbor[b, c], k], (k, 0, K(p) - 1), "
            "(c, 0, interaction_count[b] - 1)))"
        ),
    ]
    assert [item.interpretation.normalized_latex for item in system.equations] == [
        r"{D}_{i,d} = - {center}_{{leaf}_{i},d} + {x}_{i,d}",
        (
            r"{M}_{b,a} = \sum_{i=0}^{{n}_{b} - 1} "
            r"\operatorname{basis}{\left(a,{D}_{i,0} \right)} {q}_{i}"
        ),
        (
            r"{L}_{b,a} = \sum_{\substack{0 \leq k \leq K{\left(p \right)} - 1\\"
            r"0 \leq c \leq {interaction_{count}}_{b} - 1}} "
            r"\left(\operatorname{translate}{\left(a,k,{M}_{{neighbor}_{b,c},k} "
            r"\right)} + {M}_{{neighbor}_{b,c},k}\right)"
        ),
    ]
    assert system.equations[0].aggregate_work == "D_dim*N"
    assert system.equations[1].aggregate_work == (
        "N*p**2 + N*(p**2)**2 + "
        "Sum(Max(0, n[b] - 1), (b, 0, B_leaf - 1))*p**2"
    )
    assert system.total_work is not None
    assert system.primitive_invocations is not None
    assert system.equations[1].primitive_invocations is not None
    assert system.equations[2].aggregate_work is not None
    assert system.total_work.startswith("D_dim*N + N*p**2 + N*(p**2)**2")
    assert system.primitive_invocations["basis"] == "N*p**2"
    assert [item.name for item in system.relationships_used] == [
        "function:K",
        "particle_partition",
    ]
    assert system.unused_assumptions == ()
    assert "C_translate" in system.unknown_costs
    assert "unknown cost for translate" in system.unresolved
    assert system.equations[1].primitive_invocations["basis"] == "N*p**2"
    assert "C_translate" in system.equations[2].aggregate_work
    assert len(outcome.scenarios) == 3
    scenarios = {item.name: item for item in outcome.scenarios}
    assert scenarios["particles_scale"].substitutions["p"] == "8"
    assert "4163*N" in scenarios["particles_scale"].substituted_work
    assert scenarios["order_scales"].substitutions["N"] == "1000"
    assert "1000*p**2" in scenarios["order_scales"].substituted_work
    assert [item.name for item in scenarios["particles_scale"].relationships_used] == [
        "function:K",
        "particle_partition",
    ]
    assert scenarios["joint_scale"].asymptotic is None
    assert "multivariate" in " ".join(scenarios["joint_scale"].unresolved)
    assert system.total_work == outcome.system.total_work


def test_infinite_output_domain_is_rejected_as_a_finite_computational_bound() -> None:
    outcome = analyze(AnalysisRequest(
        syntax=FormulaSyntax.SYMPY,
        equations=(EquationRequest(name="a", expression="Eq(A[i], x[i])", domains={"i": IndexDomain(lower="0", upper="oo")}),),
        variables=variables("x"),
    ))
    assert outcome.status == "failure"
    assert "infinite" in outcome.error.message
