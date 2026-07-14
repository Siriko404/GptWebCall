from __future__ import annotations

import argparse
import json
import os
import struct
import sys
from pathlib import Path
from typing import Any, BinaryIO

from companion.core import (
    list_ready_calls,
    load_active_call,
    request_paths,
    start_call,
    stop_call,
)
from companion.downloads import finish_call, handle_completed_download


MAX_MESSAGE_SIZE = 1024 * 1024
ALLOWED_COMMANDS = {
    "health",
    "calls.list_ready",
    "call.active",
    "call.go",
    "download.completed",
    "call.done",
    "call.stop",
}


def read_message(stream: BinaryIO) -> dict[str, Any] | None:
    header = stream.read(4)
    if header == b"":
        return None
    if len(header) != 4:
        raise ValueError("native message header is truncated")
    length = struct.unpack("<I", header)[0]
    if length == 0:
        raise ValueError("native message body is empty")
    if length > MAX_MESSAGE_SIZE:
        raise ValueError("native message is too large")
    body = stream.read(length)
    if len(body) != length:
        raise ValueError("native message body is truncated")
    try:
        value = json.loads(body.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as error:
        raise ValueError("native message body is not valid UTF-8 JSON") from error
    if not isinstance(value, dict):
        raise ValueError("native message body must be a JSON object")
    return value


def write_message(stream: BinaryIO, value: dict[str, Any]) -> None:
    body = json.dumps(value, ensure_ascii=False, separators=(",", ":")).encode(
        "utf-8"
    )
    if not body or len(body) > MAX_MESSAGE_SIZE:
        raise ValueError("native response is empty or too large")
    stream.write(struct.pack("<I", len(body)))
    stream.write(body)
    stream.flush()


def dispatch(root: Path, message: dict[str, Any]) -> dict[str, Any] | list[Any] | None:
    if message.get("protocol_version") != 1:
        raise ValueError("protocol_version must be 1")
    command = message.get("command")
    if command not in ALLOWED_COMMANDS:
        raise ValueError(f"unknown command: {command}")
    payload = message.get("payload")
    if not isinstance(payload, dict):
        raise ValueError("payload must be a JSON object")
    root = Path(root).resolve()

    if command == "health":
        _require_keys(payload, set())
        return {"status": "OK", "protocol_version": 1, "root": str(root)}
    if command == "calls.list_ready":
        _require_keys(payload, set())
        return list_ready_calls(root)
    if command == "call.active":
        _require_keys(payload, set())
        return load_active_call(root)
    if command == "call.go":
        _require_keys(payload, {"exchange_id", "tab_id", "download_baseline"})
        exchange_id = _required_string(payload, "exchange_id")
        active = start_call(
            root,
            exchange_id,
            _required_integer(payload, "tab_id"),
            _integer_list(payload, "download_baseline"),
        )
        return {
            "active": active,
            "request_paths": request_paths(root, exchange_id),
        }
    if command == "download.completed":
        allowed = {
            "id",
            "filename",
            "state",
            "url",
            "finalUrl",
            "mime",
            "startTime",
            "endTime",
        }
        if not set(payload).issubset(allowed):
            raise ValueError("download payload contains unknown fields")
        _required_integer(payload, "id")
        _required_string(payload, "filename")
        return handle_completed_download(root, payload)
    if command == "call.done":
        _require_keys(payload, set())
        if load_active_call(root) is not None:
            return finish_call(root)
        last_result = root / "state" / "LAST_RESULT.json"
        if not last_result.is_file():
            raise RuntimeError("no call is active and no prior result exists")
        value = json.loads(last_result.read_text(encoding="utf-8"))
        return value["report"]
    if command == "call.stop":
        _require_keys(payload, set())
        return stop_call(root)
    raise AssertionError(f"unhandled command: {command}")


def serve(root: Path, incoming: BinaryIO, outgoing: BinaryIO) -> None:
    while True:
        try:
            message = read_message(incoming)
            if message is None:
                return
            command = str(message.get("command", "unknown"))
            result = dispatch(root, message)
            response = {"ok": True, "command": command, "result": result}
        except Exception as error:
            response = {
                "ok": False,
                "command": locals().get("command", "unknown"),
                "error": {"type": type(error).__name__, "message": str(error)},
            }
        write_message(outgoing, response)


def _require_keys(payload: dict[str, Any], required: set[str]) -> None:
    keys = set(payload)
    if keys != required:
        missing = sorted(required - keys)
        extra = sorted(keys - required)
        raise ValueError(f"payload fields do not match; missing={missing} extra={extra}")


def _required_string(payload: dict[str, Any], name: str) -> str:
    value = payload.get(name)
    if not isinstance(value, str) or not value:
        raise ValueError(f"{name} must be a non-empty string")
    return value


def _required_integer(payload: dict[str, Any], name: str) -> int:
    value = payload.get(name)
    if not isinstance(value, int) or isinstance(value, bool) or value < 0:
        raise ValueError(f"{name} must be a non-negative integer")
    return value


def _integer_list(payload: dict[str, Any], name: str) -> list[int]:
    value = payload.get(name)
    if not isinstance(value, list) or any(
        not isinstance(item, int) or isinstance(item, bool) or item < 0
        for item in value
    ):
        raise ValueError(f"{name} must contain non-negative integers")
    return value


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", required=True)
    options, chrome_arguments = parser.parse_known_args(argv)
    if chrome_arguments:
        origin = chrome_arguments[0]
        if not origin.startswith("chrome-extension://"):
            raise ValueError("native host caller origin is invalid")
    if os.name == "nt":
        import msvcrt

        msvcrt.setmode(sys.stdin.fileno(), os.O_BINARY)
        msvcrt.setmode(sys.stdout.fileno(), os.O_BINARY)
    serve(Path(options.root), sys.stdin.buffer, sys.stdout.buffer)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
