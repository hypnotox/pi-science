# pyright: reportPrivateUsage=false
from typing import cast

from py_science.formula.expressions import Expression
from py_science.formula.parser import ParseFailure, parse_expression


def _expression(source: str):
    parsed = parse_expression(source)
    assert not isinstance(parsed, ParseFailure)
    return cast(Expression, parsed)


def test_candidate_deduplication_ignores_occurrence_discovery_routes() -> None:
    from py_science.formula.optimization import (
        _candidate_semantic_key,
        _CandidateComputation,
        _EvaluationScope,
        _Occurrence,
    )

    expression = _expression("x + 1")
    proposed = _expression("x")
    scope = _EvaluationScope((), (), ())
    occurrences = tuple(
        _Occurrence("expression", path, expression, frozenset({"x"}), (), scope)
        for path in ((0,), (1,))
    )
    candidates = tuple(
        _CandidateComputation(
            kind="horner",
            target="expression",
            original=expression,
            proposed=proposed,
            occurrences=(occurrence,),
        )
        for occurrence in occurrences
    )

    assert _candidate_semantic_key(candidates[0]) == _candidate_semantic_key(candidates[1])


def test_cross_equation_canonical_binders_do_not_capture_user_symbols() -> None:
    from goal_requests import optimize_analysis
    from py_science.formula import (
        AnalysisRequest,
        EquationRequest,
        FormulaSyntax,
        MathematicalDomain,
        VariableDeclaration,
    )

    result = optimize_analysis(
        AnalysisRequest(
            syntax=FormulaSyntax.SYMPY,
            equations=(
                EquationRequest(name="bound", expression="Eq(bound, Sum(i, (i, 0, 3)))"),
                EquationRequest(
                    name="free",
                    expression="Eq(free, Sum(optimization_sum_0, (i, 0, 3)))",
                ),
            ),
            variables={"optimization_sum_0": VariableDeclaration(domain=MathematicalDomain.REAL)},
        ),
        projection_limit=16,
    )

    assert result.status == "success"
    assert all(
        all(step.kind != "cross_equation_sharing" for step in plan.trace)
        for plan in result.plans
    )


def test_limits_and_repeated_process_json_are_deterministic() -> None:
    import subprocess
    import sys

    from goal_requests import optimize_analysis
    from py_science.formula import AnalysisRequest, FormulaSyntax

    expression = "(a*x**3 + b*x**2 + c*x + d) + (y + 1)*(y + 1) + z*w + z*q + (r + 0)"
    for limit in (1, 3, 16):
        result = optimize_analysis(
            AnalysisRequest(syntax=FormulaSyntax.SYMPY, expression=expression),
            projection_limit=limit,
        )
        assert result.status == "success"
        assert len(result.plans) <= limit
        assert result.projection_status == "complete"
        assert result.projection_qualifications == ()
        assert result.search_scope.completion == "incomplete"
        assert result.search_scope.qualifications

    empty = optimize_analysis(
        AnalysisRequest(syntax=FormulaSyntax.SYMPY, expression="x"), projection_limit=16
    )
    assert empty.status == "success"
    assert empty.classification == "no_applicable_candidate"
    assert empty.plans == ()
    assert empty.search_scope.completion == "complete"
    assert empty.search_scope.qualifications == ()

    script = f'''
from py_science.formula import (
    BoundedGoalSearchPolicy, FormulaSyntax, GoalSpec, OptimizeRequest,
    UnitWorkObjective, VerifierBackedProofPolicy, optimize,
)
request = OptimizeRequest(
    syntax=FormulaSyntax.SYMPY,
    expression={expression!r},
    goal=GoalSpec(objective=UnitWorkObjective()),
    search=BoundedGoalSearchPolicy(),
    proof=VerifierBackedProofPolicy(),
    projection_limit=16,
)
print(optimize(request).model_dump_json())
'''
    populations = tuple(
        subprocess.check_output([sys.executable, "-c", script], text=True).strip() for _ in range(3)
    )
    assert populations[0] == populations[1] == populations[2]


def test_composed_search_v1_alpha_renamed_binders_keep_population_order() -> None:
    """Search-only canonicalization makes alpha-equivalent binders rank identically."""
    from goal_requests import optimize_analysis
    from py_science.formula import AnalysisRequest, FormulaSyntax

    def population(index: str) -> list[tuple[tuple[str, ...], str]]:
        result = optimize_analysis(
            AnalysisRequest(
                syntax=FormulaSyntax.SYMPY,
                expression=f"Sum((x + 1)*(x + 1), ({index}, 0, 3))",
            ),
            projection_limit=16,
        )
        assert result.status == "success"
        return [
            (tuple(step.kind for step in plan.trace), plan.suggestion.objective_savings)
            for plan in result.plans
        ]

    assert population("i") == population("j")


def test_composed_search_v1_deduplicates_opposite_generated_producer_orders() -> None:
    """Independent producer introduction orders collapse to one final state."""
    from goal_requests import optimize_analysis
    from py_science.formula import AnalysisRequest, FormulaSyntax

    result = optimize_analysis(
        AnalysisRequest(
            syntax=FormulaSyntax.SYMPY,
            expression="(x + 1)*(x + 1) + (y + 1)*(y + 1)",
        ),
        projection_limit=16,
    )
    assert result.status == "success"
    composed = [plan for plan in result.plans if len(plan.trace) == 2]

    assert len(composed) == 1
    assert tuple(step.kind for step in composed[0].trace) == (
        "repeated_subexpression",
        "repeated_subexpression",
    )
    assert composed[0].suggestion.objective_savings == "2"


def test_composed_search_v1_equation_permutations_keep_logical_population() -> None:
    """Search policy is equation-order invariant while replay preserves caller order."""
    from goal_requests import optimize_analysis
    from py_science.formula import (
        AnalysisRequest,
        EquationRequest,
        FormulaSyntax,
        IndexDomain,
        MathematicalDomain,
        OptimizationPlan,
        VariableDeclaration,
    )

    equations = (
        EquationRequest(
            name="left",
            expression="Eq(left[i], x[i]*x[i] + 1)",
            domains={"i": IndexDomain(lower="0", upper="3")},
        ),
        EquationRequest(
            name="right",
            expression="Eq(right[j], x[j]*x[j] - 1)",
            domains={"j": IndexDomain(lower="0", upper="3")},
        ),
    )

    def plans(order: tuple[EquationRequest, ...]) -> tuple[OptimizationPlan, ...]:
        result = optimize_analysis(
            AnalysisRequest(
                syntax=FormulaSyntax.SYMPY,
                equations=order,
                variables={"x": VariableDeclaration(domain=MathematicalDomain.REAL)},
            ),
            projection_limit=16,
        )
        assert result.status == "success"
        return result.plans

    forward = plans(equations)
    reversed_order = plans(tuple(reversed(equations)))

    def logical_population(
        items: tuple[OptimizationPlan, ...],
    ) -> list[tuple[tuple[str, ...], str, tuple[tuple[str, str], ...]]]:
        return [
            (
                tuple(step.kind for step in plan.trace),
                plan.suggestion.objective_savings,
                tuple(
                    sorted(
                        (equation.name, equation.expression)
                        for equation in plan.candidate.equations
                    )
                ),
            )
            for plan in items
        ]

    assert logical_population(forward) == logical_population(reversed_order)
    assert tuple(item.name for item in forward[0].candidate.equations[:2]) == ("left", "right")
    assert tuple(item.name for item in reversed_order[0].candidate.equations[:2]) == (
        "right",
        "left",
    )
    assert forward[0].identity != reversed_order[0].identity
