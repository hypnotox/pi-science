# pyright: reportMissingTypeStubs=false, reportPrivateUsage=false, reportUnknownMemberType=false, reportUnknownArgumentType=false, reportUnknownVariableType=false, reportAttributeAccessIssue=false, reportArgumentType=false, reportReturnType=false
"""Explicit, bounded geometric-linear series rules; never calls SymPy summation."""

from __future__ import annotations

from collections.abc import Iterator
from dataclasses import dataclass
from typing import Any

from py_science.formula.analyzer import count_operations
from py_science.formula.expressions import (
    BinaryExpression,
    BinaryOperator,
    Call,
    Expression,
    IndexedValue,
    InfinityLiteral,
    IntegerLiteral,
    RationalLiteral,
    Sum,
    Symbol,
    expression_children,
    expression_node_count,
)
from py_science.formula.models import (
    ClosedFormEvidence,
    DerivedCandidate,
    Interpretation,
    OperationCounts,
    QueryAnswer,
)
from py_science.formula.parser import ParseFailure, parse_expression
from py_science.formula.reasoning import ReasoningContext
from py_science.formula.sympy_backend import (
    bounded_linear_coefficients,
    bounded_series_candidate,
    bounded_series_verify,
    rational_ir_preflight,
    render,
)

MAX_NODES = 4096


@dataclass(frozen=True, slots=True)
class SeriesRule:
    candidate: Expression
    verification: str
    conditions: tuple[str, ...]
    uses: tuple[Any, ...]


def derive_closed_form(expression: Expression, reasoning: ReasoningContext | None) -> QueryAnswer:
    if reasoning is None:
        return _unresolved("query reasoning exceeds its bound")
    # This is the common pre-call gate, including sibling (not total descendant) sums.
    if expression_node_count(expression) > 512 or not _series_preflight(expression):
        return _unresolved("query family is unsupported")
    sums = _sums(expression)
    if not sums or len(sums) > 8:
        return _unresolved("query family is unsupported")
    if any(_has_nested_sum(item.body) for item in sums):
        return _unresolved("nested sums are unsupported")
    if not _supported_shell(expression):
        return _unresolved("query family is unsupported")
    rules: list[SeriesRule] = []
    for item in sums:
        rule = _derive_sum(item, reasoning)
        if isinstance(rule, QueryAnswer):
            return rule
        rules.append(rule)
    candidate = expression
    for item, rule in zip(sums, rules, strict=True):
        candidate = _replace(candidate, item, rule.candidate)
        if expression_node_count(candidate) > MAX_NODES:
            return _unresolved("query derived expression exceeds its bound")
    try:
        interpretation = render(candidate)
        source = render(expression).sympy
    except Exception:
        return _unresolved("query candidate cannot be rendered")
    if max(len(interpretation.sympy), len(interpretation.latex), len(source)) > 4096:
        return _unresolved("query candidate rendering exceeds its bound")
    tally = count_operations(candidate)
    conditions = tuple(dict.fromkeys(condition for rule in rules for condition in rule.conditions))
    uses = _unique(tuple(use for rule in rules for use in rule.uses))
    return QueryAnswer(
        conclusion="proved_under_assumptions" if uses or conditions else "proved",
        conditions=conditions,
        assumptions_used=uses,
        evidence=ClosedFormEvidence(
            verification=(
                "infinite_partial_sum"
                if any(r.verification == "infinite_partial_sum" for r in rules)
                else "finite_antidifference"
            ),
            statement=f"{source} = {interpretation.sympy}",
        ),
        derived_candidates=(
            DerivedCandidate(
                interpretation=Interpretation(
                    normalized_sympy=interpretation.sympy, normalized_latex=interpretation.latex
                ),
                operation_counts=OperationCounts(
                    additions=tally.additions,
                    subtractions=tally.subtractions,
                    multiplications=tally.multiplications,
                    divisions=tally.divisions,
                    powers=tally.powers,
                ),
            ),
        ),
    )


def _derive_sum(item: Sum, reasoning: ReasoningContext) -> SeriesRule | QueryAnswer:
    if (
        _contains_forbidden(item.body)
        or _contains_index(item.lower, item.index)
        or _contains_index(item.upper, item.index)
    ):
        return _unresolved("query family is unsupported")
    try:
        lower, upper, body = (
            reasoning.apply(item.lower),
            reasoning.apply(item.upper),
            reasoning.apply(item.body),
        )
    except Exception:
        return _unresolved("query reasoning exceeds its bound")
    if not reasoning.proves_integral(lower) or (
        not isinstance(upper, InfinityLiteral) and not reasoning.proves_integral(upper)
    ):
        return _unresolved("series bounds are not proved integral")
    parsed = _linear_geometric(body, item.index)
    if parsed is None:
        return _unresolved("query family is unsupported")
    a, b, r = parsed
    uses: tuple[Any, ...] = ()
    if not isinstance(upper, InfinityLiteral):
        ordered, order_uses = reasoning.prove_ordered(lower, upper)
        if not ordered:
            empty, empty_uses = reasoning.prove_strictly_ordered(upper, lower)
            if empty:
                return SeriesRule(
                    IntegerLiteral(0),
                    "finite_antidifference",
                    (f"{render(lower).sympy} > {render(upper).sympy}: empty range",),
                    empty_uses,
                )
            return _unresolved(
                "series bounds are not proved ordered", reasoning.relevant_unsupported(_names(item))
            )
        uses = order_uses
    # A submitted r**k has an original r != 0 obligation whenever k can be negative.
    nonnegative_lower, lower_uses = reasoning.prove_nonnegative(lower)
    if not nonnegative_lower:
        ratio_nonzero, ratio_uses = reasoning.prove_nonzero(r)
        if not ratio_nonzero:
            return _unresolved(
                "series ratio is not proved nonzero for a negative exponent range",
                reasoning.relevant_unsupported(_names(item)),
            )
        uses = _unique((*uses, *ratio_uses))
        negative_condition = (f"{render(r).sympy} != 0",)
    else:
        uses = _unique((*uses, *lower_uses))
        negative_condition = ()
    if isinstance(upper, InfinityLiteral):
        if upper.sign < 0:
            return _unresolved("query family is unsupported")
        converges, convergence_uses = reasoning.proves_abs_less_one_expression(r)
        if not converges:
            divergent, divergence_uses = reasoning.proves_abs_at_least_one(r)
            nonzero, nonzero_uses = reasoning.prove_nonzero(a if not _zero(a) else b)
            if divergent and nonzero:
                return QueryAnswer(
                    conclusion="inapplicable",
                    conditions=("Abs(r) >= 1: the nonzero geometric-linear series diverges",),
                    assumptions_used=_unique((*divergence_uses, *nonzero_uses)),
                )
            return _unresolved(
                "series convergence is not proved", reasoning.relevant_unsupported(_names(item))
            )
        built = bounded_series_candidate(a, b, r, lower, None)
        if built is None or not bounded_series_verify(a, b, r, lower, None, built):
            return _unresolved("series partial-sum verification failed")
        candidate = _parse_candidate(built)
        if candidate is None:
            return _unresolved("query derived expression exceeds its bound")
        ratio = render(r).sympy
        return SeriesRule(
            candidate,
            "infinite_partial_sum",
            (*negative_condition, f"Abs({ratio}) < 1", f"{ratio} != 1"),
            _unique((*uses, *convergence_uses)),
        )
    one, one_uses = reasoning.prove_equal_one(r)
    if one:
        built = bounded_series_candidate(a, b, r, lower, upper, ratio_is_one=True)
        conditions = (*negative_condition, f"{render(r).sympy} = 1")
        all_uses = _unique((*uses, *one_uses))
    else:
        not_one, not_one_uses = reasoning.prove_nonzero(
            BinaryExpression(BinaryOperator.SUBTRACT, r, IntegerLiteral(1))
        )
        if not_one is False:
            return _unresolved("series ratio is neither proved equal to one nor different from one")
        built = bounded_series_candidate(a, b, r, lower, upper)
        conditions = (*negative_condition, f"{render(r).sympy} != 1")
        all_uses = _unique((*uses, *not_one_uses))
    if built is None or not bounded_series_verify(a, b, r, lower, upper, built, ratio_is_one=one):
        return _unresolved("series antidifference verification failed")
    candidate = _parse_candidate(built)
    if candidate is None:
        return _unresolved("query derived expression exceeds its bound")
    return SeriesRule(candidate, "finite_antidifference", conditions, all_uses)


def _parse_candidate(value: Any) -> Expression | None:
    source = str(value)
    if source.startswith("(-"):
        source = "(0-" + source[2:]
    parsed = parse_expression(source)
    return (
        None
        if isinstance(parsed, (ParseFailure, tuple)) or expression_node_count(parsed) > MAX_NODES
        else parsed
    )


def _linear_geometric(
    value: Expression, index: str
) -> tuple[Expression, Expression, Expression] | None:
    """Collect only a bounded sum of products sharing exactly one r**k factor."""
    terms = _flatten(value, BinaryOperator.ADD)
    ratio: Expression | None = None
    coefficient_terms: list[Expression] = []
    for term in terms:
        factors = _flatten(term, BinaryOperator.MULTIPLY)
        powers = [
            factor
            for factor in factors
            if isinstance(factor, BinaryExpression)
            and factor.operator is BinaryOperator.POWER
            and isinstance(factor.right, Symbol)
            and factor.right.name == index
        ]
        if len(powers) != 1 or _contains_index(powers[0].left, index):
            return None
        if ratio is None:
            ratio = powers[0].left
        elif ratio != powers[0].left:
            return None
        rest = [factor for factor in factors if factor != powers[0]]
        coefficient_terms.append(_product(rest))
    if ratio is None:
        return None
    coefficient = _sum(coefficient_terms)
    # The only collection operation is guarded and isolated in the bounded backend seam.
    collected = bounded_linear_coefficients(coefficient, index)
    if collected is None:
        return None
    a, b = (parse_expression(item) for item in collected)
    if isinstance(a, (ParseFailure, tuple)) or isinstance(b, (ParseFailure, tuple)):
        return None
    return a, b, ratio


def _flatten(value: Expression, op: BinaryOperator) -> list[Expression]:
    if isinstance(value, BinaryExpression) and value.operator is op:
        return [*_flatten(value.left, op), *_flatten(value.right, op)]
    return [value]


def _product(values: list[Expression]) -> Expression:
    result: Expression = IntegerLiteral(1)
    for value in values:
        result = BinaryExpression(BinaryOperator.MULTIPLY, result, value)
    return result


def _sum(values: list[Expression]) -> Expression:
    result: Expression = IntegerLiteral(0)
    for value in values:
        result = BinaryExpression(BinaryOperator.ADD, result, value)
    return result


def _series_preflight(value: Expression) -> bool:
    if isinstance(value, Sum):
        return (
            _series_preflight(value.body)
            and rational_ir_preflight(value.lower)
            and (isinstance(value.upper, InfinityLiteral) or rational_ir_preflight(value.upper))
        )
    if isinstance(value, (Call, IndexedValue, InfinityLiteral)):
        return False
    return all(_series_preflight(child) for child in expression_children(value))


def _sums(value: Expression) -> list[Sum]:
    return [node for node in _walk(value) if isinstance(node, Sum)]


def _walk(value: Expression) -> Iterator[Expression]:
    yield value
    for child in expression_children(value):
        yield from _walk(child)


def _has_nested_sum(value: Expression) -> bool:
    return any(isinstance(node, Sum) for node in _walk(value))


def _contains_forbidden(value: Expression) -> bool:
    return any(
        isinstance(node, (Call, IndexedValue, Sum, InfinityLiteral)) for node in _walk(value)
    )


def _contains_index(value: Expression, index: str) -> bool:
    return any(isinstance(node, Symbol) and node.name == index for node in _walk(value))


def _supported_shell(value: Expression) -> bool:
    if isinstance(value, Sum):
        return not isinstance(value.upper, InfinityLiteral) or value.upper.sign > 0
    if isinstance(value, (Call, IndexedValue, InfinityLiteral)):
        return False
    return all(_supported_shell(child) for child in expression_children(value))


def _replace(value: Expression, old: Sum, new: Expression) -> Expression:
    if value == old:
        return new
    if isinstance(value, BinaryExpression):
        return BinaryExpression(
            value.operator, _replace(value.left, old, new), _replace(value.right, old, new)
        )
    return value


def _zero(value: Expression) -> bool:
    return (isinstance(value, IntegerLiteral) and value.value == 0) or (
        isinstance(value, RationalLiteral) and value.numerator == 0
    )


def _names(value: Expression) -> set[str]:
    return {node.name for node in _walk(value) if isinstance(node, Symbol)}


def _unique(values: tuple[Any, ...]) -> tuple[Any, ...]:
    seen: set[tuple[str, str]] = set()
    result = []
    for value in values:
        key = (value.name, value.relationship)
        if key not in seen:
            seen.add(key)
            result.append(value)
    return tuple(result)


def _unresolved(blocker: str, unsupported: tuple[str, ...] = ()) -> QueryAnswer:
    return QueryAnswer(
        conclusion="unresolved", blockers=(blocker,), relevant_unsupported_assumptions=unsupported
    )
