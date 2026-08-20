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
    with pytest.raises(FrozenInstanceError):
        repeated[0].path = ()  # type: ignore[misc]


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
    with pytest.raises(_TraversalExhausted):
        _detect_occurrences("a", expression, {}, max_nodes=1)
