"""Bounded canonical exact scalar values shared by formula semantics."""
from __future__ import annotations

import math
import re
from dataclasses import dataclass

MAX_EXACT_DIGITS = 1024
MAX_EXACT_BITS = 3402
_SCALAR = re.compile(r"-?(0|[1-9][0-9]*)(/[1-9][0-9]*|\.[0-9]+)?\Z")


@dataclass(frozen=True, slots=True)
class ExactRational:
    numerator: int
    denominator: int

    def __post_init__(self) -> None:
        if self.denominator <= 0:
            raise ValueError("exact rational denominator must be positive")
        if max(abs(self.numerator).bit_length(), self.denominator.bit_length()) > MAX_EXACT_BITS:
            raise ValueError("exact rational exceeds its pre-reduction bit bound")
        divisor = math.gcd(self.numerator, self.denominator)
        numerator = self.numerator // divisor
        denominator = self.denominator // divisor
        if numerator == 0:
            denominator = 1
        if max(abs(numerator).bit_length(), denominator.bit_length()) > MAX_EXACT_BITS:
            raise ValueError("exact rational exceeds its bit bound")
        object.__setattr__(self, "numerator", numerator)
        object.__setattr__(self, "denominator", denominator)


def rational(numerator: int, denominator: int = 1) -> ExactRational | None:
    if denominator <= 0 or max(abs(numerator).bit_length(), denominator.bit_length()) > MAX_EXACT_BITS:  # noqa: E501
        return None
    divisor = math.gcd(numerator, denominator)
    numerator //= divisor
    denominator //= divisor
    if numerator == 0:
        denominator = 1
    if max(abs(numerator).bit_length(), denominator.bit_length()) > MAX_EXACT_BITS:
        return None
    return ExactRational(numerator, denominator)


def parse_exact_scalar(source: str) -> ExactRational | None:
    if len(source) > MAX_EXACT_DIGITS * 2 + 2 or _SCALAR.fullmatch(source) is None:
        return None
    sign = -1 if source.startswith("-") else 1
    body = source[1:] if sign < 0 else source
    if "/" in body:
        numerator, denominator = body.split("/", 1)
        if len(numerator) > MAX_EXACT_DIGITS or len(denominator) > MAX_EXACT_DIGITS:
            return None
        return rational(sign * int(numerator), int(denominator))
    if "." in body:
        whole, fraction = body.split(".", 1)
        if len(whole) + len(fraction) > MAX_EXACT_DIGITS:
            return None
        return rational(sign * int(whole + fraction), 10 ** len(fraction))
    if len(body) > MAX_EXACT_DIGITS:
        return None
    return rational(sign * int(body))


def render_exact(value: ExactRational) -> str:
    return str(value.numerator) if value.denominator == 1 else f"{value.numerator}/{value.denominator}"  # noqa: E501
