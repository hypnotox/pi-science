# pyright: reportUnknownMemberType=false, reportUnknownVariableType=false, reportUnknownArgumentType=false
from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import Any, Protocol, cast

import sympy  # pyright: ignore[reportMissingTypeStubs]
from py_science.formula.expressions import (
    BinaryExpression,
    BinaryOperator,
    Call,
    Equation,
    Expression,
    IndexedValue,
    InfinityLiteral,
    IntegerLiteral,
    RationalLiteral,
    Sum,
    Symbol,
    expression_node_count,
)


class SympyExpression(Protocol):
    def __add__(self, other: object, /) -> SympyExpression: ...

    def __sub__(self, other: object, /) -> SympyExpression: ...

    def __mul__(self, other: object, /) -> SympyExpression: ...

    def __truediv__(self, other: object, /) -> SympyExpression: ...

    def __pow__(
        self,
        other: object,
        modulo: object | None = None,
        /,
    ) -> SympyExpression: ...


class SympyIndexedBase(Protocol):
    def __getitem__(self, key: object, /) -> SympyExpression: ...


class NormalizationError(RuntimeError):
    pass


@dataclass(frozen=True, slots=True)
class NormalizedRendering:
    sympy: str
    latex: str


@dataclass(frozen=True, slots=True)
class BoundedRationalDifference:
    left: Any
    right: Any
    numerator: Any
    denominator: Any
    symbols: tuple[Any, ...]


def rational_ir_measure(
    expression: Expression,
    *,
    max_nodes: int = 512,
    max_degree: int = 8,
    max_exponent: int = 32,
    max_coefficient_bits: int = 1024,
    max_terms: int = 4096,
) -> tuple[int, int, int, int, int, int] | None:
    """Bound rational polynomial degrees, coefficient bits, and expanded terms."""
    if expression_node_count(expression) > max_nodes:
        return None

    def measure(value: Expression) -> tuple[int, int, int, int, int, int] | None:
        if isinstance(value, IntegerLiteral):
            return 0, 0, max(1, abs(value.value).bit_length()), 1, 1, 1
        if isinstance(value, RationalLiteral):
            return (
                0,
                0,
                max(1, abs(value.numerator).bit_length()),
                value.positive_denominator.bit_length(),
                1,
                1,
            )
        if isinstance(value, Symbol):
            return 1, 0, 1, 1, 1, 1
        if not isinstance(value, BinaryExpression):
            return None
        left_measure = measure(value.left)
        right_measure = measure(value.right)
        if left_measure is None or right_measure is None:
            return None
        (
            left_num,
            left_den,
            left_num_bits,
            left_den_bits,
            left_num_terms,
            left_den_terms,
        ) = left_measure
        (
            right_num,
            right_den,
            right_num_bits,
            right_den_bits,
            right_num_terms,
            right_den_terms,
        ) = right_measure
        if value.operator in {BinaryOperator.ADD, BinaryOperator.SUBTRACT}:
            result = (
                max(left_num + right_den, right_num + left_den),
                left_den + right_den,
                max(
                    left_num_bits + right_den_bits,
                    right_num_bits + left_den_bits,
                )
                + 1,
                left_den_bits + right_den_bits,
                left_num_terms * right_den_terms + right_num_terms * left_den_terms,
                left_den_terms * right_den_terms,
            )
        elif value.operator is BinaryOperator.MULTIPLY:
            result = (
                left_num + right_num,
                left_den + right_den,
                left_num_bits + right_num_bits,
                left_den_bits + right_den_bits,
                left_num_terms * right_num_terms,
                left_den_terms * right_den_terms,
            )
        elif value.operator is BinaryOperator.DIVIDE:
            result = (
                left_num + right_den,
                left_den + right_num,
                left_num_bits + right_den_bits,
                left_den_bits + right_num_bits,
                left_num_terms * right_den_terms,
                left_den_terms * right_num_terms,
            )
        else:
            exponent = (
                value.right.value
                if isinstance(value.right, IntegerLiteral)
                else value.right.numerator
                if isinstance(value.right, RationalLiteral)
                and value.right.positive_denominator == 1
                else None
            )
            if exponent is None or abs(exponent) > max_exponent:
                return None
            if exponent >= 0:
                result = (
                    left_num * exponent,
                    left_den * exponent,
                    left_num_bits * exponent,
                    left_den_bits * exponent,
                    left_num_terms**exponent,
                    left_den_terms**exponent,
                )
            else:
                result = (
                    left_den * -exponent,
                    left_num * -exponent,
                    left_den_bits * -exponent,
                    left_num_bits * -exponent,
                    left_den_terms**-exponent,
                    left_num_terms**-exponent,
                )
        if (
            max(result[:2]) > max_degree
            or max(result[2:4]) > max_coefficient_bits
            or max(result[4:]) > max_terms
        ):
            return None
        return result

    return measure(expression)


def rational_ir_preflight(
    expression: Expression,
    *,
    max_nodes: int = 512,
    max_degree: int = 8,
    max_exponent: int = 32,
    max_coefficient_bits: int = 1024,
) -> bool:
    return (
        rational_ir_measure(
            expression,
            max_nodes=max_nodes,
            max_degree=max_degree,
            max_exponent=max_exponent,
            max_coefficient_bits=max_coefficient_bits,
        )
        is not None
    )


def bounded_rational_difference(
    left: Expression,
    right: Expression,
    *,
    max_intermediate_nodes: int = 4096,
    max_degree: int = 8,
    max_exponent: int = 32,
    max_coefficient_bits: int = 1024,
) -> BoundedRationalDifference | None:
    """Normalize one pre-allowlisted rational pair under explicit resource caps."""
    left_measure = rational_ir_measure(
        left,
        max_degree=max_degree,
        max_exponent=max_exponent,
        max_coefficient_bits=max_coefficient_bits,
    )
    right_measure = rational_ir_measure(
        right,
        max_degree=max_degree,
        max_exponent=max_exponent,
        max_coefficient_bits=max_coefficient_bits,
    )
    if left_measure is None or right_measure is None:
        return None
    (
        left_num,
        left_den,
        left_num_bits,
        left_den_bits,
        left_num_terms,
        left_den_terms,
    ) = left_measure
    (
        right_num,
        right_den,
        right_num_bits,
        right_den_bits,
        right_num_terms,
        right_den_terms,
    ) = right_measure
    cross_num_bits = (
        max(
            left_num_bits + right_den_bits,
            right_num_bits + left_den_bits,
        )
        + 1
    )
    cross_den_bits = left_den_bits + right_den_bits
    cross_num_terms = left_num_terms * right_den_terms + right_num_terms * left_den_terms
    cross_den_terms = left_den_terms * right_den_terms
    if (
        max(
            left_num + right_den,
            right_num + left_den,
            left_den + right_den,
        )
        > max_degree
        or max(cross_num_bits, cross_den_bits) > max_coefficient_bits
        or max(cross_num_terms, cross_den_terms) > max_intermediate_nodes
    ):
        return None
    try:
        lhs: Any = _to_query_sympy(left)
        rhs: Any = _to_query_sympy(right)
        if sum(1 for _ in sympy.preorder_traversal(lhs)) > max_intermediate_nodes:
            return None
        if sum(1 for _ in sympy.preorder_traversal(rhs)) > max_intermediate_nodes:
            return None
        difference = sympy.cancel(lhs - rhs)
        if sum(1 for _ in sympy.preorder_traversal(difference)) > max_intermediate_nodes:
            return None
        numerator, denominator = sympy.fraction(difference)
        symbols = tuple(
            sorted(
                lhs.free_symbols
                | rhs.free_symbols
                | numerator.free_symbols
                | denominator.free_symbols,
                key=str,
            )
        )
        for value in (numerator, denominator):
            polynomial = sympy.Poly(value, *symbols) if symbols else None
            if polynomial is not None:
                if polynomial.total_degree() > max_degree:
                    return None
                if any(
                    abs(int(exponent)) > max_exponent
                    for monomial in polynomial.monoms()
                    for exponent in monomial
                ):
                    return None
                for coefficient in polynomial.coeffs():
                    numerator_part, denominator_part = sympy.fraction(coefficient)
                    if not numerator_part.is_Integer or not denominator_part.is_Integer:
                        return None
                    coefficient_bits = max(
                        abs(int(numerator_part)).bit_length(),
                        abs(int(denominator_part)).bit_length(),
                    )
                    if coefficient_bits > max_coefficient_bits:
                        return None
        return BoundedRationalDifference(lhs, rhs, numerator, denominator, symbols)
    except Exception:
        return None


def _series_value_is_bounded(value: Any, *, max_nodes: int = 4096) -> bool:
    """Check every family-specific series intermediate before it is reused."""
    try:
        if sum(1 for _ in sympy.preorder_traversal(value)) > max_nodes:
            return False
        symbols = tuple(sorted(value.free_symbols, key=str))
        numerator, denominator = sympy.fraction(value)
        for part in (numerator, denominator):
            try:
                poly = sympy.Poly(part, *symbols) if symbols else None
            except Exception:
                # Bound exponents (for example q**p) are already checked IR atoms,
                # not polynomial variables to expand through.
                continue
            if poly is not None:
                if poly.total_degree() > 8:
                    return False
                for coefficient in poly.coeffs():
                    top, bottom = sympy.fraction(coefficient)
                    if (
                        not top.is_Integer
                        or not bottom.is_Integer
                        or max(abs(int(top)).bit_length(), abs(int(bottom)).bit_length()) > 1024
                    ):
                        return False
        return True
    except Exception:
        return False


def bounded_linear_coefficients(expression: Expression, index: str) -> tuple[str, str] | None:
    """Collect the already extracted degree-one index polynomial under the seam."""
    if not rational_ir_preflight(expression, max_degree=1):
        return None
    try:
        value = _to_query_sympy(expression)
        if not _series_value_is_bounded(value):
            return None
        index_symbol = sympy.Symbol(index)
        polynomial = sympy.Poly(value, index_symbol)
        if polynomial.degree() > 1 or any(
            index_symbol in coefficient.free_symbols for coefficient in polynomial.all_coeffs()
        ):
            return None
        coefficients = (
            str(polynomial.coeff_monomial(index_symbol)),
            str(polynomial.coeff_monomial(1)),
        )
        return coefficients if all(len(item) <= 4096 for item in coefficients) else None
    except Exception:
        return None


def bounded_series_candidate(
    a: Expression,
    b: Expression,
    r: Expression,
    lower: Expression,
    upper: Expression | None,
    *,
    ratio_is_one: bool = False,
) -> Any | None:
    """Construct one preflighted geometric-linear candidate behind the backend seam."""
    inputs = (a, b, r, lower) if upper is None else (a, b, r, lower, upper)
    if not all(rational_ir_preflight(item, max_degree=8) for item in inputs):
        return None
    try:
        av, bv, rv, mv = (_to_query_sympy(item) for item in (a, b, r, lower))
        if ratio_is_one:
            if upper is None:
                return None
            nv = _to_query_sympy(upper)
            candidate = av * (nv * (nv + 1) - (mv - 1) * mv) / 2 + bv * (nv - mv + 1)
        else:
            rho = sympy.Symbol("_series_ratio")
            if upper is None:
                g = rho**mv / (1 - rho)
            else:
                nv = _to_query_sympy(upper)
                g = (rho**mv - rho ** (nv + 1)) / (1 - rho)
            if not _series_value_is_bounded(g):
                return None
            # This differentiation and cancellation are restricted to the constructed G identity.
            derivative = sympy.diff(g, rho)
            if not _series_value_is_bounded(derivative):
                return None
            unsubstituted: Any = av * rho * derivative + bv * g
            candidate = sympy.cancel(unsubstituted.subs(rho, rv))
        return candidate if _series_value_is_bounded(candidate) else None
    except Exception:
        return None


def bounded_series_verify(
    a: Expression,
    b: Expression,
    r: Expression,
    lower: Expression,
    upper: Expression | None,
    candidate: Any,
    *,
    ratio_is_one: bool = False,
) -> bool:
    """Independently check the finite boundary or convergent partial-sum identity."""
    if not _series_value_is_bounded(candidate):
        return False
    inputs = (a, b, r, lower) if upper is None else (a, b, r, lower, upper)
    if not all(rational_ir_preflight(item, max_degree=8) for item in inputs):
        return False
    try:
        av, bv, rv, mv = (_to_query_sympy(item) for item in (a, b, r, lower))
        rho = sympy.Symbol("_series_ratio")
        if ratio_is_one:
            if upper is None:
                return False
            nv = _to_query_sympy(upper)
            boundary = av * (nv * (nv + 1) - (mv - 1) * mv) / 2 + bv * (nv - mv + 1)
            return (
                _series_value_is_bounded(boundary)
                and _series_value_is_bounded(sympy.cancel(candidate - boundary))
                and sympy.cancel(candidate - boundary) == 0
            )
        if upper is not None:
            nv = _to_query_sympy(upper)

            # H(t) is the independently constructed prefix antidifference at t.
            def prefix_antidifference(endpoint: Any) -> Any:
                return av * rho * sympy.diff((1 - rho**endpoint) / (1 - rho), rho) + bv * (
                    1 - rho**endpoint
                ) / (1 - rho)

            boundary = sympy.cancel(
                (prefix_antidifference(nv + 1) - prefix_antidifference(mv)).subs(rho, rv)
            )
            difference = sympy.cancel(candidate - boundary)
            return (
                _series_value_is_bounded(boundary)
                and _series_value_is_bounded(difference)
                and difference == 0
            )
        # Compare the candidate with every symbolic finite partial sum; the remaining
        # r**(N+1) tail is then discharged only by the caller's proved Abs(r) < 1.
        n = sympy.Symbol("_series_partial_upper")
        finite = bounded_series_candidate(a, b, r, lower, _from_sympy_integer_symbol(n))
        if finite is None:
            return False
        tail = sympy.cancel(finite - candidate)
        return _series_value_is_bounded(tail) and n in tail.free_symbols
    except Exception:
        return False


def _from_sympy_integer_symbol(value: Any) -> Expression:
    # Internal-only bridge used for the independently checked partial-sum endpoint.
    return Symbol(str(value))


def render(formula: Expression | Equation) -> NormalizedRendering:
    try:
        return _render_value(_to_sympy(formula))
    except Exception as error:
        raise NormalizationError("SymPy normalization failed") from error


def polynomial_degree(expression: Expression, variable: str) -> int | None:
    """Return a safe univariate polynomial degree without parsing submitted text."""
    try:
        symbol = cast(Callable[[str], SympyExpression], sympy.Symbol)(variable)
        value: Any = _to_sympy(expression)
        free_symbols = {str(item) for item in value.free_symbols}
        if free_symbols - {variable}:
            return None
        polynomial = value.as_poly(symbol)
        if polynomial is None:
            return None
        return int(polynomial.degree())
    except Exception:
        return None


def is_nondecreasing_polynomial(expression: Expression, variable: str) -> bool:
    """Prove endpoint ordering for polynomials with nonnegative derivative coefficients."""
    try:
        symbol: Any = cast(Callable[[str], SympyExpression], sympy.Symbol)(variable)
        value: Any = _to_sympy(expression)
        free_symbols = {str(item) for item in value.free_symbols}
        if free_symbols - {variable}:
            return False
        polynomial: Any = value.as_poly(symbol)
        if polynomial is None:
            return False
        derivative: Any = polynomial.diff()
        return all(bool(coefficient >= 0) for coefficient in derivative.all_coeffs())
    except Exception:
        return False


def render_system(equations: tuple[Equation, ...]) -> NormalizedRendering:
    try:
        constructor = cast(Callable[..., SympyExpression], sympy.Tuple)
        return _render_value(constructor(*(_to_sympy(equation) for equation in equations)))
    except Exception as error:
        raise NormalizationError("SymPy normalization failed") from error


def _render_value(value: SympyExpression) -> NormalizedRendering:
    return NormalizedRendering(
        sympy=str(value),
        latex=cast(str, sympy.latex(value)),
    )


def _to_query_sympy(expression: Expression) -> SympyExpression:
    """Convert a preflighted rational query family with evaluable integer powers."""
    if isinstance(expression, IntegerLiteral):
        constructor = cast(Callable[[int], SympyExpression], sympy.Integer)
        return constructor(expression.value)
    if isinstance(expression, RationalLiteral):
        constructor = cast(Callable[[int, int], SympyExpression], sympy.Rational)
        return constructor(expression.numerator, expression.positive_denominator)
    if isinstance(expression, Symbol):
        constructor = cast(Callable[[str], SympyExpression], sympy.Symbol)
        return constructor(expression.name)
    if not isinstance(expression, BinaryExpression):
        raise NormalizationError("query expression is outside the rational family")
    left = _to_query_sympy(expression.left)
    right = _to_query_sympy(expression.right)
    if expression.operator is BinaryOperator.ADD:
        return left + right
    if expression.operator is BinaryOperator.SUBTRACT:
        return left - right
    if expression.operator is BinaryOperator.MULTIPLY:
        return left * right
    if expression.operator is BinaryOperator.DIVIDE:
        return left / right
    power = cast(Callable[..., SympyExpression], sympy.Pow)
    return power(left, right)


def _to_sympy(formula: Expression | Equation) -> SympyExpression:
    if isinstance(formula, IntegerLiteral):
        constructor = cast(Callable[[int], SympyExpression], sympy.Integer)
        return constructor(formula.value)
    if isinstance(formula, RationalLiteral):
        constructor = cast(Callable[[int, int], SympyExpression], sympy.Rational)
        return constructor(formula.numerator, formula.positive_denominator)
    if isinstance(formula, InfinityLiteral):
        return cast(SympyExpression, sympy.oo if formula.sign > 0 else -sympy.oo)
    if isinstance(formula, Symbol):
        constructor = cast(Callable[[str], SympyExpression], sympy.Symbol)
        return constructor(formula.name)
    if isinstance(formula, IndexedValue):
        constructor = cast(Callable[[str], SympyIndexedBase], sympy.IndexedBase)
        base = constructor(formula.name)
        indices = tuple(_to_sympy(index) for index in formula.indices)
        return base[indices[0] if len(indices) == 1 else indices]
    if isinstance(formula, Call):
        arguments = tuple(_to_sympy(argument) for argument in formula.arguments)
        if formula.name == "Max":
            constructor = cast(Callable[..., SympyExpression], sympy.Max)
        else:
            function_factory = cast(Callable[[str], Callable[..., SympyExpression]], sympy.Function)
            constructor = function_factory(formula.name)
        return constructor(*arguments)
    if isinstance(formula, Sum):
        constructor = cast(Callable[..., SympyExpression], sympy.Sum)
        symbol_constructor = cast(Callable[[str], SympyExpression], sympy.Symbol)
        return constructor(
            _to_sympy(formula.body),
            (
                symbol_constructor(formula.index),
                _to_sympy(formula.lower),
                _to_sympy(formula.upper),
            ),
        )
    if isinstance(formula, Equation):
        constructor = cast(Callable[..., SympyExpression], sympy.Eq)
        return constructor(
            _to_sympy(formula.left),
            _to_sympy(formula.right),
            evaluate=False,
        )
    return _binary_to_sympy(formula)


def _binary_to_sympy(expression: BinaryExpression) -> SympyExpression:
    left = _to_sympy(expression.left)
    right = _to_sympy(expression.right)
    if expression.operator is BinaryOperator.ADD:
        return left + right
    if expression.operator is BinaryOperator.SUBTRACT:
        return left - right
    if expression.operator is BinaryOperator.MULTIPLY:
        return left * right
    if expression.operator is BinaryOperator.DIVIDE:
        return left / right
    power = cast(Callable[..., SympyExpression], sympy.Pow)
    unevaluated = cast(Callable[[object], SympyExpression], sympy.UnevaluatedExpr)
    return unevaluated(power(left, right, evaluate=False))
