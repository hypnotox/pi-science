# pyright: reportPrivateUsage=false, reportUnusedFunction=false, reportUnusedClass=false, reportUnknownArgumentType=false, reportUnknownMemberType=false, reportUnknownVariableType=false
"""Private optimizer owner."""

from __future__ import annotations

import json
from itertools import permutations

from py_science.formula._analysis.retained import RetainedComputation
from py_science.formula.expressions import (
    Expression,
)
from py_science.formula.models import (
    AnalysisRequest,
    OptimizationSuggestion,
)
from py_science.formula.sympy_backend import (
    render,
)

from .candidates import (
    _all_symbol_names,
    _CandidateComputation,
    _canonical_output_expression,
    _canonical_output_index_names,
    _generated_let_variants,
)


def _candidate_semantic_key(  # pyright: ignore[reportUnusedFunction]
    candidate: _CandidateComputation,
) -> tuple[object, ...]:
    """Legacy local-proposal identity retained for focused generator tests only."""
    transformations = candidate.transformed_targets or (
        (candidate.target, candidate.original, candidate.proposed),
    )
    return (
        tuple((target, proposed) for target, _original, proposed in transformations),
        candidate.intermediate_expression,
        candidate.intermediate_scope,
    )


def _stable_json(value: object) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def _canonical_state_key(
    request: AnalysisRequest,
    computed: RetainedComputation,
    generated_names: tuple[str, ...],
) -> tuple[object, ...]:
    """Serialize complete computation semantics independently of search history."""
    names = tuple(dict.fromkeys(generated_names))
    context = (
        request.syntax.value,
        _stable_json(
            {name: value.model_dump(mode="json") for name, value in request.variables.items()}
        ),
        _stable_json([value.model_dump(mode="json") for value in request.functions]),
        _stable_json([value.model_dump(mode="json") for value in request.primitive_costs]),
        _stable_json([value.model_dump(mode="json") for value in request.assumptions]),
        _stable_json([value.model_dump(mode="json") for value in request.definitions]),
        tuple(request.outputs),
    )

    def serialize(
        generated: dict[str, str], expression: Expression | None = None
    ) -> tuple[object, ...]:
        if computed.expression is not None:
            source = computed.expression if expression is None else expression
            canonical = _canonical_output_expression(source, (), free_names=generated)
            return (*context, "expression", render(canonical).sympy)

        equations: list[tuple[object, ...]] = []
        for equation in sorted(
            computed.equations, key=lambda item: generated.get(item.name, item.name)
        ):
            reserved = _all_symbol_names(equation.formula.right)
            for domain in equation.output_domains:
                reserved.update(_all_symbol_names(domain.lower))
                reserved.update(_all_symbol_names(domain.upper))
            canonical_indices = _canonical_output_index_names(len(equation.domain_order), reserved)
            index_names = dict(zip(equation.domain_order, canonical_indices, strict=True))
            canonical_right = _canonical_output_expression(
                equation.formula.right,
                equation.domain_order,
                reserved,
                canonical_indices,
                generated,
            )
            domains = tuple(
                (
                    index_names[domain.index],
                    render(
                        _canonical_output_expression(
                            domain.lower,
                            equation.domain_order,
                            reserved,
                            canonical_indices,
                            generated,
                        )
                    ).sympy,
                    render(
                        _canonical_output_expression(
                            domain.upper,
                            equation.domain_order,
                            reserved,
                            canonical_indices,
                            generated,
                        )
                    ).sympy,
                )
                for domain in equation.output_domains
            )
            constraints = tuple(
                sorted(
                    (
                        name,
                        index_names[target],
                        relationship.operator.value,
                        render(
                            _canonical_output_expression(
                                relationship.left,
                                equation.domain_order,
                                reserved,
                                canonical_indices,
                                generated,
                            )
                        ).sympy,
                        render(
                            _canonical_output_expression(
                                relationship.right,
                                equation.domain_order,
                                reserved,
                                canonical_indices,
                                generated,
                            )
                        ).sympy,
                    )
                    for name, target, relationship in equation.constraints
                )
            )
            equations.append(
                (
                    generated.get(equation.name, equation.name),
                    tuple(canonical_indices),
                    render(canonical_right).sympy,
                    domains,
                    constraints,
                )
            )
        return (*context, "system", tuple(equations))

    # Generated producers are binders in the complete state, not trace-order
    # labels. Depth two has at most two, so select the least complete
    # serialization across their name bijections and dependency-valid Let
    # orders. Independent producer introduction order is not state semantics.
    name_orders = tuple(permutations(names)) if names else ((),)
    expression_variants = (
        _generated_let_variants(computed.expression, frozenset(names))
        if computed.expression is not None
        else (None,)
    )
    return min(
        serialize(
            {name: f"optimization_generated_{position}" for position, name in enumerate(order)},
            expression,
        )
        for order in name_orders
        for expression in expression_variants
    )


def _trace_key(
    trace: tuple[tuple[OptimizationSuggestion, AnalysisRequest], ...],
) -> tuple[object, ...]:
    return tuple(
        (
            suggestion.kind,
            tuple(
                (
                    item.target.kind,
                    item.target.name or "",
                    tuple(occurrence.path for occurrence in item.occurrences),
                    item.proposed.normalized_sympy,
                )
                for item in suggestion.transformations
            ),
            candidate.model_dump_json(exclude_none=True),
        )
        for suggestion, candidate in trace
    )
