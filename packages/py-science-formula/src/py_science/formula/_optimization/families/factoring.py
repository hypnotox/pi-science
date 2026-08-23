# pyright: reportPrivateUsage=false, reportUnusedFunction=false, reportUnusedClass=false, reportUnknownArgumentType=false, reportUnknownMemberType=false, reportUnknownVariableType=false
"""Bounded factoring proposal policy."""

from __future__ import annotations

from py_science.formula._analysis.occurrences import _Occurrence
from py_science.formula.expressions import Expression

from ..candidates import _CandidateDescriptor, _factored, _replacement_descriptor


def propose(
    target: str, expression: Expression, occurrence: _Occurrence
) -> tuple[_CandidateDescriptor, ...]:
    replacement = _factored(occurrence.expression)
    return (
        ()
        if replacement is None
        else (
            _replacement_descriptor(
                kind="factoring",
                target=target,
                original=expression,
                occurrences=(occurrence,),
                replacement=replacement,
            ),
        )
    )
