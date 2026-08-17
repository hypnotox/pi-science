#!/usr/bin/env python3
"""Generate the provider-facing Pi schema from the Python request model."""

from __future__ import annotations

import argparse
import copy
import json
import sys
from pathlib import Path
from typing import Any

from py_science.formula import AnalysisRequest
from py_science.formula.models import MAX_FORMULA_BYTES

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_OUTPUT = ROOT / "packages" / "pi-science" / "src" / "formula-schema.json"
QUERY_DEFINITIONS = (
    "EquivalenceQuery",
    "ClosedFormQuery",
    "PropertiesQuery",
    "LimitQuery",
    "AsymptoticQuery",
)

JsonObject = dict[str, Any]


def _resolve_reference(reference: str, definitions: dict[str, JsonObject]) -> JsonObject:
    prefix = "#/$defs/"
    if not reference.startswith(prefix):
        raise ValueError(f"unsupported schema reference: {reference}")
    name = reference.removeprefix(prefix)
    if name not in definitions:
        raise ValueError(f"unknown schema reference: {reference}")
    return copy.deepcopy(definitions[name])


def _normalize(value: Any, definitions: dict[str, JsonObject]) -> Any:
    if isinstance(value, list):
        return [_normalize(item, definitions) for item in value]
    if not isinstance(value, dict):
        return value
    if "$ref" in value:
        if set(value) != {"$ref"}:
            raise ValueError("schema references with sibling keywords are unsupported")
        return _normalize(_resolve_reference(value["$ref"], definitions), definitions)

    source = {key: item for key, item in value.items() if key not in {"default", "title"}}
    source.pop("discriminator", None)
    if "const" in source:
        source["enum"] = [source.pop("const")]
    if "oneOf" in source:
        if "anyOf" in source:
            raise ValueError("schema node contains both oneOf and anyOf")
        source["anyOf"] = source.pop("oneOf")

    normalized = {key: _normalize(item, definitions) for key, item in source.items()}
    if "anyOf" in normalized:
        options = [option for option in normalized["anyOf"] if option != {"type": "null"}]
        if len(options) == 1 and set(normalized) == {"anyOf"}:
            return options[0]
        normalized["anyOf"] = options
    return normalized


def _query_variants(
    definitions: dict[str, JsonObject], *, system: bool
) -> list[JsonObject]:
    target = _normalize(_resolve_reference("#/$defs/EquationTarget", definitions), definitions)
    variants: list[JsonObject] = []
    for name in QUERY_DEFINITIONS:
        variant = _normalize(copy.deepcopy(definitions[name]), definitions)
        properties = variant["properties"]
        required = list(variant.get("required", []))
        if system:
            properties["target"] = copy.deepcopy(target)
            if "target" not in required:
                required.append("target")
        else:
            properties.pop("target", None)
            required = [field for field in required if field != "target"]
        variant["required"] = required
        variants.append(variant)
    return variants


def generate_schema() -> JsonObject:
    raw = AnalysisRequest.model_json_schema()
    definitions = raw.get("$defs")
    properties = raw.get("properties")
    if not isinstance(definitions, dict) or not isinstance(properties, dict):
        raise ValueError("AnalysisRequest emitted an incompatible JSON Schema")

    metadata = {
        name: _normalize(copy.deepcopy(schema), definitions)
        for name, schema in properties.items()
        if name not in {"syntax", "expression", "equations", "queries"}
    }
    expression_queries = {
        "items": {"anyOf": _query_variants(definitions, system=False)},
        "maxItems": properties["queries"]["maxItems"],
        "type": "array",
    }
    system_queries = {
        "items": {"anyOf": _query_variants(definitions, system=True)},
        "maxItems": properties["queries"]["maxItems"],
        "type": "array",
    }
    expression = {
        "additionalProperties": False,
        "properties": {
            "expression": {
                "maxLength": MAX_FORMULA_BYTES,
                "minLength": 1,
                "type": "string",
            },
            **copy.deepcopy(metadata),
            "queries": expression_queries,
        },
        "required": ["expression"],
        "type": "object",
    }
    equations = _normalize(copy.deepcopy(properties["equations"]), definitions)
    equations["minItems"] = 1
    system = {
        "additionalProperties": False,
        "properties": {
            "equations": equations,
            **copy.deepcopy(metadata),
            "queries": system_queries,
        },
        "required": ["equations"],
        "type": "object",
    }
    return {"anyOf": [expression, system]}


def _encoded_schema() -> bytes:
    return (json.dumps(generate_schema(), indent=2, sort_keys=True) + "\n").encode()


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()
    expected = _encoded_schema()
    output = args.output.resolve()

    if args.check:
        try:
            actual = output.read_bytes()
        except FileNotFoundError:
            actual = b""
        if actual != expected:
            relative = output.relative_to(ROOT) if output.is_relative_to(ROOT) else output
            command = (
                "uv run --locked python scripts/generate-pi-formula-schema.py "
                f"--output {relative}"
            )
            print(
                f"generated Pi formula schema is stale: run `{command}`",
                file=sys.stderr,
            )
            return 1
        return 0

    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_bytes(expected)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
