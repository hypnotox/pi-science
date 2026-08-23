# pyright: reportPrivateUsage=false, reportUnusedFunction=false, reportUnusedClass=false, reportUnknownArgumentType=false, reportUnknownMemberType=false, reportUnknownVariableType=false
"""Private optimizer owner."""

from __future__ import annotations

from py_science.formula._analysis.retained import RetainedComputation
from py_science.formula.models import (
    AnalysisRequest,
    OptimizationCandidate,
    OptimizationPlan,
    OptimizationTraceStep,
)

from .verifier import _Accepted


def project_plan(
    item: _Accepted, request: AnalysisRequest, computed: RetainedComputation
) -> OptimizationPlan:
    """Project an accepted final state into the public immutable plan model."""
    candidate_request = item.candidate
    candidate = OptimizationCandidate(
        syntax=candidate_request.syntax,
        expression=candidate_request.expression,
        equations=candidate_request.equations,
        variables=candidate_request.variables,
        functions=candidate_request.functions,
        primitive_costs=candidate_request.primitive_costs,
        assumptions=candidate_request.assumptions,
        definitions=candidate_request.definitions,
        outputs=("expression",)
        if candidate_request.expression is not None
        else tuple(equation.name for equation in computed.equations),
    )
    identity = candidate.model_dump_json(exclude_none=True)
    trace = tuple(
        OptimizationTraceStep(
            kind=s.kind,
            tier=s.tier,
            transformations=s.transformations,
            intermediate=s.intermediate,
            conclusion=s.conclusion,
            evidence=s.evidence,
            conditions=s.conditions,
            assumptions_used=s.assumptions_used,
            objective_before=s.objective_before,
            objective_after=s.objective_after,
            objective_savings=s.objective_savings,
            candidate=OptimizationCandidate(
                syntax=r.syntax,
                expression=r.expression,
                equations=r.equations,
                variables=r.variables,
                functions=r.functions,
                primitive_costs=r.primitive_costs,
                assumptions=r.assumptions,
                definitions=r.definitions,
                outputs=("expression",)
                if r.expression is not None
                else tuple(e.name for e in computed.equations),
            ),
            identity=OptimizationCandidate(
                syntax=r.syntax,
                expression=r.expression,
                equations=r.equations,
                variables=r.variables,
                functions=r.functions,
                primitive_costs=r.primitive_costs,
                assumptions=r.assumptions,
                definitions=r.definitions,
                outputs=("expression",)
                if r.expression is not None
                else tuple(e.name for e in computed.equations),
            ).model_dump_json(exclude_none=True),
        )
        for s, r in (item.trace or ((item.suggestion, item.candidate),))
    )
    return OptimizationPlan(
        identity=identity,
        objective=request.optimization.objective,
        candidate=candidate,
        suggestion=item.suggestion,
        trace=trace,
    )
