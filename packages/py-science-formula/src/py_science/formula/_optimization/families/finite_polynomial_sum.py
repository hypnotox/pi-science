# pyright: reportPrivateUsage=false, reportUnusedFunction=false, reportUnusedClass=false, reportUnknownArgumentType=false, reportUnknownMemberType=false, reportUnknownVariableType=false
"""Exact finite-polynomial Sum proposal policy."""

from __future__ import annotations

from py_science.formula._analysis.occurrences import _Occurrence
from py_science.formula.expressions import Expression
from py_science.formula.reasoning import ReasoningContext
from py_science.formula.series import CheckedNestedSumResult, derive_checked_nested_sum

from ..candidates import _CandidateDescriptor, _descriptor_from_recipe, _replace_paths


def propose(
    target: str,
    expression: Expression,
    occurrences: tuple[_Occurrence, ...],
    reasoning: ReasoningContext,
) -> tuple[_CandidateDescriptor, ...]:
    checked = derive_checked_nested_sum(expression, reasoning)
    if not isinstance(checked, CheckedNestedSumResult):
        return ()
    occurrence = next(
        (
            item
            for item in occurrences
            if item.path == checked.path and item.expression == checked.original
        ),
        None,
    )
    if occurrence is None:
        return ()
    return (
        _descriptor_from_recipe(
            kind="finite_polynomial_sum_v1",
            target=target,
            original=expression,
            proposed=_replace_paths(expression, (checked.path,), checked.candidate),
            occurrences=(occurrence,),
        ),
    )
