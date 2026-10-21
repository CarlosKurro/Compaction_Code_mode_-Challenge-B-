"""Small, dependency-free artifact and context measurement helpers."""
from __future__ import annotations

import hashlib
import json
import math
from pathlib import Path
import time
from typing import Any


def encode(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def save(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    # Replace only after a complete write, preserving the previous checkpoint on error.
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    # Windows scanners can briefly hold a file without FILE_SHARE_DELETE.
    # Keep the previous file intact and retry the atomic rename, never truncate it.
    for attempt in range(8):
        try:
            temporary.replace(path)
            break
        except PermissionError:
            if attempt == 7:
                raise
            time.sleep(.03 * (attempt + 1))


def load(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def measure(value: Any) -> dict:
    """Comparable local heuristic, NOT a model tokenizer or provider usage."""
    size = len(encode(value).encode("utf-8"))
    return {"utf8_bytes": size, "estimated_tokens": math.ceil(size / 4),
            "method": "ceil(serialized UTF-8 bytes / 4); heuristic, not API usage"}


def comparison(before: Any, after: Any) -> dict:
    first, second = measure(before), measure(after)
    return {"before": first, "after": second,
            "byte_reduction_percent": round(100 * (1 - second["utf8_bytes"] / first["utf8_bytes"]), 3)}


def request(instructions: str, data: dict, task: str) -> dict:
    return {"instructions": instructions, "input": [
        {"role": "user", "content": encode(data)},
        {"role": "user", "content": task},
    ], "store": False}


def confined(root: Path, relative: str) -> Path:
    root = root.resolve()
    path = (root / relative).resolve()
    if not path.is_relative_to(root) or path == root:
        raise ValueError("Path is outside the permitted workspace")
    return path
