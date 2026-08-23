# pyright: reportPrivateUsage=false, reportUnusedFunction=false, reportUnusedClass=false, reportUnknownArgumentType=false, reportUnknownMemberType=false, reportUnknownVariableType=false
"""Neutral-operation removal proposal policy."""

from __future__ import annotations

from py_science.formula._analysis.occurrences import _Occurrence
from py_science.formula.expressions import Expression

from ..candidates import _CandidateDescriptor, _neutral_replacement, _replacement_descriptor


def propose(
    target: str, expression: Expression, occurrence: _Occurrence
) -> tuple[_CandidateDescriptor, ...]:
    replacement = _neutral_replacement(occurrence.expression)
    return (
        ()
        if replacement is None
        else (
            _replacement_descriptor(
                kind="redundant_operation_removal",
                target=target,
                original=expression,
                occurrences=(occurrence,),
                replacement=replacement,
            ),
        )
    )
