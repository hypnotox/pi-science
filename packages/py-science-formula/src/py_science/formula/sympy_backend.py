# ruff: noqa: E501
# pyright: reportUnknownMemberType=false, reportUnknownVariableType=false, reportUnknownArgumentType=false, reportArgumentType=false, reportAssignmentType=false, reportAttributeAccessIssue=false, reportReturnType=false
from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from fractions import Fraction
from math import comb
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
    expression_children,
    expression_node_count,
)
from py_science.formula.query_diagnostics import AsymptoticFailureKind, RationalFailureKind


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


@dataclass(frozen=True, slots=True)
class RationalMeasureFailure:
    """A safe first failure from bounded rational IR inspection."""

    kind: RationalFailureKind
    observed: int | None = None
    configured: int | None = None


RationalMeasure = tuple[int, int, int, int, int, int]


@dataclass(frozen=True, slots=True)
class _RationalMeasure:
    numerator_degree: int
    denominator_degree: int
    numerator_bits: int
    denominator_bits: int
    numerator_terms: int
    denominator_terms: int
    degree_is_observed: bool
    coefficient_bits_are_observed: bool
    terms_are_observed: bool
    known_nonzero: bool

    def values(self) -> RationalMeasure:
        return (
            self.numerator_degree,
            self.denominator_degree,
            self.numerator_bits,
            self.denominator_bits,
            self.numerator_terms,
            self.denominator_terms,
        )


@dataclass(frozen=True, slots=True)
class BoundedAsymptoticRational:
    statement: str
    local_parameter: str
    conditions: tuple[str, ...]
    symbols: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class BoundedFamilyNoMatch:
    """The expression does not use a recognized family grammar."""


@dataclass(frozen=True, slots=True)
class BoundedFamilyFailure:
    """A recognized family refused for one bounded, safe reason."""

    kind: AsymptoticFailureKind
    observed: int | None = None
    configured: int | None = None
    message: str | None = None
    rational_failure: RationalMeasureFailure | None = None


@dataclass(frozen=True, slots=True)
class BoundedExponentialDecomposition:
    source: str
    rendered: str
    bases: tuple[Expression, ...]
    coefficient_symbols: tuple[str, ...]
    conditions: tuple[str, ...]
    symbols: tuple[str, ...]


# Property operations are deliberately centralized here.  The policy layer only
# receives bounded data from these seams; each transformation validates its input
# and result (4096 nodes, degree 8, exponent 32, and 1024-bit coefficients).
def property_value(expression: Expression) -> Any | None:
    if not rational_ir_preflight(expression):
        return None
    try:
        value: Any = _to_query_sympy(expression)
        return value if _property_value_is_bounded(value) else None
    except Exception:
        return None


def property_cancel(value: Any) -> Any | None:
    return _property_transform(value, sympy.cancel)


def property_substitute(value: Any, variable: Any, point: Any) -> Any | None:
    return _property_transform(value, lambda item: item.subs(variable, point))


def property_fraction(value: Any) -> tuple[Any, Any] | None:
    if not _property_value_is_bounded(value):
        return None
    try:
        numerator, denominator = sympy.fraction(value)
        if not (_property_value_is_bounded(numerator) and _property_value_is_bounded(denominator)):
            return None
        return numerator, denominator
    except Exception:
        return None


def property_factor_roots(value: Any, variable: Any) -> tuple[tuple[Any, int], ...] | None:
    """Extract bounded linear-factor roots without exposing Poly/factor to policy."""
    if not _property_value_is_bounded(value):
        return None
    try:
        result: Any = sympy.factor_list(value, variable)
        _, factors = result
        roots: list[tuple[Any, int]] = []
        for factor, multiplicity in factors:
            if not _property_value_is_bounded(factor) or variable not in factor.free_symbols:
                continue
            poly = sympy.Poly(factor, variable)
            coefficients = poly.all_coeffs()
            if poly.degree() != 1 or len(coefficients) != 2:
                return None
            root = -coefficients[1] / coefficients[0]
            if not _property_value_is_bounded(root):
                return None
            roots.append((root, int(multiplicity)))
        return tuple(roots)
    except Exception:
        return None


def property_factor_components(value: Any) -> tuple[tuple[Any, int], ...] | None:
    """Return bounded irreducible multiplicative factors for exact sign policy."""
    if not _property_value_is_bounded(value):
        return None
    try:
        result: Any = sympy.factor_list(value)
        coefficient, factors = result
        components: list[tuple[Any, int]] = []
        if not _property_value_is_bounded(coefficient):
            return None
        if coefficient != 1:
            components.append((coefficient, 1))
        for factor, multiplicity in factors:
            if not _property_value_is_bounded(factor) or multiplicity < 1:
                return None
            components.append((factor, int(multiplicity)))
        return tuple(components)
    except Exception:
        return None


def property_affine_coefficients(value: Any) -> tuple[str, Fraction, Fraction] | None:
    """Expose one bounded rational affine factor without policy-side SymPy algebra."""
    if not _property_value_is_bounded(value):
        return None
    try:
        symbols = tuple(value.free_symbols)
        if len(symbols) != 1:
            return None
        symbol = symbols[0]
        poly = sympy.Poly(value, symbol)
        if poly.degree() > 1 or any(not item.is_Rational for item in poly.all_coeffs()):
            return None
        coefficient, constant = poly.coeff_monomial(symbol), poly.coeff_monomial(1)
        if not (_property_value_is_bounded(coefficient) and _property_value_is_bounded(constant)):
            return None
        return (
            str(symbol),
            Fraction(int(coefficient.p), int(coefficient.q)),
            Fraction(int(constant.p), int(constant.q)),
        )
    except Exception:
        return None


def property_derivative(value: Any, variable: Any) -> Any | None:
    return _property_transform(value, lambda item: sympy.diff(item, variable))  # pyright: ignore[reportUnknownLambdaType]


def property_difference(value: Any, variable: Any) -> Any | None:
    return _property_transform(
        value,
        lambda item: sympy.cancel(item.subs(variable, variable + 1) - item),  # pyright: ignore[reportUnknownLambdaType]
    )


def property_local_pole_coefficient(
    numerator: Any, denominator: Any, variable: Any, point: Any, order: int
) -> Any | None:
    if not (_property_value_is_bounded(numerator) and _property_value_is_bounded(denominator)):
        return None
    try:
        cofactor = sympy.cancel(denominator / (variable - point) ** order)
        coefficient = numerator.subs(variable, point) / cofactor.subs(variable, point)
        return coefficient if _property_value_is_bounded(coefficient) else None
    except Exception:
        return None


def property_polynomial_info(
    numerator: Any, denominator: Any, variable: Any
) -> tuple[int, int, Any] | None:
    if not (_property_value_is_bounded(numerator) and _property_value_is_bounded(denominator)):
        return None
    try:
        top, bottom = sympy.Poly(numerator, variable), sympy.Poly(denominator, variable)
        leading = top.LC() / bottom.LC()
        if not _property_value_is_bounded(leading):
            return None
        return int(top.degree()), int(bottom.degree()), leading
    except Exception:
        return None


def property_render(value: Any) -> str | None:
    if not _property_value_is_bounded(value):
        return None
    try:
        rendered = str(value)
        return rendered if len(rendered) <= 4096 else None
    except Exception:
        return None


def _property_transform(value: Any, operation: Callable[[Any], Any]) -> Any | None:
    if not _property_value_is_bounded(value):
        return None
    try:
        result = operation(value)
        return result if _property_value_is_bounded(result) else None
    except Exception:
        return None


def _property_value_is_bounded(value: Any) -> bool:
    try:
        if sum(1 for _ in sympy.preorder_traversal(value)) > 4096:
            return False
        symbols = tuple(sorted(value.free_symbols, key=str))
        for part in sympy.fraction(value):
            polynomial = sympy.Poly(part, *symbols) if symbols else None
            if polynomial is None:
                if not part.is_Rational:
                    return False
                if max(abs(int(part.p)).bit_length(), abs(int(part.q)).bit_length()) > 1024:  # pyright: ignore[reportAttributeAccessIssue]
                    return False
                continue
            if polynomial.total_degree() > 8 or any(
                abs(exponent) > 32 for monomial in polynomial.monoms() for exponent in monomial
            ):
                return False
            for coefficient in polynomial.coeffs():
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


def rational_ir_measure(
    expression: Expression,
    *,
    max_nodes: int = 512,
    max_degree: int = 8,
    max_exponent: int = 32,
    max_coefficient_bits: int = 1024,
    max_terms: int = 4096,
) -> RationalMeasure | RationalMeasureFailure:
    """Bound rational IR and return its stable first refusal when it does not fit."""
    nodes = expression_node_count(expression)
    if nodes > max_nodes:
        return RationalMeasureFailure("nodes", nodes, max_nodes)

    def measure(value: Expression) -> _RationalMeasure | RationalMeasureFailure:
        if isinstance(value, IntegerLiteral):
            bits = max(1, abs(value.value).bit_length())
            if bits > max_coefficient_bits:
                return RationalMeasureFailure(
                    "coefficient_bits", bits, max_coefficient_bits
                )
            return _RationalMeasure(0, 0, bits, 1, 1, 1, True, True, True, value.value != 0)
        if isinstance(value, RationalLiteral):
            numerator_bits = max(1, abs(value.numerator).bit_length())
            denominator_bits = value.positive_denominator.bit_length()
            bits = max(numerator_bits, denominator_bits)
            if bits > max_coefficient_bits:
                return RationalMeasureFailure(
                    "coefficient_bits", bits, max_coefficient_bits
                )
            return _RationalMeasure(
                0,
                0,
                numerator_bits,
                denominator_bits,
                1,
                1,
                True,
                True,
                True,
                value.numerator != 0,
            )
        if isinstance(value, Symbol):
            return _RationalMeasure(1, 0, 1, 1, 1, 1, True, True, True, True)
        if not isinstance(value, BinaryExpression):
            return RationalMeasureFailure("unsupported_form")
        left_measure = measure(value.left)
        if isinstance(left_measure, RationalMeasureFailure):
            return left_measure
        right_measure = measure(value.right)
        if isinstance(right_measure, RationalMeasureFailure):
            return right_measure
        (
            left_num,
            left_den,
            left_num_bits,
            left_den_bits,
            left_num_terms,
            left_den_terms,
        ) = left_measure.values()
        (
            right_num,
            right_den,
            right_num_bits,
            right_den_bits,
            right_num_terms,
            right_den_terms,
        ) = right_measure.values()
        if value.operator in {BinaryOperator.ADD, BinaryOperator.SUBTRACT}:
            result = _RationalMeasure(
                max(left_num + right_den, right_num + left_den),
                left_den + right_den,
                max(left_num_bits + right_den_bits, right_num_bits + left_den_bits) + 1,
                left_den_bits + right_den_bits,
                left_num_terms * right_den_terms + right_num_terms * left_den_terms,
                left_den_terms * right_den_terms,
                False,
                False,
                False,
                False,
            )
        elif value.operator is BinaryOperator.MULTIPLY:
            known_nonzero = left_measure.known_nonzero and right_measure.known_nonzero
            result = _RationalMeasure(
                left_num + right_num,
                left_den + right_den,
                left_num_bits + right_num_bits,
                left_den_bits + right_den_bits,
                left_num_terms * right_num_terms,
                left_den_terms * right_den_terms,
                left_measure.degree_is_observed
                and right_measure.degree_is_observed
                and left_den == 0
                and right_den == 0
                and known_nonzero,
                False,
                False,
                known_nonzero,
            )
        elif value.operator is BinaryOperator.DIVIDE:
            known_nonzero = left_measure.known_nonzero and right_measure.known_nonzero
            result = _RationalMeasure(
                left_num + right_den,
                left_den + right_num,
                left_num_bits + right_den_bits,
                left_den_bits + right_num_bits,
                left_num_terms * right_den_terms,
                left_den_terms * right_num_terms,
                False,
                False,
                False,
                known_nonzero,
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
            if exponent is None:
                return RationalMeasureFailure("unsupported_form")
            if abs(exponent) > max_exponent:
                return RationalMeasureFailure("exponent", abs(exponent), max_exponent)
            known_nonzero = exponent == 0 or left_measure.known_nonzero
            if exponent >= 0:
                result = _RationalMeasure(
                    left_num * exponent,
                    left_den * exponent,
                    left_num_bits * exponent,
                    left_den_bits * exponent,
                    left_num_terms**exponent,
                    left_den_terms**exponent,
                    left_measure.degree_is_observed and known_nonzero,
                    exponent == 1 and left_measure.coefficient_bits_are_observed,
                    exponent in {0, 1} and left_measure.terms_are_observed,
                    known_nonzero,
                )
            else:
                result = _RationalMeasure(
                    left_den * -exponent,
                    left_num * -exponent,
                    left_den_bits * -exponent,
                    left_num_bits * -exponent,
                    left_den_terms**-exponent,
                    left_num_terms**-exponent,
                    left_measure.degree_is_observed and known_nonzero,
                    exponent == -1 and left_measure.coefficient_bits_are_observed,
                    exponent == -1 and left_measure.terms_are_observed,
                    known_nonzero,
                )
        values = result.values()
        degree = max(values[:2])
        if degree > max_degree:
            return RationalMeasureFailure(
                "degree", degree if result.degree_is_observed else None, max_degree
            )
        coefficient_bits = max(values[2:4])
        if coefficient_bits > max_coefficient_bits:
            return RationalMeasureFailure(
                "coefficient_bits",
                coefficient_bits if result.coefficient_bits_are_observed else None,
                max_coefficient_bits,
            )
        terms = max(values[4:])
        if terms > max_terms:
            return RationalMeasureFailure(
                "expanded_terms", terms if result.terms_are_observed else None, max_terms
            )
        return result

    measured = measure(expression)
    return measured if isinstance(measured, RationalMeasureFailure) else measured.values()


def rational_ir_preflight(
    expression: Expression,
    *,
    max_nodes: int = 512,
    max_degree: int = 8,
    max_exponent: int = 32,
    max_coefficient_bits: int = 1024,
) -> bool:
    return not isinstance(
        rational_ir_measure(
            expression,
            max_nodes=max_nodes,
            max_degree=max_degree,
            max_exponent=max_exponent,
            max_coefficient_bits=max_coefficient_bits,
        ),
        RationalMeasureFailure,
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
    if isinstance(left_measure, RationalMeasureFailure) or isinstance(
        right_measure, RationalMeasureFailure
    ):
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

        # H(t) is independently constructed as a prefix antidifference.  Verify its
        # one-step identity before using its requested boundary difference.
        def prefix_antidifference(endpoint: Any) -> Any:
            return av * rho * sympy.diff((1 - rho**endpoint) / (1 - rho), rho) + bv * (
                1 - rho**endpoint
            ) / (1 - rho)

        t = sympy.Symbol("_series_antidifference_index", integer=True)
        raw_step = prefix_antidifference(t + 1) - prefix_antidifference(t) - (av * t + bv) * rho**t
        # This is the exact integer-index rewrite r**(t+1) = r*r**t,
        # not a generic simplification pass.
        step = sympy.cancel(raw_step.xreplace({rho ** (t + 1): rho * rho**t}))
        if not _series_value_is_bounded(step) or step != 0:
            return False
        if upper is not None:
            nv = _to_query_sympy(upper)
            boundary = sympy.cancel(
                (prefix_antidifference(nv + 1) - prefix_antidifference(mv)).subs(rho, rv)
            )
            difference = sympy.cancel(candidate - boundary)
            return (
                _series_value_is_bounded(boundary)
                and _series_value_is_bounded(difference)
                and difference == 0
            )
        # Derive the exact finite partial sum independently.  Its difference from
        # the candidate must be a family-shaped endpoint tail: every additive term
        # containing the endpoint contains rho**(N+c), and no endpoint-free term is
        # permitted.  Under the caller-proved Abs(r)<1 these polynomial-times-power
        # factors tend to zero; no generic limit/summation/simplify/series is used.
        n = sympy.Symbol("_series_partial_upper", integer=True)
        finite = sympy.cancel(
            (prefix_antidifference(n + 1) - prefix_antidifference(mv)).subs(rho, rv)
        )
        if not _series_value_is_bounded(finite):
            return False
        tail = sympy.cancel(finite - candidate)
        return _series_value_is_bounded(tail) and _endpoint_tail_tends_to_zero(tail, n, rv)
    except Exception:
        return False


def _endpoint_tail_tends_to_zero(tail: Any, endpoint: Any, ratio: Any) -> bool:
    """Recognize only polynomial-times-r**(N+c) endpoint tails from this family."""
    if endpoint not in tail.free_symbols:
        return False
    try:
        numerator, denominator = sympy.fraction(tail)
        if endpoint in denominator.free_symbols:
            return False
        terms = sympy.Add.make_args(numerator)
        for term in terms:
            powers: list[Any] = []
            for factor in sympy.Mul.make_args(term):
                power: Any = factor
                if power.is_Pow and power.base == ratio and endpoint in power.exp.free_symbols:
                    powers.append(power)
            if len(powers) != 1:
                return False
            exponent = powers[0].exp
            # The exponent is exactly N plus an endpoint-independent integer offset.
            if sympy.cancel(exponent - endpoint).free_symbols & {endpoint}:
                return False
            remainder = sympy.cancel(term / powers[0])
            # The remainder may be a bounded polynomial in N and a denominator that
            # does not depend on N, but cannot hide another endpoint-dependent factor.
            remainder_numerator, remainder_denominator = sympy.fraction(remainder)
            if endpoint in remainder_denominator.free_symbols:
                return False
            polynomial = sympy.Poly(remainder_numerator, endpoint)
            if polynomial.degree() > 1:
                return False
        return True
    except Exception:
        return False


def bounded_exponential_decomposition(
    expression: Expression, variable: str, point: str, order: int
) -> BoundedExponentialDecomposition | BoundedFamilyFailure | BoundedFamilyNoMatch:
    """Recognize and independently reconstruct finite linear-exponential terms."""
    if point not in {"oo", "-oo"}:
        return BoundedFamilyNoMatch()
    terms = _exp_add_terms(expression)
    decoded: list[tuple[Any, Any, Expression]] = []
    for term in terms:
        factors = _exp_multiply_factors(term)
        powers = [factor for factor in factors if _exp_power_base(factor, variable) is not None]
        if len(powers) != 1:
            return BoundedFamilyNoMatch()
        base = _exp_power_base(powers[0], variable)
        if base is None:
            return BoundedFamilyNoMatch()
        remaining = [factor for factor in factors if factor is not powers[0]]
        linear = _exp_linear_product(remaining, variable)
        if linear is None:
            return BoundedFamilyNoMatch()
        slope, intercept = linear
        decoded.append((slope, intercept, base))
    nodes = expression_node_count(expression)
    if nodes > 512:
        return BoundedFamilyFailure("nodes", nodes, 512)
    # Each submitted additive term must reconstruct exactly; do not merge bases.
    rendered_terms: list[tuple[int, str]] = []
    bases: list[Expression] = []
    coefficient_symbols: set[str] = set()
    reconstructed: Any = sympy.Integer(0)
    query_symbol = sympy.Symbol(variable)
    try:
        source: Any = _to_query_sympy(expression)
        if not _exponential_value_is_bounded(source, query_symbol):
            return BoundedFamilyFailure("resource")
        for slope, intercept, base in decoded:
            base_value = _to_query_sympy(base)
            if not _property_value_is_bounded(base_value):
                return BoundedFamilyFailure("resource")
            coefficient_symbols.update(
                str(item)
                for item in (slope.free_symbols | intercept.free_symbols)
                if str(item) != variable
            )
            polynomial = slope * query_symbol + intercept
            piece = polynomial * base_value ** query_symbol
            if not _exponential_value_is_bounded(piece, query_symbol):
                return BoundedFamilyFailure("reconstruction")
            reconstructed += piece
            if not _exponential_value_is_bounded(reconstructed, query_symbol):
                return BoundedFamilyFailure("reconstruction")
            degree = 1 if slope != 0 else 0
            rendered_terms.append(
                (degree, f"({sympy.sstr(polynomial)})*({sympy.sstr(base_value)})**{variable}")
            )
            bases.append(base)
        # Validate the source, every reconstruction intermediate, and the uncancelled
        # difference before independently cancelling the exact identity.
        difference = source - reconstructed
        if not _exponential_value_is_bounded(difference, query_symbol):
            return BoundedFamilyFailure("reconstruction")
        cancelled = sympy.cancel(difference)
        if not _exponential_value_is_bounded(cancelled, query_symbol) or cancelled != 0:
            return BoundedFamilyFailure("reconstruction")
        if len(decoded) > order:
            # Each accepted source addend is one polynomial-times-exponential term.
            return BoundedFamilyFailure("term_count", len(decoded), order)
        rendered = " + ".join(
            item[1] for item in sorted(rendered_terms, key=lambda item: item[0], reverse=True)
        )
        source_text = sympy.sstr(source)
        if max(len(source_text), len(rendered)) > 4096:
            return BoundedFamilyFailure("rendering")
        symbols = tuple(sorted(str(item) for item in source.free_symbols))
        return BoundedExponentialDecomposition(
            source_text,
            rendered,
            tuple(bases),
            tuple(sorted(coefficient_symbols)),
            (),
            symbols,
        )
    except Exception:
        return BoundedFamilyFailure("reconstruction")


def _exponential_value_is_bounded(value: Any, variable: Any) -> bool:
    """Bound the restricted symbolic-power grammar used by this decomposition."""
    try:
        if sum(1 for _ in sympy.preorder_traversal(value)) > 4096:
            return False
        if value.is_Atom:
            return bool(value.is_Number or value.is_Symbol)
        if value.is_Pow:
            return value.exp == variable and _property_value_is_bounded(value.base)
        if value.is_Add or value.is_Mul:
            return all(_exponential_value_is_bounded(item, variable) for item in value.args)
        return False
    except Exception:
        return False


def _exp_add_terms(value: Expression) -> list[Expression]:
    if isinstance(value, BinaryExpression) and value.operator is BinaryOperator.ADD:
        return [*_exp_add_terms(value.left), *_exp_add_terms(value.right)]
    if isinstance(value, BinaryExpression) and value.operator is BinaryOperator.SUBTRACT:
        return [*_exp_add_terms(value.left), BinaryExpression(BinaryOperator.MULTIPLY, IntegerLiteral(-1), value.right)]
    return [value]


def _exp_multiply_factors(value: Expression) -> list[Expression]:
    if isinstance(value, BinaryExpression) and value.operator is BinaryOperator.MULTIPLY:
        return [*_exp_multiply_factors(value.left), *_exp_multiply_factors(value.right)]
    return [value]


def _exp_power_base(value: Expression, variable: str) -> Expression | None:
    if isinstance(value, BinaryExpression) and value.operator is BinaryOperator.POWER and isinstance(value.right, Symbol) and value.right.name == variable:
        return value.left
    return None


def _exp_constant(value: Expression, variable: str) -> Any | None:
    # Coefficients may be parameters, but never contain the approach variable.
    try:
        if variable in {str(item) for item in _to_query_sympy(value).free_symbols}:
            return None
        if not rational_ir_preflight(value):
            return None
        result: Any = _to_query_sympy(value)
        return result if sum(1 for _ in sympy.preorder_traversal(result)) <= 4096 else None
    except Exception:
        return None


def _exp_linear(value: Expression, variable: str) -> tuple[Any, Any] | None:
    constant = _exp_constant(value, variable)
    if constant is not None:
        return sympy.Integer(0), constant
    if isinstance(value, Symbol) and value.name == variable:
        return sympy.Integer(1), sympy.Integer(0)
    if not isinstance(value, BinaryExpression):
        return None
    left, right = _exp_linear(value.left, variable), _exp_linear(value.right, variable)
    if left is None or right is None:
        return None
    if value.operator is BinaryOperator.ADD:
        return left[0] + right[0], left[1] + right[1]
    if value.operator is BinaryOperator.SUBTRACT:
        return left[0] - right[0], left[1] - right[1]
    if value.operator is BinaryOperator.MULTIPLY and not (left[0] and right[0]):
        return left[0] * right[1] + left[1] * right[0], left[1] * right[1]
    return None


def _exp_linear_product(factors: list[Expression], variable: str) -> tuple[Any, Any] | None:
    slope, intercept = sympy.Integer(0), sympy.Integer(1)
    for factor in factors:
        linear = _exp_linear(factor, variable)
        if linear is None or (slope and linear[0]):
            return None
        slope, intercept = slope * linear[1] + intercept * linear[0], intercept * linear[1]
    return slope, intercept


def bounded_asymptotic_rational(
    expression: Expression,
    original: Expression,
    variable_name: str,
    point: str,
    order: int,
    direction: object,
    real_parameters: frozenset[str],
) -> BoundedAsymptoticRational | BoundedFamilyFailure | BoundedFamilyNoMatch:
    """Translate, divide, verify, and render one guarded rational expansion.

    This is deliberately the sole asymptotic polynomial/SymPy seam.  It validates
    both the submitted and transformed values before and after each operation.
    """
    measurement = rational_ir_measure(expression)
    if isinstance(measurement, RationalMeasureFailure):
        if measurement.kind == "unsupported_form":
            return BoundedFamilyNoMatch()
        return BoundedFamilyFailure("rational_measure", rational_failure=measurement)
    normalized = bounded_rational_difference(expression, IntegerLiteral(0))
    if normalized is None:
        return BoundedFamilyFailure("rational_normalization")
    variable = sympy.Symbol(variable_name)
    parameter_symbols = {str(item) for item in normalized.symbols} - {variable_name}
    if not parameter_symbols <= real_parameters:
        return BoundedFamilyFailure("real_parameters")
    try:
        numerator = sympy.Poly(normalized.left.as_numer_denom()[0], variable)
        denominator = sympy.Poly(normalized.left.as_numer_denom()[1], variable)
        # Parameter-dependent denominator roots need path ordering that this
        # bounded recurrence intentionally does not model.
        if {str(item) for item in denominator.as_expr().free_symbols} - {variable_name}:
            return BoundedFamilyFailure("parameter_denominator")
        if denominator.is_zero:
            return BoundedFamilyFailure(
                "specific", message="query denominator is identically zero"
            )
        # SymPy gives the zero polynomial degree -oo; it is an exact expansion,
        # never an integer degree conversion.
        if numerator.is_zero:
            if point == "oo":
                local, approach = f"1/{variable_name}", f"{variable_name} -> oo"
            elif point == "-oo":
                local, approach = f"-1/{variable_name}", f"{variable_name} -> -oo"
            else:
                parsed = _parse_backend_scalar(point)
                if parsed is None:
                    return BoundedFamilyFailure(
                        "specific", message="asymptotic point is invalid"
                    )
                center = sympy.Rational(parsed.numerator, parsed.denominator)
                local = f"{variable_name} - {center}"
                approach = f"{variable_name} -> {center} ({direction})"
            conditions = _asymptotic_denominator_conditions(original)
            if conditions is None:
                return BoundedFamilyFailure(
                    "specific", message="original denominator exceeds its bound"
                )
            statement = f"0 = 0 + O(t**{order}) as {approach}, t = {local}"
            if len(statement) > 4096:
                return BoundedFamilyFailure(
                    "specific", message="query result rendering exceeds its bound"
                )
            return BoundedAsymptoticRational(statement, local, (approach, *conditions), ())
        degree = max(int(numerator.degree()), int(denominator.degree()))
        if degree > 8:
            return BoundedFamilyFailure(
                "rational_measure",
                rational_failure=RationalMeasureFailure("degree", degree, 8),
            )
        if point in {"oo", "-oo"}:
            sign = 1 if point == "oo" else -1
            local, approach = (
                (f"1/{variable_name}", f"{variable_name} -> oo")
                if sign > 0
                else (f"-1/{variable_name}", f"{variable_name} -> -oo")
            )
            top = _asymptotic_reversed(numerator, sign)
            bottom = _asymptotic_reversed(denominator, sign)
            shift = int(denominator.degree()) - int(numerator.degree())
        else:
            parsed = _parse_backend_scalar(point)
            if parsed is None:
                return BoundedFamilyFailure(
                    "specific", message="asymptotic point is invalid"
                )
            center = sympy.Rational(parsed.numerator, parsed.denominator)
            local = f"{variable_name} - {center}"
            approach = f"{variable_name} -> {center} ({direction})"
            top = _asymptotic_shifted(numerator, center)
            bottom = _asymptotic_shifted(denominator, center)
            top_order, bottom_order = _asymptotic_valuation(top), _asymptotic_valuation(bottom)
            if bottom_order is None:
                return BoundedFamilyFailure(
                    "specific", message="query denominator is identically zero"
                )
            shift = (top_order or 0) - bottom_order
            top, bottom = top[top_order or 0 :], bottom[bottom_order:]
        if not bottom or bottom[0] == 0:
            return BoundedFamilyFailure(
                "specific", message="asymptotic local denominator is unsupported"
            )
        count = order - shift
        coefficients = [] if count <= 0 else _asymptotic_divide(top, bottom, count)
        if coefficients is None:
            return BoundedFamilyFailure(
                "specific", message="asymptotic intermediate exceeds its bound"
            )
        if not _asymptotic_verify(top, bottom, coefficients):
            return BoundedFamilyFailure(
                "specific", message="asymptotic remainder verification failed"
            )
        terms = _asymptotic_render_terms(coefficients, shift)
        conditions = _asymptotic_denominator_conditions(original)
        if conditions is None:
            return BoundedFamilyFailure(
                "specific", message="original denominator exceeds its bound"
            )
        statement = (
            f"{sympy.sstr(normalized.left)} = {terms} + O(t**{order}) "
            f"as {approach}, t = {local}"
        )
        if len(statement) > 4096 or any(
            len(sympy.sstr(value)) > 4096 for value in coefficients
        ):
            return BoundedFamilyFailure(
                "specific", message="query result rendering exceeds its bound"
            )
        return BoundedAsymptoticRational(
            statement,
            local,
            (approach, *conditions),
            tuple(str(item) for item in normalized.symbols),
        )
    except Exception:
        return BoundedFamilyFailure(
            "specific", message="asymptotic intermediate exceeds its bound"
        )


def _parse_backend_scalar(value: str) -> Any:
    from py_science.formula.exact_values import parse_exact_scalar
    return parse_exact_scalar(value)


def _asymptotic_denominator_conditions(expression: Expression) -> tuple[str, ...] | None:
    found: list[Expression] = []
    def visit(value: Expression) -> None:
        if isinstance(value, BinaryExpression) and value.operator is BinaryOperator.DIVIDE:
            found.append(value.right)
        if isinstance(value, BinaryExpression) and value.operator is BinaryOperator.POWER and isinstance(value.right, IntegerLiteral) and value.right.value < 0:
            found.append(value.left)
        for child in expression_children(value):
            visit(child)
    visit(expression)
    result: list[str] = []
    for item in found:
        normalized = bounded_rational_difference(item, IntegerLiteral(0))
        if normalized is None:
            return None
        rendered = f"{sympy.sstr(normalized.left)} != 0"
        if len(rendered) > 4096:
            return None
        if rendered not in result:
            result.append(rendered)
    return tuple(result)


def _asymptotic_reversed(poly: Any, sign: int) -> list[Any]:
    degree = int(poly.degree())
    return [poly.nth(degree - index) * sign ** (degree - index) for index in range(degree + 1)]


def _asymptotic_shifted(poly: Any, center: Any) -> list[Any]:
    degree = int(poly.degree())
    result = [sympy.Rational(0) for _ in range(degree + 1)]
    for power in range(degree + 1):
        for local_power in range(power + 1):
            result[local_power] += poly.nth(power) * comb(power, local_power) * center ** (power - local_power)
    return result


def _asymptotic_valuation(values: list[Any]) -> int | None:
    return next((index for index, value in enumerate(values) if value != 0), None)


def _asymptotic_divide(top: list[Any], bottom: list[Any], count: int) -> list[Any] | None:
    quotient: list[Any] = []
    for index in range(count):
        value = (top[index] if index < len(top) else sympy.Rational(0)) - sum(bottom[offset] * quotient[index - offset] for offset in range(1, min(index, len(bottom) - 1) + 1))
        coefficient = value / bottom[0]
        if not _property_value_is_bounded(coefficient):
            return None
        quotient.append(coefficient)
    return quotient


def _asymptotic_verify(top: list[Any], bottom: list[Any], quotient: list[Any]) -> bool:
    try:
        return all(sympy.cancel((top[index] if index < len(top) else 0) - sum(bottom[offset] * quotient[index - offset] for offset in range(min(index, len(bottom) - 1) + 1))) == 0 for index in range(len(quotient)))
    except Exception:
        return False


def _asymptotic_render_terms(coefficients: list[Any], shift: int) -> str:
    values: list[str] = []
    for index, coefficient in enumerate(coefficients):
        if coefficient == 0:
            continue
        exponent, rendered = shift + index, sympy.sstr(coefficient)
        values.append(rendered if exponent == 0 else f"({rendered})*t" if exponent == 1 else f"({rendered})*t**{exponent}")
    return " + ".join(values) or "0"


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


def close_direct_work_sum(
    body: Expression,
    index_name: str,
    lower: Expression,
    upper: Expression,
    *,
    max_nodes: int,
) -> str | None:
    """Close a bounded degree-two polynomial sum for direct-work accounting only."""
    inputs = (body, lower, upper)
    if (
        sum(expression_node_count(item) for item in inputs) > max_nodes
        or not rational_ir_preflight(body, max_nodes=max_nodes, max_degree=2)
    ):
        return None
    try:
        index = sympy.Symbol(index_name)
        symbolic_body = _to_sympy(body)
        polynomial = sympy.Poly(symbolic_body, index)
        if polynomial.degree() > 2:
            return None
        closed = sympy.factor(
            sympy.summation(symbolic_body, (index, _to_sympy(lower), _to_sympy(upper)))
        )
        if sum(1 for _ in sympy.preorder_traversal(closed)) > max_nodes:
            return None
        return str(closed)
    except Exception:
        return None


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
