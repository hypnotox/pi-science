# pyright: reportPrivateUsage=false, reportUnusedFunction=false, reportUnusedClass=false, reportUnknownArgumentType=false, reportUnknownMemberType=false, reportUnknownVariableType=false
"""Cross-equation sharing proposal policy."""

from __future__ import annotations

from collections.abc import Mapping

from py_science.formula._analysis.occurrences import _Occurrence
from py_science.formula._analysis.retained import RetainedComputation

from ..candidates import _CandidateDescriptor, _cross_equation_descriptors


def propose(
    computed: RetainedComputation,
    occurrences_by_target: Mapping[str, tuple[_Occurrence, ...]],
    generated_name: str,
) -> tuple[_CandidateDescriptor, ...]:
    return _cross_equation_descriptors(computed, occurrences_by_target, generated_name)
