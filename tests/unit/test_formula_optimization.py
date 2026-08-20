# pyright: reportPrivateUsage=false
from dataclasses import FrozenInstanceError
from typing import cast

import pytest
from py_science.formula.expressions import Expression
from py_science.formula.optimization import (
    _detect_occurrences,
    _extraction_opportunities,
    _TraversalExhausted,
)
from py_science.formula.parser import ParseFailure, parse_expression


def _expression(source: str):
    parsed = parse_expression(source)
    assert not isinstance(parsed, ParseFailure)
    return cast(Expression, parsed)


def test_typed_occurrences_keep_paths_free_symbols_and_sum_scope() -> None:
    expression = _expression("Sum(x[i] + 1, (i, 0, N)) + Sum(x[i] + 1, (i, 0, N))")

    occurrences = _detect_occurrences("out", expression, {}, output_indices=("j",))
    repeated = [item for item in occurrences if item.path in {(0, 2), (1, 2)}]

    assert [(item.target, item.path) for item in repeated] == [
        ("out", (0, 2)),
        ("out", (1, 2)),
    ]
    assert all(item.binders == ("i",) for item in repeated)
    assert all(item.scope.output_indices == ("j",) for item in repeated)
    assert all(item.free_symbols == frozenset({"x"}) for item in repeated)
    assert repeated[0].scope.binders != repeated[1].scope.binders
    with pytest.raises(FrozenInstanceError):
        repeated[0].path = ()  # type: ignore[misc]


def test_output_indices_are_bound_and_domains_distinguish_evaluation_scopes() -> None:
    expression = _expression("x[i] + 1")
    lower, upper_n, upper_m = _expression("0"), _expression("N"), _expression("M")

    with_n = _detect_occurrences(
        "out",
        expression,
        {},
        output_indices=("i",),
        output_domains={"i": (lower, upper_n)},
    )[0]
    with_m = _detect_occurrences(
        "out",
        expression,
        {},
        output_indices=("i",),
        output_domains={"i": (lower, upper_m)},
    )[0]

    assert with_n.free_symbols == frozenset({"x"})
    assert with_n.scope.output_bindings[0].upper == upper_n
    assert with_n.scope != with_m.scope


def test_shadowed_binders_keep_lexical_identity_and_capture_context() -> None:
    expression = _expression("Sum(Sum(x[i] + 1, (i, 0, M)), (i, 0, N))")

    body = next(
        item for item in _detect_occurrences("out", expression, {}, output_indices=("i",))
        if item.path == (2, 2)
    )

    assert body.binders == ("i", "i")
    assert tuple(binding.path for binding in body.scope.binders) == ((), (2,))
    assert body.scope.output_indices == ("i",)
    assert body.free_symbols == frozenset({"x"})


def test_call_paths_and_named_producer_index_paths_are_observable() -> None:
    call = _detect_occurrences("out", _expression("f(x + 1)"), {})
    assert [(item.path, type(item.expression).__name__) for item in call] == [
        ((), "Call"),
        ((0,), "BinaryExpression"),
    ]

    producer_expression = _expression("p[x + 1] + p[x + 1]")
    without_producer = _detect_occurrences("out", producer_expression, {})
    with_producer = _detect_occurrences("out", producer_expression, {"p": object()})
    assert [item.path for item in without_producer if item.path in {(0, 0), (1, 0)}] == [
        (0, 0),
        (1, 0),
    ]
    assert [item.path for item in with_producer] == [(), (0, 0), (1, 0)]


def test_sum_bounds_remain_outside_the_new_binder_and_named_producers_are_skipped() -> None:
    expression = _expression("Sum(x + 1, (i, x + 1, x + 1))")

    occurrences = _detect_occurrences("out", expression, {"x": object()})

    assert [(item.path, item.binders) for item in occurrences] == [
        ((), ()),
        ((0,), ()),
        ((1,), ()),
        ((2,), ("i",)),
    ]


def test_extraction_renderer_preserves_legacy_text_and_exhaustion_is_quiet() -> None:
    expression = _expression("x[i] + 1 + (x[i] + 1)")

    assert _extraction_opportunities("a", expression, {}) == (
        "equation a: extract repeated `x[i] + 1` (2 occurrences)",
    )
    assert _extraction_opportunities("a", _expression("x + 1"), {}) == ()
    with pytest.raises(_TraversalExhausted):
        _detect_occurrences("a", expression, {}, max_nodes=1)
