"""Explicit local credential loading without shell evaluation or secret output."""
from pathlib import Path
import os
import re

NAMES = {"DEEPSEEK_API_KEY", "TAVILY_API_KEY", "NEBIUS_API_KEY", "NEBIUS_MODEL", "GLM_API_KEY"}


def load_local_credentials(path, *, override=False):
    source = Path(path)
    if source.is_symlink() or not source.is_file() or source.stat().st_size > 16000:
        raise ValueError("Credential file must be a regular local file of at most 16 KB")
    values = {}
    for line in source.read_text(encoding="utf-8-sig").splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        match = re.fullmatch(r"([A-Z][A-Z0-9_]*)\s*=\s*(.*)", line)
        if not match or match[1] not in NAMES:
            raise ValueError("Credential file contains an unsupported declaration")
        name, value = match.groups()
        if name in values:
            raise ValueError("Credential file contains a repeated declaration")
        if value[:1] in {"'", '"'}:
            if len(value) < 2 or value[-1] != value[0]:
                raise ValueError("Credential file contains an unterminated quoted value")
            value = value[1:-1]
        if not value or len(value) > 4096 or any(ord(c) < 32 for c in value):
            raise ValueError("Credential file contains an empty or unsupported value")
        values[name] = value
    loaded = []
    for name, value in values.items():
        if override or not os.environ.get(name, "").strip():
            os.environ[name] = value
            loaded.append(name)
    return {"loaded": sorted(loaded), "present": sorted(values)}
