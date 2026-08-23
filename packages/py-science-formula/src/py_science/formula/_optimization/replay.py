# pyright: reportPrivateUsage=false, reportUnusedFunction=false, reportUnusedClass=false, reportUnknownArgumentType=false, reportUnknownMemberType=false, reportUnknownVariableType=false
"""Construction and authoritative replay of optimizer candidates."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass

from py_science.formula._analysis.retained import RetainedComputation
from py_science.formula.expressions import Equation, Expression, IndexedValue, Symbol
from py_science.formula.models import AnalysisFailure, AnalysisRequest, EquationRequest
from py_science.formula.sympy_backend import render

from .candidates import _CandidateComputation, _wrap_complete_let

type _RetainedAnalyzer = Callable[[AnalysisRequest], RetainedComputation | AnalysisFailure]


@dataclass(frozen=True, slots=True)
class _ReplayResult:
    """A complete candidate request and its one authoritative ordinary-analysis replay."""

    request: AnalysisRequest
    computed: RetainedComputation | AnalysisFailure


def _complete_candidate(
    candidate: _CandidateComputation,
    request: AnalysisRequest,
    computed: RetainedComputation,
) -> AnalysisRequest:
    """Build the authoritative, reparseable computation for one local proposal."""
    intermediate_name = candidate.intermediate_name
    intermediate_expression = candidate.intermediate_expression
    intermediate_scope = candidate.intermediate_scope
    if intermediate_expression is not None:
        assert intermediate_name is not None and intermediate_scope is not None
    transformations = dict(
        (target, proposed)
        for target, _original, proposed in (
            candidate.transformed_targets
            or ((candidate.target, candidate.original, candidate.proposed),)
        )
    )
    if computed.expression is not None:
        expression = transformations["expression"]
        if candidate.intermediate_expression is not None:
            expression = _wrap_complete_let(expression, candidate)
        complete = request.model_copy(
            update={"expression": render(expression).sympy, "queries": (), "scenarios": ()}
        )
        return AnalysisRequest.model_validate(complete.model_dump(mode="python"))

    equations: list[EquationRequest] = []
    for source in request.equations:
        # Untouched equations are transport state, not optimizer output: retain
        # the caller serialization exactly so every replay step has a stable
        # parent-child boundary.  Only a local transformation is rendered.
        if source.name not in transformations:
            equations.append(source)
            continue
        parsed = next(item for item in computed.equations if item.name == source.name)
        right = transformations[source.name]
        if (
            source.name == candidate.target
            and intermediate_expression is not None
            and intermediate_scope is not None
            and intermediate_scope.binders
        ):
            right = _wrap_complete_let(right, candidate)
        equation = render(Equation(parsed.formula.left, right)).sympy
        equations.append(source.model_copy(update={"expression": equation}))
    if (
        intermediate_expression is not None
        and intermediate_scope is not None
        and not intermediate_scope.binders
    ):
        assert intermediate_name is not None
        indices = intermediate_scope.output_indices
        target = next(item for item in request.equations if item.name == candidate.target)
        left: Expression = (
            IndexedValue(intermediate_name, tuple(Symbol(name) for name in indices))
            if indices
            else Symbol(intermediate_name)
        )
        equations.append(
            EquationRequest(
                name=intermediate_name,
                expression=render(Equation(left, intermediate_expression)).sympy,
                domains={name: target.domains[name] for name in indices},
                constraints=tuple(
                    constraint for constraint in target.constraints if constraint.target in indices
                ),
            )
        )
    complete = request.model_copy(
        update={"expression": None, "equations": tuple(equations), "queries": (), "scenarios": ()}
    )
    return AnalysisRequest.model_validate(complete.model_dump(mode="python"))


def _replay_request(request: AnalysisRequest, *, analyzer: _RetainedAnalyzer) -> _ReplayResult:
    """Invoke the explicit ordinary-analysis seam for a complete request."""
    return _ReplayResult(request=request, computed=analyzer(request))


def _replay_candidate(
    candidate: _CandidateComputation,
    request: AnalysisRequest,
    computed: RetainedComputation,
    *,
    analyzer: _RetainedAnalyzer,
) -> _ReplayResult:
    """Construct and replay an untrusted candidate through the only analyzer seam."""
    complete = _complete_candidate(candidate, request, computed)
    return _replay_request(complete, analyzer=analyzer)
