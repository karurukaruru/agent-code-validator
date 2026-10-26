"""Portable, sanitized evidence. Hashes establish integrity, not truth."""
from __future__ import annotations

import hashlib
import json
import math
import os
import platform
import re
import sys
from datetime import datetime, timezone
from pathlib import Path


def now():
    return datetime.now(timezone.utc).isoformat()


def canonical(value):
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False, allow_nan=False)


def digest(value):
    return hashlib.sha256(canonical(value).encode()).hexdigest()


def validate_shape(value):
    stack, visited = [(value, 0)], 0
    while stack:
        item, depth = stack.pop()
        visited += 1
        if depth > 64 or visited > 100_000:
            raise ValueError("JSON exceeds depth or node limits")
        if isinstance(item, dict):
            if any(not isinstance(k, str) for k in item):
                raise ValueError("JSON object keys must be strings")
            stack.extend((x, depth + 1) for x in item.values())
        elif isinstance(item, list):
            stack.extend((x, depth + 1) for x in item)
        elif isinstance(item, float) and not math.isfinite(item):
            raise ValueError("Nonfinite JSON number")


def strict_json(text):
    def pairs(items):
        result = {}
        for key, value in items:
            if key in result:
                raise ValueError("Duplicate JSON key: " + key)
            result[key] = value
        return result
    try:
        value = json.loads(text, object_pairs_hook=pairs, parse_constant=lambda x: (_ for _ in ()).throw(ValueError("Nonfinite JSON number")))
    except RecursionError as exc:
        raise ValueError("JSON exceeds parser depth limit") from exc
    validate_shape(value)
    return value


def sanitize(value):
    secrets = [v for k, v in os.environ.items() if any(s in k.upper() for s in ("API_KEY", "TOKEN", "SECRET", "PASSWORD")) and len(v) >= 6]
    def clean(v):
        if isinstance(v, dict):
            return {clean(str(k)): "[REDACTED]" if re.search(r"authorization|api.?key|secret|password|access.?token", str(k), re.I) else clean(x) for k, x in v.items()}
        if isinstance(v, list):
            return [clean(x) for x in v]
        if isinstance(v, str):
            for secret in secrets:
                v = v.replace(secret, "[REDACTED]")
            v = re.sub(r"(?i)bearer\s+[a-z0-9._~+/-]+=*", "Bearer [REDACTED]", v)
            return re.sub(r"\b(?:sk-|tvly-)[A-Za-z0-9_-]{8,}", "[REDACTED]", v)
        return v
    return clean(value)


def environment():
    from . import __version__
    return {"python": sys.version.split()[0], "platform": platform.platform(), "patchcourt": __version__}


def write_json(path, value):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    data = sanitize(value)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2, allow_nan=False) + "\n", encoding="utf-8")
    return data


def read_json(path):
    path = Path(path)
    if path.stat().st_size > 8_000_000:
        raise ValueError("Evidence input exceeds 8 MB")
    return strict_json(path.read_text(encoding="utf-8-sig"))
