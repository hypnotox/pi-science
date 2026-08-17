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
from py_science.formula.expressions import IntegerLiteral, Sum, Symbol
from pydantic import ValidationError


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


def test_named_rhs_closed_form_query_is_local_to_the_selected_equation() -> None:
    outcome = analyze(AnalysisRequest(
        syntax=FormulaSyntax.SYMPY,
        equations=(EquationRequest(name="tail", expression="Eq(y, Sum(k * 2**k, (k, 0, 3)))"),),
        queries=(ClosedFormQuery(name="closed", target=EquationTarget(name="tail")),),
    ))
    assert isinstance(outcome, AnalysisSuccess)
    assert outcome.queries[0].answers[0].conclusion == "proved_under_assumptions"
    assert outcome.system is not None and outcome.system.equations[0].aggregate_work is not None


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


def test_dependent_output_domains_are_rejected_and_output_indices_are_integral() -> None:
    dependent = analyze(
        AnalysisRequest(
            syntax=FormulaSyntax.SYMPY,
            equations=(
                EquationRequest(
                    name="a",
                    expression="Eq(A[i, j], x[i])",
                    domains={
                        "i": IndexDomain(lower="0", upper="j"),
                        "j": IndexDomain(lower="0", upper="N"),
                    },
                ),
            ),
            variables=variables("N", "x"),
        )
    )
    independent = analyze(
        AnalysisRequest(
            syntax=FormulaSyntax.SYMPY,
            equations=(
                EquationRequest(
                    name="a",
                    expression="Eq(A[i], x[i])",
                    domains={"i": IndexDomain(lower="0", upper="N")},
                ),
            ),
            variables=variables("N", "x"),
        )
    )
    assert dependent.status == "failure"
    assert "cannot depend on output indices: j" in dependent.error.message
    assert independent.status == "success"
    assert independent.system is not None
    assert independent.system.unresolved == ()


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
        "N*Sum(2*a + 1, (a, 0, -1 + p**2)) + N*p**2 + "
        "Sum(Max(0, n[b] - 1), (b, 0, B_leaf - 1))*p**2"
    )
    assert system.total_work is not None
    assert system.primitive_invocations is not None
    assert system.equations[1].primitive_invocations is not None
    assert system.equations[2].aggregate_work is not None
    assert system.total_work.startswith("D_dim*N + N*Sum(2*a + 1")
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
    assert "67*N" in scenarios["particles_scale"].substituted_work
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
        equations=(EquationRequest(name="a", expression="Eq(A[i], x[i])", domains={"i": IndexDomain(lower="0", upper="oo")}),),  # noqa: E501
        variables=variables("x"),
    ))
    assert outcome.status == "failure"
    assert "infinite" in outcome.error.message
