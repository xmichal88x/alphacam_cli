# ruff: noqa: TRY003

from __future__ import annotations

import json
import struct
from socket import socket
from typing import Any

MAX_FRAME_SIZE = 16 * 1024 * 1024

JSON_RPC_VERSION = "2.0"

PARSE_ERROR = -32700
INVALID_REQUEST = -32600
METHOD_NOT_FOUND = -32601
INTERNAL_ERROR = -32603
COM_ERROR = -32000


def pack_message(msg: dict[str, object]) -> bytes:
    payload = json.dumps(msg, ensure_ascii=False).encode("utf-8")
    if len(payload) > MAX_FRAME_SIZE:
        raise ValueError(f"Message exceeds maximum size of {MAX_FRAME_SIZE} bytes")
    header = struct.pack("!I", len(payload))
    return header + payload


def _recv_exact(sock: socket, n: int) -> bytes:
    buf = bytearray(n)
    view = memoryview(buf)
    while view:
        received = sock.recv_into(view, len(view))
        if received == 0:
            return b""
        view = view[received:]
    return bytes(buf)


def read_frame(sock: socket) -> dict[str, object] | None:
    header = _recv_exact(sock, 4)
    if not header:
        return None
    length = struct.unpack("!I", header)[0]
    if length > MAX_FRAME_SIZE:
        raise ValueError(f"Frame exceeds maximum size of {MAX_FRAME_SIZE} bytes")
    if length == 0:
        raise ValueError("Empty frame")
    payload = _recv_exact(sock, length)
    if not payload:
        return None
    result: dict[str, object] = json.loads(payload.decode("utf-8"))
    return result


def make_request(method: str, params: dict[str, object], msg_id: int = 1) -> dict[str, object]:
    return {
        "jsonrpc": JSON_RPC_VERSION,
        "method": method,
        "params": params,
        "id": msg_id,
    }


def make_response(result: Any, msg_id: int = 1) -> dict[str, Any]:
    return {
        "jsonrpc": JSON_RPC_VERSION,
        "result": result,
        "id": msg_id,
    }


def make_error(code: int, message: str, msg_id: int | None = None) -> dict[str, object]:
    body: dict[str, object] = {
        "jsonrpc": JSON_RPC_VERSION,
        "error": {
            "code": code,
            "message": message,
        },
    }
    if msg_id is not None:
        body["id"] = msg_id
    else:
        body["id"] = None
    return body
