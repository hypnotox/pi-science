# pyright: reportPrivateUsage=false, reportUnusedFunction=false, reportUnusedClass=false, reportUnknownArgumentType=false, reportUnknownMemberType=false, reportUnknownVariableType=false
"""Bounded Horner proposal policy."""

from __future__ import annotations

from py_science.formula._analysis.occurrences import _Occurrence
from py_science.formula.expressions import Equation, Expression, Relationship
from py_science.formula.parser import ParseFailure, parse_expression
from py_science.formula.sympy_backend import (
    BoundedHornerCandidate,
    BoundedHornerRefusal,
    bounded_horner_candidate,
    render,
)

from ..budgets import (
    MAX_HORNER_DEGREE,
    MAX_HORNER_GENERATED_NODES,
    MAX_HORNER_TARGET_NODES,
    MAX_HORNER_TERMS,
    MAX_HORNER_VARIABLES,
)
from ..candidates import _CandidateComputation, _CandidateDescriptor, _replace_paths


def _horner_candidate(
    target: str, original: Expression, occurrence: _Occurrence, rendered: str
) -> _CandidateComputation:
    """Parse the bounded Horner rendering only after scheduler admission."""
    parsed = parse_expression(rendered)
    assert not isinstance(parsed, (ParseFailure, Equation, Relationship))
    return _CandidateComputation(
        kind="horner",
        target=target,
        original=original,
        proposed=_replace_paths(original, (occurrence.path,), parsed),
        occurrences=(occurrence,),
    )


def propose(
    target: str, expression: Expression, occurrence: _Occurrence
) -> tuple[tuple[_CandidateDescriptor, ...], tuple[str, ...]]:
    result = bounded_horner_candidate(
        occurrence.expression,
        max_target_nodes=MAX_HORNER_TARGET_NODES,
        max_polynomial_variables=MAX_HORNER_VARIABLES,
        max_degree=MAX_HORNER_DEGREE,
        max_terms=MAX_HORNER_TERMS,
        max_generated_nodes=MAX_HORNER_GENERATED_NODES,
    )
    if isinstance(result, BoundedHornerRefusal):
        detail = f"optimization Horner {result.resource}" + (
            "" if result.resource.endswith("refusal") else " refused"
        )
        if result.observed is not None and result.configured is not None:
            detail += f" (measured {result.observed}, configured {result.configured})"
        return (), (detail,)
    if not isinstance(result, BoundedHornerCandidate):
        return (), ()
    rendered = result.rendered
    return (
        _CandidateDescriptor(
            "horner",
            ("horner", target, render(expression).sympy, occurrence.path, rendered),
            lambda: _horner_candidate(target, expression, occurrence, rendered),
        ),
    ), ()
