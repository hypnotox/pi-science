#!/usr/bin/env python3
"""Private JSON-lines adapter; stdout is reserved for exactly one response."""

from __future__ import annotations

import json
import sys
from typing import Any, cast

from py_science.formula import AnalysisRequest, FormulaSyntax, analyze
from pydantic import ValidationError

PROTOCOL_VERSION = 1
MAX_ENVELOPE_BYTES = 66_560


def response(payload: dict[str, Any]) -> None:
    print(json.dumps(payload, separators=(",", ":"), sort_keys=True))


def main() -> int:
    if sys.argv[1:] == ["--health"]:
        response({"version": PROTOCOL_VERSION, "result": {"status": "healthy"}})
        return 0
    try:
        raw = sys.stdin.buffer.read(MAX_ENVELOPE_BYTES + 1)
        if len(raw) > MAX_ENVELOPE_BYTES:
            raise ValueError("protocol envelope exceeds its byte bound")
        envelope = json.loads(raw)
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
        typed_request = cast(dict[str, object], request_payload)
        if set(typed_request) != {"syntax", "expression"}:
            raise ValueError("invalid analysis request")
        if typed_request["syntax"] != "sympy" or not isinstance(
            typed_request["expression"], str
        ):
            raise ValueError("invalid analysis request")
        request = AnalysisRequest(
            syntax=FormulaSyntax.SYMPY,
            expression=typed_request["expression"],
        )
        result = analyze(request).model_dump(mode="json", exclude_none=True)
        response({"version": PROTOCOL_VERSION, "result": result})
    except (
        ValueError,
        TypeError,
        json.JSONDecodeError,
        UnicodeDecodeError,
        ValidationError,
    ) as error:
        response({"version": PROTOCOL_VERSION, "error": {"kind": "request", "message": str(error)}})
        return 2
    return 0


if __name__ == "__main__":
    sys.exit(main())
