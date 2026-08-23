# pyright: reportPrivateUsage=false, reportUnusedFunction=false, reportUnusedClass=false, reportUnknownArgumentType=false, reportUnknownMemberType=false, reportUnknownVariableType=false
"""Iterator-invariant hoisting proposal policy."""

from __future__ import annotations

from py_science.formula._analysis.occurrences import _EvaluationScope, _free_symbols, _Occurrence
from py_science.formula.expressions import BinaryExpression, Call, Expression, expression_node_count

from ..candidates import _CandidateDescriptor, _generated_replacement_descriptor, _smallest_scope


def propose(
    target: str, expression: Expression, occurrence: _Occurrence, generated_name: str
) -> tuple[_CandidateDescriptor, ...]:
    node = occurrence.expression
    if (
        not occurrence.scope.binders
        or not isinstance(node, (BinaryExpression, Call))
        or expression_node_count(node) <= 1
    ):
        return ()
    binding = occurrence.scope.binders[-1]
    if binding.name in _free_symbols(node) or occurrence.path[: len(binding.path) + 1] != (
        *binding.path,
        2,
    ):
        return ()
    outer = _EvaluationScope(
        occurrence.scope.output_indices,
        occurrence.scope.output_bindings,
        occurrence.scope.binders[:-1],
    )
    return (
        _generated_replacement_descriptor(
            kind="iterator_invariant_hoisting",
            target=target,
            original=expression,
            occurrences=(occurrence,),
            generated_name=generated_name,
            intermediate_expression=node,
            intermediate_scope=_smallest_scope(node, outer),
        ),
    )
