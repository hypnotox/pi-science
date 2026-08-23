# pyright: reportPrivateUsage=false, reportUnusedFunction=false, reportUnusedClass=false, reportUnknownArgumentType=false, reportUnknownMemberType=false, reportUnknownVariableType=false
"""Cross-equation sharing proposal policy."""

from __future__ import annotations

from collections import defaultdict
from collections.abc import Mapping

from py_science.formula._analysis.occurrences import _free_symbols, _Occurrence
from py_science.formula._analysis.retained import RetainedComputation
from py_science.formula.expressions import (
    Expression,
    IndexedValue,
    Symbol,
    expression_node_count,
    substitute,
)

from ..budgets import MAX_OPTIMIZATION_TRANSFORM_NODES
from ..candidates import (
    _all_symbol_names,
    _CandidateDescriptor,
    _canonical_output_expression,
    _canonical_output_index_names,
    _descriptor_from_recipe,
    _replace_paths,
    _smallest_scope,
)


def _cross_equation_descriptors(
    computed: RetainedComputation,
    occurrences_by_target: Mapping[str, tuple[_Occurrence, ...]],
    generated_name: str,
) -> tuple[_CandidateDescriptor, ...]:
    if computed.expression is not None or len(computed.equations) < 2:
        return ()
    equations = {item.name: item for item in computed.equations}
    canonical_reserved: set[str] = set()
    for equation in computed.equations:
        canonical_reserved.update(_all_symbol_names(equation.formula.right))
        for domain in equation.output_domains:
            canonical_reserved.update(_all_symbol_names(domain.lower))
            canonical_reserved.update(_all_symbol_names(domain.upper))
    grouped: dict[
        tuple[int, Expression, tuple[tuple[Expression, Expression], ...]],
        list[_Occurrence],
    ] = defaultdict(list)
    for target, occurrences in occurrences_by_target.items():
        equation = equations[target]
        # Equation-local constraints cannot be attached to one shared producer.
        if equation.submitted_constraints:
            continue
        canonical_output_indices = _canonical_output_index_names(
            len(equation.domain_order), canonical_reserved
        )
        replacements: dict[str, Expression] = {
            name: Symbol(canonical)
            for name, canonical in zip(equation.domain_order, canonical_output_indices, strict=True)
        }
        domain_signature = tuple(
            (
                substitute(domain.lower, replacements, max_nodes=MAX_OPTIMIZATION_TRANSFORM_NODES),
                substitute(domain.upper, replacements, max_nodes=MAX_OPTIMIZATION_TRANSFORM_NODES),
            )
            for domain in equation.output_domains
        )
        for occurrence in occurrences:
            if occurrence.scope.binders or expression_node_count(occurrence.expression) < 2:
                continue
            grouped[
                (
                    len(equation.domain_order),
                    _canonical_output_expression(
                        occurrence.expression,
                        equation.domain_order,
                        canonical_reserved,
                        canonical_output_indices,
                    ),
                    domain_signature,
                )
            ].append(occurrence)

    result: list[_CandidateDescriptor] = []
    for (_arity, _canonical, _domains), grouped_occurrences in grouped.items():
        by_target: dict[str, _Occurrence] = {}
        for occurrence in grouped_occurrences:
            by_target.setdefault(occurrence.target, occurrence)
        if len(by_target) < 2:
            continue
        selected = tuple(by_target[name] for name in sorted(by_target))
        target_names = frozenset(by_target)
        # A producer depending on one of its consumers would introduce a cycle.
        producer_dependencies = {
            computed.producers[name].equation_name
            for name in _all_symbol_names(selected[0].expression)
            if name in computed.producers
        }
        if producer_dependencies & target_names:
            continue
        first = selected[0]
        first_equation = equations[first.target]
        raw = _free_symbols(first.expression)
        interface_positions = tuple(
            position for position, name in enumerate(first_equation.domain_order) if name in raw
        )
        transformed: list[tuple[str, Expression, Expression]] = []
        compatible = True
        for occurrence in selected:
            equation = equations[occurrence.target]
            used_positions = tuple(
                position
                for position, name in enumerate(equation.domain_order)
                if name in _free_symbols(occurrence.expression)
            )
            if used_positions != interface_positions:
                compatible = False
                break
            arguments = tuple(
                Symbol(equation.domain_order[position]) for position in interface_positions
            )
            reference: Expression = (
                IndexedValue(generated_name, arguments) if arguments else Symbol(generated_name)
            )
            transformed.append(
                (
                    occurrence.target,
                    equation.formula.right,
                    _replace_paths(equation.formula.right, (occurrence.path,), reference),
                )
            )
        if not compatible:
            continue
        result.append(
            _descriptor_from_recipe(
                kind="cross_equation_sharing",
                target=first.target,
                original=transformed[0][1],
                proposed=transformed[0][2],
                occurrences=selected,
                transformed_targets=tuple(transformed),
                intermediate_name=generated_name,
                intermediate_expression=first.expression,
                intermediate_scope=_smallest_scope(first.expression, first.scope),
            )
        )
    return tuple(result)


def propose(
    computed: RetainedComputation,
    occurrences_by_target: Mapping[str, tuple[_Occurrence, ...]],
    generated_name: str,
) -> tuple[_CandidateDescriptor, ...]:
    return _cross_equation_descriptors(computed, occurrences_by_target, generated_name)
