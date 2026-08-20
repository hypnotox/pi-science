"""Neutral bounded mapped-output expansion, alignment, and equivalence proof."""

from __future__ import annotations

from collections.abc import Callable, Mapping
from dataclasses import dataclass
from typing import Literal

from py_science.formula.computation import NamedRelationship, RetainedComputation
from py_science.formula.domains import OutputDomain
from py_science.formula.equivalence import equivalence_answer
from py_science.formula.expressions import (
    BinaryExpression,
    Call,
    Expression,
    ExpressionTooComplex,
    IndexedValue,
    Relationship,
    RelationshipOperator,
    Sum,
    Symbol,
)
from py_science.formula.models import (
    EquationTarget,
    ExpressionTarget,
    Interpretation,
    QueryAnswer,
)
from py_science.formula.reasoning import ReasoningContext
from py_science.formula.sympy_backend import NormalizationError, render

MAX_MAPPED_OUTPUT_EXPANSION_NODES = 16_384

@dataclass(slots=True)
class ExpansionBudget:
    remaining: int = MAX_MAPPED_OUTPUT_EXPANSION_NODES

    def consume(self, nodes: int = 1) -> None:
        self.remaining -= nodes
        if self.remaining < 0:
            raise ExpressionTooComplex(
                "comparison expansion exceeds its aggregate node bound"
            )


@dataclass(frozen=True, slots=True)
class MappedOperand:
    value: Expression
    binders: tuple[str, ...] | None
    domains: tuple[OutputDomain, ...]


@dataclass(frozen=True, slots=True)
class MappedOutputResult:
    interface_status: Literal["compatible", "incompatible", "unresolved"]
    expanded_interpretations: tuple[Interpretation, Interpretation] | None
    answer: QueryAnswer


class MappedOutputExpander:
    def __init__(
        self,
        analyzed: RetainedComputation,
        budget: ExpansionBudget,
        reserved_names: set[str],
    ) -> None:
        self.analyzed = analyzed
        self.budget = budget
        self.reserved_names = set(reserved_names)
        self.fresh_position = 0

    def expand(
        self,
        value: Expression,
        replacements: Mapping[str, Expression] | None = None,
    ) -> Expression:
        return self._visit(value, replacements or {}, frozenset(), ())

    def _visit(
        self,
        value: Expression,
        replacements: Mapping[str, Expression],
        bound: frozenset[str],
        producer_stack: tuple[str, ...],
    ) -> Expression:
        self.budget.consume()
        if isinstance(value, Symbol):
            if value.name in replacements and value.name not in bound:
                return self._visit(replacements[value.name], {}, bound, producer_stack)
            producer = self.analyzed.producers.get(value.name)
            if producer is not None and producer.arity == 0 and value.name not in bound:
                if producer.equation_name in producer_stack:
                    raise ExpressionTooComplex("comparison producer expansion is recursive")
                equation = self._producer_equation(producer.equation_name)
                return self._visit(
                    equation.formula.right,
                    {},
                    bound,
                    (*producer_stack, producer.equation_name),
                )
            return value
        if isinstance(value, IndexedValue):
            indices = tuple(
                self._visit(index, replacements, bound, producer_stack)
                for index in value.indices
            )
            producer = self.analyzed.producers.get(value.name)
            if producer is None:
                return IndexedValue(value.name, indices)
            if producer.arity != len(indices):
                raise ExpressionTooComplex("comparison producer arity changed after validation")
            if producer.equation_name in producer_stack:
                raise ExpressionTooComplex("comparison producer expansion is recursive")
            equation = self._producer_equation(producer.equation_name)
            lhs = equation.formula.left
            if not isinstance(lhs, IndexedValue):
                raise ExpressionTooComplex("comparison producer interface is inconsistent")
            formal_symbols = tuple(
                index for index in lhs.indices if isinstance(index, Symbol)
            )
            if len(formal_symbols) != len(lhs.indices):
                raise ExpressionTooComplex("comparison producer binders are inconsistent")
            formal = tuple(index.name for index in formal_symbols)
            return self._visit(
                equation.formula.right,
                dict(zip(formal, indices, strict=True)),
                bound,
                (*producer_stack, producer.equation_name),
            )
        if isinstance(value, Call):
            return Call(
                value.name,
                tuple(
                    self._visit(argument, replacements, bound, producer_stack)
                    for argument in value.arguments
                ),
            )
        if isinstance(value, BinaryExpression):
            return BinaryExpression(
                value.operator,
                self._visit(value.left, replacements, bound, producer_stack),
                self._visit(value.right, replacements, bound, producer_stack),
            )
        if isinstance(value, Sum):
            lower = self._visit(value.lower, replacements, bound, producer_stack)
            upper = self._visit(value.upper, replacements, bound, producer_stack)
            fresh = self._fresh_sum_name()
            renamed_body = _rename_bound(value.body, value.index, fresh)
            inner_replacements = {
                name: replacement
                for name, replacement in replacements.items()
                if name != value.index
            }
            body = self._visit(
                renamed_body,
                inner_replacements,
                bound | {fresh},
                producer_stack,
            )
            return Sum(body, fresh, lower, upper)
        return value

    def _producer_equation(self, name: str):
        return next(equation for equation in self.analyzed.equations if equation.name == name)

    def _fresh_sum_name(self) -> str:
        while True:
            name = f"comparison_sum_{self.fresh_position}"
            self.fresh_position += 1
            if name not in self.reserved_names:
                self.reserved_names.add(name)
                return name


def compare_mapped_outputs(
    name: str,
    left_target: ExpressionTarget | EquationTarget,
    right_target: ExpressionTarget | EquationTarget,
    left: RetainedComputation,
    right: RetainedComputation,
    budget: ExpansionBudget,
    reserved_names: set[str],
    reasoning_for: Callable[[tuple[NamedRelationship, ...]], ReasoningContext | None],
) -> MappedOutputResult:
    """Expand, align, and prove two mapped outputs behind neutral typed targets."""
    operands: list[MappedOperand] = []
    for target, analyzed in ((left_target, left), (right_target, right)):
        operand, blocker = _target_operand(target, analyzed)
        if operand is None:
            return _mapped_output(
                "incompatible",
                None,
                QueryAnswer(conclusion="inapplicable", blockers=(blocker,)),
            )
        operands.append(operand)
    left_operand, right_operand = operands
    if (left_operand.binders is None) != (right_operand.binders is None):
        return _mapped_incompatible(
            "mapped outputs have incompatible scalar and indexed interfaces"
        )
    if (
        left_operand.binders is not None
        and right_operand.binders is not None
        and len(left_operand.binders) != len(right_operand.binders)
    ):
        return _mapped_incompatible("mapped indexed outputs have different arity")

    canonical = canonical_indices(len(left_operand.binders or ()), reserved_names)
    left_expander = MappedOutputExpander(left, budget, reserved_names)
    right_expander = MappedOutputExpander(right, budget, reserved_names)
    domain_facts: tuple[NamedRelationship, ...] = ()
    interface_answers: tuple[QueryAnswer, ...] = ()
    if left_operand.binders is not None and right_operand.binders is not None:
        try:
            interface = _compare_mapped_domains(
                name,
                left_operand,
                right_operand,
                canonical,
                left_expander,
                right_expander,
                reasoning_for,
            )
        except ExpressionTooComplex as error:
            return _mapped_output(
                "unresolved",
                None,
                QueryAnswer(conclusion="unresolved", blockers=(str(error),)),
            )
        if isinstance(interface, MappedOutputResult):
            return interface
        domain_facts, interface_answers = interface

    try:
        left_value = left_expander.expand(
            left_operand.value,
            dict(
                zip(
                    left_operand.binders or (),
                    (Symbol(index) for index in canonical),
                    strict=True,
                )
            ),
        )
        right_value = right_expander.expand(
            right_operand.value,
            dict(
                zip(
                    right_operand.binders or (),
                    (Symbol(index) for index in canonical),
                    strict=True,
                )
            ),
        )
        answer = equivalence_answer(left_value, right_value, reasoning_for(domain_facts))
        answer = _merge_interface_qualification(answer, interface_answers)
        left_rendered = render(left_value)
        right_rendered = render(right_value)
    except ExpressionTooComplex as error:
        return _mapped_output(
            "compatible",
            None,
            QueryAnswer(conclusion="unresolved", blockers=(str(error),)),
        )
    except NormalizationError:
        return _mapped_output(
            "compatible",
            None,
            QueryAnswer(
                conclusion="unresolved",
                blockers=("expanded mapped output cannot be normalized",),
            ),
        )
    interpretations = (
        Interpretation(
            normalized_sympy=left_rendered.sympy,
            normalized_latex=left_rendered.latex,
        ),
        Interpretation(
            normalized_sympy=right_rendered.sympy,
            normalized_latex=right_rendered.latex,
        ),
    )
    return _mapped_output("compatible", interpretations, answer)



def _merge_interface_qualification(
    answer: QueryAnswer, interface_answers: tuple[QueryAnswer, ...]
) -> QueryAnswer:
    conditions = tuple(
        dict.fromkeys(
            condition
            for item in (*interface_answers, answer)
            for condition in item.conditions
        )
    )
    uses = tuple(
        {
            (use.name, use.relationship): use
            for item in (*interface_answers, answer)
            for use in item.assumptions_used
        }.values()
    )
    unsupported = tuple(
        dict.fromkeys(
            value
            for item in (*interface_answers, answer)
            for value in item.relevant_unsupported_assumptions
        )
    )
    conclusion = answer.conclusion
    if conclusion == "proved" and (conditions or uses):
        conclusion = "proved_under_assumptions"
    return answer.model_copy(
        update={
            "check": None,
            "conclusion": conclusion,
            "conditions": conditions,
            "assumptions_used": uses,
            "relevant_unsupported_assumptions": unsupported,
            "derived_candidates": (),
            "constraint_uses": (),
        }
    )

def _compare_mapped_domains(
    name: str,
    left: MappedOperand,
    right: MappedOperand,
    canonical: tuple[str, ...],
    left_expander: MappedOutputExpander,
    right_expander: MappedOutputExpander,
    reasoning_for: Callable[[tuple[NamedRelationship, ...]], ReasoningContext | None],
) -> tuple[tuple[NamedRelationship, ...], tuple[QueryAnswer, ...]] | MappedOutputResult:
    assert left.binders is not None and right.binders is not None
    left_by_name = {domain.index: domain for domain in left.domains}
    right_by_name = {domain.index: domain for domain in right.domains}
    left_replacements = dict(
        zip(left.binders, (Symbol(index) for index in canonical), strict=True)
    )
    right_replacements = dict(
        zip(right.binders, (Symbol(index) for index in canonical), strict=True)
    )
    facts: list[NamedRelationship] = []
    answers: list[QueryAnswer] = []
    reasoning = reasoning_for(())
    for position, (left_name, right_name, canonical_name) in enumerate(
        zip(left.binders, right.binders, canonical, strict=True)
    ):
        left_domain = left_by_name[left_name]
        right_domain = right_by_name[right_name]
        aligned_left = (
            left_expander.expand(left_domain.lower, left_replacements),
            left_expander.expand(left_domain.upper, left_replacements),
        )
        aligned_right = (
            right_expander.expand(right_domain.lower, right_replacements),
            right_expander.expand(right_domain.upper, right_replacements),
        )
        for endpoint, left_bound, right_bound in zip(
            ("lower", "upper"), aligned_left, aligned_right, strict=True
        ):
            answer = equivalence_answer(left_bound, right_bound, reasoning)
            if answer.conclusion == "disproved":
                return _mapped_incompatible(
                    f"mapped output {endpoint} domains differ at position {position}"
                )
            if answer.conclusion not in {"proved", "proved_under_assumptions"}:
                blockers = answer.blockers or (
                    f"mapped output {endpoint} domain equality is unproved",
                )
                return _mapped_output(
                    "unresolved",
                    None,
                    QueryAnswer(conclusion="unresolved", blockers=blockers),
                )
            answers.append(answer)
        lower, upper = aligned_left
        facts.extend(
            (
                NamedRelationship(
                    name=f"comparison:{name}:{position}:lower",
                    source=f"{canonical_name} >= {render(lower).sympy}",
                    value=Relationship(
                        RelationshipOperator.GREATER_EQUAL,
                        Symbol(canonical_name),
                        lower,
                    ),
                ),
                NamedRelationship(
                    name=f"comparison:{name}:{position}:upper",
                    source=f"{canonical_name} <= {render(upper).sympy}",
                    value=Relationship(
                        RelationshipOperator.LESS_EQUAL,
                        Symbol(canonical_name),
                        upper,
                    ),
                ),
            )
        )
    return tuple(facts), tuple(answers)


def _target_operand(
    target: ExpressionTarget | EquationTarget,
    analyzed: RetainedComputation,
) -> tuple[MappedOperand | None, str]:
    if isinstance(target, ExpressionTarget):
        if analyzed.expression is None:
            return None, "expression target requires an expression candidate"
        return MappedOperand(analyzed.expression, None, ()), ""
    equation = next(
        (item for item in analyzed.equations if item.name == target.name), None
    )
    if equation is None:
        return None, "mapped equation target is unknown"
    lhs = equation.formula.left
    if isinstance(lhs, IndexedValue):
        binder_symbols = tuple(
            index for index in lhs.indices if isinstance(index, Symbol)
        )
        if len(binder_symbols) != len(lhs.indices):
            return None, "mapped equation binders are inconsistent"
        binders = tuple(index.name for index in binder_symbols)
        domains = tuple(
            next(domain for domain in equation.output_domains if domain.index == binder)
            for binder in binders
        )
        return MappedOperand(equation.formula.right, binders, domains), ""
    return MappedOperand(equation.formula.right, None, ()), ""


def _mapped_incompatible(blocker: str) -> MappedOutputResult:
    return _mapped_output(
        "incompatible",
        None,
        QueryAnswer(conclusion="inapplicable", blockers=(blocker,)),
    )


def _mapped_output(
    interface: Literal["compatible", "incompatible", "unresolved"],
    expanded: tuple[Interpretation, Interpretation] | None,
    answer: QueryAnswer,
) -> MappedOutputResult:
    return MappedOutputResult(
        interface_status=interface,
        expanded_interpretations=expanded,
        answer=answer.model_copy(
            update={"check": None, "derived_candidates": (), "constraint_uses": ()}
        ),
    )


def canonical_indices(arity: int, reserved_names: set[str]) -> tuple[str, ...]:
    result: list[str] = []
    position = 0
    while len(result) < arity:
        name = f"comparison_index_{position}"
        position += 1
        if name not in reserved_names:
            reserved_names.add(name)
            result.append(name)
    return tuple(result)
def _rename_bound(value: Expression, old: str, new: str) -> Expression:
    if isinstance(value, Symbol):
        return Symbol(new) if value.name == old else value
    if isinstance(value, IndexedValue):
        return IndexedValue(
            value.name,
            tuple(_rename_bound(index, old, new) for index in value.indices),
        )
    if isinstance(value, Call):
        return Call(
            value.name,
            tuple(_rename_bound(argument, old, new) for argument in value.arguments),
        )
    if isinstance(value, BinaryExpression):
        return BinaryExpression(
            value.operator,
            _rename_bound(value.left, old, new),
            _rename_bound(value.right, old, new),
        )
    if isinstance(value, Sum):
        lower = _rename_bound(value.lower, old, new)
        upper = _rename_bound(value.upper, old, new)
        body = value.body if value.index == old else _rename_bound(value.body, old, new)
        return Sum(body, value.index, lower, upper)
    return value
