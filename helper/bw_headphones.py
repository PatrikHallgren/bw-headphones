#!/usr/bin/env python3
"""Px7 S3 state and RPC helpers.

The transport is deliberately small and dependency-light.  It uses BlueZ's
GDBus API through PyGObject, and keeps the B&W RPC framing independent from
the D-Bus session so it can be tested without hardware.
"""

from __future__ import annotations

import json
import os
import struct
import subprocess
import sys
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable

REQUEST_UUID = "ada50ce9-67b8-4a97-9d8e-37e1d083156c"
RESPONSE_UUID = "cb909093-3559-4b0c-9a7f-3f1773122fdc"
NOTIFICATION_UUID = "df55d475-9a32-457a-9e20-38cf14e853fb"

ANC_MODES = ("off", "anc", "pass-through")

COMMANDS = {
    (0x03, 0x01): "ANC mode",
    (0x03, 0x02): "Set ANC mode",
    (0x08, 0x0C): "Battery percentage",
    (0x08, 0x0B): "Charging status",
    (0x04, 0x0C): "Audio source",
    (0x05, 0x06): "Audio codec",
    (0x04, 0x14): "Sampling rate",
    (0x02, 0x01): "Software version",
}


class ProtocolError(ValueError):
    pass


def _pack(value: Any) -> bytes:
    if value is None:
        return b"\xc0"
    if value is True:
        return b"\xc3"
    if value is False:
        return b"\xc2"
    if isinstance(value, int):
        if 0 <= value < 128:
            return bytes([value])
        if -32 <= value < 0:
            return bytes([value & 0xFF])
        if 0 <= value <= 0xFF:
            return b"\xcc" + struct.pack("<B", value)
        if 0 <= value <= 0xFFFF:
            return b"\xcd" + struct.pack(">H", value)
        if -128 <= value <= 127:
            return b"\xd0" + struct.pack(">b", value)
        if -32768 <= value <= 32767:
            return b"\xd1" + struct.pack(">h", value)
        return b"\xd2" + struct.pack(">i", value)
    if isinstance(value, str):
        raw = value.encode("utf-8")
        if len(raw) < 32:
            return bytes([0xA0 | len(raw)]) + raw
        if len(raw) <= 0xFF:
            return b"\xd9" + bytes([len(raw)]) + raw
        return b"\xda" + struct.pack(">H", len(raw)) + raw
    if isinstance(value, (bytes, bytearray)):
        raw = bytes(value)
        return b"\xc4" + bytes([len(raw)]) + raw
    if isinstance(value, list):
        prefix = bytes([0x90 | len(value)]) if len(value) < 16 else b"\xdc" + struct.pack(">H", len(value))
        return prefix + b"".join(_pack(item) for item in value)
    if isinstance(value, dict):
        prefix = bytes([0x80 | len(value)]) if len(value) < 16 else b"\xde" + struct.pack(">H", len(value))
        return prefix + b"".join(_pack(k) + _pack(v) for k, v in value.items())
    raise TypeError(f"unsupported MessagePack value: {type(value)!r}")


def _unpack(raw: bytes, offset: int = 0) -> tuple[Any, int]:
    if offset >= len(raw):
        raise ProtocolError("truncated MessagePack value")
    marker = raw[offset]
    offset += 1
    if marker <= 0x7F:
        return marker, offset
    if marker >= 0xE0:
        return marker - 256, offset
    if 0xA0 <= marker <= 0xBF:
        size = marker & 0x1F
        return raw[offset:offset + size].decode(), offset + size
    if 0x90 <= marker <= 0x9F:
        values = []
        for _ in range(marker & 0x0F):
            value, offset = _unpack(raw, offset)
            values.append(value)
        return values, offset
    if 0x80 <= marker <= 0x8F:
        result = {}
        for _ in range(marker & 0x0F):
            key, offset = _unpack(raw, offset)
            value, offset = _unpack(raw, offset)
            result[key] = value
        return result, offset
    if marker == 0xC0: return None, offset
    if marker == 0xC2: return False, offset
    if marker == 0xC3: return True, offset
    sizes = {0xCC: (">B", 1), 0xCD: (">H", 2), 0xD0: (">b", 1), 0xD1: (">h", 2), 0xD2: (">i", 4)}
    if marker in sizes:
        fmt, size = sizes[marker]
        end = offset + size
        if end > len(raw): raise ProtocolError("truncated numeric value")
        return struct.unpack(fmt, raw[offset:end])[0], end
    if marker in (0xD9, 0xDA):
        size_len = 1 if marker == 0xD9 else 2
        fmt = ">B" if size_len == 1 else ">H"
        if offset + size_len > len(raw): raise ProtocolError("truncated string length")
        size = struct.unpack(fmt, raw[offset:offset + size_len])[0]
        offset += size_len
        return raw[offset:offset + size].decode(), offset + size
    if marker == 0xC4:
        if offset >= len(raw): raise ProtocolError("truncated binary length")
        size = raw[offset]
        offset += 1
        return raw[offset:offset + size], offset + size
    if marker == 0xDC:
        if offset + 2 > len(raw): raise ProtocolError("truncated array length")
        count = struct.unpack(">H", raw[offset:offset + 2])[0]
        offset += 2
        values = []
        for _ in range(count):
            value, offset = _unpack(raw, offset)
            values.append(value)
        return values, offset
    if marker == 0xDE:
        if offset + 2 > len(raw): raise ProtocolError("truncated map length")
        count = struct.unpack(">H", raw[offset:offset + 2])[0]
        offset += 2
        result = {}
        for _ in range(count):
            key, offset = _unpack(raw, offset)
            value, offset = _unpack(raw, offset)
            result[key] = value
        return result, offset
    raise ProtocolError(f"unsupported MessagePack marker 0x{marker:02x}")


def encode_request(namespace: int, command_id: int, payload: Any = None) -> bytes:
    body = _pack(payload) if payload is not None else b""
    kind = b"\x0b\x92" if body else b"\x0b\x12"
    packet = kind + bytes([command_id, namespace])
    if body:
        packet += struct.pack("<H", len(body)) + body
    return bytes([len(packet)]) + packet


def decode_frame(raw: bytes) -> dict[str, Any]:
    # BlueZ delivers the characteristic value without the request envelope's
    # leading size byte. Accepting it as well makes captured traces easier to
    # replay without weakening the frame checks.
    if len(raw) > 4 and raw[0] == len(raw) - 1 and raw[1] in (0x0C, 0x0D) and raw[2] in (0x12, 0x92):
        raw = raw[1:]
    if len(raw) < 4:
        raise ProtocolError("RPC frame is too short")
    kind = int.from_bytes(raw[:2], "little")
    command_id, namespace = raw[2], raw[3]
    key = (namespace, command_id)
    result: dict[str, Any] = {
        "kind": "response" if kind in (0x120C, 0x920C) else "notification",
        "namespace": namespace,
        "command_id": command_id,
        "name": COMMANDS.get(key, f"Unknown {namespace:02X}:{command_id:02X}"),
        "error": 0,
        "payload": None,
    }
    if kind not in (0x120C, 0x920C, 0x120D, 0x920D):
        raise ProtocolError(f"unsupported RPC type 0x{kind:04x}")
    if kind in (0x120C, 0x920C):
        if len(raw) < 6: raise ProtocolError("response has no error field")
        result["error"] = int.from_bytes(raw[4:6], "little")
        payload_offset = 6
    else:
        payload_offset = 4
    if kind in (0x920C, 0x920D):
        header_offset = payload_offset
        if kind == 0x920C:
            header_offset = 6
        if len(raw) < header_offset + 2: raise ProtocolError("payload header is truncated")
        size = int.from_bytes(raw[header_offset:header_offset + 2], "little")
        payload_offset = header_offset + 2
        payload = raw[payload_offset:payload_offset + size]
        if len(payload) != size: raise ProtocolError("payload length exceeds frame")
        result["payload"], end = _unpack(payload)
        if end != len(payload): raise ProtocolError("payload has trailing bytes")
    return result


def state_path() -> Path:
    return Path(os.environ.get("XDG_STATE_HOME", Path.home() / ".local/state")) / "bw-headphones/status.json"


def write_state(state: dict[str, Any]) -> None:
    path = state_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(".json.tmp")
    tmp.write_text(json.dumps(state, sort_keys=True) + "\n", encoding="utf-8")
    tmp.replace(path)


def base_state() -> dict[str, Any]:
    return {
        "schema_version": 1,
        "connected": False,
        "address": "",
        "name": "Px7 S3",
        "battery": {"level": -1, "charging": False},
        "anc_mode": "unknown",
        "capabilities": [],
        "transport_ready": False,
        "audio_source": "",
        "codec": "",
        "sampling_rate": "",
        "firmware": "",
        "last_error": "",
        "updated_at": int(time.time()),
    }


def matching_name(name: str) -> bool:
    normalized = "".join(ch for ch in name.lower() if ch.isalnum())
    return "px7s3" in normalized or ("bowerswilkins" in normalized and "head" in normalized)


def selected_address() -> str:
    return os.environ.get("BW_HEADPHONES_ADDRESS", "").lower().replace("-", ":")


def command(mode: str) -> tuple[int, int, Any]:
    if mode not in ANC_MODES:
        raise ValueError(f"unknown ANC mode: {mode}")
    return 0x03, 0x02, ANC_MODES.index(mode)


def retry(operation: Callable[[], Any], attempts: int = 3, delay: float = 0.15,
          sleep: Callable[[float], None] = time.sleep) -> Any:
    """Run a bounded transport operation, preserving the final exception."""
    if attempts < 1:
        raise ValueError("attempts must be positive")
    last_error = None
    for index in range(attempts):
        try:
            return operation()
        except Exception as exc:
            last_error = exc
            if index + 1 < attempts:
                sleep(delay * (index + 1))
    raise last_error


def cli_main(argv: list[str]) -> int:
    if argv[:1] == ["status"]:
        path = state_path()
        if path.exists():
            sys.stdout.write(path.read_text(encoding="utf-8"))
        else:
            sys.stdout.write(json.dumps(base_state()) + "\n")
        return 0
    if argv[:1] == ["refresh"]:
        subprocess.run(["systemctl", "--user", "try-restart", "io.github.patrikhallgren.bw-headphones.service"], check=False)
        return 0
    if argv[:1] == ["set-anc"] and len(argv) == 2:
        mode = argv[1]
        command(mode)
        return control_once(mode)
    print("usage: px7s3ctl status --json | refresh | set-anc off|anc|pass-through", file=sys.stderr)
    return 2


def control_once(mode: str) -> int:
    # The daemon owns the live GATT session. A command is sent over its local
    # stdin socket once that socket exists; otherwise return a useful error.
    socket_path = Path(os.environ.get("XDG_RUNTIME_DIR", "/run/user/" + str(os.getuid()))) / "bw-headphones.sock"
    if not socket_path.exists():
        print("px7s3d is not running", file=sys.stderr)
        return 1
    try:
        import socket
        with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as sock:
            sock.settimeout(3)
            sock.connect(str(socket_path))
            sock.sendall((json.dumps({"op": "set-anc", "mode": mode}) + "\n").encode())
            response = sock.recv(4096).decode().strip()
        result = json.loads(response or "{}")
        if not result.get("ok"):
            print(result.get("error", "command failed"), file=sys.stderr)
            return 1
        return 0
    except Exception as exc:
        print(str(exc), file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(cli_main(sys.argv[1:]))
