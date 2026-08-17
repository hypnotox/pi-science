# ruff: noqa: E501
# pyright: reportMissingTypeStubs=false, reportPrivateUsage=false, reportUnknownMemberType=false, reportUnknownVariableType=false, reportUnknownArgumentType=false, reportAttributeAccessIssue=false
"""Bounded assumption reasoning owned by mathematical queries.

Only directed definitions, safe symbol equalities, declared scalar domains, and
single-symbol affine rational inequalities are interpreted. Everything else is
retained as a relevant unsupported qualification rather than guessed.
"""
from __future__ import annotations

from dataclasses import dataclass
from fractions import Fraction
from typing import Any

import sympy
from py_science.formula.expressions import (
    BinaryExpression,
    BinaryOperator,
    Expression,
    IntegerLiteral,
    RationalLiteral,
    Relationship,
    RelationshipOperator,
    Symbol,
    expression_children,
    substitute,
)
from py_science.formula.models import MathematicalDomain, RelationshipUse
from py_science.formula.sympy_backend import _to_sympy, rational_ir_preflight

MAX_REASONING_STEPS = 4096
MAX_INTERMEDIATE_NODES = 4096


@dataclass(frozen=True, slots=True)
class DomainFact:
    symbol: str
    lower: Fraction | None = None
    lower_strict: bool = False
    upper: Fraction | None = None
    upper_strict: bool = False
    integer: bool = False
    sources: tuple[RelationshipUse, ...] = ()

    def excludes_zero(self) -> bool:
        return (self.lower is not None and (self.lower > 0 or (self.lower == 0 and self.lower_strict))) or (self.upper is not None and (self.upper < 0 or (self.upper == 0 and self.upper_strict)))

    def accepts(self, value: sympy.Rational) -> bool:
        rational = Fraction(int(value.p), int(value.q))
        if self.integer and value.q != 1:
            return False
        if self.lower is not None and (rational < self.lower or (rational == self.lower and self.lower_strict)):
            return False
        return not (
            self.upper is not None
            and (rational > self.upper or (rational == self.upper and self.upper_strict))
        )


@dataclass(frozen=True, slots=True)
class ReasoningContext:
    domains: dict[str, MathematicalDomain]
    definitions: tuple[Any, ...]
    assumptions: tuple[Any, ...]
    replacements: dict[str, Expression]
    replacement_uses: tuple[RelationshipUse, ...]
    facts: dict[str, DomainFact]
    unsupported: tuple[tuple[str, frozenset[str]], ...]

    @classmethod
    def build(
        cls,
        domains: dict[str, MathematicalDomain],
        definitions: tuple[Any, ...],
        assumptions: tuple[Any, ...],
    ) -> ReasoningContext:
        replacements: dict[str, Expression] = {}
        replacement_uses: list[RelationshipUse] = []
        steps = 0
        for item in definitions:
            expression = substitute(item.expression, replacements, max_nodes=MAX_INTERMEDIATE_NODES)
            replacements[item.name] = expression
            replacement_uses.append(RelationshipUse(name=item.name, relationship=item.source))
            steps += 1
        unsupported: list[tuple[str, frozenset[str]]] = []
        inequalities: list[Any] = []
        for item in assumptions:
            steps += 1
            if steps > MAX_REASONING_STEPS:
                unsupported.append((item.name, frozenset(_symbols_relationship(item.value))))
                continue
            relationship: Relationship = item.value
            left = substitute(relationship.left, replacements, max_nodes=MAX_INTERMEDIATE_NODES)
            right = substitute(relationship.right, replacements, max_nodes=MAX_INTERMEDIATE_NODES)
            oriented = _oriented_equality(relationship.operator, left, right)
            if oriented is not None:
                name, expression = oriented
                replacements[name] = substitute(expression, replacements, max_nodes=MAX_INTERMEDIATE_NODES)
                replacement_uses.append(RelationshipUse(name=item.name, relationship=item.source))
            elif relationship.operator is not RelationshipOperator.EQUAL:
                inequalities.append(item)
            else:
                unsupported.append((item.name, frozenset(_symbols_relationship(relationship))))
        facts = {name: _domain_fact(name, domain) for name, domain in domains.items()}
        for item in inequalities:
            derived = _affine_fact(item, replacements, facts.get)
            if derived is None:
                unsupported.append((item.name, frozenset(_symbols_relationship(item.value))))
                continue
            current = facts.get(derived.symbol, DomainFact(derived.symbol))
            facts[derived.symbol] = _intersect(current, derived)
        return cls(domains, definitions, assumptions, replacements, tuple(replacement_uses), facts, tuple(unsupported))

    def apply(self, expression: Expression) -> Expression:
        resolved = expression
        for _ in range(len(self.replacements) + 1):
            updated = substitute(resolved, self.replacements, max_nodes=MAX_INTERMEDIATE_NODES)
            if updated == resolved:
                return resolved
            resolved = updated
        return resolved

    def relevant_unsupported(self, symbols: set[str]) -> tuple[str, ...]:
        return tuple(name for name, relevant in self.unsupported if relevant & symbols)

    def relevant_uses(self, symbols: set[str], *, include_facts: bool = False) -> tuple[RelationshipUse, ...]:
        uses = [use for use in self.replacement_uses if _relationship_source_symbols(use.relationship) & symbols]
        if include_facts:
            for symbol in symbols:
                fact = self.facts.get(symbol)
                if fact is not None:
                    uses.extend(fact.sources)
        return _unique_uses(uses)

    def prove_nonzero(self, expression: Expression) -> tuple[bool, tuple[RelationshipUse, ...]]:
        applied = self.apply(expression)
        if isinstance(applied, IntegerLiteral):
            return applied.value != 0, ()
        if isinstance(applied, RationalLiteral):
            return applied.numerator != 0, ()
        if isinstance(applied, Symbol):
            fact = self.facts.get(applied.name)
            return (fact.excludes_zero(), fact.sources) if fact is not None else (False, ())
        if isinstance(applied, BinaryExpression) and applied.operator is BinaryOperator.MULTIPLY:
            left, left_uses = self.prove_nonzero(applied.left)
            right, right_uses = self.prove_nonzero(applied.right)
            return left and right, _unique_uses((*left_uses, *right_uses))
        if isinstance(applied, BinaryExpression) and applied.operator is BinaryOperator.POWER:
            exponent = applied.right
            if isinstance(exponent, IntegerLiteral) and exponent.value != 0:
                return self.prove_nonzero(applied.left)
        return False, ()

    def proves_abs_less_one(self, symbol: str) -> tuple[bool, tuple[RelationshipUse, ...]]:
        fact = self.facts.get(symbol)
        if fact is None or fact.lower is None or fact.upper is None:
            return False, ()
        lower_ok = fact.lower > -1 or (fact.lower == -1 and fact.lower_strict)
        upper_ok = fact.upper < 1 or (fact.upper == 1 and fact.upper_strict)
        return lower_ok and upper_ok, fact.sources

    def sign(self, expression: Expression) -> tuple[int | None, tuple[RelationshipUse, ...]]:
        applied = self.apply(expression)
        if isinstance(applied, IntegerLiteral):
            return (1 if applied.value > 0 else -1 if applied.value < 0 else 0), ()
        if isinstance(applied, RationalLiteral):
            return (1 if applied.numerator > 0 else -1 if applied.numerator < 0 else 0), ()
        if isinstance(applied, Symbol):
            fact = self.facts.get(applied.name)
            if fact is None:
                return None, ()
            if fact.lower is not None and (fact.lower > 0 or (fact.lower == 0 and fact.lower_strict)):
                return 1, fact.sources
            if fact.upper is not None and (fact.upper < 0 or (fact.upper == 0 and fact.upper_strict)):
                return -1, fact.sources
            return None, ()
        if isinstance(applied, BinaryExpression) and applied.operator is BinaryOperator.MULTIPLY:
            left, left_uses = self.sign(applied.left)
            right, right_uses = self.sign(applied.right)
            if left is not None and right is not None:
                return left * right, _unique_uses((*left_uses, *right_uses))
        if isinstance(applied, BinaryExpression) and applied.operator is BinaryOperator.POWER and isinstance(applied.right, IntegerLiteral):
            base, uses = self.sign(applied.left)
            if base is not None:
                if applied.right.value == 0:
                    return 1, uses
                return (abs(base) if applied.right.value % 2 == 0 else base), uses
        return None, ()

    def assignment_valid(self, values: dict[Any, Any]) -> bool:
        for symbol, value in values.items():
            if not isinstance(value, sympy.Rational):
                return False
            fact = self.facts.get(str(symbol), _domain_fact(str(symbol), self.domains.get(str(symbol), MathematicalDomain.REAL)))
            if not fact.accepts(value):
                return False
        for name, domain in self.domains.items():
            try:
                resolved = _to_sympy(self.apply(Symbol(name))).subs(values)
                if resolved.free_symbols or not resolved.is_Rational:
                    return False
                fact = self.facts.get(name, _domain_fact(name, domain))
                if not fact.accepts(resolved):
                    return False
            except Exception:
                return False
        for item in self.assumptions:
            try:
                relationship = item.value
                left = _to_sympy(self.apply(relationship.left)).subs(values)
                right = _to_sympy(self.apply(relationship.right)).subs(values)
                if left.free_symbols or right.free_symbols:
                    return False
                if not _relation_holds(relationship.operator, left, right):
                    return False
            except Exception:
                return False
        return True


def collect_denominators(expression: Expression) -> tuple[Expression, ...]:
    found: list[Expression] = []
    def visit(value: Expression) -> None:
        if isinstance(value, BinaryExpression) and value.operator is BinaryOperator.DIVIDE:
            found.append(value.right)
        for child in expression_children(value):
            visit(child)
    visit(expression)
    return tuple(found)


def _oriented_equality(operator: RelationshipOperator, left: Expression, right: Expression) -> tuple[str, Expression] | None:
    if operator is not RelationshipOperator.EQUAL:
        return None
    if isinstance(left, Symbol) and left.name not in _symbols(right):
        return left.name, right
    if isinstance(right, Symbol) and right.name not in _symbols(left):
        return right.name, left
    return None


def _domain_fact(name: str, domain: MathematicalDomain) -> DomainFact:
    if domain is MathematicalDomain.POSITIVE_INTEGER:
        return DomainFact(name, Fraction(0), True, integer=True)
    if domain is MathematicalDomain.NONNEGATIVE_INTEGER:
        return DomainFact(name, Fraction(0), integer=True)
    if domain is MathematicalDomain.INTEGER:
        return DomainFact(name, integer=True)
    if domain is MathematicalDomain.POSITIVE_REAL:
        return DomainFact(name, Fraction(0), True)
    return DomainFact(name)


def _affine_fact(item: Any, replacements: dict[str, Expression], existing: Any) -> DomainFact | None:
    try:
        relationship: Relationship = item.value
        left_expression = substitute(
            relationship.left,
            replacements,
            max_nodes=MAX_INTERMEDIATE_NODES,
        )
        right_expression = substitute(
            relationship.right,
            replacements,
            max_nodes=MAX_INTERMEDIATE_NODES,
        )
        if not rational_ir_preflight(left_expression, max_degree=1) or not rational_ir_preflight(
            right_expression, max_degree=1
        ):
            return None
        left = _to_sympy(left_expression)
        right = _to_sympy(right_expression)
        difference = sympy.expand(left - right)
        if sum(1 for _ in sympy.preorder_traversal(difference)) > MAX_INTERMEDIATE_NODES:
            return None
        symbols = tuple(difference.free_symbols)
        if len(symbols) != 1:
            return None
        symbol = symbols[0]
        polynomial = sympy.Poly(difference, symbol)
        if polynomial.degree() != 1 or any(not coefficient.is_Rational for coefficient in polynomial.all_coeffs()):
            return None
        coefficient, constant = polynomial.all_coeffs()
        bound = Fraction(int((-constant / coefficient).p), int((-constant / coefficient).q))
        operator = relationship.operator
        if coefficient < 0:
            operator = {
                RelationshipOperator.LESS: RelationshipOperator.GREATER,
                RelationshipOperator.LESS_EQUAL: RelationshipOperator.GREATER_EQUAL,
                RelationshipOperator.GREATER: RelationshipOperator.LESS,
                RelationshipOperator.GREATER_EQUAL: RelationshipOperator.LESS_EQUAL,
            }[operator]
        use = RelationshipUse(name=item.name, relationship=item.source)
        if operator in {RelationshipOperator.GREATER, RelationshipOperator.GREATER_EQUAL}:
            return DomainFact(str(symbol), lower=bound, lower_strict=operator is RelationshipOperator.GREATER, sources=(use,))
        if operator in {RelationshipOperator.LESS, RelationshipOperator.LESS_EQUAL}:
            return DomainFact(str(symbol), upper=bound, upper_strict=operator is RelationshipOperator.LESS, sources=(use,))
    except Exception:
        return None
    return None


def _intersect(left: DomainFact, right: DomainFact) -> DomainFact:
    lower, lower_strict = left.lower, left.lower_strict
    if right.lower is not None and (lower is None or right.lower > lower or (right.lower == lower and right.lower_strict)):
        lower, lower_strict = right.lower, right.lower_strict
    elif right.lower == lower:
        lower_strict = lower_strict or right.lower_strict
    upper, upper_strict = left.upper, left.upper_strict
    if right.upper is not None and (upper is None or right.upper < upper or (right.upper == upper and right.upper_strict)):
        upper, upper_strict = right.upper, right.upper_strict
    elif right.upper == upper:
        upper_strict = upper_strict or right.upper_strict
    return DomainFact(left.symbol, lower, lower_strict, upper, upper_strict, left.integer or right.integer, _unique_uses((*left.sources, *right.sources)))


def _relation_holds(operator: RelationshipOperator, left: Any, right: Any) -> bool:
    if operator is RelationshipOperator.EQUAL:
        return bool(left == right)
    if operator is RelationshipOperator.LESS:
        return bool(left < right)
    if operator is RelationshipOperator.LESS_EQUAL:
        return bool(left <= right)
    if operator is RelationshipOperator.GREATER:
        return bool(left > right)
    return bool(left >= right)


def _symbols(expression: Expression) -> set[str]:
    names = {expression.name} if isinstance(expression, Symbol) else set()
    for child in expression_children(expression):
        names |= _symbols(child)
    return names


def _symbols_relationship(value: Relationship) -> set[str]:
    return _symbols(value.left) | _symbols(value.right)


def _relationship_source_symbols(source: str) -> set[str]:
    import re
    return set(re.findall(r"[A-Za-z][A-Za-z0-9_]*", source))


def _unique_uses(values: tuple[RelationshipUse, ...] | list[RelationshipUse]) -> tuple[RelationshipUse, ...]:
    seen: set[tuple[str, str]] = set()
    result: list[RelationshipUse] = []
    for value in values:
        key = (value.name, value.relationship)
        if key not in seen:
            seen.add(key)
            result.append(value)
    return tuple(result)
