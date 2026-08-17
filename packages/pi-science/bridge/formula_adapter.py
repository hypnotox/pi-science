#!/usr/bin/env python3
"""Private bounded JSON adapter; stdout is reserved for exactly one response."""

from __future__ import annotations

import json
import sys
from typing import Any, cast

from py_science.formula import AnalysisRequest, analyze
from pydantic import ValidationError

PROTOCOL_VERSION = 4
# The public request permits 262,144 UTF-8 source bytes. This whole-envelope
# limit also covers JSON escaping and every bounded collection/name field.
MAX_ENVELOPE_BYTES = 2_097_152
# The Python result policy is 262,144 bytes; this adds bounded protocol framing.
MAX_RESPONSE_BYTES = 262_400
MAX_DIAGNOSTIC_BYTES = 4_096


def _strict_object(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    value: dict[str, Any] = {}
    for key, item in pairs:
        if key in value:
            raise ValueError("duplicate JSON object key")
        value[key] = item
    return value


def _encoded(payload: dict[str, Any]) -> bytes | None:
    encoder = json.JSONEncoder(
        ensure_ascii=False,
        separators=(",", ":"),
        sort_keys=True,
    )
    chunks: list[bytes] = []
    size = 0
    for chunk in encoder.iterencode(payload):
        encoded = chunk.encode("utf-8")
        size += len(encoded)
        if size + 1 > MAX_RESPONSE_BYTES:
            return None
        chunks.append(encoded)
    chunks.append(b"\n")
    return b"".join(chunks)


def response(payload: dict[str, Any]) -> bool:
    encoded = _encoded(payload)
    if encoded is None:
        return False
    sys.stdout.buffer.write(encoded)
    return True


def _request_error(error: Exception) -> int:
    message = str(error).encode("utf-8")[:MAX_DIAGNOSTIC_BYTES].decode("utf-8", "replace")
    response(
        {
            "version": PROTOCOL_VERSION,
            "error": {"kind": "request", "message": message},
        }
    )
    return 2


def main() -> int:
    if sys.argv[1:] == ["--health"]:
        response({"version": PROTOCOL_VERSION, "result": {"status": "healthy"}})
        return 0
    try:
        raw = sys.stdin.buffer.read(MAX_ENVELOPE_BYTES + 1)
        if len(raw) > MAX_ENVELOPE_BYTES:
            raise ValueError("protocol envelope exceeds its 2,097,152-byte UTF-8 bound")
        envelope = json.loads(raw, object_pairs_hook=_strict_object)
        if not isinstance(envelope, dict):
            raise ValueError("invalid protocol envelope")
        typed_envelope = cast(dict[str, object], envelope)
        if len(typed_envelope) != 2 or set(typed_envelope) != {"version", "request"}:
            raise ValueError("invalid protocol envelope")
        if typed_envelope["version"] != PROTOCOL_VERSION:
            raise ValueError("unsupported protocol version")
        request_payload = typed_envelope["request"]
        if not isinstance(request_payload, dict):
            raise ValueError("invalid analysis request")
        # JSON validation preserves the strict frozen public contract while accepting
        # JSON arrays for tuple fields. Mathematical policy remains in AnalysisRequest.
        request = AnalysisRequest.model_validate_json(
            json.dumps(request_payload, ensure_ascii=False, separators=(",", ":"))
        )
        outcome = analyze(request)
        result = outcome.model_dump(mode="json", exclude_none=True)
        if outcome.status == "success":
            result["abstract_work"] = outcome.abstract_work
            if outcome.system is not None:
                system_result = result["system"]
                system_result.update({
                    "aggregate_operation_counts": (
                        outcome.system.aggregate_operation_counts.model_dump(mode="json")
                        if outcome.system.aggregate_operation_counts is not None
                        else None
                    ),
                    "total_work": outcome.system.total_work,
                    "primitive_invocations": outcome.system.primitive_invocations,
                })
                for equation_result, equation in zip(
                    system_result["equations"], outcome.system.equations, strict=True
                ):
                    equation_result.update({
                        "aggregate_operation_counts": (
                            equation.aggregate_operation_counts.model_dump(mode="json")
                            if equation.aggregate_operation_counts is not None
                            else None
                        ),
                        "aggregate_work": equation.aggregate_work,
                        "primitive_invocations": equation.primitive_invocations,
                    })
        if outcome.status == "failure":
            error = result["error"]
            error.update({
                "location": outcome.error.location.model_dump(mode="json") if outcome.error.location else None,  # noqa: E501
                "source": outcome.error.source.model_dump(mode="json") if outcome.error.source else None,  # noqa: E501
                "supported_alternative": outcome.error.supported_alternative,
            })
        if not response({"version": PROTOCOL_VERSION, "result": result}):
            response(
                {
                    "version": PROTOCOL_VERSION,
                    "error": {
                        "kind": "internal",
                        "message": "formula adapter response exceeds its bound",
                    },
                }
            )
            return 3
    except (
        ValueError,
        TypeError,
        json.JSONDecodeError,
        UnicodeDecodeError,
        UnicodeEncodeError,
        ValidationError,
    ) as error:
        return _request_error(error)
    return 0


if __name__ == "__main__":
    sys.exit(main())
