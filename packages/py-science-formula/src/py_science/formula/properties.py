# ruff: noqa: E501, E701, I001, RUF007, RUF034
# pyright: reportMissingTypeStubs=false, reportUnknownMemberType=false, reportUnknownArgumentType=false, reportUnknownVariableType=false, reportUnknownParameterType=false, reportReturnType=false, reportAttributeAccessIssue=false
"""Guarded exact univariate property and limit rules.

This module deliberately exposes no general SymPy property operation.  Its only
backend transformations are factor/cancel and derivative/forward difference of
an expression that has passed the query rational IR and intermediate bounds.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import sympy
from py_science.formula.exact_values import ExactRational, parse_exact_scalar, render_exact
from py_science.formula.expressions import BinaryExpression, BinaryOperator, Expression, InfinityLiteral, IntegerLiteral, Sum, Symbol, expression_children
from py_science.formula.models import LimitEvidence, LimitQuery, PropertyCheck, PropertyEvidence, QueryAnswer
from py_science.formula.reasoning import ReasoningContext
from py_science.formula.sympy_backend import bounded_rational_difference, rational_ir_preflight

MAX_NODES = 4096


@dataclass(frozen=True, slots=True)
class RationalShape:
    value: Any
    numerator: Any
    denominator: Any
    variable: Any


def afmm_tail_property_answer(expression: Expression, check: PropertyCheck, reasoning: ReasoningContext | None) -> QueryAnswer | None:
    """Qualify the already-closed AFMM geometric tail without a generic series call."""
    if reasoning is None or not isinstance(expression, Sum) or not isinstance(expression.upper, InfinityLiteral) or expression.upper.sign < 0:
        return None
    if not isinstance(expression.lower, Symbol) or not reasoning.proves_integral(expression.lower):
        return None
    power = next((node for node in _walk(expression.body) if isinstance(node, BinaryExpression) and node.operator is BinaryOperator.POWER and isinstance(node.right, Symbol) and node.right.name == expression.index and isinstance(node.left, Symbol)), None)
    if power is None: return None
    p, q = expression.lower.name, power.left.name
    p_fact, q_fact = reasoning.facts.get(p), reasoning.facts.get(q)
    if p_fact is None or q_fact is None or p_fact.lower is None or p_fact.lower < 0 or q_fact.lower is None or q_fact.lower < 0 or q_fact.upper is None or q_fact.upper > 1 or (q_fact.upper == 1 and not q_fact.upper_strict):
        return None
    uses = tuple(dict.fromkeys((*p_fact.sources, *q_fact.sources)))
    if check.kind == "sign":
        strict = q_fact.lower > 0 or (q_fact.lower == 0 and q_fact.lower_strict) or (p_fact.lower == 0 and p_fact.upper == 0)
        return QueryAnswer(check=check, conclusion="proved_under_assumptions" if uses else "proved", assumptions_used=uses, evidence=PropertyEvidence(value="strictly positive" if strict else "nonnegative (strict positivity is not proved)", intervals=(f"0 <= {q} < 1",)))
    if check.kind == "monotonicity" and check.variable == p:
        return QueryAnswer(check=check, conclusion="proved_under_assumptions" if uses else "proved", assumptions_used=uses, evidence=PropertyEvidence(value="nonincreasing (integer forward difference)", intervals=(f"{p} >= 0",)))
    if check.kind == "monotonicity" and check.variable == q:
        return QueryAnswer(check=check, conclusion="proved_under_assumptions" if uses else "proved", assumptions_used=uses, evidence=PropertyEvidence(value="nondecreasing", intervals=(f"0 <= {q} < 1",)))
    if check.kind == "valid_domain" and check.variable == q:
        return QueryAnswer(check=check, conclusion="proved_under_assumptions" if uses else "proved", assumptions_used=uses, evidence=PropertyEvidence(value="exclude 1", intervals=(f"active domain: 0 <= {q} < 1",)))
    if check.kind == "singularities" and check.variable == q:
        return QueryAnswer(check=check, conclusion="proved_under_assumptions" if uses else "proved", assumptions_used=uses, evidence=PropertyEvidence(value=f"{q} = 1: pole of order 2; outside the active domain", intervals=(f"active domain: 0 <= {q} < 1",)))
    return None


def property_answer(expression: Expression, check: PropertyCheck, reasoning: ReasoningContext | None) -> QueryAnswer:
    if reasoning is None:
        return _unresolved("query reasoning exceeds its bound", check)
    shape = _shape(expression, check.variable if check.kind != "sign" else None, reasoning)
    if shape is None:
        return _unresolved("query family is unsupported", check)
    if check.kind == "valid_domain":
        roots = _roots(shape.denominator, shape.variable)
        if roots is None:
            return _unresolved("denominator factors are unsupported", check)
        excluded = tuple(_number(root) for root, _ in roots)
        return _proved(check, "all real values" if not excluded else "exclude " + ", ".join(excluded), tuple(f"x != {root}" for root in excluded))
    if check.kind == "singularities":
        roots = _roots(shape.denominator, shape.variable)
        if roots is None:
            return _unresolved("denominator factors are unsupported", check)
        if not roots:
            return _proved(check, "no singularities")
        items = tuple(f"x = {_number(root)}: pole of order {multiplicity}" for root, multiplicity in roots)
        domain = reasoning.facts.get(check.variable)
        suffix = ""
        if domain is not None:
            excluded = [root for root, _ in roots if not domain.accepts(root)]
            if excluded:
                suffix = "; outside the active domain: " + ", ".join(_number(root) for root in excluded)
        return _proved(check, "; ".join(items) + suffix)
    if check.kind == "sign":
        # A sign chart needs a real ordering for every free parameter.
        if any(str(item) not in reasoning.facts for item in shape.value.free_symbols):
            return QueryAnswer(check=check, conclusion="inapplicable", blockers=("realness or sign of symbolic parameters is not proved",))
        chart = _sign_chart(shape)
        if chart is None:
            return _unresolved("exact factor sign chart is unsupported", check)
        return _proved(check, chart[0], chart[1])
    # Monotonicity: real variables use the guarded derivative; integral variables
    # use f(x+1)-f(x), then precisely the same chart grammar.
    fact = reasoning.facts.get(check.variable)
    if fact is None:
        return QueryAnswer(check=check, conclusion="inapplicable", blockers=("realness of the query variable is not proved",))
    transformed = _difference(shape.value, shape.variable) if fact.integer else _derivative(shape.value, shape.variable)
    if transformed is None:
        return _unresolved("guarded monotonicity transformation exceeds its bound", check)
    transformed_expression = _from_sympy(transformed)
    if transformed_expression is None:
        return _unresolved("guarded monotonicity transformation exceeds its bound", check)
    derivative_shape = _shape(transformed_expression, check.variable, reasoning)
    if derivative_shape is None:
        return _unresolved("guarded monotonicity transformation exceeds its bound", check)
    chart = _sign_chart(derivative_shape)
    if chart is None:
        return _unresolved("exact factor sign chart is unsupported", check)
    value, intervals = chart
    if value.startswith("nonnegative"):
        return _proved(check, "nondecreasing (integer forward difference)" if fact.integer else "nondecreasing", intervals)
    if value.startswith("nonpositive"):
        return _proved(check, "nonincreasing (integer forward difference)" if fact.integer else "nonincreasing", intervals)
    nonnegative = tuple(item.split(": ")[0] for item in intervals if item.endswith("positive"))
    nonpositive = tuple(item.split(": ")[0] for item in intervals if item.endswith("negative"))
    if nonnegative:
        return _proved(check, "nondecreasing (integer forward difference)" if fact.integer else "nondecreasing", nonnegative)
    if nonpositive:
        return _proved(check, "nonincreasing (integer forward difference)" if fact.integer else "nonincreasing", nonpositive)
    return _unresolved("derivative sign is not uniform on the active domain", check)


def limit_answer(expression: Expression, query: LimitQuery, reasoning: ReasoningContext | None) -> QueryAnswer:
    if reasoning is None:
        return _unresolved("query reasoning exceeds its bound")
    shape = _shape(expression, query.variable, reasoning)
    if shape is None:
        return _unresolved("query family is unsupported")
    point = str(query.point)
    if point in {"oo", "-oo"}:
        result = _infinite_limit(shape, point == "oo")
        return result if result is not None else _unresolved("polynomial-degree limit is unsupported")
    exact = parse_exact_scalar(point)
    if exact is None:
        return _unresolved("limit point is invalid")
    value = sympy.Rational(exact.numerator, exact.denominator)
    denominator_at_point = shape.denominator.subs(shape.variable, value)
    if denominator_at_point != 0:
        evaluated = shape.value.subs(shape.variable, value)
        if not evaluated.is_Rational:
            return _unresolved("exact substitution is unsupported")
        rendered = _number(evaluated)
        return QueryAnswer(conclusion="proved", evidence=LimitEvidence(exists=True, value=rendered, left=rendered, right=rendered))
    roots = _roots(shape.denominator, shape.variable)
    if roots is None:
        return _unresolved("denominator factors are unsupported")
    order = next((multiplicity for root, multiplicity in roots if root == value), None)
    if order is None:
        return _unresolved("limit cancellation is unsupported")
    # cancel was already guarded in _shape: a remaining denominator root is a pole.
    numerator = shape.numerator.subs(shape.variable, value)
    if numerator == 0:
        return _unresolved("limit cancellation is unsupported")
    lead = sympy.sign(numerator) * (1 if order % 2 == 0 else 1)
    left = "oo" if (lead > 0 if order % 2 == 0 else lead < 0) else "-oo"
    right = "oo" if lead > 0 else "-oo"
    if query.direction == "left":
        return QueryAnswer(conclusion="proved", evidence=LimitEvidence(exists=True, value=left, left=left, right=None))
    if query.direction == "right":
        return QueryAnswer(conclusion="proved", evidence=LimitEvidence(exists=True, value=right, left=None, right=right))
    if left == right:
        return QueryAnswer(conclusion="proved", evidence=LimitEvidence(exists=True, value=left, left=left, right=right))
    return QueryAnswer(conclusion="proved", evidence=LimitEvidence(exists=False, value=None, left=left, right=right))


def _shape(expression: Expression, variable_name: str | None, reasoning: ReasoningContext) -> RationalShape | None:
    try:
        applied = reasoning.apply(expression)
    except Exception:
        return None
    if not rational_ir_preflight(applied):
        return None
    normalized = bounded_rational_difference(applied, IntegerLiteral(0))
    if normalized is None:
        return None
    symbols = tuple(normalized.left.free_symbols | normalized.right.free_symbols)
    if variable_name is None:
        if len(symbols) != 1:
            return None
        variable = symbols[0]
    else:
        variable = sympy.Symbol(variable_name)
        if variable not in symbols and symbols:
            # Constants are permitted; other symbols are parameters.
            pass
    if not _bounded(normalized.numerator) or not _bounded(normalized.denominator):
        return None
    return RationalShape(sympy.cancel(normalized.left), normalized.numerator, normalized.denominator, variable)


def _roots(denominator: Any, variable: Any) -> tuple[tuple[Any, int], ...] | None:
    try:
        if not _bounded(denominator): return None
        factored: Any = sympy.factor_list(denominator, variable)
        factors: Any = factored[1]
        roots: list[tuple[Any, int]] = []
        for factor, multiplicity in factors:
            polynomial = sympy.Poly(factor, variable)
            if polynomial.degree() != 1 or any(not item.is_Rational for item in polynomial.all_coeffs()): return None
            root = -polynomial.coeff_monomial(1) / polynomial.coeff_monomial(variable)
            roots.append((root, int(multiplicity)))
        return tuple(sorted(roots, key=lambda item: float(item[0])))
    except Exception:
        return None


def _sign_chart(shape: RationalShape) -> tuple[str, tuple[str, ...]] | None:
    roots_n, roots_d = _roots(shape.numerator, shape.variable), _roots(shape.denominator, shape.variable)
    if roots_n is None or roots_d is None: return None
    roots = sorted({root for root, _ in (*roots_n, *roots_d)}, key=float)
    if any(symbol != shape.variable for symbol in shape.value.free_symbols): return None
    # Factor chart is evaluated at exact rational representatives of each cell.
    points = [roots[0] - 1] if roots else [sympy.Rational(0)]
    points += [(left + right) / 2 for left, right in zip(roots, roots[1:], strict=False)]
    if roots: points.append(roots[-1] + 1)
    signs = []
    for point in points:
        value = shape.value.subs(shape.variable, point)
        if not value.is_Rational: return None
        signs.append(sympy.sign(value))
    intervals = tuple(_interval(index, roots) for index, sign in enumerate(signs) if sign >= 0)
    if signs and all(sign >= 0 for sign in signs): return "nonnegative", intervals
    if signs and all(sign <= 0 for sign in signs): return "nonpositive", tuple(_interval(index, roots) for index, sign in enumerate(signs) if sign <= 0)
    return "sign chart", tuple(f"{_interval(index, roots)}: {'positive' if sign > 0 else 'negative'}" for index, sign in enumerate(signs))


def _derivative(value: Any, variable: Any) -> Any | None:
    try:
        if not _bounded(value): return None
        result = sympy.diff(value, variable)
        return result if _bounded(result) else None
    except Exception: return None


def _difference(value: Any, variable: Any) -> Any | None:
    try:
        if not _bounded(value): return None
        result = sympy.cancel(value.subs(variable, variable + 1) - value)
        return result if _bounded(result) else None
    except Exception: return None


def _infinite_limit(shape: RationalShape, positive: bool) -> QueryAnswer | None:
    try:
        numerator, denominator = sympy.Poly(shape.numerator, shape.variable), sympy.Poly(shape.denominator, shape.variable)
        if any(not item.is_Rational for item in (*numerator.all_coeffs(), *denominator.all_coeffs())): return None
        degree = numerator.degree() - denominator.degree()
        if degree < 0: value = "0"
        elif degree == 0: value = _number(numerator.LC() / denominator.LC())
        else:
            sign = sympy.sign(numerator.LC() / denominator.LC()) * (1 if positive or degree % 2 == 0 else -1)
            value = "oo" if sign > 0 else "-oo"
        return QueryAnswer(conclusion="proved", evidence=LimitEvidence(exists=True, value=value, left=value if not positive else None, right=value if positive else None))
    except Exception: return None


def _walk(value: Expression):
    yield value
    for child in expression_children(value):
        yield from _walk(child)


def _bounded(value: Any) -> bool:
    try: return sum(1 for _ in sympy.preorder_traversal(value)) <= MAX_NODES
    except Exception: return False


def _from_sympy(value: Any) -> Expression | None:
    from py_science.formula.parser import ParseFailure, parse_expression
    parsed = parse_expression(str(value))
    return None if isinstance(parsed, (ParseFailure, tuple)) else parsed


def _number(value: Any) -> str:
    return render_exact(ExactRational(int(value.p), int(value.q)))


def _interval(index: int, roots: list[Any]) -> str:
    left = "-oo" if index == 0 else _number(roots[index - 1])
    right = "oo" if index == len(roots) else _number(roots[index])
    return f"({left}, {right})"


def _proved(check: PropertyCheck, value: str, intervals: tuple[str, ...] = ()) -> QueryAnswer:
    return QueryAnswer(check=check, conclusion="proved", evidence=PropertyEvidence(value=value, intervals=intervals))


def _unresolved(blocker: str, check: PropertyCheck | None = None) -> QueryAnswer:
    return QueryAnswer(check=check, conclusion="unresolved", blockers=(blocker,))
