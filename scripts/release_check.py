"""Check selected release files without printing any matching secret values."""
import json
import os
import re
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
files = subprocess.check_output(["git", "ls-files", "-z", "--cached", "--others", "--exclude-standard"], cwd=ROOT).decode().split("\0")
secrets = [v.encode() for k, v in os.environ.items() if any(s in k.upper() for s in ("API_KEY", "SECRET", "PASSWORD", "ACCESS_TOKEN")) and len(v) > 12]
hits, checked = [], 0
for name in sorted(set(filter(None, files))):
    path = ROOT / name
    if not path.is_file():
        continue
    data = path.read_bytes()
    checked += 1
    reasons = []
    if any(value in data for value in secrets):
        reasons.append("configured credential value present")
    if re.search(rb"\b(?:sk-proj-|tvly-)[A-Za-z0-9_-]{20,}", data):
        reasons.append("credential-shaped token")
    if re.search(rb"-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----", data):
        reasons.append("private key marker")
    if reasons:
        hits.append({"file": name, "reasons": reasons})
result = {"status": "PASS" if not hits else "FAIL", "files_checked": checked, "findings": hits, "scope": "Known configured credentials, token patterns and private-key markers; not a guarantee against all sensitive content"}
print(json.dumps(result, indent=2))
raise SystemExit(bool(hits))
