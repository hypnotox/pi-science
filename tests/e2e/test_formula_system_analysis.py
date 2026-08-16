import pytest
from py_science.formula import (
    AnalysisRequest,
    EquationRequest,
    FormulaSyntax,
    FunctionDefinition,
    IndexDomain,
    MathematicalDomain,
    PrimitiveCost,
    VariableDeclaration,
    analyze,
)
from pydantic import ValidationError


def variables(*names: str) -> dict[str, VariableDeclaration]:
    return {
        name: VariableDeclaration(domain=MathematicalDomain.NONNEGATIVE_INTEGER)
        for name in names
    }


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
    assert "Max" in outcome.system.equations[0].aggregate_work
    assert outcome.system.extraction_opportunities == ()


def test_sum_work_handles_empty_one_term_nested_and_symbolic_domains() -> None:
    empty = analyze(
        AnalysisRequest(syntax=FormulaSyntax.SYMPY, expression="Sum(x[i], (i, 2, 1))")
    )
    one = analyze(
        AnalysisRequest(syntax=FormulaSyntax.SYMPY, expression="Sum(x[i], (i, 2, 2))")
    )
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
    assert "cardinality" in outcome.system.total_work
    assert outcome.system.unresolved == ("sum index i cardinality requires integral bounds",)


def test_function_definitions_primitive_work_and_unknown_costs_are_distinct() -> None:
    outcome = analyze(
        AnalysisRequest(
            syntax=FormulaSyntax.SYMPY,
            expression="defined(x) + primitive(n) + opaque(x)",
            variables=variables("n", "x"),
            functions=(
                FunctionDefinition(name="defined", parameters=("z",), body="z * z"),
            ),
            primitive_costs=(
                PrimitiveCost(name="primitive", parameters=("k",), work="2 * k + 1"),
            ),
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
